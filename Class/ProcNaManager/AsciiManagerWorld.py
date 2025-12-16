import sys
import os
import threading
import time
import copy
import signal

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
from Class.Util.FrSshUtil import FrSshUtil

# Manager Imports (Lazy Import pattern for circular dependency safety)
try:
    from Class.ProcNaManager.DataRouterConnMgr import DataRouterConnMgr
    from Class.ProcNaManager.ParserConnMgr import ParserConnMgr
    from Class.ProcNaManager.ConnectorConnMgr import ConnectorConnMgr
    from Class.ProcNaManager.RouterConnMgr import RouterConnMgr
    from Class.ProcNaManager.LogRouterConnMgr import LogRouterConnMgr
    from Class.ProcNaManager.ServerConnection import ServerConnection
    from Class.ProcNaManager.AsciiManagerType import MmcPublishSetQueue, MmcPublishSet
except ImportError:
    pass

class AsciiManagerWorld(AsWorld):
    """
    AsciiManager의 메인 월드 클래스.
    서버 연결, 하위 프로세스 관리, MMC 라우팅 등을 수행합니다.
    """
    _instance = None

    # Constants (Macros from .h)
    MGR_UNIX_PARSER             = "MGR_PARSER_LISTEN"
    MGR_UNIX_CONNECTOR          = "MGR_CONNECTOR_LISTEN"
    MGR_UNIX_ROUTER             = "MGR_ROUTER_LISTEN"
    MGR_UNIX_LOG_ROUTER         = "MGR_LOG_ROUTER_LISTEN"
    MGR_UNIX_DATAROUTER         = "MGR_DATAROUTER_LISTEN"
    UNIX_PARSER_LISTEN_PREFIX   = "/PARSER_LISTEN_"
    UNIX_ROUTER_LISTEN_PREFIX   = "/ROUTER_LISTEN_"
    UNIX_DATAROUTER_LISTEN_PREFIX = "/DATAROUTER_LISTEN_"

    def __init__(self):
        """
        C++: AsciiManagerWorld()
        """
        super().__init__()
        AsciiManagerWorld._instance = self
        
        self.m_MsgId = 0
        
        # MMC Publish Queues (Priority 0, 1)
        self.m_MmcPublishSetQueueList = []
        for i in range(2):
            self.m_MmcPublishSetQueueList.append(MmcPublishSetQueue(i))
            
        self.m_MMCPublishThreadStatus = True
        self.m_MMCPublishThread = None

        # --- Connection Managers ---
        self.m_DataRouterConnMgr = DataRouterConnMgr()
        self.m_ParserConnMgr = ParserConnMgr()
        self.m_ConnectorConnMgr = ConnectorConnMgr()
        self.m_RouterConnMgr = RouterConnMgr()
        self.m_LogRouterConnMgr = LogRouterConnMgr()
        
        # Server Connection (Connects to AsciiServer)
        self.m_ServerConnection = ServerConnection(None)

        # --- Config & State ---
        self.m_ProcName = ""
        self.m_ServerAddress = ""
        self.m_ServerPort = 0
        self.m_RouterListenPort = 0
        self.m_LogRouterListenPort = 0
        
        # Map: ProcessId -> AsProcControlT (설정 정보 저장)
        self.m_ProcessInfo = {} 
        # List: AsCmdOpenPortT (열린 포트 정보)
        self.m_CmdOpenPortList = [] 
        # Map: DataHandlerId -> AsDataHandlerInfoT
        self.m_DataHandlerInfoMap = {} 
        
        self.m_ChildProcManager = ChildProcessManager()
        self.m_SystemInfo = AsSystemInfoT() 

    def __del__(self):
        """
        C++: ~AsciiManagerWorld()
        """
        self.m_MMCPublishThreadStatus = False
        if self.m_MMCPublishThread:
            self.m_MMCPublishThread.join()
        
        self.m_MmcPublishSetQueueList.clear()
        super().__del__()

    @staticmethod
    def get_instance():
        return AsciiManagerWorld._instance

    # -------------------------------------------------------
    # AppStart & Initialization
    # -------------------------------------------------------
    def app_start(self, argc, argv):
        """
        C++: bool AppStart(int Argc, char** Argv)
        """
        # 1. Config & System Check
        if not self.init_config():
            print(f"[AsciiManagerWorld] [CORE_ERROR] Env Init Error")
            return False

        if not self.ascii_system_dir_check():
            print("[AsciiManagerWorld] [CORE_ERROR] AsciiSystemDirCheck ERROR")
            return False

        # 2. Logger Setup
        FrLogger.get_instance().enable("AsciiManager", level=3)
        FrLogger.get_instance().enable("Common", level=1)

        # 3. Argument Parsing
        if argc != 7:
            print(f"[Usage] {argv[0]} -name Manager1 -svrip 172.21.90.90 -svrport 3434")
            return False

        parser = FrArgParser(argv)
        self.m_ProcName = parser.get_value(ARG_NAME)
        self.m_ServerAddress = parser.get_value(ARG_SVR_IP)
        self.m_ServerPort = int(parser.get_value(ARG_SVR_PORT) or "0")

        # 4. Load Ports from Env
        self.m_RouterListenPort = int(self.get_env_value(ASCII_MANAGER, "router_listen_port") or "0")
        self.m_LogRouterListenPort = int(self.get_env_value(ASCII_MANAGER, "log_router_listen_port") or "0")

        self.set_log_file(ASCII_MANAGER)
        self.set_system_info(ASCII_MANAGER, self.m_ProcName)

        print("[AsciiManagerWorld] Netadapter Manager Start..............")

        if not self.config_value_check():
            return False

        if not self.init_manager(argc, argv):
            print("[AsciiManagerWorld] Manager Init Fail")
            return False

        print(f"[AsciiManagerWorld] Alive Check Interval : {self.get_proc_alive_check_time()}")
        print(f"[AsciiManagerWorld] Alive Check Limit Cnt : {self.get_alive_check_limit_cnt()}")

        return True

    def init_manager(self, argc, argv):
        """
        C++: bool InitManager(int Argc, char** Argv)
        서버 연결, 리스닝 소켓 생성, 초기 프로세스 실행, 스레드 시작
        """
        # 1. Connect to Server
        if not self.m_ServerConnection.connect(self.m_ServerAddress, self.m_ServerPort):
            print(f"[AsciiManagerWorld] [CORE_ERROR] Server({self.m_ServerAddress}, {self.m_ServerPort}) Connect Error")
            return False

        # 2. Create Unix Domain Sockets
        unix_dir = self.get_unix_socket_dir()

        if not self.m_DataRouterConnMgr.init_unix_socket(f"{unix_dir}/{self.MGR_UNIX_DATAROUTER}"):
             print(f"[AsciiManagerWorld] [CORE_ERROR] Listen Error For DataHandler")
             return False

        if not self.m_ParserConnMgr.init_unix_socket(f"{unix_dir}/{self.MGR_UNIX_PARSER}"):
             print(f"[AsciiManagerWorld] [CORE_ERROR] Listen Error For Parser")
             return False

        if not self.m_ConnectorConnMgr.init_unix_socket(f"{unix_dir}/{self.MGR_UNIX_CONNECTOR}"):
             print(f"[AsciiManagerWorld] [CORE_ERROR] Listen Error For Connector")
             return False

        if not self.m_RouterConnMgr.init_unix_socket(f"{unix_dir}/{self.MGR_UNIX_ROUTER}"):
             print(f"[AsciiManagerWorld] [CORE_ERROR] Listen Error For Router")
             return False

        if not self.m_LogRouterConnMgr.init_unix_socket(f"{unix_dir}/{self.MGR_UNIX_LOG_ROUTER}"):
             print(f"[AsciiManagerWorld] [CORE_ERROR] Listen Error For Log Router")
             return False

        # 3. Start Default Processes
        self.start_proc_by_type(ASCII_ROUTER, "Router")
        self.start_proc_by_type(ASCII_LOG_ROUTER, "LogRouter")

        # 4. Start MMC Thread
        try:
            self.m_MMCPublishThread = threading.Thread(target=self.mmc_publish_manager, daemon=True)
            self.m_MMCPublishThread.start()
            print("[AsciiManagerWorld] Thread Create Success For MMCPublish Management")
        except Exception as e:
            print(f"[AsciiManagerWorld] [CORE_ERROR] Thread Create Fail : {e}")
            return False

        # 5. Handshake with Server
        self.m_ServerConnection.set_session_identify(ASCII_MANAGER, self.m_ProcName, self.get_proc_alive_check_time())

        # 6. Rule Sync
        self.parsing_rule_copy()
        self.mapping_rule_copy()

        self.m_ServerConnection.send_ack(MANAGER_INIT_END, 1)

        # 7. Send Info to Server
        router_port_info = AsRouterPortInfoT()
        router_port_info.RouterPortNo = self.m_RouterListenPort
        body = router_port_info.pack()
        self.m_ServerConnection.packet_send(PacketT(ROUTER_PORT_INFO, len(body), body))

        body_sys = self.m_SystemInfo.pack()
        self.m_ServerConnection.packet_send(PacketT(AS_SYSTEM_INFO, len(body_sys), body_sys))

        # 8. Send Process Info
        proc_info = AsProcessStatusT()
        proc_info.Pid = os.getpid()
        proc_info.ProcessId = self.m_ProcName
        proc_info.Status = START
        proc_info.ProcessType = ASCII_MANAGER
        self.send_process_info(proc_info)

        # 9. SockMgr (Optional)
        sock_mgr_port = int(self.get_env_value(ASCII_MANAGER, "sock_mgr_listen_port") or "0")
        if sock_mgr_port > 3000:
            # self.enable_sock_mgr_session("ManagerSockMgrListener", sock_mgr_port)
            pass

        return True

    # -------------------------------------------------------
    # Process Start Logic
    # -------------------------------------------------------
    def start_proc(self, proc_ctl):
        """
        C++: void StartProc(AS_PROC_CONTROL_T* ProcCtl)
        설정 정보를 받아 프로세스 시작 (Parser/Connector 등)
        """
        print(f"[AsciiManagerWorld] StartProc Request : {proc_ctl.ProcessId}, Delay: {proc_ctl.DelayTime}")
        
        # 설정 정보 저장 (Map Insert)
        self.m_ProcessInfo[proc_ctl.ProcessId] = copy.deepcopy(proc_ctl)
        
        self.start_proc_by_type(ASCII_PARSER, proc_ctl.ProcessId, proc_ctl.RuleId, 
                                proc_ctl.MmcIdentType, proc_ctl.CmdResponseType, 
                                0, proc_ctl.LogCycle) # DelayTime은 C++에서 0으로 초기화됨

    def start_proc_by_type(self, proc_type, name, rule_id="", msg_ident_type=1, cmd_response_type=0, delay_time=0, log_cycle=0):
        """
        C++: void StartProc(int ProcType, string Name, ...)
        실제 프로세스 실행 (Fork/Exec)
        """
        args = []
        proc_bin_name = AsUtil.get_process_type_string(proc_type)
        bin_path = f"{self.get_bin_dir()}/{proc_bin_name}" 
        unix_dir = self.get_unix_socket_dir()
        
        # Common Arguments
        args.append(bin_path) # Argv[0]
        args.append(ARG_NAME) # -name

        pid = -1

        if proc_type == ASCII_PARSER:
            enc_name = self.parser_id_encode(name)
            args.append(enc_name)
            args.append(ARG_MANAGER_SOCKET_PATH)
            args.append(f"{unix_dir}/{self.MGR_UNIX_PARSER}")
            args.append(ARG_RULEID); args.append(rule_id)
            args.append(ARG_DELAY_TIME); args.append(str(delay_time))
            args.append(ARG_CMD_IDENT_TYPE); args.append(str(msg_ident_type))
            
            pid = self.m_ParserConnMgr.start_proc(enc_name, args)

        elif proc_type == ASCII_CONNECTOR:
            enc_name = self.connector_id_encode(name)
            # print(f"Connector Name : {enc_name}")
            args.append(enc_name)
            args.append(ARG_MANAGER_SOCKET_PATH)
            args.append(f"{unix_dir}/{self.MGR_UNIX_CONNECTOR}")
            args.append(ARG_CMD_RESPONSE_TYPE); args.append(str(cmd_response_type))
            if log_cycle == 1:
                args.append(ARG_LOG_CYCLE)
                args.append(ARG_LOG_HOUR)
                
            pid = self.m_ConnectorConnMgr.start_proc(enc_name, args)

        elif proc_type == ASCII_ROUTER:
            args.append(name)
            args.append(ARG_MANAGER_SOCKET_PATH)
            args.append(f"{unix_dir}/{self.MGR_UNIX_ROUTER}")
            args.append("-portno"); args.append(str(self.m_RouterListenPort))
            args.append("-socketpathforparser")
            args.append(self.get_router_listen_socket_path(name))
            
            pid = self.m_RouterConnMgr.start_proc(name, args)

        elif proc_type == ASCII_LOG_ROUTER:
            args.append(name)
            args.append(ARG_MANAGER_SOCKET_PATH)
            args.append(f"{unix_dir}/{self.MGR_UNIX_LOG_ROUTER}")
            args.append(ARG_PORT_NO); args.append(str(self.m_LogRouterListenPort))
            
            pid = self.m_LogRouterConnMgr.start_proc(name, args)

        elif proc_type == ASCII_DATA_ROUTER:
            args.append(name)
            args.append(ARG_MANAGER_SOCKET_PATH)
            args.append(f"{unix_dir}/{self.MGR_UNIX_DATAROUTER}")
            
            pid = self.m_DataRouterConnMgr.start_proc(name, args)

        else:
            print(f"[AsciiManagerWorld] [CORE_ERROR] Unknown Process Type : {proc_type}")
            return

        # Check PID
        if pid == -1:
            msg = f"Forking the process in {AsUtil.get_process_type_string(ASCII_MANAGER)}({self.m_ProcName}) fails."
            self.send_ascii_error(1, msg)
        else:
            self.add_pid(pid)
            print(f"[AsciiManagerWorld] Process Execute : {AsUtil.get_process_type_string(proc_type)}({name}, pid:{pid})")

    # -------------------------------------------------------
    # Rule Management
    # -------------------------------------------------------
    def parsing_rule_copy(self):
        """
        C++: bool ParsingRuleCopy()
        룰 파일을 복사합니다. (시스템 명령 호출)
        """
        cmd = "~/NAA/Bin/RuleCopy -name RuleCopy -type 0"
        print(f"[AsciiManagerWorld] RuleCopy : {cmd}")
        
        retry = 0
        while True:
            if retry < 2:
                ret = os.system(cmd)
                print(f"[AsciiManagerWorld] ParsingRule Rule RCopy Result : {ret}")
                if ret != 0:
                    print("[AsciiManagerWorld] [CORE_ERROR] PARSING RULE DOWN Fail")
                    retry += 1
                    continue
                else:
                    break
            else:
                print("[AsciiManagerWorld] [CORE_ERROR] PARSING RULE DOWN RETRY FAIL")
                break
        
        print("[AsciiManagerWorld] Rule Down Success")
        return True

    def mapping_rule_copy(self):
        """
        C++: bool MappingRuleCopy()
        """
        cmd = "~/NAA/Bin/RuleCopy -name RuleCopy -type 1"
        print(f"[AsciiManagerWorld] Mapping Rule Copy : {cmd}")
        
        retry = 0
        while True:
            if retry < 2:
                ret = os.system(cmd)
                print(f"[AsciiManagerWorld] Mapping Rule RCopy Result : {ret}")
                if ret != 0:
                    print("[AsciiManagerWorld] [CORE_ERROR] Mapping Down Fail")
                    retry += 1
                    continue
                else:
                    break
            else:
                print("[AsciiManagerWorld] [CORE_ERROR] Mapping Rule Down Retry Error")
                break
                
        print("[AsciiManagerWorld] Mapping Down Success")
        return True

    # -------------------------------------------------------
    # MMC Command Handling
    # -------------------------------------------------------
    def send_mmc_command(self, mmc_com):
        """
        C++: void SendMMCCommand(AS_MMC_PUBLISH_T* MMCCom)
        MMC 명령을 받아 적절한 Connector를 찾아 큐에 삽입하거나 에러를 반환합니다.
        """
        result = False
        print(f"[AsciiManagerWorld] Receive MMC Command : msgid({mmc_com.id}), ne({mmc_com.ne}), mmc({mmc_com.mmc})")

        # 1. 명령어 필터링 (Blacklist)
        # 예시: "DIS-MS:", "RTRV-MS-INF:" 등
        cmd_str = mmc_com.mmc.strip()
        blocked_cmds = ["DIS-MS:", "DIS-3GMS:", "RTRV-MS-INF:", "DIS-MS MDN"]
        
        is_blocked = any(cmd_str.startswith(b) for b in blocked_cmds)

        if is_blocked:
            res = AsMmcResultT()
            res.id = mmc_com.id
            res.resultMode = R_ERROR
            res.result = " 감사/권고 사항으로 인하여 Command를 발행할 수 없습니다."
            self.send_command_response(res)
            return

        # 2. 적절한 Port 찾기 (Open Port List 검색)
        for port_info in self.m_CmdOpenPortList:
            if port_info.EquipId == mmc_com.ne:
                result = True
                if port_info.CommandPortFlag == 1:
                    # 큐에 삽입
                    new_mmc = copy.deepcopy(mmc_com)
                    self.insert_mmc_publish_set(MmcPublishSet(new_mmc, port_info.ConnectorId))
                    return

        # 3. 실패 처리
        res = AsMmcResultT()
        res.id = mmc_com.id
        res.resultMode = R_ERROR
        if result:
            msg = f"The NE({mmc_com.ne}) is found, but has no command port."
        else:
            msg = f"The NE({mmc_com.ne}) is not found."
        
        res.result = msg
        print(f"[AsciiManagerWorld] {msg}")
        self.send_command_response(res)

    def insert_mmc_publish_set(self, mmc_com_set):
        """
        C++: void InsertMMCPublishSet(MmcPublishSet* MMCComSet)
        """
        if mmc_com_set.m_MmcPublish.responseMode == RESPONSE:
            self.m_MmcPublishSetQueueList[0].insert_mmc_publish_set(mmc_com_set)
        else:
            self.m_MmcPublishSetQueueList[1].insert_mmc_publish_set(mmc_com_set)

    def mmc_publish_manager(self):
        """
        C++: void* MMCPublishManager(void* Arg)
        MMC 전송 스레드. 큐에서 명령을 꺼내 ConnectorConnMgr를 통해 전송.
        """
        while self.m_MMCPublishThreadStatus:
            processed_any = False
            
            for queue in self.m_MmcPublishSetQueueList:
                mmc_set = queue.get_mmc_publish_set()
                if not mmc_set:
                    continue
                
                processed_any = True
                print(f"[AsciiManagerWorld] MmcPublish Queue Send Command : ne({mmc_set.m_MmcPublish.ne}), mmc({mmc_set.m_MmcPublish.mmc})")
                
                # Send via ConnectorConnMgr
                if self.m_ConnectorConnMgr.send_mmc_command(mmc_set.m_ConnectorId, mmc_set.m_MmcPublish):
                    print(f"[AsciiManagerWorld] MMC Send Success")
            
            # Idle 시 Sleep
            if not processed_any:
                time.sleep(0.07) # 70ms

    def send_command_response(self, mmc_result):
        self.m_ServerConnection.send_command_response(mmc_result)

    # -------------------------------------------------------
    # Process & Status Control
    # -------------------------------------------------------
    def recv_process_control(self, proc_ctl):
        """
        C++: void RecvProcessControl(AS_PROC_CONTROL_T* ProcCtl)
        서버로부터 프로세스 제어 명령 수신 (Start/Stop)
        """
        print(f"[AsciiManagerWorld] Recv Process Control : {proc_ctl.ProcessId}, Status: {proc_ctl.Status}")
        
        proc_type = proc_ctl.ProcessType
        
        if proc_type in [ASCII_PARSER, ASCII_CONNECTOR]:
            if proc_ctl.Status == START:
                if proc_ctl.ProcessId in self.m_ProcessInfo:
                    self.send_ascii_error(1, f"The process({proc_ctl.ProcessId}) has already been being executed.")
                    return
                self.start_proc(proc_ctl)
                
            elif proc_ctl.Status == STOP:
                if proc_ctl.ProcessId not in self.m_ProcessInfo:
                    self.send_ascii_error(1, f"The process({proc_ctl.ProcessId}) has not been executed.")
                    return
                
                del self.m_ProcessInfo[proc_ctl.ProcessId]
                
                # Remove from Port List
                self.m_CmdOpenPortList = [p for p in self.m_CmdOpenPortList if p.ConnectorId != proc_ctl.ProcessId]
                
                # Stop Logic
                self.m_ParserConnMgr.stop_process(self.parser_id_encode(proc_ctl.ProcessId))
                self.m_ConnectorConnMgr.stop_process(self.connector_id_encode(proc_ctl.ProcessId))

    def recv_session_control(self, session_ctl):
        """
        C++: void RecvSessionControl(AS_SESSION_CONTROL_T* SessionCtl)
        """
        if session_ctl.Status == STOP:
            enc_id = self.connector_id_encode(session_ctl.ConnectorId)
            session_ctl.ConnectorId = enc_id
            
            # Remove from Port List based on Sequence/ID
            # (Simplified logic)
            self.m_CmdOpenPortList = [p for p in self.m_CmdOpenPortList if p.Sequence != session_ctl.Sequence]
            
            self.m_ConnectorConnMgr.send_session_control(session_ctl)

    def process_dead(self, proc_type, name, pid):
        """
        C++: void ProcessDead(int ProcessType, string ProcessName, int Pid)
        """
        msg = f"The {AsUtil.get_process_type_string(proc_type)}({name}) is killed abnormal."
        self.send_ascii_error(1, msg)
        
        # Core file handling (omitted or use simple move)
        # os.system(f"mv core core_{pid}_{name}")
        
        self.remove_pid(pid)
        
        # Restart Logic
        if proc_type in [ASCII_CONNECTOR, ASCII_PARSER]:
            decoded_name = self.connector_id_decode(name) # Or Parser decode, same logic
            
            if decoded_name in self.m_ProcessInfo:
                info = self.m_ProcessInfo[decoded_name]
                
                # Status flag update logic (simplified)
                if proc_type == ASCII_CONNECTOR:
                    # Update status, remove ports
                    self.m_CmdOpenPortList = [p for p in self.m_CmdOpenPortList if p.ConnectorId != decoded_name]
                
                # Restart
                self.start_proc_by_type(proc_type, info.ProcessId, info.RuleId, info.MmcIdentType, info.CmdResponseType, 0, info.LogCycle)
                
        elif proc_type == ASCII_ROUTER:
            self.start_proc_by_type(ASCII_ROUTER, "Router")
        elif proc_type == ASCII_LOG_ROUTER:
            self.start_proc_by_type(ASCII_LOG_ROUTER, "LogRouter")
        elif proc_type == ASCII_DATA_ROUTER:
            # DataRouter restart logic based on DataHandlerInfoMap
            pass

    # -------------------------------------------------------
    # Info Exchange
    # -------------------------------------------------------
    def send_cmd_open_info(self, port_info):
        """
        C++: void SendCmdOpenInfo(AS_CMD_OPEN_PORT_T* PortInfo)
        """
        AsUtil.cmd_open_port_display(port_info)
        
        # Encode ID
        port_info.ConnectorId = self.connector_id_encode(port_info.ConnectorId)
        
        if self.m_ConnectorConnMgr.send_cmd_open_info(port_info):
            self.m_CmdOpenPortList.append(copy.deepcopy(port_info))

    def set_parser_proc_status(self, session_name):
        decoded = self.parser_id_decode(session_name)
        if decoded in self.m_ProcessInfo:
            # Update status logic
            return True
        return False

    def set_connector_proc_status(self, session_name):
        decoded = self.connector_id_decode(session_name)
        if decoded in self.m_ProcessInfo:
            # Trigger Open Port logic if Parser is ready
            # (Simplification: Just request port info from Server)
            self.m_ServerConnection.connector_port_info_request(decoded)
            return True
        return False

    def router_start(self, router_name):
        self.m_ParserConnMgr.send_router_conn_info(router_name)

    def recv_cmd_parsing_rule_down(self):
        if self.parsing_rule_copy():
            self.m_ParserConnMgr.send_cmd_rule_down()

    def recv_cmd_mapping_rule_down(self):
        if self.mapping_rule_copy():
            self.m_ParserConnMgr.send_cmd_mapping_rule_down()

    def parser_rule_change(self, change_info):
        # Update Info in Map
        if change_info.ProcessId in self.m_ProcessInfo:
            self.m_ProcessInfo[change_info.ProcessId].RuleId = change_info.RuleId
            self.m_ProcessInfo[change_info.ProcessId].MmcIdentType = change_info.MmcIdentType
            
        enc_id = self.parser_id_encode(change_info.ProcessId)
        change_info.ProcessId = enc_id
        
        self.m_ParserConnMgr.parser_rule_change(change_info)

    def recv_data_handler_info(self, info):
        """
        C++: void RecvDataHandlerInfo(AS_DATA_HANDLER_INFO_T* Info)
        """
        # Logic to update m_DataHandlerInfoMap and start/stop DataRouter processes
        if info.DataHandlerId not in self.m_DataHandlerInfoMap:
            self.m_DataHandlerInfoMap[info.DataHandlerId] = copy.deepcopy(info)
        else:
            # Update
            self.m_DataHandlerInfoMap[info.DataHandlerId] = copy.deepcopy(info)
            
        if info.SettingStatus == START:
            self.start_proc_by_type(ASCII_DATA_ROUTER, info.DataHandlerId)
        elif info.SettingStatus == STOP:
            self.m_DataRouterConnMgr.stop_process(info.DataHandlerId)
            
        self.m_ParserConnMgr.send_data_handler_info(info)

    def recv_init_info(self, init_info):
        self.m_DataRouterConnMgr.recv_init_info(init_info)

    def send_process_info(self, proc_info):
        proc_info.ManagerId = self.m_ProcName
        self.m_ServerConnection.send_process_info(proc_info)

    def send_ascii_error(self, priority, fmt, *args):
        msg = fmt
        if args: msg = fmt % args
        err = AsAsciiErrorMsgT()
        err.Priority = priority
        err.ErrMsg = msg
        self.m_ServerConnection.send_ascii_error(err)

    def send_log_status(self, status):
        # C++: sprintf(logs, "%s,%s", GetProcName(), Status->logs)
        status.logs = f"{self.m_ProcName},{status.logs}"
        self.m_ServerConnection.send_log_status(status)

    def receive_cmd_log_status_change(self, log_ctl):
        proc_type = log_ctl.ProcessType
        if proc_type == ASCII_MANAGER:
            pass # Self log logic
        elif proc_type == ASCII_CONNECTOR:
            self.m_ConnectorConnMgr.send_cmd_log_status_change(log_ctl, log_ctl.ProcessId)
        elif proc_type == ASCII_PARSER:
            self.m_ParserConnMgr.send_cmd_log_status_change(log_ctl, log_ctl.ProcessId)
        # ... others ...

    # -------------------------------------------------------
    # Utilities
    # -------------------------------------------------------
    def parser_id_encode(self, name): return "PARSER_" + name
    def parser_id_decode(self, name): return name.replace("PARSER_", "", 1)
    def connector_id_encode(self, name): return "CONNECTOR_" + name
    def connector_id_decode(self, name): return name.replace("CONNECTOR_", "", 1)
    
    def add_pid(self, pid): self.m_ChildProcManager.add_pid(pid)
    def remove_pid(self, pid): self.m_ChildProcManager.remove_pid(pid)
    
    def config_value_check(self):
        if self.m_RouterListenPort == 0: return False
        if self.m_LogRouterListenPort == 0: return False
        return True

    def get_unix_socket_dir(self): return "/tmp" # Or AsUtil
    def get_bin_dir(self): return "../Bin"
    def get_proc_alive_check_time(self): return 30
    def get_alive_check_limit_cnt(self): return 5
    
    def get_parser_listen_socket_path(self, session_name):
        return f"{self.get_unix_socket_dir()}{self.UNIX_PARSER_LISTEN_PREFIX}{self.parser_id_decode(session_name)}"
    def get_router_listen_socket_path(self, session_name):
        return f"{self.get_unix_socket_dir()}{self.UNIX_ROUTER_LISTEN_PREFIX}{session_name}"
    def get_data_router_listen_socket_path(self, session_name):
        return f"{self.get_unix_socket_dir()}{self.UNIX_DATAROUTER_LISTEN_PREFIX}{session_name}"

    def get_data_handler_info(self, data_handler_id):
        return self.m_DataHandlerInfoMap.get(data_handler_id)
    def get_data_handler_info_map(self):
        return self.m_DataHandlerInfoMap