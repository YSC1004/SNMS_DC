import sys
import os
import threading

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 모듈 Import
from Class.Event.FrWorld import FrWorld, FR_MODE
from Class.Event.FrThreadWorld import FrThreadWorld
from Class.Common.AsEnvrion import AsEnvrion
from Class.Common.AsUtil import AsUtil
from Class.Common.AsWorldLogTimer import AsWorldLogTimer
from Class.Common.AsWorldTimer import AsWorldTimer
from Class.Util.FrArgParser import FrArgParser
from Class.Util.FrTime import FrTime
from Class.Event.FrLogger import FrLogger, FrLogDef

# 임시 Import (나중에 구현 필요)
try:
    from Class.Common.SockMgrConnMgr import SockMgrConnMgr
except ImportError:
    SockMgrConnMgr = None

try:
    from Class.Common.AsSystemChecker import AsSystemChecker
except ImportError:
    AsSystemChecker = None

try:
    from Class.Common.CommType import *
except ImportError:
    pass

# -------------------------------------------------------
# AsWorld Class
# 애플리케이션 메인 비즈니스 로직을 담는 World 클래스
# -------------------------------------------------------
class AsWorld(FrWorld):
    # Static Members
    m_ConnectionMgrVector = []
    m_ConnectionMgrVectorLock = threading.Lock()
    m_StartDir = ""

    def __init__(self):
        """
        C++: AsWorld()
        """
        super().__init__(FR_MODE.FR_MAIN)
        
        self.m_ProcName = ""
        self.m_ProcessType = -1
        self.m_HostName = ""
        self.m_AsWorldTimer = None
        self.m_AsWorldLogTimer = None
        self.m_ProcType = -5
        self.m_UserAccount = ""
        
        self.m_SockMgrConnMgr = None
        self.m_SockMgrWorld = None
        
        # System Info (AsSystemInfoT 구조체)
        self.m_SystemInfo = None 
        
        # Config Parser
        self.m_Envrion = AsEnvrion()
        
        # Paths
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
        if self.m_AsWorldTimer:
            self.m_AsWorldTimer.unregister_sensor()
        if self.m_AsWorldLogTimer:
            self.m_AsWorldLogTimer.unregister_sensor()
            
        # Vector 자체는 Static이라 여기서 지우면 안 될 수 있음 (C++ 로직 확인)
        # Python GC에 맡김
        super().__del__()

    # ---------------------------------------------------
    # Configuration & Init
    # ---------------------------------------------------
    def init_config(self):
        """
        C++: bool InitConfig()
        환경변수에서 설정파일 경로를 읽어 로딩
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
        
        # Root Dir
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

    # ... (기타 GetDir 함수들은 패턴이 같으므로 생략 가능하나 필요시 추가) ...

    def ascii_system_dir_check(self):
        """
        필수 디렉토리가 있는지 확인하고 없으면 생성
        """
        dirs = [
            self.get_log_dir(),
            self.get_bin_dir(),
            self.get_system_dir(),
            self.get_unix_socket_dir(),
            # ...
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
        self.m_ProcType = proc_type
        self.log_file_changed_event()

    def log_file_changed_event(self):
        """
        로그 파일명 생성 및 Open, 다음 변경 타이머 설정
        """
        cur_time = FrTime()
        hour_buf = ""
        
        # Argv 파싱 (로그 주기 확인)
        arg_parser = FrArgParser(FrWorld.m_Argv)
        log_cycle = arg_parser.get_value("-logcycle") # ARG_LOG_CYCLE
        
        if log_cycle == "HOUR":
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

        # 타이머 설정 (다음 변경 시점)
        if self.m_AsWorldLogTimer is None:
            self.m_AsWorldLogTimer = AsWorldLogTimer(self)

        if log_cycle == "HOUR":
            sec_val = cur_time.get_remain_hour_sec()
            if sec_val == 0: sec_val = 3600
        else:
            sec_val = cur_time.get_remain_day_sec()
            if sec_val == 0: sec_val = 86400
            
        # 20초 여유를 둠
        self.m_AsWorldLogTimer.set_timer(sec_val + 20, 1)

    # ---------------------------------------------------
    # Timer Management (Delegate to AsWorldTimer)
    # ---------------------------------------------------
    def set_timer(self, interval, reason, extra_reason=None):
        if self.m_AsWorldTimer is None:
            self.m_AsWorldTimer = AsWorldTimer(self)
        return self.m_AsWorldTimer.set_timer(interval, reason, extra_reason)

    def receive_time_out(self, reason, extra_reason):
        """
        C++: virtual void ReceiveTimeOut(...)
        자식 클래스에서 구현
        """
        # print("[AsWorld] ReceiveTimeOut virtual function")
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
        if not SockMgrConnMgr:
            print("[AsWorld] SockMgrConnMgr not found")
            return False

        self.m_SockMgrConnMgr = SockMgrConnMgr()
        self.m_SockMgrConnMgr.set_object_name(session_name)

        # 리스너 생성 (Create -> Listen) - SockMgrConnMgr 내부 구현 가정
        if not self.m_SockMgrConnMgr.listen(port):
            print(f"[AsWorld] Enable SockMgr Session Fail (Port:{port})")
            return False

        # 별도 스레드 월드 생성 및 실행
        self.m_SockMgrWorld = FrThreadWorld()
        if not self.m_SockMgrWorld.run():
            return False

        # 소켓 매니저를 새 월드로 이동
        self.m_SockMgrConnMgr.change_world(self.m_SockMgrWorld)
        
        print(f"[AsWorld] Enable SockMgr Session Success (Port:{port})")
        return True