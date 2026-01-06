import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import AS_SEGFLAG from CommType
# (Assuming CommType defines AsSegFlag class or similar structure)
try:
    from Class.Common.CommType import AsSegFlag
except ImportError:
    # Fallback if CommType is not fully defined yet
    class AsSegFlag:
        def __init__(self):
            self.type = 0
            self.seq = 0
            self.len = 0

# -------------------------------------------------------
# Constants & Macros
# -------------------------------------------------------
MAX_ERROR_SIZE = 2048
MAX_DATA_SIZE = 4000

DB_CONN_REQ = 60001
DB_CONN_RES = 60002

DB_CLOSE_REQ = 60003
DB_CLOSE_RES = 60004

DB_QUERY_REQ = 60011
DB_QUERY_RES = 60012

DB_BULK_QUERY_DATA = 60013
DB_RS_QUERY_DATA = 60014

DB_QUERY_LONG_UPDATE_REQ = 60015
DB_QUERY_LONG_UPDATE_RES = 60016

DB_RS_MOVE_NEXT_REQ = 60021

DB_RS_CLOSE_REQ = 60031

DB_COMMIT_REQ = 60032
DB_COMMIT_RES = 60033

DB_ROLLBACK_REQ = 60034
DB_ROLLBACK_RES = 60035

QUERY_TYPE_SELECT = 0
QUERY_TYPE_UPDATE = 1
QUERY_TYPE_INSERT = 2

QUERY_REQ_TYPE_BULK = 0
QUERY_REQ_TYPE_RS = 1

DEF_BUF_SIZE = 2048000 # 2M

# MFC_ERROR Macro is ignored in Python logic

# -------------------------------------------------------
# Data Structures (Structs -> Classes)
# -------------------------------------------------------

class DbConnReqT:
    """
    C++: typedef struct { char DbUser[40]; ... } DB_CONN_REQ_T;
    """
    def __init__(self):
        self.DbUser = ""      # char[40]
        self.DbPasswd = ""    # char[40]
        self.DbName = ""      # char[40]
        self.UserId = ""      # char[40]
        self.HostName = ""    # char[40]
        self.HostIp = ""      # char[40]
        self.ProcPid = 0      # int

class DbConnResT:
    """
    C++: typedef struct { short int m_Result; char m_Error[MAX_ERROR_SIZE]; } DB_CONN_RES_T;
    """
    def __init__(self):
        self.m_Result = 0     # short int
        self.m_Error = ""     # char[MAX_ERROR_SIZE]

class DbCloseReqT:
    """
    C++: typedef struct { int m_Req; } DB_CLOSE_REQ_T;
    """
    def __init__(self):
        self.m_Req = 0        # int

class DbQueryReqT:
    """
    C++: typedef struct { int m_QueryId; ... } DB_QUERY_REQ_T;
    """
    def __init__(self):
        self.m_QueryId = 0       # int
        self.m_QueryType = 0     # int (1:select, 2:update, insert)
        self.m_QueryReqType = 0  # int (1:bulk, 2:recordset)
        self.m_Commit = 0        # int (1:commit, 2:nocommit)
        self.m_SegFlag = AsSegFlag() # AS_SEGFLAG
        self.m_Query = ""        # char[MAX_DATA_SIZE]

class DbQueryResT:
    """
    C++: typedef struct { int m_QueryId; ... } DB_QUERY_RES_T;
    """
    def __init__(self):
        self.m_QueryId = 0    # int
        self.m_ColCnt = 0     # int
        self.m_RowCnt = 0     # int
        self.m_Result = 0     # short int
        self.m_DataSize = 0   # int
        self.m_Error = ""     # char[MAX_ERROR_SIZE]

class DbBulkQueryDataT:
    """
    C++: typedef struct { int m_QueryId; AS_SEGFLAG m_SegFlag; char m_Data[MAX_DATA_SIZE]; } DB_BULK_QUERY_DATA_T;
    """
    def __init__(self):
        self.m_QueryId = 0           # int
        self.m_SegFlag = AsSegFlag() # AS_SEGFLAG
        self.m_Data = ""             # char[MAX_DATA_SIZE]

class DbRsQueryDataT:
    """
    C++: typedef struct { int m_QueryId; int m_CurRow; ... } DB_RS_QUERY_DATA_T;
    """
    def __init__(self):
        self.m_QueryId = 0           # int
        self.m_CurRow = 0            # int
        self.m_SegFlag = AsSegFlag() # AS_SEGFLAG
        self.m_Size = 0              # int (if -1: error, if -2: eor)
        self.m_Data = ""             # char[MAX_DATA_SIZE]

class DbRsMoveNextReqT:
    """
    C++: typedef struct { int m_QueryId; int m_Reserved; } DB_RS_MOVE_NEXT_REQ_T;
    """
    def __init__(self):
        self.m_QueryId = 0    # int
        self.m_Reserved = 0   # int

class DbRsCloseReqT:
    """
    C++: typedef struct { int m_QueryId; int m_Reserved; } DB_RS_CLOSE_REQ_T;
    """
    def __init__(self):
        self.m_QueryId = 0    # int
        self.m_Reserved = 0   # int

class DbCommitResT:
    """
    C++: typedef struct { short int m_Result; char m_Error[MAX_ERROR_SIZE]; } DB_COMMIT_RES_T;
    """
    def __init__(self):
        self.m_Result = 0     # short int
        self.m_Error = ""     # char[MAX_ERROR_SIZE]

class DbRollbackResT:
    """
    C++: typedef struct { short int m_Result; char m_Error[MAX_ERROR_SIZE]; } DB_ROLLBACK_RES_T;
    """
    def __init__(self):
        self.m_Result = 0     # short int
        self.m_Error = ""     # char[MAX_ERROR_SIZE]

class DbQueryLongUpdateReqT:
    """
    C++: typedef struct { char Table[36]; char Field[40]; ... } DB_QUERY_LONG_UPDATE_REQ_T;
    """
    def __init__(self):
        self.Table = ""              # char[36]
        self.Field = ""              # char[40]
        self.m_SegFlag = AsSegFlag() # AS_SEGFLAG
        self.m_DataSize = 0          # int
        self.m_Data = ""             # char[MAX_DATA_SIZE]

class DbQueryLongUpdateResT:
    """
    C++: typedef struct { short int m_Result; char m_Error[MAX_ERROR_SIZE]; } DB_QUERY_LONG_UPDATE_RES_T;
    """
    def __init__(self):
        self.m_Result = 0     # short int
        self.m_Error = ""     # char[MAX_ERROR_SIZE]