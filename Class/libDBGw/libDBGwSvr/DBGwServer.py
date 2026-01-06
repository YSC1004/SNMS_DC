import sys
import os
import struct
import time
import socket

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import definitions from DbCommon
from Class.Common.DbCommon import (
    DB_CONN_REQ, DB_CONN_RES, DB_QUERY_REQ, DB_QUERY_RES,
    DB_CLOSE_REQ, DB_RS_MOVE_NEXT_REQ, DB_RS_CLOSE_REQ,
    DB_COMMIT_REQ, DB_COMMIT_RES, DB_ROLLBACK_REQ, DB_ROLLBACK_RES,
    DB_QUERY_LONG_UPDATE_REQ, DB_QUERY_LONG_UPDATE_RES,
    DB_BULK_QUERY_DATA, DB_RS_QUERY_DATA,
    QUERY_TYPE_SELECT, QUERY_TYPE_UPDATE, QUERY_TYPE_INSERT,
    QUERY_REQ_TYPE_BULK, QUERY_REQ_TYPE_RS,
    MAX_ERROR_SIZE, MAX_DATA_SIZE, DEF_BUF_SIZE
)

# Import CommType for SegFlag
from Class.Common.CommType import NO_SEG, SEG_ING, SEG_END

# Mock Imports for External Frameworks (fr)
# These should be replaced with actual implementations (e.g., pymysql wrappers)
try:
    from Class.Sql.FrDbSession import FrDbSession, QueryResult
    from Class.Util.FrUtilMisc import FrUtilMisc
    from Class.Event.FrLogger import FrLogger
except ImportError:
    # Placeholder classes for compilation
    class FrDbSession:
        @staticmethod
        def get_instance(): return FrDbSession()
        def connect(self, u, p, n, ip, port): return True
        def get_error(self): return "DB Error"
        def sql_query(self, query, result): pass
        def execute_rs(self, query): return None
        def execute(self, query, commit): return True
        def free(self, result): pass
        def commit(self): return True
        def rollback(self): return True
        def update_long(self, t, f, v, w): return True

    class QueryResult:
        def __init__(self):
            self.m_Result = 0
            self.m_RowCnt = 0
            self.m_ColCnt = 0
            self.m_ErrorString = ""
            self.m_Buf = [] # List of Lists
            self.m_Param = None # Metadata

    class FrUtilMisc:
        @staticmethod
        def get_pid(): return os.getpid()
        @staticmethod
        def string_replace(s, old, new): return s.replace(old, new)
    
    class FrLogger:
        @staticmethod
        def open(path): print(f"[Log Open] {path}")

class FrDbRecordSetMap:
    """
    C++: frDbRecordSetMap
    Manages active RecordSets (Cursors) for RS-type queries.
    """
    def __init__(self):
        self.m_Map = {} # Dict[int, FrDbRecordSet]

    def __del__(self):
        self.clear()

    def clear(self):
        # In Python, clearing the dict allows GC to collect the objects
        # If RecordSets need explicit close, iterate and close them here.
        self.m_Map.clear()

    def insert(self, query_id, r_set):
        self.m_Map[query_id] = r_set

    def find(self, query_id):
        return self.m_Map.get(query_id)

    def remove(self, query_id):
        if query_id in self.m_Map:
            del self.m_Map[query_id]
            return True
        return False

class DBGwServer:
    """
    C++: DBGwServer
    Core Database Gateway Server logic.
    Handles DB connections, query execution, result packing, and segmentation.
    """
    def __init__(self, session, db_kind, default_db_user, default_db_passwd, default_db_name):
        self.m_DbType = db_kind
        self.m_DBServerSession = session
        self.m_DbSession = None # FrDbSession instance

        self.m_DbUser = default_db_user
        self.m_DbPasswd = default_db_passwd
        self.m_DbName = default_db_name
        self.m_LogFile = ""
        
        self.m_DbRecordSetMap = FrDbRecordSetMap()

    def __del__(self):
        """
        C++: ~DBGwServer()
        """
        if self.m_DbSession:
            # self.m_DbSession.close() # Explicit close if needed
            self.m_DbSession = None

    def receive_packet(self, packet):
        """
        C++: void ReceivePacket(PACKET_T* Packet)
        Dispatcher for incoming packets.
        """
        msg_id = packet.msgId
        msg = packet.msg

        if msg_id == DB_CONN_REQ:
            self.db_conn_req(msg)
        elif msg_id == DB_QUERY_REQ:
            self.db_query_req(msg)
        elif msg_id == DB_CLOSE_REQ:
            self.db_close_req(msg)
        elif msg_id == DB_RS_MOVE_NEXT_REQ:
            self.db_rs_move_next_req(msg)
        elif msg_id == DB_RS_CLOSE_REQ:
            self.db_rs_close_req(msg)
        elif msg_id == DB_COMMIT_REQ:
            self.db_commit_req()
        elif msg_id == DB_ROLLBACK_REQ:
            self.db_rollback_req()
        elif msg_id == DB_QUERY_LONG_UPDATE_REQ:
            self.db_query_long_update_req(msg)
        else:
            pass

    def db_conn_req(self, req):
        """
        C++: void DbConnReq(DB_CONN_REQ_T* Req)
        Handles DB Connection Request.
        """
        # Logging Setup
        if self.m_DBServerSession.m_IsLoggingMode:
            host_ip = req.HostIp.replace(".", "_")
            log_file = f"{self.m_DBServerSession.m_LogDir}/DBGW_{FrUtilMisc.get_pid()}_{req.HostName}_{host_ip}_{req.ProcPid}.log"
            
            FrLogger.open(log_file)
            self.m_LogFile = log_file
            print(f"PID : {FrUtilMisc.get_pid()}[{self.m_LogFile}]")
            
            self.m_DBServerSession.m_IsLoggingMode = False

        print(f"Request connect db({req.DbUser}/{req.DbPasswd}@{req.DbName})")

        # Get DB Session Instance
        # Assuming FrDbSession singleton/factory pattern matches C++
        self.m_DbSession = FrDbSession.get_instance()

        from Class.Common.DbCommon import DbConnResT
        res = DbConnResT()
        result = False
        
        # Connection Logic
        # C++ logic checks if Req fields are empty to use Default values, else use Req values
        
        target_user = req.DbUser if req.DbUser else self.m_DbUser
        target_passwd = req.DbPasswd if req.DbPasswd else self.m_DbPasswd
        target_name = req.DbName if req.DbName else self.m_DbName
        
        # Hardcoded IP/Port in C++ snippet (192.168.1.4:3306), applying here
        if target_user and target_passwd and target_name:
             result = self.m_DbSession.connect(target_user, target_passwd, target_name, "192.168.1.4", 3306)
             if not result:
                 res.m_Error = self.m_DbSession.get_error()[:MAX_ERROR_SIZE]
        else:
            res.m_Error = f"invalid connect info.({req.DbUser}{req.DbPasswd}@{req.DbName})"
            print(res.m_Error)

        res.m_Result = 1 if result else 0
        
        self.m_DBServerSession.send_packet(DB_CONN_RES, res)

    def db_query_req(self, req):
        """
        C++: void DbQueryReq(DB_QUERY_REQ_T* Req)
        Handles SQL Query Request (Select, Insert, Update).
        Supports segmented (Long) queries.
        """
        from Class.Common.DbCommon import DbQueryResT
        res = DbQueryResT()
        res.m_Result = 0
        
        ret = True
        long_query = ""

        # 1. Handle Segmented Query Assembly
        if req.m_SegFlag == SEG_ING:
            cnt = 0
            long_query = req.m_Query
            cnt += 1
            print(f"### Start Long query : {cnt} [{time.ctime()}]")
            
            while True:
                # Wait for next packet (Blocking)
                # Assuming session has wait_packet method
                tmp_req = self.m_DBServerSession.wait_packet(DB_QUERY_REQ) 
                
                if tmp_req:
                    cnt += 1
                    print(f"### Wait Long query ok : {cnt} [{time.ctime()}]")
                    long_query += tmp_req.m_Query
                    
                    if tmp_req.m_SegFlag == SEG_END:
                        print(f"### Wait Long query end : {cnt} [{time.ctime()}]")
                        break
                else:
                    print("### Wait Long query error")
                    ret = False
                    break
        
        # 2. Execute Query
        if ret:
            current_query = long_query if long_query else req.m_Query
            print(f"query : [{time.ctime()}][{current_query}]")

            if req.m_QueryType == QUERY_TYPE_SELECT:
                if req.m_QueryReqType == QUERY_REQ_TYPE_BULK:
                    self.db_query_req_select_bulk(req, current_query)
                    return
                elif req.m_QueryReqType == QUERY_REQ_TYPE_RS:
                    self.db_query_req_select_rs(req, current_query)
                    return
                else:
                    res.m_Error = "Unknown DbQueryReq Type"
            
            elif req.m_QueryType in (QUERY_TYPE_UPDATE, QUERY_TYPE_INSERT):
                self.db_query_req_insert(req, current_query)
                return
            else:
                 res.m_Error = "Unknown DbQueryReq Type"
        else:
            res.m_Error = "Segment Query isn't terminated well"
            
        self.m_DBServerSession.send_packet(DB_QUERY_RES, res)

    def db_query_req_select_bulk(self, req, query_str):
        """
        C++: void DbQueryReqSelectBulk(...)
        Executes Select query and sends ALL results in bulk chunks.
        """
        from Class.Sql.FrDbSession import QueryResult
        result = QueryResult()
        
        start_time = time.time()
        self.m_DbSession.sql_query(query_str, result)
        elapsed = time.time() - start_time
        
        print(f"query end form DB : elapse[{elapsed:.2f} sec] rowcnt[{result.m_RowCnt}]")
        
        from Class.Common.DbCommon import DbQueryResT
        res = DbQueryResT()
        res.m_Result = result.m_Result
        res.m_QueryId = req.m_QueryId
        res.m_ColCnt = result.m_ColCnt
        res.m_RowCnt = result.m_RowCnt
        
        print(f"query end form DB : result = [{res.m_Result}], rowcnt[{result.m_RowCnt}]")

        if res.m_Result == 0:
            res.m_Error = result.m_ErrorString[:MAX_ERROR_SIZE]

        if res.m_Result > 0 and res.m_RowCnt > 0:
            # Send Data (Header + Body)
            self.encode_bulk_data_send(req.m_QueryId, res, result)
        else:
            # Send Header Only (Error or Empty)
            self.m_DBServerSession.send_packet(DB_QUERY_RES, res)

        self.m_DbSession.free(result)

    def db_query_req_select_rs(self, req, query_str):
        """
        C++: void DbQueryReqSelectRs(...)
        Executes Select query and stores RecordSet for creating a cursor.
        """
        r_set = self.m_DbSession.execute_rs(query_str)
        
        from Class.Common.DbCommon import DbQueryResT
        res = DbQueryResT()
        res.m_Result = 1 if r_set and r_set.is_valid() else 0
        res.m_QueryId = req.m_QueryId
        
        if r_set and r_set.is_valid():
            res.m_ColCnt = r_set.get_col()
            self.m_DbRecordSetMap.insert(req.m_QueryId, r_set)
        else:
            if r_set:
                res.m_Error = r_set.m_Error[:MAX_ERROR_SIZE]
                # delete r_set (handled by GC/Framework)
        
        self.m_DBServerSession.send_packet(DB_QUERY_RES, res)

    def db_query_req_insert(self, req, query_str):
        """
        C++: void DbQueryReqInsert(...)
        Handles Insert/Update execution.
        """
        from Class.Common.DbCommon import DbQueryResT
        res = DbQueryResT()
        
        is_commit = True if req.m_Commit == 1 else False
        result = self.m_DbSession.execute(query_str, is_commit)
        
        res.m_Result = 1 if result else 0
        
        if not result:
            res.m_Error = self.m_DbSession.get_error()[:MAX_ERROR_SIZE]
            
        self.m_DBServerSession.send_packet(DB_QUERY_RES, res)
        print(f"End sending query result to client : [{time.ctime()}]")

    def encode_bulk_data_send(self, query_id, query_res, result):
        """
        C++: void EncodeBulkDataSend(...)
        Serializes the DB result set into a binary stream and sends it in chunks.
        Format: [Col1Len][Col1Data][Col2Len][Col2Data]... (Row by Row)
        Lengths are Big-Endian 4-byte integers (htonl).
        """
        # 1. Serialize All Data
        data_buffer = bytearray()
        
        # Assuming result.m_Param.GetRecordHead() logic is abstracted in result structure
        # In Python, we might iterate over result.m_Buf (Rows)
        # We need metadata for column sizes? 
        # C++ uses `rec->m_ColSize[col]`.
        # Assuming `result.m_Buf` contains raw bytes or strings.
        
        for row_idx in range(result.m_RowCnt):
            row_data = result.m_Buf[row_idx] # List of columns
            
            for col_idx in range(result.m_ColCnt):
                val = row_data[col_idx]
                
                # Convert value to bytes if needed
                if isinstance(val, str):
                    val_bytes = val.encode('utf-8') # Or specific DB encoding
                elif isinstance(val, bytes):
                    val_bytes = val
                else:
                    val_bytes = str(val).encode('utf-8')
                
                # Size + Data
                size = len(val_bytes)
                # htonl (Big Endian)
                data_buffer.extend(struct.pack('>I', size))
                data_buffer.extend(val_bytes)
        
        total_size = len(data_buffer)
        
        # 2. Send Header (QUERY_RES) with DataSize
        query_res.m_DataSize = total_size
        self.m_DBServerSession.send_packet(DB_QUERY_RES, query_res)
        
        # 3. Send Body (BULK_QUERY_DATA) in Chunks
        from Class.Common.DbCommon import DbBulkQueryDataT
        
        offset = 0
        while offset < total_size:
            chunk_req = DbBulkQueryDataT()
            chunk_req.m_QueryId = query_id
            
            remaining = total_size - offset
            if remaining > MAX_DATA_SIZE:
                chunk_req.m_SegFlag = SEG_ING
                send_size = MAX_DATA_SIZE
            else:
                chunk_req.m_SegFlag = SEG_END
                send_size = remaining
            
            # Copy slice to m_Data (which accepts bytes/string)
            chunk_req.m_Data = data_buffer[offset : offset + send_size]
            
            self.m_DBServerSession.send_packet(DB_BULK_QUERY_DATA, chunk_req)
            
            offset += send_size

    def db_rs_move_next_req(self, req):
        """
        C++: void DbRsMoveNextReq(DB_RS_MOVE_NEXT_REQ_T* Req)
        Fetches next row from RecordSet and sends it.
        """
        from Class.Common.DbCommon import DbRsQueryDataT
        
        r_set = self.m_DbRecordSetMap.find(req.m_QueryId)
        
        if not r_set:
            res = DbRsQueryDataT()
            res.m_Size = -1 # Error
            res.m_Data = f"Can't find recordset : {req.m_QueryId}".encode('utf-8')
            res.m_QueryId = req.m_QueryId
            res.m_SegFlag = NO_SEG
            self.m_DBServerSession.send_packet(DB_RS_QUERY_DATA, res)
            return

        record = r_set.move_next()
        self.encode_rs_data_send(req.m_QueryId, r_set.get_row(), record)

    def encode_rs_data_send(self, query_id, row_cnt, record):
        """
        C++: void EncodeRsDataSend(...)
        Serializes a single row (Record) and sends it.
        """
        from Class.Common.DbCommon import DbRsQueryDataT
        
        if not record:
            # End of RecordSet
            res = DbRsQueryDataT()
            res.m_QueryId = query_id
            res.m_Size = -2 # EOR
            res.m_CurRow = row_cnt
            self.m_DBServerSession.send_packet(DB_RS_QUERY_DATA, res)
            return

        # Serialize Record
        data_buffer = bytearray()
        
        # Iterate record columns
        # Assuming record has m_Values (list of bytes) and m_ColSize
        for col_idx in range(record.m_Col):
            val = record.m_Values[col_idx]
            # Ensure val is bytes
            if isinstance(val, str): val = val.encode('utf-8')
            
            size = len(val)
            data_buffer.extend(struct.pack('>I', size))
            data_buffer.extend(val)
            
        total_size = len(data_buffer)
        offset = 0
        
        # Send in Chunks
        while offset < total_size:
            res = DbRsQueryDataT()
            res.m_QueryId = query_id
            res.m_CurRow = row_cnt
            
            remaining = total_size - offset
            
            if remaining > MAX_DATA_SIZE:
                res.m_SegFlag = SEG_ING
                res.m_Data = data_buffer[offset : offset + MAX_DATA_SIZE]
                res.m_Size = MAX_DATA_SIZE
                send_len = MAX_DATA_SIZE
            else:
                res.m_SegFlag = SEG_END
                res.m_Data = data_buffer[offset : offset + remaining]
                res.m_Size = remaining
                send_len = remaining
                
            self.m_DBServerSession.send_packet(DB_RS_QUERY_DATA, res)
            offset += send_len

    def db_rs_close_req(self, req):
        self.m_DbRecordSetMap.remove(req.m_QueryId)

    def db_close_req(self, req):
        pass

    def db_commit_req(self):
        from Class.Common.DbCommon import DbCommitResT
        res = DbCommitResT()
        res.m_Result = 1 if self.m_DbSession.commit() else 0
        self.m_DBServerSession.send_packet(DB_COMMIT_RES, res)

    def db_rollback_req(self):
        from Class.Common.DbCommon import DbRollbackResT
        res = DbRollbackResT()
        res.m_Result = 1 if self.m_DbSession.rollback() else 0
        self.m_DBServerSession.send_packet(DB_ROLLBACK_RES, res)

    def db_query_long_update_req(self, req):
        """
        C++: void DbQueryLongUpdateReq(...)
        Handles Long Update requests by assembling segmented data.
        """
        from Class.Common.DbCommon import DbQueryLongUpdateReqT
        
        final_data = bytearray()
        
        if req.m_SegFlag == SEG_ING:
            # First chunk
            final_data.extend(req.m_Data) # Assuming m_Data is bytes
            
            while True:
                tmp_req = self.m_DBServerSession.wait_packet(DB_QUERY_LONG_UPDATE_REQ)
                if tmp_req:
                     final_data.extend(tmp_req.m_Data)
                     if tmp_req.m_SegFlag != SEG_ING:
                         break
            
            self.db_query_long_update(req.Table, req.Field, final_data)
        else:
            self.db_query_long_update(req.Table, req.Field, req.m_Data)

    def db_query_long_update(self, table, field, data):
        """
        C++: void DbQueryLongUpdate(...)
        Decodes the binary 'Where' and 'Value' clauses and executes UpdateLong.
        Format: [WhereLen(4)][WhereStr][ValueLen(4)][ValueStr]
        """
        offset = 0
        
        # Decode Where Length
        if len(data) < 4: return # Error
        where_len = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        
        # Decode Where String
        where_str = data[offset : offset + where_len].decode('utf-8')
        offset += where_len
        
        # Decode Value Length
        value_len = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        
        # Decode Value String
        value_str = data[offset : offset + value_len].decode('utf-8')
        
        from Class.Common.DbCommon import DbQueryLongUpdateResT
        res = DbQueryLongUpdateResT()
        
        result = self.m_DbSession.update_long(table, field, value_str, where_str)
        
        res.m_Result = 1 if result else 0
        if not result:
            res.m_Error = self.m_DbSession.get_error()[:MAX_ERROR_SIZE]
            
        self.m_DBServerSession.send_packet(DB_QUERY_LONG_UPDATE_RES, res)

    def get_log_file(self):
        return self.m_LogFile