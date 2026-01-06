import sys
import os
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
    DB_CONN_REQ, DB_CONN_RES, DB_CLOSE_REQ,
    DB_QUERY_REQ, DB_QUERY_RES, DB_BULK_QUERY_DATA,
    DB_RS_QUERY_DATA, DB_RS_MOVE_NEXT_REQ, DB_RS_CLOSE_REQ,
    DB_COMMIT_RES, DB_ROLLBACK_RES,
    DB_QUERY_LONG_UPDATE_REQ, DB_QUERY_LONG_UPDATE_RES
)

# Assuming AsSocket is in Class.Common.AsSocket
try:
    from Class.Common.AsSocket import AsSocket
except ImportError:
    # Fallback dummy class if AsSocket is not available yet
    class AsSocket:
        def hton_struct(self, packet): pass
        def ntoh_struct(self, packet): pass
        def disable(self): pass

class AsSocketDisableGuard:
    """
    C++: AsSocketDisableGuard
    RAII wrapper to ensure socket is disabled.
    Implemented as a Context Manager in Python.
    """
    def __init__(self, sock):
        self.m_Socket = sock
        if self.m_Socket:
            self.m_Socket.disable()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        C++ destructor logic: m_Socket->Disable()
        """
        if self.m_Socket:
            # m_Socket->Enable(); // Commented out in C++
            self.m_Socket.disable()

class DBGwBaseSocket(AsSocket):
    """
    C++: DBGwBaseSocket
    Handles byte-order conversion for database gateway packets.
    """
    def __init__(self):
        super().__init__()

    def hton_struct(self, packet):
        """
        C++: void HtonStruct(PACKET_T*& Packet)
        Host to Network Byte Order (Little Endian -> Big Endian)
        """
        # packet.msg is assumed to be an instance of the specific Req/Res class
        msg = packet.msg
        msg_id = packet.msgId

        if msg_id == DB_CONN_REQ:
            msg.ProcPid = socket.htonl(msg.ProcPid)

        elif msg_id == DB_CONN_RES:
            msg.m_Result = socket.htons(msg.m_Result)

        elif msg_id == DB_CLOSE_REQ:
            msg.m_Req = socket.htonl(msg.m_Req)

        elif msg_id == DB_QUERY_REQ:
            msg.m_QueryId = socket.htonl(msg.m_QueryId)
            msg.m_QueryType = socket.htonl(msg.m_QueryType)
            msg.m_QueryReqType = socket.htonl(msg.m_QueryReqType)
            msg.m_Commit = socket.htonl(msg.m_Commit)
            
            # Handling Enum/Flag casting
            # C++: enumTmp = (int)req->m_SegFlag;
            # Assuming m_SegFlag is stored as int in the msg object for transport
            if isinstance(msg.m_SegFlag, int):
                msg.m_SegFlag = socket.htonl(msg.m_SegFlag)

        elif msg_id == DB_QUERY_RES:
            msg.m_QueryId = socket.htonl(msg.m_QueryId)
            msg.m_ColCnt = socket.htonl(msg.m_ColCnt)
            msg.m_RowCnt = socket.htonl(msg.m_RowCnt)
            msg.m_DataSize = socket.htonl(msg.m_DataSize)
            msg.m_Result = socket.htons(msg.m_Result)

        elif msg_id == DB_BULK_QUERY_DATA:
            msg.m_QueryId = socket.htonl(msg.m_QueryId)
            if isinstance(msg.m_SegFlag, int):
                msg.m_SegFlag = socket.htonl(msg.m_SegFlag)

        elif msg_id == DB_RS_QUERY_DATA:
            msg.m_QueryId = socket.htonl(msg.m_QueryId)
            msg.m_CurRow = socket.htonl(msg.m_CurRow)
            if isinstance(msg.m_SegFlag, int):
                msg.m_SegFlag = socket.htonl(msg.m_SegFlag)
            msg.m_Size = socket.htonl(msg.m_Size)

        elif msg_id == DB_RS_MOVE_NEXT_REQ:
            msg.m_QueryId = socket.htonl(msg.m_QueryId)
            msg.m_Reserved = socket.htonl(msg.m_Reserved)

        elif msg_id == DB_RS_CLOSE_REQ:
            msg.m_QueryId = socket.htonl(msg.m_QueryId)
            msg.m_Reserved = socket.htonl(msg.m_Reserved)

        elif msg_id == DB_COMMIT_RES:
            msg.m_Result = socket.htons(msg.m_Result)

        elif msg_id == DB_ROLLBACK_RES:
            msg.m_Result = socket.htons(msg.m_Result)

        elif msg_id == DB_QUERY_LONG_UPDATE_REQ:
            if isinstance(msg.m_SegFlag, int):
                msg.m_SegFlag = socket.htonl(msg.m_SegFlag)
            msg.m_DataSize = socket.htonl(msg.m_DataSize)

        elif msg_id == DB_QUERY_LONG_UPDATE_RES:
            msg.m_Result = socket.htons(msg.m_Result)

        else:
            # Call parent implementation
            super().hton_struct(packet)

    def ntoh_struct(self, packet):
        """
        C++: void NtohStruct(PACKET_T*& Packet)
        Network to Host Byte Order (Big Endian -> Little Endian)
        """
        msg = packet.msg
        msg_id = packet.msgId

        if msg_id == DB_CONN_REQ:
            msg.ProcPid = socket.ntohl(msg.ProcPid)

        elif msg_id == DB_CONN_RES:
            msg.m_Result = socket.ntohs(msg.m_Result)

        elif msg_id == DB_CLOSE_REQ:
            msg.m_Req = socket.ntohl(msg.m_Req)

        elif msg_id == DB_QUERY_REQ:
            msg.m_QueryId = socket.ntohl(msg.m_QueryId)
            msg.m_QueryType = socket.ntohl(msg.m_QueryType)
            msg.m_QueryReqType = socket.ntohl(msg.m_QueryReqType)
            msg.m_Commit = socket.ntohl(msg.m_Commit)
            
            if isinstance(msg.m_SegFlag, int):
                msg.m_SegFlag = socket.ntohl(msg.m_SegFlag)

        elif msg_id == DB_QUERY_RES:
            msg.m_QueryId = socket.ntohl(msg.m_QueryId)
            msg.m_ColCnt = socket.ntohl(msg.m_ColCnt)
            msg.m_DataSize = socket.ntohl(msg.m_DataSize)
            msg.m_RowCnt = socket.ntohl(msg.m_RowCnt)
            msg.m_Result = socket.ntohs(msg.m_Result)

        elif msg_id == DB_BULK_QUERY_DATA:
            msg.m_QueryId = socket.ntohl(msg.m_QueryId)
            if isinstance(msg.m_SegFlag, int):
                msg.m_SegFlag = socket.ntohl(msg.m_SegFlag)

        elif msg_id == DB_RS_QUERY_DATA:
            msg.m_QueryId = socket.ntohl(msg.m_QueryId)
            msg.m_CurRow = socket.ntohl(msg.m_CurRow)
            if isinstance(msg.m_SegFlag, int):
                msg.m_SegFlag = socket.ntohl(msg.m_SegFlag)
            msg.m_Size = socket.ntohl(msg.m_Size)

        elif msg_id == DB_RS_MOVE_NEXT_REQ:
            msg.m_QueryId = socket.ntohl(msg.m_QueryId)
            msg.m_Reserved = socket.ntohl(msg.m_Reserved)

        elif msg_id == DB_RS_CLOSE_REQ:
            msg.m_QueryId = socket.ntohl(msg.m_QueryId)
            msg.m_Reserved = socket.ntohl(msg.m_Reserved)

        elif msg_id == DB_COMMIT_RES:
            msg.m_Result = socket.ntohs(msg.m_Result)

        elif msg_id == DB_ROLLBACK_RES:
            msg.m_Result = socket.ntohs(msg.m_Result)

        elif msg_id == DB_QUERY_LONG_UPDATE_REQ:
            if isinstance(msg.m_SegFlag, int):
                msg.m_SegFlag = socket.ntohl(msg.m_SegFlag)
            msg.m_DataSize = socket.ntohl(msg.m_DataSize)

        elif msg_id == DB_QUERY_LONG_UPDATE_RES:
            msg.m_Result = socket.ntohs(msg.m_Result)

        else:
            super().ntoh_struct(packet)