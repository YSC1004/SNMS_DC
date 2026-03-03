# -*- coding: utf-8 -*-
"""
frOraSession2.h / frOraSession2.C  →  fr_ora_session2.py
Python 3.6.8 호환 버전

변환 설계:
  frOraSession2    → OraSession2  (DbSession 상속)

C++ → Python 주요 변환 포인트:
  FARPROC OCI 함수포인터 21개  → cx_Oracle 직접 호출
  OCIEnv/OCISvcCtx/OCIStmt    → cx_Oracle Connection / Cursor
  STMTSTRUCT2                 → 내부적으로 cx_Oracle cursor 가 대체
  _Describe / _Fetch          → cursor.description + fetchall()
  BindByPos / BindByName      → cx_Oracle execute(query, params)
  frDbDescRecord / DefRecord  → 불필요 (cx_Oracle 자동 처리)
  OCI_NON_BLOCKING            → cx_Oracle 기본 동작
  _InitOciModule()            → import cx_Oracle 로 대체

패키지 설치:
    pip3 install --user cx_Oracle
    # Oracle Instant Client 도 필요:
    # https://www.oracle.com/database/technologies/instant-client.html

변경 이력:
  v1 - 초기 변환
"""

import logging
import datetime
from typing import Optional, List, Dict, TYPE_CHECKING

try:
    import cx_Oracle
except ImportError:
    raise ImportError(
        "cx_Oracle 패키지가 필요합니다.\n"
        "  pip3 install --user cx_Oracle\n"
        "  Oracle Instant Client 설치도 필요합니다."
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

_ORACLE_DATE_FMT = 'YYYY/MM/DD HH24:MI:SS'   # C++ ORACLE_DATE_FORMAT
_MAX_BUF_SIZE    = 2048                        # C++ MAX_BUF_SIZE


# ─────────────────────────────────────────────────────────────────────────────
# OraSession2
# ─────────────────────────────────────────────────────────────────────────────
class OraSession2(DbSession):
    """
    Oracle DB 세션 구현 클래스 (frOraSession2 대응).
    cx_Oracle 을 사용하여 C++ OCI FARPROC 함수포인터 테이블을 대체.

    C++ OCIEnv / OCISvcCtx / OCIStmt 핸들 구조:
      m_Envhp  → cx_Oracle 내부 관리
      m_Svchp  → self._conn  (cx_Oracle Connection)
      m_Stmtinfo->stmthp → self._cursor (cx_Oracle Cursor, 재사용)
    """

    def __init__(self, name=''):
        # type: (str) -> None
        super(OraSession2, self).__init__(name)
        self._db_type = DbType.ORACLE_OCI2
        self._conn    = None   # type: Optional[cx_Oracle.Connection]
        self._cursor  = None   # type: Optional[cx_Oracle.Cursor]

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
        Oracle 은 db_ip / db_port 없이 TNS 이름(db_name)으로 접속.
        db_ip/db_port 가 있으면 Easy Connect 문자열로 자동 구성.
        """
        self._connect = False

        try:
            if db_ip and db_port:
                # Easy Connect: host:port/service_name
                dsn = cx_Oracle.makedsn(db_ip, db_port, service_name=db_name)
            else:
                # TNS alias
                dsn = db_name

            self._conn = cx_Oracle.connect(
                user     = user,
                password = passwd,
                dsn      = dsn,
                encoding = 'UTF-8',
            )
            # autocommit=False 가 cx_Oracle 기본값
            self._cursor = self._conn.cursor()
            self._connect = True
            return True

        except cx_Oracle.Error as e:
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
        """C++ Commit() 대응."""
        try:
            self._conn.commit()
            return True
        except cx_Oracle.Error as e:
            self._set_error(e)
            return False

    def rollback(self):
        # type: () -> bool
        """C++ RollBack() 대응."""
        try:
            self._conn.rollback()
            return True
        except cx_Oracle.Error as e:
            self._set_error(e)
            return False

    # ------------------------------------------------------------------ #
    # execute_query  (DML: INSERT / UPDATE / DELETE)
    # ------------------------------------------------------------------ #
    def execute_query(self, query, bind_param=None, auto_commit=True):
        # type: (str, Optional[BindParam], bool) -> bool
        """
        C++ Execute(char* Query, ...) 3종 오버로드 통합.
        BindParamByPos  → 위치 바인드  (:1, :2, ...)
        BindParamByName → 이름 바인드  (:name)
        """
        self._set_exec_row_count(-1)

        try:
            params = self._build_params(bind_param)
            self._cursor.execute(query, params)
            self._set_exec_row_count(self._cursor.rowcount)

            if auto_commit:
                return self.commit()
            return True

        except cx_Oracle.Error as e:
            self._set_error(e, query)
            return False

    # ------------------------------------------------------------------ #
    # execute  (SELECT → DbParam 결과 적재)
    # ------------------------------------------------------------------ #
    def execute(self, param, bind_param=None):
        # type: (DbParam, Optional[BindParam]) -> bool
        """
        C++ Execute(frDbParam*, ...) 3종 오버로드 통합.
        _Describe + _Fetch 를 cx_Oracle cursor.description + fetchall 로 대체.
        """
        query = param.get_query()
        logger.debug('execute query: %s', query)

        try:
            params = self._build_params(bind_param)
            self._cursor.execute(query, params)

            # _Describe 대응: col 수 세팅
            col_cnt = len(self._cursor.description) if self._cursor.description else 0
            if col_cnt == 0:
                return True
            param.set_col(col_cnt)

            # _Fetch 대응: 행 단위로 DbRecord 생성
            for row in self._cursor:
                record = DbRecord(col_cnt)
                for i, val in enumerate(row):
                    record.set_value(i, self._val_to_str(val))
                param.add_record(record)

            param.rewind()
            return True

        except cx_Oracle.Error as e:
            self._set_error(e, query)
            return False

    # ------------------------------------------------------------------ #
    # execute_rs  (커서 스트리밍 — frDbRecordSet 용)
    # ------------------------------------------------------------------ #
    def execute_rs(self, query):
        # type: (str) -> Optional[DbRecordSet]
        """
        C++ ExecuteRs() 대응.
        frDbRecordSet 이 구현되면 연결; 현재는 미구현 반환.
        """
        self._error    = 'not yet impl'
        self._err_code = -1
        return None

    # ------------------------------------------------------------------ #
    # update_long  (LONG / CLOB 컬럼 업데이트)
    # ------------------------------------------------------------------ #
    def update_long(self, table, field, value, where):
        # type: (str, str, str, str) -> bool
        """C++ UpdateLong() 대응. LONG/CLOB 컬럼 업데이트."""
        self._set_exec_row_count(-1)

        if value is None:
            self._error = 'VALUE is NULL'
            return False

        sql = 'UPDATE %s SET %s = :1 WHERE %s' % (table, field, where)
        try:
            self._cursor.execute(sql, [value])
            self._set_exec_row_count(self._cursor.rowcount)
            return True
        except cx_Oracle.Error as e:
            self._set_error(e, sql)
            return False

    # ------------------------------------------------------------------ #
    # 추상 메서드 구현 (내부)
    # ------------------------------------------------------------------ #
    def _fetch_data(self, fetch_info):
        # type: (RsFetchInfo) -> Optional[DbRecord]
        """
        C++ _FetchData() 대응.
        frDbRecordSet 스트리밍 fetch 용 — execute_rs 구현 시 사용.
        현재 execute() 에서 fetchall 로 처리하므로 미사용.
        """
        return None

    def _close_cursor(self, cursor):
        # type: (object) -> None
        """C++ _CloseCursor() / FreeHandles() 대응."""
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
        """
        BindParamByPos  → list  (cx_Oracle 위치 바인드)
        BindParamByName → dict  (cx_Oracle 이름 바인드)
        None            → []
        """
        if bind_param is None:
            return []

        if isinstance(bind_param, BindParamByPos):
            return self._build_pos_params(bind_param)

        if isinstance(bind_param, BindParamByName):
            return self._build_name_params(bind_param)

        return []

    def _build_pos_params(self, bind):
        # type: (BindParamByPos) -> list
        """C++ BindByPos() 대응. BindParamByPos → cx_Oracle 위치 파라미터 리스트."""
        params = []
        for bd in bind:
            params.append(self._bd_to_value(bd))
        return params

    def _build_name_params(self, bind):
        # type: (BindParamByName) -> dict
        """C++ BindByName() 대응. BindParamByName → cx_Oracle 이름 파라미터 dict."""
        params = {}
        for bd in bind:
            params[bd.bind_name] = self._bd_to_value(bd)
        return params

    def _bd_to_value(self, bd):
        # type: (object) -> object
        """
        QueryBindData 하나를 cx_Oracle 에 전달할 Python 값으로 변환.
        BIND_DATE: frDate → datetime.datetime
        """
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
        """
        cx_Oracle fetch 결과값 → str 변환.
        C++ _FetchData 의 FLOAT/INT/LONG/STRING 분기 대응.
        cx_Oracle 은 타입을 자동 변환하므로 str() 로 통일.
        """
        if val is None:
            return ''
        if isinstance(val, float):
            # C++ : 정수면 %d, 소수면 %f
            i = int(val)
            return str(i) if float(i) == val else str(val)
        return str(val)

    def _set_error(self, exc, query=None):
        # type: (cx_Oracle.Error, Optional[str]) -> None
        """C++ _Error() 대응. OCIErrorGet 결과를 _error / _err_code 에 세팅."""
        err_obj, = exc.args
        self._err_code = err_obj.code if hasattr(err_obj, 'code') else -1
        msg = '%d %s' % (self._err_code, err_obj.message.rstrip())
        if query:
            msg += ' [%s]' % query
        self._error = msg
        logger.error('OraSession2 error: %s', self._error)