"""
frDbSession.h / frDbSession.C  →  fr_db_session.py

변환 설계:
  frDbSession (순수 가상 함수 포함 추상 클래스) → DbSession (ABC)
  GetInstance() 팩토리                          → DbSession.get_instance()
  frDbRecordSet friend                           → _fetch_data / _close_cursor 내부 메서드

순수 가상 함수 → @abstractmethod:
  connect / disconnect / execute_rs
  execute / execute_query (bind 파라미터 Optional 통합)
  commit / rollback / update_long
  _fetch_data / _close_cursor

구현된 메서드 (그대로 변환):
  sql_query (3 오버로드) → sql_query()  (쿼리 타입 자동 감지)
  make_insert_query / make_select_query
  make_query_outer_join / make_query_binder
  make_nvl_or_is_null_query
  is_exist_table / is_db_disconnect_err
  make_bulk_loader_command

변경 이력:
  v1 - 초기 변환
  v2 - is_exist_table MySQL 지원 추가, _extract_keyword 분리,
       make_bulk_loader_command 반환값 Optional[str] 로 변경,
       get_instance 에서 _db_type 올바르게 세팅 (C++ 원본 버그 수정),
       get_db_kind() 추가
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

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
    from Class.Sql.proc_call_param  import ProcCallParam

logger = logging.getLogger(__name__)

# ── 연결 끊김 에러 코드 테이블 ────────────────────────────────────────────────
_ORA_DISCON_CODES:   frozenset[int] = frozenset({3114, 3113, 12154, 1017, 1012})
_ORA_DISCON_STRS:    tuple[str, ...]= ("ORA-03114", "ORA-03113", "ORA-00000",
                                       "ORA-12154", "ORA-01017", "ORA-01012")
_MYSQL_DISCON_CODES: frozenset[int] = frozenset({2006, 2013, 2003})

# ── DML 키워드 ────────────────────────────────────────────────────────────────
_DML_KEYWORDS: frozenset[str] = frozenset({"INSERT", "UPDATE", "DELETE"})


# ─────────────────────────────────────────────────────────────────────────────
# DbSession
# ─────────────────────────────────────────────────────────────────────────────
class DbSession(ABC):
    """
    DB 세션 추상 기반 클래스 (frDbSession 대응).
    MySQL / Oracle 등 구체 구현 클래스가 상속하여 abstract 메서드를 구현.
    """

    # ------------------------------------------------------------------ #
    # 생성
    # ------------------------------------------------------------------ #
    def __init__(self, name: str = "") -> None:
        self._name:         str     = name
        self._error:        str     = ""
        self._err_code:     int     = 0
        self._connect:      bool    = False
        self._exec_row_cnt: int     = -1
        self._db_type:      DbType  = DbType.UNKNOWN

    # ------------------------------------------------------------------ #
    # 팩토리 (GetInstance)
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_instance(
        db_kind: int = int(DbType.MYSQL),
        name:    str = "",
    ) -> Optional["DbSession"]:
        """
        C++ GetInstance(int DbKind, char* Name) 대응.
        db_kind 에 맞는 구체 세션 인스턴스를 반환.

        Note: C++ 원본은 모든 타입에 대해 m_DBType = eDB_MYSQL 로 덮어쓰는
              버그가 있었으나, 여기서는 올바르게 db_type 을 세팅한다.
        """
        try:
            db_type = DbType(db_kind)
        except ValueError:
            logger.error("get_instance: unsupported db_kind=%d", db_kind)
            return None

        session: Optional[DbSession] = None

        if db_type == DbType.MYSQL:
            from Class.Sql.fr_mysql_session import MySQLSession   # 지연 임포트
            session = MySQLSession(name)
        elif db_type == DbType.ORACLE_OCI2:
            from Class.Sql.fr_ora_session2 import OraSession2     # 지연 임포트
            session = OraSession2(name)
        else:
            logger.error("get_instance: unsupported db_type=%s", db_type)
            return None

        session._db_type = db_type
        return session

    # ------------------------------------------------------------------ #
    # DB 타입 조회
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_db_type_from_str(db_type_str: str) -> DbType:
        """C++ GetDbType(string) 대응."""
        s = db_type_str.strip().upper()
        if s == DB_ORACLE_OCI_STR:
            return DbType.ORACLE_OCI2
        if s == DB_MYSQL_STR:
            return DbType.MYSQL
        logger.error("get_db_type_from_str: unknown type '%s'", db_type_str)
        return DbType.UNKNOWN

    @staticmethod
    def get_db_kind(db_kind_str: str) -> int:
        """C++ GetDBKind(string) 대응. 문자열 → DbType 정수값 반환."""
        return int(DbSession.get_db_type_from_str(db_kind_str))

    def get_db_type(self) -> DbType:
        return self._db_type

    def get_db_type_str(self) -> str:
        if self._db_type in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD):
            return DB_ORACLE_OCI_STR
        if self._db_type == DbType.MYSQL:
            return DB_MYSQL_STR
        return "unknown dbtype"

    def get_name(self) -> str:
        return self._name

    def get_error(self) -> str:
        return self._error

    def get_error_code(self) -> int:
        return self._err_code

    def get_exec_row_count(self) -> int:
        return self._exec_row_cnt

    def _set_exec_row_count(self, cnt: int) -> None:
        self._exec_row_cnt = cnt

    # ------------------------------------------------------------------ #
    # 추상 메서드 (순수 가상 함수)
    # ------------------------------------------------------------------ #
    @abstractmethod
    def connect(
        self,
        user:    str,
        passwd:  str,
        db_name: str,
        db_ip:   str = "",
        db_port: int = 0,
    ) -> bool: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def execute_rs(self, query: str) -> "DbRecordSet": ...

    @abstractmethod
    def execute(
        self,
        param:      DbParam,
        bind_param: Optional[BindParamByPos | BindParamByName] = None,
    ) -> bool: ...

    @abstractmethod
    def execute_query(
        self,
        query:       str,
        bind_param:  Optional[BindParamByPos | BindParamByName] = None,
        auto_commit: bool = True,
    ) -> bool: ...

    @abstractmethod
    def commit(self) -> bool: ...

    @abstractmethod
    def rollback(self) -> bool: ...

    @abstractmethod
    def update_long(
        self, table: str, field: str, value: str, where: str,
    ) -> bool: ...

    @abstractmethod
    def _fetch_data(self, fetch_info: "RsFetchInfo") -> Optional[DbRecord]: ...

    @abstractmethod
    def _close_cursor(self, cursor) -> None: ...

    # ------------------------------------------------------------------ #
    # sql_query  (C++ 3개 오버로드 → 1개로 통합)
    # ------------------------------------------------------------------ #
    def sql_query(
        self,
        query:         str,
        result:        QueryResult,
        bind_param:    Optional[BindParamByPos | BindParamByName] = None,
        addition_text: str = "",
    ) -> bool:
        """
        C++ SqlQuery() 3개 오버로드 통합.
        쿼리 앞 6글자로 DML / SELECT 자동 판별.

        INSERT / UPDATE / DELETE → execute_query()
        그 외 (SELECT 등)        → execute()
        """
        keyword = self._extract_keyword(query)
        ok      = False

        if keyword in _DML_KEYWORDS:
            # ── DML ──────────────────────────────────────────────────── #
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
            # ── SELECT 등 ────────────────────────────────────────────── #
            param        = DbParam()
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
        """C++ Free(QueryResult&) 대응."""
        result.free()

    # ------------------------------------------------------------------ #
    # 프로시저 (기본 미구현 — 하위 클래스에서 오버라이드)
    # ------------------------------------------------------------------ #
    def execute_procedure(
        self,
        call_value:  "ProcCallParam",
        auto_commit: bool = False,
    ) -> bool:
        """C++ ExecuteProcedure() 기본 구현."""
        self._error = "Undefined function"
        return False

    # ------------------------------------------------------------------ #
    # 테이블 존재 확인
    # ------------------------------------------------------------------ #
    def is_exist_table(self, table_name: str) -> bool:
        """C++ IsExistTable() 대응. MySQL 지원 추가."""
        db = self._db_type
        if db in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD, DbType.ORACLE_ODBC):
            # Oracle: TAB 뷰 사용
            query = (
                f"SELECT COUNT(*) FROM TAB "
                f"WHERE TNAME = '{table_name.upper()}'"
            )
        elif db in (DbType.MSSQL_ODBC, DbType.MYSQL):
            # MSSQL / MySQL: INFORMATION_SCHEMA 사용
            query = (
                f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                f"WHERE TABLE_NAME = '{table_name}'"
            )
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
    # DB별 쿼리 조각 생성 헬퍼
    # ------------------------------------------------------------------ #
    def make_insert_query(self, data_type: QueryDataType, data: str) -> str:
        """C++ MakeInsertQuery() 대응. DB 타입별 날짜 삽입 표현식 생성."""
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
        """C++ MakeSelectQuery() 대응. DB 타입별 날짜 조회 표현식 생성."""
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

    def make_query_outer_join(
        self,
        position: QueryJoinPosition,
        l_field:  str,
        r_field:  str,
    ) -> str:
        """C++ MakeQueryOuterJoin() 대응."""
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
        """C++ MakeQueryBinder() 대응. DB 타입별 바인드 플레이스홀더 반환."""
        db = self._db_type
        if db in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD):
            return f":{bind_name}"
        if db in (DbType.MYSQL, DbType.MSSQL_ODBC):
            return "?"
        return "undefined dbms type"

    def make_nvl_or_is_null_query(self) -> str:
        """C++ MakeNvlOrIsNullQuery() 대응."""
        db = self._db_type
        if db in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD, DbType.ORACLE_ODBC):
            return "NVL"
        if db == DbType.MSSQL_ODBC:
            return "ISNULL"
        if db == DbType.MYSQL:
            return "ifnull"
        return ""

    def set_db_character_set(self, charset_name: str) -> bool:
        """C++ SetDBCharacterSet() 기본 구현."""
        self._error    = "need impl"
        self._err_code = -1
        return True

    # ------------------------------------------------------------------ #
    # DB 연결 끊김 에러 판별
    # ------------------------------------------------------------------ #
    def is_db_disconnect_err(self, error_code: Optional[int] = None) -> bool:
        """C++ IsDbDisConnectErr() 대응. 인스턴스 DB 타입 기준으로 판별."""
        code = error_code if error_code is not None else self._err_code
        return DbSession.is_db_disconnect_err_static(self._db_type, code)

    @staticmethod
    def is_db_disconnect_err_static(db_type: DbType, error_code: int) -> bool:
        """C++ IsDbDisConnectErr(eDB_TYPE, int) 정적 메서드 대응."""
        if db_type in (DbType.ORACLE_OCI2, DbType.ORACLE_OCI_OLD):
            return error_code in _ORA_DISCON_CODES
        if db_type == DbType.MYSQL:
            return error_code in _MYSQL_DISCON_CODES
        return False

    @staticmethod
    def is_db_discon_err_by_code(ora_err_code: int) -> bool:
        """C++ IsDbDisConErr(int) 대응 (Oracle 전용)."""
        return ora_err_code in _ORA_DISCON_CODES

    @staticmethod
    def is_db_discon_err_by_msg(ora_err_msg: str) -> bool:
        """C++ IsDbDisConErr(const char*) 대응 (Oracle 전용)."""
        return any(s in ora_err_msg for s in _ORA_DISCON_STRS)

    # ------------------------------------------------------------------ #
    # Bulk Loader 명령 생성
    # ------------------------------------------------------------------ #
    @staticmethod
    def make_bulk_loader_command(
        db_type:         DbType,
        db_user:         str,
        db_passwd:       str,
        db_name:         str,
        table_name:      str,
        ctl_file_path:   str,
        ctl_file_name:   str,
        target_path:     str,
        target_filename: str,
    ) -> Optional[str]:
        """
        C++ MakeBulkLoaderCommand() 대응.
        Oracle → sqlldr, MSSQL → bcp 명령 문자열 생성.
        실패 시 None 반환 (C++ 원본: Command="" + return false).
        """
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
        """
        쿼리 앞 공백 제거 후 첫 6글자를 대문자로 반환.
        C++ StringUpper() + erase(6, ...) 로직 대응.
        """
        s = query.lstrip()
        return s[:6].upper() if len(s) >= 6 else s.upper()

    @staticmethod
    def string_upper(s: str) -> str:
        """C++ StringUpper() 대응 (앞 공백 제거 + 대문자 변환)."""
        return s.lstrip().upper()