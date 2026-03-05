# -*- coding: utf-8 -*-
"""
ProcCallParam.h / ProcCallParam.C  →  proc_call_param.py
Python 3.11

변환 설계:
  PROC_PARAM_TYPE enum → ProcParamType (IntEnum)
  BindData             → BindData
  ProcCallParam        → ProcCallParam (list 상속)

C++ → Python 주요 변환:
  vector<BindData*> 상속 → list 상속
  frIntVector            → list[int]
  new/delete char[]      → str 자동 관리
  memset/strcpy          → 문자열 직접 대입
  eDB_TYPE               → DbType (IntEnum)
"""

import logging
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Class.SqlType.fr_db_base_type import DbType

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# ProcParamType  (C++ PROC_PARAM_TYPE 대응)
# ─────────────────────────────────────────────────────────────────────────────
class ProcParamType(IntEnum):
    IN    = 0   # ORA_PARAM_IN
    OUT   = 1   # ORA_PARAM_OUT
    INOUT = 2   # ORA_PARAM_INOUT


# ─────────────────────────────────────────────────────────────────────────────
# BindData
# ─────────────────────────────────────────────────────────────────────────────
class BindData:
    """
    C++ BindData 대응.
    프로시저 파라미터 하나의 바인드 정보를 담는다.
    """

    class BindType(IntEnum):
        BIND_STR = 0
        BIND_INT = 1
        BIND_FLT = 2

    # 클래스 레벨 상수 (C++ BindData::BIND_STR 접근 호환)
    BIND_STR = BindType.BIND_STR
    BIND_INT = BindType.BIND_INT
    BIND_FLT = BindType.BIND_FLT

    def __init__(self) -> None:
        self.proc_param_type: ProcParamType     = ProcParamType.IN
        self.bind_name:       str               = ""
        self.bind_type:       BindData.BindType = BindData.BindType.BIND_STR
        self.str_data:        str               = ""
        self.int_data:        int               = 0
        self.number_data:     float             = 0.0
        self.bind_size:       int               = 0
        self.str_len:         int               = 0

    # ------------------------------------------------------------------ #
    # bind_str / bind_int / bind_double  (C++ BindStr/Int/Double 대응)
    # ------------------------------------------------------------------ #
    def bind_str(self, proc_param_type: ProcParamType,
                 bind_name: str, bind_value: str = "", bind_size: int = 1024) -> None:
        """C++ BindStr() 대응."""
        self.bind_type       = BindData.BIND_STR
        self.proc_param_type = proc_param_type
        self.bind_name       = bind_name

        if proc_param_type in (ProcParamType.IN, ProcParamType.INOUT):
            self.bind_size = max(bind_size, len(bind_value) + 1)
            self.str_data  = bind_value
        else:                           # OUT: 빈 버퍼만 확보
            self.bind_size = bind_size
            self.str_data  = ""

        self.str_len = len(self.str_data)

    def bind_int(self, proc_param_type: ProcParamType,
                 bind_name: str, bind_value: int = 0) -> None:
        """C++ BindInt() 대응."""
        self.bind_type       = BindData.BIND_INT
        self.proc_param_type = proc_param_type
        self.bind_name       = bind_name
        self.int_data        = bind_value

    def bind_double(self, proc_param_type: ProcParamType,
                    bind_name: str, bind_value: float = 0.0) -> None:
        """C++ BindDouble() 대응."""
        self.bind_type       = BindData.BIND_FLT
        self.proc_param_type = proc_param_type
        self.bind_name       = bind_name
        self.number_data     = bind_value

    # ------------------------------------------------------------------ #
    # __repr__
    # ------------------------------------------------------------------ #
    def __repr__(self) -> str:
        type_map = {
            BindData.BIND_STR: "BIND_STR",
            BindData.BIND_INT: "BIND_INT",
            BindData.BIND_FLT: "BIND_FLT",
        }
        param_map = {
            ProcParamType.IN:    "IN",
            ProcParamType.OUT:   "OUT",
            ProcParamType.INOUT: "INOUT",
        }
        val: str
        if self.bind_type == BindData.BIND_STR:
            val = self.str_data or "NULL"
        elif self.bind_type == BindData.BIND_INT:
            val = str(self.int_data)
        else:
            val = f"{self.number_data:.1f}"

        return (f"BindData(name={self.bind_name}, "
                f"param={param_map.get(self.proc_param_type, 'UNKNOWN')}, "
                f"type={type_map.get(self.bind_type, 'UNKNOWN')}, "
                f"val={val})")


# ─────────────────────────────────────────────────────────────────────────────
# ProcCallParam
# ─────────────────────────────────────────────────────────────────────────────
class ProcCallParam(list):
    """
    C++ ProcCallParam (vector<BindData*> 상속) 대응.
    list[BindData] 상속으로 동일한 인터페이스 제공.
    """

    def __init__(self, procedure_name: str) -> None:
        super().__init__()
        self.procedure_name: str        = procedure_name
        self.err_msg:        str        = ""
        self.db_type:        "DbType | None" = None
        self.res_pos_vector: list[int]  = []   # MySQL OUT/INOUT 위치 인덱스

    # ------------------------------------------------------------------ #
    # 파라미터 추가
    # ------------------------------------------------------------------ #
    def add_variable(self, proc_param_type: ProcParamType,
                     name: str, value: str = "") -> bool:
        """C++ AddVariable() 대응 (add_param_str 래퍼)."""
        return self.add_param_str(proc_param_type, name, value)

    def add_param_str(self, proc_param_type: ProcParamType,
                      name: str, value: str = "", bind_size: int = 1024) -> bool:
        """C++ AddParamStr() 대응."""
        data = BindData()
        data.bind_str(proc_param_type, name, value, bind_size)
        self.append(data)
        if proc_param_type in (ProcParamType.OUT, ProcParamType.INOUT):
            self.res_pos_vector.append(len(self) - 1)
        return True

    def add_param_int(self, proc_param_type: ProcParamType,
                      name: str, value: int = 0) -> bool:
        """C++ AddParamInt() 대응."""
        data = BindData()
        data.bind_int(proc_param_type, name, value)
        self.append(data)
        if proc_param_type in (ProcParamType.OUT, ProcParamType.INOUT):
            self.res_pos_vector.append(len(self) - 1)
        return True

    def add_param_double(self, proc_param_type: ProcParamType,
                         name: str, value: float = 0.0) -> bool:
        """C++ AddParamDouble() 대응."""
        data = BindData()
        data.bind_double(proc_param_type, name, value)
        self.append(data)
        if proc_param_type in (ProcParamType.OUT, ProcParamType.INOUT):
            self.res_pos_vector.append(len(self) - 1)
        return True

    # ------------------------------------------------------------------ #
    # 값 조회
    # ------------------------------------------------------------------ #
    def get_value(self, name: str) -> str:
        """C++ GetValue(string Name) 대응. 이름으로 OUT/INOUT 결과값 조회."""
        for bd in self:
            if bd.bind_name == name:
                return bd.str_data
        return ""

    def get_err_msg(self) -> str:
        """C++ GetErrMsg() 대응."""
        return self.err_msg

    # ------------------------------------------------------------------ #
    # 쿼리 생성
    # ------------------------------------------------------------------ #
    def make_query(self, db_type: "DbType") -> str:
        """
        C++ MakeQuery(eDB_TYPE) 대응.
          Oracle : BEGIN proc(:name1, :name2); END;
          MySQL  : CALL proc(?, ?)
        """
        from Class.SqlType.fr_db_base_type import DbType as DT

        self.db_type = db_type

        if db_type == DT.ORACLE_OCI2:
            params = ", ".join(f":{bd.bind_name}" for bd in self)
            return f"BEGIN {self.procedure_name}({params}); END;"

        if db_type == DT.MYSQL:
            params = ", ".join("?" for _ in self)
            return f"CALL {self.procedure_name}({params})"

        logger.error("make_query: unknown db_type=%s", db_type)
        return ""

    # ------------------------------------------------------------------ #
    # 디버그 출력
    # ------------------------------------------------------------------ #
    def print_info(self) -> None:
        """C++ Print() 대응."""
        print(f"\n------- Procedure call [{self.procedure_name}] ---------")
        for bd in self:
            print(f"  {bd!r}")
        print("-------------------------------------")