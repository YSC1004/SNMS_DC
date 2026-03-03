# -*- coding: utf-8 -*-
"""
frMySQLSession.h / frMySQLSession.C  →  fr_mysql_session.py
Python 3.6.8 호환 버전

패키지 설치:
    pip3 install --user PyMySQL
"""

import logging
import datetime
from typing import Optional, Union, List, TYPE_CHECKING

import pymysql
import pymysql.cursors

from Class.Sql.fr_db_session import DbSession, BindParam
from Class.SqlType.fr_db_base_type import DbType
from Class.SqlType.fr_db_param import (
    DbParam, DbRecord,
    BindParamByPos, BindParamByName, QueryBindData,
)

if TYPE_CHECKING:
    from Class.Sql.fr_db_result_set import DbRecordSet, RsFetchInfo
    from Class.SqlType.fr_db_param   import ProcCallParam, BindData

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 7   # C++ SetMySQLOption: MYSQL_OPT_CONNECT_TIMEOUT


class MySQLSession(DbSession):
    """
    MySQL DB 세션 구현 클래스 (frMySQLSession 대응).
    PyMySQL 을 사용하여 C++ FARPROC 함수포인터 테이블을 대체.
    """

    def __init__(self, name=''):
        # type: (str) -> None
        super(MySQLSession, self).__init__(name)
        self._db_type = DbType.MYSQL
        self._conn    = None   # type: Optional[pymysql.connections.Connection]

    def __del__(self):
        if self._connect:
            self.disconnect()

    # ------------------------------------------------------------------ #
    # connect / disconnect
    # ------------------------------------------------------------------ #
    def connect(self, user, passwd, db_name, db_ip='', db_port=0):
        # type: (str, str, str, str, int) -> bool
        """C++ Connect() 대응."""
        if self._conn:
            self.disconnect()

        self._connect = False

        if not db_ip or db_port == 0:
            self._error = 'need MySQL server IpAddress or Port'
            return False

        try:
            self._conn = pymysql.connect(
                host             = db_ip,
                port             = db_port,
                user             = user,
                password         = passwd,
                database         = db_name,
                autocommit       = False,
                connect_timeout  = _CONNECT_TIMEOUT,
                charset          = 'utf8',
                cursorclass      = pymysql.cursors.Cursor,
            )
            self._connect = True
            return True
        except pymysql.Error as e:
            self._set_error(e)
            return False

    def disconnect(self):
        # type: () -> None
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
    def commit(self):
        # type: () -> bool
        try:
            self._conn.commit()
            return True
        except pymysql.Error as e:
            self._set_error(e)
            return False

    def rollback(self):
        # type: () -> bool
        try:
            self._conn.rollback()
            return True
        except pymysql.Error as e:
            self._set_error(e)
            return False

    # ------------------------------------------------------------------ #
    # execute_query  (DML)
    # ------------------------------------------------------------------ #
    def execute_query(self, query, bind_param=None, auto_commit=True):
        # type: (str, Optional[BindParam], bool) -> bool
        """C++ Execute(char* Query, ...) 3종 오버로드 통합."""
        self._set_exec_row_count(-1)

        if isinstance(bind_param, BindParamByName):
            self._error = "MySQL Doesn't support BindParamByName"
            return False

        try:
            cur = self._conn.cursor()

            if isinstance(bind_param, BindParamByPos):
                params = self._build_pos_params(bind_param)
                cur.execute(query, params)
            else:
                cur.execute(query)

            self._set_exec_row_count(cur.rowcount)
            cur.close()

            if auto_commit:
                return self.commit()
            return True

        except pymysql.Error as e:
            self._set_error(e, query)
            return False

    # ------------------------------------------------------------------ #
    # execute  (SELECT → DbParam 결과 적재)
    # ------------------------------------------------------------------ #
    def execute(self, param, bind_param=None):
        # type: (DbParam, Optional[BindParam]) -> bool
        """C++ Execute(frDbParam*, ...) 3종 오버로드 통합."""
        if isinstance(bind_param, BindParamByName):
            self._error = "MySQL Doesn't support BindParamByName"
            return False

        query = param.get_query()
        logger.debug('execute query: %s', query)

        try:
            cur = self._conn.cursor()

            if isinstance(bind_param, BindParamByPos):
                params = self._build_pos_params(bind_param)
                cur.execute(query, params)
            else:
                cur.execute(query)

            col_cnt = len(cur.description) if cur.description else 0
            if col_cnt == 0:
                cur.close()
                return True

            param.set_col(col_cnt)

            rows = cur.fetchall()
            for row in rows:
                record = DbRecord(col_cnt)
                for i, val in enumerate(row):
                    record.set_value(i, '' if val is None else str(val))
                param.add_record(record)

            cur.close()
            param.rewind()
            return True

        except pymysql.Error as e:
            self._set_error(e, query)
            return False

    # ------------------------------------------------------------------ #
    # execute_rs  (미구현)
    # ------------------------------------------------------------------ #
    def execute_rs(self, query):
        # type: (str) -> None
        """C++ ExecuteRs() — 미구현."""
        self._error    = 'not yet impl'
        self._err_code = -1
        return None

    # ------------------------------------------------------------------ #
    # update_long
    # ------------------------------------------------------------------ #
    def update_long(self, table, field, value, where):
        # type: (str, str, str, str) -> bool
        """C++ UpdateLong() 대응. BLOB/MEDIUMBLOB 컬럼 업데이트."""
        self._set_exec_row_count(-1)

        if value is None:
            self._error = 'VALUE is NULL'
            return False

        sql = 'UPDATE %s SET %s = %%s WHERE %s' % (table, field, where)
        try:
            cur = self._conn.cursor()
            cur.execute(sql, (value,))
            self._set_exec_row_count(cur.rowcount)
            cur.close()
            return True
        except pymysql.Error as e:
            self._set_error(e, sql)
            return False

    # ------------------------------------------------------------------ #
    # execute_procedure
    # ------------------------------------------------------------------ #
    def execute_procedure(self, call_value, auto_commit=False):
        # type: (ProcCallParam, bool) -> bool
        """
        C++ ExecuteProcedure() 대응.
        PyMySQL callproc() 사용.
        OUT / INOUT 파라미터는 @_procname_N 변수로 회수.
        """
        from Class.SqlType.fr_db_param import BindData

        in_params    = []   # type: List
        out_positions = []  # type: List[int]

        for i, bd in enumerate(call_value):
            if bd.proc_param_type in ('OUT', 'INOUT'):
                out_positions.append(i)

            if bd.bind_type == BindData.BIND_STR:
                in_params.append(bd.str_data)
            elif bd.bind_type == BindData.BIND_INT:
                in_params.append(bd.int_data)
            elif bd.bind_type == BindData.BIND_FLT:
                in_params.append(bd.number_data)
            else:
                self._error = 'Unknown bind data type'
                call_value.err_msg = self._error
                return False

        try:
            cur = self._conn.cursor()
            result_args = cur.callproc(call_value.procedure_name, in_params)

            # OUT / INOUT 값 회수
            for pos in out_positions:
                bd  = call_value[pos]
                val = result_args[pos] if result_args else None
                bd.str_data = '' if val is None else str(val)

            # 추가 결과셋 소비
            while cur.nextset():
                pass

            cur.close()

        except pymysql.Error as e:
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
    def set_db_character_set(self, charset_name):
        # type: (str) -> bool
        """C++ SetDBCharacterSet() 대응."""
        try:
            self._conn.set_charset(charset_name)
            return True
        except pymysql.Error as e:
            self._set_error(e)
            return False

    # ------------------------------------------------------------------ #
    # 추상 메서드 구현
    # ------------------------------------------------------------------ #
    def _fetch_data(self, fetch_info):
        # type: (RsFetchInfo) -> None
        return None

    def _close_cursor(self, cursor):
        # type: (object) -> None
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #
    def _build_pos_params(self, bind):
        # type: (BindParamByPos) -> list
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
                    datetime.datetime(
                        d.get_year(), d.get_month(),  d.get_day(),
                        d.get_hour(), d.get_minute(), d.get_second(),
                    )
                )
            else:
                self._error = 'Unknown bind data type'
                raise ValueError(self._error)
        return params

    def _set_error(self, exc, query=None):
        # type: (pymysql.Error, Optional[str]) -> None
        """C++ _Error() / _ErrorStmt() 통합."""
        self._err_code = exc.args[0] if exc.args else -1
        msg = '%d %s' % (self._err_code, exc.args[1] if len(exc.args) > 1 else '')
        msg = msg.rstrip()
        if query:
            msg += ' [%s]' % query
        self._error = msg
        logger.error('MySQLSession error: %s', self._error)