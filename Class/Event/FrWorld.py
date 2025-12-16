import sys
import os
import select
import threading
import errno
import time

# -------------------------------------------------------
# 1. 프로젝트 경로 설정
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# 2. 모듈 Import
# -------------------------------------------------------
from Class.Event.FrEventSrc import FrEventSrc

# [Input Event Source]
try:
    from Class.Event.FrInputEventSrc import FrInputEventSrc
except ImportError:
    FrInputEventSrc = None

# [Timer Event Source]
try:
    from Class.Event.FrTimerEventSrc import FrTimerEventSrc
except ImportError:
    FrTimerEventSrc = None

# [Signal Event Source]
try:
    from Class.Event.FrSignalEventSrc import FrSignalEventSrc
except ImportError:
    FrSignalEventSrc = None

# [World Pipe & Message Info]
try:
    from Class.Event.FrWorldPipe import FrWorldPipe, FrMessageInfo
except ImportError:
    FrWorldPipe = None
    FrMessageInfo = None

# -------------------------------------------------------
# Enums
# -------------------------------------------------------
class FR_MODE:
    FR_MAIN = 0
    FR_SUB = 1

class EVENT_MSG:
    SENSOR_ADD = 1
    WORLD_THREAD_CLEAR = 2

# -------------------------------------------------------
# FrWorld Class
# 이벤트 루프 및 스레드/월드 관리자 (The Core Engine)
# -------------------------------------------------------
class FrWorld:
    # Static Members
    m_GlobalWorldId = 0
    m_frWorldInfoList = [] # List of {'world_id':..., 'thread_id':..., 'world_ptr':...}
    m_WorldInfoMgrLock = threading.Lock()
    m_MainWorldPtr = None
    m_ExitCode = 0
    m_Argc = 0
    m_Argv = []

    def __init__(self, mode=FR_MODE.FR_SUB):
        self.m_FrMode = mode
        self.m_RunStatus = False
        
        self.m_EventSrcList = [] # List of FrEventSrc
        
        # ---------------------------------------------------
        # Event Sources 초기화 및 등록
        # ---------------------------------------------------
        
        # 1. Input Event Source (소켓 I/O)
        if FrInputEventSrc:
            self.m_InputEventSrc = FrInputEventSrc()
        else:
            self.m_InputEventSrc = FrEventSrc() # Fallback

        # 2. Timer Event Source (타이머)
        if FrTimerEventSrc:
            self.m_TimerEventSrc = FrTimerEventSrc()
        else:
            self.m_TimerEventSrc = FrEventSrc() # Fallback
        
        # 리스트에 등록 (우선순위: Input -> Timer)
        self.register_event_src(self.m_InputEventSrc)
        self.register_event_src(self.m_TimerEventSrc)

        # 3. Signal Event Source (시그널 - Main World만 가짐)
        self.m_SignalEventSrc = None
        if self.m_FrMode == FR_MODE.FR_MAIN:
            if FrSignalEventSrc:
                self.m_SignalEventSrc = FrSignalEventSrc()
                self.register_event_src(self.m_SignalEventSrc)
            
            # 메인 월드 등록
            FrWorld.m_MainWorldPtr = self
            self.m_EventThreadId = threading.get_ident()
            self.register_world(self, self.m_EventThreadId)

        self.m_WorldPipe = None 
        
        self.m_WorldId = FrWorld.m_GlobalWorldId
        FrWorld.m_GlobalWorldId += 1
        
        self.m_MajorVersion = 0
        self.m_MinorVersion = 0
        self.m_VersionInfo = ""
        
        # Select용 변수
        self.rd_fds = []
        self.wr_fds = []
        self.ex_fds = []
        self.timeout = 1.0

    def __del__(self):
        self.unregister_world(self)
        
        # Pipe 정리
        if self.m_WorldPipe:
            # Python GC가 처리하겠지만 명시적 close 권장
            try: self.m_WorldPipe.close()
            except: pass

        # EventSrc 정리
        for src in self.m_EventSrcList:
            if hasattr(src, 'release_sensor'):
                src.release_sensor(self)
        self.m_EventSrcList.clear()

    # -------------------------------------------------------
    # Initialization & Main Loop
    # -------------------------------------------------------
    def init(self, argv):
        FrWorld.m_Argv = argv
        FrWorld.m_Argc = len(argv)

        if FrWorld.m_Argc == 2 and argv[1] == "-ver":
            if self.m_VersionInfo:
                print(f"{argv[0]} Ver. {self.m_MajorVersion}.{self.m_MinorVersion} {self.m_VersionInfo}")
            else:
                print(f"{argv[0]} Ver. No Defined")
            sys.stdout.flush()
            return False

        self.create_world_pipe()
        return self.app_start(FrWorld.m_Argc, FrWorld.m_Argv)

    def app_start(self, argc, argv):
        """
        C++: virtual bool AppStart(...)
        자식 클래스에서 오버라이딩
        """
        return True

    def set_version(self, major, minor, info):
        self.m_MajorVersion = major
        self.m_MinorVersion = minor
        self.m_VersionInfo = info

    def run_world(self):
        print(f"[FrWorld] RunWorld({self.m_WorldId}) Started")
        self.m_RunStatus = True
        
        while self.m_RunStatus:
            # 1. 이벤트 읽기 (Select 대기)
            # TimerEventSrc가 있다면 timeout 값이 자동으로 계산되어 갱신됨
            if self.read_event() < 0:
                time.sleep(0.1) # 에러 시 CPU 폭주 방지
                continue
                
            # 2. 이벤트 처리 (Dispatch)
            # 발생한 이벤트를 각 센서(소켓, 타이머, 시그널)에게 전달
            self.dispatch_src()
            
        print(f"[FrWorld] RunWorld({self.m_WorldId}) Finished")
        return True

    def is_running(self):
        return self.m_RunStatus

    def clean_up(self):
        print("CleanUp() virtual function")

    def stop(self):
        self.m_RunStatus = False
        # 메인 월드가 아니라면, 메인 월드에게 내 스레드 정리 요청
        if FrWorld.m_MainWorldPtr != self and FrWorld.m_MainWorldPtr:
            FrWorld.m_MainWorldPtr.send_event(EVENT_MSG.WORLD_THREAD_CLEAR, None, self)
        else:
            # 메인 월드는 Signal 등으로 종료됨
            pass

    def exit(self, exit_code):
        FrWorld.m_ExitCode = exit_code
        self.m_RunStatus = False
        self.clean_up()

    # -------------------------------------------------------
    # Event Source Management
    # -------------------------------------------------------
    def register_event_src(self, src):
        if src not in self.m_EventSrcList:
            self.m_EventSrcList.append(src)
        return 1

    def unregister_event_src(self, src):
        if src in self.m_EventSrcList:
            self.m_EventSrcList.remove(src)
        return 1

    # -------------------------------------------------------
    # Select Loop Logic
    # -------------------------------------------------------
    def make_select_request(self):
        # 리스트 초기화
        self.rd_fds.clear()
        self.wr_fds.clear()
        self.ex_fds.clear()
        
        self.timeout = None # None = 무한 대기

        # 각 EventSrc에게 요청 위임
        for src in self.m_EventSrcList:
            # 1. FrInputEventSrc: 소켓 FD 수집
            # 2. FrTimerEventSrc: 최소 타임아웃 계산 후 self.timeout 갱신
            # 3. FrSignalEventSrc: (Select와 무관, Pass)
            src.make_select_request(self.rd_fds, self.wr_fds, self.ex_fds, self)
        return 1

    def read_event(self):
        self.make_select_request()
        
        # 타임아웃 보정
        if self.timeout is not None and self.timeout < 0:
            self.timeout = 0

        try:
            # Python select
            r_in, w_in, x_in = select.select(self.rd_fds, self.wr_fds, self.ex_fds, self.timeout)
            
            # 결과 전달 -> 각 Src는 자신의 센서들에게 통지
            self.get_events(r_in, w_in, x_in)
            return 1

        except select.error as e:
            if e.args[0] == errno.EINTR:
                return 1 # Signal interrupt (정상)
            else:
                print(f"[Error] Select error: {e}")
                return -1
        except OSError as e:
             print(f"[Error] Select OSError: {e}")
             return -1
        except ValueError as e:
             print(f"[Error] Select ValueError: {e}")
             return -1

    def get_events(self, r_in, w_in, x_in):
        for src in self.m_EventSrcList:
            src.get_events(r_in, w_in, x_in, None)
        return 1

    def dispatch_src(self):
        for src in self.m_EventSrcList:
            src.dispatch_sensor()
        return 1

    # -------------------------------------------------------
    # Inter-World Communication (Pipe)
    # -------------------------------------------------------
    def create_world_pipe(self):
        if FrWorldPipe:
            self.m_WorldPipe = FrWorldPipe(self)
        else:
            print("[FrWorld] Warning: FrWorldPipe module not found.")

    def send_event(self, message, sensor, addition_info=None):
        """
        다른 스레드/월드에게 메시지 전송
        """
        if self.m_WorldPipe:
            if FrMessageInfo:
                info = FrMessageInfo(message, sensor, addition_info)
                self.m_WorldPipe.write(info)
                return 1
        else:
            # print(f"[Error] Does not exist world pipe WorldId({self.m_WorldId})")
            return -1
        return -1

    def attach_sensor(self, sensor):
        return self.send_event(EVENT_MSG.SENSOR_ADD, sensor)

    # -------------------------------------------------------
    # Global World Management (Thread Safe)
    # -------------------------------------------------------
    def register_world(self, world_ptr, thread_id):
        with FrWorld.m_WorldInfoMgrLock:
            info = {
                'world_id': world_ptr.m_WorldId,
                'thread_id': thread_id,
                'world_ptr': world_ptr
            }
            # print(f"[Debug] Register World Id : {world_ptr.m_WorldId}, tId : {thread_id}")
            FrWorld.m_frWorldInfoList.append(info)

    def unregister_world(self, world_ptr):
        with FrWorld.m_WorldInfoMgrLock:
            FrWorld.m_frWorldInfoList = [
                info for info in FrWorld.m_frWorldInfoList 
                if info['world_ptr'] != world_ptr or (FrWorld.m_MainWorldPtr == world_ptr)
            ]

    @staticmethod
    def find_world_info(thread_id):
        with FrWorld.m_WorldInfoMgrLock:
            for info in FrWorld.m_frWorldInfoList:
                if info['thread_id'] == thread_id:
                    return info['world_ptr']
        return None

    @staticmethod
    def get_current_world_id():
        tid = threading.get_ident()
        for info in FrWorld.m_frWorldInfoList:
            if info['thread_id'] == tid:
                return info['world_id']
        return int(tid)