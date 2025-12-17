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
    #from Class.ProcParser.ParserType import ExtractDataInfo, TemporaryMsgInfo
    from Class.ProcParser.ParserType import *
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

    def get_temporary_dir(self):
        """
        C++: const char* GetTemporaryDir()
        Returns the temporary directory path for this parser instance.
        """
        return self.m_TmpDirNameStr
    
    def send_response_command_data(self, mmc_result):
        """
        C++: void SendResponseCommandData(AS_MMC_RESULT_T* MmcResult)
        Sends the execution result of an MMC command back to the Manager.
        """
        # 디버그 로그 출력 (frDEBUG 대응)
        print(f"[ParserWorld] Send MMC Result : msgid({mmc_result.id})")
        
        # ManagerConnection으로 전송 위임
        self.m_ManagerConnection.send_response_command_data(mmc_result)
        
    def receive_mmc_respon_data_req(self, mmc_com):
        """
        C++: void ReceiveMMCResponDataReq(AS_MMC_PUBLISH_T* MMCCom)
        Registers an MMC command to wait for a response.
        """
        # ResponseCommand 객체 생성 (ParserType.py에 정의됨)
        cmd = ResponseCommand()
        
        # 데이터 복사
        cmd.Id = mmc_com.id
        cmd.Ne = mmc_com.ne
        cmd.IdString = mmc_com.idString
        cmd.Key = mmc_com.key
        cmd.Mmc = mmc_com.mmc
        
        # 리스트에 추가
        self.m_ResponseCmdList.append(cmd)

        # 로그 출력
        print(f"[ParserWorld] Receive Response Cmd : {mmc_com.mmc}")
        print(f"[ParserWorld] MsgId : {cmd.Id}, Ne : {cmd.Ne}, IdString : {cmd.IdString}, Key : {cmd.Key}")

        # 타이머 설정 (TimeOut 시 cmd 객체를 인자로 전달)
        # Reason: MMC_CMD_RESULT (상수 정의 필요)
        cmd.TimerKey = self.set_timer(self.m_CmdResponseTimeOut, self.MMC_CMD_RESULT, cmd)
        
    def get_response_cmd_list(self):
        """
        C++: ResponseCommandList* GetResponseCmdList()
        Returns the list of pending MMC commands.
        """
        return self.m_ResponseCmdList

    def receive_time_out(self, reason, extra_reason=None):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        Handles various timeout events (MMC response timeout, Log rotation, File switching).
        """
        # 1. MMC Command Response Timeout
        if reason == self.MMC_CMD_RESULT:
            cmd = extra_reason # Python passes the object directly
            if cmd:
                print(f"[ParserWorld] Command Response Wait TimeOut : ne({cmd.Ne}), mmc({cmd.Mmc})")

                mmc_res = AsMmcResultT()
                mmc_res.id = cmd.Id
                mmc_res.resultMode = R_ERROR
                mmc_res.result = f"Command Time Over({cmd.Ne}:{cmd.Mmc})"
                
                self.send_response_command_data(mmc_res)
                
                # 리스트에서 제거 및 메모리 해제(GC)
                if cmd in self.m_ResponseCmdList:
                    self.m_ResponseCmdList.remove(cmd)

        # 2. Raw Log File Search Timeout
        elif reason == self.SEARCH_RAW_LOG_TIME_OUT:
            self.search_raw_file_change()

        # 3. Debug Memory Leak Check
        elif reason == self.DEBUG_MEMORY_LEAK_EXTRACTDATAINFO:
            if self.m_DeleteDebugSet:
                with self.m_DeleteDebugSet.m_Lock:
                    # Logging size logic
                    total_cnt = 0
                    # Python dictionary iteration
                    for dh_id, id_set in self.m_DeleteDebugSet.items():
                        print(f"[ParserWorld] Parsing remain message EXTRACTDATAINFO size : [{dh_id}],[{len(id_set)}]")
                        total_cnt += len(id_set)
                    print(f"[ParserWorld] Parsing Total remain message EXTRACTDATAINFO size : [{total_cnt}]")
                
                # Reset Timer
                self.set_timer(self.EXTRACTDATAINFO_CHECK_INTERVAL, self.DEBUG_MEMORY_LEAK_EXTRACTDATAINFO)

        # 4. Parsing Raw File Rotation Timeout
        elif reason == self.PARSING_RAW_TIME_OUT:
            self.parsing_raw_file_change()

        # 5. Unknown Reason
        else:
            print(f"[ParserWorld] [CORE_ERROR] Unknown Time Out Reason : {reason}")
            
    def get_rule_type(self):
        """
        C++: int GetRuleType()
        Returns the configured Rule Type (MsgIdentType).
        1: SAMSUNG_BSM, MSAMSUNG_BSM, MOTOROLA_OMCR, SAMSUNG_HLR
        2: SAMSUNG_1XBSS
        3: PCX etc.
        """
        return self.m_MsgIdentType
    
    def send_router_ne_msg(self, ne_msg):
        """
        C++: void SendRouter(AS_CONNECTOR_DATA_T* NeMsg)
        Sends raw connector data to the Router process.
        Currently disabled in C++ source.
        """
        return
        # [Future Implementation]
        # if self.m_RouterConnection.is_connect():
        #     # Assuming ne_msg has a pack() method or similar serialization
        #     self.m_RouterConnection.send_packet(CONNECTOR_DATA, ne_msg)
        # else:
        #     print("[ParserWorld] Router is Not Connect")

    def send_router_parsed_msg(self, parsed_msg):
        """
        C++: void SendRouter(AS_PARSED_DATA_T* ParsedMsg)
        Sends parsed data to the Router process.
        Currently disabled in C++ source.
        """
        return
        # [Future Implementation]
        # if self.m_RouterConnection.is_connect():
        #     self.m_RouterConnection.send_packet(PARSED_DATA, parsed_msg)
        # else:
        #     print("[ParserWorld] Router is Not Connect")
        
    def recv_cmd_init_ne_mapping_rule(self):
        """
        C++: void RecvCmdIntiNeMappingRule()
        Handles the command to initialize (reload) NE Mapping Rules.
        """
        # 룰 변경이 이미 진행 중인지 확인
        if self.m_MappingRuleChangeStatus or self.m_RuleChangeStatus:
            print("[ParserWorld] Now Rule Change progress....")
            return
        else:
            # 룰 변경 상태 플래그 설정
            self.m_MappingRuleChangeStatus = True
            print("[ParserWorld] Receive Cmd Init Ne Mapping Rule")

            # LockManager 생성하여 DataSender 잠금 절차 시작
            self.create_lock_manager()
    
    def recv_cmd_init_parsing_rule(self):
        """
        C++: void RecvCmdInitParsingRule()
        Handles the command to initialize (reload) Parsing Rules.
        """
        # 룰 변경이 이미 진행 중인지 확인 (Parsing Rule 또는 Mapping Rule)
        if self.m_RuleChangeStatus or self.m_MappingRuleChangeStatus:
            print("[ParserWorld] Now Rule Change progress....")
            return
        else:
            # 파싱 룰 변경 상태 플래그 설정
            self.m_RuleChangeStatus = True

            print("[ParserWorld] Receive Cmd Init Parsing Rule")
            
            # LockManager 생성하여 DataSender 잠금 절차 시작
            self.create_lock_manager()
            
    def rule_change(self, change_info):
        """
        C++: void RuleChange(AS_RULE_CHANGE_INFO_T* ChangeInfo)
        Handles the request to change the current Parsing Rule ID.
        """
        print(f"[ParserWorld] Receive Rule Change : RuleId({change_info.RuleId}), MmcIdentType({change_info.MmcIdentType})")

        # 룰 ID가 변경되었는지 확인
        if self.m_RuleId != change_info.RuleId:
            self.m_RuleId = change_info.RuleId
            self.m_MsgIdentType = change_info.MmcIdentType

            # 이미 룰 변경 작업이 진행 중인지 확인
            if self.m_RuleChangeStatus:
                err_msg = f"Now Rule({self.m_RuleId}) Init progress...., Please Rule({change_info.RuleId}) change retry later..."
                
                # 에러 메시지 전송 (Manager)
                self.send_ascii_error(1, err_msg)
                print(f"[ParserWorld] {err_msg}")
                return
            else:
                # 룰 변경 상태로 전환하고 락 매니저 시작
                self.m_RuleChangeStatus = True
                self.create_lock_manager()
    
    def create_lock_manager(self):
        """
        C++: void CreateLockManager()
        Initiates the LockManager to safely pause DataSenders during rule changes.
        """
        # 기존 LockManager가 남아있는지 확인 (비정상 상태)
        if self.m_LockManager:
            print("[ParserWorld] [CORE_ERROR] m_LockManager is not null....something wrong..........")
            # Python에서는 참조를 끊으면 GC가 __del__을 호출하여 리소스를 정리합니다.
            self.m_LockManager = None

        # LockManager 생성 및 시작
        self.m_LockManager = LockManager()
        self.m_LockManager.lock_check()
        
        print("[ParserWorld] Wait Rule Change progress....")
    
    def search_raw_file_change(self):
        """
        C++: void SearchRawFileChange()
        Handles raw message logging file creation and rotation based on date/hour.
        Path: RawDir/HostName/ProcName/YYYYMMDD/ProcName_YYYYMMDDHH.msg
        """
        cur_time = FrTime()
        ne_name = self.m_ProcName.replace("PARSER_", "", 1)
        
        # Base Dir: RawDir/HostName
        base_dir = f"{self.get_raw_dir()}/{AsUtil.get_host_name()}"
        
        try:
            if not os.path.exists(base_dir):
                os.makedirs(base_dir, 0o777)
                
            # Sub Dir: /ProcName
            proc_dir = f"{base_dir}/{ne_name}"
            if not os.path.exists(proc_dir):
                os.makedirs(proc_dir, 0o777)
                
            # Date Dir: /YYYYMMDD
            date_dir = f"{proc_dir}/{cur_time.get_year():04d}{cur_time.get_month():02d}{cur_time.get_day():02d}"
            if not os.path.exists(date_dir):
                os.makedirs(date_dir, 0o777)
                
            # File Name: ProcName_YYYYMMDDHH.msg
            file_name = f"{date_dir}/{ne_name}_{cur_time.get_year():04d}{cur_time.get_month():02d}{cur_time.get_day():02d}{cur_time.get_hour():02d}.msg"
            
            if self.m_SearchRawLogFp:
                self.m_SearchRawLogFp.close()
                self.m_SearchRawLogFp = None
                
            self.m_SearchRawLogFp = open(file_name, "a+") # Append & Read
            print(f"[ParserWorld] Search Raw File Change Success : {file_name}")
            
        except OSError as e:
            print(f"[ParserWorld] [CORE_ERROR] Search Raw Log File Create/Open Error : {e}")
            if self.m_SearchRawLogFp:
                self.m_SearchRawLogFp.close()
                self.m_SearchRawLogFp = None
            return

        # Set Timer for Next Hour
        self.set_timer(cur_time.get_remain_hour_sec(), self.SEARCH_RAW_LOG_TIME_OUT)

    def insert_parsing_data(self, info):
        """
        C++: void InsertParsingData(ExtractDataInfo* Info)
        """
        # (This was already implemented in previous step, ensuring consistency)
        consumers = info.m_IdentRulePtr.m_ConsumerVector
        ref_cnt = 0
        
        for consumer in consumers:
            if consumer in self.m_DataSenderMap:
                ref_cnt += 1
                # Duplicate info for specific consumer
                new_info = info.dup_instance(ref_cnt, consumer)
                self.m_DataSenderMap[consumer].push_extract_data_info(new_info)
            else:
                # print(f"[ParserWorld] DataRouter({consumer}) is not Connected")
                pass

    def create_data_sender(self, data_handler_id):
        """
        C++: bool CreateDataSender(string DataHandlerId)
        """
        if data_handler_id in self.m_DataSenderMap:
            print(f"[ParserWorld] [CORE_ERROR] Already Create DataSender({data_handler_id})")
            return False
            
        conn = DataRouterConnection(data_handler_id)
        sender = DataSender(data_handler_id, conn)
        sender.run() # Start thread (if applicable)
        
        socket_path = self.get_data_router_listen_socket_path(data_handler_id)
        conn.start(socket_path)
        
        conn.set_data_sender(sender, self.m_MappingMgr)
        conn.change_world(sender) # Assuming Conn inherits from EventSrc and needs context
        
        self.m_DataSenderMap[data_handler_id] = sender
        print(f"[ParserWorld] CreateDataSender Success : {data_handler_id}")
        return True

    def destroy_data_sender(self, data_handler_id):
        """
        C++: void DestoryDataSender(string DataHandlerId)
        """
        if data_handler_id not in self.m_DataSenderMap:
            print(f"[ParserWorld] Can't Find Data Sender({data_handler_id})")
            return
            
        sender = self.m_DataSenderMap[data_handler_id]
        sender.clear_extract_data_info_list()
        
        # Signal connection to delete handler
        sender.m_DataRouterConnection.recv_message(DELETE_DATA_HANDLER) 
        # C++ called SendMessage but connection handles it. 
        # In Python we call the handler method directly or use queue if async.
        
        del self.m_DataSenderMap[data_handler_id]
        print(f"[ParserWorld] Destroy Data Sender : {data_handler_id}")

    def data_sender_lock(self):
        """
        C++: void DataSenderLock()
        Acquires locks for all DataSender threads.
        """
        print("[ParserWorld] DataSenderLock Start")
        for dh_id, sender in self.m_DataSenderMap.items():
            print(f"[ParserWorld] DataSenderLock {dh_id}) Try")
            sender.sender_lock()
            print(f"[ParserWorld] DataSenderLock({dh_id}) Success")
        print("[ParserWorld] DataSenderLock End")

    def data_sender_unlock(self):
        """
        C++: void DataSenderUnLock()
        Releases locks for all DataSender threads.
        """
        print("[ParserWorld] DataSenderUnLock Start")
        for dh_id, sender in self.m_DataSenderMap.items():
            sender.sender_unlock()
            print(f"[ParserWorld] DataSenderUnLock({dh_id}) OK")
        print("[ParserWorld] DataSenderUnLock End")

    def get_cur_raw_file_name(self):
        """
        C++: const char* GetCurRawFileName()
        """
        with self.m_RawFileChangeLock:
            return self.m_RawMsgFpFileName
    
    def data_sender_lock_finish(self):
        """
        C++: void DataSenderLockFinish()
        Called when lock is acquired. Performs rule init and data re-identification.
        """
        tmp_extract_data_info_list = []
        
        print("[ParserWorld] DataSenderLockFinish")
        
        # 1. Drain queues if rule changing
        if self.m_RuleChangeStatus:
            for dh_id, sender in self.m_DataSenderMap.items():
                print(f"[ParserWorld] Start data recollection and reidentfy in DataSender({dh_id}) thread")
                while True:
                    ptr = sender.get_end_extract_data_info()
                    if ptr:
                        if ptr.m_RefCnt == 1:
                            tmp_extract_data_info_list.append(ptr)
                        else:
                            # ptr destroyed by GC
                            pass
                    else:
                        break
                print(f"[ParserWorld] End data recollection in DataSender({dh_id}) thread")
            print("[ParserWorld] End data recollection in DataSender all thread")

        if self.m_MappingRuleChangeStatus:
            self.init_ne_mapping_rule()

        # 2. Unlock
        self.data_sender_unlock()

        # 3. Re-Identify & Process
        if self.m_RuleChangeStatus:
            # Re-Init Rules
            self.init_ident_manager()
            
            # Reprocess drained items
            for ptr in tmp_extract_data_info_list:
                if ptr.m_MsgId != RAW_MSG_CHANGE_FLAG:
                    if self.m_IdentManager:
                        try:
                            self.m_RawMsgFp.seek(ptr.m_FilePos)
                            data = self.m_RawMsgFp.read(ptr.m_MsgSize)
                            
                            if len(data) == ptr.m_MsgSize:
                                msg_buf = data.decode('utf-8', errors='ignore')
                                info = self.m_IdentManager.data_identify(msg_buf)
                                
                                if info and info.m_IdentRulePtr and info.m_IdentRulePtr.m_ConsumerVector:
                                    ptr.m_IdentRulePtr = info.m_IdentRulePtr
                                    ptr.m_IdentIdString = info.m_IdentIdString
                                    self.insert_parsing_data(ptr)
                            else:
                                print(f"[ParserWorld] [CORE_ERROR] Msg Read Error -- Read: {len(data)}, Expected: {ptr.m_MsgSize}")
                        except Exception as e:
                            print(f"[ParserWorld] [CORE_ERROR] File Error: {e}")
                    else:
                        print("[ParserWorld] [CORE_ERROR] Drop Recollection... IdentManager Not Init")
                else:
                    self.insert_dummy_instance()
            
            # Reprocess Temporary Buffer (During rule change)
            self.m_RawMsgFp.seek(0, 2) # Seek End
            
            if self.m_RawMsgTmpFp:
                self.m_RawMsgTmpFp.seek(0)
                
                # Logic for temporary msg list
                while self.m_TemporaryMsgInfoList:
                    # In Python tmp list stores dicts (as implemented in parsing method)
                    # or Objects. Let's assume we fetch object/dict.
                    
                    ptr_info = self.m_TemporaryMsgInfoList.pop(0)
                    # ptr_info is dict: msg_id, ne_id, port_no, file_pos, msg_len
                    
                    try:
                        self.m_RawMsgTmpFp.seek(ptr_info['file_pos'])
                        data = self.m_RawMsgTmpFp.read(ptr_info['msg_len'])
                        
                        if len(data) == ptr_info['msg_len']:
                            msg_buf = data.decode('utf-8', errors='ignore')
                            self.parsing(ptr_info['msg_id'], ptr_info['ne_id'], ptr_info['port_no'], 
                                         msg_buf, len(msg_buf), 0, True)
                    except Exception as e:
                        print(f"[ParserWorld] [CORE_ERROR] Tmp File Read Error: {e}")

                self.m_RawMsgFp.write("\n--Temp Msg End--------------------------------------------------------\n")
                self.m_RawMsgFp.flush()
            else:
                print(f"[ParserWorld] Tmp file is null, Temporary Msg size : {len(self.m_TemporaryMsgInfoList)}")

        # Cleanup
        self.m_LockManager = None # GC handles deletion
        self.check_data_handler_info()
        
        if self.m_RawMsgTmpFp:
            self.m_RawMsgTmpFp.close()
            self.m_RawMsgTmpFp = None
            if os.path.exists(self.m_RawMsgTmpFileName):
                os.remove(self.m_RawMsgTmpFileName)
            self.m_RawMsgTmpFileName = ""

    def data_sender_lock_finish2(self):
        """
        C++: void DataSenderLockFinish2()
        Alternative finish method (called via Pipe). Similar logic but delegated re-identify.
        """
        print("[ParserWorld] DataSenderLockFinish2")
        tmp_rule_change_status = self.m_RuleChangeStatus

        if tmp_rule_change_status:
            self.init_ident_manager()
            
            for dh_id, sender in self.m_DataSenderMap.items():
                if self.m_IdentManager:
                    print(f"[ParserWorld] Start data reidentfy in DataSender({dh_id})")
                    sender.re_identify(self.m_RawMsgFp, self.m_IdentManager)
                else:
                    print("[ParserWorld] [CORE_ERROR] Drop reidentfy... IdentManager Not Init")
                    sender.clear_extract_data_info_list()
            print("[ParserWorld] End data reidentfy in DataSender all thread")

        if self.m_MappingRuleChangeStatus:
            self.init_ne_mapping_rule()

        self.data_sender_unlock()

        if tmp_rule_change_status:
            self.m_RawMsgFp.seek(0, 2)
            
            # Reprocess Temporary (Common Logic)
            if self.m_RawMsgTmpFp:
                self.m_RawMsgTmpFp.seek(0)
                while self.m_TemporaryMsgInfoList:
                    ptr_info = self.m_TemporaryMsgInfoList.pop(0)
                    try:
                        self.m_RawMsgTmpFp.seek(ptr_info['file_pos'])
                        data = self.m_RawMsgTmpFp.read(ptr_info['msg_len'])
                        
                        if len(data) == ptr_info['msg_len']:
                            msg_buf = data.decode('utf-8', errors='ignore')
                            self.parsing(ptr_info['msg_id'], ptr_info['ne_id'], ptr_info['port_no'], 
                                         msg_buf, len(msg_buf), 0, True)
                    except Exception as e:
                        print(f"[ParserWorld] [CORE_ERROR] Tmp File Read Error: {e}")

                self.m_RawMsgFp.write("\n--Temp Msg End--------------------------------------------------------\n")
                self.m_RawMsgFp.flush()

        self.m_LockManager = None
        self.check_data_handler_info()

        if self.m_RawMsgTmpFp:
            self.m_RawMsgTmpFp.close()
            self.m_RawMsgTmpFp = None
            if os.path.exists(self.m_RawMsgTmpFileName):
                os.remove(self.m_RawMsgTmpFileName)
            self.m_RawMsgTmpFileName = ""

    def recv_data_handler_info(self, info):
        """
        C++: void RecvDataHandlerInfo(AS_DATA_HANDLER_INFO_T* Info)
        """
        print(f"[ParserWorld] Recv DataHandler Info : {info.DataHandlerId}, Status: {info.SettingStatus}")

        if self.m_LockManager:
            print("[ParserWorld] Waiting DataSender Lock finish, later processing...")
            # Deep copy info and store
            self.m_TmpDataHandlerInfoList.append(copy.deepcopy(info))
            return

        # Simplified Logic for Python (Dictionary Update)
        # DELETE / UPDATE / CREATE logic
        if info.SettingStatus == START:
            self.create_data_sender(info.DataHandlerId)
        elif info.SettingStatus == STOP:
            self.destroy_data_sender(info.DataHandlerId)

    def check_data_handler_info(self):
        """
        C++: void CheckDatahandlerInfo()
        Process pending DataHandler requests after lock finish.
        """
        print(f"[ParserWorld] Parser CheckDatahandlerInfo cnt : {len(self.m_TmpDataHandlerInfoList)}")
        
        for info in self.m_TmpDataHandlerInfoList:
            self.recv_data_handler_info(info)
        
        self.m_TmpDataHandlerInfoList.clear()

    def get_data_router_listen_socket_path(self, session_name):
        return f"{self.get_unix_socket_dir()}/DATAROUTER_LISTEN_{session_name}"
    
    def get_msg_logging(self):
        """
        C++: bool GetMsgLogging()
        """
        return self.m_IsMsgLogging

    def check_data_handler_info(self):
        """
        C++: void CheckDatahandlerInfo()
        Processes buffered DataHandlerInfo requests (e.g., received during lock).
        """
        print(f"[ParserWorld] Parser CheckDatahandlerInfo cnt : {len(self.m_TmpDataHandlerInfoList)}")

        # Process buffered items
        for info in self.m_TmpDataHandlerInfoList:
            self.recv_data_handler_info(info)
            # Python GC handles deletion
            
        self.m_TmpDataHandlerInfoList.clear()

    def fputs(self, data, file_ptr):
        """
        C++: void Fputs(char* Data, FILE*& FilePtr)
        Wrapper for file writing with error handling.
        """
        if not file_ptr:
            return

        try:
            file_ptr.write(data)
            # Flush is separate in C++, mimicking behavior
        except IOError as e:
            host_name = AsUtil.get_host_name()
            err_msg = f"-- Disk Write Error({host_name}:{e})!!!!!!!!!!"
            print(f"[ParserWorld] [CORE_ERROR] {err_msg}")
            
            self.send_ascii_error(1, err_msg)

    def fflush(self, file_ptr):
        """
        C++: void Fflush(FILE*& FilePtr)
        """
        if file_ptr:
            try:
                file_ptr.flush()
            except IOError:
                pass

    def get_default_buffer_size(self):
        """
        C++: int GetDefaultBufferSize()
        """
        return self.m_DefaultBufferSize

    def resize_msg_buf(self, cur_buf, cur_size, new_size):
        """
        C++: void ResizeMsgBuf(char*& CurBuf, int& CurSize, int NewSize)
        Resizes the buffer if the new size is larger.
        
        [Python Difference]
        Since Python arguments are passed by assignment (and integers are immutable),
        we cannot modify 'CurBuf' and 'CurSize' variables of the caller directly via arguments.
        Instead, this method **returns** the (potentially new) buffer and size.
        
        Usage:
            self.m_MsgBuf, self.m_BufSize = world.resize_msg_buf(self.m_MsgBuf, self.m_BufSize, new_len)
        """
        if cur_size < new_size:
            print(f"[ParserWorld] Default Msg Buf resize : old({cur_size} byte), new({new_size} byte)")
            
            # Create new buffer (bytearray for mutability)
            new_buf = bytearray(new_size)
            
            # If we needed to preserve data, we would copy here. 
            # C++ implementation creates a fresh buffer (memset 0 implies no copy needed or overwriting).
            
            return new_buf, new_size
            
        return cur_buf, cur_size
