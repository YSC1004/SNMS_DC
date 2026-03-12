"""
DBGwMgr.py
C++ DBGwMgr.h/.C → Python 변환

DBGwServerMgr를 상속하여 AcceptSession()을 오버라이드한다.
클라이언트 접속 시 fork() 대신 multiprocessing.Process로 자식 프로세스를 생성하고,
자식은 동일 실행 파일(DBGwWorld.AppStart)을 -alone/-sessionid 인자로 재실행한다.
"""

import os
import sys
import signal
import logging
import multiprocessing
from typing import TYPE_CHECKING

from libDBGw.libDBGwSvr.DBGwServerMgr import DBGwServerMgr
from libDBGw.libDBGwSvr.DBGwServerSession import DBGwServerSession

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DBGwMgr(DBGwServerMgr):
    """
    DB Gateway 서버 관리자 (애플리케이션 레벨).

    AcceptSession()에서 클라이언트 연결마다 자식 프로세스를 생성한다.

    C++ fork()/execv() 패턴 → Python multiprocessing.Process + os.execv() 로 변환.
    SIGCHLD SIG_IGN → multiprocessing 에서는 daemon=False + 좀비 방지 설정으로 대응.
    """

    def __init__(self,
                 DbKind: int,
                 DefaultDbUser: str = "",
                 DefaultDbPasswd: str = "",
                 DefaultDbName: str = "") -> None:
        super().__init__(DbKind, DefaultDbUser, DefaultDbPasswd, DefaultDbName)

        # C++ : signal(SIGCHLD, SIG_IGN) → 자식 프로세스 좀비 방지
        # Python : multiprocessing.Process(daemon=True) 또는 signal 설정
        try:
            signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        except (OSError, ValueError):
            # Windows 또는 메인 스레드 외에서 호출 시 무시
            pass

    def __del__(self) -> None:
        pass

    # -------------------------------------------------------------------------
    # DBGwServerMgr override
    # -------------------------------------------------------------------------

    def AcceptSession(self, Session: DBGwServerSession) -> bool:
        """
        클라이언트 세션 수락 후 자식 프로세스를 생성한다.

        C++ 동작:
          - fork() 후 자식에서 execv()로 자기 자신을 -alone -sessionid <fd> 옵션으로 재실행
          - 부모는 true 반환 → AcceptSocket()이 session 자원 해제

        Python 변환:
          - Session 소켓 FD를 자식 프로세스에 상속 가능하도록 CloseOnExec=False 설정
          - multiprocessing.Process로 자식 프로세스 생성
          - 자식은 os.execv()로 동일 인터프리터+스크립트를 -alone -sessionid <fd>로 재실행
          - 부모는 True 반환 → AcceptSocket()이 session 참조 해제

        Returns:
            True : 항상 (부모 프로세스 기준) → AcceptSocket()이 session 해제
        """
        # FD를 자식에게 상속하기 위해 close-on-exec 해제
        Session.SetCloseOnExec(False)
        fd  = Session.GetFD()
        pid = os.getpid()

        # 실행 인자 구성 (C++ execv args 와 동일한 순서)
        child_name = f"DBGW_CHILD_{pid}_{fd}"

        # 현재 프로세스 argv 참조 (DBGwWorld.m_Argv 대응)
        argv0 = sys.argv[0]

        exec_args = [
            sys.executable,   # python 인터프리터
            argv0,            # 스크립트 경로
            "-alone",
            "-name", child_name,
            "-sessionid", str(fd),
        ]

        # -log 옵션 전달 (원본 argParser.GetValue("-log") 대응)
        try:
            log_idx = sys.argv.index("-log")
            exec_args += ["-log", sys.argv[log_idx + 1]]
        except (ValueError, IndexError):
            pass

        proc = multiprocessing.Process(
            target=_child_exec,
            args=(exec_args,),
            name=child_name,
            daemon=False      # 부모 종료 시 자식도 정리되지 않도록
        )
        proc.start()

        if proc.pid and proc.pid > 0:
            logger.info("Create child success (child_pid=%d, fd=%d)", proc.pid, fd)
        else:
            logger.error("Fork fail: child process creation failed (fd=%d)", fd)

        # 부모는 True 반환 → AcceptSocket()이 session 자원 해제
        return True


# ---------------------------------------------------------------------------
# 자식 프로세스 진입점 (fork 후 execv 대응)
# ---------------------------------------------------------------------------

def _child_exec(exec_args: list) -> None:
    """
    자식 프로세스에서 os.execv()로 자기 자신을 재실행한다.
    C++ 의 execv(args[0], procArgs) 에 해당한다.
    """
    try:
        os.execv(exec_args[0], exec_args)
    except OSError as e:
        logger.error("execv fail(%s) : %s", exec_args[0], e)
        sys.exit(0)