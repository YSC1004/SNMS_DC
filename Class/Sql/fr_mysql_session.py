# -*- coding: utf-8 -*-
"""
frMySQLSession.h / frMySQLSession.C  →  fr_mysql_session.py
Python 3.11

패키지 설치:
    pip install PyMySQL
"""

import logging
import datetime
from typing import TYPE_CHECKING

try:
    import pymysql
    import pymysql.cursors
    _PYMYSQL_AVAILABLE = True
    _PyMySQLError = pymysql.Error          # 타입 표현식·except 절 공용 별칭
except ImportError:
    pymysql = None                         # type: ignore[assignment]
    _PYMYSQL_AVAILABLE = False
    _PyMySQLError = Exception              # fallback (실제로는 도달 안 함)

from Class.Sql.fr_db_session import DbSession, BindParam
from Class.SqlType.fr_db_base_type import (
    DbType, QueryBindData,
    BindParamByPos, BindParamByName,
)
from Class.SqlType.fr_db_param import DbParam, DbRecord
from Class.Sql.proc_call_param import BindData, ProcParamType

if TYPE_CHECKING:
    from Class.Sql.fr_db_result_set import RsFetchInfo
    from Class.Sql.proc_call_param  import ProcCallParam

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 7   # C++ SetMySQLOption: MYSQL_OPT_CONNECT_TIMEOUT


class MySQLSession(DbSession):
    """
    MySQL DB 세션 구현 클래스 (frMySQLSession 대응).
    PyMySQL 을 사용하여 C++ FARPROC 함수포인터 테이블을 대체.
    """

    def __init__(self, name: str = "") -> None:
        super().__init__(name)
        self._db_type = DbType.MYSQL
        self._conn = None

    def __del__(self) -> None:
        if self._connect:
            self.disconnect()

    # ------------------------------------------------------------------ #
    # connect / disconnect
    # ------------------------------------------------------------------ #
    def connect(self, user: str, passwd: str, db_name: str,
                db_ip: str = "", db_port: int = 0) -> bool:
        """C++ Connect() 대응."""
        if not _PYMYSQL_AVAILABLE:
            self._error = "PyMySQL 패키지가 설치되어 있지 않습니다."
            logger.error(self._error)
            return False

        if self._conn:
            self.disconnect()

        self._connect = False

        if not db_ip or db_port == 0:
            self._error = "need MySQL server IpAddress or Port"
            return False

        try:
            self._conn = pymysql.connect(
                host            = db_ip,
                port            = db_port,
                user            = user,
                password        = passwd,
                database        = db_name,
                autocommit      = False,
                connect_timeout = _CONNECT_TIMEOUT,
                charset         = "utf8",
                cursorclass     = pymysql.cursors.Cursor,
            )
            self._connect = True
            return True
        except _PyMySQLError as e:
            self._set_error(e)
            return False

    def disconnect(self) -> None:
        """C++ Disconnect() 대응."""
        self._connect = False
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    # ------------------------------------------------------------------ #
    # commit / rollback
    # ------------------------------------------------------------------ #
    def commit(self) -> bool:
        try:
            self._conn.commit()
            return True
        except _PyMySQLError as e:
            self._set_error(e)
            return False

    def rollback(self) -> bool:
        try:
            self._conn.rollback()
            return True
        except _PyMySQLError as e:
            self._set_error(e)
            return False

    # ------------------------------------------------------------------ #
    # execute_query  (DML: INSERT / UPDATE / DELETE)
    # ------------------------------------------------------------------ #
    def execute_query(self, query: str,
                      bind_param: BindParam | None = None,
                      auto_commit: bool = True) -> bool:
        """C++ Execute(char* Query, ...) 3종 오버로드 통합."""
        self._set_exec_row_count(-1)

        if isinstance(bind_param, BindParamByName):
            self._error = "MySQL doesn't support BindParamByName"
            return False

        try:
            cur = self._conn.cursor()
            if isinstance(bind_param, BindParamByPos):
                cur.execute(query, self._build_pos_params(bind_param))
            else:
                cur.execute(query)

            self._set_exec_row_count(cur.rowcount)
            cur.close()

            return self.commit() if auto_commit else True

        except _PyMySQLError as e:
            self._set_error(e, query)
            return False

    # ------------------------------------------------------------------ #
    # execute  (SELECT → DbParam 결과 적재)
    # ------------------------------------------------------------------ #
    def execute(self, param: DbParam,
                bind_param: BindParam | None = None) -> bool:
        """C++ Execute(frDbParam*, ...) 3종 오버로드 통합."""
        if isinstance(bind_param, BindParamByName):
            self._error = "MySQL doesn't support BindParamByName"
            return False

        query = param.get_query()
        logger.debug("execute query: %s", query)

        try:
            cur = self._conn.cursor()
            if isinstance(bind_param, BindParamByPos):
                cur.execute(query, self._build_pos_params(bind_param))
            else:
                cur.execute(query)

            col_cnt = len(cur.description) if cur.description else 0
            if col_cnt == 0:
                cur.close()
                return True

            param.set_col(col_cnt)
            for row in cur.fetchall():
                record = DbRecord(col_cnt)
                for i, val in enumerate(row):
                    record.set_value(i, "" if val is None else str(val))
                param.add_record(record)

            cur.close()
            param.rewind()
            return True

        except _PyMySQLError as e:
            self._set_error(e, query)
            return False

    # ------------------------------------------------------------------ #
    # execute_rs  (미구현 — C++ 원본도 미구현)
    # ------------------------------------------------------------------ #
    def execute_rs(self, query: str) -> None:
        """C++ ExecuteRs() — 미구현."""
        self._error    = "not yet impl"
        self._err_code = -1
        return None

    # ------------------------------------------------------------------ #
    # update_long  (BLOB / MEDIUMBLOB 컬럼 업데이트)
    # ------------------------------------------------------------------ #
    def update_long(self, table: str, field: str,
                    value: str, where: str) -> bool:
        """C++ UpdateLong() 대응."""
        self._set_exec_row_count(-1)

        if value is None:
            self._error = "VALUE is NULL"
            return False

        sql = f"UPDATE {table} SET {field} = %s WHERE {where}"
        try:
            cur = self._conn.cursor()
            cur.execute(sql, (value,))
            self._set_exec_row_count(cur.rowcount)
            cur.close()
            return True
        except _PyMySQLError as e:
            self._set_error(e, sql)
            return False

    # ------------------------------------------------------------------ #
    # execute_procedure
    # ------------------------------------------------------------------ #
    def execute_procedure(self, call_value: "ProcCallParam",
                          auto_commit: bool = False) -> bool:
        """
        C++ ExecuteProcedure() 대응.
        PyMySQL callproc() 사용.
        OUT / INOUT 파라미터는 result_args 위치로 회수.
        """
        in_params:     list      = []
        out_positions: list[int] = []

        for i, bd in enumerate(call_value):
            if bd.proc_param_type in (ProcParamType.OUT, ProcParamType.INOUT):
                out_positions.append(i)

            if bd.bind_type == BindData.BIND_STR:
                in_params.append(bd.str_data)
            elif bd.bind_type == BindData.BIND_INT:
                in_params.append(bd.int_data)
            elif bd.bind_type == BindData.BIND_FLT:
                in_params.append(bd.number_data)
            else:
                self._error = "Unknown bind data type"
                call_value.err_msg = self._error
                return False

        try:
            cur = self._conn.cursor()
            result_args = cur.callproc(call_value.procedure_name, in_params)

            for pos in out_positions:
                val = result_args[pos] if result_args else None
                call_value[pos].str_data = "" if val is None else str(val)

            while cur.nextset():
                pass
            cur.close()

        except _PyMySQLError as e:
            self._set_error(e, call_value.procedure_name)
            call_value.err_msg = self._error
            return False

        if auto_commit:
            ok = self.commit()
            if not ok:
                call_value.err_msg = self._error
            return ok

        return True

    # ------------------------------------------------------------------ #
    # set_db_character_set
    # ------------------------------------------------------------------ #
    def set_db_character_set(self, charset_name: str) -> bool:
        """C++ SetDBCharacterSet() 대응."""
        try:
            self._conn.set_charset(charset_name)
            return True
        except _PyMySQLError as e:
            self._set_error(e)
            return False

    # ------------------------------------------------------------------ #
    # 추상 메서드 구현
    # ------------------------------------------------------------------ #
    def _fetch_data(self, fetch_info: "RsFetchInfo") -> None:
        """C++ _FetchData() — MySQLSession 에서 미사용."""
        return None

    def _close_cursor(self, cursor: object) -> None:
        """C++ _CloseCursor() 대응."""
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #
    def _build_pos_params(self, bind: BindParamByPos) -> list:
        """C++ BindByPos() 대응. BindParamByPos → PyMySQL 파라미터 리스트."""
        params = []
        for bd in bind:
            if bd.bind_type == QueryBindData.BIND_STR:
                params.append(bd.str_data)
            elif bd.bind_type == QueryBindData.BIND_INT:
                params.append(bd.int_data)
            elif bd.bind_type == QueryBindData.BIND_FLT:
                params.append(bd.number_data)
            elif bd.bind_type == QueryBindData.BIND_DATE:
                d = bd.date
                params.append(
                    d if isinstance(d, datetime.datetime) else
                    datetime.datetime(d.get_year(),  d.get_month(),  d.get_day(),
                                      d.get_hour(),  d.get_minute(), d.get_second())
                )
            else:
                self._error = "Unknown bind data type"
                raise ValueError(self._error)
        return params

    def _set_error(self, exc: Exception,
                   query: str | None = None) -> None:
        """C++ _Error() / _ErrorStmt() 통합."""
        self._err_code = exc.args[0] if exc.args else -1
        msg = f"{self._err_code} {exc.args[1] if len(exc.args) > 1 else ''}".rstrip()
        if query:
            msg += f" [{query}]"
        self._error = msg
        logger.error("MySQLSession error: %s", self._error)