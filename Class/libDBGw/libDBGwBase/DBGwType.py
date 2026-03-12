# -*- coding: utf-8 -*-
"""
DBGwType.h  →  DBGwType.py
Python 3.11.10 변환

변환 설계:
  C typedef struct → Python dataclass
  #define 상수    → 모듈 상수

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

from dataclasses import dataclass, field
from Common.CommType import AS_SEGFLAG

# ─────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────
MAX_ERROR_SIZE = 2048
MAX_DATA_SIZE  = 4000

# 메시지 ID
DB_CONN_REQ               = 60001
DB_CONN_RES               = 60002
DB_CLOSE_REQ              = 60003
DB_CLOSE_RES              = 60004
DB_QUERY_REQ              = 60011
DB_QUERY_RES              = 60012
DB_BULK_QUERY_DATA        = 60013
DB_RS_QUERY_DATA          = 60014
DB_QUERY_LONG_UPDATE_REQ  = 60015
DB_QUERY_LONG_UPDATE_RES  = 60016
DB_RS_MOVE_NEXT_REQ       = 60021
DB_RS_CLOSE_REQ           = 60031
DB_COMMIT_REQ             = 60032
DB_COMMIT_RES             = 60033
DB_ROLLBACK_REQ           = 60034
DB_ROLLBACK_RES           = 60035

# 쿼리 타입
QUERY_TYPE_SELECT = 0
QUERY_TYPE_UPDATE = 1
QUERY_TYPE_INSERT = 2

# 쿼리 요청 타입
QUERY_REQ_TYPE_BULK = 0
QUERY_REQ_TYPE_RS   = 1

# 버퍼 크기
DEF_BUF_SIZE = 2_048_000   # 2MB


# ─────────────────────────────────────────────
# dataclass (C typedef struct 대응)
# ─────────────────────────────────────────────

@dataclass
class DbConnReqT:
    """C++ DB_CONN_REQ_T 대응."""
    db_user:   str = ""
    db_passwd: str = ""
    db_name:   str = ""
    user_id:   str = ""
    host_name: str = ""
    host_ip:   str = ""
    proc_pid:  int = 0


@dataclass
class DbConnResT:
    """C++ DB_CONN_RES_T 대응."""
    result:  int = 0    # short int
    error:   str = ""


@dataclass
class DbCloseReqT:
    """C++ DB_CLOSE_REQ_T 대응."""
    req: int = 0


@dataclass
class DbQueryReqT:
    """C++ DB_QUERY_REQ_T 대응."""
    query_id:       int        = 0
    query_type:     int        = QUERY_TYPE_SELECT
    query_req_type: int        = QUERY_REQ_TYPE_BULK
    commit:         int        = 0
    seg_flag:       AS_SEGFLAG = AS_SEGFLAG.NO_SEG
    query:          str        = ""


@dataclass
class DbQueryResT:
    """C++ DB_QUERY_RES_T 대응."""
    query_id:  int = 0
    col_cnt:   int = 0
    row_cnt:   int = 0
    result:    int = 0    # short int
    data_size: int = 0
    error:     str = ""


@dataclass
class DbBulkQueryDataT:
    """C++ DB_BULK_QUERY_DATA_T 대응."""
    query_id: int        = 0
    seg_flag: AS_SEGFLAG = AS_SEGFLAG.NO_SEG
    data:     str        = ""


@dataclass
class DbRsQueryDataT:
    """
    C++ DB_RS_QUERY_DATA_T 대응.
    size == -1: 에러, size == -2: EOR(End Of Recordset)
    """
    query_id: int        = 0
    cur_row:  int        = 0
    seg_flag: AS_SEGFLAG = AS_SEGFLAG.NO_SEG
    size:     int        = 0
    data:     str        = ""


@dataclass
class DbRsMoveNextReqT:
    """C++ DB_RS_MOVE_NEXT_REQ_T 대응."""
    query_id: int = 0
    reserved: int = 0


@dataclass
class DbRsCloseReqT:
    """C++ DB_RS_CLOSE_REQ_T 대응."""
    query_id: int = 0
    reserved: int = 0


@dataclass
class DbCommitResT:
    """C++ DB_COMMIT_RES_T 대응."""
    result: int = 0    # short int
    error:  str = ""


@dataclass
class DbRollbackResT:
    """C++ DB_ROLLBACK_RES_T 대응."""
    result: int = 0    # short int
    error:  str = ""


@dataclass
class DbQueryLongUpdateReqT:
    """C++ DB_QUERY_LONG_UPDATE_REQ_T 대응."""
    table:     str        = ""
    field:     str        = ""
    seg_flag:  AS_SEGFLAG = AS_SEGFLAG.NO_SEG
    data_size: int        = 0
    data:      str        = ""


@dataclass
class DbQueryLongUpdateResT:
    """C++ DB_QUERY_LONG_UPDATE_RES_T 대응."""
    result: int = 0    # short int
    error:  str = ""