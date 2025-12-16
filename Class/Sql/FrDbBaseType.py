import sys
import os
from datetime import datetime

# -------------------------------------------------------
# 1. Helper Enums (C++ frDbBaseType.h 대응)
# -------------------------------------------------------
class BIND_TYPE:
    BIND_STR = 0
    BIND_INT = 1
    BIND_FLT = 2
    BIND_DATE = 3

# -------------------------------------------------------
# 2. QueryResult Class
#    쿼리 실행 결과(성공여부, 에러, 데이터 등)를 담는 컨테이너
# -------------------------------------------------------
class QueryResult:
    def __init__(self):
        self.init()

    def init(self):
        self.m_Buf = []         # 결과 데이터 (2차원 리스트: [Row][Col])
        self.m_RowCnt = 0       # 행 개수
        self.m_ColCnt = 0       # 열 개수
        self.m_Result = 0       # 1: 성공, 0: 실패
        self.m_Param = None     # FrDbParam 객체 (결과셋 원본)
        self.m_ErrorCode = -1
        self.m_ErrorString = ""

    def free(self):
        # Python은 GC가 작동하므로 명시적 delete 불필요
        self.m_Buf = []
        self.m_Param = None
        self.m_RowCnt = 0

    def print_result(self):
        """
        C++: void Print()
        """
        for row_idx, row_data in enumerate(self.m_Buf):
            row_buf = ""
            for col_data in row_data:
                # None 처리 및 문자열 변환
                val = col_data if col_data is not None else ""
                row_buf += f"[{val}]"
            
            print(f"(ROW:{row_idx + 1}){row_buf}")
            
        sys.stdout.flush()

# -------------------------------------------------------
# 3. QueryBindData Class
#    단일 바인딩 변수의 값과 타입을 저장
# -------------------------------------------------------
class QueryBindData:
    def __init__(self):
        self.m_BindType = BIND_TYPE.BIND_STR
        self.m_StrData = ""
        self.m_IntData = 0
        self.m_NumberData = 0.0
        self.m_Date = None      # Python datetime 객체
        self.m_BindName = ""    # 이름 기반 바인딩용
        self.m_BindName2 = ""   # :name 형태

# -------------------------------------------------------
# 4. BindParamByPos Class (위치 기반 바인딩 목록)
#    C++: vector<QueryBindData*> 상속
#    Python: list 상속
# -------------------------------------------------------
class BindParamByPos(list):
    def __init__(self):
        super().__init__()

    def clear(self):
        self.clear() # list.clear()

    # Python은 오버로딩을 지원하지 않으므로 타입 검사(isinstance)로 분기
    def add_variable(self, value):
        ptr = QueryBindData()

        if isinstance(value, int):
            ptr.m_BindType = BIND_TYPE.BIND_INT
            ptr.m_IntData = value
        elif isinstance(value, float):
            ptr.m_BindType = BIND_TYPE.BIND_FLT
            ptr.m_NumberData = value
        elif isinstance(value, datetime):
            ptr.m_BindType = BIND_TYPE.BIND_DATE
            ptr.m_Date = value
            # C++의 m_Ora7Time (byte manipulation) 로직은 
            # oracledb 라이브러리가 자동으로 처리하므로 불필요
        else:
            # String or Others
            ptr.m_BindType = BIND_TYPE.BIND_STR
            ptr.m_StrData = str(value) if value is not None else ""

        self.append(ptr)

# -------------------------------------------------------
# 5. BindParamByName Class (이름 기반 바인딩 목록)
# -------------------------------------------------------
class BindParamByName(list):
    def __init__(self):
        super().__init__()

    def clear(self):
        self.clear()

    def add_variable(self, bind_name, value):
        ptr = QueryBindData()
        ptr.m_BindName = bind_name if bind_name else ""
        ptr.m_BindName2 = f":{ptr.m_BindName}"

        if isinstance(value, int):
            ptr.m_BindType = BIND_TYPE.BIND_INT
            ptr.m_IntData = value
        elif isinstance(value, float):
            ptr.m_BindType = BIND_TYPE.BIND_FLT
            ptr.m_NumberData = value
        elif isinstance(value, datetime):
            ptr.m_BindType = BIND_TYPE.BIND_DATE
            ptr.m_Date = value
        else:
            # String or Others
            ptr.m_BindType = BIND_TYPE.BIND_STR
            ptr.m_StrData = str(value) if value is not None else ""

        self.append(ptr)