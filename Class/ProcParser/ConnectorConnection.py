import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.AsSocket import AsSocket
from Class.Common.CommType import *
from Class.Common.AsUtil import AsUtil

class ConnectorConnection(AsSocket):
    """
    Handles connection from Connector processes.
    Receives raw data (potentially segmented) and reassembles it before parsing.
    """
    def __init__(self, conn_mgr):
        """
        C++: ConnectorConnection(ConnectorConnMgr* ConMgr)
        """
        super().__init__()
        self.m_ConnectorConnMgr = conn_mgr
        
        # Buffer Management
        from ParserWorld import ParserWorld
        world = ParserWorld.get_instance()
        
        self.m_DefaultBufSize = world.get_default_buffer_size()
        self.m_MsgBuf = bytearray(self.m_DefaultBufSize) # Use bytearray for mutable buffer
        self.m_TmpFileName = ""

    def __del__(self):
        """
        C++: ~ConnectorConnection()
        """
        # Python handles memory deallocation automatically
        super().__del__()

    def receive_packet(self, packet, session_identify=0):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        if packet.msg_id == CONNECTOR_DATA:
            ne_msg = AsConnectorDataT.unpack(packet.msg_body)
            if ne_msg: self.recv_raw_data(ne_msg)

        elif packet.msg_id == MMC_RESPONSE_DATA_REQ:
            mmc_com = AsMmcPublishT.unpack(packet.msg_body)
            if mmc_com: self.receive_mmc_respon_data_req(mmc_com)

        else:
            print(f"[ConnectorConnection] UnKnown MsgId : {packet.msg_id}")

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Error)
        """
        print("[ConnectorConnection] Socket Broken Connector")
        self.m_ConnectorConnMgr.remove(self)

    def recv_raw_data(self, ne_msg):
        """
        C++: void RecvRawData(AS_CONNECTOR_DATA_T* NeMsg)
        Handles raw message reassembly and parsing trigger.
        """
        from ParserWorld import ParserWorld
        world = ParserWorld.get_instance()

        # Extract RawMsg (assuming it's bytes or string)
        # Note: NeMsg->Length includes null terminator? C++ logic suggests Length-1 for writing.
        # Python slicing: data = ne_msg.RawMsg[:ne_msg.Length-1]
        
        # Adjust data extraction based on actual struct definition
        raw_data = ne_msg.RawMsg
        write_len = ne_msg.Length - 1 if ne_msg.Length > 0 else 0
        data_to_write = raw_data[:write_len] if isinstance(raw_data, (bytes, bytearray)) else raw_data[:write_len].encode('utf-8')

        if ne_msg.SegFlag == NO_SEG:
            # Direct Parsing
            world.parsing(ne_msg.MsgId, ne_msg.AgentNeId, ne_msg.PortNo, 
                          data_to_write.decode('utf-8', errors='ignore'), 
                          write_len, ne_msg.LoggingFlag)

        elif ne_msg.SegFlag == SEG_ING:
            # Segment: Append to Temp File
            # Path: TmpDir/MsgId
            self.m_TmpFileName = f"{world.get_temporary_dir()}/{ne_msg.MsgId}"
            
            try:
                # O_WRONLY | O_CREAT | O_APPEND equivalent
                with open(self.m_TmpFileName, "ab") as f:
                    f.write(data_to_write)
            except IOError as e:
                print(f"[ConnectorConnection] [CORE_ERROR] Temporary File({self.m_TmpFileName}) Open Error : {e}")
                return

        else: # SEG_END or other
            # Segment End: Append last chunk, Read full file, Parse, Delete file
            self.m_TmpFileName = f"{world.get_temporary_dir()}/{ne_msg.MsgId}"
            
            try:
                # Append last chunk
                with open(self.m_TmpFileName, "ab") as f:
                    f.write(data_to_write)
                
                # Read full content
                full_data = b""
                with open(self.m_TmpFileName, "rb") as f:
                    full_data = f.read()
                
                size = len(full_data)
                
                # Resize Buffer logic simulation (In Python just use the bytes object)
                # But to follow structure:
                if size + 1 > len(self.m_MsgBuf):
                    self.m_MsgBuf = bytearray(size + 1)
                
                # Copy data to buffer (Conceptual, Python usually passes object)
                decoded_msg = full_data.decode('utf-8', errors='ignore')
                
                world.parsing(ne_msg.MsgId, ne_msg.AgentNeId, ne_msg.PortNo, 
                              decoded_msg, size, ne_msg.LoggingFlag)
                
                # Remove Temp File
                os.remove(self.m_TmpFileName)

            except IOError as e:
                print(f"[ConnectorConnection] [CORE_ERROR] Temporary File({self.m_TmpFileName}) Error : {e}")
                return

    def receive_mmc_respon_data_req(self, mmc_com):
        """
        C++: void ReceiveMMCResponDataReq(AS_MMC_PUBLISH_T* MMCCom)
        """
        from ParserWorld import ParserWorld
        ParserWorld.get_instance().receive_mmc_respon_data_req(mmc_com)