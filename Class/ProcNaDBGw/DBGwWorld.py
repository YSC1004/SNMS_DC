"""
DBGwWorld.py
C++ DBGwWorld.h/.C → Python 변환

ProcNaDBGw 프로세스의 최상위 애플리케이션 클래스.
AsProcWorldBase를 상속하며 두 가지 실행 모드를 지원한다.

[일반 모드]  : DBGwMgr를 생성하고 지정 포트에서 Listen 시작
[Alone 모드] : fork된 자식 프로세스에서 -sessionid로 전달받은 FD로
               DBGwServerSession을 직접 실행 (1:1 전용 세션)
"""

import os
import sys
import logging
from typing import Optional, ClassVar

from Common.AsWorld import AsProcWorldBase      # 변환 완료된 Common 모듈
from ProcNaDBGw.DBGwMgr import DBGwMgr
from libDBGw.libDBGwBase.DBGwType import eDB_TYPE
from libDBGw.libDBGwSvr.DBGwServerSession import DBGwServerSession
from Util.fr_arg_parser import ArgParser

logger = logging.getLogger(__name__)

# C++ : #define MAINPTR DBGwWorld::m_WorldPtr
# Python : 모듈 레벨 접근 함수로 제공 (또는 DBGwWorld.m_WorldPtr 직접 참조)
def MAINPTR() -> "DBGwWorld":
    return DBGwWorld.m_WorldPtr


class DBGwWorld(AsProcWorldBase):
    """
    DBGw 프로세스 월드 클래스 (싱글톤 패턴).

    C++ IMPL_PROC(DBGwWorld, "DBGw") 매크로 대응:
      - 프로세스 이름 "DBGw" 등록
      - m_WorldPtr 싱글톤 포인터 유지
    """

    # C++ : static DBGwWorld* m_WorldPtr
    m_WorldPtr: ClassVar[Optional["DBGwWorld"]] = None

    # 프로세스 식별 이름 (IMPL_PROC 매크로 두 번째 인자)
    PROC_NAME: ClassVar[str] = "DBGw"

    def __init__(self) -> None:
        super().__init__()
        DBGwWorld.m_WorldPtr = self

    def __del__(self) -> None:
        pass

    # -------------------------------------------------------------------------
    # AsProcWorldBase override
    # -------------------------------------------------------------------------

    def AppStart(self, Argc: int, Argv: list[str]) -> bool:
        """
        프로세스 시작 진입점.

        실행 모드 판별:
          1. -sessionid 존재 → Alone 모드 (fork된 자식 세션)
          2. -dbgwport 존재 → 일반 서버 모드 (Listen + Accept)
          3. 둘 다 없음    → 사용법 출력 후 False 반환

        Args:
            Argc : sys.argv 길이
            Argv : sys.argv 리스트

        Returns:
            True  : 정상 시작
            False : 인자 오류 또는 포트 바인딩 실패
        """
        logger.setLevel(logging.DEBUG)   # frLogger::Enable("DBGwWorld", 5) 대응

        args = ArgParser(Argv)

        # 사용법 출력 (C++ -name 체크 대응)
        if args.get_value("-name"):
            print("\n[Usage] ./procNaDBGw -alone -name DB_GW "
                  "-dbgwport 4100 -log (off) &\n")

        # ── Alone 모드 ──────────────────────────────────────────────────────
        if args.does_it_exist("-sessionid"):
            parent_pid = os.getppid()
            session_id = int(args.get_value("-sessionid"))
            logger.info("parentPID : %d, sessionid : %d", parent_pid, session_id)

            session = DBGwServerSession(eDB_TYPE.eDB_ORACLE_OCI2)
            session.m_IsAloneMode   = True
            session.m_IsLoggingMode = True

            # -log off 처리
            log_val = args.get_value("-log")
            if log_val and log_val.upper() == "OFF":
                session.m_IsLoggingMode = False

            # 로그 디렉토리 설정 (BASE_MAINPTR->GetLogDir() 대응)
            from Common.AsWorld import BASE_MAINPTR  # type: ignore
            session.m_LogDir = BASE_MAINPTR().GetLogDir()

            # 전달받은 FD로 소켓 세션 활성화
            session.SetFD(session_id)
            session.Enable()
            return True

        # ── 일반 서버 모드 ───────────────────────────────────────────────────
        db_gw_port_str = args.get_value("-dbgwport")
        if not db_gw_port_str:
            print(f"\n## [Usage] {Argv[0]} -dbgwport 410x\n")
            logger.error("## [Usage] %s -dbgwport 410x", Argv[0])
            return False

        db_gw_port = int(db_gw_port_str)

        gw = DBGwMgr(eDB_TYPE.eDB_ORACLE_OCI2)

        if gw.Run(db_gw_port):
            gw.SetLogDir(self.GetLogDir())
            logger.debug("DBGwMgr Run Success (pid:%d)(port:%d)",
                         os.getpid(), db_gw_port)
        else:
            logger.error("DBGwMgr Run Error(port:%d) : %s",
                         db_gw_port, gw.GetObjErrMsg())
            return False

        return True