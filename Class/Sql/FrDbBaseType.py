import sys
import os
import ctypes
from enum import Enum
from datetime import datetime

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import FrTime if exists, else use datetime or placeholder
try:
    from Class.Util.FrTime import FrTime
except ImportError:
    # If FrTime is not defined, we treat it compatibly with datetime in bindings
    FrTime = datetime

# -------------------------------------------------------
# Type Definitions (typedefs for C++ compatibility)
# -------------------------------------------------------
sb1 = ctypes.c_byte      # signed char
sb2 = ctypes.c_short     # signed short
sb4 = ctypes.c_int       # signed int
sword = ctypes.c_int     # signed int
ub1 = ctypes.c_ubyte     # unsigned char
ub2 = ctypes.c_ushort    # unsigned short
ub4 = ctypes.c_uint      # unsigned int

# Lda_Def, Cda_Def are opaque pointers in C++. In Python, use None or object.
Lda_Def = object
Cda_Def = object

# -------------------------------------------------------
# Constants & Macros
# -------------------------------------------------------
DB_MAX_ITEM_BUF_SIZE = 2048

NEW_INSTANCE = 0
ALREADY_INSTANCE = 1

# String Constants
DB_ORACLE_OCI_STR = "ORACLE"
DB_MYSQL_STR = "MYSQL"

# -------------------------------------------------------
# Enums
# -------------------------------------------------------
class eDB_TYPE(Enum):
    eDB_ORACLE_OCI2 = 0
    eDB_MYSQL = 1
    eDB_MSSQL_ODBC = 2
    eDB_ORACLE_ODBC = 3
    eASCA_DB_GW = 4
    eDB_ORACLE_OCI_OLD = 5
    eUnknownType = 99

class eDB_CHARACTER_SET(Enum):
    DB_CHAR_NOTE = 0
    DB_CHAR_UTF8 = 1

class eQUERY_DATA_TYPE(Enum):
    eDATE_TYPE = 0
    eSYSDATE = 1

class eQUERY_JOIN_POSITION(Enum):
    eLEFT_JOIN = 0
    eRIGHT_JOIN = 1

# -------------------------------------------------------
# Helper Enums (C++ frDbBaseType.h 대응 - BIND_TYPE)
# -------------------------------------------------------
class BIND_TYPE:
    BIND_STR = 0
    BIND_INT = 1
    BIND_FLT = 2
    BIND_DATE = 3

# -------------------------------------------------------
# Classes & Structures
# -------------------------------------------------------

class FrDbDescRecord:
    """
    C++: class frDbDescRecord
    Description Record for DB Columns.
    """
    def __init__(self):
        self.m_DbSize = 0      # sb4
        self.m_DbType = 0      # sb2
        self.m_Buf = bytearray(DB_MAX_ITEM_BUF_SIZE) # sb1[DB_MAX_ITEM_BUF_SIZE]
        self.m_BufLen = 0      # sb4
        self.m_Dsize = 0       # sb4
        self.m_Precision = 0   # sb2
        self.m_Scale = 0       # sb2
        self.m_NullOk = 0      # sb2

class FrDbDescRecordList:
    """
    C++: class frDbDescRecordList : public list<frDbDescRecord*>
    """
    def __init__(self):
        self.items = [] # List of FrDbDescRecord

    def clear(self):
        self.items.clear()
    
    def add(self, item):
        self.items.append(item)

class FrDbDefRecord:
    """
    C++: class frDbDefRecord
    Definition Record for DB Data Fetching.
    """
    def __init__(self):
        self.m_Buf = bytearray(DB_MAX_ITEM_BUF_SIZE) # ub1[DB_MAX_ITEM_BUF_SIZE]
        self.m_LongBuf = None  # ub1* (Pointer to bytearray or string)
        self.m_FltBuf = 0.0    # float
        self.m_IntBuf = 0      # sword
        self.m_Indp = 0        # sb2 (Indicator pointer)
        self.m_ColRetLen = 0   # ub2
        self.m_ColRetCode = 0  # ub2

class FrDbDefRecordList:
    """
    C++: class frDbDefRecordList : public list<frDbDefRecord*>
    """
    def __init__(self):
        self.items = [] # List of FrDbDefRecord

    def clear(self):
        self.items.clear()
    
    def add(self, item):
        self.items.append(item)

class RsFetchInfo:
    """
    C++: class RsFetchInfo
    Holds context for fetching result sets (cursors, column info).
    """
    def __init__(self, cursor, col_cnt, desc_list, def_list):
        self.m_Cursor = cursor        # void*
        self.m_ColCnt = col_cnt       # int
        self.m_DescList = desc_list   # FrDbDescRecordList*
        self.m_DefList = def_list     # FrDbDefRecordList*

class FrOCITime:
    """C++: struct frOCITime"""
    def __init__(self):
        self.OCITimeHH = 0 # ub1
        self.OCITimeMI = 0 # ub1
        self.OCITimeSS = 0 # ub1

class FrOCIDate:
    """C++: struct frOCIDate"""
    def __init__(self):
        self.OCIDateYYYY = 0 # sb2
        self.OCIDateMM = 0   # ub1
        self.OCIDateDD = 0   # ub1
        self.OCIDateTime = FrOCITime()

class FrMySQLDate:
    """C++: struct frMySQLDate"""
    def __init__(self):
        self.year = 0
        self.month = 0
        self.day = 0
        self.hour = 0
        self.minute = 0
        self.second = 0
        self.second_part = 0
        self.neg = 0
        self.time_type = 0

# -------------------------------------------------------
# QueryResult Class (Combined & Enhanced)
# -------------------------------------------------------
class QueryResult:
    """
    C++: class QueryResult
    Container for Query execution results.
    """
    def __init__(self):
        self.init()

    def init(self):
        self.m_Buf = []         # 결과 데이터 (2차원 리스트: [Row][Col]) - C++ char*** 대응
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
# QueryBindData Class (Combined & Enhanced)
# -------------------------------------------------------
class QueryBindData:
    """
    C++: class QueryBindData
    Stores bind variable data for prepared statements.
    """
    def __init__(self):
        self.m_BindType = BIND_TYPE.BIND_STR
        self.m_StrData = ""
        self.m_IntData = 0
        self.m_NumberData = 0.0
        self.m_Date = None      # Python datetime 객체
        self.m_OCIDate = FrOCIDate()
        self.m_DBDatePtr = None # char*
        
        self.m_BindName = ""    # 이름 기반 바인딩용
        self.m_BindName2 = ""   # :name 형태
        self.m_Ora7Time = bytearray(7) # ub1[7]
        self.m_StrLen = 0

# -------------------------------------------------------
# BindParamByPos Class (Combined & Enhanced)
# -------------------------------------------------------
class BindParamByPos(list):
    """
    C++: class BindParamByPos : public vector<QueryBindData*>
    """
    def __init__(self):
        super().__init__()

    def clear(self):
        super().clear() # list.clear()

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
        elif isinstance(value, FrTime): # Support FrTime if it's a separate class
            ptr.m_BindType = BIND_TYPE.BIND_DATE
            ptr.m_Date = value # Assuming compatible or conversion needed
        else:
            # String or Others
            ptr.m_BindType = BIND_TYPE.BIND_STR
            val_str = str(value) if value is not None else ""
            ptr.m_StrData = val_str
            ptr.m_StrLen = len(val_str)

        self.append(ptr)

# -------------------------------------------------------
# BindParamByName Class (Combined & Enhanced)
# -------------------------------------------------------
class BindParamByName(list):
    """
    C++: class BindParamByName : public vector<QueryBindData*>
    """
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
        elif isinstance(value, FrTime):
            ptr.m_BindType = BIND_TYPE.BIND_DATE
            ptr.m_Date = value
        else:
            # String or Others
            ptr.m_BindType = BIND_TYPE.BIND_STR
            val_str = str(value) if value is not None else ""
            ptr.m_StrData = val_str
            ptr.m_StrLen = len(val_str)

        self.append(ptr)

# -------------------------------------------------------
# DB Info Structure
# -------------------------------------------------------
class FrDbInfoT:
    """
    C++: typedef struct { ... } FR_DB_INFO_T;
    """
    def __init__(self):
        self.Dbtype = eDB_TYPE.eDB_ORACLE_OCI2
        self.Userid = ""        # char[100]
        self.Userpw = ""        # char[100]
        self.Dbname = ""        # char[100]
        self.Dbip = ""          # char[60]
        self.Dbport = 0         # int
        self.DbCharacterSet = ""# char[30]
        self.Reserved = ""      # char[100]