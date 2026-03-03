# -*- coding: utf-8 -*-
"""
ProcCallParam.h / ProcCallParam.C  →  proc_call_param.py
Python 3.6.8 호환 버전

변환 설계:
  PROC_PARAM_TYPE enum   → ProcParamType (IntEnum)
  BindData               → BindData
  ProcCallParam          → ProcCallParam (list 상속)

C++ → Python 주요 변환:
  vector<BindData*>  상속  → list 상속
  frIntVector        → List[int]
  new/delete char[]  → str 자동 관리
  memset/strcpy      → 문자열 직접 대입
  eDB_TYPE           → DbType enum
"""

import logging
from enum import IntEnum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from Class.SqlType.fr_db_base_type import DbType

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# ProcParamType  (C++ PROC_PARAM_TYPE enum 대응)
# ─────────────────────────────────────────────────────────────────────────────
class ProcParamType(IntEnum):
    """C++ PROC_PARAM_TYPE 대응."""
    IN    = 0   # ORA_PARAM_IN
    OUT   = 1   # ORA_PARAM_OUT
    INOUT = 2   # ORA_PARAM_INOUT


# ─────────────────────────────────────────────────────────────────────────────
# BindData
# ─────────────────────────────────────────────────────────────────────────────
class BindData(object):
    """
    C++ BindData 대응.
    프로시저 파라미터 하나의 바인드 정보를 담는다.
    """

    class BindType(IntEnum):
        """C++ BindData::BIND_TYPE 대응."""
        BIND_STR = 0
        BIND_INT = 1
        BIND_FLT = 2

    # 클래스 레벨 상수 (C++ 스타일 접근 호환)
    BIND_STR = BindType.BIND_STR
    BIND_INT = BindType.BIND_INT
    BIND_FLT = BindType.BIND_FLT

    def __init__(self):
        self.proc_param_type = ProcParamType.IN              # type: ProcParamType
        self.bind_name       = str('')                       # type: str
        self.bind_type       = BindData.BindType(0)          # type: BindData.BindType

        self.str_data        = str('')                       
        self.int_data        = int(0)                        
        self.number_data     = float(0.0)                    

        self.bind_size       = int(0)                        
        self.str_len         = int(0)                        

    # ------------------------------------------------------------------ #
    # C++ BindStr / BindInt / BindDouble 대응
    # ------------------------------------------------------------------ #
    def bind_str(self, proc_param_type, bind_name, bind_value='', bind_size=1024):
        # type: (ProcParamType, str, str, int) -> None
        """C++ BindStr() 대응."""
        self.bind_type       = BindData.BIND_STR
        self.proc_param_type = proc_param_type
        self.bind_name       = bind_name

        # IN / INOUT 은 값 복사, OUT 은 빈 버퍼
        if proc_param_type in (ProcParamType.IN, ProcParamType.INOUT):
            # C++ : bind_size 가 value 길이보다 작으면 늘림
            self.bind_size = max(bind_size, len(bind_value) + 1)
            self.str_data  = bind_value
        else:
            self.bind_size = bind_size
            self.str_data  = ''

        self.str_len = len(self.str_data)

    def bind_int(self, proc_param_type, bind_name, bind_value=0):
        # type: (ProcParamType, str, int) -> None
        """C++ BindInt() 대응."""
        self.bind_type       = BindData.BIND_INT
        self.proc_param_type = proc_param_type
        self.bind_name       = bind_name
        self.int_data        = bind_value

    def bind_double(self, proc_param_type, bind_name, bind_value=0.0):
        # type: (ProcParamType, str, float) -> None
        """C++ BindDouble() 대응."""
        self.bind_type       = BindData.BIND_FLT
        self.proc_param_type = proc_param_type
        self.bind_name       = bind_name
        self.number_data     = bind_value

    def __repr__(self):
        type_name = {
            BindData.BIND_STR: 'BIND_STR',
            BindData.BIND_INT: 'BIND_INT',
            BindData.BIND_FLT: 'BIND_FLT',
        }.get(self.bind_type, 'UNKNOWN')

        param_name = {
            ProcParamType.IN:    'IN',
            ProcParamType.OUT:   'OUT',
            ProcParamType.INOUT: 'INOUT',
        }.get(self.proc_param_type, 'UNKNOWN')

        if self.bind_type == BindData.BIND_STR:
            val = self.str_data if self.str_data else 'NULL'
        elif self.bind_type == BindData.BIND_INT:
            val = str(self.int_data)
        else:
            val = '%.1f' % self.number_data

        return 'BindData(name=%s, param=%s, type=%s, val=%s)' % (
            self.bind_name, param_name, type_name, val)


# ─────────────────────────────────────────────────────────────────────────────
# ProcCallParam
# ─────────────────────────────────────────────────────────────────────────────
class ProcCallParam(list):
    """
    C++ ProcCallParam (vector<BindData*> 상속) 대응.
    list[BindData] 를 상속하여 동일한 인터페이스 제공.
    """

    def __init__(self, procedure_name):
        # type: (str) -> None
        super(ProcCallParam, self).__init__()
        self.procedure_name  = procedure_name   
        self.err_msg         = ''               
        self.db_type         = None             
        self.res_pos_vector  = []               

    def __del__(self):
        # C++ 소멸자에서 BindData* 를 delete — Python GC 가 자동 처리
        del self[:]

    # ------------------------------------------------------------------ #
    # 파라미터 추가 (C++ AddParam* 대응)
    # ------------------------------------------------------------------ #
    def add_variable(self, proc_param_type, name, value=''):
        # type: (ProcParamType, str, str) -> bool
        """C++ AddVariable() 대응 (AddParamStr 래퍼)."""
        return self.add_param_str(proc_param_type, name, value)

    def add_param_str(self, proc_param_type, name, value='', bind_size=1024):
        # type: (ProcParamType, str, str, int) -> bool
        """C++ AddParamStr() 대응."""
        data = BindData()
        data.bind_str(proc_param_type, name, value, bind_size)
        self.append(data)

        if proc_param_type in (ProcParamType.OUT, ProcParamType.INOUT):
            self.res_pos_vector.append(len(self) - 1)
        return True

    def add_param_int(self, proc_param_type, name, value=0):
        # type: (ProcParamType, str, int) -> bool
        """C++ AddParamInt() 대응."""
        data = BindData()
        data.bind_int(proc_param_type, name, value)
        self.append(data)

        if proc_param_type in (ProcParamType.OUT, ProcParamType.INOUT):
            self.res_pos_vector.append(len(self) - 1)
        return True

    def add_param_double(self, proc_param_type, name, value=0.0):
        # type: (ProcParamType, str, float) -> bool
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
    def get_value(self, name):
        # type: (str) -> str
        """C++ GetValue(string Name) 대응. 이름으로 OUT 값 조회."""
        for bd in self:
            if bd.bind_name == name:
                return bd.str_data
        return ''

    def get_err_msg(self):
        # type: () -> str
        """C++ GetErrMsg() 대응."""
        return self.err_msg

    # ------------------------------------------------------------------ #
    # 쿼리 생성
    # ------------------------------------------------------------------ #
    def make_query(self, db_type):
        # type: (DbType) -> str
        """
        C++ MakeQuery(eDB_TYPE) 대응.
        Oracle: BEGIN proc(:p1, :p2); END;
        MySQL : CALL proc(?, ?)
        """
        from Class.SqlType.fr_db_base_type import DbType as DT

        self.db_type = db_type

        if db_type == DT.ORACLE_OCI2:
            params = ', '.join(':%s' % bd.bind_name for bd in self)
            return 'BEGIN %s(%s); END;' % (self.procedure_name, params)

        elif db_type == DT.MYSQL:
            params = ', '.join('?' for _ in self)
            return 'CALL %s(%s)' % (self.procedure_name, params)

        else:
            logger.error('make_query: unknown db_type=%s', db_type)
            return ''

    # ------------------------------------------------------------------ #
    # 디버그 출력
    # ------------------------------------------------------------------ #
    def print_info(self):
        # type: () -> None
        """C++ Print() 대응."""
        print('\n------- Procedure call [%s] ---------' % self.procedure_name)
        for bd in self:
            print(repr(bd))
        print('-------------------------------------')