"""
GuiConnMgr.py
C++ GuiConnMgr.h/.C → Python 변환

GUI 클라이언트 연결 관리자.
  - GuiConnection Accept 관리
  - 전체 GUI 세션에 상태/에러/InfoChange 브로드캐스트
  - Rule Down 요청/결과 중계 (Parsing/Mapping/Scheduler/Command)
"""

import asyncio
import logging
from typing import Optional, TYPE_CHECKING

from Common.ConnectionMgr import ConnectionMgr          # add/remove/find_session (소문자)
from Common.CommTypeList import (
    AS_LOG_STATUS_T, AS_ASCII_ERROR_MSG_T, AS_ASCII_ACK_T,
    AS_CONNECTION_INFO_T, AS_CONNECTOR_INFO_T, AS_MANAGER_INFO_T,
    AS_PROCESS_STATUS_T, AS_DATA_HANDLER_INFO_T,
    AS_COMMAND_AUTHORITY_INFO_T, AS_SYSTEM_INFO_T,
    AS_SESSION_CFG_T, AS_SUB_PROC_INFO_T,
)
from Common.CommType import (
    GUI_ASCII_STATUS_INFO, GUI_ASCII_CONFIG_INFO,
    AS_LOG_INFO, ASCII_ERROR_MSG,
    AS_CONNECTION_INFO, AS_CONNECTOR_INFO, AS_MANAGER_INFO,
    AS_PROCESS_INFO, AS_DATA_HANDLER_INFO,
    AS_COMMAND_AUTHORITY_INFO, AS_SYSTEM_INFO,
    AS_SESSION_CFG, AS_SUB_PROC_INFO,
    CMD_PARSING_RULE_DOWN_ACK, CMD_MAPPING_RULE_DOWN_ACK,
    CMD_SCHEDULER_RULE_DOWN_ACK, CMD_COMMAND_RULE_DOWN_ACK,
)

if TYPE_CHECKING:
    from ProcNaServer.GuiConnection import GuiConnection

logger = logging.getLogger(__name__)


class GuiConnMgr(ConnectionMgr):
    """
    C++ GuiConnMgr (ConnectionMgr 상속) 대응.

    Rule Down 요청 커넥션 포인터:
      C++ GuiConnection* → Optional[GuiConnection]
      연결 유효성은 is_valid_connection() 으로 확인.
    """

    def __init__(self) -> None:
        super().__init__()
        self._parsing_rule_down_req_con:   Optional["GuiConnection"] = None
        self._mapping_rule_down_req_con:   Optional["GuiConnection"] = None
        self._scheduler_rule_down_req_con: Optional["GuiConnection"] = None
        self._command_rule_down_req_con:   Optional["GuiConnection"] = None

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """C++: AcceptSocket()"""
        from ProcNaServer.GuiConnection import GuiConnection

        conn = GuiConnection(self)
        if not self.Accept(conn):
            logger.debug("Gui Socket Accept Error : %s", self.GetObjErrMsg())
            return

        self.add(conn)                              # ConnectionMgr.add()
        logger.debug("Connection Gui(%s)", conn.get_peer_ip())  # AsSocket.get_peer_ip()

    # =========================================================================
    # SendLogStatus / SendAsciiError
    # =========================================================================

    def SendLogStatus(self, status: AS_LOG_STATUS_T) -> None:
        """C++: SendLogStatus() — GUI_ASCII_STATUS_INFO 세션에만 전송."""
        payload = _pack(status)
        to_remove = []
        for sock in list(self._socket_connection_list):
            if sock.GetSessionType() == GUI_ASCII_STATUS_INFO:
                if not asyncio.ensure_future(
                        sock.SendPacket(AS_LOG_INFO, payload, len(payload))):
                    to_remove.append(sock)
        for sock in to_remove:
            self.remove(sock)                       # ConnectionMgr.remove()

    def SendAsciiError(self, err_msg: AS_ASCII_ERROR_MSG_T) -> None:
        """C++: SendAsciiError() — GUI_ASCII_STATUS_INFO 세션에만 전송."""
        to_remove = []
        for sock in list(self._socket_connection_list):
            gui_con: "GuiConnection" = sock
            if gui_con.GetSessionType() == GUI_ASCII_STATUS_INFO:
                if not _run(gui_con.SendAsciiError(err_msg)):
                    to_remove.append(gui_con)
        for sock in to_remove:
            self.remove(sock)

    # =========================================================================
    # SendInfoChange (타입 오버로드 → 타입 분기)
    # =========================================================================

    def SendInfoChange(self, info) -> None:
        """
        C++ 오버로드 9종 → 타입 분기.
        세션 타입별 필터링 후 해당 패킷 브로드캐스트.
        """
        dispatch = {
            AS_CONNECTION_INFO_T:        self._send_connection_info,
            AS_CONNECTOR_INFO_T:         self._send_connector_info,
            AS_MANAGER_INFO_T:           self._send_manager_info,
            AS_PROCESS_STATUS_T:         self._send_process_info,
            AS_DATA_HANDLER_INFO_T:      self._send_data_handler_info,
            AS_COMMAND_AUTHORITY_INFO_T: self._send_command_authority_info,
            AS_SYSTEM_INFO_T:            self._send_system_info,
            AS_SESSION_CFG_T:            self._send_session_cfg,
            AS_SUB_PROC_INFO_T:          self._send_sub_proc_info,
        }
        handler = dispatch.get(type(info))
        if handler:
            handler(info)
        else:
            logger.debug("SendInfoChange: Unknown type %s", type(info))

    # ── 개별 InfoChange 브로드캐스트 ─────────────────────────────────────────

    def _broadcast(self, msg_id: int, payload: bytes,
                   *allowed_session_types: int) -> None:
        """allowed_session_types 에 해당하는 세션에만 패킷 브로드캐스트."""
        to_remove = []
        for sock in list(self._socket_connection_list):
            if sock.GetSessionType() in allowed_session_types:
                fut = asyncio.ensure_future(
                    sock.SendPacket(msg_id, payload, len(payload)))
                # SendPacket 실패 처리는 close_socket 에서 담당
        for sock in to_remove:
            self.remove(sock)

    def _send_connection_info(self, info: AS_CONNECTION_INFO_T) -> None:
        logger.debug("SendInfoChange AS_CONNECTION_INFO_T")
        self._broadcast(AS_CONNECTION_INFO, _pack(info),
                        GUI_ASCII_STATUS_INFO, GUI_ASCII_CONFIG_INFO)

    def _send_connector_info(self, info: AS_CONNECTOR_INFO_T) -> None:
        logger.debug("SendInfoChange AS_CONNECTOR_INFO_T")
        self._broadcast(AS_CONNECTOR_INFO, _pack(info),
                        GUI_ASCII_STATUS_INFO, GUI_ASCII_CONFIG_INFO)

    def _send_manager_info(self, info: AS_MANAGER_INFO_T) -> None:
        logger.debug("SendInfoChange AS_MANAGER_INFO_T")
        self._broadcast(AS_MANAGER_INFO, _pack(info),
                        GUI_ASCII_STATUS_INFO, GUI_ASCII_CONFIG_INFO)

    def _send_process_info(self, info: AS_PROCESS_STATUS_T) -> None:
        logger.debug("SendInfoChange AS_PROCESS_STATUS_T")
        self._broadcast(AS_PROCESS_INFO, _pack(info),
                        GUI_ASCII_STATUS_INFO)

    def _send_data_handler_info(self, info: AS_DATA_HANDLER_INFO_T) -> None:
        logger.debug("SendInfoChange AS_DATA_HANDLER_INFO_T")
        self._broadcast(AS_DATA_HANDLER_INFO, _pack(info),
                        GUI_ASCII_STATUS_INFO, GUI_ASCII_CONFIG_INFO)

    def _send_command_authority_info(self,
                                      info: AS_COMMAND_AUTHORITY_INFO_T) -> None:
        logger.debug("SendInfoChange AS_COMMAND_AUTHORITY_INFO_T")
        self._broadcast(AS_COMMAND_AUTHORITY_INFO, _pack(info),
                        GUI_ASCII_STATUS_INFO, GUI_ASCII_CONFIG_INFO)

    def _send_system_info(self, info: AS_SYSTEM_INFO_T) -> None:
        self._broadcast(AS_SYSTEM_INFO, _pack(info),
                        GUI_ASCII_STATUS_INFO)

    def _send_session_cfg(self, info: AS_SESSION_CFG_T) -> None:
        self._broadcast(AS_SESSION_CFG, _pack(info),
                        GUI_ASCII_STATUS_INFO)

    def _send_sub_proc_info(self, info: AS_SUB_PROC_INFO_T) -> None:
        logger.debug("SendInfoChange AS_SUB_PROC_INFO_T")
        self._broadcast(AS_SUB_PROC_INFO, _pack(info),
                        GUI_ASCII_STATUS_INFO, GUI_ASCII_CONFIG_INFO)

    # =========================================================================
    # Rule Down 요청 / 결과
    # =========================================================================

    def CmdParsingRuleDown(self, req_con: "GuiConnection") -> None:
        """C++: CmdParsingRuleDown(GuiConnection*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR
        self._parsing_rule_down_req_con = req_con
        logger.debug("Rule Down Request(%s)", req_con.get_peer_ip())
        MAINPTR().CmdParsingRuleDown()

    def RecvParsingRuleDownResult(self, ack: AS_ASCII_ACK_T) -> None:
        """C++: RecvParsingRuleDownResult(AS_ASCII_ACK_T*)"""
        logger.debug("Send Parsing Rule Down Result to GUI")
        con = self._parsing_rule_down_req_con
        if con and self.is_valid_connection(con):   # ConnectionMgr.is_valid_connection()
            asyncio.ensure_future(
                con.SendPacket(CMD_PARSING_RULE_DOWN_ACK, _pack(ack), _size(ack)))
        self._parsing_rule_down_req_con = None

    def CmdMappingRuleDown(self, req_con: "GuiConnection") -> None:
        """C++: CmdMappingRuleDown(GuiConnection*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR
        self._mapping_rule_down_req_con = req_con
        MAINPTR().CmdMappingRuleDown()

    def RecvMappingRuleDownResult(self, ack: AS_ASCII_ACK_T) -> None:
        """C++: RecvMappingRuleDownResult(AS_ASCII_ACK_T*)"""
        logger.debug("Send MappingRuleDown Result to GUI")
        con = self._mapping_rule_down_req_con
        if con and self.is_valid_connection(con):
            asyncio.ensure_future(
                con.SendPacket(CMD_MAPPING_RULE_DOWN_ACK, _pack(ack), _size(ack)))
        self._mapping_rule_down_req_con = None

    def CmdSchedulerRuleDonw(self, req_con: "GuiConnection") -> None:
        """C++: CmdSchedulerRuleDonw(GuiConnection*) — 오타 유지"""
        from ProcNaServer.AsciiServerWorld import MAINPTR
        self._scheduler_rule_down_req_con = req_con
        MAINPTR().CmdSchedulerRuleDown()

    def RecvSchedulerRuleDownResult(self, ack: AS_ASCII_ACK_T) -> None:
        """C++: RecvSchedulerRuleDownResult(AS_ASCII_ACK_T*)"""
        logger.debug("Send Scheduler RuleDown Result to GUI")
        con = self._scheduler_rule_down_req_con
        if con and self.is_valid_connection(con):
            asyncio.ensure_future(
                con.SendPacket(CMD_SCHEDULER_RULE_DOWN_ACK, _pack(ack), _size(ack)))
        self._scheduler_rule_down_req_con = None

    def CmdCommandRuleDown(self, req_con: "GuiConnection") -> None:
        """C++: CmdCommandRuleDown(GuiConnection*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR
        self._command_rule_down_req_con = req_con
        MAINPTR().CmdCommandRuleDown()

    def RecvCommandRuleDownResult(self, ack: AS_ASCII_ACK_T) -> None:
        """C++: RecvCommandRuleDownResult(AS_ASCII_ACK_T*)"""
        logger.debug("Send Command Rule Down Result to GUI")
        con = self._command_rule_down_req_con
        if con and self.is_valid_connection(con):
            asyncio.ensure_future(
                con.SendPacket(CMD_COMMAND_RULE_DOWN_ACK, _pack(ack), _size(ack)))
        self._command_rule_down_req_con = None

    # =========================================================================
    # RemoveRequestConn
    # =========================================================================

    def RemoveRequestConn(self, conn: "GuiConnection") -> None:
        """C++: RemoveRequestConn(GuiConnection*) — 소켓 종료 시 요청 포인터 정리."""
        for attr in ("_parsing_rule_down_req_con",
                     "_mapping_rule_down_req_con",
                     "_scheduler_rule_down_req_con",
                     "_command_rule_down_req_con"):
            if getattr(self, attr) is conn:
                setattr(self, attr, None)
                return


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    """CommTypeList 구조체 → bytes. pack() 메서드가 있으면 사용."""
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''

def _size(obj) -> int:
    payload = _pack(obj)
    return len(payload)

def _run(coro) -> bool:
    """동기 컨텍스트에서 코루틴 결과를 얻어야 할 때 사용 (블로킹 주의)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(coro)
            return True
        return loop.run_until_complete(coro)
    except Exception:
        return False