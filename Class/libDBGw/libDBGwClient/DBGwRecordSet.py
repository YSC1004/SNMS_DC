import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import definitions from DbCommon
from Class.Common.DbCommon import (
    DB_RS_MOVE_NEXT_REQ, DB_RS_QUERY_DATA, DB_RS_CLOSE_REQ,
    DbRsMoveNextReqT, DbRsQueryDataT, DbRsCloseReqT,
    DEF_BUF_SIZE
)
from Class.Common.CommType import SEG_ING, SEG_END

# Mock for Framework classes (frDbParam, frDbRecord)
# Assuming these exist in the framework or need placeholders
from Class.Sql.FrDbParam import FrDbParam, FrDbRecord

class DBGwRecordSet:
    """
    C++: DBGwRecordSet
    Manages server-side cursors (RecordSet).
    Fetches rows sequentially from the server.
    """
    def __init__(self, gw_user):
        """
        C++: DBGwRecordSet(DBGwUser* GwUser)
        """
        self.m_QueryId = 0
        self.m_DBGwUser = gw_user
        self.m_IsEndRow = False
        self.m_IsValid = False
        
        # C++: m_DbParam = new frDbParam;
        self.m_DbParam = FrDbParam()

    def __del__(self):
        """
        C++: ~DBGwRecordSet()
        """
        # C++ deletes m_DbParam here. Python GC handles it.
        self.close_record_set()

    def is_valid(self):
        """C++: bool IsValid()"""
        return self.m_IsValid

    def get_col(self):
        """C++: int GetCol()"""
        return self.m_DbParam.get_col()

    def get_row(self):
        """C++: int GetRow()"""
        return self.m_DbParam.get_row()

    def set_col(self, col):
        """C++: void SetCol(int Col)"""
        self.m_DbParam.set_col(col)

    def set_row(self, row):
        """C++: void SetRow(int Row)"""
        self.m_DbParam.set_row(row)

    def move_next(self):
        """
        C++: frDbRecord* MoveNext()
        Fetches the next row from the server.
        Handles packet segmentation (re-assembly) if data is large.
        """
        if self.m_IsEndRow:
            return None

        # Prepare Request
        req = DbRsMoveNextReqT()
        req.m_QueryId = self.m_QueryId

        # Prepare Response Holder
        query_data = DbRsQueryDataT()
        record = None

        # Send Request and Wait for Response
        # Assuming m_DBGwUser has m_DBClientSocket which has send_and_wait_packet
        if self.m_DBGwUser.m_DBClientSocket.send_and_wait_packet(
            DB_RS_MOVE_NEXT_REQ, req, DB_RS_QUERY_DATA, query_data
        ) > 0:
            
            # Error Case
            if query_data.m_Size == -1:
                return record

            # End of Record Set
            if query_data.m_Size == -2:
                self.m_IsEndRow = True
                return record

            # Check Segmentation
            if query_data.m_SegFlag == SEG_ING:
                # C++ allocates DEF_BUF_SIZE. Python bytearray grows automatically.
                data_buf = bytearray()
                
                # Append first chunk
                # Assuming query_data.m_Data is bytes
                data_buf.extend(query_data.m_Data[:query_data.m_Size])
                
                while True:
                    # Reset holder for next chunk
                    query_data = DbRsQueryDataT()
                    
                    # Wait for next chunk
                    if self.m_DBGwUser.m_DBClientSocket.wait_packet(
                        DB_RS_QUERY_DATA, query_data
                    ) > 0:
                        data_buf.extend(query_data.m_Data[:query_data.m_Size])
                        
                        if query_data.m_SegFlag != SEG_ING:
                            break
                    else:
                        # Wait failed
                        break
                
                # Decode Assembled Data
                record = self.m_DBGwUser.decode_rs_data(self.get_col(), self.m_DbParam, data_buf)
            
            else:
                # No Segmentation, Decode directly
                # Note: m_Data usually fixed size array in C struct, need slicing by m_Size in Python logic if mapped that way
                data = query_data.m_Data[:query_data.m_Size]
                record = self.m_DBGwUser.decode_rs_data(self.get_col(), self.m_DbParam, data)

            if record:
                # Optional: Update internal row count or pointers if needed
                pass

        return record

    def move_first(self):
        """C++: frDbRecord* MoveFirst()"""
        return None

    def move_last(self):
        """C++: frDbRecord* MoveLast()"""
        return None

    def close_record_set(self):
        """
        C++: bool CloseRecordSet()
        Sends a close request to the server to free the cursor.
        """
        if self.m_IsValid:
            req = DbRsCloseReqT()
            req.m_QueryId = self.m_QueryId
            req.m_Reserved = 0
            
            if self.m_DBGwUser and self.m_DBGwUser.m_DBClientSocket:
                self.m_DBGwUser.m_DBClientSocket.send_packet(DB_RS_CLOSE_REQ, req)
            
            self.m_IsValid = False
            
        return True