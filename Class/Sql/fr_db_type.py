# -*- coding: utf-8 -*-
"""
frDbType.h  →  fr_db_type.py

원본 역할:
  frDbType.h 는 frDbBaseType.h 를 포함하는 래퍼 헤더.
  실제 타입 정의는 모두 frDbBaseType.h 에 있음.

Python 에서는 fr_db_base_type / fr_db_param 의 심볼을
re-export 하는 pass-through 모듈로 구현.

사용법:
    from Class.SqlType.fr_db_type import DbType, QueryResult, DbParam
    from Class.SqlType.fr_db_type import BindParamByPos, BindParamByName
"""

from Class.SqlType.fr_db_base_type import (   # noqa: F401
    # 상수
    DB_MAX_ITEM_BUF_SIZE,
    DB_ORACLE_OCI_STR,
    DB_MYSQL_STR,

    # Enum
    DbType,
    DbCharSet,
    QueryDataType,
    QueryJoinPosition,

    # 날짜 구조체  (변환 시 FrOCI* / FrMySQL* 로 명명)
    FrOCITime,
    FrOCIDate,
    FrMySQLDate,

    # Oracle Describe / Define (OraSession2 내부 전용)
    DbDescRecord,
    DbDescRecordList,
    DbDefRecord,
    DbDefRecordList,

    # Fetch 정보
    RsFetchInfo,

    # 쿼리 결과
    QueryResult,

    # 바인드 파라미터
    QueryBindData,
    BindParamByPos,
    BindParamByName,

    # DB 접속 정보
    DbInfo,
)

from Class.SqlType.fr_db_param import (       # noqa: F401
    DbRecord,
    DbBinder,
    DbParam,
)