import sys
import os
import oracledb

# -------------------------------------------------------
# 1. 프로젝트 경로 및 모듈 Import 설정
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))

if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Sql.FrBaseType import EDB_TYPE, E_QUERY_DATA_TYPE, E_QUERY_JOIN_POSITION
from Class.Sql.FrDbSession import FrDbSession
from Class.Sql.FrDbParam import FrDbParam, FrDbRecord

try:
    from Class.Sql.FrDbRecordSet import FrDbRecordSet
except ImportError:
    FrDbRecordSet = None

# -------------------------------------------------------
# 2. FrOraSession2 클래스 정의
# -------------------------------------------------------
class FrOraSession2(FrDbSession):
    def __init__(self, name=None):
        """
        C++: frOraSession2(char *Name)
        OCI 핸들(Env, Svc, Stmt 등) 초기화는 oracledb가 내부적으로 처리하므로 불필요
        """
        super().__init__(name)
        self.m_DBType = EDB_TYPE.ORACLE
        self.conn = None
        
        # 오라클 날짜 포맷 (C++ 코드의 ORACLE_DATE_FORMAT 대응)
        self.DATE_FMT = "YYYY/MM/DD HH24:MI:SS"

    def __del__(self):
        """
        C++: ~frOraSession2()
        """
        if self.m_Connect:
            self.disconnect()

    # -------------------------------------------------------
    # 연결 관리
    # -------------------------------------------------------
    def connect(self, user, password, db_name, db_ip=None, db_port=1521):
        """
        C++: bool Connect(...)
        OCI 초기화, 핸들 할당, 서버 어태치 과정을 oracledb.connect 하나로 해결
        """
        if self.conn:
            self.disconnect()

        try:
            # DSN(Data Source Name) 구성
            # 1. IP/Port가 있으면 -> EZConnect 형식 (IP:Port/ServiceName)
            # 2. 없으면 -> TNS Alias (tnsnames.ora에 정의된 이름)
            dsn_str = db_name
            if db_ip and db_port:
                dsn_str = f"{db_ip}:{db_port}/{db_name}"

            # Thin 모드 사용 (Oracle Client 설치 불필요)
            self.conn = oracledb.connect(
                user=user,
                password=password,
                dsn=dsn_str
            )
            
            # C++의 OCIAttrSet(TIMEOUT 등) 설정 대응
            self.conn.call_timeout = 30 * 1000 # 밀리초 단위 (30초)

            self.m_Connect = True
            return True

        except oracledb.Error as e:
            error_obj = e.args[0]
            self.m_ErrCode = error_obj.code
            self._error(error_obj.message)
            return False

    def disconnect(self):
        """
        C++: void Disconnect()
        OCIHandleFree 등 복잡한 해제 과정 불필요
        """
        self.m_Connect = False
        if self.conn:
            try:
                self.conn.close()
            except:
                pass
            self.conn = None

    # -------------------------------------------------------
    # 트랜잭션
    # -------------------------------------------------------
    def commit(self):
        if not self.m_Connect: return False
        try:
            self.conn.commit()
            return True
        except oracledb.Error as e:
            self._error(e.args[0].message)
            return False

    def rollback(self):
        if not self.m_Connect: return False
        try:
            self.conn.rollback()
            return True
        except oracledb.Error as e:
            self._error(e.args[0].message)
            return False

    # -------------------------------------------------------
    # 실행 (Execute) - 통합 메서드
    # -------------------------------------------------------
    def execute(self, query_or_param, bind_params=None, auto_commit=True):
        """
        C++의 BindParamByPos(위치 기반)와 BindParamByName(이름 기반)을 모두 처리
        """
        if not self.m_Connect:
            return False

        self.set_exec_row_count(-1)
        
        target_query = ""
        is_fetching = False
        fr_param_obj = None

        # 1. 인자 분석 (FrDbParam 객체 vs 문자열 쿼리)
        if isinstance(query_or_param, FrDbParam):
            fr_param_obj = query_or_param
            target_query = fr_param_obj.GetQuery()
            is_fetching = True
        else:
            target_query = query_or_param
            is_fetching = False

        # 2. 바인딩 파라미터 변환 (C++ 객체 -> Python dict/list)
        # C++ 코드에서 BParam은 벡터 형태. Python 호출 시에는 
        # [1, "val"] (List) 또는 {"key": "val"} (Dict) 형태로 넘어온다고 가정하거나,
        # C++ 구조체(BindParamByPos)를 흉내낸 객체라면 변환 로직이 필요함.
        # 여기서는 Python의 표준적인 List/Dict 사용을 가정함.
        
        real_params = bind_params
        
        # 만약 bind_params가 C++ 포팅된 객체 리스트라면 값만 추출 (예시 로직)
        if bind_params and isinstance(bind_params, list) and hasattr(bind_params[0], 'm_BindType'):
             # BindParamByPos 대응 (값 리스트로 변환)
             real_params = [p.m_StrData if p.m_BindType == 0 else (p.m_IntData if p.m_BindType == 1 else p.m_NumberData) for p in bind_params]

        try:
            cursor = self.conn.cursor()
            
            # 3. 실행
            # oracledb는 위치 기반(:1, :2)은 리스트, 이름 기반(:name)은 딕셔너리로 바인딩함
            cursor.execute(target_query, real_params)
            
            # 영향받은 행 개수
            if cursor.rowcount > -1:
                self.set_exec_row_count(cursor.rowcount)

            # 4. 조회 결과 처리
            if is_fetching and fr_param_obj:
                rows = cursor.fetchall()
                if cursor.description:
                    col_cnt = len(cursor.description)
                    fr_param_obj.SetCol(col_cnt)
                    
                    for row in rows:
                        # C++ 호환성: 모든 값을 문자열로 변환
                        str_row = []
                        for val in row:
                            if val is None:
                                str_row.append("")
                            elif isinstance(val, oracledb.LOB):
                                str_row.append(str(val.read())) # CLOB 처리
                            else:
                                str_row.append(str(val))
                                
                        record = FrDbRecord(str_row)
                        fr_param_obj.AddRecord(record)
                
                fr_param_obj.Rewind()

            if auto_commit:
                self.commit()
            
            cursor.close()
            return True

        except oracledb.Error as e:
            error_obj = e.args[0]
            self.m_ErrCode = error_obj.code
            self._error(error_obj.message, target_query)
            if auto_commit:
                self.rollback()
            return False

    def execute_rs(self, query):
        """
        C++: virtual frDbRecordSet* ExecuteRs(char* Query)
        """
        if not self.m_Connect or FrDbRecordSet is None:
            return None

        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            
            rs = FrDbRecordSet(self, self.m_DBType, cursor)
            return rs
            
        except oracledb.Error as e:
            self.m_ErrCode = e.args[0].code
            self._error(e.args[0].message, query)
            return None

    def execute_procedure(self, proc_obj_or_name, args=(), auto_commit=False):
        """
        프로시저 실행
        """
        if not self.m_Connect: return False
        
        proc_name = proc_obj_or_name
        proc_args = list(args) # List로 변환

        # ProcCallParam 객체 처리
        if hasattr(proc_obj_or_name, 'm_ProcedureName'):
            proc_name = proc_obj_or_name.m_ProcedureName
            # C++ ProcCallParam에서 값을 추출해야 함
            # 여기서는 args가 이미 변환되어 들어왔다고 가정하거나 추가 로직 구현 필요
        
        try:
            cursor = self.conn.cursor()
            
            # oracledb의 callproc 사용
            cursor.callproc(proc_name, proc_args)
            
            if auto_commit:
                self.commit()
            cursor.close()
            return True
        except oracledb.Error as e:
            self._error(e.args[0].message, proc_name)
            return False

    def update_long(self, table, field, value, where_clause):
        """
        C++: UpdateLong (CLOB/BLOB 업데이트)
        oracledb는 긴 문자열도 일반 execute로 처리 가능
        """
        if value is None:
            return False
            
        # 오라클 바인딩 변수 문법 (:1) 사용
        query = f"UPDATE {table} SET {field} = :1 WHERE {where_clause}"
        return self.execute(query, [value], auto_commit=True)

    # -------------------------------------------------------
    # SQL 생성 헬퍼 (Oracle Syntax)
    # -------------------------------------------------------
    def make_insert_query(self, data_type, data):
        if data_type == E_QUERY_DATA_TYPE.DATE:
            return f"TO_DATE('{data}', '{self.DATE_FMT}')"
        return f"'{data}'"

    def make_select_query(self, data_type, field):
        if data_type == E_QUERY_DATA_TYPE.DATE:
            return f"TO_CHAR({field}, '{self.DATE_FMT}')"
        return field

    def make_query_outer_join(self, join_pos, l_field, r_field):
        """
        C++ 코드 로직: Oracle 전용 (+) 문법 사용
        """
        if join_pos == E_QUERY_JOIN_POSITION.LEFT:
            return f"{l_field} (+) = {r_field}"
        else:
            return f"{l_field} = {r_field} (+)"

    def make_query_binder(self, bind_name):
        return f":{bind_name}"

    def set_db_character_set(self, charset_name):
        # Python oracledb는 connect 시 encoding을 설정함.
        # 실행 중 변경은 불가능하므로 Pass
        return True

    def _error(self, error_msg, query=None):
        self.m_Error = error_msg
        if query:
            self.m_Error += f" [{query}]"
        print(f"[Oracle Error] {self.m_Error}")