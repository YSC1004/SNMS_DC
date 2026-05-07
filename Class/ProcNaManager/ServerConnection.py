"""
ProcNaManager/ServerConnection.py
C++ ServerConnection.h/.C (procNaManager) → Python 변환

procNaServer와의 TCP 소켓 연결 처리.
  - procNaServer로부터 CMD_OPEN_PORT / CMD_MMC_PUBLISH_REQ 등 수신
  - procNaServer로 PROCESS_INFO / PORT_STATUS_INFO / MMC_RESULT 등 전송
  - 소켓 종료 시 프로세스 종료 (SIGINT → sys.exit)

※ ProcNaServer의 ServerConnection(Active↔Standby)과 다른 별개 클래스.
"""

import asyncio
import logging
import os
import signal
import sys
from typing import List, TYPE_CHECKING

from Common.AsSocket import AsSocket                    # 가상함수 오버라이드 (치트시트)
from Common.CommTypeList import (
    AS_CMD_OPEN_PORT_T, AS_MMC_PUBLISH_T, AS_MMC_RESULT_T,
    AS_LOG_STATUS_T, AS_CMD_LOG_CONTROL_T, AS_ASCII_ERROR_MSG_T,
    AS_PROCESS_STATUS_T, AS_PROCESS_STATUS_LIST_T,
    AS_PORT_STATUS_INFO_T, AS_PROC_CONTROL_T, AS_SESSION_CONTROL_T,
    AS_RULE_CHANGE_INFO_T, AS_DATA_HANDLER_INFO_T, AS_DATA_ROUTING_INIT_T,
    AS_CONNECTOR_PORT_INFO_REQ_T,
)
from Common.CommType import (
    CMD_OPEN_PORT, CMD_MMC_PUBLISH_REQ, CMD_LOG_STATUS_CHANGE,
    PROC_CONTROL, SESSION_CONTROL, CMD_PROC_TERMINATE,
    CMD_PARSING_RULE_DOWN, CMD_MAPPING_RULE_DOWN,
    CMD_PARSING_RULE_CHANGE,
    AS_DATA_HANDLER_INFO, AS_DATA_ROUTING_INIT,
    CMD_MMC_PUBLISH_RES, CONNECTOR_PORT_INFO_REQ,
    ASCII_ERROR_MSG, PROCESS_INFO, PROCESS_INFO_LIST,
    PORT_STATUS_INFO,
)

logger = logging.getLogger(__name__)

# AS_PROCESS_STATUS_LIST_T의 최대 개수
try:
    from Common.CommType import PROCESS_STATUS_LIST_MAX
except ImportError:
    PROCESS_STATUS_LIST_MAX = 50                    # fallback 기본값


class ServerConnection(AsSocket):
    """
    C++ ServerConnection (AsSocket 상속, procNaManager 버전) 대응.

    procNaServer에 Connect하는 클라이언트 소켓.
    AsciiManagerWorld._server_connection 으로 보유.

    AsSocket 가상 메서드 오버라이드:
      receive_packet()  ← C++ ReceivePacket()
      close_socket()    ← C++ CloseSocket()
    """

    def __init__(self, conn_mgr=None) -> None:
        super().__init__()
        # conn_mgr 인자는 인터페이스 통일용 (ServerConnMgr 없음)

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        msg_id = packet.MsgId

        if msg_id == CMD_OPEN_PORT:
            MAINPTR().SendCmdOpenInfo(packet.Msg)

        elif msg_id == CMD_MMC_PUBLISH_REQ:
            MAINPTR().SendMMCCommand(packet.Msg)

        elif msg_id == CMD_LOG_STATUS_CHANGE:
            MAINPTR().ReceiveCmdLogStatusChange(packet.Msg)

        elif msg_id == PROC_CONTROL:
            MAINPTR().RecvProcessControl(packet.Msg)

        elif msg_id == SESSION_CONTROL:
            MAINPTR().RecvSessionControl(packet.Msg)

        elif msg_id == CMD_PROC_TERMINATE:
            # C++: CloseSocket(0); return
            logger.debug("RECV CMD_PROC_TERMINATE..............")
            self.close_socket(0)

        elif msg_id == CMD_PARSING_RULE_DOWN:
            MAINPTR().RecvCmdParsingRuleDown()

        elif msg_id == CMD_MAPPING_RULE_DOWN:
            MAINPTR().RecvCmdMappingRuleDown()

        elif msg_id == CMD_PARSING_RULE_CHANGE:
            MAINPTR().ParserRuleChange(packet.Msg)

        elif msg_id == AS_DATA_HANDLER_INFO:
            MAINPTR().RecvDataHandlerInfo(packet.Msg)

        elif msg_id == AS_DATA_ROUTING_INIT:
            MAINPTR().RecvInitInfo(packet.Msg)

        else:
            logger.debug("Unknown Msg Id : %d", msg_id)

    def close_socket(self, errno_val: int) -> None:
        """
        C++: virtual CloseSocket(int Errno)
        C++: kill(getpid(), SIGINT) → Python: os.kill(os.getpid(), SIGINT)
        서버 연결 끊김 시 프로세스 종료.
        """
        logger.error("Server Connection Broken")
        try:
            os.kill(os.getpid(), signal.SIGINT)
        except Exception:
            sys.exit(1)

    # =========================================================================
    # 전송 메서드
    # =========================================================================

    async def ConnectorPortInfoRequest(self, connector_name: str) -> None:
        """C++: ConnectorPortInfoRequest(string ConnectorName)"""
        req = AS_CONNECTOR_PORT_INFO_REQ_T()
        req.ConnectorId = connector_name
        payload = _pack(req)
        await self.SendPacket(CONNECTOR_PORT_INFO_REQ, payload, len(payload))
        logger.debug("Send ConnectorPortInfoReq : %s", connector_name)

    async def SendCommandResponse(self, mmc_result: AS_MMC_RESULT_T) -> None:
        """C++: SendCommandResponse(AS_MMC_RESULT_T*)"""
        payload = _pack(mmc_result)
        await self.SendPacket(CMD_MMC_PUBLISH_RES, payload, len(payload))

    def SendLogStatus(self, status: AS_LOG_STATUS_T) -> None:
        """C++: SendLogStatus(AS_LOG_STATUS_T*) — C++ 원본 미사용(주석처리)."""
        pass                                        # C++ 원본: not use

    async def SendAsciiError(self, err_msg: AS_ASCII_ERROR_MSG_T) -> None:
        """C++: SendAsciiError(AS_ASCII_ERROR_MSG_T*)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR
        err_msg.ManagerId = MAINPTR().GetProcName()
        payload = _pack(err_msg)
        await self.SendPacket(ASCII_ERROR_MSG, payload, len(payload))

    async def SendProcessInfo(
            self, proc_info: AS_PROCESS_STATUS_T) -> None:
        """C++: SendProcessInfo(AS_PROCESS_STATUS_T*) — 단일 프로세스 상태."""
        payload = _pack(proc_info)
        await self.SendPacket(PROCESS_INFO, payload, len(payload))

    async def SendProcessInfoList(
            self, proc_info_list: List[AS_PROCESS_STATUS_T]) -> None:
        """
        C++: SendProcessInfo(ProcessInfoList*) — 복수 프로세스 상태.
        PROCESS_STATUS_LIST_MAX 단위로 분할 전송.
        """
        proc_status_list = AS_PROCESS_STATUS_LIST_T()
        pos = 0

        for proc_info in proc_info_list:
            proc_status_list.ProcStatus[pos] = proc_info
            if pos >= PROCESS_STATUS_LIST_MAX - 2:
                proc_status_list.ProcStatusNo = PROCESS_STATUS_LIST_MAX
                payload = _pack(proc_status_list)
                await self.SendPacket(
                    PROCESS_INFO_LIST, payload, len(payload))
                proc_status_list = AS_PROCESS_STATUS_LIST_T()
                pos = -1
            pos += 1

        if pos > 0:
            proc_status_list.ProcStatusNo = pos
            payload = _pack(proc_status_list)
            await self.SendPacket(PROCESS_INFO_LIST, payload, len(payload))

        logger.debug("Process Info List Send Success(cnt : %d)",
                     len(proc_info_list))

    async def SendPortInfo(self,
                           status_info: AS_PORT_STATUS_INFO_T) -> None:
        """C++: SendPortInfo(AS_PORT_STATUS_INFO_T*)"""
        payload = _pack(status_info)
        await self.SendPacket(PORT_STATUS_INFO, payload, len(payload))


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''