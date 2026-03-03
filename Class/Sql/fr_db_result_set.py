"""
frDbResultSet.h / frDbResultSet.C  →  fr_db_result_set.py

변환 매핑:
  frDbRecordSet          → DbRecordSet
  frDbSession* (friend)  → DbSession 참조 (순환 참조 방지: TYPE_CHECKING)
  frDbParam*             → DbParam
  frDbDescRecordList*    → DbDescRecordList
  frDbDefRecordList*     → DbDefRecordList
  RsFetchInfo*           → RsFetchInfo
  void* m_Cursor         → Any (DB 드라이버 커서 객체)

  MoveNext()             → move_next()   : 한 행씩 fetch
  MoveFirst()            → move_first()  : 첫 행으로 이동 (결과 재순회)
  MoveLast()             → move_last()   : 마지막 행까지 모두 fetch
  IsValid()              → is_valid()

설계:
  - C++ 에서 frDbSession 이 friend 로 내부 멤버를 직접 설정했던 부분은
    Python 에서 DbSession 이 DbRecordSet 의 메서드를 통해 설정.
  - MoveFirst() 는 C++ 헤더에 선언됐지만 구현이 없었음 →
    Python 에서 rewind + 첫 레코드 반환으로 구현.
  - MoveLast() 도 선언만 있었음 → 전체 fetch 후 마지막 행 반환으로 구현.
  - Python iterator 지원 추가 (for record in rs:)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Iterator, Optional

from Class.SqlType.fr_db_base_type import (
    DbDescRecordList,
    DbDefRecordList,
    DbType,
    RsFetchInfo,
)
from Class.SqlType.fr_db_param import DbParam, DbRecord

if TYPE_CHECKING:
    from Class.Sql.fr_db_session import DbSession   # 순환 참조 방지

logger = logging.getLogger(__name__)


class DbRecordSet:
    """
    DB 쿼리 결과 커서 및 레코드 순회 클래스 (frDbRecordSet 대응).

    DbSession.execute_query() 가 반환하며, 직접 생성하지 않는 것이 원칙.
    """

    def __init__(self, db_session: "DbSession", db_kind: int):
        """
        C++ frDbRecordSet(frDbSession*, int DbKind) 대응.
        db_kind: DbType enum 값
        """
        self._is_valid:   bool                      = False
        self._is_end_row: bool                      = False
        self._db_session: "DbSession"               = db_session
        self._db_kind:    int                       = db_kind
        self._cursor:     Any                       = None
        self._desc_list:  DbDescRecordList          = DbDescRecordList()
        self._def_list:   DbDefRecordList           = DbDefRecordList()
        self._db_param:   DbParam                   = DbParam()
        self._fetch_info: Optional[RsFetchInfo]     = None

        # 외부에서 읽기 가능한 속성
        self.error: str = ""
        self.query: str = ""

    def __del__(self):
        self._close()

    def __enter__(self) -> "DbRecordSet":
        return self

    def __exit__(self, *_) -> None:
        self._close()

    # ------------------------------------------------------------------ #
    # 유효성 확인
    # ------------------------------------------------------------------ #

    def is_valid(self) -> bool:
        """C++ IsValid() 대응."""
        return self._is_valid

    # ------------------------------------------------------------------ #
    # 행 이동 / Fetch
    # ------------------------------------------------------------------ #

    def move_next(self) -> Optional[DbRecord]:
        """
        C++ MoveNext() 대응.
        다음 행을 DB 에서 fetch 하여 반환.
        더 이상 행이 없으면 None.

        동작:
          1) FetchInfo 미생성 시 최초 1회 생성
          2) DbSession._fetch_data() 로 한 행 fetch
          3) 결과를 m_DbParam 에 AddRecord
          4) 행 없으면 m_IsEndRow = True
        """
        if not self._db_param.get_col():
            return None

        if self._is_end_row:
            return None

        # FetchInfo 최초 생성
        if self._fetch_info is None:
            self._fetch_info = RsFetchInfo(
                cursor    = self._cursor,
                col_cnt   = self._db_param.get_col(),
                desc_list = self._desc_list,
                def_list  = self._def_list,
            )

        record = self._db_session._fetch_data(self._fetch_info)
        if record:
            self._db_param.add_record(record)
        else:
            self._is_end_row = True

        return record

    def move_first(self) -> Optional[DbRecord]:
        """
        C++ MoveFirst() 대응 (구현 없었음 → 첫 레코드 반환으로 구현).
        이미 fetch 된 레코드가 있으면 첫 번째 반환,
        없으면 move_next() 호출.
        """
        if self._db_param.get_row() > 0:
            return self._db_param.get_record_head()
        return self.move_next()

    def move_last(self) -> Optional[DbRecord]:
        """
        C++ MoveLast() 대응 (구현 없었음 → 전체 fetch 후 마지막 반환).
        """
        last: Optional[DbRecord] = None
        while True:
            rec = self.move_next()
            if rec is None:
                break
            last = rec
        return last

    def fetch_all(self) -> list[DbRecord]:
        """
        모든 행을 fetch 하여 리스트로 반환 (Python 추가 편의 메서드).
        """
        records: list[DbRecord] = []
        while True:
            rec = self.move_next()
            if rec is None:
                break
            records.append(rec)
        return records

    # ------------------------------------------------------------------ #
    # 행/열 수
    # ------------------------------------------------------------------ #

    def get_col(self) -> int:
        """C++ GetCol() 대응."""
        return self._db_param.get_col()

    def get_row(self) -> int:
        """C++ GetRow() 대응. (fetch 된 행 수)"""
        return self._db_param.get_row()

    def set_col(self, col: int) -> None:
        """C++ SetCol() 대응. DbSession 이 쿼리 실행 후 설정."""
        self._db_param.set_col(col)

    def set_row(self, row: int) -> None:
        """C++ SetRow() 대응."""
        self._db_param.set_row(row)

    # ------------------------------------------------------------------ #
    # DbParam / Cursor 접근 (DbSession friend 접근 대응)
    # ------------------------------------------------------------------ #

    @property
    def db_param(self) -> DbParam:
        """내부 DbParam 접근 (DbSession 에서 사용)."""
        return self._db_param

    def set_cursor(self, cursor: Any) -> None:
        """DB 드라이버 커서 설정 (DbSession 이 호출)."""
        self._cursor = cursor

    def set_valid(self, valid: bool) -> None:
        """유효성 플래그 설정 (DbSession 이 호출)."""
        self._is_valid = valid

    # ------------------------------------------------------------------ #
    # Python iterator 지원
    # ------------------------------------------------------------------ #

    def __iter__(self) -> Iterator[DbRecord]:
        """
        for record in rs: 직접 순회 지원.
        이미 fetch 된 레코드 + 미fetch 행 모두 순회.
        """
        # 이미 fetch 된 레코드 먼저 반환
        for rec in self._db_param.get_value() or []:
            yield DbRecord(rec)

        # 나머지 fetch
        while not self._is_end_row:
            rec = self.move_next()
            if rec is None:
                break
            yield rec

    def __len__(self) -> int:
        return self._db_param.get_row()

    def __repr__(self) -> str:
        return (
            f"DbRecordSet(valid={self._is_valid}, "
            f"rows={self.get_row()}, cols={self.get_col()}, "
            f"end={self._is_end_row})"
        )

    # ------------------------------------------------------------------ #
    # 내부 정리
    # ------------------------------------------------------------------ #

    def _close(self) -> None:
        """
        C++ ~frDbRecordSet() 대응.
        커서 닫기 + 내부 객체 정리.
        """
        try:
            if self._cursor and self._db_session:
                self._db_session._close_cursor(self._cursor)
                self._cursor = None
        except Exception as e:
            logger.debug("DbRecordSet._close: %s", e)

        self._desc_list.clear_all()
        self._def_list.clear_all()
        self._db_param.clear()
        self._fetch_info = None