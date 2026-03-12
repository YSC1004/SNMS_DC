# -*- coding: utf-8 -*-
"""
SockMgrConnMgr.h / SockMgrConnMgr.C  →  SockMgrConnMgr.py
Python 3.11.10 변환

변환 설계:
  SockMgrConnMgr → SockMgrConnMgr  (ConnectionMgr 상속)

C++ → Python 주요 변환 포인트:
  new SockMgrConnection(this)  → SockMgrConnection(self)  (GC 위임)
  Accept(mgrConn)              → self.accept(mgr_conn)
  GetObjErrMsg()               → self.get_obj_err_msg()
  Add(mgrConn)                 → self.add(mgr_conn)
  mgrConn->GetPeerIp()         → mgr_conn.get_peer_ip()

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging

from Common.ConnectionMgr import ConnectionMgr
from Common.SockMgrConnection import SockMgrConnection

logger = logging.getLogger(__name__)


class SockMgrConnMgr(ConnectionMgr):
    """
    C++ SockMgrConnMgr 대응.
    ConnectionMgr 를 상속하며 SockMgrConnection 소켓 accept 를 담당.
    """

    def __init__(self) -> None:
        super().__init__()

    def accept_socket(self) -> None:
        """
        C++ AcceptSocket() 대응.
        새 SockMgrConnection 을 생성하여 accept 후 연결 목록에 추가.
        실패 시 에러 로그 출력.
        """
        mgr_conn = SockMgrConnection(self)
        if not self.accept(mgr_conn):
            logger.debug("Mgr Socket Accept Error : %s", self.get_obj_err_msg())
            return
        self.add(mgr_conn)
        logger.debug("Connection Mgr Sock(%s)", mgr_conn.get_peer_ip())