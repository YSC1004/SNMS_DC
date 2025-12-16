import sys
import os
import threading

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# Imports
# -------------------------------------------------------
from Class.Event.FrWorld import FrWorld, FR_MODE
from Class.Event.FrThreadWorld import FrThreadWorld
from Class.Common.AsEnvrion import AsEnvrion
from Class.Common.AsUtil import AsUtil
from Class.Common.AsWorldLogTimer import AsWorldLogTimer
from Class.Common.AsWorldTimer import AsWorldTimer
from Class.Util.FrArgParser import FrArgParser
from Class.Util.FrTime import FrTime
from Class.Event.FrLogger import FrLogger

# Lazy / Optional Imports
try:
    from Class.Common.SockMgrConnMgr import SockMgrConnMgr
except ImportError:
    SockMgrConnMgr = None

try:
    from Class.Common.CommType import *
except ImportError:
    pass

# -------------------------------------------------------
# AsWorld Class
# -------------------------------------------------------
class AsWorld(FrWorld):
    """
    Application Core Logic World Class.
    Manages Config, Directories, Logging, Timers, and Connection Managers.
    Inherits from FrWorld (Event Loop Engine).
    """
    
    # Static Members (Shared across instances if multiple, though usually Singleton)
    m_ConnectionMgrVector = []
    m_ConnectionMgrVectorLock = threading.Lock()
    m_StartDir = ""

    def __init__(self, mode=FR_MODE.FR_MAIN):
        """
        C++: AsWorld()
        """
        super().__init__(mode)
        
        self.m_ProcName = ""
        self.m_ProcessType = -1
        self.m_HostName = ""
        self.m_AsWorldTimer = None
        self.m_AsWorldLogTimer = None
        self.m_ProcType = -5
        self.m_UserAccount = ""
        
        self.m_SockMgrConnMgr = None
        self.m_SockMgrWorld = None
        
        # System Info (AsSystemInfoT)
        self.m_SystemInfo = None 
        
        # Config Parser
        self.m_Envrion = AsEnvrion()
        
        # Directory Paths
        self.m_RootDir = ""
        self.m_BinDir = ""
        self.m_LogDir = ""
        self.m_BCDir = ""
        self.m_ConfigDir = ""
        self.m_UnixSocketListenDir = ""
        self.m_ParserTempDir = ""
        self.m_ConnectorTempDir = ""
        self.m_DataHandlerDir = ""
        self.m_JobMonitorDir = ""
        self.m_ScriptDir = ""
        self.m_RawDir = ""
        self.m_RuleDir = ""
        self.m_MainRuleDir = ""
        self.m_SystemDir = ""
        
        # Alive Check Settings
        self.m_AliveCheckLimitCnt = 5
        self.m_AliveCheckIntervalTime = 100

    def __del__(self):
        """
        C++: ~AsWorld()
        """
        # Cleanup Timers (Check existence to avoid AttributeError during failed init)
        if hasattr(self, 'm_AsWorldTimer') and self.m_AsWorldTimer:
            self.m_AsWorldTimer.unregister_sensor()
            
        if hasattr(self, 'm_AsWorldLogTimer') and self.m_AsWorldLogTimer:
            self.m_AsWorldLogTimer.unregister_sensor()
            
        super().__del__()

    # ---------------------------------------------------
    # Configuration & Init
    # ---------------------------------------------------
    def init_config(self):
        """
        C++: bool InitConfig()
        Loads configuration from file specified in env NETADAPTER_CONFIG_FILE.
        """
        env_file = os.environ.get("NETADAPTER_CONFIG_FILE")
        if not env_file:
            print("[AsWorld] Can't find env NETADAPTER_CONFIG_FILE")
            return False

        if not self.m_Envrion.init_config(env_file, True):
            return False

        # Start Dir
        self.m_StartDir = self.get_env_value("COMMON", "netadapter_start_dir_name")
        if not self.m_StartDir:
            print("[AsWorld] Use default netadapter_start_dir_name : [NAA]")
            self.m_StartDir = "NAA"
        
        # Root Dir (Home + StartDir)
        home_dir = AsUtil.get_home_dir()
        if not home_dir:
            print("[AsWorld] Can't find home dir (env : HOME)")
            return False
            
        self.m_RootDir = os.path.join(home_dir, self.m_StartDir)
        self.m_BinDir = os.path.join(self.m_RootDir, "Bin")
        
        # Alive Check Config
        val = self.get_env_value("COMMON", "alive_check_maxcount")
        if val: self.m_AliveCheckLimitCnt = int(val)
        if self.m_AliveCheckLimitCnt < 5: self.m_AliveCheckLimitCnt = 5

        val = self.get_env_value("COMMON", "alive_check_interval")
        if val: self.m_AliveCheckIntervalTime = int(val)
        if self.m_AliveCheckIntervalTime < 100: self.m_AliveCheckIntervalTime = 100
        
        # User Account
        self.m_UserAccount = AsUtil.get_user_name()
        if not self.m_UserAccount:
            print("[AsWorld] Can't Find env User Account Name")
            return False

        return True

    def get_env_value(self, section, sub_section):
        """
        C++: string GetEnvValue(string Section, string SubSection)
        """
        return self.m_Envrion.get_env_value(section, sub_section)

    # ---------------------------------------------------
    # Directory Management
    # ---------------------------------------------------
    def get_log_dir(self):
        self.m_LogDir = os.path.join(self.m_RootDir, "Log")
        return self.m_LogDir

    def get_bin_dir(self): return self.m_BinDir
    
    def get_system_dir(self):
        self.m_SystemDir = os.path.join(self.m_RootDir, "System")
        return self.m_SystemDir

    def get_unix_socket_dir(self):
        self.m_UnixSocketListenDir = os.path.join(self.get_system_dir(), "UnixSocket")
        return self.m_UnixSocketListenDir
        
    def get_raw_dir(self):
        self.m_RawDir = os.path.join(self.m_RootDir, "RawLog")
        return self.m_RawDir

    def ascii_system_dir_check(self):
        """
        C++: bool AsciiSystemDirCheck()
        Checks if required directories exist, creates them if not.
        """
        dirs = [
            self.get_log_dir(),
            self.get_bin_dir(),
            self.get_system_dir(),
            self.get_unix_socket_dir(),
            self.get_raw_dir()
            # Add other dirs as needed
        ]
        
        for d in dirs:
            if not self.dir_check(d, True): # True: MakeFlag
                return False
        return True

    def dir_check(self, dir_name, make_flag):
        if not os.path.isdir(dir_name):
            print(f"[AsWorld] Can't Find Dir({dir_name})")
            if make_flag:
                try:
                    os.makedirs(dir_name, 0o755)
                    print(f"[AsWorld] Create Dir({dir_name})")
                except OSError as e:
                    print(f"[AsWorld] Dir Create Error : {e}")
                    return False
            else:
                return False
        return True

    # ---------------------------------------------------
    # Logging
    # ---------------------------------------------------
    def set_proc_name(self, name):
        self.m_ProcName = name

    def get_proc_name(self):
        return self.m_ProcName

    def set_log_file(self, proc_type):
        """
        C++: void SetLogFile(int ProcType)
        Sets up the log file based on process type and rotation cycle.
        """
        self.m_ProcType = proc_type
        self.log_file_changed_event()

    def log_file_changed_event(self):
        """
        C++: void LogFileChangedEvent()
        Handles log rotation logic.
        """
        cur_time = FrTime()
        hour_buf = ""
        
        # Parse argv to find -logcycle
        log_cycle = "DAY" # Default
        # Using FrWorld.m_Argv directly (assuming it's set in init)
        parser = FrArgParser(FrWorld.m_Argv)
        val = parser.get_value("-logcycle")
        if val == "HOUR":
            log_cycle = "HOUR"
            hour_buf = f"{cur_time.get_hour():02d}"
        
        proc_type_str = AsUtil.get_process_type_string(self.m_ProcType)
        date_str = f"{cur_time.get_year():04d}{cur_time.get_month():02d}{cur_time.get_day():02d}"
        
        if proc_type_str == "UNKNOWN_TYPE":
            log_name = f"{self.m_ProcName}_{date_str}{hour_buf}.log"
        else:
            log_name = f"{proc_type_str}_{self.m_ProcName}_{date_str}{hour_buf}.log"
            
        full_path = os.path.join(self.get_log_dir(), log_name)
        
        print(f"[AsWorld] Log Change: {full_path}")
        
        logger = FrLogger.get_instance()
        logger.open(full_path)

        # Set Timer for Next Rotation
        if self.m_AsWorldLogTimer is None:
            self.m_AsWorldLogTimer = AsWorldLogTimer(self)

        sec_val = 0
        if log_cycle == "HOUR":
            sec_val = cur_time.get_remain_hour_sec()
            if sec_val == 0: sec_val = 3600
        else:
            sec_val = cur_time.get_remain_day_sec()
            if sec_val == 0: sec_val = 86400
            
        # Add 20 seconds buffer
        self.m_AsWorldLogTimer.set_timer(sec_val + 20, 1)

    # ---------------------------------------------------
    # Timer Management
    # ---------------------------------------------------
    def set_timer(self, interval, reason, extra_reason=None):
        """
        C++: int SetTimer(int Interval, int Reason, void* ExtraReason)
        Delegates to AsWorldTimer.
        """
        if self.m_AsWorldTimer is None:
            self.m_AsWorldTimer = AsWorldTimer(self)
        return self.m_AsWorldTimer.set_timer(interval, reason, extra_reason)

    def receive_time_out(self, reason, extra_reason):
        """
        C++: virtual void ReceiveTimeOut(...)
        To be overridden by child classes.
        """
        pass

    # ---------------------------------------------------
    # Connection Manager Management
    # ---------------------------------------------------
    @classmethod
    def register_connection_mgr(cls, conn_mgr):
        with cls.m_ConnectionMgrVectorLock:
            cls.m_ConnectionMgrVector.append(conn_mgr)

    @classmethod
    def deregister_connection_mgr(cls, conn_mgr):
        with cls.m_ConnectionMgrVectorLock:
            if conn_mgr in cls.m_ConnectionMgrVector:
                cls.m_ConnectionMgrVector.remove(conn_mgr)
                return True
        return False

    # ---------------------------------------------------
    # SockMgr Session (Separate Thread)
    # ---------------------------------------------------
    def enable_sock_mgr_session(self, session_name, port):
        """
        C++: bool EnableSockMgrSession(string SessionName, int Port)
        Creates a separate thread/world for socket management (e.g. Admin interface).
        """
        if not SockMgrConnMgr:
            print("[AsWorld] SockMgrConnMgr not found (Import Error)")
            return False

        self.m_SockMgrConnMgr = SockMgrConnMgr()
        self.m_SockMgrConnMgr.set_object_name(session_name)

        if not self.m_SockMgrConnMgr.listen(port):
            print(f"[AsWorld] Enable SockMgr Session Fail (Port:{port})")
            return False

        self.m_SockMgrWorld = FrThreadWorld()
        if not self.m_SockMgrWorld.run():
            return False

        self.m_SockMgrConnMgr.change_world(self.m_SockMgrWorld)
        
        print(f"[AsWorld] Enable SockMgr Session Success (Port:{port})")
        return True

    # ---------------------------------------------------
    # Helper Methods
    # ---------------------------------------------------
    def get_proc_alive_check_time(self):
        return self.m_AliveCheckIntervalTime

    def get_alive_check_limit_cnt(self):
        return self.m_AliveCheckLimitCnt
        
    def set_system_info(self, proc_type, proc_name):
        """
        Initialize System Info structure.
        """
        # Needs AsSystemInfoT definition
        # self.m_SystemInfo = AsSystemInfoT()
        pass