# -*- coding: utf-8 -*-
"""
frDbParam.h / frDbParam.C  →  fr_db_param.py
Python 3.11

변환 설계:
  frDbRecord      → DbRecord      (linked-list 노드)
  frDbBinder      → DbBinder      (바인드 정보)
  frDbBinderList  → list[DbBinder]
  frDbParam       → DbParam       (쿼리 실행 파라미터 + 결과 보관)

C++ → Python 주요 변환:
  char** m_Values (malloc)   → list[str]
  char*** m_ResultPtr        → list[list[str]]  (get_value() 캐시)
  linked-list (m_Next)       → list[DbRecord] 로 내부 관리
  frDbBinder enum            → DbBinder.BindType (IntEnum)
  atoi/atol/atof             → int() / float()
"""

import logging
from enum import IntEnum
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# DbRecord  (C++ frDbRecord 대응)
# ─────────────────────────────────────────────────────────────────────────────
class DbRecord:
    """
    C++ frDbRecord 대응.
    한 행(row)의 컬럼 값 목록을 보관.
    C++ 의 char** m_Values / int* m_ColSize → list[str] 로 단순화.
    """

    def __init__(self, col: int = 0) -> None:
        self.col:       int       = col          # C++ m_Col
        self.values:    list[str] = [''] * col   # C++ char** m_Values
        self.col_sizes: list[int] = [0]  * col   # C++ int* m_ColSize

    def set_value(self, col_idx: int, value: str) -> None:
        """컬럼 값 세팅 (MySQLSession / OraSession2 에서 호출)."""
        self.values[col_idx]    = value
        self.col_sizes[col_idx] = len(value)

    def clear(self) -> None:
        """C++ Clear() 대응."""
        self.values    = []
        self.col_sizes = []
        self.col       = 0

    def __repr__(self) -> str:
        return f"DbRecord(col={self.col}, values={self.values})"


# ─────────────────────────────────────────────────────────────────────────────
# DbBinder  (C++ frDbBinder 대응)
# ─────────────────────────────────────────────────────────────────────────────
class DbBinder:
    """
    C++ frDbBinder 대응.
    Next() 호출 시 컬럼 값을 외부 변수에 바인딩하는 정보.
    Python 에서는 가변 컨테이너(list)로 참조를 흉내냄.
    """

    class BindType(IntEnum):
        STRING = 0
        INT    = 1
        LONG   = 2
        FLOAT  = 3
        DATE   = 4

    def __init__(self, col: int, var: list, bind_type: "DbBinder.BindType") -> None:
        """
        col      : 1-based 컬럼 번호 (C++ 원본 동일)
        var      : [value] 형태의 1원소 list — Python 에서 참조 전달 흉내
        bind_type: DbBinder.BindType
        """
        self.col:       int               = col
        self.var:       list              = var
        self.bind_type: DbBinder.BindType = bind_type


# ─────────────────────────────────────────────────────────────────────────────
# DbParam  (C++ frDbParam 대응)
# ─────────────────────────────────────────────────────────────────────────────
class DbParam:
    """
    C++ frDbParam 대응.
    쿼리 문자열 보관 + 실행 결과(DbRecord 리스트) 관리.

    C++ linked-list(m_Record→m_Next) → Python list[DbRecord] 로 변환.
    get_value() 의 char*** 반환     → list[list[str]] 로 변환.
    """

    def __init__(self) -> None:
        self._query:      str            = ""
        self._records:    list[DbRecord] = []
        self._cur_idx:    int            = 0      # Rewind/Next 커서
        self._col:        int            = 0
        self._binders:    list[DbBinder] = []
        self._result_cache: list[list[str]] | None = None  # get_value() 캐시

    # ------------------------------------------------------------------ #
    # 쿼리 설정
    # ------------------------------------------------------------------ #
    def set_query(self, query: str) -> None:
        """C++ SetQuery() 3종 오버로드 통합."""
        self.clear()
        self._query = query

    def get_query(self) -> str:
        """C++ GetQuery() 대응."""
        return self._query

    # ------------------------------------------------------------------ #
    # 행/열 수
    # ------------------------------------------------------------------ #
    def get_row(self) -> int:
        """C++ GetRow() 대응."""
        return len(self._records)

    def get_col(self) -> int:
        """C++ GetCol() 대응."""
        return self._col

    def set_col(self, col: int) -> None:
        """C++ SetCol() 대응."""
        self._col = col

    def set_row(self, row: int) -> None:
        """C++ SetRow() 대응 — 직접 사용 거의 없음."""
        pass  # list 로 관리하므로 별도 세팅 불필요

    # ------------------------------------------------------------------ #
    # 레코드 추가
    # ------------------------------------------------------------------ #
    def add_record(self, record: DbRecord) -> None:
        """C++ AddRecord() 대응."""
        self._records.append(record)
        self._result_cache = None   # 캐시 무효화

    def get_record_head(self) -> DbRecord | None:
        """C++ GetRecordHead() 대응."""
        return self._records[0] if self._records else None

    # ------------------------------------------------------------------ #
    # 값 조회  (C++ GetValue 3종 오버로드)
    # ------------------------------------------------------------------ #
    def get_value_at(self, row: int, col: int) -> str | None:
        """C++ GetValue(int row, int col) 대응."""
        if row >= self.get_row() or col >= self._col:
            return None
        return self._records[row].values[col]

    def get_row_values(self, row: int) -> list[str] | None:
        """C++ GetValue(int row) → char** 대응."""
        if row >= self.get_row():
            return None
        return self._records[row].values

    def get_value(self) -> list[list[str]] | None:
        """
        C++ GetValue() → char*** 대응.
        buf[row][col] 형태의 2D 리스트 반환 (캐시).
        QueryResult.buf 에 직접 대입해서 사용.
        """
        if not self._records:
            return None
        if self._result_cache is None:
            self._result_cache = [r.values for r in self._records]
        return self._result_cache

    # ------------------------------------------------------------------ #
    # 바인더  (Next() 호출 시 외부 변수에 값 복사)
    # ------------------------------------------------------------------ #
    def bind(self, col: int, var: list,
             bind_type: DbBinder.BindType = DbBinder.BindType.STRING) -> None:
        """
        C++ Bind(int col, T& var) 4종 오버로드 통합.

        Python 에서는 참조 전달이 없으므로
        var = [initial_value] 형태의 1원소 리스트를 전달한다.

        사용 예:
            result = ['']
            param.bind(1, result, DbBinder.BindType.STRING)
            while param.next():
                print(result[0])
        """
        self._binders.append(DbBinder(col, var, bind_type))

    def rewind(self) -> None:
        """C++ Rewind() 대응. 커서를 첫 번째 레코드로 복귀."""
        self._cur_idx = 0

    def next(self) -> bool:
        """
        C++ Next() 대응.
        현재 레코드의 값을 바인더에 복사하고 커서를 전진.
        바인더가 없어도 커서만 전진하여 True 반환.
        """
        if self._cur_idx >= len(self._records):
            return False
        self._eval(self._records[self._cur_idx])
        self._cur_idx += 1
        return True

    def _eval(self, record: DbRecord) -> None:
        """C++ _Eval() 대응. 바인더에 현재 레코드 값 복사."""
        for binder in self._binders:
            col = binder.col - 1   # 1-based → 0-based
            if col < 0 or col >= self._col:
                continue
            value = record.values[col]
            try:
                if binder.bind_type == DbBinder.BindType.STRING:
                    binder.var[0] = value
                elif binder.bind_type == DbBinder.BindType.INT:
                    binder.var[0] = int(value) if value else 0
                elif binder.bind_type == DbBinder.BindType.LONG:
                    binder.var[0] = int(value) if value else 0
                elif binder.bind_type == DbBinder.BindType.FLOAT:
                    binder.var[0] = float(value) if value else 0.0
            except (ValueError, IndexError) as e:
                logger.warning("DbParam._eval bind error col=%d: %s", col, e)

    # ------------------------------------------------------------------ #
    # 초기화
    # ------------------------------------------------------------------ #
    def clear(self) -> None:
        """C++ Clear() 대응."""
        self._binders.clear()
        self._records.clear()
        self._result_cache = None
        self._col     = 0
        self._cur_idx = 0