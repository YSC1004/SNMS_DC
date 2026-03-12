"""
DBGwServerSession.py
C++ DBGwServerSession.h/.C → Python 변환

DBGwBaseSocket을 상속받아 클라이언트 연결 세션 1개를 담당한다.
패킷 수신 시 DBGwServer에 위임하고,
소켓 종료 시 AloneMode(단독 실행 모드)이면 로그 파일을 삭제하고 프로세스를 종료한다.
"""

import os
import sys
import logging
from typing import Optional, TYPE_CHECKING

from libDBGw.libDBGwBase.DBGwBaseSocket import DBGwBaseSocket
from libDBGw.libDBGwBase.DBGwType import PACKET_T

# 순환 참조 방지: 타입 힌트 전용 import
if TYPE_CHECKING:
    from libDBGw.libDBGwSvr.DBGwServer import DBGwServer

logger = logging.getLogger(__name__)


class DBGwServerSession(DBGwBaseSocket):
    """
    DB Gateway 서버 측 클라이언트 세션 클래스.

    - DBGwBaseSocket 상속 : 소켓 송수신 기반
    - 수신 패킷은 DBGwServer에 위임
    - m_IsAloneMode=True 이면 소켓 종료 시 로그 파일 삭제 후 프로세스 종료
    """

    def __init__(self,
                 DbKind: int,
                 DefaultDbUser: str = "",
                 DefaultDbPasswd: str = "",
                 DefaultDbName: str = "") -> None:
        super().__init__()

        # 순환 참조를 런타임에 해소하기 위해 여기서 import
        from libDBGw.libDBGwSvr.DBGwServer import DBGwServer

        self.m_DBGwSvr: "DBGwServer" = DBGwServer(
            self, DbKind, DefaultDbUser, DefaultDbPasswd, DefaultDbName
        )
        self.m_IsAloneMode: bool   = False
        self.m_IsLoggingMode: bool = False
        self.m_LogDir: str         = "."

    def __del__(self) -> None:
        # DBGwServer 명시적 정리 (GC 순서 보장 목적)
        self.m_DBGwSvr = None

    # -------------------------------------------------------------------------
    # DBGwBaseSocket override
    # -------------------------------------------------------------------------

    def ReceivePacket(self,
                      Packet: PACKET_T,
                      SessionIdentify: int = -1) -> None:
        """수신된 패킷을 DBGwServer로 위임한다."""
        self.m_DBGwSvr.ReceivePacket(Packet)

    def CloseSocket(self, Errno: int) -> None:
        """
        소켓 종료 처리.

        - 소켓을 닫는다.
        - AloneMode이면 로그 파일 삭제 후 sys.exit(1).
        - 일반 모드이면 세션 객체 자원을 정리한다.

        C++ 의 `delete this` → Python에서는 참조를 모두 제거하면
        GC가 처리하므로, 여기서는 내부 자원을 명시적으로 None 처리한다.
        """
        self.Close()
        # self.m_DBGwSvr.CloseSession(Errno)  # C++ 원본과 동일하게 주석 유지

        logger.info("Closed Session")

        if self.m_IsAloneMode:
            log_file: str = self.m_DBGwSvr.GetLogFile()
            logger.info("LOG FILE : [%s], PID[%d]", log_file, os.getpid())

            if log_file:
                # C++: remove() + unlink() 이중 삭제 → Python: 단일 os.remove()
                try:
                    os.remove(log_file)
                except OSError as e:
                    logger.warning("Failed to remove log file [%s]: %s", log_file, e)

            sys.exit(1)

        # 일반 모드 : C++ `delete this` 에 해당하는 자원 정리
        self.m_DBGwSvr = None