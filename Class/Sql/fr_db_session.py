# -*- coding: utf-8 -*-
"""
frDbSession.h / frDbSession.C  →  fr_db_session.py
Python 3.11
"""

import logging
from abc import ABC, abstractmethod
from typing import Union, Optional, TYPE_CHECKING

from Class.SqlType.fr_db_base_type import (
    DbType, QueryDataType, QueryJoinPosition,
    DB_ORACLE_OCI_STR, DB_MYSQL_STR,
)
from Class.SqlType.fr_db_param import (
    DbParam, DbRecord,
    BindParamByPos, BindParamByName, QueryResult,
)

if TYPE_CHECKING:
    from Class.Sql.fr_db_result_set import DbRecordSet, RsFetchInfo
    from Class.SqlType.fr_db_param    import ProcCallParam

logger = logging.getLogger(__name__)

# ── 연결 끊김 에러 코드 ───────────────────────────────────────────────────────
_ORA_DISCON_CODES:   frozenset[int] = frozenset({3114, 3113, 12154, 1017, 1012})
_ORA_DISCON_STRS:    tuple[str, ...] = (
    "ORA-03114", "ORA-03113", "ORA-00000",
    "ORA-12154", "ORA-01017", "ORA-01012",
)
_MYSQL_DISCON_CODES: frozenset[int] = frozenset({2006, 2013, 2003})
_DML_KEYWORDS:       frozenset[str] = frozenset({"INSERT", "UPDATE", "DELETE"})

# ── BindParam 통합 타입 ───────────────────────────────────────────────────────
BindParam = Union[BindParamByPos | BindParamByName]

class DbSession(ABC):
    """
    DB 세션 추상 기반 클래스 (frDbSession 대응).
    MySQL / Oracle 등 구체 구현 클래스가 상속하여 abstract 메서드를 구현.
    """

    def __init__(self, name: str = "") -> None:
        self._name:         str     = name
        self._error:        str     = ""
        self._err_code:     int     = 0
        self._connect:      bool    = False
        self._exec_row_cnt: int     = -1
        self._db_type:      DbType  = DbType.UNKNOWN

    # ------------------------------------------------------------------ #
    # 팩토리
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_instance(db_kind: int = int(DbType.MYSQL),
                     name: str = "") -> Optional["DbSession"]:
        """C++ GetInstance() 대응."""
        try:
            db_type = DbType(db_kind)
        except ValueError:
            logger.error("get_instance: unsupported db_kind=%d", db_kind)
            return None

        session: DbSession | None = None

        if db_type == DbType.MYSQL:
            from Class.Sql.fr_mysql_session import MySQLSession
            session = MySQLSession(name)
        elif db_type == DbType.ORACLE_OCI2:
            from Class.Sql.fr_ora_session2 import OraSession2
            session = OraSession2(name)
        else:
            logger.error("get_instance: unsupported db_type=%s", db_type)
            return None

        if session:
            session._db_type = db_type
        return session

    @staticmethod
    def get_db_type_from_str(db_type_str: str) -> DbType:
        s = db_type_str.strip().upper()
        if s == DB_ORACLE_OCI_STR:
            return DbType.ORACLE_OCI2
        if s == DB_MYSQL_STR:
            return DbType.MYSQL
        logger.error("get_db_type_from_str: unknown type '%s'", db_type_str)
        return DbType.UNKNOWN

    @staticmethod
    def get_db_kind(db_kind_str: str) -> int:
        return int(DbSession.get_db_type_from_str(db_kind_str))

    # ------------------------------------------------------------------ #
    # 타입 / 이름 조회
    # ------------------------------------------------------------------ #
    def get_db_type(self) -> DbType:
        return self._db_type

    def get_db_type_str(self) -> str:
        if self._db_type in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD):
            return DB_ORACLE_OCI_STR
        if self._db_type == DbType.MYSQL:
            return DB_MYSQL_STR
        return "unknown dbtype"

    def get_name(self)          -> str:  return self._name
    def get_error(self)         -> str:  return self._error
    def get_error_code(self)    -> int:  return self._err_code
    def get_exec_row_count(self)-> int:  return self._exec_row_cnt

    def _set_exec_row_count(self, cnt: int) -> None:
        self._exec_row_cnt = cnt

    # ------------------------------------------------------------------ #
    # 추상 메서드
    # ------------------------------------------------------------------ #
    @abstractmethod
    def connect(self, user: str, passwd: str, db_name: str,
                db_ip: str = "", db_port: int = 0) -> bool: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def execute_rs(self, query: str) -> "DbRecordSet": ...

    @abstractmethod
    def execute(self, param: DbParam,
                bind_param: BindParam | None = None) -> bool: ...

    @abstractmethod
    def execute_query(self, query: str,
                      bind_param: BindParam | None = None,
                      auto_commit: bool = True) -> bool: ...

    @abstractmethod
    def commit(self) -> bool: ...

    @abstractmethod
    def rollback(self) -> bool: ...

    @abstractmethod
    def update_long(self, table: str, field: str,
                    value: str, where: str) -> bool: ...

    @abstractmethod
    def _fetch_data(self, fetch_info: "RsFetchInfo") -> DbRecord | None: ...

    @abstractmethod
    def _close_cursor(self, cursor: object) -> None: ...

    # ------------------------------------------------------------------ #
    # sql_query
    # ------------------------------------------------------------------ #
    def sql_query(self, query: str, result: QueryResult,
                  bind_param: BindParam | None = None,
                  addition_text: str = "") -> bool:
        """C++ SqlQuery() 3종 오버로드 통합."""
        keyword = self._extract_keyword(query)
        ok = False

        if keyword in _DML_KEYWORDS:
            self._set_exec_row_count(-1)
            ok = self.execute_query(query, bind_param, auto_commit=False)
            if ok:
                result.result  = 1
                result.row_cnt = self.get_exec_row_count()
            else:
                result.result       = 0
                result.row_cnt      = -1
                result.error_string = self.get_error()
                result.error_code   = self.get_error_code()
        else:
            param = DbParam()
            param.set_query(query)
            result.param = param
            ok = self.execute(param, bind_param)
            if ok:
                result.result  = 1
                result.col_cnt = param.get_col()
                result.row_cnt = param.get_row()
                if result.row_cnt:
                    result.buf = param.get_value()
            else:
                result.result       = 0
                result.error_string = self.get_error()
                result.error_code   = self.get_error_code()
        return ok

    def free(self, result: QueryResult) -> None:
        result.free()

    # ------------------------------------------------------------------ #
    # 프로시저 (기본 미구현)
    # ------------------------------------------------------------------ #
    def execute_procedure(self, call_value: "ProcCallParam",
                          auto_commit: bool = False) -> bool:
        self._error = "Undefined function"
        return False

    # ------------------------------------------------------------------ #
    # 테이블 존재 확인
    # ------------------------------------------------------------------ #
    def is_exist_table(self, table_name: str) -> bool:
        db = self._db_type
        if db in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD, DbType.ORACLE_ODBC):
            query = "SELECT COUNT(*) FROM TAB WHERE TNAME = '%s'" % table_name.upper()
        elif db in (DbType.MSSQL_ODBC, DbType.MYSQL):
            query = ("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                     "WHERE TABLE_NAME = '%s'" % table_name)
        else:
            return False

        result = QueryResult()
        if not self.sql_query(query, result):
            return False
        try:
            count = int(result.buf[0][0] or 0)
            self.free(result)
            return count > 0
        except (IndexError, TypeError, ValueError):
            return False

    # ------------------------------------------------------------------ #
    # 쿼리 조각 생성 헬퍼
    # ------------------------------------------------------------------ #
    def make_insert_query(self, data_type: QueryDataType, data: str) -> str:
        db = self._db_type
        if data_type == QueryDataType.DATE_TYPE:
            if db in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD):
                return f"TO_DATE('{data}', 'YYYY/MM/DD HH24:MI:SS')"
            if db == DbType.MYSQL:
                return f"STR_TO_DATE('{data}', '%Y/%m/%d %H:%i:%s')"
            if db == DbType.MSSQL_ODBC:
                return f"'{data}'"
        elif data_type == QueryDataType.SYSDATE:
            if db in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD):
                return "SYSDATE"
            if db == DbType.MYSQL:
                return "sysdate()"
            if db == DbType.MSSQL_ODBC:
                return "not impl"
        return "undefined dbtype or datatype"

    def make_select_query(self, data_type: QueryDataType, field: str) -> str:
        db = self._db_type
        if data_type == QueryDataType.DATE_TYPE:
            if db in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD):
                return f"TO_CHAR({field}, 'YYYY/MM/DD HH24:MI:SS')"
            if db == DbType.MYSQL:
                return f"DATE_FORMAT({field}, '%Y/%m/%d %H:%i:%s')"
            if db == DbType.MSSQL_ODBC:
                return field
        elif data_type == QueryDataType.SYSDATE:
            if db in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD):
                return "SYSDATE"
            if db == DbType.MYSQL:
                return "sysdate()"
            if db == DbType.MSSQL_ODBC:
                return "not impl"
        return "undefined dbtype or datatype"

    def make_query_outer_join(self, position: QueryJoinPosition,
                              l_field: str, r_field: str) -> str:
        db = self._db_type
        L  = QueryJoinPosition.LEFT_JOIN
        if db in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD):
            return (f"{l_field} (+) = {r_field}" if position == L
                    else f"{l_field} = {r_field} (+)")
        if db == DbType.MSSQL_ODBC:
            return (f"{l_field} =* {r_field}" if position == L
                    else f"{l_field} *= {r_field}")
        if db == DbType.MYSQL:
            return ""  # need impl
        return "undefined dbtype or jointype"

    def make_query_binder(self, bind_name: str) -> str:
        db = self._db_type
        if db in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD):
            return f":{bind_name}"
        if db in (DbType.MYSQL, DbType.MSSQL_ODBC):
            return "?"
        return "undefined dbms type"

    def make_nvl_or_is_null_query(self) -> str:
        db = self._db_type
        if db in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD, DbType.ORACLE_ODBC):
            return "NVL"
        if db == DbType.MSSQL_ODBC:
            return "ISNULL"
        if db == DbType.MYSQL:
            return "ifnull"
        return ""

    def set_db_character_set(self, charset_name: str) -> bool:
        self._error    = "need impl"
        self._err_code = -1
        return True

    # ------------------------------------------------------------------ #
    # 연결 끊김 에러 판별
    # ------------------------------------------------------------------ #
    def is_db_disconnect_err(self, error_code: int | None = None) -> bool:
        code = error_code if error_code is not None else self._err_code
        return DbSession.is_db_disconnect_err_static(self._db_type, code)

    @staticmethod
    def is_db_disconnect_err_static(db_type: DbType, error_code: int) -> bool:
        if db_type in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD):
            return error_code in _ORA_DISCON_CODES
        if db_type == DbType.MYSQL:
            return error_code in _MYSQL_DISCON_CODES
        return False

    @staticmethod
    def is_db_discon_err_by_code(ora_err_code: int) -> bool:
        return ora_err_code in _ORA_DISCON_CODES

    @staticmethod
    def is_db_discon_err_by_msg(ora_err_msg: str) -> bool:
        return any(s in ora_err_msg for s in _ORA_DISCON_STRS)

    # ------------------------------------------------------------------ #
    # Bulk Loader 명령 생성
    # ------------------------------------------------------------------ #
    @staticmethod
    def make_bulk_loader_command(
            db_type: DbType, db_user: str, db_passwd: str, db_name: str,
            table_name: str, ctl_file_path: str, ctl_file_name: str,
            target_path: str, target_filename: str) -> str | None:
        if db_type in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD):
            return (
                f"sqlldr {db_user}/{db_passwd}@{db_name} "
                f"control={ctl_file_path}/{ctl_file_name}.ctl "
                f"data={target_path}/{target_filename} "
                f"log={target_path}/{target_filename}.log "
                f"bad={target_path}/{target_filename}.bad "
                f"errors=9999999999 silent=all"
            )
        if db_type == DbType.MSSQL_ODBC:
            return (
                f"bcp {table_name} in "
                f"{target_path}/{target_filename} -c -t \"|\" "
                f"-U {db_user} -P {db_passwd} -S {db_name} "
                f"-e {target_path}/{target_filename}.bad > "
                f"{target_path}/{target_filename}.log"
            )
        logger.error("make_bulk_loader_command: unknown db_type=%s", db_type)
        return None

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_keyword(query: str) -> str:
        s = query.lstrip()
        return s[:6].upper() if len(s) >= 6 else s.upper()

    @staticmethod
    def string_upper(s: str) -> str:
        return s.lstrip().upper()