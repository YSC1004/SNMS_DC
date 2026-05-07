"""
LogRouterConnMgr.py / LogRouterConnection.py
C++ LogRouterConnMgr.h/.C + LogRouterConnection.h/.C → Python 변환

LogRouter 프로세스 연결 관리자 + 개별 소켓 연결 처리.
RouterConnMgr/RouterConnection과 거의 동일한 구조.

차이점:
  - ProcessType: ASCII_LOG_ROUTER
  - StopProcess: ProcConnectionMgr::StopProcess() 호출 없음 (C++ 원본 동일)
  - ReceiveTimeOut PROC_TERMINATE_WAIT: VariousAckCheckTimeOut 호출
    (RouterConnection은 StopProcess 호출)
  - SessionIdentify: RouterStart() 호출 없음
"""

import asyncio
import logging
from typing import Optional

from Common.ProcConnectionMgr import ProcConnectionMgr  # process_dead (치트시트)
from Common.AsSocket import AsSocket                    # 가상함수 오버라이드 (치트시트)
from Common.AsUtil import AsUtil
from Common.CommTypeList import (
    AS_LOG_STATUS_T, AS_ASCII_ERROR_MSG_T, AS_PROCESS_STATUS_T,
)
from Common.CommType import (
    ASCII_LOG_ROUTER,
    START, STOP, ORDER_KILL, LOG_DEL,
    AS_LOG_INFO, ASCII_ERROR_MSG,
    CMD_PROC_TERMINATE,
    PROC_TERMINATE_WAIT, PROC_TERMINATE_WAIT_TIMEOUT,
)

logger = logging.getLogger(__name__)


# =============================================================================
# LogRouterConnMgr
# =============================================================================

class LogRouterConnMgr(ProcConnectionMgr):
    """
    C++ LogRouterConnMgr (ProcConnectionMgr 상속) 대응.
    RouterConnMgr과 거의 동일. ProcessType만 ASCII_LOG_ROUTER.
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
                1, "The process(%s) is killed normally.", name)
        else:
            MAINPTR().ProcessDead(ASCII_LOG_ROUTER, name, pid)

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """C++: AcceptSocket()"""
        conn = LogRouterConnection(self)
        if not self.Accept(conn):
            logger.debug("Log Router Socket Accept Error : %s",
                         self.GetObjErrMsg())
            return
        self.add(conn)                              # ConnectionMgr.add()

    # =========================================================================
    # StopProcess
    # =========================================================================

    def StopProcess(self, session_name: str) -> bool:
        """
        C++: StopProcess(string SessionName)
        RouterConnMgr과 달리 ProcConnectionMgr::StopProcess() 미호출.
        """
        con: Optional[LogRouterConnection] = self.find_session(session_name)
        if con is None:
            logger.debug("Can't Find Log Router : %s", session_name)
            return False
        con.StopProcess()
        return True                                 # C++ 원본: ProcConnectionMgr::StopProcess 미호출

    # =========================================================================
    # SendProcessInfo
    # =========================================================================

    def SendProcessInfo(self, session_name: str, status: int) -> None:
        """C++: SendProcessInfo(const char* SessionName, int Status)"""
        from ProcNaManager.AsciiManagerWorld import AsciiManagerWorld

        proc_info = AS_PROCESS_STATUS_T()
        proc_info.ProcessId   = session_name
        proc_info.Status      = status
        proc_info.ProcessType = ASCII_LOG_ROUTER

        if status == START:
            if not self.get_process_info_by_name(session_name, proc_info):
                return

        AsciiManagerWorld.m_WorldPtr.SendProcessInfo(proc_info)


# =============================================================================
# LogRouterConnection
# =============================================================================

class LogRouterConnection(AsSocket):
    """
    C++ LogRouterConnection (AsSocket 상속) 대응.
    RouterConnection과 거의 동일.

    차이점:
      - SessionIdentify: RouterStart() 호출 없음
      - ReceiveTimeOut PROC_TERMINATE_WAIT:
          RouterConnection → StopProcess()
          LogRouterConnection → VariousAckCheckTimeOut()
    """

    def __init__(self, conn_mgr: LogRouterConnMgr) -> None:
        super().__init__()
        self._log_router_conn_mgr: LogRouterConnMgr = conn_mgr
        self._log_router_status:   bool             = True
        self._terminate_timer_key: Optional[int]    = None

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)"""
        if session_identify == ASCII_LOG_ROUTER:
            self._log_router_proc_req(packet)
        else:
            logger.debug("UnKnown Session : %d", session_identify)

    def session_identify_callback(self, session_type: int,
                                   session_name: str = "") -> None:
        """C++: virtual SessionIdentify(int SessionType, string SessionName)"""
        from ProcNaManager.AsciiManagerWorld import AsciiManagerWorld

        if not self._log_router_conn_mgr.add_session_name(session_name):  # ConnectionMgr
            self._close()
            self._log_router_conn_mgr.remove(self)  # ConnectionMgr.remove()
            return

        logger.debug("SessionType : %s, SessionName : %s",
                     AsUtil.GetProcessTypeString(session_type), session_name)

        self._log_router_conn_mgr.SendProcessInfo(
            self.GetSessionName(), START)

        self.StartAliveCheck(                       # AsSocket.StartAliveCheck
            AsciiManagerWorld.m_WorldPtr.GetProcAliveCheckTime(),
            AsciiManagerWorld.m_WorldPtr.GetAliveCheckLimitCnt(),
        )
        # RouterConnection과 달리 RouterStart() 호출 없음

    def close_socket(self, errno_val: int) -> None:
        """C++: virtual CloseSocket(int Errno)"""
        logger.debug("Socket Broken Log Router SessionName : %s",
                     self.GetSessionName())
        self.SendLogStatus()

        if self._log_router_status:
            self._log_router_conn_mgr.child_process_dead(self)      # ProcConnectionMgr
        else:
            self._log_router_conn_mgr.child_process_dead(
                self, ORDER_KILL)

    def alive_check_fail(self, fail_count: int) -> None:
        """C++: virtual AliveCheckFail(int FailCount) — RouterConnection과 동일."""
        from ProcNaManager.AsciiManagerWorld import AsciiManagerWorld

        if fail_count > AsciiManagerWorld.m_WorldPtr.GetAliveCheckLimitCnt():
            logger.debug("Alive Check Fail(count : %d) Limite Over",
                         fail_count)
            AsciiManagerWorld.m_WorldPtr.SendAsciiError(
                1, "Alive Check Fail(count : %d) Limite Over", fail_count)

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """
        C++: ReceiveTimeOut(int Reason, void* ExtraReason)
        PROC_TERMINATE_WAIT:
          RouterConnection    → StopProcess()
          LogRouterConnection → VariousAckCheckTimeOut() (차이점)
        """
        if reason == PROC_TERMINATE_WAIT:
            self._terminate_timer_key = None
            self._close()
            self.SendLogStatus()
            self._log_router_conn_mgr.various_ack_check_time_out(self)  # ProcConnectionMgr
        else:
            logger.debug("UnKnown TimeOut Reason : %d", reason)

    # =========================================================================
    # StopProcess
    # =========================================================================

    def StopProcess(self) -> None:
        """C++: StopProcess() — RouterConnection과 동일 패턴."""
        self._log_router_status = False
        asyncio.ensure_future(self.SendPacket(CMD_PROC_TERMINATE))

        if self._terminate_timer_key is not None:
            self.CancelTimer(self._terminate_timer_key)  # AsWorld.CancelTimer

        self._terminate_timer_key = self.SetTimer(   # AsWorld.SetTimer
            PROC_TERMINATE_WAIT_TIMEOUT,
            PROC_TERMINATE_WAIT,
        )

    # =========================================================================
    # 패킷 처리
    # =========================================================================

    def _log_router_proc_req(self, packet) -> None:
        """C++: LogRouterProcReq(PACKET_T*)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        msg_id = packet.MsgId

        if msg_id == AS_LOG_INFO:
            MAINPTR().SendLogStatus(packet.Msg)

        elif msg_id == ASCII_ERROR_MSG:
            MAINPTR().SendAsciiError(packet.Msg)
            # C++ 원본: break 없이 default fall-through → Python에서 elif로 분리
        else:
            logger.debug("Unknown Msg Id : %d", msg_id)

    # =========================================================================
    # SendLogStatus
    # =========================================================================

    def SendLogStatus(self) -> None:
        """C++: SendLogStatus() — LOG_DEL 상태 전송."""
        from ProcNaManager.AsciiManagerWorld import AsciiManagerWorld

        log = AS_LOG_STATUS_T()
        log.name   = self.GetSessionName()
        log.logs   = (f"{AsUtil.GetProcessTypeString(self.GetSessionType())},"
                      f"{self.GetSessionName()},")
        log.status = LOG_DEL
        AsciiManagerWorld.m_WorldPtr.SendLogStatus(log)