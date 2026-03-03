"""
frDbType.h  →  fr_db_type.py

원본 역할:
  frDbType.h 는 frDbBaseType.h 를 포함하는 래퍼 헤더로,
  실제 타입 정의는 모두 frDbBaseType.h / frDbBaseType.C 에 있음.

Python 에서는 fr_db_base_type 의 모든 심볼을 re-export 하는
패스-스루(pass-through) 모듈로 구현.

다른 모듈에서 frDbType.h 를 include 하던 코드는
'from Class.SqlType.fr_db_type import *' 또는
'from Class.SqlType.fr_db_type import DbParam, QueryResult, ...' 로 대체.
"""

from Class.SqlType.fr_db_base_type import (   # noqa: F401  (re-export)
    # 상수
    DB_MAX_ITEM_BUF_SIZE,
    NEW_INSTANCE,
    ALREADY_INSTANCE,
    DB_ORACLE_OCI_STR,
    DB_MYSQL_STR,

    # Enum
    DbType,
    DbCharSet,
    QueryDataType,
    QueryJoinPosition,
    BindType,

    # 날짜 구조체
    OciTime,
    OciDate,
    MySQLDate,

    # DB 메타/결과 타입
    DbDescRecord,
    DbDescRecordList,
    DbDefRecord,
    DbDefRecordList,
    RsFetchInfo,
    QueryResult,

    # 바인드 타입
    QueryBindData,
    BindParamByPos,
    BindParamByName,

    # DB 접속 정보
    DbInfo,
)

from Class.SqlType.fr_db_param import (       # noqa: F401  (re-export)
    BinderType,
    DbBinder,
    DbRecord,
    DbParam,
)