"""
RouterConnMgr.py / RouterConnection.py
C++ RouterConnMgr.h/.C + RouterConnection.h/.C → Python 변환

Router 프로세스 연결 관리자 + 개별 소켓 연결 처리.

ConnectorConnMgr/ParserConnMgr과 구조 동일.
RouterConnection 특이사항:
  - StopProcess: CMD_PROC_TERMINATE 전송 + PROC_TERMINATE_WAIT 타이머
  - AliveCheckFail: 횟수 로그만 (강제종료 없음)
  - RouterStart: 세션 식별 후 AsciiManagerWorld.RouterStart() 호출
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
    ASCII_ROUTER,
    START, STOP, ORDER_KILL, LOG_DEL,
    AS_LOG_INFO, ASCII_ERROR_MSG,
    CMD_PROC_TERMINATE,
    PROC_TERMINATE_WAIT, PROC_TERMINATE_WAIT_TIMEOUT,
)

logger = logging.getLogger(__name__)


# =============================================================================
# RouterConnMgr
# =============================================================================

class RouterConnMgr(ProcConnectionMgr):
    """
    C++ RouterConnMgr (ProcConnectionMgr 상속) 대응.
    뮤텍스 없음 (ConnectorConnMgr/ParserConnMgr과 달리).
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
            MAINPTR().ProcessDead(ASCII_ROUTER, name, pid)

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """C++: AcceptSocket()"""
        conn = RouterConnection(self)
        if not self.Accept(conn):
            logger.debug("Router Socket Accept Error : %s",
                         self.GetObjErrMsg())
            return
        self.add(conn)                              # ConnectionMgr.add()

    # =========================================================================
    # StopProcess
    # =========================================================================

    def StopProcess(self, session_name: str) -> bool:
        """C++: StopProcess(string SessionName)"""
        con: Optional[RouterConnection] = self.find_session(session_name)
        if con is None:
            logger.debug("Can't Find Router : %s", session_name)
            return False
        con.StopProcess()
        self.stop_process_by_name(session_name)     # ProcConnectionMgr
        return True

    # =========================================================================
    # SendProcessInfo
    # =========================================================================

    def SendProcessInfo(self, session_name: str, status: int) -> None:
        """C++: SendProcessInfo(const char* SessionName, int Status)"""
        from ProcNaManager.AsciiManagerWorld import AsciiManagerWorld

        proc_info = AS_PROCESS_STATUS_T()
        proc_info.ProcessId   = session_name
        proc_info.Status      = status
        proc_info.ProcessType = ASCII_ROUTER

        if status == START:
            if not self.get_process_info_by_name(session_name, proc_info):
                return

        AsciiManagerWorld.m_WorldPtr.SendProcessInfo(proc_info)


# =============================================================================
# RouterConnection
# =============================================================================

class RouterConnection(AsSocket):
    """
    C++ RouterConnection (AsSocket 상속) 대응.

    AsSocket 가상 메서드 오버라이드:
      receive_packet()              ← C++ ReceivePacket()
      close_socket()                ← C++ CloseSocket()
      session_identify_callback()   ← C++ SessionIdentify()
      alive_check_fail()            ← C++ AliveCheckFail()
      ReceiveTimeOut()              ← C++ ReceiveTimeOut()

    ConnectorConnection과의 차이:
      - StopProcess: CMD_PROC_TERMINATE 전송 + SetTimer(PROC_TERMINATE_WAIT)
      - AliveCheckFail: 강제종료 없이 로그/에러만
      - 세션 식별 후 AsciiManagerWorld.RouterStart() 호출
    """

    def __init__(self, conn_mgr: RouterConnMgr) -> None:
        super().__init__()
        self._router_conn_mgr: RouterConnMgr = conn_mgr
        self._router_status:   bool          = True
        self._terminate_timer_key: Optional[int] = None

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)"""
        if session_identify == ASCII_ROUTER:
            self._router_proc_req(packet)
        else:
            logger.debug("UnKnown Session : %d", session_identify)

    def session_identify_callback(self, session_type: int,
                                   session_name: str = "") -> None:
        """C++: virtual SessionIdentify(int SessionType, string SessionName)"""
        from ProcNaManager.AsciiManagerWorld import AsciiManagerWorld

        if not self._router_conn_mgr.add_session_name(session_name):  # ConnectionMgr
            self._close()
            self._router_conn_mgr.remove(self)      # ConnectionMgr.remove()
            return

        logger.debug("SessionType : %s, SessionName : %s",
                     AsUtil.GetProcessTypeString(session_type), session_name)

        self._router_conn_mgr.SendProcessInfo(
            self.GetSessionName(), START)

        self.StartAliveCheck(                       # AsSocket.StartAliveCheck
            AsciiManagerWorld.m_WorldPtr.GetProcAliveCheckTime(),
            AsciiManagerWorld.m_WorldPtr.GetAliveCheckLimitCnt(),
        )
        # Router 기동 완료 통보
        AsciiManagerWorld.m_WorldPtr.RouterStart(self.GetSessionName())

    def close_socket(self, errno_val: int) -> None:
        """C++: virtual CloseSocket(int Errno)"""
        logger.debug("Socket Broken Router SessionName : %s",
                     self.GetSessionName())
        self.SendLogStatus()

        if self._router_status:
            self._router_conn_mgr.child_process_dead(self)          # ProcConnectionMgr
        else:
            self._router_conn_mgr.child_process_dead(self, ORDER_KILL)

    def alive_check_fail(self, fail_count: int) -> None:
        """
        C++: virtual AliveCheckFail(int FailCount)
        C++ 원본: 강제종료 없이 로그/에러만 출력.
        """
        from ProcNaManager.AsciiManagerWorld import AsciiManagerWorld

        if fail_count > AsciiManagerWorld.m_WorldPtr.GetAliveCheckLimitCnt():
            logger.debug("Alive Check Fail(count : %d) Limite Over", fail_count)
            AsciiManagerWorld.m_WorldPtr.SendAsciiError(
                1, "Alive Check Fail(count : %d) Limite Over", fail_count)

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """
        C++: ReceiveTimeOut(int Reason, void* ExtraReason)
        PROC_TERMINATE_WAIT: 종료 대기 타임아웃 → 강제 CloseSocket.
        """
        if reason == PROC_TERMINATE_WAIT:
            self._terminate_timer_key = None
            self._close()
            self.SendLogStatus()
            self._router_conn_mgr.StopProcess(self.GetSessionName())
        else:
            logger.debug("UnKnown TimeOut Reason : %d", reason)

    # =========================================================================
    # StopProcess
    # =========================================================================

    def StopProcess(self) -> None:
        """
        C++: StopProcess()
        정상 종료 플래그 설정 + CMD_PROC_TERMINATE 전송 + 타이머 설정.
        """
        self._router_status = False
        asyncio.ensure_future(self.SendPacket(CMD_PROC_TERMINATE))

        # 기존 타이머 취소 후 재설정
        if self._terminate_timer_key is not None:
            self.CancelTimer(self._terminate_timer_key)  # AsWorld.CancelTimer

        self._terminate_timer_key = self.SetTimer(   # AsWorld.SetTimer
            PROC_TERMINATE_WAIT_TIMEOUT,
            PROC_TERMINATE_WAIT,
        )

    # =========================================================================
    # 패킷 처리
    # =========================================================================

    def _router_proc_req(self, packet) -> None:
        """C++: RouterProcReq(PACKET_T*)"""
        from ProcNaManager.AsciiManagerWorld import MAINPTR

        msg_id = packet.MsgId

        if msg_id == AS_LOG_INFO:
            MAINPTR().SendLogStatus(packet.Msg)

        elif msg_id == ASCII_ERROR_MSG:
            MAINPTR().SendAsciiError(packet.Msg)
            # C++ 원본: case ASCII_ERROR_MSG에 break 없이 default로 fall-through
            # → Python에서는 elif로 처리하여 중복 방지
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