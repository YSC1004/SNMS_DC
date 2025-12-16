import sys
import os
import threading

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
from Class.Common.CommType import ASCII_LOG_ROUTER, ARG_NAME, ARG_MANAGER_SOCKET_PATH, ARG_PORT_NO

# Lazy Import to avoid circular dependencies if necessary
try:
    from Class.ProcLogRouter.ManagerConnection import ManagerConnection
    from Class.ProcLogRouter.LogGuiConnMgr import LogGuiConnMgr
except ImportError:
    pass

class LogRouterWorld(AsWorld):
    """
    LogRouter 프로세스의 메인 월드 클래스.
    Manager와의 연결 및 GUI 클라이언트 리스너를 관리합니다.
    """
    _instance = None

    def __init__(self):
        """
        C++: LogRouterWorld()
        """
        super().__init__()
        LogRouterWorld._instance = self
        
        # Connections
        self.m_ManagerConnection = ManagerConnection()
        self.m_LogGuiConnMgr = LogGuiConnMgr()
        
        # Config
        self.m_ManagerSocketPath = ""
        self.m_LogGuiListenPort = 0
        self.m_ProcName = "LogRouter"

    def __del__(self):
        """
        C++: ~LogRouterWorld()
        """
        super().__del__()

    @staticmethod
    def get_instance():
        return LogRouterWorld._instance

    def app_start(self, argc, argv):
        """
        C++: bool AppStart(int Argc, char** Argv)
        """
        # 1. Init Config
        if not self.init_config():
            print(f"[LogRouterWorld] [CORE_ERROR] Env Init Error")
            return False

        # 2. Logger Setup
        FrLogger.get_instance().enable("LogRouter", 3)
        FrLogger.get_instance().enable("Common", 2)
        # FrLogger.get_instance().enable("Event", 1)

        # 3. Argument Parsing
        parser = FrArgParser(argv)
        
        name = parser.get_value(ARG_NAME)
        if name:
            self.m_ProcName = name
            # SetObjectName(name) - AsWorld logic
            
        self.m_ManagerSocketPath = parser.get_value(ARG_MANAGER_SOCKET_PATH)
        port_str = parser.get_value(ARG_PORT_NO)
        self.m_LogGuiListenPort = int(port_str) if port_str else 0

        # 4. Log File Setup
        self.set_log_file(ASCII_LOG_ROUTER)

        print("\n\n\n\n\n\n\n")
        print("[LogRouterWorld] LogRouter Start.............")

        # 5. Init Components
        if not self.init_log_router():
            print("[LogRouterWorld] LogRouter Init Fail")
            return False
            
        print("[LogRouterWorld] LogRouter Init Success")
        return True

    def init_log_router(self):
        """
        C++: bool InitLogRouter()
        Manager 연결 및 LogGui 리스너 생성
        """
        

        # 1. Connect to Manager (Unix Domain Socket)
        # Assuming ManagerConnection inherits AsSocket and has connect_unix or creates socket based on path
        if not self.m_ManagerConnection.connect_unix(self.m_ManagerSocketPath):
             print(f"[LogRouterWorld] [CORE_ERROR] Can't connect ({self.m_ManagerConnection.get_obj_err_msg()})")
             # Return False logic omitted in C++ but implied needed, keeping C++ flow (continues)

        # 2. Create LogGui Listener (TCP)
        if not self.m_LogGuiConnMgr.init_socket("", self.m_LogGuiListenPort):
             print(f"[LogRouterWorld] [CORE_ERROR] Listener Error For LogGui(port:{self.m_LogGuiListenPort})")
             return False

        # 3. Identify Session with Manager
        # Using 30 sec as default alive check time if GetProcAliveCheckTime not defined
        self.m_ManagerConnection.set_session_identify(ASCII_LOG_ROUTER, self.m_ProcName, self.get_proc_alive_check_time())

        # 4. Initial Log Status
        self.set_log_status(ASCII_LOG_ROUTER, self.m_ProcName)
        self.send_log_status(self.get_log_status())
        
        return True

    def env_value(self, section, sub_section):
        """
        C++: string EnvValue(int Section, string SubSection)
        """
        return self.get_env_value(section, "name")

    def send_log_status(self, status):
        """
        C++: void SendLogStatus(const AS_LOG_STATUS_T* Status)
        """
        # C++ code commented out: //m_ManagerConnection.SendLogStatus(Status);
        # Uncomment if implemented in ManagerConnection
        # self.m_ManagerConnection.send_log_status(status)
        pass

    def get_proc_alive_check_time(self):
        return 30 # Default