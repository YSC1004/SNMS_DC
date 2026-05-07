"""
DataRouterConnMgr.py / DataRouterConnection.py
C++ DataRouterConnMgr.h/.C + DataRouterConnection.h/.C → Python 변환

DataRouter 프로세스 연결 관리자 + 개별 소켓 연결 처리.

특이사항:
  - ProcessId = "DATAROUTER_<SessionName>" 조합
  - 세션 식별 시 DATAROUTER_LISTEN + DATAHANDLER_CONNECT 포트 오픈 정보 2개 전송
  - RecvInitInfo: DataRouter에 AS_DATA_ROUTING_INIT 패킷 전달
"""

import asyncio
import logging
from typing import Optional

from Common.ProcConnectionMgr import ProcConnectionMgr  # process_dead (치트시트)
from Common.AsSocket import AsSocket                    # 가상함수 오버라이드 (치트시트)
from Common.AsUtil import AsUtil
from Common.CommTypeList import (
    AS_CMD_OPEN_PORT_T, AS_ASCII_ACK_T, AS_LOG_STATUS_T,
    AS_ASCII_ERROR_MSG_T, AS_DATA_ROUTING_INIT_T, AS_PROCESS_STATUS_T,
)
from Common.CommType import (
    ASCII_DATA_ROUTER,
    START, STOP, ORDER_KILL, LOG_DEL,
    CMD_OPEN_PORT, CMD_OPEN_PORT_ACK,
    AS_LOG_INFO, ASCII_ERROR_MSG, PROC_INIT_END,
    AS_DATA_ROUTING_INIT,
    DATAROUTER_LISTEN, DATAHANDLER_CONNECT,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DataRouterConnMgr
# =============================================================================

class DataRouterConnMgr(ProcConnectionMgr):
    """
    C++ DataRouterConnMgr (ProcConnectionMgr 상속) 대응.
    뮤텍스 없음 (RouterConnMgr과 동일).
    """

    def __init__(self) -> None:
        super().__init__()

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
                1, "The DataRouter(%s) is killed normally.", name)
        else:
            MAINPTR().ProcessDead(ASCII_DATA_ROUTER, name, pid)

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """C++: AcceptSocket()"""
        conn = DataRouterConnection(self)
        if not self.Accept(conn):
            logger.debug("Data Router Socket Accept Error : %s",
                         self.GetObjErrMsg())
            return
        self.add(conn)                              # ConnectionMgr.add()

    # =========================================================================
    # StopProcess
    # =========================================================================

    def StopProcess(self, data_handler_id: str) -> bool:
        """C++: StopProcess(string DataHandlerId)"""
        con: Optional[DataRouterConnection] = self.find_session(data_handler_id)
        if con is None:
            logger.debug("Can't Find Data Router : %s", data_handler_id)
            return False
        con.StopProcess()
        logger.debug("Data Router(%s) Stop", data_handler_id)
        return self.stop_process_by_name(data_handler_id)  # ProcConnectionMgr

    # =========================================================================
    # SendProcessInfo
    # =========================================================================

    def SendProcessInfo(self, session_name: str, status: int) -> None:
        """
        C++: SendProcessInfo(const char* SessionName, int Status)
        ProcessId = "DATAROUTER_<SessionName>" 조합.
        """
        from ProcNaManager.AsciiManagerWorld import AsciiManagerWorld

        proc_info = AS_PROCESS_STATUS_T()
        proc_info.ProcessId = (
            f"{AsUtil.GetProcessTypeString(ASCII_DATA_ROUTER)}_{session_name}")
        proc_info.Status      = status
        proc_info.ProcessType = ASCII_DATA_ROUTER

        if status == START:
            if not self.get_process_info_by_name(session_name, proc_info):
                return

        AsciiManagerWorld.m_WorldPtr.SendProcessInfo(proc_info)

    # =========================================================================
    # RecvInitInfo
    # =========================================================================

    def RecvInitInfo(self, init_info: AS_DATA_ROUTING_INIT_T) -> None:
        """C++: RecvInitInfo(AS_DATA_ROUTING_INIT_T*)"""
        con: Optional[DataRouterConnection] = self.find_session(
            init_info.DataHandlerId)                # ConnectionMgr.find_session()
        if con is None:
            logger.debug("Can't Find Data Router : %s",
                         init_info.DataHandlerId)
            return
        asyncio.ensure_future(con.SendInitInfo(init_info))


# =============================================================================
# DataRouterConnection
# =============================================================================

class DataRouterConnection(AsSocket):
    """
    C++ DataRouterConnection (AsSocket 상속) 대응.

    AsSocket 가상 메서드 오버라이드:
      receive_packet()              ← C++ ReceivePacket()
      close_socket()                ← C++ CloseSocket()
      session_identify_callback()   ← C++ SessionIdentify()
      alive_check_fail()            ← C++ AliveCheckFail()
      ReceiveTimeOut()              ← C++ ReceiveTimeOut()

    세션 식별 시 포트 오픈 2종 전송:
      1. DATAROUTER_LISTEN : DataRouter 리슨 소켓 경로
      2. DATAHANDLER_CONNECT: DataHandler IP/Port 접속 정보
    """

    def __init__(self, conn_mgr: DataRouterConnMgr) -> None:
        super().__init__()
        self._data_router_conn_mgr: DataRouterConnMgr = conn_mgr
        self._data_router_status:   bool              = True

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)"""
        if session_identify == ASCII_DATA_ROUTER:
            self._data_router_proc_req(packet)
        else:
            logger.debug("UnKnown Session : %d", session_identify)

    def session_identify_callback(self, session_type: int,
                                   session_name: str = "") -> None:
        """C++: virtual SessionIdentify(int SessionType, string SessionName)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        if not self._data_router_conn_mgr.add_session_name(session_name):  # ConnectionMgr
            self._close()
            self._data_router_conn_mgr.remove(self)  # ConnectionMgr.remove()
            return

        logger.debug("SessionType : %s, SessionName : %s",
                     AsUtil.GetProcessTypeString(session_type), session_name)

        self._data_router_conn_mgr.SendProcessInfo(
            self.GetSessionName(), START)

        # ① DATAROUTER_LISTEN: DataRouter 리슨 소켓 경로 전송
        open_port1 = AS_CMD_OPEN_PORT_T()
        open_port1.ProtocolType = DATAROUTER_LISTEN
        open_port1.Name         = session_name
        open_port1.PortPath     = MAINPTR().GetDataRouterListenSocketPath(
            self.GetSessionName())
        asyncio.ensure_future(self.CmdOpenPortInfo(open_port1))

        # ② DATAHANDLER_CONNECT: DataHandler 접속 정보 전송
        dh_info = MAINPTR().GetDataHandlerInfo(session_name)
        if dh_info:
            open_port2 = AS_CMD_OPEN_PORT_T()
            open_port2.ProtocolType = DATAHANDLER_CONNECT
            open_port2.Consumer     = dh_info.DataHandlerId
            open_port2.IpAddress    = dh_info.IpAddress
            open_port2.PortNo       = dh_info.ListenPort
            asyncio.ensure_future(self.CmdOpenPortInfo(open_port2))
        else:
            logger.error("Can't Find DataHandler Info : %s", session_name)

        self.StartAliveCheck(                       # AsSocket.StartAliveCheck
            MAINPTR().GetProcAliveCheckTime(),
            MAINPTR().GetAliveCheckLimitCnt(),
        )

    def close_socket(self, errno_val: int) -> None:
        """C++: virtual CloseSocket(int Errno)"""
        logger.debug("Socket Broken SessionName : %s", self.GetSessionName())
        self.SendLogStatus()

        if self._data_router_status:
            self._data_router_conn_mgr.child_process_dead(self)     # ProcConnectionMgr
        else:
            self._data_router_conn_mgr.child_process_dead(
                self, ORDER_KILL)

    def alive_check_fail(self, fail_count: int) -> None:
        """C++: virtual AliveCheckFail(int FailCount)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        logger.debug("Alive Check Fail(count : %d) Limite Over", fail_count)
        MAINPTR().SendAsciiError(
            1, "The process is killed on purpose for no reply from %s.",
            self.GetSessionName())
        self._data_router_conn_mgr.various_ack_check_time_out(self)  # ProcConnectionMgr

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """C++: ReceiveTimeOut(int Reason, void* ExtraReason)"""
        logger.debug("Unknown Time Out Reason : %d", reason)

    # =========================================================================
    # 패킷 처리
    # =========================================================================

    def _data_router_proc_req(self, packet) -> None:
        """C++: DataRouterProcReq(PACKET_T*)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        msg_id = packet.MsgId

        if msg_id == CMD_OPEN_PORT_ACK:
            self._cmd_open_port_ack(packet.Msg)

        elif msg_id == AS_LOG_INFO:
            MAINPTR().SendLogStatus(packet.Msg)

        elif msg_id == ASCII_ERROR_MSG:
            MAINPTR().SendAsciiError(packet.Msg)

        elif msg_id == PROC_INIT_END:
            pass                                    # C++ 원본 동일하게 처리 없음

        else:
            logger.error("Unknown Msg Id : %d", msg_id)

    def _cmd_open_port_ack(self, ack: AS_ASCII_ACK_T) -> None:
        """C++: CmdOpenPortAck(AS_ASCII_ACK_T*)"""
        logger.debug("Receive CmdOpenPortAck : %s, MsgId : %d",
                     self.GetSessionName(), ack.Id)
        if not ack.ResultMode:
            logger.debug("CmdOpen Error(%s) : %s",
                         self.GetSessionName(), ack.Result)

    # =========================================================================
    # 전송 메서드
    # =========================================================================

    async def CmdOpenPortInfo(self,
                               port_info: AS_CMD_OPEN_PORT_T) -> bool:
        """C++: CmdOpenPortInfo(AS_CMD_OPEN_PORT_T*) → CMD_OPEN_PORT 전송."""
        payload = _pack(port_info)
        await self.SendPacket(CMD_OPEN_PORT, payload, len(payload))
        return True                                 # C++ 원본: 항상 true

    async def SendInitInfo(self,
                            init_info: AS_DATA_ROUTING_INIT_T) -> None:
        """C++: SendPacket(AS_DATA_ROUTING_INIT, ...) — RecvInitInfo에서 호출."""
        payload = _pack(init_info)
        await self.SendPacket(AS_DATA_ROUTING_INIT, payload, len(payload))

    def SendLogStatus(self) -> None:
        """C++: SendLogStatus() — LOG_DEL 상태 전송."""
        from ProcNaManager.AsciiManagerWorld import AsciiManagerWorld

        log = AS_LOG_STATUS_T()
        log.name   = self.GetSessionName()
        log.logs   = (f"{AsUtil.GetProcessTypeString(self.GetSessionType())},"
                      f"{self.GetSessionName()},")
        log.status = LOG_DEL
        AsciiManagerWorld.m_WorldPtr.SendLogStatus(log)

    def StopProcess(self) -> None:
        """C++: StopProcess() — 정상 종료 플래그만 설정 (CMD_PROC_TERMINATE 없음)."""
        self._data_router_status = False


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''