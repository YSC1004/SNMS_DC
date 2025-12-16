import sys
import os
from datetime import datetime

# -------------------------------------------------------
# 1. Global Enums (프로젝트 전반에서 사용)
# -------------------------------------------------------

# DB 종류
class EDB_TYPE:
    MYSQL = 0
    ORACLE = 1
    SQLITE = 2

# 쿼리 데이터 타입 (MakeInsertQuery 등에서 사용)
class E_QUERY_DATA_TYPE:
    STRING = 0
    NUMBER = 1
    DATE = 2
    SYSDATE = 4 # C++ 소스 기반 추정

# 조인 위치
class E_QUERY_JOIN_POSITION:
    LEFT = 0
    RIGHT = 1

# 프로시저 파라미터 타입
class PROC_PARAM_TYPE:
    ORA_PARAM_IN = 0
    ORA_PARAM_OUT = 1
    ORA_PARAM_INOUT = 2

# 바인딩 데이터 타입
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
        디버깅용 결과 출력
        """
        for row_idx, row_data in enumerate(self.m_Buf):
            row_buf = ""
            for col_data in row_data:
                # None 처리 및 문자열 변환
                val = str(col_data) if col_data is not None else ""
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
#    C++: vector<QueryBindData*> 상속 -> Python: list 상속
# -------------------------------------------------------
class BindParamByPos(list):
    def __init__(self):
        super().__init__()

    def clear(self):
        # [중요] self.clear()는 재귀 호출 에러 발생함. super() 사용 필수.
        super().clear()

    # Python은 오버로딩을 지원하지 않으므로 타입 검사(isinstance)로 분기
    def add_variable(self, value):
        ptr = QueryBindData()

        if isinstance(value, int):
            # Python의 bool은 int의 서브클래스이므로 bool 체크가 필요할 수도 있음
            # 여기서는 C++ 로직대로 int 처리
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

# -------------------------------------------------------
# 5. BindParamByName Class (이름 기반 바인딩 목록)
# -------------------------------------------------------
class BindParamByName(list):
    def __init__(self):
        super().__init__()

    def clear(self):
        super().clear()

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