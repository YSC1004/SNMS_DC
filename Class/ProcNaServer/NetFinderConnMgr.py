"""
NetFinderConnMgr.py / NetFinderConnection.py
C++ NetFinderConnMgr.h/.C + NetFinderConnection.h/.C → Python 변환

단순 구조 → 하나의 파일로 통합.

NetFinderConnMgr  : ProcConnectionMgr 상속, Accept + ProcessDead + SendProcessInfo
NetFinderConnection: AsSocket 상속, 세션 식별 + AS_LOG_INFO 수신(no-op)
"""

import asyncio
import logging
from typing import Optional

from Common.ProcConnectionMgr import ProcConnectionMgr  # process_dead/@abstractmethod (치트시트)
from Common.AsSocket import AsSocket                    # 가상함수 오버라이드 (치트시트)
from Common.AsUtil import AsUtil
from Common.CommTypeList import AS_PROCESS_STATUS_T
from Common.CommType import (
    NETFINDER,
    START, STOP, ORDER_KILL,
    AS_LOG_INFO,
)

logger = logging.getLogger(__name__)


# =============================================================================
# NetFinderConnMgr
# =============================================================================

class NetFinderConnMgr(ProcConnectionMgr):
    """
    C++ NetFinderConnMgr (ProcConnectionMgr 상속) 대응.
    RuleDownLoaderConnMgr과 동일한 패턴.
    """

    def __init__(self) -> None:
        super().__init__()
        self._net_finder_conn: Optional["NetFinderConnection"] = None

    # =========================================================================
    # ProcConnectionMgr 추상 메서드 구현
    # =========================================================================

    def process_dead(self, name: str, pid: int, status: int = -1) -> None:
        """
        C++: ProcessDead(string Name, int Pid, int Status)
        ProcConnectionMgr.child_process_dead() 에서 호출.
        """
        self.SendProcessInfo(name, STOP)

        if status != ORDER_KILL:
            self._net_finder_conn = None
            from ProcNaServer.AsciiServerWorld import MAINPTR
            MAINPTR().ProcessDead(name, pid)

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """C++: AcceptSocket()"""
        conn = NetFinderConnection(self)
        if not self.Accept(conn):
            logger.debug("NetFinderConnMgr Socket Accept Error : %s",
                         self.GetObjErrMsg())
            return

        logger.debug("Connection success Netfinder")
        self.add(conn)                              # ConnectionMgr.add()

    # =========================================================================
    # StartProc (ProcConnectionMgr.start_proc 위임)
    # =========================================================================

    def StartProc(self, name: str, args: list) -> int:
        """C++: StartProc() → ProcConnectionMgr.start_proc() 위임."""
        return self.start_proc(name, args)          # ProcConnectionMgr.start_proc()

    # =========================================================================
    # SetNetFinderConn
    # =========================================================================

    def SetNetFinderConn(self,
                          conn: Optional["NetFinderConnection"]) -> None:
        """C++: SetNetFinderConn(NetFinderConnection* Con)"""
        self._net_finder_conn = conn

    # =========================================================================
    # SendProcessInfo
    # =========================================================================

    def SendProcessInfo(self, session_name: str, status: int) -> None:
        """C++: SendProcessInfo(const char* SessionName, int Status)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        proc_info = AS_PROCESS_STATUS_T()
        proc_info.ProcessId   = session_name
        proc_info.Status      = status

        if status == START:
            # ProcConnectionMgr.get_process_info_by_name()
            if not self.get_process_info_by_name(session_name, proc_info):
                return

        proc_info.ManagerId   = MAINPTR().GetProcName()
        proc_info.ProcessType = NETFINDER
        MAINPTR().UpdateProcessInfo(proc_info)


# =============================================================================
# NetFinderConnection
# =============================================================================

class NetFinderConnection(AsSocket):
    """
    C++ NetFinderConnection (AsSocket 상속) 대응.

    AsSocket 가상 메서드 오버라이드:
      receive_packet()              ← C++ ReceivePacket()
      close_socket()                ← C++ CloseSocket()
      session_identify_callback()   ← C++ SessionIdentify()
    """

    def __init__(self, conn_mgr: NetFinderConnMgr) -> None:
        super().__init__()
        self._net_finder_conn_mgr: NetFinderConnMgr = conn_mgr

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)"""
        if session_identify == NETFINDER:
            self._net_finder_req(packet)
        else:
            logger.debug("UnKnown Session : %d", session_identify)

    def session_identify_callback(self, session_type: int,
                                   session_name: str = "") -> None:
        """C++: virtual SessionIdentify(int SessionType, string SessionName)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        logger.debug("Session Identify : Type(%s), SessionName(%s)",
                     AsUtil.GetProcessTypeString(session_type), session_name)

        if not self._net_finder_conn_mgr.add_session_name(session_name):  # ConnectionMgr.add_session_name()
            self._close()
            self._net_finder_conn_mgr.remove(self)  # ConnectionMgr.remove()
            return

        # AliveCheck 시작 (AsSocket.StartAliveCheck)
        self.StartAliveCheck(
            MAINPTR().GetProcAliveCheckTime(),      # AsWorld.GetProcAliveCheckTime()
            MAINPTR().GetAliveCheckLimitCnt(),      # AsWorld.GetAliveCheckLimitCnt()
        )
        self._net_finder_conn_mgr.SendProcessInfo(
            self.GetSessionName(), START)
        self._net_finder_conn_mgr.SetNetFinderConn(self)

    def close_socket(self, errno_val: int) -> None:
        """C++: virtual CloseSocket(int Errno)"""
        logger.debug("Socket Broken : %s", self.GetSessionName())
        self._net_finder_conn_mgr.child_process_dead(self)  # ProcConnectionMgr.child_process_dead()

    # =========================================================================
    # NetFinderReq
    # =========================================================================

    def _net_finder_req(self, packet) -> None:
        """C++: NetFinderReq(PACKET_T*) — AS_LOG_INFO 수신(no-op)."""
        if packet.MsgId == AS_LOG_INFO:
            pass                                    # C++ 원본 동일하게 처리 없음
        else:
            logger.error("Unknown Msg Id : %d", packet.MsgId)