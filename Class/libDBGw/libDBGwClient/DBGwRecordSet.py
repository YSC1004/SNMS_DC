# -*- coding: utf-8 -*-
"""
DBGwRecordSet.h / DBGwRecordSet.C  →  DBGwRecordSet.py
Python 3.11.10 변환

변환 설계:
  DBGwRecordSet → DBGwRecordSet

C++ → Python 주요 변환 포인트:
  frDbParam* m_DbParam        → FrDbParam() 인스턴스 (GC 위임)
  frDbRecord*                 → Optional[FrDbRecord]
  new char[DEF_BUF_SIZE]      → bytearray / bytes
  memset/memcpy               → 초기화 / bytes 연산
  SendAndWaitPacket(...)      → send_and_wait_packet(...)
  WaitPacket(...)             → wait_packet(...)
  SEG_ING                     → AS_SEGFLAG.SEG_ING
  size == -1 : 에러, -2 : EOR → 동일 처리
  MoveFirst / MoveLast        → None 반환 (C++ 원본과 동일)

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
from typing import Optional, TYPE_CHECKING

from libDBGw.libDBGwBase.DBGwType import (
    DB_RS_MOVE_NEXT_REQ, DB_RS_QUERY_DATA, DB_RS_CLOSE_REQ,
    DEF_BUF_SIZE,
    DbRsMoveNextReqT, DbRsQueryDataT, DbRsCloseReqT,
)
from Common.CommType import AS_SEGFLAG

if TYPE_CHECKING:
    from libDBGw.libDBGwClient.DBGwUser import DBGwUser
    from Sql.fr_db_session import FrDbParam, FrDbRecord

logger = logging.getLogger(__name__)


class DBGwRecordSet:
    """
    C++ DBGwRecordSet 대응.
    DB Gateway 를 통해 SELECT 결과를 레코드셋 방식으로 순회한다.
    """

    def __init__(self, gw_user: 'DBGwUser') -> None:
        from Sql.fr_db_session import FrDbParam
        self.query_id:    int             = 0
        self.db_param:    FrDbParam       = FrDbParam()
        self.error:       str             = ""
        self.query:       str             = ""
        self.is_end_row:  bool            = False
        self.is_valid:    bool            = False
        self.m_db_gw_user: 'DBGwUser'    = gw_user

    def __del__(self) -> None:
        self.close_record_set()

    # ── 상태 조회 ─────────────────────────────

    def is_valid_rs(self) -> bool:
        """C++ IsValid() 대응."""
        return self.is_valid

    def get_col(self) -> int:
        """C++ GetCol() 대응."""
        return self.db_param.get_col()

    def get_row(self) -> int:
        """C++ GetRow() 대응."""
        return self.db_param.get_row()

    def set_col(self, col: int) -> None:
        """C++ SetCol() 대응."""
        self.db_param.set_col(col)

    def set_row(self, row: int) -> None:
        """C++ SetRow() 대응."""
        self.db_param.set_row(row)

    # ── 레코드 이동 ───────────────────────────

    def move_next(self) -> Optional['FrDbRecord']:
        """
        C++ MoveNext() 대응.
        DB_RS_MOVE_NEXT_REQ 전송 → DB_RS_QUERY_DATA 수신 → 레코드 반환.
        size == -1 : 에러 → None
        size == -2 : EOR  → None (is_end_row = True)
        SEG_ING    : 분절 수신 → 조립 후 디코드
        """
        if self.is_end_row:
            return None

        req = DbRsMoveNextReqT(query_id=self.query_id)
        query_data = DbRsQueryDataT()

        sock = self.m_db_gw_user.db_client_socket
        if sock.send_and_wait_packet(
            DB_RS_MOVE_NEXT_REQ, req, DB_RS_QUERY_DATA, query_data
        ) <= 0:
            return None

        if query_data.size == -1:
            return None

        if query_data.size == -2:
            self.is_end_row = True
            return None

        # 분절(SEG_ING) 처리
        if query_data.seg_flag == AS_SEGFLAG.SEG_ING:
            buf = bytearray()
            buf += query_data.data.encode() if isinstance(query_data.data, str) else query_data.data

            while True:
                query_data = DbRsQueryDataT()
                if sock.wait_packet(DB_RS_QUERY_DATA, query_data) <= 0:
                    break
                chunk = query_data.data.encode() if isinstance(query_data.data, str) else query_data.data
                buf += chunk
                if query_data.seg_flag != AS_SEGFLAG.SEG_ING:
                    break

            return self.m_db_gw_user.decode_rs_data(self.get_col(), self.db_param, bytes(buf))

        return self.m_db_gw_user.decode_rs_data(
            self.get_col(), self.db_param, query_data.data
        )

    def move_first(self) -> None:
        """C++ MoveFirst() 대응 — NULL 반환 (미구현)."""
        return None

    def move_last(self) -> None:
        """C++ MoveLast() 대응 — NULL 반환 (미구현)."""
        return None

    # ── 레코드셋 닫기 ─────────────────────────

    def close_record_set(self) -> bool:
        """
        C++ CloseRecordSet() 대응.
        유효한 레코드셋이면 DB_RS_CLOSE_REQ 전송 후 is_valid = False.
        """
        if self.is_valid:
            req = DbRsCloseReqT(query_id=self.query_id, reserved=0)
            self.m_db_gw_user.db_client_socket.send_packet(DB_RS_CLOSE_REQ, req)
            self.is_valid = False
        return True