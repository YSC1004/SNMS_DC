"""
RuleDownLoaderConnection.py
C++ RuleDownLoaderConnection.h/.C → Python 변환

RuleDownLoader 프로세스 개별 소켓 연결 처리.
  - 파싱/매핑 룰 다운 ACK 수신 → ConnMgr 전달
  - 세션 식별 후 AliveCheck 시작
  - 소켓 종료 시 ChildProcessDead 처리
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from Common.AsSocket import AsSocket                    # 가상함수 오버라이드 (치트시트)
from Common.AsUtil import AsUtil
from Common.CommTypeList import (
    AS_LOG_STATUS_T, AS_ASCII_ACK_T,
)
from Common.CommType import (
    ASCII_RULE_DOWNLOADER,
    START, LOG_DEL,
    CMD_PARSING_RULE_DOWN, CMD_MAPPING_RULE_DOWN,
    CMD_PARSING_RULE_DOWN_ACK, CMD_MAPPING_RULE_DOWN_ACK,
    AS_LOG_INFO,
)

if TYPE_CHECKING:
    from ProcNaServer.RuleDownLoaderConnMgr import RuleDownLoaderConnMgr

logger = logging.getLogger(__name__)


class RuleDownLoaderConnection(AsSocket):
    """
    C++ RuleDownLoaderConnection (AsSocket 상속) 대응.

    AsSocket 가상 메서드 오버라이드:
      receive_packet()              ← C++ ReceivePacket()
      close_socket()                ← C++ CloseSocket()
      session_identify_callback()   ← C++ SessionIdentify()
    """

    def __init__(self, conn_mgr: "RuleDownLoaderConnMgr") -> None:
        super().__init__()
        self._rule_down_conn_mgr: "RuleDownLoaderConnMgr" = conn_mgr

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)"""
        if session_identify == ASCII_RULE_DOWNLOADER:
            self._rule_down_loader_req(packet)
        else:
            logger.debug("UnKnown Session : %d", session_identify)

    def session_identify_callback(self, session_type: int,
                                   session_name: str = "") -> None:
        """C++: virtual SessionIdentify(int SessionType, string SessionName)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        logger.debug("Session Identify : Type(%s), SessionName(%s)",
                     AsUtil.GetProcessTypeString(session_type), session_name)

        if not self._rule_down_conn_mgr.add_session_name(session_name):  # ConnectionMgr.add_session_name()
            self._close()
            self._rule_down_conn_mgr.remove(self)   # ConnectionMgr.remove()
            return

        # AliveCheck 시작 (AsSocket.StartAliveCheck)
        self.StartAliveCheck(
            MAINPTR().GetProcAliveCheckTime(),      # AsWorld.GetProcAliveCheckTime()
            MAINPTR().GetAliveCheckLimitCnt(),      # AsWorld.GetAliveCheckLimitCnt()
        )
        self._rule_down_conn_mgr.SendProcessInfo(
            self.GetSessionName(), START)
        self._rule_down_conn_mgr.SetRuleDownConn(self)

    def close_socket(self, errno_val: int) -> None:
        """C++: virtual CloseSocket(int Errno)"""
        session_name = self.GetSessionName()
        logger.debug("Socket Broken : %s", session_name)

        # 로그 상태 DEL (C++ 원본에서 logStatus를 만들지만 UpdateProcessLogStatus 미호출 — 동일 유지)
        log_status = AS_LOG_STATUS_T()
        log_status.name   = session_name
        log_status.status = LOG_DEL
        log_status.logs   = (
            f"sun,{AsUtil.GetProcessTypeString(self.GetSessionType())},"
            f"{session_name},"
        )
        # C++ 원본: UpdateProcessLogStatus 호출 없이 바로 ChildProcessDead
        self._rule_down_conn_mgr.child_process_dead(self)  # ProcConnectionMgr.child_process_dead()

    # =========================================================================
    # 패킷 처리
    # =========================================================================

    def _rule_down_loader_req(self, packet) -> None:
        """C++: RuleDownLoaderReq(PACKET_T*)"""
        msg_id = packet.MsgId

        if msg_id == CMD_PARSING_RULE_DOWN_ACK:
            self._rule_down_conn_mgr.RecvRuleDownAck(packet.Msg)

        elif msg_id == CMD_MAPPING_RULE_DOWN_ACK:
            self._rule_down_conn_mgr.RecvMappingRuleDownAck(packet.Msg)

        elif msg_id == AS_LOG_INFO:
            self._rule_down_conn_mgr.UpdateProcessLogStatus(packet.Msg)

        else:
            logger.error("Unknown Msg Id : %d", msg_id)

    # =========================================================================
    # Rule Down 명령 전송
    # =========================================================================

    async def SendCmdParsingRuleDown(self) -> None:
        """C++: SendCmdParsingRuleDown() → CMD_PARSING_RULE_DOWN 패킷 전송."""
        logger.info("Send Rule Down Cmd")
        await self.SendPacket(CMD_PARSING_RULE_DOWN)

    async def SendCmdMappingRuleDown(self) -> None:
        """C++: SendCmdMappingRuleDown() → CMD_MAPPING_RULE_DOWN 패킷 전송."""
        logger.info("Send Mapping Rule Down Cmd")
        await self.SendPacket(CMD_MAPPING_RULE_DOWN)