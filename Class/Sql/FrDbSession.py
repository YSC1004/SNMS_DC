import sys
import os

# -------------------------------------------------------
# 1. 프로젝트 경로 설정
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))

if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# 2. 모듈 Import
# -------------------------------------------------------
# FrBaseType에서 Enum과 QueryResult를 가져옵니다.
from Class.Sql.FrBaseType import EDB_TYPE, E_QUERY_DATA_TYPE, E_QUERY_JOIN_POSITION, QueryResult

# SqlQuery 메서드에서 Select 쿼리 처리를 위해 FrDbParam이 필요합니다.
from Class.Sql.FrDbParam import FrDbParam

# -------------------------------------------------------
# 3. Main Class: FrDbSession (Abstract Base Class)
# -------------------------------------------------------
class FrDbSession:
    # 에러 코드 상수 (C++ IsDbDisConErr 대응)
    ORA_DISCON_ERRS = [3114, 3113, 12154, 1017, 1012]
    MYSQL_DISCON_ERRS = [2006, 2013, 2003, 2055]

    def __init__(self, name=None):
        self.m_Name = name
        self.m_Connect = False
        self.m_Error = ""
        self.m_ErrCode = 0
        self.m_ExecRowCnt = -1
        self.m_DBType = EDB_TYPE.MYSQL  # Default

    # -------------------------------------------------------
    # Factory Method (GetInstance)
    # -------------------------------------------------------
    @staticmethod
    def get_instance(db_kind=EDB_TYPE.MYSQL, name=None):
        """
        DB 타입에 맞는 자식 클래스 인스턴스(MySQL/Oracle)를 생성하여 반환
        """
        ret = None
        
        # 순환 참조(Circular Import) 방지를 위해 함수 내부에서 import
        if db_kind == EDB_TYPE.MYSQL:
            try:
                from Class.Sql.FrMySQLSession import FrMySQLSession
                ret = FrMySQLSession(name)
            except ImportError as e:
                print(f"[Error] FrMySQLSession import failed: {e}")

        elif db_kind == EDB_TYPE.ORACLE:
            try:
                from Class.Sql.FrOraSession2 import FrOraSession2
                ret = FrOraSession2(name)
            except ImportError as e:
                print(f"[Error] FrOraSession2 import failed: {e}")

        if ret:
            ret.m_DBType = db_kind
        else:
            print("[Error] DB Instance Creation Failed (DB IS NULL)")
            
        return ret

    @staticmethod
    def get_db_type_from_str(db_type_str):
        """문자열("MYSQL", "ORACLE")을 Enum으로 변환"""
        if not db_type_str: return -1
        s = db_type_str.upper().strip()
        if "ORACLE" in s:
            return EDB_TYPE.ORACLE
        if "MYSQL" in s:
            return EDB_TYPE.MYSQL
        return -1

    # -------------------------------------------------------
    # SqlQuery Logic (C++ SqlQuery 구현)
    # -------------------------------------------------------
    def sql_query(self, query, result_obj, bind_param=None, addition_text=""):
        """
        C++: bool SqlQuery(string Query, QueryResult& Result, ...)
        쿼리 문자열을 분석하여 SELECT(조회)인지 INSERT/UPDATE/DELETE(변경)인지
        자동으로 판단하고 실행 결과를 result_obj에 채웁니다.
        """
        # 1. 쿼리 앞부분 정제 (주석 제거 등은 복잡하므로 단순 strip 처리)
        tmp_query = query.strip().upper()
        
        # C++ 로직 대응: 앞부분 단어로 쿼리 타입 추론
        cmd = tmp_query.split()[0] if tmp_query else ""
        
        is_modification = cmd in ["INSERT", "UPDATE", "DELETE"]
        
        success = False

        # --- Case 1: 데이터 변경 (INSERT / UPDATE / DELETE) ---
        if is_modification:
            self.set_exec_row_count(-1)
            
            # execute 호출 (AutoCommit=False로 트랜잭션 관리)
            if bind_param:
                success = self.execute(query, bind_param, auto_commit=False)
            else:
                success = self.execute(query, auto_commit=False)

            if success:
                result_obj.m_Result = 1
                result_obj.m_RowCnt = self.get_exec_row_count()
            else:
                result_obj.m_Result = 0
                result_obj.m_RowCnt = -1
                result_obj.m_ErrorString = self.get_error()
                result_obj.m_ErrorCode = self.m_ErrCode

        # --- Case 2: 데이터 조회 (SELECT 등) ---
        else:
            # 조회 결과를 담을 FrDbParam 객체 생성
            param = FrDbParam(query)
            result_obj.m_Param = param
            
            if bind_param:
                success = self.execute(param, bind_param)
            else:
                success = self.execute(param)

            if success:
                result_obj.m_Result = 1
                result_obj.m_ColCnt = param.GetCol()
                
                # 결과 레코드 추출
                records = param.get_all_records()
                result_obj.m_RowCnt = len(records)
                
                if result_obj.m_RowCnt > 0:
                    # QueryResult의 m_Buf(2차원 리스트)에 값 참조 연결
                    result_obj.m_Buf = [rec.m_Values for rec in records]
            else:
                result_obj.m_Result = 0
                result_obj.m_ErrorString = self.get_error()
                result_obj.m_ErrorCode = self.m_ErrCode

        return success

    # -------------------------------------------------------
    # Utility Methods (테이블 존재 확인, Bulk Loader 등)
    # -------------------------------------------------------
    def is_exist_table(self, table_name):
        """
        C++: bool IsExistTable(string TableName)
        """
        query = ""
        if self.m_DBType == EDB_TYPE.ORACLE:
             query = f"SELECT COUNT(*) FROM TAB WHERE TNAME = '{table_name.upper()}'"
        elif self.m_DBType == EDB_TYPE.MYSQL:
             # MySQL은 DB명을 명시하지 않으면 현재 DB 기준
             query = f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = '{table_name}'"
        else:
            return False

        # 테이블 존재 여부 확인을 위한 임시 파라미터 객체 사용
        param = FrDbParam(query)
        if self.execute(param):
            records = param.get_all_records()
            if records and len(records) > 0:
                # 결과값(Count)이 0보다 크면 True
                try:
                    cnt = int(records[0].m_Values[0])
                    return cnt > 0
                except:
                    return False
        return False

    def make_bulk_loader_command(self, db_type, db_user, db_passwd, db_name, 
                                 table_name, ctl_path, ctl_file, target_path, target_file):
        """
        C++: static bool MakeBulkLoaderCommand(...)
        Oracle SQL*Loader 또는 기타 DB 로더 커맨드라인 문자열 생성
        """
        cmd = ""
        if db_type == EDB_TYPE.ORACLE:
            # Oracle sqlldr 문법
            cmd = (
                f"sqlldr {db_user}/{db_passwd}@{db_name} "
                f"control={ctl_path}/{ctl_file}.ctl "
                f"data={target_path}/{target_file} "
                f"log={target_path}/{target_file}.log "
                f"bad={target_path}/{target_file}.bad "
                "errors=9999999999 silent=all"
            )
        elif db_type == EDB_TYPE.MYSQL:
            # MySQL mysqlimport 예시 (C++ 원본엔 없으나 추가 가능)
            # cmd = f"mysqlimport --local --user={db_user} --password={db_passwd} {db_name} {target_path}/{target_file}"
            pass
        
        return cmd

    def make_nvl_or_isnull_query(self):
        if self.m_DBType == EDB_TYPE.ORACLE:
            return "NVL"
        elif self.m_DBType == EDB_TYPE.MYSQL:
            return "IFNULL"
        return "ISNULL"

    # -------------------------------------------------------
    # Abstract Methods (Interface) - 자식 클래스 구현 필수
    # -------------------------------------------------------
    def execute(self, query_or_param, bind_params=None, auto_commit=True):
        raise NotImplementedError
    
    def connect(self, user, password, db_name, db_ip=None, db_port=0):
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError

    def commit(self):
        raise NotImplementedError

    def rollback(self):
        raise NotImplementedError

    # -------------------------------------------------------
    # Getters / Setters
    # -------------------------------------------------------
    def set_exec_row_count(self, row_cnt):
        self.m_ExecRowCnt = row_cnt
    
    def get_exec_row_count(self):
        return self.m_ExecRowCnt
    
    def get_error(self):
        return self.m_Error

    def get_db_type(self):
        return self.m_DBType

    # -------------------------------------------------------
    # Error Checking
    # -------------------------------------------------------
    def is_db_disconnect_err(self, error_code=None):
        code = error_code if error_code is not None else self.m_ErrCode
        
        if self.m_DBType == EDB_TYPE.ORACLE:
            return code in self.ORA_DISCON_ERRS
        elif self.m_DBType == EDB_TYPE.MYSQL:
            return code in self.MYSQL_DISCON_ERRS
        return False

    # -------------------------------------------------------
    # SQL Generators (Dialect Handling)
    # -------------------------------------------------------
    def make_insert_query(self, data_type, data):
        if data_type == E_QUERY_DATA_TYPE.DATE:
            if self.m_DBType == EDB_TYPE.ORACLE:
                return f"TO_DATE('{data}', 'YYYY/MM/DD HH24:MI:SS')"
            elif self.m_DBType == EDB_TYPE.MYSQL:
                return f"STR_TO_DATE('{data}', '%Y/%m/%d %H:%i:%s')"
            else:
                return f"'{data}'"
                
        # SYSDATE 처리 (Enum 값 4 가정)
        elif data_type == 4: 
             if self.m_DBType == EDB_TYPE.ORACLE:
                 return "SYSDATE"
             elif self.m_DBType == EDB_TYPE.MYSQL:
                 return "SYSDATE()"
        
        return f"'{data}'"

    def make_select_query(self, data_type, field):
        if data_type == E_QUERY_DATA_TYPE.DATE:
            if self.m_DBType == EDB_TYPE.ORACLE:
                return f"TO_CHAR({field}, 'YYYY/MM/DD HH24:MI:SS')"
            elif self.m_DBType == EDB_TYPE.MYSQL:
                return f"DATE_FORMAT({field}, '%Y/%m/%d %H:%i:%s')"
        
        elif data_type == 4: # SYSDATE
             if self.m_DBType == EDB_TYPE.ORACLE:
                 return "SYSDATE"
             elif self.m_DBType == EDB_TYPE.MYSQL:
                 return "SYSDATE()"
                 
        return field

    def make_query_outer_join(self, join_pos, l_field, r_field):
        if self.m_DBType == EDB_TYPE.ORACLE:
            if join_pos == E_QUERY_JOIN_POSITION.LEFT:
                return f"{l_field} (+) = {r_field}"
            else:
                return f"{l_field} = {r_field} (+)"
        
        elif self.m_DBType == EDB_TYPE.MYSQL:
            # MySQL은 (+) 문법 미지원 -> ANSI 표준 권장
            # 기존 로직 유지를 위해 단순 등호 반환 (주의 필요)
            return f"{l_field} = {r_field}"
            
        return f"{l_field} = {r_field}"

    def make_query_binder(self, bind_name):
        if self.m_DBType == EDB_TYPE.ORACLE:
            return f":{bind_name}"
        elif self.m_DBType == EDB_TYPE.MYSQL:
             return "%s" # pymysql Style
        return "?"