"""
ParserConnMgr.py / ParserConnection.py
C++ ParserConnMgr.h/.C + ParserConnection.h/.C → Python 변환

Parser 프로세스 연결 관리자 + 개별 소켓 연결 처리.
  - ConnectorConnMgr/Connection과 대칭적 구조
  - 세션 식별 시 PARSER_LISTEN 포트 정보 전달
  - 룰 다운 명령 브로드캐스트
  - DataHandlerInfo 브로드캐스트
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
    AS_DATA_HANDLER_INFO_T, AS_RULE_CHANGE_INFO_T, AS_PROCESS_STATUS_T,
)
from Common.CommType import (
    ASCII_PARSER,
    START, STOP, ORDER_KILL, LOG_DEL,
    CMD_OPEN_PORT, CMD_OPEN_PORT_ACK,
    CMD_PARSING_RULE_DOWN, CMD_MAPPING_RULE_DOWN,
    CMD_PARSING_RULE_CHANGE,
    AS_LOG_INFO, ASCII_ERROR_MSG,
    PROC_INIT_END, MMC_RESPONSE_DATA,
    MMC_RESPONSE_DATA_REQ, AS_DATA_HANDLER_INFO,
    PARSER_LISTEN,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ParserConnMgr
# =============================================================================

class ParserConnMgr(ProcConnectionMgr):
    """
    C++ ParserConnMgr (ProcConnectionMgr 상속) 대응.
    ConnectorConnMgr과 대칭적 구조.
    """

    def __init__(self) -> None:
        super().__init__()
        self._remove_lock = threading.Lock()        # C++: pthread_mutex_t

    # =========================================================================
    # ConnectionMgr 뮤텍스 오버라이드
    # =========================================================================

    def _socket_remove_lock(self) -> None:
        self._remove_lock.acquire()

    def _socket_remove_unlock(self) -> None:
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
            MAINPTR().SendAsciiError(1, "%s is killed normally.", name)
        else:
            MAINPTR().ProcessDead(ASCII_PARSER, name, pid)

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """C++: AcceptSocket()"""
        conn = ParserConnection(self)
        if not self.Accept(conn):
            logger.debug("Parser Socket Accept Error : %s",
                         self.GetObjErrMsg())
            return
        self.add(conn)                              # ConnectionMgr.add()

    # =========================================================================
    # ParserStart
    # =========================================================================

    def ParserStart(self, conn: "ParserConnection") -> None:
        """
        C++: ParserStart(ParserConnection* Conn)
        Parser PROC_INIT_END 수신 후 호출.
        SetParserProcStatus + DataHandlerInfo 전송.
        """
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        if MAINPTR().SetParserProcStatus(conn.GetSessionName()):
            info_map = MAINPTR().GetDataHandlerInfoMap()
            asyncio.ensure_future(
                self._send_data_handler_info_to_conn(conn, info_map))

    async def _send_data_handler_info_to_conn(
            self, conn: "ParserConnection",
            info_map: dict) -> None:
        """DataHandlerInfo 목록을 특정 Parser 세션에 전송."""
        for info in info_map.values():
            payload = _pack(info)
            if not await conn.SendPacket(
                    AS_DATA_HANDLER_INFO, payload, len(payload)):
                return

    # =========================================================================
    # SendDataHandlerInfo
    # =========================================================================

    def SendDataHandlerInfo(self, info: AS_DATA_HANDLER_INFO_T) -> None:
        """C++: SendDataHandlerInfo(AS_DATA_HANDLER_INFO_T*) — 전체 Parser에 브로드캐스트."""
        payload = _pack(info)
        for sock in self._socket_connection_list:
            asyncio.ensure_future(
                sock.SendPacket(AS_DATA_HANDLER_INFO, payload, len(payload)))

    # =========================================================================
    # SendRouterConnInfo (C++ 원본 주석 처리 — no-op)
    # =========================================================================

    def SendRouterConnInfo(self, router_name: str) -> None:
        """C++: SendRouterConnInfo(string RouterName) — C++ 원본 전체 주석 처리."""
        pass

    # =========================================================================
    # SendResponseCommand
    # =========================================================================

    def SendResponseCommand(self, session_name: str,
                             mmc_com: AS_MMC_PUBLISH_T) -> bool:
        """C++: SendResponseCommand(const char* SessionName, AS_MMC_PUBLISH_T*)"""
        self._socket_remove_lock()
        try:
            con: Optional[ParserConnection] = self.find_session(session_name)
            if con is None:
                logger.debug("Can't Find Parser : %s", session_name)
                return False
            asyncio.ensure_future(con.SendResponseCommand(mmc_com))
            return True
        finally:
            self._socket_remove_unlock()

    # =========================================================================
    # StopProcess
    # =========================================================================

    def StopProcess(self, session_name: str) -> bool:
        """C++: StopProcess(string SessionName)"""
        con: Optional[ParserConnection] = self.find_session(session_name)
        if con is None:
            logger.debug("Can't Find Parser : %s", session_name)
            return False
        con.StopProcess()
        return self.stop_process_by_name(session_name)  # ProcConnectionMgr

    # =========================================================================
    # SendProcessInfo
    # =========================================================================

    def SendProcessInfo(self, session_name: str, status: int) -> None:
        """C++: SendProcessInfo(const char* SessionName, int Status)"""
        from ProcNaManager.AsciiManagerWorld import AsciiManagerWorld

        proc_info = AS_PROCESS_STATUS_T()
        proc_info.ProcessId   = session_name
        proc_info.Status      = status
        proc_info.ProcessType = ASCII_PARSER

        if status == START:
            if not self.get_process_info_by_name(session_name, proc_info):
                return

        AsciiManagerWorld.m_WorldPtr.SendProcessInfo(proc_info)

    # =========================================================================
    # 룰 다운 브로드캐스트
    # =========================================================================

    def SendCmdRuleDown(self) -> None:
        """C++: SendCmdRuleDown() — 전체 Parser에 CMD_PARSING_RULE_DOWN 전송."""
        for sock in self._socket_connection_list:
            asyncio.ensure_future(
                sock.SendPacket(CMD_PARSING_RULE_DOWN))

    def SendCmdMappingRuleDown(self) -> None:
        """C++: SendCmdMappingRuleDown() — 전체 Parser에 CMD_MAPPING_RULE_DOWN 전송."""
        for sock in self._socket_connection_list:
            asyncio.ensure_future(
                sock.SendPacket(CMD_MAPPING_RULE_DOWN))

    # =========================================================================
    # ParserRuleChange
    # =========================================================================

    def ParserRuleChange(self,
                          change_info: AS_RULE_CHANGE_INFO_T) -> None:
        """C++: ParserRuleChange(AS_RULE_CHANGE_INFO_T*)"""
        self._socket_remove_lock()
        try:
            con: Optional[ParserConnection] = self.find_session(
                change_info.ProcessId)
            if con is None:
                logger.debug("Can't Find Parser : %s", change_info.ProcessId)
                return
            asyncio.ensure_future(con.ParserRuleChange(change_info))
        finally:
            self._socket_remove_unlock()


# =============================================================================
# ParserConnection
# =============================================================================

class ParserConnection(AsSocket):
    """
    C++ ParserConnection (AsSocket 상속) 대응.

    AsSocket 가상 메서드 오버라이드:
      receive_packet()              ← C++ ReceivePacket()
      close_socket()                ← C++ CloseSocket()
      session_identify_callback()   ← C++ SessionIdentify()
      alive_check_fail()            ← C++ AliveCheckFail()
      ReceiveTimeOut()              ← C++ ReceiveTimeOut()

    ConnectorConnection과의 차이:
      - 세션 식별 시 PARSER_LISTEN 포트 오픈 정보 전송
      - PROC_INIT_END → ParserConnMgr.ParserStart()
      - SendCmdRuleDown / SendCmdMappingRuleDown 개별 전송
    """

    def __init__(self, conn_mgr: ParserConnMgr) -> None:
        super().__init__()
        self._parser_conn_mgr: ParserConnMgr = conn_mgr
        self._parser_status:   bool          = True    # C++: m_ParserStaus (오타 유지)

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)"""
        if session_identify == ASCII_PARSER:
            self._parser_proc_req(packet)
        else:
            logger.debug("UnKnown Session : %d", session_identify)

    def session_identify_callback(self, session_type: int,
                                   session_name: str = "") -> None:
        """C++: virtual SessionIdentify(int SessionType, string SessionName)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        if not self._parser_conn_mgr.add_session_name(session_name):  # ConnectionMgr
            self._close()
            self._parser_conn_mgr.remove(self)      # ConnectionMgr.remove()
            return

        logger.debug("SessionType : %s, SessionName : %s",
                     AsUtil.GetProcessTypeString(session_type), session_name)

        # PARSER_LISTEN 포트 오픈 정보 전송
        open_port = AS_CMD_OPEN_PORT_T()
        open_port.ProtocolType = PARSER_LISTEN
        socket_path = MAINPTR().GetParserListenSocketPath(
            self.GetSessionName())
        logger.debug("socketPath : %s", socket_path)
        open_port.PortPath = socket_path
        asyncio.ensure_future(self.CmdOpenPortInfo(open_port))

        self._parser_conn_mgr.SendProcessInfo(
            self.GetSessionName(), START)

        self.StartAliveCheck(                       # AsSocket.StartAliveCheck
            MAINPTR().GetProcAliveCheckTime(),
            MAINPTR().GetAliveCheckLimitCnt(),
        )

    def close_socket(self, errno_val: int) -> None:
        """C++: virtual CloseSocket(int Errno)"""
        logger.debug("Socket Broken SessionName : %s", self.GetSessionName())
        self.SendLogStatus()

        if self._parser_status:
            self._parser_conn_mgr.child_process_dead(self)          # ProcConnectionMgr
        else:
            self._parser_conn_mgr.child_process_dead(self, ORDER_KILL)

    def alive_check_fail(self, fail_count: int) -> None:
        """C++: virtual AliveCheckFail(int FailCount)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        logger.debug("AliveCheckFail(%s) , Count : %d",
                     self.GetSessionName(), fail_count)
        MAINPTR().SendAsciiError(
            1, "The Process is killed on purpose for no reply from %s.",
            self.GetSessionName())
        self._parser_conn_mgr.various_ack_check_time_out(self)      # ProcConnectionMgr

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """C++: ReceiveTimeOut(int Reason, void* ExtraReason)"""
        logger.error("Unknown Time Out Reason : %d", reason)

    # =========================================================================
    # 패킷 처리
    # =========================================================================

    def _parser_proc_req(self, packet) -> None:
        """C++: ParserProcReq(PACKET_T*)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        msg_id = packet.MsgId

        if msg_id == CMD_OPEN_PORT_ACK:
            self._cmd_open_port_ack(packet.Msg)

        elif msg_id == MMC_RESPONSE_DATA:
            self._receive_response_command(packet.Msg)

        elif msg_id == AS_LOG_INFO:
            MAINPTR().SendLogStatus(packet.Msg)

        elif msg_id == ASCII_ERROR_MSG:
            MAINPTR().SendAsciiError(packet.Msg)

        elif msg_id == PROC_INIT_END:
            self._parser_conn_mgr.ParserStart(self)

        else:
            logger.debug("Unknown Msg Id : %d", msg_id)

    def _cmd_open_port_ack(self, ack: AS_ASCII_ACK_T) -> None:
        """C++: CmdOpenPortAck(AS_ASCII_ACK_T*)"""
        if not ack.ResultMode:
            logger.debug("CmdOpen Error(%s) : %s",
                         self.GetSessionName(), ack.Result)

    def _receive_response_command(self,
                                   mmc_result: AS_MMC_RESULT_T) -> None:
        """C++: ReceiveResponseCommand(AS_MMC_RESULT_T*)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        logger.debug("Receive MMC Cmd Response : msgid(%d), resultMode(%s)",
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
        await self.SendPacket(CMD_OPEN_PORT, payload, len(payload))
        return True                                 # C++ 원본: 항상 true

    async def SendResponseCommand(self,
                                   mmc_com: AS_MMC_PUBLISH_T) -> None:
        """C++: SendResponseCommand(AS_MMC_PUBLISH_T*) → MMC_RESPONSE_DATA_REQ 전송."""
        payload = _pack(mmc_com)
        await self.SendPacket(MMC_RESPONSE_DATA_REQ, payload, len(payload))

    def SendLogStatus(self) -> None:
        """C++: SendLogStatus() — LOG_DEL 상태 전송."""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        log = AS_LOG_STATUS_T()
        log.name   = self.GetSessionName()
        log.logs   = (f"{AsUtil.GetProcessTypeString(self.GetSessionType())},"
                      f"{self.GetSessionName()},")
        log.status = LOG_DEL
        MAINPTR().SendLogStatus(log)

    async def SendCmdRuleDown(self) -> None:
        """C++: SendCmdRuleDown() → CMD_PARSING_RULE_DOWN 전송."""
        await self.SendPacket(CMD_PARSING_RULE_DOWN)

    async def SendCmdMappingRuleDown(self) -> None:
        """C++: SendCmdMappingRuleDown() → CMD_MAPPING_RULE_DOWN 전송."""
        await self.SendPacket(CMD_MAPPING_RULE_DOWN)

    async def ParserRuleChange(self,
                                change_info: AS_RULE_CHANGE_INFO_T) -> None:
        """C++: ParserRuleChange(AS_RULE_CHANGE_INFO_T*) → CMD_PARSING_RULE_CHANGE 전송."""
        payload = _pack(change_info)
        await self.SendPacket(
            CMD_PARSING_RULE_CHANGE, payload, len(payload))

    def StopProcess(self) -> None:
        """C++: StopProcess() — 정상 종료 플래그 설정."""
        self._parser_status = False


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''