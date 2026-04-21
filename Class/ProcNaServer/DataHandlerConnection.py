"""
DataHandlerConnection.py
C++ DataHandlerConnection.h/.C → Python 변환

DataHandler 개별 소켓 연결 처리.
  - 패킷 수신 분기 (PROC_INIT_END / AS_LOG_INFO / PROCESS_INFO / AS_SYSTEM_INFO)
  - 세션 식별 후 DataHandlerInfo 전송 및 AliveCheck 시작
  - 소켓 종료 시 재기동 또는 정상 종료 처리
"""

import asyncio
import logging
from typing import Optional, TYPE_CHECKING

from Common.AsSocket import AsSocket                    # 가상함수 오버라이드 (치트시트)
from Common.AsUtil import AsUtil
from Common.CommTypeList import (
    AS_DATA_HANDLER_INFO_T, AS_PROCESS_STATUS_T,
    AS_LOG_STATUS_T, AS_ASCII_ERROR_MSG_T, AS_SYSTEM_INFO_T,
)
from Common.CommType import (
    ASCII_DATA_HANDLER,
    START, STOP, WAIT_NO, LOG_DEL,
    PROC_INIT_END, AS_LOG_INFO, ASCII_ERROR_MSG,
    PROCESS_INFO, AS_SYSTEM_INFO,
    AS_DATA_HANDLER_INFO,
    CMD_PROC_TERMINATE,
    PROC_TERMINATE_WAIT, PROC_TERMINATE_WAIT_TIMEOUT,
)

if TYPE_CHECKING:
    from ProcNaServer.DataHandlerConnMgr import DataHandlerConnMgr

logger = logging.getLogger(__name__)


class DataHandlerConnection(AsSocket):
    """
    C++ DataHandlerConnection (AsSocket 상속) 대응.

    AsSocket 가상 메서드 오버라이드:
      receive_packet()              ← C++ ReceivePacket()
      close_socket()                ← C++ CloseSocket()
      session_identify_callback()   ← C++ SessionIdentify()
      alive_check_fail()            ← C++ AliveCheckFail()
      ReceiveTimeOut()              ← C++ ReceiveTimeOut()
    """

    def __init__(self, conn_mgr: "DataHandlerConnMgr") -> None:
        super().__init__()
        self._data_handler_conn_mgr: "DataHandlerConnMgr"           = conn_mgr
        self._data_handler_info:     Optional[AS_DATA_HANDLER_INFO_T] = None
        self._terminate_timer_key:   Optional[int]                   = None

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)"""
        if session_identify == ASCII_DATA_HANDLER:
            self._data_handler_req_process(packet)
        else:
            logger.debug("UnKnown Session : %d", session_identify)

    def close_socket(self, errno_val: int) -> None:
        """C++: virtual CloseSocket(int Errno)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        session_name = self.GetSessionName()
        logger.debug("Socket Broken : %s", session_name)

        if self._data_handler_info is None:
            self._data_handler_conn_mgr.remove(self)   # ConnectionMgr.remove()
            return

        self._data_handler_info.CurStatus     = STOP
        self._data_handler_info.RequestStatus = WAIT_NO
        MAINPTR().SendInfoChange(self._data_handler_info)

        # 로그 상태 DEL 처리
        log_status = AS_LOG_STATUS_T()
        log_status.name   = session_name
        log_status.logs   = (
            f"sUn,{AsUtil.GetProcessTypeString(self.GetSessionType())},"
            f"{session_name},"
        )
        log_status.status = LOG_DEL
        self._data_handler_conn_mgr.UpdateDataHandlerLogStatus(log_status)

        self._data_handler_conn_mgr.remove_session_name(session_name)  # ConnectionMgr.remove_session_name()

        # 프로세스 상태 업데이트
        proc_info = AS_PROCESS_STATUS_T()
        proc_info.ManagerId   = MAINPTR().GetProcName()
        proc_info.ProcessId   = (
            f"{AsUtil.GetProcessTypeString(ASCII_DATA_HANDLER)}_{session_name}")
        proc_info.Status      = STOP
        proc_info.ProcessType = ASCII_DATA_HANDLER
        MAINPTR().UpdateProcessInfo(proc_info)

        # 설정 상태 START → 비정상 종료 → 재기동
        if self._data_handler_info.SettingStatus == START:
            MAINPTR().SendAsciiError(
                1, "The DataHandler(%s) is killed abnormal.", session_name)
            self._data_handler_conn_mgr.ExecuteDataHandler(
                self._data_handler_info)
            MAINPTR().SendAsciiError(
                1, "DataHandler(%s) is reexecuted.",
                self._data_handler_info.DataHandlerId)
        else:
            MAINPTR().SendAsciiError(
                1, "The DataHandler(%s) is killed normally.", session_name)

        self._data_handler_conn_mgr.remove(self)        # ConnectionMgr.remove()

    def session_identify_callback(self, session_type: int,
                                   session_name: str = "") -> None:
        """C++: virtual SessionIdentify(int SessionType, string SessionName)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        self._data_handler_info = \
            self._data_handler_conn_mgr.FindDataHandlerInfo(session_name)

        if self._data_handler_info is None:
            logger.error("Can't Find DataHandler : %s", session_name)
            self._close()
            self._data_handler_conn_mgr.remove(self)
            return

        if not self._data_handler_conn_mgr.add_session_name(session_name):  # ConnectionMgr.add_session_name()
            self._close()
            self._data_handler_conn_mgr.remove(self)
            return

        logger.debug("DataHandler Session Identify : Type(%s), SessionName(%s)",
                     AsUtil.GetProcessTypeString(session_type), session_name)

        # 기동 대기 타이머 취소
        self._data_handler_conn_mgr.DataHandlerSessionIdentify(session_name)

        # DataHandlerInfo 패킷 전송
        payload = _pack(self._data_handler_info)
        asyncio.ensure_future(
            self.SendPacket(AS_DATA_HANDLER_INFO, payload, len(payload)))

        self._data_handler_info.CurStatus     = START
        self._data_handler_info.RequestStatus = WAIT_NO
        MAINPTR().SendInfoChange(self._data_handler_info)

        # AliveCheck 시작 (AsSocket.StartAliveCheck)
        self.StartAliveCheck(
            MAINPTR().GetProcAliveCheckTime(),      # AsWorld.GetProcAliveCheckTime()
            MAINPTR().GetAliveCheckLimitCnt(),      # AsWorld.GetAliveCheckLimitCnt()
        )

    def alive_check_fail(self, fail_count: int) -> None:
        """C++: virtual AliveCheckFail(int FailCount)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        session_name = self.GetSessionName()
        logger.debug("AliveCheckFail(%s) , Count : %d",
                     session_name, fail_count)
        logger.debug("The DataHandler(%s) is killed on purpose for no reply.",
                     session_name)
        MAINPTR().SendAsciiError(
            1, "The DataHandler(%s) is killed on purpose for no reply.",
            session_name)

        if self._data_handler_info:
            self._data_handler_conn_mgr.KillDataHandler(
                self._data_handler_info.DataHandlerId)

    # =========================================================================
    # ReceiveTimeOut (AsWorld 가상함수 오버라이드)
    # =========================================================================

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """C++: ReceiveTimeOut — PROC_TERMINATE_WAIT: 강제 Kill."""
        if reason == PROC_TERMINATE_WAIT:
            session_name = self.GetSessionName()
            logger.error("DataHandler Terminate TimeOut")
            logger.error("DataHandler Kill Force!!! : %s", session_name)
            self._terminate_timer_key = None
            if self._data_handler_info:
                self._data_handler_conn_mgr.KillDataHandler(
                    self._data_handler_info.DataHandlerId)
        else:
            logger.debug("Unknown Timeout Reason %d", reason)

    # =========================================================================
    # StopDataHandler
    # =========================================================================

    async def StopDataHandler(self) -> None:
        """C++: StopDataHandler() — CMD_PROC_TERMINATE + 타임아웃 타이머."""
        await self.SendPacket(CMD_PROC_TERMINATE)   # AsSocket.SendPacket (async)

        if self._terminate_timer_key is not None:
            self.CancelTimer(self._terminate_timer_key)  # AsWorld.CancelTimer

        self._terminate_timer_key = self.SetTimer(  # AsWorld.SetTimer
            PROC_TERMINATE_WAIT_TIMEOUT,
            PROC_TERMINATE_WAIT,
        )

    # =========================================================================
    # 패킷 처리 내부 메서드
    # =========================================================================

    def _data_handler_req_process(self, packet) -> None:
        """C++: DataHandlerReqProcess(PACKET_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        msg_id = packet.MsgId

        if msg_id == PROC_INIT_END:
            pass                                    # C++ 원본 동일하게 처리 없음

        elif msg_id == AS_LOG_INFO:
            self._receive_log_info(packet.Msg)

        elif msg_id == ASCII_ERROR_MSG:
            MAINPTR().SendAsciiError(packet.Msg)

        elif msg_id == PROCESS_INFO:
            proc_info: AS_PROCESS_STATUS_T = packet.Msg
            proc_info.ManagerId = MAINPTR().GetProcName()
            proc_info.ProcessId = (
                f"{AsUtil.GetProcessTypeString(ASCII_DATA_HANDLER)}_"
                f"{self.GetSessionName()}")
            self._data_handler_conn_mgr.ReceiveProcInfo(proc_info)

        elif msg_id == AS_SYSTEM_INFO:
            MAINPTR().RecvSystemInfo(packet.Msg)

        else:
            logger.debug("UnKnown MsgId : %d", msg_id)

    def _receive_log_info(self, status: AS_LOG_STATUS_T) -> None:
        """C++: ReceiveLogInfo(AS_LOG_STATUS_T*)"""
        self._data_handler_conn_mgr.UpdateDataHandlerLogStatus(status)


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''