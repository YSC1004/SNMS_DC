import sys
import os
import time
import threading
import signal
import subprocess
from collections import deque

# -------------------------------------------------------
# 1. 프로젝트 경로 설정
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# 2. 모듈 Import
# -------------------------------------------------------
from Class.Common.AsWorld import AsWorld
from Class.Util.FrArgParser import FrArgParser
from Class.Util.FrTime import FrTime
from Class.Event.FrLogger import FrLogger
from Class.Common.AsUtil import AsUtil
from Class.Common.CommType import *
from Class.Common.ProcConnectionMgr import ProcConnectionMgr
from Class.Common.ChildProcessManager import ChildProcessManager
from Class.Common.AsciiServerType import *

# Managers (Lazy Import 및 순환 참조 방지)
try:
    from Class.ProcNaServer.DbManager import DbManager
    from Class.ProcNaServer.ManagerConnMgr import ManagerConnMgr
    from Class.ProcNaServer.GuiConnMgr import GuiConnMgr
    from Class.ProcNaServer.ServerConnMgr import ServerConnMgr
    from Class.ProcNaServer.ExternalConnMgr import ExternalConnMgr
    from Class.ProcNaServer.MMCGeneratorConnMgr import MMCGeneratorConnMgr
    from Class.ProcNaServer.RuleDownLoaderConnMgr import RuleDownLoaderConnMgr
    from Class.ProcNaServer.DataHandlerConnMgr import DataHandlerConnMgr
    from Class.ProcNaServer.SubProcConnMgr import SubProcConnMgr
    from Class.ProcNaServer.RouterInfoConnMgr import RouterInfoConnMgr
    from Class.ProcNaServer.SimsConnMgr import SimsConnMgr
    from Class.ProcNaServer.NetFinderConnMgr import NetFinderConnMgr # [추가]
except ImportError:
    pass

# -------------------------------------------------------
# AsciiServerWorld Class
# -------------------------------------------------------
class AsciiServerWorld(AsWorld):
    _instance = None

    # Constants
    MMCRESPONSE_GABAGE_CLEAR = 5001
    MMCQUEUE_GABAGE_CLEAR = 5002
    DEFAULT_GABAGE_CLEAR_INTERVAL = 60*60*3 # 3 hours

    def __init__(self):
        """
        C++: AsciiServerWorld()
        """
        super().__init__()
        AsciiServerWorld._instance = self
        
        # Status Flags
        self.m_IsActive = True
        self.m_UseNameServer = False
        self.m_ThreadStatus = True
        
        self.m_ParsingRuleDownLoading = False
        self.m_MappingRuleDownLoading = False
        self.m_CommandRuleDownLoading = False
        self.m_SchedulerRuleDownLoading = False
        
        # DB Info
        self.m_DbUserId = ""; self.m_DbPassword = ""; self.m_DbTns = ""
        self.m_DbIp = ""; self.m_DbPort = "1521"
        self.m_DbManager = None
        self.m_MMCResultDbManager = None
        self.m_MmcStoredFunctionStatus = False
        
        # Server Info
        self.m_ActiveServerIp = ""
        self.m_ActiveServerPort = 0

        # Ports
        self.m_ServerPort = 0; self.m_GuiPort = 0; self.m_ExtPort = 0
        self.m_DataHandlerPort = 0; self.m_RouterInfoListenPort = 0
        self.m_SimsListenPort = 0; self.m_NetFinderListenPort = 0
        self.m_StandBySvrListenPort = 0; self.m_SubProcListenPort = 0
        
        # Connection Managers
        self.m_ManagerConnMgr = ManagerConnMgr()
        self.m_GuiConnMgr = GuiConnMgr()
        self.m_ExternalConnMgr = ExternalConnMgr()
        self.m_MMCGeneratorConnMgr = MMCGeneratorConnMgr()
        self.m_DataHandlerConnMgr = DataHandlerConnMgr()
        self.m_SubProcConnMgr = SubProcConnMgr()
        self.m_RuleDownLoaderConnMgr = RuleDownLoaderConnMgr()
        self.m_ServerConnMgr = ServerConnMgr()
        self.m_RouterInfoConnMgr = RouterInfoConnMgr()
        self.m_SimsConnMgr = None # init_active_server에서 생성
        self.m_NetFinderConnMgr = NetFinderConnMgr() # [추가]

        # Child Process Managers
        self.m_ChildProcManager = ChildProcessManager()
        self.m_ProcConnectionMgr = ProcConnectionMgr()
        
        # Queues & Maps
        self.m_MMCRequestQueueList = [] 
        self.m_MmcGenResultQueue = MmcGenResultQueue()
        self.m_ExtMMCReqMap = ExtMMCReqMap()
        self.m_ExtMMCReqWaitMap = ExtMMCReqMap()
        self.m_MmcRequestMap = MmcRequestMap()
        self.m_MmcPublishSetQueueList = []
        
        # System Info & Session Cfg
        self.m_AsSystemInfoMap = {}
        self.m_AsSessionCfgMap = {}
        
        for _ in range(5):
            self.m_MmcPublishSetQueueList.append(MmcPublishSetQueue())
            
        # Locks
        self.m_MsgIdLock = threading.Lock()
        self.m_MsgId = 0
        self.m_ExtMMCReqWaitMapLock = threading.Lock()
        
        # Garbage List
        self.m_MMCResultStoredList = []
        self.m_MMCResultStoredListLock = threading.Lock()
        self.m_MMCResultStoredMap = {}
        self.m_MMCReqQueueGarbageList = []
        self.m_MMCReqQueueGarbageListLock = threading.Lock()

        # Info Maps
        self.m_ProcStatusMap = {}
        self.m_CommandAuthorityInfoMap = {}

        self.m_ErrorLogFp = None
        self.m_ProcName = "AsciiServer"

    def __del__(self):
        self.clean_up()
        super().__del__()

    # ---------------------------------------------------
    # AppStart
    # ---------------------------------------------------
    def app_start(self, argc, argv):
        print(">> AsciiServerWorld AppStart...")
        
        # 1. Args
        parser = FrArgParser(argv)
        type_val = parser.get_value("-type")
        
        if type_val == "active":
            self.m_IsActive = True
            print("SERVER TYPE : ACTIVE")
        elif type_val == "standby":
            self.m_IsActive = False
            val = parser.get_value("-svrip")
            if val: self.m_ActiveServerIp = val
            val = parser.get_value("-portno")
            if val: self.m_ActiveServerPort = int(val)
            print(f"SERVER TYPE : STANDBY ({self.m_ActiveServerIp}:{self.m_ActiveServerPort})")
        else:
            self.m_IsActive = True

        # 2. Config
        if not self.init_config(): return False
        if not self.ascii_system_dir_check(): return False
        
        FrLogger.get_instance().enable("AsciiServer", level=3)
        
        # 3. Env
        self.m_ProcName = self.get_env_value(ASCII_SERVER, "name")
        self.m_DbUserId = self.get_env_value(ASCII_SERVER, "db_user")
        self.m_DbPassword = self.get_env_value(ASCII_SERVER, "db_password")
        self.m_DbTns = self.get_env_value(ASCII_SERVER, "db_tns")
        self.m_DbIp = self.get_env_value(ASCII_SERVER, "db_ip")
        self.m_DbPort = self.get_env_value(ASCII_SERVER, "db_port")
        
        # 4. Ports
        self.m_ServerPort = int(self.get_env_value(ASCII_SERVER, "server_listen_port") or 0)
        self.m_GuiPort = int(self.get_env_value(ASCII_SERVER, "gui_listen_port") or 0)
        self.m_ExtPort = int(self.get_env_value(ASCII_SERVER, "external_system_listenport") or 0)
        self.m_DataHandlerPort = int(self.get_env_value(ASCII_SERVER, "datahandler_listen_port") or 0)
        self.m_SubProcListenPort = int(self.get_env_value(ASCII_SERVER, "subproc_listen_port") or 0)
        self.m_StandBySvrListenPort = int(self.get_env_value(ASCII_SERVER, "standby_listen_port") or 0)
        self.m_RouterInfoListenPort = int(self.get_env_value(ASCII_SERVER, "router_info_listen_port") or 0)
        self.m_SimsListenPort = int(self.get_env_value(ASCII_SERVER, "sims_listen_port") or 0)
        self.m_NetFinderListenPort = int(self.get_env_value(ASCII_SERVER, "netfinder_listen_port") or 0) # [추가]
        
        self.set_system_info(ASCII_SERVER, self.m_ProcName)
        
        # 5. Log
        self.set_log_file(ASCII_SERVER)
        self.error_file_changed()
        
        # 6. Common
        if not self.init_common_server(): return False
        
        # 7. Server Init
        if self.m_IsActive:
            if not self.init_active_server(): return False
        else:
            if not self.init_standby_server(): return False
            
        print(">> Finish Ascii Server init..............")
        return True

    # ---------------------------------------------------
    # Initialization Methods
    # ---------------------------------------------------
    def init_active_server(self):
        print("[AsciiServerWorld] Init Active Server Start...")

        # 1. External System
        if not self.m_ExternalConnMgr.init_socket("", self.m_ExtPort):
            print(f"[AsciiServerWorld] Listen Error For External System(port:{self.m_ExtPort})")
            return False

        # 2. MMC Generator (Unix Socket)
        mmc_path = self.get_mmc_listen_socket_path()
        if hasattr(self.m_MMCGeneratorConnMgr, 'init_unix_socket'):
             if not self.m_MMCGeneratorConnMgr.init_unix_socket(mmc_path):
                print(f"[AsciiServerWorld] Listen Error For MMC : {mmc_path}")
                return False
        else:
            print(f"[AsciiServerWorld] Unix Socket Init skipped: {mmc_path}")

        # 3. Manager
        if not self.m_ManagerConnMgr.init_socket("", self.m_ServerPort):
            print(f"[AsciiServerWorld] Listen Error For Manager(port:{self.m_ServerPort})")
            return False

        # 4. DataHandler
        if not self.m_DataHandlerConnMgr.init_socket("", self.m_DataHandlerPort):
            print(f"[AsciiServerWorld] Listen Error For DataHandler(port:{self.m_DataHandlerPort})")
            return False

        # 5. SubProc
        if not self.m_SubProcConnMgr.init_socket("", self.m_SubProcListenPort):
            print(f"[AsciiServerWorld] Listen Error For SubProc(port:{self.m_SubProcListenPort})")
            return False

        # 6. GUI
        if not self.m_GuiConnMgr.init_socket("", self.m_GuiPort):
            print(f"[AsciiServerWorld] Listener Error For GUI(port:{self.m_GuiPort})")
            return False

        # 7. Sims
        self.m_SimsConnMgr = SimsConnMgr(self.m_ExternalConnMgr)
        if self.m_SimsListenPort:
            if not self.m_SimsConnMgr.init_socket("", self.m_SimsListenPort):
                print(f"[AsciiServerWorld] Listener Error For Sims(port:{self.m_SimsListenPort})")
                return False
        else:
            print("[AsciiServerWorld] Sim port is not defined")

        # 8. NetFinder (Unix Socket) [추가]
        # C++ 코드에서는 주석 처리되어 있었으나, 필요 시 사용
        nf_path = self.get_net_finder_listen_socket_path()
        if hasattr(self.m_NetFinderConnMgr, 'init_unix_socket'):
            if not self.m_NetFinderConnMgr.init_unix_socket(nf_path):
                print(f"[AsciiServerWorld] Listen Error For NetFinder : {nf_path}")
                # return False (선택 사항)
        else:
            print(f"[AsciiServerWorld] NetFinder Unix Socket Init skipped")

        # 9. Standby
        if not self.m_ServerConnMgr.init_socket("", self.m_StandBySvrListenPort):
            print(f"[AsciiServerWorld] Listen Error For standby server(port:{self.m_StandBySvrListenPort})")
            return False

        # 10. Router Info
        if not self.m_RouterInfoConnMgr.init_socket("", self.m_RouterInfoListenPort):
            print(f"[AsciiServerWorld] Listen Error For Router info(port:{self.m_RouterInfoListenPort})")
            return False

        # 11. Thread Creation
        try:
            threading.Thread(target=self.mmc_request_manager, daemon=True).start()
            threading.Thread(target=self.mmc_gen_result_manager, daemon=True).start()
            threading.Thread(target=self.mmc_publish_manager, daemon=True).start()
            print("[AsciiServerWorld] Threads Created Success")
        except Exception as e:
            print(f"[AsciiServerWorld] Thread Create Fail : {e}")
            return False

        # 12. DB Init
        self.m_DbManager = DbManager()
        if not self.m_DbManager.init_db_manager(self.m_DbUserId, self.m_DbPassword, 
                                                self.m_DbTns, self.m_DbIp, self.m_DbPort):
            print(f"[AsciiServerWorld] Db Connection Error : {self.m_DbManager.get_error_msg()}")
            return False

        # 13. Execute Processes & Load Data
        self.m_DbManager.get_command_authority_info(self.m_CommandAuthorityInfoMap)
        dbm_msg_id = self.m_DbManager.get_current_msg_id()
        self.m_MsgId = dbm_msg_id if dbm_msg_id >= 0 else 0

        self.m_SubProcConnMgr.execute_sub_proc_all()
        self.m_DataHandlerConnMgr.execute_manager()
        self.m_ManagerConnMgr.execute_manager()

        # 14. Timers & Process Info
        self.set_timer(10, self.MMCQUEUE_GABAGE_CLEAR)
        self.set_timer(120, self.MMCRESPONSE_GABAGE_CLEAR)

        proc_info = AsProcessStatusT()
        proc_info.ProcessId = self.m_ProcName
        proc_info.ManagerId = self.m_ProcName
        proc_info.Status = START
        proc_info.ProcessType = ASCII_SERVER
        proc_info.Pid = os.getpid()
        self.update_process_info(proc_info)
        
        return True

    def init_standby_server(self):
        self.m_DbManager = DbManager()
        if not self.m_DbManager.init_db_manager(self.m_DbUserId, self.m_DbPassword, self.m_DbTns, self.m_DbIp, self.m_DbPort):
            return False
            
        from Class.ProcNaServer.ServerConnection import ServerConnection
        self.m_ServerConnection = ServerConnection(None)
        if not self.m_ServerConnection.connect(self.m_ActiveServerIp, self.m_ActiveServerPort):
            print("[Error] Active Server connect error")
            return False
            
        self.m_ServerConnection.set_session_identify(ASCII_SERVER, self.m_ProcName, 100, False)
        return True

    def init_common_server(self):
        # RuleDownLoader (Unix Socket)
        path = self.get_rule_down_loader_listen_socket_path()
        if hasattr(self.m_RuleDownLoaderConnMgr, 'init_unix_socket'):
            if not self.m_RuleDownLoaderConnMgr.init_unix_socket(path):
                return False
        
        self.start_proc(ASCII_RULE_DOWNLOADER)
        return True

    def start_proc(self, proc_type):
        proc_name = AsUtil.get_process_type_string(proc_type)
        bin_path = f"{self.get_bin_dir()}/{proc_name}"
        
        args = [bin_path, ARG_NAME, proc_name, ARG_SVR_SOCKET_PATH]
        
        if proc_type == ASCII_RULE_DOWNLOADER:
            args.append(self.get_rule_down_loader_listen_socket_path())
        elif proc_type == NETFINDER:
            args.append(self.get_net_finder_listen_socket_path())
        else:
            args.append(self.get_mmc_listen_socket_path())

        pid = self.m_ProcConnectionMgr.start_proc(proc_name, args)
        if pid != -1:
            self.add_pid(pid)

    # ... (Other logic methods: recv_info_change, process_dead, etc. same as before) ...
    def process_dead(self, name, pid):
        self.remove_pid(pid)
        print(f"[AsciiServerWorld] Process Dead : {name}({pid})")

    # Placeholder Managers
    def mmc_request_manager(self):
        while self.m_ThreadStatus: time.sleep(1)
    def mmc_gen_result_manager(self):
        while self.m_ThreadStatus: time.sleep(1)
    def mmc_publish_manager(self):
        while self.m_ThreadStatus: time.sleep(1)

    # Info & Utilities
    def get_mmc_listen_socket_path(self):
        return os.path.join(self.get_unix_socket_dir(), "SERVER_UNIX_MMC_LISTEN")
    def get_rule_down_loader_listen_socket_path(self):
        return os.path.join(self.get_unix_socket_dir(), "SERVER_UNIX_RULE_DOWNLOADER_LISTEN")
    def get_net_finder_listen_socket_path(self):
        return os.path.join(self.get_unix_socket_dir(), "SERVER_UNIX_NETFINDER_LISTEN")
    
    def recv_info_change(self, info, result_msg=""):
        if isinstance(info, AsConnectionInfoListT):
            return self._recv_connection_info_list_change(info, result_msg)
        # ... (Dispatch logic) ...
        return False

    def _recv_connection_info_list_change(self, info_list, result_msg):
        # ... (List logic) ...
        return True

    def update_process_info(self, proc_info):
        mgr_id = proc_info.ManagerId
        proc_id = proc_info.ProcessId
        if mgr_id not in self.m_ProcStatusMap:
            self.m_ProcStatusMap[mgr_id] = {}
        
        if proc_info.Status == START:
            import copy
            self.m_ProcStatusMap[mgr_id][proc_id] = copy.deepcopy(proc_info)
        elif proc_info.Status == STOP:
            if proc_id in self.m_ProcStatusMap[mgr_id]:
                del self.m_ProcStatusMap[mgr_id][proc_id]
                
        self.m_GuiConnMgr.send_info_change(proc_info)

    def send_log_status(self, status):
        self.m_GuiConnMgr.send_log_status(status)

    def add_pid(self, pid):
        self.m_ChildProcManager.add_pid(pid)
    def remove_pid(self, pid):
        self.m_ChildProcManager.remove_pid(pid)
        
    def error_file_changed(self):
        pass # Log rotation logic
        
    def clean_up(self):
        self.m_ThreadStatus = False
        if self.m_ErrorLogFp: self.m_ErrorLogFp.close()