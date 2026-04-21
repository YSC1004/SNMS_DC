"""
SimsConnMgr.py
C++ SimsConnMgr.h/.C → Python 변환

SIMS 시스템 연결 관리자.
  - C++: frSocketSensor 상속 → Python: ConnectionMgr 상속
    (Accept() 사용을 위해 ConnectionMgr 기반으로 변환)
  - AcceptSocket 시 ExternalConnection 생성 후
    ExternalConnMgr(_ext_mgr)에 add() — 자신의 리스트가 아닌 ExtMgr에 위임
  - ExternalConnMgr와 소켓 리스너를 분리하는 패턴:
    SimsConnMgr는 별도 포트를 Listen하지만
    접속된 커넥션은 ExternalConnMgr가 관리
"""

import logging
from typing import TYPE_CHECKING

from Common.ConnectionMgr import ConnectionMgr          # Accept() 사용 (치트시트)

if TYPE_CHECKING:
    from ProcNaServer.ExternalConnMgr import ExternalConnMgr

logger = logging.getLogger(__name__)


class SimsConnMgr(ConnectionMgr):
    """
    C++ SimsConnMgr (frSocketSensor 상속) 대응.

    C++ frSocketSensor → Python ConnectionMgr
      frSocketSensor는 소켓 수락(Accept) 기능만 제공하는 베이스.
      Python에서는 Accept()가 ConnectionMgr에 구현되어 있으므로
      ConnectionMgr를 상속하여 동일한 기능 활용.

    핵심 특징:
      Accept한 ExternalConnection을 자신이 아닌
      m_ExtMgr(ExternalConnMgr)에 add() — C++ 원본 동일.
    """

    def __init__(self, ext_mgr: "ExternalConnMgr") -> None:
        super().__init__()
        self._ext_mgr: "ExternalConnMgr" = ext_mgr

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """
        C++: AcceptSocket()
        SIMS 포트로 접속한 클라이언트를 ExternalConnection으로 수락.
        커넥션 관리는 ExternalConnMgr에 위임 (m_ExtMgr->Add).
        """
        from ProcNaServer.ExternalConnection import ExternalConnection

        conn = ExternalConnection(self._ext_mgr)
        if not self.Accept(conn):
            logger.error("Sims Connection Accept Error : %s",
                         self.GetObjErrMsg())
            return

        # ── 핵심: 자신(SimsConnMgr)이 아닌 ExtMgr에 add ──────────────────
        self._ext_mgr.add(conn)                     # ConnectionMgr.add()
        logger.debug("Connected with Sims(%s)", conn.get_peer_ip())