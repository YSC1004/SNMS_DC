"""
DBGwServerMgr.py
C++ DBGwServerMgr.h/.C → Python 변환

DB Gateway 서버의 리스닝 소켓 관리자.
- Run()으로 지정 포트에서 Listen 시작
- 클라이언트 Accept 시 DBGwServerSession 생성 후 AcceptSession()에 위임
- AcceptSession()은 서브클래스에서 오버라이드하여 세션 관리 정책 구현
"""

import logging
import socket
import threading
from typing import Optional, TYPE_CHECKING

from libDBGw.libDBGwBase.DBGwBaseSocket import DBGwBaseSocket
from libDBGw.libDBGwSvr.DBGwServerSession import DBGwServerSession

logger = logging.getLogger(__name__)


class DBGwServerMgr(DBGwBaseSocket):
    """
    DB Gateway 서버 리스닝 관리자.

    클라이언트 접속을 수락하고 DBGwServerSession을 생성한다.
    AcceptSession()을 오버라이드하여 세션 수락/거부 및 수명 관리를 결정한다.

    AcceptSession() 반환값 규칙 (C++ 원본 동일):
        True  → AcceptSocket()이 session을 delete(해제)한다.  (세션 거부 또는 직접 관리)
        False → AcceptSocket()이 session을 해제하지 않는다.  (서브클래스가 관리)
    """

    # Listen backlog (C++ 원본 100 유지)
    _LISTEN_BACKLOG = 100

    def __init__(self,
                 DbKind: int,
                 DefaultDbUser: str = "",
                 DefaultDbPasswd: str = "",
                 DefaultDbName: str = "") -> None:
        super().__init__()

        self.m_DbKind:  int = DbKind
        self.m_DbUser:  str = DefaultDbUser
        self.m_DbPasswd: str = DefaultDbPasswd
        self.m_DbName:  str = DefaultDbName
        self.m_LogDir:  str = "."

        # Accept 루프용 스레드 (Run() 호출 시 생성)
        self._accept_thread: Optional[threading.Thread] = None
        self._running: bool = False

    def __del__(self) -> None:
        self._running = False

    # -------------------------------------------------------------------------
    # Public
    # -------------------------------------------------------------------------

    def Run(self, ListenPort: int) -> bool:
        """
        소켓 생성 → Listen → Accept 루프 스레드 시작.

        C++ 원본은 Listen() 후 상위 이벤트 루프에서 AcceptSocket()을 호출하지만,
        Python에서는 별도 스레드에서 Accept 루프를 실행한다.

        Returns:
            True  : Listen 성공 및 Accept 스레드 시작
            False : 소켓 생성 또는 Listen 실패
        """
        if not self.Create(socket.AF_INET):
            logger.error("DBGwServerMgr: socket Create failed")
            return False

        if not self.Listen(ListenPort, self._LISTEN_BACKLOG):
            logger.error("DBGwServerMgr: Listen on port %d failed", ListenPort)
            return False

        logger.info("DBGwServerMgr: Listening on port %d", ListenPort)
        self._running = True
        self._accept_thread = threading.Thread(
            target=self._AcceptLoop,
            name=f"DBGwServerMgr-Accept-{ListenPort}",
            daemon=True
        )
        self._accept_thread.start()
        return True

    def AcceptSession(self, Session: DBGwServerSession) -> bool:
        """
        세션 수락 후 처리 정책을 결정한다.
        서브클래스에서 오버라이드하여 세션 목록 관리, 스레드 시작 등을 수행한다.

        Returns:
            True  → AcceptSocket()이 session 자원을 해제한다.
            False → 서브클래스(오버라이드)가 session 수명을 직접 관리한다.

        C++ 원본 기본 구현은 False를 반환한다.
        """
        return False

    def AcceptSocket(self) -> None:
        """
        클라이언트 연결 1개를 수락하고 DBGwServerSession을 생성한다.

        - Accept 성공 시 AcceptSession()을 호출
        - AcceptSession()이 True 반환 → session 자원 직접 해제
        - AcceptSession()이 False 반환 → 서브클래스가 session 관리 책임
        - Accept 실패 시 생성된 session 즉시 해제
        """
        session = DBGwServerSession(
            self.m_DbKind,
            self.m_DbUser,
            self.m_DbPasswd,
            self.m_DbName
        )
        # 로깅 설정 전달
        session.m_LogDir = self.m_LogDir

        if self.Accept(session):
            ret = self.AcceptSession(session)
            if ret:
                # AcceptSession이 True → 이 쪽에서 session 관리 종료
                session = None
            # False → 서브클래스가 session 참조를 보관하여 직접 관리
        else:
            logger.warning("DBGwServerMgr: Accept failed, session discarded")
            session = None

    def SetLogDir(self, LogDir: str) -> None:
        """로그 파일 저장 디렉토리를 설정한다."""
        self.m_LogDir = LogDir

    # -------------------------------------------------------------------------
    # Protected
    # -------------------------------------------------------------------------

    def _AcceptLoop(self) -> None:
        """
        Accept 루프 스레드 본체.
        C++ 원본에서는 상위 이벤트 루프(frEventMgr 등)가 AcceptSocket()을 호출하지만,
        Python에서는 이 스레드가 직접 루프를 돌며 AcceptSocket()을 호출한다.
        """
        logger.info("DBGwServerMgr: Accept loop started")
        while self._running:
            try:
                self.AcceptSocket()
            except OSError as e:
                if self._running:
                    logger.error("DBGwServerMgr: AcceptSocket error: %s", e)
                break
            except Exception as e:
                logger.exception("DBGwServerMgr: Unexpected error in AcceptLoop: %s", e)
                break
        logger.info("DBGwServerMgr: Accept loop stopped")