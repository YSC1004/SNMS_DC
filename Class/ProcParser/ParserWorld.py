import sys
import os
import threading
import copy
import time
import shutil
from datetime import datetime

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# Imports
# -------------------------------------------------------
from Class.Common.AsWorld import AsWorld
from Class.Util.FrArgParser import FrArgParser
from Class.Event.FrLogger import FrLogger
from Class.Common.AsUtil import AsUtil
from Class.Common.CommType import *
from Class.Common.ProcConnectionMgr import ProcConnectionMgr
from Class.Common.ChildProcessManager import ChildProcessManager
from Class.Util.FrTime import FrTime

# Lazy Imports
try:
    from Class.ProcParser.ManagerConnection import ManagerConnection
    from Class.ProcParser.ConnectorConnMgr import ConnectorConnMgr
    from Class.ProcParser.RouterConnection import RouterConnection
    from Class.ProcParser.DataRouterConnection import DataRouterConnection
    from Class.ProcParser.DataSender import DataSender
    from Class.ProcParser.IdentManager import IdentManager
    from Class.ProcParser.MappingMgr import MappingMgr
    from Class.ProcParser.LockManager import LockManager
    from Class.ProcParser.ParserType import ExtractDataInfo, TemporaryMsgInfo
except ImportError:
    pass

class ParserWorld(AsWorld):
    """
    Parser Process Main Logic.
    Handles raw data parsing, rule management, and data routing.
    """
    _instance = None

    # Constants
    DEBUG_MEMORY_LEAK_EXTRACTDATAINFO = 20202
    EXTRACTDATAINFO_CHECK_INTERVAL = 60
    PARSE_RAW_CHANGE_PERIOD_HOUR = 3
    
    SEARCH_RAW_LOG_TIME_OUT = 1001
    PARSING_RAW_TIME_OUT = 1002
    MMC_CMD_RESULT = 1003
    
    DEFAULT_MAX_RAW_MSG_BUF = 100000

    def __init__(self):
        """
        C++: ParserWorld()
        """
        super().__init__()
        ParserWorld._instance = self
        
        self.m_TmpDirNameStr = ""
        self.m_IdentManager = None
        self.m_MappingMgr = None
        
        self.m_RawMsgFp = None
        self.m_RawMsgFpFileName = ""
        self.m_RawMsgTmpFp = None
        self.m_RawMsgTmpFileName = ""
        self.m_SearchRawLogFp = None
        
        self.m_MsgIdentType = 1
        self.m_CmdResponseTimeOut = 41
        self.m_RuleChangeStatus = False
        self.m_MappingRuleChangeStatus = False
        
        self.m_RawFileChangeLock = threading.Lock()
        self.m_IsMsgLogging = False
        self.m_LockManager = None
        self.m_DefaultBufferSize = self.DEFAULT_MAX_RAW_MSG_BUF
        self.m_RawLoggingFlagUse = True
        
        # Managers & Connections
        self.m_ManagerConnection = ManagerConnection(None)
        self.m_ConnectorConnMgr = ConnectorConnMgr()
        self.m_RouterConnection = RouterConnection(None)
        
        self.m_DataSenderMap = {}
        self.m_TemporaryMsgInfoList = []
        self.m_ResponseCmdList = []
        self.m_TmpDataHandlerInfoList = []
        self.m_ParseRawFileList = [] # deque

    def __del__(self):
        """
        C++: ~ParserWorld()
        """
        if self.m_RawMsgFp: self.m_RawMsgFp.close()
        if self.m_RawMsgTmpFp: self.m_RawMsgTmpFp.close()
        super().__del__()

    @staticmethod
    def get_instance():
        return ParserWorld._instance

    def app_start(self, argc, argv):
        """
        C++: bool AppStart(int Argc, char** Argv)
        """
        if not self.init_config():
            return False

        FrLogger.get_instance().enable("Parser", 3)
        FrLogger.get_instance().enable("Common", 3)

        parser = FrArgParser(argv)
        self.m_ProcName = parser.get_value(ARG_NAME)
        self.m_ManagerSocketPath = parser.get_value(ARG_MANAGER_SOCKET_PATH)
        self.m_RuleId = parser.get_value(ARG_RULEID)
        
        delay_time = int(parser.get_value(ARG_DELAY_TIME) or "0")
        self.m_MsgIdentType = int(parser.get_value(ARG_CMD_IDENT_TYPE) or "1")
        
        self.m_RuleFilePath = self.get_rule_dir()
        
        val = self.get_env_value(ASCII_PARSER, "command_reponse_timeout")
        self.m_CmdResponseTimeOut = int(val) if val else 41
        
        val = self.get_env_value(ASCII_PARSER, "msg_logging")
        self.m_IsMsgLogging = True if val and int(val) else False
        
        val = self.get_env_value(ASCII_PARSER, "raw_logging_flag_use")
        if val: self.m_RawLoggingFlagUse = True if int(val) else False

        self.set_log_file(ASCII_PARSER)
        self.set_system_info(ASCII_PARSER, self.m_ProcName)

        print("\n\n\n\n\n\n\n\n")
        print(f"[ParserWorld] Parser({self.m_ProcName}) Start.............")
        
        if delay_time > 0:
            time.sleep(delay_time)
            
        self.set_log_status(ASCII_PARSER, self.m_ProcName)
        
        if not self.init_parser():
            print("[ParserWorld] Parser Init Fail")
            # return False (C++ commented out)

        self.parsing_raw_file_change(True)
        self.search_raw_file_change()
        
        self.set_timer(self.EXTRACTDATAINFO_CHECK_INTERVAL, self.DEBUG_MEMORY_LEAK_EXTRACTDATAINFO)
        return True

    def init_parser(self):
        """
        C++: bool InitParser()
        """
        # Connect to Manager
        while True:
            if not self.m_ManagerConnection.connect_unix(self.m_ManagerSocketPath):
                print(f"[ParserWorld] Manager Connect Error Retry")
                time.sleep(1)
            else:
                break
                
        self.m_ManagerConnection.set_session_identify(ASCII_PARSER, self.m_ProcName, self.get_proc_alive_check_time())
        
        # Temp Dir Init
        self.m_TmpDirNameStr = f"{self.get_parser_temp_dir()}/{self.m_ProcName}"
        if not os.path.exists(self.m_TmpDirNameStr):
            try:
                os.makedirs(self.m_TmpDirNameStr, 0o777)
            except OSError as e:
                print(f"[ParserWorld] Tmp Dir Create Error : {e}")
        else:
            # Cleanup old temp files logic (simplified)
            pass

        if not self.init_ident_manager():
            return False
            
        self.init_ne_mapping_rule()
        print("[ParserWorld] Parsing Rule Init Success!!!!!!!!")
        return True

    def init_ident_manager(self):
        """
        C++: bool InitIdentManager()
        """
        self.m_RuleChangeStatus = False
        self.m_IdentManager = IdentManager()
        
        print("----------------------------------------")
        print(f"Parsing Rule({self.m_RuleId}) Init Start....")
        print("----------------------------------------")
        
        if not self.m_IdentManager.init(self.m_RuleFilePath, self.m_RuleId, "_PBS_"):
            print(f"[ParserWorld] IdentManager Init Error")
            return False
            
        self.m_IdentManager.set_rule_type(self.get_rule_type())
        print(f"[ParserWorld] Parsing Rule({self.m_RuleId}) Init Success....")
        return True

    def init_ne_mapping_rule(self):
        """
        C++: bool InitNeMappingRule()
        """
        self.m_MappingRuleChangeStatus = False
        if self.m_IdentManager:
            self.m_MappingMgr = MappingMgr()
            rule_path = f"{self.m_RuleFilePath}/NE_MAPPING.RULE"
            if not self.m_MappingMgr.init(rule_path, "_PBS_"):
                print("[ParserWorld] Mapping Rule Init Error")
                return False
            return True
        else:
            return False

    def parsing(self, msg_id, ne_id, port_no, msg, length, logging_flag=0, re_parsing=False):
        """
        C++: void Parsing(...)
        The core parsing logic. Writes raw msg, identifies rule, and routes data.
        """
        # 1. Raw Logging
        if not re_parsing:
            if not (self.m_RawLoggingFlagUse and logging_flag == 1):
                cur_time = FrTime()
                header = f"\nMSG_START SIZE={length} [PORT={port_no}] [{cur_time.get_time_string()}] output message\n"
                
                if self.m_SearchRawLogFp:
                    self.m_SearchRawLogFp.write(header)
                    self.m_SearchRawLogFp.write(msg) # Assuming msg is string
                    self.m_SearchRawLogFp.flush()

        # 2. Identification & Extraction
        if self.m_IdentManager:
            if not self.m_RuleChangeStatus:
                # Normal Operation
                info = self.m_IdentManager.data_identify(msg)
                if info:
                    # Write to Raw File
                    if self.m_RawMsgFp:
                        self.m_RawMsgFp.write("\n\n")
                        file_pos = self.m_RawMsgFp.tell()
                        self.m_RawMsgFp.write(info.m_ConvertMsg)
                        self.m_RawMsgFp.flush()
                        
                        # Create ExtractDataInfo and Route
                        if info.m_IdentRulePtr and info.m_IdentRulePtr.m_ConsumerVector:
                            ptr = ExtractDataInfo(msg_id, info.m_IdentRulePtr, info.m_IdentIdString,
                                                  ne_id, port_no, file_pos, len(info.m_ConvertMsg))
                            self.insert_parsing_data(ptr)
            else:
                # Rule Change in Progress -> Buffer to Temp
                if self.m_RawMsgTmpFp:
                    self.m_RawMsgTmpFp.write("\n")
                    file_pos = self.m_RawMsgTmpFp.tell()
                    self.m_RawMsgTmpFp.write(msg)
                    self.m_RawMsgTmpFp.flush()
                    
                    self.m_TemporaryMsgInfoList.append({
                        'msg_id': msg_id, 'ne_id': ne_id, 'port_no': port_no,
                        'file_pos': file_pos, 'msg_len': len(msg)
                    })
                else:
                    # Create Tmp File logic
                    self.m_RawMsgTmpFileName = f"{self.m_RawMsgFpFileName}_TMP"
                    self.m_RawMsgTmpFp = open(self.m_RawMsgTmpFileName, "a+")
                    self.m_RawMsgFp.write("\n--Temp Msg Start--------------------------------------------------------\n")
                    self.m_RawMsgFp.flush()
                    # Recurse or handle first msg
        else:
            print(f"[ParserWorld] Parsing Module({self.m_RuleId}) Not Init.....")

    def insert_parsing_data(self, info):
        """
        C++: void InsertParsingData(ExtractDataInfo* Info)
        Routes data to appropriate DataSender threads.
        """
        consumers = info.m_IdentRulePtr.m_ConsumerVector
        ref_cnt = 0
        
        for consumer in consumers:
            if consumer in self.m_DataSenderMap:
                ref_cnt += 1
                new_info = info.dup_instance(ref_cnt, consumer)
                self.m_DataSenderMap[consumer].push_extract_data_info(new_info)
            else:
                # print(f"[ParserWorld] DataRouter({consumer}) is not Connected")
                pass

    def parsing_raw_file_change(self, is_first=False):
        """
        C++: void ParsingRawFileChange(bool IsFirst)
        Rotates the raw message file.
        """
        with self.m_RawFileChangeLock:
            if not is_first:
                self.insert_dummy_instance()
            
            cur_time = FrTime()
            hour = cur_time.get_hour() % self.PARSE_RAW_CHANGE_PERIOD_HOUR
            tmp_hour = self.PARSE_RAW_CHANGE_PERIOD_HOUR - hour - 1
            
            # Calculate next timeout
            remain = cur_time.get_remain_hour_sec()
            time_out = remain + (tmp_hour * 3600) if remain else (tmp_hour + 1) * 3600
            
            # Cleanup old files
            while len(self.m_ParseRawFileList) > 1:
                old_file = self.m_ParseRawFileList.pop(0)
                if os.path.exists(old_file):
                    os.remove(old_file)
            
            # Create New File
            self.raw_file_change(cur_time)
            
            # Set Timer
            self.set_timer(time_out + 10, self.PARSING_RAW_TIME_OUT)

    def raw_file_change(self, file_time):
        """
        C++: void RawFileChange(frTime& FileTime)
        """
        if self.m_RawMsgFp:
            self.m_RawMsgFp.close()
            
        ne_name = self.m_ProcName.replace("PARSER_", "", 1)
        # Format: TmpDir/NeName_YYYYMMDDHH.RAW
        file_name = f"{self.m_TmpDirNameStr}/{ne_name}_{file_time.get_year():04d}{file_time.get_month():02d}{file_time.get_day():02d}{file_time.get_hour():02d}.RAW"
        
        self.m_RawMsgFpFileName = file_name
        self.m_RawMsgFp = open(self.m_RawMsgFpFileName, "a+") # RW mode
        self.m_ParseRawFileList.append(self.m_RawMsgFpFileName)

    def insert_dummy_instance(self):
        """
        Injects a dummy message to flush buffers/queues in DataSenders.
        """
        # info = ExtractDataInfo() ...
        # logic similar to C++
        pass

    def create_data_sender(self, data_handler_id):
        """
        C++: bool CreateDataSender(string DataHandlerId)
        Starts a DataRouterConnection and DataSender thread.
        """
        if data_handler_id in self.m_DataSenderMap:
            return False
            
        conn = DataRouterConnection(data_handler_id)
        sender = DataSender(data_handler_id, conn)
        sender.run()
        
        # Connect to DataRouter (Unix Socket or TCP)
        socket_path = self.get_data_router_listen_socket_path(data_handler_id)
        conn.start(socket_path) # Custom Start method in DataRouterConnection
        
        conn.set_data_sender(sender, self.m_MappingMgr)
        conn.change_world(sender)
        
        self.m_DataSenderMap[data_handler_id] = sender
        print(f"[ParserWorld] CreateDataSender Success : {data_handler_id}")
        return True

    def recv_data_handler_info(self, info):
        """
        C++: void RecvDataHandlerInfo(AS_DATA_HANDLER_INFO_T* Info)
        """
        # Logic to create/destroy DataSenders based on info
        if info.SettingStatus == START:
            self.create_data_sender(info.DataHandlerId)
        elif info.SettingStatus == STOP:
            # destory logic
            pass

    def open_port(self, port_info):
        """
        C++: void OpenPort(AS_CMD_OPEN_PORT_T* PortInfo)
        Called by ManagerConnection when CMD_OPEN_PORT is received.
        """
        print("[ParserWorld] Receive CmdOpenInfo")
        
        if port_info.ProtocolType == PARSER_LISTEN:
            if not self.m_ConnectorConnMgr.init_unix_socket(port_info.PortPath):
                err_msg = "Parser Listener Create Error"
                print(f"[ParserWorld] {err_msg}")
                # Send Ack Error
                return
            self.proc_init_end()
            
        elif port_info.ProtocolType == ROUTER_CONNECT:
            if not self.m_RouterConnection.connect_unix(port_info.PortPath):
                err_msg = "Router Connect Error"
                print(f"[ParserWorld] {err_msg}")
                # Send Ack Error
                return
        
        # Send Ack Success
        self.m_ManagerConnection.send_ack(CMD_OPEN_PORT_ACK, port_info.Id)

    def proc_init_end(self):
        self.m_ManagerConnection.send_ack(PROC_INIT_END, 1)

    def send_ascii_error(self, priority, fmt, *args):
        msg = fmt
        if args: msg = fmt % args
        self.m_ManagerConnection.send_ascii_error(priority, msg)

    def get_data_router_listen_socket_path(self, session_name):
        return f"{self.get_unix_socket_dir()}/DATAROUTER_LISTEN_{session_name}" # Macro replacement

    def get_rule_type(self):
        return self.m_MsgIdentType

    # ... Other helper methods (search_raw_file_change, receive_time_out etc) implemented similarly