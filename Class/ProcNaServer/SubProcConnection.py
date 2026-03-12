"""
SubProcConnection.py
C++ SubProcConnection.h/.C → Python 변환

개별 SubProc(자식 프로세스) 소켓 연결 처리.
  - 패킷 수신 분기 (PROC_INIT_END / ASCII_ERROR_MSG / PROCESS_INFO / AS_SYSTEM_INFO)
  - 소켓 종료 시 재기동 또는 정상 종료 처리
  - 세션 식별 (session_identify_callback)
  - AliveCheck 실패 시 강제 Kill
  - SubProc 종료 요청 (StopSubProc) + 타임아웃 처리
"""

import logging
from typing import Optional, TYPE_CHECKING

from Common.AsSocket import AsSocket                    # receive_packet/close_socket/session_identify_callback 오버라이드
from Common.CommTypeList import (
    AS_SUB_PROC_INFO_T,
    AS_PROCESS_STATUS_T,
    AS_ASCII_ERROR_MSG_T,
    AS_SYSTEM_INFO_T,
)
from Common.CommType import (
    ASCII_SUB_PROCESS,
    START, STOP, WAIT_NO,
    PROC_INIT_END,
    ASCII_ERROR_MSG,
    PROCESS_INFO,
    AS_SYSTEM_INFO,
    CMD_PROC_TERMINATE,
    PROC_TERMINATE_WAIT,
    PROC_TERMINATE_WAIT_TIMEOUT,
)
from Common.AsUtil import AsUtil                        # GetProcessTypeString

if TYPE_CHECKING:
    from ProcNaServer.SubProcConnMgr import SubProcConnMgr

logger = logging.getLogger(__name__)


class SubProcConnection(AsSocket):
    """
    C++ SubProcConnection (AsSocket 상속) 대응.

    AsSocket 가상 메서드 오버라이드:
      receive_packet()              ← C++ ReceivePacket()
      close_socket()                ← C++ CloseSocket()
      session_identify_callback()   ← C++ SessionIdentify()
      alive_check_fail()            ← C++ AliveCheckFail()

    타이머:
      AsWorld.SetTimer / CancelTimer (asyncio.Task 기반) 사용.
      _terminate_timer_key : int | None
    """

    def __init__(self, conn_mgr: "SubProcConnMgr") -> None:
        super().__init__()
        self._conn_mgr:   "SubProcConnMgr"              = conn_mgr
        self._sub_proc_info: Optional[AS_SUB_PROC_INFO_T] = None
        self._terminate_timer_key: Optional[int]          = None  # AsWorld.SetTimer 키

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """
        C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)
        AsSocket.ReceiveMessage()에서 세션 타입에 따라 호출.
        """
        if session_identify == ASCII_SUB_PROCESS:
            self._sub_proc_req_process(packet)
        else:
            logger.debug("UnKnown Session : %d", session_identify)

    def close_socket(self, errno_val: int) -> None:
        """
        C++: virtual CloseSocket(int Errno)
        AsSocket._socket_broken()에서 호출.
        소켓 종료 시 SubProc 상태 업데이트 및 재기동 여부 판단.
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR

        session_name = self.GetSessionName()
        logger.debug("Socket Broken : %s", session_name)

        if self._sub_proc_info is None:
            self._conn_mgr.remove(self)             # ConnectionMgr.remove()
            return

        # SubProc 상태 초기화
        self._sub_proc_info.CurStatus     = STOP
        self._sub_proc_info.RequestStatus = WAIT_NO
        MAINPTR().SendInfoChange(self._sub_proc_info)

        self._conn_mgr.remove_session_name(session_name)   # ConnectionMgr.remove_session_name()

        # 프로세스 상태 업데이트
        proc_info = AS_PROCESS_STATUS_T()
        proc_info.ManagerId   = MAINPTR().GetProcName()
        proc_info.ProcessId   = session_name
        proc_info.Status      = STOP
        proc_info.ProcessType = ASCII_SUB_PROCESS
        MAINPTR().UpdateProcessInfo(proc_info)

        # 설정 상태가 START → 비정상 종료 → 재기동
        if self._sub_proc_info.SettingStatus == START:
            MAINPTR().SendAsciiError(
                1, "The SubProc(%s) is killed abnormal.", session_name)
            self._conn_mgr.ExecuteSubProc(self._sub_proc_info)
            MAINPTR().SendAsciiError(
                1, "SubProc(%s) is reexecuted.", self._sub_proc_info.ProcIdStr)
        else:
            MAINPTR().SendAsciiError(
                1, "The SubProc(%s) is killed normally.", session_name)

        self._conn_mgr.remove(self)                 # ConnectionMgr.remove()

    def session_identify_callback(self, session_type: int,
                                   session_name: str = "") -> None:
        """
        C++: virtual SessionIdentify(int SessionType, string SessionName)
        AsSocket._do_session_identify()에서 세션 식별 완료 후 호출.
        SubProcInfo 검색 → 타이머 취소 → 상태 업데이트 → AliveCheck 시작.
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR

        self._sub_proc_info = self._conn_mgr.FindSubProcInfo(session_name)
        if self._sub_proc_info is None:
            logger.error("Can't find SubProc : %s", session_name)
            self._close()
            self._conn_mgr.remove(self)             # ConnectionMgr.remove()
            return

        if not self._conn_mgr.add_session_name(session_name):  # ConnectionMgr.add_session_name()
            self._close()
            self._conn_mgr.remove(self)
            return

        logger.debug("SubProc Session Identify : Type(%s), SessionName(%s)",
                     AsUtil.GetProcessTypeString(session_type), session_name)

        # 기동 대기 타이머 취소 (SubProcConnMgr → AsWorld.CancelTimer)
        self._conn_mgr.SubProcSessionIdentify(session_name)

        # 상태 업데이트
        self._sub_proc_info.CurStatus     = START
        self._sub_proc_info.RequestStatus = WAIT_NO
        MAINPTR().SendInfoChange(self._sub_proc_info)

        # AliveCheck 시작 (AsSocket.StartAliveCheck)
        self.StartAliveCheck(
            MAINPTR().GetProcAliveCheckTime(),      # AsWorld.GetProcAliveCheckTime()
            MAINPTR().GetAliveCheckLimitCnt(),      # AsWorld.GetAliveCheckLimitCnt()
        )

    def alive_check_fail(self, fail_count: int) -> None:
        """
        C++: virtual AliveCheckFail(int FailCount)
        AsSocket._alive_check_loop()에서 최대 실패 횟수 초과 시 호출.
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR

        session_name = self.GetSessionName()
        logger.debug("AliveCheckFail(%s) , Count : %d", session_name, fail_count)
        logger.debug("The SubProc(%s) is killed on purpose for no reply.",
                     session_name)

        MAINPTR().SendAsciiError(
            1, "The SubProc(%s) is killed on purpose for no reply.", session_name)

        if self._sub_proc_info:
            self._conn_mgr.KillSubProc(self._sub_proc_info.ProcIdStr)

    # =========================================================================
    # StopSubProc
    # =========================================================================

    async def StopSubProc(self) -> None:
        """
        C++: StopSubProc()
        SubProc에 종료 패킷 전송 + 타임아웃 타이머 설정 (AsWorld.SetTimer).
        """
        await self.SendPacket(CMD_PROC_TERMINATE)   # AsSocket.SendPacket (async)

        # 기존 타이머 취소
        if self._terminate_timer_key is not None:
            self.CancelTimer(self._terminate_timer_key)  # AsWorld.CancelTimer

        self._terminate_timer_key = self.SetTimer(  # AsWorld.SetTimer
            PROC_TERMINATE_WAIT_TIMEOUT,
            PROC_TERMINATE_WAIT,
        )

    # =========================================================================
    # ReceiveTimeOut  (AsWorld 가상함수 오버라이드)
    # =========================================================================

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """
        C++: ReceiveTimeOut(int Reason, void* ExtraReason)
        AsWorld.SetTimer 콜백.
        PROC_TERMINATE_WAIT: SubProc 종료 대기 타임아웃 → 강제 Kill.
        """
        if reason == PROC_TERMINATE_WAIT:
            session_name = self.GetSessionName()
            logger.error("SubProc Terminate TimeOut")
            logger.error("SubProc Kill Force!!! : %s", session_name)
            self._terminate_timer_key = None
            if self._sub_proc_info:
                self._conn_mgr.KillSubProc(self._sub_proc_info.ProcIdStr)
        else:
            logger.debug("Unknown Timeout Reason %d", reason)

    # =========================================================================
    # 내부: 패킷 처리
    # =========================================================================

    def _sub_proc_req_process(self, packet) -> None:
        """
        C++: SubProcReqProcess(PACKET_T*)
        MsgId 별 처리.
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR

        msg_id = packet.MsgId

        if msg_id == PROC_INIT_END:
            pass  # C++ 원본 동일하게 처리 없음

        elif msg_id == ASCII_ERROR_MSG:
            MAINPTR().SendAsciiError(packet.Msg)    # AS_ASCII_ERROR_MSG_T 직접 전달

        elif msg_id == PROCESS_INFO:
            proc_info: AS_PROCESS_STATUS_T = packet.Msg
            proc_info.ManagerId = MAINPTR().GetProcName()   # AsWorld.GetProcName()
            proc_info.ProcessId = self.GetSessionName()     # AsSocket.GetSessionName()
            self._conn_mgr.ReceiveProcInfo(proc_info)

        elif msg_id == AS_SYSTEM_INFO:
            MAINPTR().RecvSystemInfo(packet.Msg)

        else:
            logger.debug("UnKnown MsgId : %d", msg_id)