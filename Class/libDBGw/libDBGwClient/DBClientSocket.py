# -*- coding: utf-8 -*-
"""
DBClientSocket.h / DBClientSocket.C  →  DBClientSocket.py
Python 3.11.10 변환

변환 설계:
  DBClientSocket → DBClientSocket  (DBGwBaseSocket 상속)

C++ → Python 주요 변환 포인트:
  Disable()                  → self.disable()  (생성자에서 호출)
  ReceivePacket(PACKET_T*)   → receive_packet(packet, session_identify)
  CloseSocket(int)           → close_socket(errno_val)
  Close()                    → self.close()
  m_DbGwUser->ReceivePacket  → self._db_gw_user.receive_packet(packet)
  m_DbGwUser->CloseSession   → self._db_gw_user.close_session(errno_val)
  DBGwUser*                  → TYPE_CHECKING 전용 임포트 (순환 참조 방지)

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
from typing import TYPE_CHECKING

from libDBGw.libDBGwBase.DBGwBaseSocket import DBGwBaseSocket
from Common.CommType import PacketT

if TYPE_CHECKING:
    from libDBGw.libDBGwClient.DBGwUser import DBGwUser

logger = logging.getLogger(__name__)


class DBClientSocket(DBGwBaseSocket):
    """
    C++ DBClientSocket 대응.
    DB Gateway 클라이언트 소켓.
    수신 패킷과 소켓 종료 이벤트를 DBGwUser 로 위임한다.
    """

    def __init__(self, gw_user: 'DBGwUser') -> None:
        super().__init__()
        self._db_gw_user = gw_user
        self.disable()

    def receive_packet(self, packet: PacketT, session_identify: int = -1) -> None:
        """C++ ReceivePacket() 대응. DBGwUser 로 패킷 위임."""
        self._db_gw_user.receive_packet(packet)

    def close_socket(self, errno_val: int) -> None:
        """C++ CloseSocket() 대응. 소켓 닫고 DBGwUser 세션 종료 통보."""
        self.close()
        self._db_gw_user.close_session(errno_val)