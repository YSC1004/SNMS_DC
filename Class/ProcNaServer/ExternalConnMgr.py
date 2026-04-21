"""
ExternalConnMgr.py
C++ ExternalConnMgr.h/.C → Python 변환

외부 시스템(MMC 요청 클라이언트) 연결 관리자.
  - ExternalConnection Accept 관리
  - MMC 결과 해당 세션으로 전달 (SendExtMMCReqResult)
  - 세션 ID 별 현재 접속 수 조회 (GetCurSessionCnt)
"""

import asyncio
import logging
import threading
from typing import TYPE_CHECKING

from Common.ConnectionMgr import ConnectionMgr          # add/remove/is_valid_connection (치트시트)
from Common.CommTypeList import AS_MMC_RESULT_T
from ProcNaServer.MMCRequestConnection import MMCRequestConnection

if TYPE_CHECKING:
    from ProcNaServer.ExternalConnection import ExternalConnection

logger = logging.getLogger(__name__)


class ExternalConnMgr(ConnectionMgr):
    """
    C++ ExternalConnMgr (ConnectionMgr 상속) 대응.

    뮤텍스:
      C++ frMutex m_SocketRemoveLock
      → _socket_remove_lock() / _socket_remove_unlock() 오버라이드
    """

    def __init__(self) -> None:
        super().__init__()
        self._remove_lock = threading.Lock()    # C++: frMutex m_SocketRemoveLock

    # =========================================================================
    # ConnectionMgr 뮤텍스 오버라이드
    # =========================================================================

    def _socket_remove_lock(self) -> None:
        """C++: SocketRemoveLock() → frMutex.Lock()"""
        self._remove_lock.acquire()

    def _socket_remove_unlock(self) -> None:
        """C++: SocketRemoveUnLock() → frMutex.UnLock()"""
        self._remove_lock.release()

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """C++: AcceptSocket()"""
        from ProcNaServer.ExternalConnection import ExternalConnection

        conn = ExternalConnection(self)
        if not self.Accept(conn):
            logger.debug("Ext Socket Accept Error : %s", self.GetObjErrMsg())
            return

        self.add(conn)                              # ConnectionMgr.add()
        conn.SetReReadCheck(True)                   # AsSocket.SetReReadCheck()
        logger.debug("External System Connection(%s)", conn.get_peer_ip())

    # =========================================================================
    # SendExtMMCReqResult
    # =========================================================================

    def SendExtMMCReqResult(self, ext_con: MMCRequestConnection,
                             res: AS_MMC_RESULT_T) -> None:
        """
        C++: SendExtMMCReqResult(MMCRequestConnection* ExtCon, AS_MMC_RESULT_T* Res)
        해당 External 세션이 유효한 경우에만 MMC 결과 전송.
        """
        self._socket_remove_lock()
        try:
            if self.is_valid_connection(ext_con):   # ConnectionMgr.is_valid_connection()
                logger.debug("Send MMC Result to [%s][%s]",
                             ext_con.GetSessionName(), ext_con.get_peer_ip())
                asyncio.ensure_future(ext_con.SendMMCResult(res))
            else:
                logger.debug("Send MMC Result Error : "
                             "Disconnected Session Or Invalid Session...")
        finally:
            self._socket_remove_unlock()

    # =========================================================================
    # GetCurSessionCnt
    # =========================================================================

    def GetCurSessionCnt(self, session_id: str) -> int:
        """
        C++: GetCurSessionCnt(string SessionID)
        동일 세션명으로 접속 중인 수 반환.
        C++: frMutexGuard → with self._remove_lock
        """
        with self._remove_lock:
            return sum(
                1 for sock in self._socket_connection_list
                if sock.GetSessionName() == session_id
            )