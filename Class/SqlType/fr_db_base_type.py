# -*- coding: utf-8 -*-
"""
frDbBaseType.h  →  fr_db_base_type.py
Python 3.11

변환 설계:
  eDB_TYPE            → DbType       (IntEnum)
  eDB_CHARACTER_SET   → DbCharSet    (IntEnum)
  eQUERY_DATA_TYPE    → QueryDataType  (IntEnum)
  eQUERY_JOIN_POSITION→ QueryJoinPosition (IntEnum)
  frDbDescRecord      → DbDescRecord
  frDbDescRecordList  → DbDescRecordList (list 상속)
  frDbDefRecord       → DbDefRecord
  frDbDefRecordList   → DbDefRecordList  (list 상속)
  RsFetchInfo         → RsFetchInfo
  QueryResult         → QueryResult
  QueryBindData       → QueryBindData
  BindParamByPos      → BindParamByPos   (list 상속)
  BindParamByName     → BindParamByName  (list 상속)
  FR_DB_INFO_T        → DbInfo          (dataclass)
  frOCIDate/Time      → 내부 참조용 (cx_Oracle datetime 으로 대체)
"""

import logging
import datetime
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from Class.SqlType.fr_db_param import DbParam

logger = logging.getLogger(__name__)

DB_MAX_ITEM_BUF_SIZE = 2048

# ── DB 타입 문자열 상수 ────────────────────────────────────────────────────────
DB_ORACLE_OCI_STR = "ORACLE"
DB_MYSQL_STR      = "MYSQL"


# ─────────────────────────────────────────────────────────────────────────────
# Enum 정의
# ─────────────────────────────────────────────────────────────────────────────
class DbType(IntEnum):
    """C++ eDB_TYPE 대응."""
    ORACLE_OCI2  = 0
    MYSQL        = 1
    MSSQL_ODBC   = 2
    ORACLE_ODBC  = 3
    ASCA_DB_GW   = 4
    ORACLE_OCI_OLD = 5
    UNKNOWN      = 99


class DbCharSet(IntEnum):
    """C++ eDB_CHARACTER_SET 대응."""
    NOTE = 0
    UTF8 = 1


class QueryDataType(IntEnum):
    """C++ eQUERY_DATA_TYPE 대응."""
    DATE_TYPE = 0   # eDATE_TYPE
    SYSDATE   = 1   # eSYSDATE


class QueryJoinPosition(IntEnum):
    """C++ eQUERY_JOIN_POSITION 대응."""
    LEFT_JOIN  = 0  # eLEFT_JOIN
    RIGHT_JOIN = 1  # eRIGHT_JOIN


# ─────────────────────────────────────────────────────────────────────────────
# Oracle OCI 날짜 구조체 (cx_Oracle datetime 으로 대체 가능하나 호환용 유지)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class FrOCITime:
    """C++ frOCITime 대응."""
    hour:   int = 0
    minute: int = 0
    second: int = 0


@dataclass
class FrOCIDate:
    """C++ frOCIDate 대응."""
    year:  int = 0
    month: int = 1
    day:   int = 1
    time:  FrOCITime = field(default_factory=FrOCITime)

    def to_datetime(self) -> datetime.datetime:
        return datetime.datetime(
            self.year, self.month, self.day,
            self.time.hour, self.time.minute, self.time.second,
        )


@dataclass
class FrMySQLDate:
    """C++ frMySQLDate 대응."""
    year:        int = 0
    month:       int = 0
    day:         int = 0
    hour:        int = 0
    minute:      int = 0
    second:      int = 0
    second_part: int = 0
    neg:         bool = False

    def to_datetime(self) -> datetime.datetime:
        return datetime.datetime(
            self.year, self.month, self.day,
            self.hour, self.minute, self.second,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Oracle Describe / Define 레코드 (OraSession2 내부 전용)
# ─────────────────────────────────────────────────────────────────────────────
class DbDescRecord:
    """
    C++ frDbDescRecord 대응.
    cx_Oracle 에서는 cursor.description 으로 대체되므로
    OraSession2 내부에서만 참조.
    """
    __slots__ = ('db_size', 'db_type', 'buf', 'buf_len',
                 'dsize', 'precision', 'scale', 'null_ok')

    def __init__(self) -> None:
        self.db_size:  int   = 0
        self.db_type:  int   = 0
        self.buf:      bytes = b'\x00' * DB_MAX_ITEM_BUF_SIZE
        self.buf_len:  int   = 0
        self.dsize:    int   = 0
        self.precision:int   = 0
        self.scale:    int   = 0
        self.null_ok:  int   = 0


class DbDescRecordList(list):
    """C++ frDbDescRecordList 대응."""

    def clear_all(self) -> None:
        """C++ Clear() 대응."""
        self.clear()


class DbDefRecord:
    """
    C++ frDbDefRecord 대응.
    cx_Oracle 에서는 cursor fetch 결과가 Python 객체로 반환되므로
    OraSession2 내부에서만 참조.
    """
    __slots__ = ('buf', 'long_buf', 'flt_buf', 'int_buf',
                 'indp', 'col_ret_len', 'col_ret_code')

    def __init__(self) -> None:
        self.buf:          bytearray = bytearray(DB_MAX_ITEM_BUF_SIZE)
        self.long_buf:     bytearray | None = None
        self.flt_buf:      float = 0.0
        self.int_buf:      int   = 0
        self.indp:         int   = 0    # < 0 이면 NULL
        self.col_ret_len:  int   = 0
        self.col_ret_code: int   = 0


class DbDefRecordList(list):
    """C++ frDbDefRecordList 대응."""

    def clear_all(self) -> None:
        """C++ Clear() 대응."""
        self.clear()


# ─────────────────────────────────────────────────────────────────────────────
# RsFetchInfo  (OraSession2 내부 전용)
# ─────────────────────────────────────────────────────────────────────────────
class RsFetchInfo:
    """
    C++ RsFetchInfo 대응.
    frDbRecordSet 스트리밍 fetch 시 커서·컬럼 정보를 묶어 전달.
    """
    __slots__ = ('cursor', 'col_cnt', 'desc_list', 'def_list')

    def __init__(self,
                 cursor:    object,
                 col_cnt:   int,
                 desc_list: DbDescRecordList,
                 def_list:  DbDefRecordList) -> None:
        self.cursor    = cursor
        self.col_cnt   = col_cnt
        self.desc_list = desc_list
        self.def_list  = def_list


# ─────────────────────────────────────────────────────────────────────────────
# QueryResult
# ─────────────────────────────────────────────────────────────────────────────
class QueryResult:
    """
    C++ QueryResult 대응.
    sql_query() 실행 결과를 담는 컨테이너.

    buf 구조: buf[row][col] → str  (C++ char*** m_Buf)
    """

    def __init__(self) -> None:
        self.init()

    def init(self) -> None:
        """C++ Init() 대응."""
        self.buf:          list[list[str]] | None = None  # C++ char*** m_Buf
        self.error_string: str  = ""
        self.error_code:   int  = 0
        self.row_cnt:      int  = 0
        self.col_cnt:      int  = 0
        self.result:       int  = 0
        self.param:        "DbParam | None" = None        # C++ frDbParam* m_Param

    def free(self) -> None:
        """C++ Free() 대응. param 해제 후 초기화."""
        if self.param is not None:
            self.param.clear()
            self.param = None
        self.buf = None

    def print_info(self) -> None:
        """C++ Print() 대응."""
        print(f"QueryResult: result={self.result}, "
              f"rows={self.row_cnt}, cols={self.col_cnt}")
        if self.buf:
            for r, row in enumerate(self.buf):
                print(f"  [{r}] {row}")
        if self.error_string:
            print(f"  Error: {self.error_string} (code={self.error_code})")


# ─────────────────────────────────────────────────────────────────────────────
# QueryBindData
# ─────────────────────────────────────────────────────────────────────────────
class QueryBindData:
    """
    C++ QueryBindData 대응.
    BindParamByPos / BindParamByName 의 원소.
    """

    class BindType(IntEnum):
        BIND_STR  = 0
        BIND_INT  = 1
        BIND_FLT  = 2
        BIND_DATE = 3

    # 클래스 레벨 상수 (C++ QueryBindData::BIND_STR 접근 호환)
    BIND_STR  = BindType.BIND_STR
    BIND_INT  = BindType.BIND_INT
    BIND_FLT  = BindType.BIND_FLT
    BIND_DATE = BindType.BIND_DATE

    def __init__(self) -> None:
        self.int_data:    int      = 0
        self.str_data:    str      = ""
        self.number_data: float    = 0.0
        self.date:        datetime.datetime = datetime.datetime.now()
        self.oci_date:    FrOCIDate = FrOCIDate()
        self.db_date_ptr: bytes | None = None   # MySQL MYSQL_TIME 포인터 대체

        self.bind_name:   str      = ""
        self.bind_type:   QueryBindData.BindType = QueryBindData.BIND_STR
        self.str_len:     int      = 0          # MySQL 전용


# ─────────────────────────────────────────────────────────────────────────────
# BindParamByPos / BindParamByName
# ─────────────────────────────────────────────────────────────────────────────
class BindParamByPos(list):
    """
    C++ BindParamByPos (vector<QueryBindData*>) 대응.
    위치 기반 바인드 파라미터 리스트.
    """

    def clear_all(self) -> None:
        """C++ Clear() 대응."""
        self.clear()

    # ── AddVariable 오버로드 통합 ─────────────────────────────────────────── #
    def add_str(self, value: str) -> None:
        """C++ AddVariable(char*) 대응."""
        bd = QueryBindData()
        bd.bind_type = QueryBindData.BIND_STR
        bd.str_data  = value
        bd.str_len   = len(value)
        self.append(bd)

    def add_int(self, value: int) -> None:
        """C++ AddVariable(int) 대응."""
        bd = QueryBindData()
        bd.bind_type = QueryBindData.BIND_INT
        bd.int_data  = value
        self.append(bd)

    def add_float(self, value: float) -> None:
        """C++ AddVariable(double) 대응."""
        bd = QueryBindData()
        bd.bind_type    = QueryBindData.BIND_FLT
        bd.number_data  = value
        self.append(bd)

    def add_date(self, value: datetime.datetime) -> None:
        """C++ AddVariable(frTime) 대응."""
        bd = QueryBindData()
        bd.bind_type = QueryBindData.BIND_DATE
        bd.date      = value
        self.append(bd)

    def add_variable(self, value: str | int | float | datetime.datetime) -> None:
        """타입 자동 감지 래퍼."""
        if isinstance(value, str):
            self.add_str(value)
        elif isinstance(value, int):
            self.add_int(value)
        elif isinstance(value, float):
            self.add_float(value)
        elif isinstance(value, datetime.datetime):
            self.add_date(value)
        else:
            raise TypeError(f"Unsupported bind type: {type(value)}")


class BindParamByName(list):
    """
    C++ BindParamByName (vector<QueryBindData*>) 대응.
    이름 기반 바인드 파라미터 리스트 (Oracle 전용).
    """

    def clear_all(self) -> None:
        self.clear()

    def _add(self, bind_name: str, bd: QueryBindData) -> None:
        bd.bind_name = bind_name
        self.append(bd)

    def add_str(self, bind_name: str, value: str) -> None:
        """C++ AddVariable(char* BindName, char* Value) 대응."""
        bd = QueryBindData()
        bd.bind_type = QueryBindData.BIND_STR
        bd.str_data  = value
        bd.str_len   = len(value)
        self._add(bind_name, bd)

    def add_int(self, bind_name: str, value: int) -> None:
        """C++ AddVariable(char* BindName, int Value) 대응."""
        bd = QueryBindData()
        bd.bind_type = QueryBindData.BIND_INT
        bd.int_data  = value
        self._add(bind_name, bd)

    def add_float(self, bind_name: str, value: float) -> None:
        """C++ AddVariable(char* BindName, double Value) 대응."""
        bd = QueryBindData()
        bd.bind_type   = QueryBindData.BIND_FLT
        bd.number_data = value
        self._add(bind_name, bd)

    def add_date(self, bind_name: str, value: datetime.datetime) -> None:
        """C++ AddVariable(char* BindName, frTime Date) 대응."""
        bd = QueryBindData()
        bd.bind_type = QueryBindData.BIND_DATE
        bd.date      = value
        self._add(bind_name, bd)

    def add_variable(self, bind_name: str,
                     value: str | int | float | datetime.datetime) -> None:
        """타입 자동 감지 래퍼."""
        if isinstance(value, str):
            self.add_str(bind_name, value)
        elif isinstance(value, int):
            self.add_int(bind_name, value)
        elif isinstance(value, float):
            self.add_float(bind_name, value)
        elif isinstance(value, datetime.datetime):
            self.add_date(bind_name, value)
        else:
            raise TypeError(f"Unsupported bind type: {type(value)}")


# ─────────────────────────────────────────────────────────────────────────────
# DbInfo  (C++ FR_DB_INFO_T struct 대응)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class DbInfo:
    """C++ FR_DB_INFO_T 대응. DB 접속 정보 구조체."""
    db_type:       DbType = DbType.UNKNOWN
    user_id:       str    = ""
    user_pw:       str    = ""
    db_name:       str    = ""
    db_ip:         str    = ""
    db_port:       int    = 0
    db_charset:    str    = ""
    reserved:      str    = ""