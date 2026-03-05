# -*- coding: utf-8 -*-
"""
frDbResultSet.h / frDbResultSet.C  →  fr_db_result_set.py
Python 3.11

변환 설계:
  frDbRecordSet → DbRecordSet

C++ → Python 주요 변환:
  friend class frDbSession   → DbSession 의 _fetch_data / _close_cursor 호출
  frDbDescRecordList*        → DbDescRecordList (인스턴스)
  frDbDefRecordList*         → DbDefRecordList  (인스턴스)
  frDbParam*                 → DbParam          (인스턴스)
  void* m_Cursor             → object (cx_Oracle cursor 또는 None)
  MoveFirst / MoveLast       → 원본 미구현 → 구현 추가
"""

import logging
from typing import Optional, TYPE_CHECKING

from Class.SqlType.fr_db_base_type import (
    DbType,
    DbDescRecordList, DbDefRecordList,
    RsFetchInfo,
)
from Class.SqlType.fr_db_param import DbParam, DbRecord

if TYPE_CHECKING:
    from Class.Sql.fr_db_session import DbSession

logger = logging.getLogger(__name__)


class DbRecordSet:
    """
    C++ frDbRecordSet 대응.
    execute_rs() 가 반환하는 스트리밍 커서 래퍼.

    MoveNext() 를 반복 호출하여 한 행씩 fetch.
    모든 행을 소비하거나 소멸 시 커서를 자동 해제.

    사용 예:
        rs = session.execute_rs("SELECT ...")
        if rs.is_valid():
            while True:
                record = rs.move_next()
                if record is None:
                    break
                print(record.values)
    """

    def __init__(self, db_session: "DbSession", db_kind: int) -> None:
        self._db_session: "DbSession"       = db_session
        self._db_kind:    int               = db_kind

        self._is_valid:   bool              = False
        self._is_end_row: bool              = False

        self._cursor:     object            = None   # C++ void* m_Cursor
        self._db_param:   DbParam           = DbParam()
        self._desc_list:  DbDescRecordList  = DbDescRecordList()
        self._def_list:   DbDefRecordList   = DbDefRecordList()
        self._fetch_info: RsFetchInfo | None = None

        self.error: str = ""    # C++ m_Error
        self.query: str = ""    # C++ m_Query

    def __del__(self) -> None:
        self._close()

    def __iter__(self):
        """Python iterator 지원 — for record in rs: 사용 가능."""
        return self

    def __next__(self) -> DbRecord:
        record = self.move_next()
        if record is None:
            raise StopIteration
        return record

    # ------------------------------------------------------------------ #
    # 내부 해제
    # ------------------------------------------------------------------ #
    def _close(self) -> None:
        """C++ 소멸자 대응. 커서 및 리소스 해제."""
        if self._cursor is not None:
            try:
                self._db_session._close_cursor(self._cursor)
            except Exception:
                pass
            self._cursor = None

        if self._fetch_info is not None:
            self._fetch_info = None

    # ------------------------------------------------------------------ #
    # 유효성
    # ------------------------------------------------------------------ #
    def is_valid(self) -> bool:
        """C++ IsValid() 대응."""
        return self._is_valid

    # ------------------------------------------------------------------ #
    # 행/열 수
    # ------------------------------------------------------------------ #
    def get_col(self) -> int:
        """C++ GetCol() 대응."""
        return self._db_param.get_col()

    def get_row(self) -> int:
        """C++ GetRow() — 현재까지 fetch 된 행 수."""
        return self._db_param.get_row()

    def set_col(self, col: int) -> None:
        """C++ SetCol() 대응. execute_rs() 내부에서 호출."""
        self._db_param.set_col(col)

    def set_row(self, row: int) -> None:
        """C++ SetRow() 대응."""
        self._db_param.set_row(row)

    # ------------------------------------------------------------------ #
    # 커서 이동
    # ------------------------------------------------------------------ #
    def move_next(self) -> DbRecord | None:
        """
        C++ MoveNext() 대응.
        다음 행을 fetch 하여 DbRecord 반환.
        더 이상 행이 없으면 None 반환.
        """
        if not self.get_col() or self._is_end_row:
            return None

        # FetchInfo 최초 생성 (커서 + 컬럼 메타 묶음)
        if self._fetch_info is None:
            self._fetch_info = RsFetchInfo(
                cursor    = self._cursor,
                col_cnt   = self.get_col(),
                desc_list = self._desc_list,
                def_list  = self._def_list,
            )

        record = self._db_session._fetch_data(self._fetch_info)
        if record is not None:
            self._db_param.add_record(record)
        else:
            self._is_end_row = True

        return record

    def move_first(self) -> DbRecord | None:
        """
        C++ MoveFirst() 대응 (원본 미구현).
        이미 fetch 된 레코드가 있으면 첫 번째 반환,
        없으면 move_next() 로 첫 행 fetch.
        """
        if self._db_param.get_row() > 0:
            self._db_param.rewind()
            return self._db_param.get_record_head()
        return self.move_next()

    def move_last(self) -> DbRecord | None:
        """
        C++ MoveLast() 대응 (원본 미구현).
        모든 행을 fetch 한 뒤 마지막 레코드 반환.
        """
        last: DbRecord | None = None
        while True:
            record = self.move_next()
            if record is None:
                break
            last = record
        return last

    def fetch_all(self) -> list[DbRecord]:
        """
        전체 행을 한 번에 fetch 하여 리스트로 반환.
        Python 편의 메서드 (C++ 원본 없음).
        """
        records: list[DbRecord] = []
        while True:
            record = self.move_next()
            if record is None:
                break
            records.append(record)
        return records