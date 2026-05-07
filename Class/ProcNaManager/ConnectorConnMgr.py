"""
ConnectorConnMgr.py / ConnectorConnection.py
C++ ConnectorConnMgr.h/.C + ConnectorConnection.h/.C → Python 변환

Connector 프로세스 연결 관리자 + 개별 소켓 연결 처리.
  - ProcConnectionMgr 상속
  - MMC 명령 전달, 포트 오픈 정보 전달
  - Connector 세션 식별 후 SetConnectorProcStatus 호출
"""

import asyncio
import logging
import threading
from typing import Optional, TYPE_CHECKING

from Common.ProcConnectionMgr import ProcConnectionMgr  # process_dead (치트시트)
from Common.AsSocket import AsSocket                    # 가상함수 오버라이드 (치트시트)
from Common.AsUtil import AsUtil
from Common.CommTypeList import (
    AS_CMD_OPEN_PORT_T, AS_MMC_PUBLISH_T, AS_MMC_RESULT_T,
    AS_ASCII_ACK_T, AS_LOG_STATUS_T, AS_ASCII_ERROR_MSG_T,
    AS_PORT_STATUS_INFO_T, AS_SESSION_CONTROL_T, AS_PROCESS_STATUS_T,
)
from Common.CommType import (
    ASCII_CONNECTOR,
    START, STOP, ORDER_KILL, LOG_DEL,
    CMD_OPEN_PORT, CMD_OPEN_PORT_ACK,
    CMD_MMC_PUBLISH_REQ, PROC_INIT_END,
    AS_LOG_INFO, ASCII_ERROR_MSG, PORT_STATUS_INFO,
    MMC_RESPONSE_DATA, SESSION_CONTROL,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ConnectorConnMgr
# =============================================================================

class ConnectorConnMgr(ProcConnectionMgr):
    """
    C++ ConnectorConnMgr (ProcConnectionMgr 상속) 대응.

    뮤텍스:
      C++ pthread_mutex_t m_SocketRemoveLock
      → _socket_remove_lock() / _socket_remove_unlock() 오버라이드
    """

    def __init__(self) -> None:
        super().__init__()
        self._remove_lock = threading.Lock()        # C++: pthread_mutex_t

    # =========================================================================
    # ConnectionMgr 뮤텍스 오버라이드
    # =========================================================================

    def _socket_remove_lock(self) -> None:
        logger.debug("ConnectorConnMgr Lock")
        self._remove_lock.acquire()

    def _socket_remove_unlock(self) -> None:
        logger.debug("ConnectorConnMgr UnLock")
        self._remove_lock.release()

    # =========================================================================
    # ProcConnectionMgr 추상 메서드 구현
    # =========================================================================

    def process_dead(self, name: str, pid: int, status: int = -1) -> None:
        """C++: ProcessDead(string Name, int Pid, int Status)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        self.SendProcessInfo(name, STOP)

        if status == ORDER_KILL:
            MAINPTR().RemovePid(pid)
            MAINPTR().SendAsciiError(
                1, "%s is killed normally.", name)
        else:
            MAINPTR().ProcessDead(ASCII_CONNECTOR, name, pid)

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """C++: AcceptSocket()"""
        conn = ConnectorConnection(self)
        if not self.Accept(conn):
            logger.debug("Connect Socket Accept Error : %s",
                         self.GetObjErrMsg())
            return
        self.add(conn)                              # ConnectionMgr.add()

    # =========================================================================
    # StopProcess
    # =========================================================================

    def StopProcess(self, session_name: str) -> bool:
        """C++: StopProcess(string SessionName)"""
        con: Optional[ConnectorConnection] = self.find_session(session_name)
        if con is None:
            logger.debug("Can't Find Connector : %s", session_name)
            return False
        con.StopProcess()
        return self.stop_process_by_name(session_name)  # ProcConnectionMgr

    # =========================================================================
    # ConnectorInitEnd
    # =========================================================================

    def ConnectorInitEnd(self, session_name: str) -> None:
        """C++: ConnectorInitEnd(string SessionName)"""
        from ProcNaManager.AsciiManagerWorld import AsciiManagerWorld
        AsciiManagerWorld.m_WorldPtr.SetConnectorProcStatus(session_name)

    # =========================================================================
    # SendCmdOpenInfo
    # =========================================================================

    def SendCmdOpenInfo(self, port_info: AS_CMD_OPEN_PORT_T) -> bool:
        """C++: SendCmdOpenInfo(AS_CMD_OPEN_PORT_T*)"""
        if not self.CmdOpenPortInfo(port_info.ConnectorId, port_info):
            logger.debug("Can't Find Connector : %s", port_info.ConnectorId)
            return False
        return True

    def CmdOpenPortInfo(self, session_name: str,
                         port_info: AS_CMD_OPEN_PORT_T) -> bool:
        """C++: CmdOpenPortInfo(string SessionName, AS_CMD_OPEN_PORT_T*)"""
        con: Optional[ConnectorConnection] = self.find_session(session_name)
        if con is None:
            return False
        asyncio.ensure_future(con.CmdOpenPortInfo(port_info))
        return True

    # =========================================================================
    # SendMMCCommand
    # =========================================================================

    def SendMMCCommand(self, session_name: str,
                        mmc_com: AS_MMC_PUBLISH_T) -> bool:
        """C++: SendMMCCommand(const char* SessionName, AS_MMC_PUBLISH_T*)"""
        self._socket_remove_lock()
        try:
            con: Optional[ConnectorConnection] = self.find_session(session_name)
            if con is None:
                logger.debug("Can't Find Connector : %s", session_name)
                return False
            asyncio.ensure_future(con.SendMMCCommand(mmc_com))
            return True
        finally:
            self._socket_remove_unlock()

    # =========================================================================
    # SendSessionControl
    # =========================================================================

    def SendSessionControl(self,
                            session_ctl: AS_SESSION_CONTROL_T) -> None:
        """C++: SendSessionControl(AS_SESSION_CONTROL_T*)"""
        from ProcNaManager.AsciiManagerWorld import AsciiManagerWorld

        con: Optional[ConnectorConnection] = self.find_session(
            session_ctl.ConnectorId)
        if con is None:
            logger.debug("Can't Find Execute Connector(%s)",
                         session_ctl.ConnectorId)
            AsciiManagerWorld.m_WorldPtr.SendAsciiError(
                1, "Can't Find Execute Connector(%s)",
                session_ctl.ConnectorId)
            return
        asyncio.ensure_future(con.SendSessionControl(session_ctl))

    # =========================================================================
    # SendProcessInfo
    # =========================================================================

    def SendProcessInfo(self, session_name: str, status: int) -> None:
        """C++: SendProcessInfo(const char* SessionName, int Status)"""
        from ProcNaManager.AsciiManagerWorld import AsciiManagerWorld

        proc_info = AS_PROCESS_STATUS_T()
        proc_info.ProcessId   = session_name
        proc_info.Status      = status
        proc_info.ProcessType = ASCII_CONNECTOR

        if status == START:
            if not self.get_process_info_by_name(session_name, proc_info):
                return                              # ProcConnectionMgr

        AsciiManagerWorld.m_WorldPtr.SendProcessInfo(proc_info)


# =============================================================================
# ConnectorConnection
# =============================================================================

class ConnectorConnection(AsSocket):
    """
    C++ ConnectorConnection (AsSocket 상속) 대응.

    AsSocket 가상 메서드 오버라이드:
      receive_packet()              ← C++ ReceivePacket()
      close_socket()                ← C++ CloseSocket()
      session_identify_callback()   ← C++ SessionIdentify()
      alive_check_fail()            ← C++ AliveCheckFail()
      ReceiveTimeOut()              ← C++ ReceiveTimeOut()
    """

    def __init__(self, conn_mgr: ConnectorConnMgr) -> None:
        super().__init__()
        self._connector_conn_mgr: ConnectorConnMgr = conn_mgr
        self._connector_status:   bool             = True

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)"""
        if session_identify == ASCII_CONNECTOR:
            self._connector_proc_req(packet)
        else:
            logger.debug("UnKnown SessionType : %d", session_identify)

    def session_identify_callback(self, session_type: int,
                                   session_name: str = "") -> None:
        """C++: virtual SessionIdentify(int SessionType, string SessionName)"""
        from ProcNaManager.AsciiManagerWorld import AsciiManagerWorld

        if not self._connector_conn_mgr.add_session_name(session_name):  # ConnectionMgr
            self._close()
            self._connector_conn_mgr.remove(self)   # ConnectionMgr.remove()
            return

        logger.debug("SessionType : %s, SessionName : %s",
                     AsUtil.GetProcessTypeString(session_type), session_name)

        self._connector_conn_mgr.SendProcessInfo(
            self.GetSessionName(), START)

        self.StartAliveCheck(                       # AsSocket.StartAliveCheck
            AsciiManagerWorld.m_WorldPtr.GetProcAliveCheckTime(),
            AsciiManagerWorld.m_WorldPtr.GetAliveCheckLimitCnt(),
        )

    def close_socket(self, errno_val: int) -> None:
        """C++: virtual CloseSocket(int Errno)"""
        logger.debug("Socket Broken SessionName : %s", self.GetSessionName())

        if self._connector_status:
            self._connector_conn_mgr.child_process_dead(self)       # ProcConnectionMgr
        else:
            self._connector_conn_mgr.child_process_dead(self, ORDER_KILL)

    def alive_check_fail(self, fail_count: int) -> None:
        """C++: virtual AliveCheckFail(int FailCount)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        logger.debug("AliveCheckFail(%s) , Count : %d",
                     self.GetSessionName(), fail_count)
        MAINPTR().SendAsciiError(
            1, "The process is killed on purpose for no reply from %s.",
            self.GetSessionName())
        self._connector_conn_mgr.various_ack_check_time_out(self)   # ProcConnectionMgr

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """C++: ReceiveTimeOut(int Reason, void* ExtraReason)"""
        logger.error("Unknown Time Out Reason : %d", reason)

    # =========================================================================
    # 패킷 처리
    # =========================================================================

    def _connector_proc_req(self, packet) -> None:
        """C++: ConnectorProcReq(PACKET_T*)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        msg_id = packet.MsgId

        if msg_id == CMD_OPEN_PORT_ACK:
            self._cmd_open_port_ack(packet.Msg)

        elif msg_id == PROC_INIT_END:
            self._connector_conn_mgr.ConnectorInitEnd(self.GetSessionName())

        elif msg_id == AS_LOG_INFO:
            MAINPTR().SendLogStatus(packet.Msg)

        elif msg_id == ASCII_ERROR_MSG:
            MAINPTR().SendAsciiError(packet.Msg)

        elif msg_id == PORT_STATUS_INFO:
            MAINPTR().SendPortInfo(packet.Msg)

        elif msg_id == MMC_RESPONSE_DATA:
            self._receive_response_command(packet.Msg)

        else:
            logger.error("Unknown Msg Id : %d", msg_id)

    def _cmd_open_port_ack(self, ack: AS_ASCII_ACK_T) -> None:
        """C++: CmdOpenPortAck(AS_ASCII_ACK_T*)"""
        if not ack.ResultMode:
            logger.debug("CmdOpen Error(%s) : %s",
                         self.GetSessionName(), ack.Result)

    def _receive_response_command(self,
                                   mmc_result: AS_MMC_RESULT_T) -> None:
        """C++: ReceiveResponseCommand(AS_MMC_RESULT_T*)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        logger.debug("Receive MMC Cmd Response From Connector(%s)",
                     self.GetSessionName())
        logger.debug(" msgid(%d), resultMode(%s)",
                     mmc_result.id,
                     AsUtil.GetEnumTypeString(mmc_result.resultMode))
        MAINPTR().SendCommandResponse(mmc_result)

    # =========================================================================
    # 전송 메서드
    # =========================================================================

    async def CmdOpenPortInfo(self,
                               port_info: AS_CMD_OPEN_PORT_T) -> bool:
        """C++: CmdOpenPortInfo(AS_CMD_OPEN_PORT_T*) → CMD_OPEN_PORT 전송."""
        payload = _pack(port_info)
        if not await self.SendPacket(CMD_OPEN_PORT, payload, len(payload)):
            logger.debug("Connector Socket Broken : %s", self.GetSessionName())
            return False
        return True

    async def SendMMCCommand(self,
                              mmc_com: AS_MMC_PUBLISH_T) -> bool:
        """C++: SendMMCCommand(AS_MMC_PUBLISH_T*) → CMD_MMC_PUBLISH_REQ 전송."""
        payload = _pack(mmc_com)
        return await self.SendPacket(
            CMD_MMC_PUBLISH_REQ, payload, len(payload))

    def SendLogStatus(self) -> None:
        """C++: SendLogStatus() — LOG_DEL 상태 전송."""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        log = AS_LOG_STATUS_T()
        log.name   = self.GetSessionName()
        log.logs   = (f"{AsUtil.GetProcessTypeString(self.GetSessionType())},"
                      f"{self.GetSessionName()},")
        log.status = LOG_DEL
        MAINPTR().SendLogStatus(log)

    async def SendSessionControl(self,
                                  session_ctl: AS_SESSION_CONTROL_T) -> None:
        """C++: SendSessionControl(AS_SESSION_CONTROL_T*)"""
        payload = _pack(session_ctl)
        await self.SendPacket(SESSION_CONTROL, payload, len(payload))

    def StopProcess(self) -> None:
        """C++: StopProcess() — 정상 종료 플래그 설정."""
        self._connector_status = False


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''