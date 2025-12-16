import sys
import os
import pymysql
from pymysql.constants import CLIENT
from Class.Sql.FrDbRecordSet import FrDbRecordSet

# -------------------------------------------------------
# 1. 프로젝트 경로 및 모듈 Import 설정
# -------------------------------------------------------
# 현재 파일 위치: .../Class/Sql/FrMySQLSession.py
# 상위 2단계(.../Class/..)를 참조하기 위해 sys.path 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))

if project_root not in sys.path:
    sys.path.append(project_root)

# [Import] Enum 정의 (위치 변경 반영: Class/Sql/FrBaseType.py)
from Class.Sql.FrBaseType import EDB_TYPE

# [Import] 부모 클래스
from Class.Sql.FrDbSession import FrDbSession

# [Import] 파라미터 클래스 (위치 변경 반영: Class/SqlType/FrDbParam.py)
from Class.Sql.FrDbParam import FrDbParam, FrDbRecord

# [Import] 결과셋 클래스 (순환 참조 방지 처리)
try:
    from Class.Sql.FrDbRecordSet import FrDbRecordSet
except ImportError:
    FrDbRecordSet = None

# -------------------------------------------------------
# 2. FrMySQLSession 클래스 정의
# -------------------------------------------------------
class FrMySQLSession(FrDbSession):
    def __init__(self, name=None):
        """
        C++ 생성자: frMySQLSession(char *Name)
        """
        super().__init__(name) # 부모 클래스(FrDbSession) 초기화
        self.m_DBType = EDB_TYPE.MYSQL
        self.conn = None
        
        # C++의 함수 포인터 초기화(_InitMySQLModule)는 Python 라이브러리 사용으로 불필요

    def __del__(self):
        """
        C++ 소멸자: ~frMySQLSession()
        """
        if self.m_Connect:
            self.disconnect()

    # -------------------------------------------------------
    # 연결 관리 (Connect / Disconnect)
    # -------------------------------------------------------
    def connect(self, user, password, db_name, db_ip='127.0.0.1', db_port=3306, charset='utf8mb4'):
        """
        C++: bool Connect(...)
        """
        # 기존 연결이 있으면 끊음
        if self.conn:
            self.disconnect()

        # 필수 정보 체크
        if not db_ip or not db_port:
            self._error("Need MySQL server IpAddress or Port")
            return False

        try:
            self.conn = pymysql.connect(
                host=db_ip,
                user=user,
                password=password,
                database=db_name,
                port=db_port,
                charset=charset,
                # CLIENT.MULTI_STATEMENTS: 프로시저나 다중 쿼리 지원을 위해 필요
                client_flag=CLIENT.MULTI_STATEMENTS,
                # C++ 코드에서 autocommit을 0으로 셋팅하므로 False 설정
                autocommit=False,
                connect_timeout=10
            )
            self.m_Connect = True
            return True

        except pymysql.MySQLError as e:
            self.m_ErrCode = e.args[0]
            self._error(str(e))
            return False

    def disconnect(self):
        """
        C++: void Disconnect()
        """
        self.m_Connect = False
        if self.conn:
            try:
                self.conn.close()
            except:
                pass
            self.conn = None

    # -------------------------------------------------------
    # 트랜잭션 (Commit / RollBack)
    # -------------------------------------------------------
    def commit(self):
        """
        C++: bool Commit()
        """
        if not self.m_Connect or not self.conn:
            return False
        try:
            self.conn.commit()
            return True
        except pymysql.MySQLError as e:
            self._error(str(e))
            return False

    def rollback(self):
        """
        C++: bool RollBack()
        """
        if not self.m_Connect or not self.conn:
            return False
        try:
            self.conn.rollback()
            return True
        except pymysql.MySQLError as e:
            self._error(str(e))
            return False

    # -------------------------------------------------------
    # 실행 (Execute) - 통합 메서드
    # -------------------------------------------------------
    def execute(self, query_or_param, bind_params=None, auto_commit=True):
        """
        C++의 여러 Execute 오버로딩을 하나로 통합
        1. Execute(char* Query, ...) -> query_or_param이 str
        2. Execute(char* Query, BindParamByPos*, ...) -> bind_params 사용
        3. Execute(frDbParam* Param) -> query_or_param이 FrDbParam 객체
        4. Execute(frDbParam* Param, BindParamByPos*)
        """
        if not self.m_Connect:
            return False

        self.set_exec_row_count(-1)
        
        target_query = ""
        is_fetching = False
        fr_param_obj = None

        # 인자가 FrDbParam 객체인지, 단순 문자열인지 확인
        if isinstance(query_or_param, FrDbParam):
            fr_param_obj = query_or_param
            target_query = fr_param_obj.GetQuery()
            is_fetching = True
        else:
            target_query = query_or_param
            is_fetching = False

        try:
            cursor = self.conn.cursor()
            
            # 쿼리 실행
            # bind_params가 있으면 pymysql이 내부적으로 Prepared Statement 처리 (%s 사용)
            cursor.execute(target_query, bind_params)
            
            # 영향받은 행 개수 설정
            affected_rows = cursor.rowcount
            self.set_exec_row_count(affected_rows)

            # 조회(SELECT) 로직: FrDbParam에 결과 채우기
            if is_fetching and fr_param_obj:
                rows = cursor.fetchall()
                
                if cursor.description:
                    col_cnt = len(cursor.description)
                    fr_param_obj.SetCol(col_cnt)
                    
                    for row in rows:
                        # C++ 호환성을 위해 모든 값을 문자열로 변환하여 저장
                        # None(NULL)은 빈 문자열("")로 처리
                        str_row = [str(val) if val is not None else "" for val in row]
                        record = FrDbRecord(str_row)
                        fr_param_obj.AddRecord(record)
                
                fr_param_obj.Rewind()

            # Auto Commit 처리
            if auto_commit:
                self.commit()
            
            cursor.close()
            return True

        except pymysql.MySQLError as e:
            self.m_ErrCode = e.args[0]
            self._error(str(e), target_query)
            
            # 에러 발생 시 자동 롤백 시도
            if auto_commit:
                self.rollback()
            return False

    # -------------------------------------------------------
    # 결과셋 반환 실행 (ExecuteRs)
    # -------------------------------------------------------
    def execute_rs(self, query):
        """
        C++: virtual frDbRecordSet* ExecuteRs(char* Query)
        SELECT 결과를 한 번에 다 가져오지 않고, Cursor를 가진 RecordSet 객체를 반환
        """
        if not self.m_Connect:
            return None

        try:
            # 커서를 닫지 않고 RecordSet에게 넘겨줌
            cursor = self.conn.cursor()
            cursor.execute(query)
            
            # RecordSet 객체 생성 (Session 자신과 커서 전달)
            rs = FrDbRecordSet(self, self.m_DBType, cursor)
            return rs
            
        except pymysql.MySQLError as e:
            self._error(str(e), query)
            return None
        
    # -------------------------------------------------------
    # BLOB/CLOB 업데이트 (UpdateLong)
    # -------------------------------------------------------
    def update_long(self, table, field, value, where_clause):
        """
        C++: bool UpdateLong(...)
        BLOB 등의 데이터를 업데이트할 때 사용.
        pymysql은 일반 execute로도 바이너리/긴 문자열 처리가 가능함.
        """
        if value is None:
            self.m_Error = "VALUE is NULL"
            return False

        # %s 바인딩을 사용하면 pymysql이 알아서 이스케이프/바이너리 처리 수행
        query = f"UPDATE {table} SET {field} = %s WHERE {where_clause}"
        return self.execute(query, [value], auto_commit=True)

    # -------------------------------------------------------
    # 프로시저 실행 (ExecuteProcedure)
    # -------------------------------------------------------
    def execute_procedure(self, proc_obj_or_name, args=(), auto_commit=False):
        """
        C++: bool ExecuteProcedure(ProcCallParam& CallValue, bool AutoCommit)
        
        [개선된 로직]
        1. 인자가 ProcCallParam 객체이면 -> 내부에서 프로시저 이름과 인자 리스트 추출
        2. 인자가 문자열(프로시저명)이면 -> args 튜플 사용 (Python 스타일)
        """
        if not self.m_Connect:
            return False

        proc_name = ""
        proc_args = ()

        # Duck Typing: ProcCallParam 객체인지 확인 (m_ProcedureName 속성 유무로 판단)
        if hasattr(proc_obj_or_name, 'm_ProcedureName') and hasattr(proc_obj_or_name, 'get_args_list'):
            # C++ 스타일 호출 (ProcCallParam 객체 전달)
            proc_name = proc_obj_or_name.m_ProcedureName
            proc_args = proc_obj_or_name.get_args_list()
        else:
            # Python 스타일 호출 (이름, 인자 전달)
            proc_name = proc_obj_or_name
            proc_args = args

        try:
            cursor = self.conn.cursor()
            
            # 프로시저 호출
            # pymysql callproc: IN 인자는 그대로, OUT 인자는 실행 후 반환값에 포함됨
            cursor.callproc(proc_name, proc_args)
            
            # (선택사항) C++ 로직처럼 OUT 파라미터를 ProcCallParam 객체에 다시 채워넣으려면
            # cursor.fetchall() 등을 통해 값을 가져와서 proc_obj_or_name의 BindData에 
            # 역으로 값을 셋팅하는 로직을 여기에 추가할 수 있습니다.

            if auto_commit:
                self.commit()
            
            cursor.close()
            return True

        except pymysql.MySQLError as e:
            self.m_ErrCode = e.args[0]
            self._error(str(e), proc_name)
            return False

    # -------------------------------------------------------
    # 유틸리티 (SetDBCharacterSet / Error Helper)
    # -------------------------------------------------------
    def set_db_character_set(self, charset_name):
        """
        C++: bool SetDBCharacterSet(...)
        """
        return self.execute(f"SET NAMES '{charset_name}'", auto_commit=False)

    def _error(self, error_msg, query=None):
        """
        C++: void _Error(...)
        에러 메시지를 포맷팅하고 저장/출력
        """
        self.m_Error = error_msg
        if query:
            self.m_Error += f" [{query}]"
        
        # 로그 출력 (서버 환경에 맞춰 logging 모듈로 대체 가능)
        print(f"[DB Error] {self.m_Error}")