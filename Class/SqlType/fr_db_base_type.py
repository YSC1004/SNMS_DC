"""
frDbBaseType.h / frDbBaseType.C  →  fr_db_base_type.py

변환 매핑:
  C++ typedef (sb1~ub4)           → Python int (크기 제한 없음, 주석으로 범위 표기)
  eDB_TYPE                        → DbType(IntEnum)
  eDB_CHARACTER_SET               → DbCharSet(IntEnum)
  eQUERY_DATA_TYPE                → QueryDataType(IntEnum)
  eQUERY_JOIN_POSITION            → QueryJoinPosition(IntEnum)
  QueryBindData::BIND_TYPE        → BindType(IntEnum)
  frDbDescRecord                  → DbDescRecord (dataclass)
  frDbDescRecordList              → DbDescRecordList (list 래퍼)
  frDbDefRecord                   → DbDefRecord (dataclass)
  frDbDefRecordList               → DbDefRecordList (list 래퍼)
  RsFetchInfo                     → RsFetchInfo (dataclass)
  QueryResult                     → QueryResult
  QueryBindData                   → QueryBindData (dataclass)
  BindParamByPos                  → BindParamByPos (list 래퍼)
  BindParamByName                 → BindParamByName (list 래퍼)
  FR_DB_INFO_T (struct)           → DbInfo (dataclass)
  frOCIDate / frOCITime           → OciDate / OciTime (dataclass)
  frMySQLDate                     → MySQLDate (dataclass)
  char***  m_Buf                  → list[list[str | None]]
  DB_MAX_ITEM_BUF_SIZE = 2048     → 상수로 유지
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional

from Class.Util.fr_time import FrTime

logger = logging.getLogger(__name__)

# ── 상수 ─────────────────────────────────────────────────────────────────────
DB_MAX_ITEM_BUF_SIZE = 2048
NEW_INSTANCE         = 0
ALREADY_INSTANCE     = 1

# ── DB 타입 상수 문자열 ───────────────────────────────────────────────────────
DB_ORACLE_OCI_STR = "ORACLE"
DB_MYSQL_STR      = "MYSQL"


# ══════════════════════════════════════════════════════════════════════════════
# Enum 정의
# ══════════════════════════════════════════════════════════════════════════════

class DbType(IntEnum):
    """eDB_TYPE 대응."""
    ORACLE_OCI2   = 0
    MYSQL         = 1
    MSSQL_ODBC    = 2
    ORACLE_ODBC   = 3
    ASCA_DB_GW    = 4
    ORACLE_OCI_OLD= 5
    UNKNOWN       = 99

    @classmethod
    def from_str(cls, s: str) -> "DbType":
        s = s.upper()
        if s == DB_ORACLE_OCI_STR:
            return cls.ORACLE_OCI2
        if s == DB_MYSQL_STR:
            return cls.MYSQL
        return cls.UNKNOWN


class DbCharSet(IntEnum):
    """eDB_CHARACTER_SET 대응."""
    NONE = 0
    UTF8 = 1


class QueryDataType(IntEnum):
    """eQUERY_DATA_TYPE 대응."""
    DATE_TYPE = 0
    SYSDATE   = 1


class QueryJoinPosition(IntEnum):
    """eQUERY_JOIN_POSITION 대응."""
    LEFT_JOIN  = 0
    RIGHT_JOIN = 1


class BindType(IntEnum):
    """QueryBindData::BIND_TYPE 대응."""
    BIND_STR  = 0
    BIND_INT  = 1
    BIND_FLT  = 2
    BIND_DATE = 3


# ══════════════════════════════════════════════════════════════════════════════
# OCI / MySQL 날짜 구조체
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class OciTime:
    """frOCITime 대응."""
    hour:   int = 0   # 0 ~ 23
    minute: int = 0   # 0 ~ 59
    second: int = 0   # 0 ~ 59


@dataclass
class OciDate:
    """frOCIDate 대응."""
    year:     int     = 0
    month:    int     = 1
    day:      int     = 1
    datetime: OciTime = field(default_factory=OciTime)


@dataclass
class MySQLDate:
    """frMySQLDate 대응."""
    year:        int  = 0
    month:       int  = 0
    day:         int  = 0
    hour:        int  = 0
    minute:      int  = 0
    second:      int  = 0
    second_part: int  = 0
    neg:         bool = False
    time_type:   int  = 0


# ══════════════════════════════════════════════════════════════════════════════
# frDbDescRecord / frDbDescRecordList
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DbDescRecord:
    """
    frDbDescRecord 대응.
    DB 컬럼 메타 정보(타입, 크기, 정밀도 등).
    """
    db_size:   int   = 0
    db_type:   int   = 0
    buf:       bytes = field(default_factory=lambda: bytes(DB_MAX_ITEM_BUF_SIZE))
    buf_len:   int   = 0
    dsize:     int   = 0
    precision: int   = 0
    scale:     int   = 0
    null_ok:   int   = 0


class DbDescRecordList(list):
    """
    frDbDescRecordList 대응.
    list[DbDescRecord] 래퍼. clear_all() 로 명시적 초기화.
    """
    def clear_all(self) -> None:
        """C++ Clear() 대응 (GC 자동 처리)."""
        self.clear()


# ══════════════════════════════════════════════════════════════════════════════
# frDbDefRecord / frDbDefRecordList
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DbDefRecord:
    """
    frDbDefRecord 대응.
    DB fetch 결과 버퍼.
    """
    buf:          bytearray = field(
                      default_factory=lambda: bytearray(DB_MAX_ITEM_BUF_SIZE)
                  )
    long_buf:     Optional[bytearray] = None   # m_LongBuf (동적 할당 대응)
    flt_buf:      float                = 0.0
    int_buf:      int                  = 0
    indp:         int                  = 0     # sb2 m_Indp (NULL 지시자)
    col_ret_len:  int                  = 0
    col_ret_code: int                  = 0


class DbDefRecordList(list):
    """
    frDbDefRecordList 대응.
    list[DbDefRecord] 래퍼.
    """
    def clear_all(self) -> None:
        """C++ Clear() 대응."""
        self.clear()


# ══════════════════════════════════════════════════════════════════════════════
# RsFetchInfo
# ══════════════════════════════════════════════════════════════════════════════

class RsFetchInfo:
    """
    frRsFetchInfo 대응.
    커서 + 컬럼 수 + 메타/결과 리스트 묶음.
    """
    def __init__(
        self,
        cursor:    Any,
        col_cnt:   int,
        desc_list: DbDescRecordList,
        def_list:  DbDefRecordList,
    ):
        self.cursor    = cursor
        self.col_cnt   = col_cnt
        self.desc_list = desc_list
        self.def_list  = def_list


# ══════════════════════════════════════════════════════════════════════════════
# QueryResult
# ══════════════════════════════════════════════════════════════════════════════

class QueryResult:
    """
    frQueryResult 대응.
    DB 쿼리 결과를 담는 컨테이너.

    C++ char*** m_Buf → list[list[str | None]]
    (row 우선, None = SQL NULL 값)
    """

    def __init__(self):
        self.buf:          list[list[Optional[str]]] = []
        self.error_string: str  = ""
        self.error_code:   int  = -1
        self.row_cnt:      int  = 0
        self.col_cnt:      int  = 0
        self.result:       int  = 0
        self.param:        Any  = None

    def init(self) -> None:
        """C++ Init() 대응. 모든 필드 초기화."""
        self.buf          = []
        self.error_string = ""
        self.error_code   = -1
        self.row_cnt      = 0
        self.col_cnt      = 0
        self.result       = 0
        self.param        = None

    def free(self) -> None:
        """C++ Free() 대응. param 해제."""
        self.param = None

    def print(self) -> None:
        """C++ Print() 대응. 결과를 stdout 에 출력."""
        for row_idx, row in enumerate(self.buf):
            row_str = "".join(
                f"[{col if col is not None else ''}]"
                for col in row
            )
            print(f"(ROW:{row_idx + 1}){row_str}")

    def get(self, row: int, col: int) -> Optional[str]:
        """buf[row][col] 안전 접근 (Python 추가)."""
        try:
            return self.buf[row][col]
        except IndexError:
            return None

    def __repr__(self) -> str:
        return (
            f"QueryResult(rows={self.row_cnt}, cols={self.col_cnt}, "
            f"result={self.result}, error={self.error_code})"
        )


# ══════════════════════════════════════════════════════════════════════════════
# QueryBindData
# ══════════════════════════════════════════════════════════════════════════════

class QueryBindData:
    """
    frQueryBindData 대응.
    SQL 바인드 변수 단일 항목.
    """

    def __init__(self):
        self.bind_type:   BindType        = BindType.BIND_STR
        self.int_data:    int             = 0
        self.str_data:    str             = ""
        self.number_data: float           = 0.0
        self.date:        FrTime          = FrTime()
        self.oci_date:    OciDate         = OciDate()
        self.bind_name:   str             = ""
        self.bind_name2:  str             = ""   # ":bindname" (Oracle OCI 용)
        # Oracle7 OCI 날짜 인코딩 (7바이트 배열)
        self.ora7_time:   bytearray       = bytearray(7)

    def _set_ora7_time(self) -> None:
        """
        frTime → Oracle7 7바이트 날짜 인코딩.
        C++ 원본 AddVariable(frTime) 내 로직 그대로 재현.
        """
        d = self.date
        self.ora7_time[0] = 120
        self.ora7_time[1] = 100 + (d.get_year() - 2000)
        self.ora7_time[2] = d.get_month()
        self.ora7_time[3] = d.get_day()
        self.ora7_time[4] = d.get_hour()   + 1
        self.ora7_time[5] = d.get_minute() + 1
        self.ora7_time[6] = d.get_second() + 1


# ══════════════════════════════════════════════════════════════════════════════
# BindParamByPos  ←  위치 기반 바인드 파라미터
# ══════════════════════════════════════════════════════════════════════════════

class BindParamByPos(list):
    """
    BindParamByPos 대응.
    위치(순서) 기반 SQL 바인드 파라미터 리스트.

    사용:
        bp = BindParamByPos()
        bp.add("hello")
        bp.add(42)
        bp.add(3.14)
        bp.add(FrTime())
    """

    def clear_all(self) -> None:
        """C++ Clear() 대응."""
        self.clear()

    def add(self, value) -> None:
        """
        타입에 따라 BIND_STR / INT / FLT / DATE 자동 선택.
        C++ AddVariable() 오버로드 통합.
        """
        bd = QueryBindData()
        if isinstance(value, FrTime):
            bd.bind_type = BindType.BIND_DATE
            bd.date      = value
            bd._set_ora7_time()
        elif isinstance(value, bool):
            bd.bind_type = BindType.BIND_INT
            bd.int_data  = int(value)
        elif isinstance(value, int):
            bd.bind_type = BindType.BIND_INT
            bd.int_data  = value
        elif isinstance(value, float):
            bd.bind_type = BindType.BIND_FLT
            bd.number_data = value
        else:
            bd.bind_type = BindType.BIND_STR
            bd.str_data  = str(value) if value is not None else ""
        self.append(bd)

    # C++ 원본 호환 메서드명
    def add_variable(self, value) -> None:
        self.add(value)


# ══════════════════════════════════════════════════════════════════════════════
# BindParamByName  ←  이름 기반 바인드 파라미터
# ══════════════════════════════════════════════════════════════════════════════

class BindParamByName(list):
    """
    BindParamByName 대응.
    이름(`:name`) 기반 SQL 바인드 파라미터 리스트.

    사용:
        bp = BindParamByName()
        bp.add("user_id", "ncadmin")
        bp.add("port",    8080)
        bp.add("ratio",   1.5)
        bp.add("reg_dt",  FrTime())
    """

    def clear_all(self) -> None:
        """C++ Clear() 대응."""
        self.clear()

    def add(self, bind_name: str, value) -> None:
        """
        C++ AddVariable(BindName, Value) 오버로드 통합.
        bind_name2 = ":" + bind_name (Oracle OCI 규칙).
        """
        bd              = QueryBindData()
        bd.bind_name    = bind_name or ""
        bd.bind_name2   = ":" + bd.bind_name

        if isinstance(value, FrTime):
            bd.bind_type = BindType.BIND_DATE
            bd.date      = value
            bd._set_ora7_time()
        elif isinstance(value, bool):
            bd.bind_type = BindType.BIND_INT
            bd.int_data  = int(value)
        elif isinstance(value, int):
            bd.bind_type = BindType.BIND_INT
            bd.int_data  = value
        elif isinstance(value, float):
            bd.bind_type = BindType.BIND_FLT
            bd.number_data = value
        else:
            bd.bind_type = BindType.BIND_STR
            bd.str_data  = str(value) if value is not None else ""

        self.append(bd)

    # C++ 원본 호환 메서드명
    def add_variable(self, bind_name: str, value) -> None:
        self.add(bind_name, value)


# ══════════════════════════════════════════════════════════════════════════════
# FR_DB_INFO_T  →  DbInfo
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DbInfo:
    """
    FR_DB_INFO_T struct 대응.
    DB 접속 정보.
    """
    db_type:       DbType    = DbType.UNKNOWN
    user_id:       str       = ""
    user_pw:       str       = ""
    db_name:       str       = ""
    db_ip:         str       = ""
    db_port:       int       = 0
    db_charset:    str       = ""
    reserved:      str       = ""