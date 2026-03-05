# -*- coding: utf-8 -*-
"""
frOraSession2.h / frOraSession2.C  →  fr_ora_session2.py
Python 3.6.8 호환 버전

변환 설계:
  frOraSession2    → OraSession2  (DbSession 상속)

변경 이력:
  v1 - 초기 변환 (cx_Oracle 기반)
  v2 - cx_Oracle → oracledb (Thin 모드, Oracle Client 설치 불필요)

패키지 설치:
    pip install oracledb
"""

import logging
import datetime
from typing import Optional, List, Dict, TYPE_CHECKING

try:
    import oracledb
except ImportError:
    raise ImportError(
        "oracledb 패키지가 필요합니다.\n"
        "  pip install oracledb\n"
        "  ※ Oracle Client 설치 불필요 (Thin 모드 기본값)"
    )

from Class.Sql.fr_db_session import DbSession, BindParam
from Class.SqlType.fr_db_base_type import DbType
from Class.SqlType.fr_db_param import (
    DbParam, DbRecord,
    BindParamByPos, BindParamByName, QueryBindData,
)

if TYPE_CHECKING:
    from Class.Sql.fr_db_result_set  import DbRecordSet, RsFetchInfo
    from Class.SqlType.fr_db_param   import ProcCallParam, BindData

logger = logging.getLogger(__name__)

_ORACLE_DATE_FMT = 'YYYY/MM/DD HH24:MI:SS'
_MAX_BUF_SIZE    = 2048


# ─────────────────────────────────────────────────────────────────────────────
# OraSession2
# ─────────────────────────────────────────────────────────────────────────────
class OraSession2(DbSession):
    """
    Oracle DB 세션 구현 클래스 (frOraSession2 대응).
    oracledb (Thin 모드) 를 사용 — Oracle Client 설치 불필요.

    cx_Oracle → oracledb 변경 포인트:
      import cx_Oracle              → import oracledb
      cx_Oracle.connect(...)        → oracledb.connect(...)
      cx_Oracle.makedsn(...)        → oracledb.makedsn(...)   # 호환 유지
      cx_Oracle.Error               → oracledb.Error
      encoding='UTF-8' 파라미터    → 제거 (oracledb Thin 모드는 항상 UTF-8)
      err_obj, = exc.args           → str(exc) 로 직접 파싱 (구조 변경)
    """

    def __init__(self, name=''):
        # type: (str) -> None
        super(OraSession2, self).__init__(name)
        self._db_type = DbType.ORACLE_OCI2
        self._conn    = None   # type: Optional[oracledb.Connection]
        self._cursor  = None   # type: Optional[oracledb.Cursor]

    def __del__(self):
        if self._connect:
            self.disconnect()

    # ------------------------------------------------------------------ #
    # connect / disconnect
    # ------------------------------------------------------------------ #
    def connect(self, user, passwd, db_name, db_ip='', db_port=0):
        # type: (str, str, str, str, int) -> bool
        """
        C++ Connect(UserName, Password, DbName) 대응.
        oracledb Thin 모드는 Oracle Client 없이 직접 DB 소켓 접속.

        [cx_Oracle 대비 변경]
          - encoding='UTF-8' 제거 (Thin 모드 항상 UTF-8)
          - makedsn → oracledb.makedsn (API 동일, 라이브러리만 교체)
        """
        self._connect = False

        try:
            if db_ip and db_port:
                # Easy Connect: host:port/service_name
                dsn = oracledb.makedsn(db_ip, db_port, service_name=db_name)
            else:
                # TNS alias 또는 "host:port/service_name" 문자열
                dsn = db_name

            self._conn = oracledb.connect(
                user     = user,
                password = passwd,
                dsn      = dsn,
                # encoding 파라미터 없음 — Thin 모드는 항상 UTF-8
            )
            # autocommit=False 가 기본값 (cx_Oracle 동일)
            self._cursor = self._conn.cursor()
            self._connect = True
            return True

        except oracledb.Error as e:
            self._set_error(e)
            return False

    def disconnect(self):
        # type: () -> None
        """C++ Disconnect() 대응."""
        self._connect = False
        self._close_cursor(self._cursor)
        self._cursor = None
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
        except oracledb.Error as e:
            self._set_error(e)
            return False

    def rollback(self):
        # type: () -> bool
        try:
            self._conn.rollback()
            return True
        except oracledb.Error as e:
            self._set_error(e)
            return False

    # ------------------------------------------------------------------ #
    # execute_query  (DML: INSERT / UPDATE / DELETE)
    # ------------------------------------------------------------------ #
    def execute_query(self, query, bind_param=None, auto_commit=True):
        # type: (str, Optional[BindParam], bool) -> bool
        self._set_exec_row_count(-1)

        try:
            params = self._build_params(bind_param)
            self._cursor.execute(query, params)
            self._set_exec_row_count(self._cursor.rowcount)

            if auto_commit:
                return self.commit()
            return True

        except oracledb.Error as e:
            self._set_error(e, query)
            return False

    # ------------------------------------------------------------------ #
    # execute  (SELECT → DbParam 결과 적재)
    # ------------------------------------------------------------------ #
    def execute(self, param, bind_param=None):
        # type: (DbParam, Optional[BindParam]) -> bool
        query = param.get_query()
        logger.debug('execute query: %s', query)

        try:
            params = self._build_params(bind_param)
            self._cursor.execute(query, params)

            col_cnt = len(self._cursor.description) if self._cursor.description else 0
            if col_cnt == 0:
                return True
            param.set_col(col_cnt)

            for row in self._cursor:
                record = DbRecord(col_cnt)
                for i, val in enumerate(row):
                    record.set_value(i, self._val_to_str(val))
                param.add_record(record)

            param.rewind()
            return True

        except oracledb.Error as e:
            self._set_error(e, query)
            return False

    # ------------------------------------------------------------------ #
    # execute_rs  (커서 스트리밍 — frDbRecordSet 용)
    # ------------------------------------------------------------------ #
    def execute_rs(self, query):
        # type: (str) -> Optional[DbRecordSet]
        self._error    = 'not yet impl'
        self._err_code = -1
        return None

    # ------------------------------------------------------------------ #
    # update_long  (LONG / CLOB 컬럼 업데이트)
    # ------------------------------------------------------------------ #
    def update_long(self, table, field, value, where):
        # type: (str, str, str, str) -> bool
        self._set_exec_row_count(-1)

        if value is None:
            self._error = 'VALUE is NULL'
            return False

        sql = 'UPDATE %s SET %s = :1 WHERE %s' % (table, field, where)
        try:
            self._cursor.execute(sql, [value])
            self._set_exec_row_count(self._cursor.rowcount)
            return True
        except oracledb.Error as e:
            self._set_error(e, sql)
            return False

    # ------------------------------------------------------------------ #
    # 추상 메서드 구현 (내부)
    # ------------------------------------------------------------------ #
    def _fetch_data(self, fetch_info):
        # type: (RsFetchInfo) -> Optional[DbRecord]
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
    def _build_params(self, bind_param):
        # type: (Optional[BindParam]) -> object
        if bind_param is None:
            return []
        if isinstance(bind_param, BindParamByPos):
            return self._build_pos_params(bind_param)
        if isinstance(bind_param, BindParamByName):
            return self._build_name_params(bind_param)
        return []

    def _build_pos_params(self, bind):
        # type: (BindParamByPos) -> list
        return [self._bd_to_value(bd) for bd in bind]

    def _build_name_params(self, bind):
        # type: (BindParamByName) -> dict
        return {bd.bind_name: self._bd_to_value(bd) for bd in bind}

    def _bd_to_value(self, bd):
        # type: (object) -> object
        if bd.bind_type == QueryBindData.BIND_STR:
            return bd.str_data
        elif bd.bind_type == QueryBindData.BIND_INT:
            return bd.int_data
        elif bd.bind_type == QueryBindData.BIND_FLT:
            return bd.number_data
        elif bd.bind_type == QueryBindData.BIND_DATE:
            d = bd.date
            return datetime.datetime(
                d.get_year(), d.get_month(),  d.get_day(),
                d.get_hour(), d.get_minute(), d.get_second(),
            )
        else:
            self._error = 'Unknown bind data type'
            raise ValueError(self._error)

    @staticmethod
    def _val_to_str(val):
        # type: (object) -> str
        if val is None:
            return ''
        if isinstance(val, float):
            i = int(val)
            return str(i) if float(i) == val else str(val)
        return str(val)

    def _set_error(self, exc, query=None):
        # type: (oracledb.Error, Optional[str]) -> None
        """
        [cx_Oracle 대비 변경]
          cx_Oracle : err_obj, = exc.args  →  err_obj.code / err_obj.message
          oracledb  : exc.args[0] 가 문자열일 수도 있어 안전하게 처리
        """
        args = exc.args
        if args and hasattr(args[0], 'code'):
            # thick 모드 또는 일부 버전: _Error 객체
            err_obj = args[0]
            self._err_code = err_obj.code
            msg = '%d %s' % (self._err_code, err_obj.message.rstrip())
        else:
            # thin 모드: 문자열 형태 "ORA-XXXXX: ..."
            self._err_code = -1
            raw = str(exc).rstrip()
            # ORA-NNNNN 코드 파싱 시도
            import re
            m = re.search(r'ORA-(\d+)', raw)
            if m:
                self._err_code = int(m.group(1))
            msg = raw

        if query:
            msg += ' [%s]' % query
        self._error = msg
        logger.error('OraSession2 error: %s', self._error)