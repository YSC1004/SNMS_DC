"""
frDbParam.h / frDbParam.C  →  fr_db_param.py

변환 매핑:
  frDbRecord        → DbRecord       (연결 리스트 노드 → list 로 단순화)
  frDbBinder        → DbBinder       (dataclass)
  frDbBinderList    → list[DbBinder]
  frDbParam         → DbParam        (쿼리 + 결과 + 바인드 통합 관리)

설계 변경:
  C++ 연결 리스트(frDbRecord* m_Next) → Python list[list[str|None]]
  char*** m_ResultPtr                 → list[list[str|None]] (동일 구조)
  Bind(col, &var) 참조 전달          → Python 미지원 → binder 에 값 저장 후
                                        Next()/eval() 호출 시 딕셔너리로 반환
  Rewind() / Next() / _Eval()        → 이터레이터 패턴으로 재현

바인드 타입:
  STRING = 0, INT = 1, LONG = 2, FLOAT = 3, DATE = 4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Iterator

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# DbBinder  ←  frDbBinder
# ══════════════════════════════════════════════════════════════════════════════

class BinderType(IntEnum):
    """frDbBinder::enum 대응."""
    STRING = 0
    INT    = 1
    LONG   = 2
    FLOAT  = 3
    DATE   = 4


@dataclass
class DbBinder:
    """
    frDbBinder 대응.
    col    : 1-based 컬럼 번호 (C++ 원본 동일)
    btype  : BinderType
    name   : 결과 딕셔너리 키 (Python 추가, col 인덱스 대신 사용 가능)
    """
    col:   int         = 0
    btype: BinderType  = BinderType.STRING
    name:  str         = ""   # Python 추가: 결과 키 이름

    def convert(self, raw: Optional[str]):
        """
        raw 문자열 → btype 에 맞는 Python 값으로 변환.
        C++ _Eval() 내 switch(binder->m_Type) 대응.
        """
        if raw is None:
            return None
        try:
            if self.btype == BinderType.INT:
                return int(raw)
            elif self.btype in (BinderType.LONG, BinderType.FLOAT):
                return float(raw)
            else:   # STRING / DATE
                return raw
        except (ValueError, TypeError):
            return raw


# ══════════════════════════════════════════════════════════════════════════════
# DbRecord  ←  frDbRecord (연결 리스트 노드)
# ══════════════════════════════════════════════════════════════════════════════

class DbRecord:
    """
    frDbRecord 대응.
    C++ 연결 리스트(m_Next) 구조를 Python list 로 단순화.
    내부적으로 한 행(row)의 컬럼 값 리스트를 보유.
    """

    def __init__(self, values: list[Optional[str]]):
        self._values: list[Optional[str]] = values

    @property
    def col(self) -> int:
        return len(self._values)

    def get(self, col_idx: int) -> Optional[str]:
        """0-based 인덱스로 값 반환."""
        if 0 <= col_idx < len(self._values):
            return self._values[col_idx]
        return None

    @property
    def values(self) -> list[Optional[str]]:
        return self._values


# ══════════════════════════════════════════════════════════════════════════════
# DbParam  ←  frDbParam
# ══════════════════════════════════════════════════════════════════════════════

class DbParam:
    """
    frDbParam 대응.
    SQL 쿼리 문자열 + 결과 레코드 + 바인드 변수를 통합 관리.

    사용 예:
        param = DbParam()
        param.set_query("SELECT id, name FROM tb_user WHERE id = :1")
        param.bind(1, BinderType.INT, name="id")
        param.bind(2, BinderType.STRING, name="name")

        # DB 실행 후 결과 주입 (ProcNaDBGw 등에서 호출)
        param.add_record(DbRecord(["1", "ncadmin"]))
        param.add_record(DbRecord(["2", "admin"]))

        # 순회
        param.rewind()
        while param.next():
            row = param.current_row()   # {"id": 1, "name": "ncadmin"}
            print(row)

        # 또는 iterator
        for row in param:
            print(row)
    """

    def __init__(self):
        self._query:    str              = ""
        self._records:  list[DbRecord]   = []
        self._binders:  list[DbBinder]   = []
        self._row:      int              = 0
        self._col:      int              = 0
        self._cur_idx:  int              = 0    # Rewind/Next 이터레이터 위치

    # ------------------------------------------------------------------ #
    # 쿼리 설정
    # ------------------------------------------------------------------ #

    def set_query(self, query: str) -> None:
        """C++ SetQuery() 대응. 설정 시 내부 상태 초기화."""
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
        return self._row

    def get_col(self) -> int:
        """C++ GetCol() 대응."""
        return self._col

    def set_row(self, row: int) -> None:
        self._row = row

    def set_col(self, col: int) -> None:
        self._col = col

    # ------------------------------------------------------------------ #
    # 값 접근
    # ------------------------------------------------------------------ #

    def get_value(
        self,
        row: Optional[int] = None,
        col: Optional[int] = None,
    ) -> Optional[str] | list[Optional[str]] | list[list[Optional[str]]]:
        """
        C++ GetValue(row, col) / GetValue(row) / GetValue() 오버로드 통합.

        get_value(row, col) → str | None        (단일 셀, 0-based)
        get_value(row)      → list[str | None]   (행 전체, 0-based)
        get_value()         → list[list[...]]    (전체 2D)
        """
        if row is None and col is None:
            return [rec.values for rec in self._records]
        if col is None:
            if row < 0 or row >= self._row:
                return None
            return self._records[row].values
        if row < 0 or row >= self._row or col < 0 or col >= self._col:
            return None
        return self._records[row].get(col)

    def get_record_head(self) -> Optional[DbRecord]:
        """C++ GetRecordHead() 대응. 첫 번째 레코드 반환."""
        return self._records[0] if self._records else None

    # ------------------------------------------------------------------ #
    # 바인드
    # ------------------------------------------------------------------ #

    def bind(
        self,
        col:   int,
        btype: BinderType = BinderType.STRING,
        name:  str        = "",
    ) -> None:
        """
        C++ Bind(col, &var, type) 대응.
        Python 은 참조 전달이 없으므로 btype + name 만 등록하고,
        Next() 호출 시 current_row() 로 변환된 값을 반환.

        col  : 1-based 컬럼 번호 (C++ 원본 동일)
        btype: BinderType
        name : 결과 딕셔너리 키 (생략 시 "col_{col}")
        """
        bd = DbBinder(
            col   = col,
            btype = btype,
            name  = name or f"col_{col}",
        )
        self._binders.append(bd)

    # ── 편의 메서드 (C++ 타입별 오버로드 대응) ─────────────────────────────
    def bind_str(self,   col: int, name: str = "") -> None:
        self.bind(col, BinderType.STRING, name)

    def bind_int(self,   col: int, name: str = "") -> None:
        self.bind(col, BinderType.INT, name)

    def bind_long(self,  col: int, name: str = "") -> None:
        self.bind(col, BinderType.LONG, name)

    def bind_float(self, col: int, name: str = "") -> None:
        self.bind(col, BinderType.FLOAT, name)

    # ------------------------------------------------------------------ #
    # 레코드 관리
    # ------------------------------------------------------------------ #

    def add_record(self, record: DbRecord) -> None:
        """
        C++ AddRecord() 대응. 결과 레코드 추가.
        DB 드라이버(ProcNaDBGw 등)에서 fetch 결과를 주입할 때 사용.
        """
        self._records.append(record)
        self._row += 1
        if record.col > self._col:
            self._col = record.col

    def add_row(self, values: list[Optional[str]]) -> None:
        """Python 편의 메서드: 값 리스트로 직접 행 추가."""
        self.add_record(DbRecord(values))

    # ------------------------------------------------------------------ #
    # 순회 (Rewind / Next / _Eval)
    # ------------------------------------------------------------------ #

    def rewind(self) -> None:
        """C++ Rewind() 대응. 커서를 첫 행으로 초기화."""
        self._cur_idx = 0

    def next(self) -> bool:
        """
        C++ Next() 대응. 현재 행을 전진시키고,
        다음 행이 있으면 True.
        """
        if self._cur_idx < self._row:
            self._cur_idx += 1
            return True
        return False

    def current_row(self) -> dict:
        """
        C++ _Eval() 대응.
        현재 행의 값을 바인드 설정에 따라 변환하여 dict 로 반환.
        binder 가 없으면 {"col_0": val0, ...} 형태로 반환.
        """
        idx = self._cur_idx - 1
        if idx < 0 or idx >= self._row:
            return {}

        rec = self._records[idx]

        if self._binders:
            result = {}
            for bd in self._binders:
                col_0 = bd.col - 1    # 1-based → 0-based
                raw   = rec.get(col_0)
                result[bd.name] = bd.convert(raw)
            return result
        else:
            return {
                f"col_{i}": rec.get(i)
                for i in range(rec.col)
            }

    # ── Python iterator 지원 ────────────────────────────────────────────
    def __iter__(self) -> Iterator[dict]:
        """for row in param: 직접 순회 지원."""
        self.rewind()
        while self.next():
            yield self.current_row()

    def __len__(self) -> int:
        return self._row

    # ------------------------------------------------------------------ #
    # 초기화
    # ------------------------------------------------------------------ #

    def clear(self) -> None:
        """C++ Clear() 대응. 모든 상태 초기화."""
        self._records.clear()
        self._binders.clear()
        self._row     = 0
        self._col     = 0
        self._cur_idx = 0
        self._query   = ""

    def __repr__(self) -> str:
        return (
            f"DbParam(rows={self._row}, cols={self._col}, "
            f"query='{self._query[:40]}{'...' if len(self._query)>40 else ''}')"
        )