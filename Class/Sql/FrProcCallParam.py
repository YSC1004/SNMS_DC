import sys
import os

# 상위 폴더 참조
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Sql.FrBaseType import EDB_TYPE, PROC_PARAM_TYPE, BIND_DATA_TYPE

# -------------------------------------------------------
# BindData Class (C++ BindData 대응)
# -------------------------------------------------------
class BindData:
    def __init__(self):
        self.m_BindType = BIND_DATA_TYPE.BIND_STR
        self.m_ProcParamType = PROC_PARAM_TYPE.ORA_PARAM_IN
        self.m_BindName = ""
        
        # Python은 타입 구분이 느슨하므로 값을 하나의 변수에 저장해도 되지만,
        # C++ 구조를 유지하기 위해 개별 변수 사용
        self.m_StrData = ""
        self.m_IntData = 0
        self.m_NumberData = 0.0
        self.m_BindSize = 0

    def bind_str(self, proc_param_type, bind_name, bind_value, bind_size=0):
        self.m_BindType = BIND_DATA_TYPE.BIND_STR
        self.m_ProcParamType = proc_param_type
        self.m_BindName = bind_name
        self.m_BindSize = bind_size
        
        # 문자열 값 저장
        self.m_StrData = str(bind_value) if bind_value is not None else ""

    def bind_int(self, proc_param_type, bind_name, bind_value):
        self.m_BindType = BIND_DATA_TYPE.BIND_INT
        self.m_ProcParamType = proc_param_type
        self.m_BindName = bind_name
        self.m_IntData = int(bind_value)

    def bind_double(self, proc_param_type, bind_name, bind_value):
        self.m_BindType = BIND_DATA_TYPE.BIND_FLT
        self.m_ProcParamType = proc_param_type
        self.m_BindName = bind_name
        self.m_NumberData = float(bind_value)

    def get_value(self):
        """현재 바인딩된 실제 값을 반환하는 헬퍼 메서드"""
        if self.m_BindType == BIND_DATA_TYPE.BIND_INT:
            return self.m_IntData
        elif self.m_BindType == BIND_DATA_TYPE.BIND_FLT:
            return self.m_NumberData
        return self.m_StrData

# -------------------------------------------------------
# ProcCallParam Class (C++ ProcCallParam 대응)
# -------------------------------------------------------
class ProcCallParam:
    def __init__(self, procedure_name=""):
        self.m_ProcedureName = procedure_name
        self.m_DbType = -1 # eUnknownType
        self.m_ErrMsg = ""
        
        # 파라미터 목록 (List of BindData)
        self.m_Params = [] 
        
        # OUT/INOUT 파라미터의 인덱스를 저장하는 리스트
        self.m_ResPosVector = [] 

    def size(self):
        return len(self.m_Params)

    def clear(self):
        self.m_Params = []
        self.m_ResPosVector = []

    def at(self, index):
        if 0 <= index < len(self.m_Params):
            return self.m_Params[index]
        return None

    # --- Add Parameter Methods ---

    def add_variable(self, proc_param_type, name, value):
        """AddParamStr과 동일 (C++ 소스 참조)"""
        return self.add_param_str(proc_param_type, name, value)

    def add_param_str(self, proc_param_type, name, value, bind_size=0):
        data = BindData()
        data.bind_str(proc_param_type, name, value, bind_size)
        self.m_Params.append(data)

        if proc_param_type in [PROC_PARAM_TYPE.ORA_PARAM_OUT, PROC_PARAM_TYPE.ORA_PARAM_INOUT]:
            self.m_ResPosVector.append(len(self.m_Params) - 1)
        return True

    def add_param_int(self, proc_param_type, name, value):
        data = BindData()
        data.bind_int(proc_param_type, name, value)
        self.m_Params.append(data)

        if proc_param_type in [PROC_PARAM_TYPE.ORA_PARAM_OUT, PROC_PARAM_TYPE.ORA_PARAM_INOUT]:
            self.m_ResPosVector.append(len(self.m_Params) - 1)
        return True

    def add_param_double(self, proc_param_type, name, value):
        data = BindData()
        data.bind_double(proc_param_type, name, value)
        self.m_Params.append(data)

        if proc_param_type in [PROC_PARAM_TYPE.ORA_PARAM_OUT, PROC_PARAM_TYPE.ORA_PARAM_INOUT]:
            self.m_ResPosVector.append(len(self.m_Params) - 1)
        return True

    # --- Query Generation ---

    def make_query(self, db_type):
        self.m_DbType = db_type
        query = ""
        
        # 파라미터 목록 생성
        params_str_list = []
        
        if self.m_DbType == EDB_TYPE.ORACLE:
            for param in self.m_Params:
                params_str_list.append(f":{param.m_BindName}")
            
            param_str = ", ".join(params_str_list)
            query = f"BEGIN {self.m_ProcedureName}({param_str}); END;"

        elif self.m_DbType == EDB_TYPE.MYSQL:
            # MySQL은 값 바인딩 시 '?' 또는 '%s' 사용 (여기서는 C++ 로직인 '?' 유지하되 pymysql은 실제 호출 시 인자로 값 전달)
            # pymysql callproc는 쿼리를 직접 짜는게 아니라 프로시저 이름과 인자 리스트를 넘김
            # 하지만 make_query의 목적이 로그용이거나 직접 실행용이라면 문자열 생성은 필요함
            for _ in self.m_Params:
                params_str_list.append("?") # 또는 %s
            
            param_str = ", ".join(params_str_list)
            query = f"CALL {self.m_ProcedureName}({param_str})"
            
        else:
            print("Error: unknown db type at ProcCallParam::MakeQuery")
            
        return query

    def get_value(self, name):
        """이름으로 값 찾기"""
        for param in self.m_Params:
            if param.m_BindName == name:
                return param.m_StrData # C++ 코드 기준으로는 StrData 반환
        return ""
    
    def get_err_msg(self):
        return self.m_ErrMsg

    # --- Debug / Print ---
    
    def print_param(self):
        """
        C++: Print()
        """
        print(f"\n------- Procedure call [{self.m_ProcedureName}] ---------")
        
        for param in self.m_Params:
            p_type = "UNKNOWN"
            if param.m_ProcParamType == PROC_PARAM_TYPE.ORA_PARAM_IN: p_type = "IN"
            elif param.m_ProcParamType == PROC_PARAM_TYPE.ORA_PARAM_OUT: p_type = "OUT"
            elif param.m_ProcParamType == PROC_PARAM_TYPE.ORA_PARAM_INOUT: p_type = "INOUT"

            b_type = "UNKNOWN"
            val_str = ""
            
            if param.m_BindType == BIND_DATA_TYPE.BIND_STR:
                b_type = "STR"
                val_str = param.m_StrData
            elif param.m_BindType == BIND_DATA_TYPE.BIND_INT:
                b_type = "INT"
                val_str = str(param.m_IntData)
            elif param.m_BindType == BIND_DATA_TYPE.BIND_FLT:
                b_type = "FLT"
                val_str = f"{param.m_NumberData:.1f}"

            print(f"BindName[{param.m_BindName}], ParamType[{p_type}], BindType[{b_type}], Value[{val_str}]")
            
        print("-------------------------------------")

    # --- Helper for Python Execution ---
    def get_args_list(self):
        """
        pymysql.callproc()에 넘겨줄 인자 리스트(튜플)를 생성
        """
        args = []
        for param in self.m_Params:
            args.append(param.get_value())
        return tuple(args)