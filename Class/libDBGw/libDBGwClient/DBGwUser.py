import sys
import os
import struct
import time
import socket
import threading

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from Class.Sql.FrDbBaseType import (
        eDB_TYPE, 
        eDB_CHARACTER_SET, 
        eQUERY_DATA_TYPE, 
        eQUERY_JOIN_POSITION
    )
except ImportError:
    print("[Error] FrDbBaseType Import Failed. Check the path.")
    
# Import definitions from DbCommon
from Class.Common.DbCommon import (
    DB_CONN_REQ, DB_CONN_RES, DB_CLOSE_REQ,
    DB_QUERY_REQ, DB_QUERY_RES, DB_BULK_QUERY_DATA,
    DB_COMMIT_REQ, DB_COMMIT_RES, DB_ROLLBACK_REQ, DB_ROLLBACK_RES,
    DB_QUERY_LONG_UPDATE_REQ, DB_QUERY_LONG_UPDATE_RES,
    QUERY_TYPE_SELECT, QUERY_TYPE_UPDATE, QUERY_TYPE_INSERT,
    QUERY_REQ_TYPE_BULK, QUERY_REQ_TYPE_RS,
    DbConnReqT, DbConnResT, DbCloseReqT,
    DbQueryReqT, DbQueryResT, DbBulkQueryDataT,
    DbCommitResT, DbRollbackResT,
    DbQueryLongUpdateReqT, DbQueryLongUpdateResT,
    MAX_DATA_SIZE
)
from Class.Common.CommType import NO_SEG, SEG_ING, SEG_END

# Import DBClientSocket
from libDBGw.libDBGwClient.DBClientSocket import DBClientSocket
from libDBGw.libDBGwClient.DBGwRecordSet import DBGwRecordSet
from Class.Sql.FrDbBaseType import *

# Mock Framework Imports (Replace with actual implementations)
try:
    from Class.Util.FrUtilMisc import FrUtilMisc
    from Class.Common.AsUtil import AsUtil
    from Class.Sql.FrDbParam import FrDbParam, FrDbRecord

except ImportError:
    class FrUtilMisc:
        @staticmethod
        def get_pid(): return os.getpid()
        @staticmethod
        def string_upper(s): return s.upper()

    class AsUtil:
        @staticmethod
        def get_host_name(): return socket.gethostname()
        @staticmethod
        def get_local_ip(): return socket.gethostbyname(socket.gethostname())
        @staticmethod
        def get_user_name(): return os.getlogin()

    class FrDbParam:
        def __init__(self):
            self.records = []
            self.col_cnt = 0
            self.row_cnt = 0
        def set_col(self, col): self.col_cnt = col
        def set_row(self, row): self.row_cnt = row
        def add_record(self, record): self.records.append(record)
        def get_value(self): return [rec.m_Values for rec in self.records]

    class FrDbRecord:
        def __init__(self):
            self.m_Col = 0
            self.m_Values = []

class QueryResult:
    """
    Helper class to hold query results.
    """
    def __init__(self):
        self.m_Result = 0
        self.m_ErrorString = ""
        self.m_ColCnt = 0
        self.m_RowCnt = 0
        self.m_Buf = []
        self.m_Param = None

    def free(self):
        self.m_Param = None
        self.m_Buf = []

class DBGwUser:
    """
    C++: DBGwUser
    Manages DB Gateway connection, query execution, and transactions.
    """
    def __init__(self):
        self.m_DBClientSocket = None
        self.m_IsOpen = False
        self.m_QueryId = 0

        self.m_DbGwIp = ""
        self.m_DbGwPort = 0
        self.m_DbUser = ""
        self.m_DbPasswd = ""
        self.m_DbName = ""
        
        self.m_Error = ""
        self.m_DBType = eDB_TYPE.eDB_ORACLE_OCI2 # Default assumption
        
        self.m_SqlLock = threading.Lock()

    def __del__(self):
        self.close_db()

    def connect(self, db_gw_ip="", db_gw_port=0, db_user="", db_passwd="", db_name=""):
        """
        C++: bool Connect(...)
        Establishes connection to the DB Gateway Server.
        """
        # Handle overload / default params logic
        if not db_gw_ip:
            # Reconnect Logic
            if self.m_DbGwIp and self.m_DbGwPort:
                return self.connect(self.m_DbGwIp, self.m_DbGwPort, self.m_DbUser, self.m_DbPasswd, self.m_DbName)
            return False

        with self.m_SqlLock:
            if self.m_IsOpen:
                self.m_Error = "Already Open"
                return False

            if self.m_DBClientSocket:
                self.m_Error = "Already Open Socket"
                return False

            self.m_IsOpen = False
            self.m_DBClientSocket = DBClientSocket(self)

            # Python socket creation is implicit in connect logic usually, but mimicking structure
            # self.m_DBClientSocket.Create() -> handled in __init__ or connect

            if not self.m_DBClientSocket.connect(db_gw_ip, db_gw_port):
                self.m_Error = f"DB GW Connect Error({self.m_DBClientSocket.get_last_error()})" # Assuming get_last_error
                self.m_DBClientSocket = None
                return False

            # Prepare Connection Request
            req = DbConnReqT()
            req.DbUser = db_user
            req.DbPasswd = db_passwd
            req.DbName = db_name
            self.get_local_info(req)

            res = DbConnResT()
            
            # AsSocketDisableGuard equivalent logic
            self.m_DBClientSocket.disable()
            
            try:
                ret = self.m_DBClientSocket.send_and_wait_packet(
                    DB_CONN_REQ, req, DB_CONN_RES, res
                )
                
                if ret > 0:
                    self.m_Error = res.m_Error
                    self.m_IsOpen = True if res.m_Result else False

                    if self.m_IsOpen:
                        self.m_DbGwIp = db_gw_ip
                        self.m_DbGwPort = db_gw_port
                        self.m_DbUser = db_user
                        self.m_DbPasswd = db_passwd
                        self.m_DbName = db_name
                        return True
                    else:
                         return False
                else:
                    self.m_DBClientSocket = None
                    return False
            finally:
                pass # Guard destruction logic handled if using 'with' context, or manual re-enable

    def get_local_info(self, req):
        """C++: bool GetLocalInfo(DB_CONN_REQ_T& ConReq)"""
        req.HostName = AsUtil.get_host_name()
        req.HostIp = AsUtil.get_local_ip()
        req.UserId = AsUtil.get_user_name()
        req.ProcPid = FrUtilMisc.get_pid()
        return True

    def close_db(self):
        """C++: bool CloseDB()"""
        if self.m_DBClientSocket:
            with self.m_SqlLock:
                req = DbCloseReqT()
                req.m_Req = 1
                self.m_DBClientSocket.send_packet(DB_CLOSE_REQ, req)
                # self.m_DBClientSocket.close() # Usually called
                self.m_DBClientSocket = None
        
        self.m_IsOpen = False
        return True

    def receive_packet(self, packet):
        pass

    def close_session(self, n_error_code):
        """C++: void CloseSession(int nErrorCode)"""
        with self.m_SqlLock:
            print(f"Disconnected db session :({self.m_DbGwIp}:{self.m_DbGwPort}...)")
            
            self.m_DBClientSocket = None
            self.m_IsOpen = False
            
            print("Try reconnect db (only 1 time)")
            ret = self.connect()
            print(f"Try reconnect {'success' if ret else 'fail'}")

    def execute_rs(self, query):
        """
        C++: DBGwRecordSet* ExecuteRs(char* Query)
        Executes a Select query and returns a RecordSet cursor.
        """
        with self.m_SqlLock:
            if not self.m_DBClientSocket:
                if not self.connect(): return None

            req = DbQueryReqT()
            req.m_QueryId = self.m_QueryId
            self.m_QueryId += 1
            req.m_QueryType = QUERY_TYPE_SELECT
            req.m_SegFlag = NO_SEG
            req.m_QueryReqType = QUERY_REQ_TYPE_RS
            req.m_Query = query

            res = DbQueryResT()
            
            self.m_DBClientSocket.disable()
            
            if self.m_DBClientSocket.send_and_wait_packet(
                DB_QUERY_REQ, req, DB_QUERY_RES, res
            ) > 0:
                rs = DBGwRecordSet(self)
                rs.m_IsValid = True if res.m_Result else False
                rs.m_Query = query
                rs.m_QueryId = res.m_QueryId
                
                if rs.m_IsValid:
                    rs.set_col(res.m_ColCnt)
                else:
                    rs.m_Error = res.m_Error
                
                return rs
            else:
                return None

    def sql_query(self, query, result, addition_text=""):
        """
        C++: bool SqlQuery(...)
        Executes a query and fetches results (Bulk).
        Handles Long Query Segmentation.
        """
        with self.m_SqlLock:
            if not self.m_DBClientSocket:
                if not self.connect():
                    result.m_ErrorString = self.m_Error
                    return False

            # Check Query Type (INSERT/UPDATE/DELETE handled separately)
            tmp_query = FrUtilMisc.string_upper(query.strip())
            if tmp_query.startswith("INSERT") or tmp_query.startswith("UPDATE") or tmp_query.startswith("DELETE"):
                res = self.execute_no_lock(query, False)
                if res:
                    result.m_Result = 1
                else:
                    result.m_Result = 0
                    result.m_ErrorString = self.get_error()
                return res

            # Select Query Preparation
            req = DbQueryReqT()
            req.m_QueryId = self.m_QueryId
            self.m_QueryId += 1
            req.m_QueryType = QUERY_TYPE_SELECT
            req.m_SegFlag = NO_SEG
            req.m_QueryReqType = QUERY_REQ_TYPE_BULK

            # Long Query Handling
            query_len = len(query)
            if query_len > MAX_DATA_SIZE - 1:
                # Segmented Sending
                offset = 0
                cnt = 0
                while offset < query_len:
                    chunk_size = min(MAX_DATA_SIZE - 1, query_len - offset)
                    req.m_Query = query[offset : offset + chunk_size]
                    
                    offset += chunk_size
                    
                    if offset < query_len:
                        req.m_SegFlag = SEG_ING
                        print(f"### long query send : {cnt}")
                        self.m_DBClientSocket.send_packet(DB_QUERY_REQ, req)
                        cnt += 1
                    else:
                        req.m_SegFlag = SEG_END
                        # Last chunk is sent via SendAndWait below
                        break
            else:
                req.m_Query = query

            res = DbQueryResT()
            self.m_DBClientSocket.disable()

            if self.m_DBClientSocket.send_and_wait_packet(
                DB_QUERY_REQ, req, DB_QUERY_RES, res
            ) > 0:
                result.m_Result = res.m_Result
                result.m_ErrorString = res.m_Error
                self.m_Error = res.m_Error
                
                if res.m_Result == 1:
                    result.m_ColCnt = res.m_ColCnt
                    result.m_RowCnt = res.m_RowCnt
                    
                    if result.m_RowCnt > 0:
                        # Receive Bulk Data
                        data_buf = bytearray()
                        bulk_data = DbBulkQueryDataT()
                        
                        while True:
                            # Reset struct
                            bulk_data = DbBulkQueryDataT() 
                            if self.m_DBClientSocket.wait_packet(DB_BULK_QUERY_DATA, bulk_data) < 0:
                                return False
                            
                            # Assuming m_Data comes as bytes
                            data_buf.extend(bulk_data.m_Data)
                            
                            if bulk_data.m_SegFlag != SEG_ING:
                                break
                        
                        if self.decode_bulk_data(result, data_buf):
                            return True
                        return False
                    return True
                return False
            return False

    def decode_bulk_data(self, result, data_buf):
        """
        C++: bool DecodeBulkData(...)
        Decodes the binary result stream into FrDbParam/FrDbRecord structures.
        """
        result.m_Param = FrDbParam()
        result.m_Param.set_col(result.m_ColCnt)
        
        offset = 0
        buf_len = len(data_buf)
        
        for _ in range(result.m_RowCnt):
            record = FrDbRecord()
            record.m_Col = result.m_ColCnt
            record.m_Values = [] # List of strings/bytes
            
            for _ in range(result.m_ColCnt):
                # Read Length (4 bytes)
                if offset + 4 > buf_len: return False
                
                # ntohl is implicitly handled if data was packed with big-endian
                # Here we assume standard packing
                col_len = struct.unpack('>I', data_buf[offset:offset+4])[0]
                offset += 4
                
                # Read Data
                if offset + col_len > buf_len: return False
                val = data_buf[offset : offset + col_len].decode('utf-8', errors='ignore') # Or bytes
                record.m_Values.append(val)
                offset += col_len
                
            result.m_Param.add_record(record)
            
        result.m_Param.set_row(result.m_RowCnt)
        result.m_Buf = result.m_Param.get_value()
        return True

    def decode_rs_data(self, col_cnt, param, data_buf):
        """
        C++: frDbRecord* DecodeRsData(...)
        Decodes a single row for RecordSet.
        """
        offset = 0
        buf_len = len(data_buf)
        
        record = FrDbRecord()
        record.m_Col = col_cnt
        record.m_Values = []
        
        for _ in range(col_cnt):
            if offset + 4 > buf_len: return None
            col_len = struct.unpack('>I', data_buf[offset:offset+4])[0]
            offset += 4
            
            if offset + col_len > buf_len: return None
            val = data_buf[offset : offset + col_len].decode('utf-8', errors='ignore')
            record.m_Values.append(val)
            offset += col_len
            
        param.add_record(record)
        return record

    def execute_no_lock(self, query, auto_commit):
        """
        C++: bool ExecuteNoLock(...)
        """
        if not self.m_DBClientSocket:
            if not self.connect(): return False

        req = DbQueryReqT()
        req.m_QueryId = self.m_QueryId
        self.m_QueryId += 1
        req.m_QueryType = QUERY_TYPE_UPDATE # UPDATE/INSERT
        req.m_SegFlag = NO_SEG
        req.m_Commit = 1 if auto_commit else 2
        req.m_Query = query
        
        res = DbQueryResT()
        self.m_DBClientSocket.disable()
        
        if self.m_DBClientSocket.send_and_wait_packet(
            DB_QUERY_REQ, req, DB_QUERY_RES, res
        ) > 0:
            self.m_Error = res.m_Error
            return True if res.m_Result else False
        return False

    def execute(self, query, auto_commit):
        with self.m_SqlLock:
            return self.execute_no_lock(query, auto_commit)

    def commit(self):
        with self.m_SqlLock:
            if not self.m_DBClientSocket:
                if not self.connect(): return False
            
            res = DbCommitResT()
            self.m_DBClientSocket.disable()
            
            if self.m_DBClientSocket.send_and_wait_packet(
                DB_COMMIT_REQ, None, DB_COMMIT_RES, res
            ) > 0:
                self.m_Error = res.m_Error
                return True if res.m_Result else False
            return False

    def rollback(self):
        with self.m_SqlLock:
            if not self.m_DBClientSocket:
                if not self.connect(): return False
            
            res = DbRollbackResT()
            self.m_DBClientSocket.disable()
            
            if self.m_DBClientSocket.send_and_wait_packet(
                DB_ROLLBACK_REQ, None, DB_ROLLBACK_RES, res
            ) > 0:
                self.m_Error = res.m_Error
                return True if res.m_Result else False
            return False

    def update_long(self, table, field, value, where):
        """
        C++: bool UpdateLong(...)
        Handles CLOB/BLOB updates by sending segmented data.
        """
        with self.m_SqlLock:
            if not self.m_DBClientSocket:
                if not self.connect(): return False
            
            req = DbQueryLongUpdateReqT()
            req.Table = table
            req.Field = field
            
            # Pack Where & Value into binary
            # Structure: [WhereLen][Where][ValueLen][Value]
            packed_data = bytearray()
            
            where_bytes = where.encode('utf-8')
            value_bytes = value.encode('utf-8')
            
            packed_data.extend(struct.pack('>I', len(where_bytes)))
            packed_data.extend(where_bytes)
            packed_data.extend(struct.pack('>I', len(value_bytes)))
            packed_data.extend(value_bytes)
            
            total_size = len(packed_data)
            req.m_DataSize = total_size
            
            res = DbQueryLongUpdateResT()
            self.m_DBClientSocket.disable()
            
            # Segmented Sending Loop
            offset = 0
            while offset < total_size:
                # Clear m_Data logic handled by creating new req/assigning
                # In Python we just overwrite the field
                
                remaining = total_size - offset
                
                if remaining > MAX_DATA_SIZE:
                    req.m_SegFlag = SEG_ING
                    req.m_Data = packed_data[offset : offset + MAX_DATA_SIZE]
                    offset += MAX_DATA_SIZE
                    
                    self.m_DBClientSocket.send_packet(DB_QUERY_LONG_UPDATE_REQ, req)
                else:
                    req.m_SegFlag = SEG_END
                    req.m_Data = packed_data[offset:]
                    offset += remaining
                    
                    self.m_DBClientSocket.send_and_wait_packet(
                        DB_QUERY_LONG_UPDATE_REQ, req, DB_QUERY_LONG_UPDATE_RES, res
                    )
            
            self.m_Error = res.m_Error
            return True if res.m_Result else False

    def get_error(self):
        return self.m_Error

    def make_query_insert(self, data_type, data):
        """
        C++: string MakeQueryInsert(eQUERY_DATA_TYPE DataType, string Data)
        """
        out_query = ""
        
        # [변경] eQUERY_DATA_TYPE Enum 사용
        if data_type == eQUERY_DATA_TYPE.eDATE_TYPE:
            # [변경] eDB_TYPE Enum 비교
            if self.m_DBType in (eDB_TYPE.eDB_ORACLE_OCI2, eDB_TYPE.eDB_ORACLE_OCI_OLD):
                out_query = f"TO_DATE('{data}', 'YYYY/MM/DD HH24:MI:SS')"
            elif self.m_DBType == eDB_TYPE.eDB_MYSQL:
                out_query = f"STR_TO_DATE('{data}', '%Y/%m/%d %H:%i:%s')"
            elif self.m_DBType == eDB_TYPE.eDB_MSSQL_ODBC:
                out_query = f"'{data}'"
        
        elif data_type == eQUERY_DATA_TYPE.eSYSDATE:
            if self.m_DBType in (eDB_TYPE.eDB_ORACLE_OCI2, eDB_TYPE.eDB_ORACLE_OCI_OLD):
                out_query = "SYSDATE"
            elif self.m_DBType == eDB_TYPE.eDB_MYSQL:
                out_query = "sysdate()"
            elif self.m_DBType == eDB_TYPE.eDB_MSSQL_ODBC:
                out_query = "not impl"

        if not out_query:
            out_query = "undefined dbtype or datatype"
            
        return out_query
    
    def make_query_select(self, data_type, field):
        """
        C++: string MakeQuerySelect(eQUERY_DATA_TYPE DataType, string Field)
        """
        out_query = ""

        # [변경] Enum 사용
        if data_type == eQUERY_DATA_TYPE.eDATE_TYPE:
            if self.m_DBType in (eDB_TYPE.eDB_ORACLE_OCI2, eDB_TYPE.eDB_ORACLE_OCI_OLD):
                out_query = f"TO_CHAR({field}, 'YYYY/MM/DD HH24:MI:SS')"
            elif self.m_DBType == eDB_TYPE.eDB_MYSQL:
                out_query = f"DATE_FORMAT({field}, '%Y/%m/%d %H:%i:%s')"
            elif self.m_DBType == eDB_TYPE.eDB_MSSQL_ODBC:
                out_query = field
        
        elif data_type == eQUERY_DATA_TYPE.eSYSDATE:
            if self.m_DBType in (eDB_TYPE.eDB_ORACLE_OCI2, eDB_TYPE.eDB_ORACLE_OCI_OLD):
                out_query = "SYSDATE"
            elif self.m_DBType == eDB_TYPE.eDB_MYSQL:
                out_query = "sysdate()"
            elif self.m_DBType == eDB_TYPE.eDB_MSSQL_ODBC:
                out_query = "not impl"

        if not out_query:
            out_query = "undefined dbtype or datatype"

        return out_query
    
    def is_exist_table(self, table_name):
        """
        C++: bool IsExistTable(string TableName)
        """
        if not self.m_DBClientSocket:
            if not self.connect():
                return False

        query = ""
        # [변경] getter를 사용하거나 직접 접근
        db_type = self.m_DBType 

        # [변경] Enum 사용
        if db_type in (eDB_TYPE.eDB_ORACLE_OCI_OLD, eDB_TYPE.eDB_ORACLE_OCI2, eDB_TYPE.eDB_ORACLE_ODBC):
            query = f"SELECT COUNT(*) FROM TAB WHERE TNAME = '{table_name}'"
            
        elif db_type in (eDB_TYPE.eDB_MSSQL_ODBC, eDB_TYPE.eDB_MYSQL):
            query = f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = '{table_name}'"
            
        else:
            return False

        # (이하 쿼리 실행 및 결과 처리 로직은 동일)
        result = QueryResult()
        if not self.sql_query(query, result):
            return False

        is_table = 0
        try:
            if result.m_Buf and len(result.m_Buf) > 0 and len(result.m_Buf[0]) > 0:
                is_table = int(result.m_Buf[0][0])
        except (ValueError, IndexError, TypeError):
            is_table = 0

        self.free(result)
        return True if is_table > 0 else False

    def is_connect(self):
        """
        C++: bool IsConnect()
        """
        if self.m_DBClientSocket:
            return self.m_DBClientSocket.is_connect() # Assuming Socket wrapper has is_connect
        return False

    def get_db_type(self):
        """
        C++: eDB_TYPE GetDbType()
        """
        return self.m_DBType