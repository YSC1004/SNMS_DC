import sys
import os
import time
import copy

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
from Class.ProcParser.ParserType import *
from Class.ProcParser.DataExtractManager import DataExtractManager
from Class.Util.FrUtilMisc import FrUtilMisc

class DataRouterConnection(AsSocket):
    """
    Manages connection to DataRouter (Unix Socket) and handles data extraction/sending.
    Polls data from DataSender, extracts fields, and sends to DataRouter.
    """
    
    # Timer Constants
    PARSINGDATA_POLLING_TIME_OUT = 2001
    DATA_ROUTER_CONN_TIME_OUT = 2002
    
    PARSINGDATA_POLLING_TIME = 0.01 # 10ms (approx)
    DATA_ROUTER_CONN_TIME = 1 # 1 sec

    def __init__(self, consumer):
        """
        C++: DataRouterConnection(string Consumer)
        """
        super().__init__()
        self.set_session_name(consumer)
        
        self.m_DataSender = None
        self.m_ParsingDataPollingTimerKey = -1
        self.m_DataRouterConnTimerKey = -1
        self.m_DataExtractManager = None
        self.m_MappingMgr = None
        
        self.m_NowNeId = None
        self.m_NowPortNo = -1
        self.m_RawMsgFp = None
        
        from ParserWorld import ParserWorld
        world = ParserWorld.get_instance()
        self.m_DefaultBufSize = world.m_DefaultBufferSize
        self.m_MsgBuf = bytearray(self.m_DefaultBufSize)
        
        self.m_DataRouterListen = ""
        self.m_SendedRecordCnt = 0

    def __del__(self):
        """
        C++: ~DataRouterConnection()
        """
        if self.m_RawMsgFp:
            self.m_RawMsgFp.close()
        # DataExtractManager cleanup by GC
        super().__del__()

    def set_data_sender(self, data_sender, mapping_mgr):
        """
        C++: void SetDataSender(DataSender* DataSender, MappingMgr** MappingMgr)
        """
        self.m_DataSender = data_sender
        self.m_MappingMgr = mapping_mgr
        
        self.m_DataExtractManager = DataExtractManager(self)
        self.m_DataExtractManager.init_guid_maker(
            os.getpid(), 
            self.get_thread_id(), # Inherited or util
            AsUtil.get_local_ip()
        )
        
        from ParserWorld import ParserWorld
        world = ParserWorld.get_instance()
        
        # Open Raw File Read Mode
        file_name = world.get_cur_raw_file_name()
        if file_name:
            try:
                self.m_RawMsgFp = open(file_name, "rb")
            except IOError:
                print(f"[DataRouterConnection] Raw File Open Error: {file_name}")

    def receive_time_out(self, reason, extra_reason=None):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        """
        if reason == self.PARSINGDATA_POLLING_TIME_OUT:
            self._handle_polling_timeout()
            
        elif reason == self.DATA_ROUTER_CONN_TIME_OUT:
            self.m_DataRouterConnTimerKey = -1
            self.start(self.m_DataRouterListen)
            
        else:
            print(f"[DataRouterConnection] Unknown Time Out Reason : {reason}")

    def _handle_polling_timeout(self):
        """
        Internal logic for PARSINGDATA_POLLING_TIME_OUT
        """
        cnt = 0
        while True:
            if not self.is_connect():
                return

            if cnt > 30:
                time.sleep(0.007) # 7ms
                cnt = 0

            self.m_DataSender.sender_lock()
            
            info = self.m_DataSender.get_extract_data_info()
            cnt += 1
            
            if info:
                if info.m_MsgId != -1: # RAW_MSG_CHANGE_FLAG equivalent (-1)
                    self.m_NowNeId = info.m_NeId
                    self.m_NowPortNo = info.m_PortNo
                    
                    try:
                        self.m_RawMsgFp.seek(info.m_FilePos)
                        
                        # Resize logic (Python handles automatically usually)
                        if info.m_MsgSize + 1 > len(self.m_MsgBuf):
                            self.m_MsgBuf = bytearray(info.m_MsgSize + 1)
                            
                        data = self.m_RawMsgFp.read(info.m_MsgSize)
                        # data is bytes
                        
                        if len(data) != info.m_MsgSize:
                            print(f"[DataRouterConnection] Msg Read Error -- Read: {len(data)}, Expected: {info.m_MsgSize}")
                        
                        self.m_SendedRecordCnt = 0
                        
                        # Extract Data
                        # Needs decoding bytes to string for extraction? Usually extraction works on strings
                        msg_str = data.decode('utf-8', errors='ignore')
                        
                        self.m_DataExtractManager.data_extract(
                            info.m_IdentRulePtr, 
                            info.m_IdentIdString, 
                            msg_str, 
                            self.get_session_name()
                        )
                        
                        print(f"[DataRouterConnection] Total Sended Record Count : {self.m_SendedRecordCnt}({self.get_session_name()},{info.m_IdentRulePtr.m_IdentName})")

                    except Exception as e:
                        print(f"[DataRouterConnection] Parsing Error: {e}")

                else: # Raw File Change
                    print(f"[DataRouterConnection] Raw msg file change({self.get_session_name()})")
                    if self.m_RawMsgFp:
                        self.m_RawMsgFp.close()
                    
                    from ParserWorld import ParserWorld
                    file_name = ParserWorld.get_instance().get_cur_raw_file_name()
                    try:
                        self.m_RawMsgFp = open(file_name, "rb")
                    except:
                        pass
                
                # Cleanup Info (C++ delete info)
                # Python GC handles it
                self.m_DataSender.sender_unlock()
            
            else: # No Info
                self.m_DataSender.sender_unlock()
                break
        
        # Reset Timer
        self.m_ParsingDataPollingTimerKey = self.set_timer(self.PARSINGDATA_POLLING_TIME, self.PARSINGDATA_POLLING_TIME_OUT)

    def parsing_result(self, consumers, p_data):
        """
        C++: void ParsingResult(const char* Consumers, const AS_PARSED_DATA_T* Pdata)
        Callback from DataExtractManager with extracted data.
        Fills NeId, MappingId and sends packet.
        """
        # p_data is AsParsedDataT instance
        p_data.neId = self.m_NowNeId
        
        mapping_name = None
        if self.m_MappingMgr:
            mapping_name = self.m_MappingMgr.find_mapping_name(p_data.neId, p_data.bscNo, self.m_NowPortNo)
            if mapping_name:
                p_data.mappingNeId = mapping_name
            else:
                p_data.mappingNeId = "" # Null handling

        if p_data.listSequence == -1: # EOR
            # Debug log
            pass
        else:
            self.m_SendedRecordCnt += 1
            
        self.send_parsed_data(p_data)

    def send_parsed_data(self, p_data):
        """
        C++: void SendParsedData(const AS_PARSED_DATA_T* Pdata)
        """
        body = p_data.pack()
        if not self.packet_send(PacketT(AS_PARSED_DATA, len(body), body)):
            self.close()
            if self.m_DataRouterConnTimerKey == -1:
                self.m_DataRouterConnTimerKey = self.set_timer(self.DATA_ROUTER_CONN_TIME, self.DATA_ROUTER_CONN_TIME_OUT)

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        """
        print(f"[DataRouterConnection] DataRouter Connection Broken({self.get_session_name()})")
        if self.m_DataRouterConnTimerKey == -1:
            self.m_DataRouterConnTimerKey = self.set_timer(self.DATA_ROUTER_CONN_TIME, self.DATA_ROUTER_CONN_TIME_OUT)

    def start(self, data_router_listen_path):
        """
        C++: void Start(string DataRouterListen)
        Initiates connection to DataRouter (Unix Domain Socket).
        """
        self.m_DataRouterListen = data_router_listen_path
        print(f"[DataRouterConnection] Try DataRouter Connect : {self.get_session_name()}")
        
        if self.connect_unix(self.m_DataRouterListen):
            print(f"[DataRouterConnection] DataRouter({self.get_session_name()}) Connect Success")
            
            if self.m_ParsingDataPollingTimerKey != -1:
                self.cancel_timer(self.m_ParsingDataPollingTimerKey)
                
            self.m_ParsingDataPollingTimerKey = self.set_timer(self.PARSINGDATA_POLLING_TIME, self.PARSINGDATA_POLLING_TIME_OUT)
        else:
            print(f"[DataRouterConnection] DataRouter Connect Fail")
            if self.m_DataRouterConnTimerKey == -1:
                self.m_DataRouterConnTimerKey = self.set_timer(self.DATA_ROUTER_CONN_TIME, self.DATA_ROUTER_CONN_TIME_OUT)

    def recv_message(self, message, addition_info=None):
        """
        C++: void RecvMessage(int Message, void* AdditionInfo)
        Handles inter-thread message (DELETE_DATA_HANDLER) to destroy self.
        """
        print(f"[DataRouterConnection] Recv DataSender Destroy Message({message})")
        
        if message == DELETE_DATA_HANDLER: # Enum constant
            ptr = self.m_DataSender
            # Python GC handles delete this
            # Need to signal parent thread loop to stop managing this connection?
            # Usually handled by returning False in Run loop or explicit cleanup
            ptr.stop()
            print("[DataRouterConnection] Recv DataSender Destroy finished")
        else:
            print(f"[DataRouterConnection] unknown message : {message}")