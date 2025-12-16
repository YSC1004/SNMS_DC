import sys
import os
import fcntl
import errno

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrSensor import FrSensor, SENSOR_TYPE, SENSOR_MODE
from Class.Event.FrRdFdSensorTimer import FrRdFdSensorTimer

# -------------------------------------------------------
# FrRdFdSensor Class
# 소켓 등 파일 디스크립터(FD)의 I/O 이벤트를 감시하는 센서
# -------------------------------------------------------
class FrRdFdSensor(FrSensor):
    def __init__(self, fd=-1, sensor_mode=SENSOR_MODE.FR_NORMAL_SENSOR):
        """
        C++ 생성자 오버로딩 통합:
        1. frRdFdSensor()
        2. frRdFdSensor(int FileDes)
        3. frRdFdSensor(FR_SENSOR_MODE SensorMode)
        """
        super().__init__(sensor_mode=sensor_mode)
        
        self.m_FD = fd
        self.m_SensorType = SENSOR_TYPE.INPUT_SENSOR
        self.m_frRdFdSensorTimer = None # 타이머 헬퍼 (Lazy Init)
        self.m_BlockMode = True

        # FD가 유효하고 Normal 모드면 설정 및 등록
        if self.m_frSensorMode == SENSOR_MODE.FR_NORMAL_SENSOR:
            if self.m_FD != -1:
                self.set_close_on_exec(True)
            self.register_sensor()

    def __del__(self):
        """
        C++: ~frRdFdSensor()
        """
        if self.m_FD != -1:
            self.close()
        
        # 타이머 해제 (참조 끊기)
        if self.m_frRdFdSensorTimer:
            self.m_frRdFdSensorTimer = None
            
        self.unregister_sensor()

    # ---------------------------------------------------
    # Interface Methods (For Select)
    # ---------------------------------------------------
    def make_select_request(self, rd_list, wr_list, ex_list, world_ptr):
        """
        C++: FD_SET(m_FD, Rd)
        감시할 FD를 읽기 리스트(rd_list)에 추가
        """
        if self.m_FD != -1:
            rd_list.append(self.m_FD)
        return 1

    def get_events(self, rd_list, wr_list, ex_list, world_ptr):
        """
        C++: if(FD_ISSET(m_FD, Rd)) ...
        FD가 준비되었으면 Notify 대기열에 추가
        """
        if self.m_FD != -1 and (self.m_FD in rd_list):
            if self.m_WorldPtr and self.m_WorldPtr.m_InputEventSrc:
                self.m_WorldPtr.m_InputEventSrc.insert_notify_sensor(self)
        return 1

    # ---------------------------------------------------
    # I/O Operations
    # ---------------------------------------------------
    def write(self, packet):
        """
        C++: int Write(char* Packet, int Length)
        """
        if self.m_FD == -1: return -1
        try:
            # packet이 str이면 encode, bytes면 그대로 사용
            data = packet.encode() if isinstance(packet, str) else packet
            return os.write(self.m_FD, data)
        except OSError as e:
            print(f"[FrRdFdSensor] Write Error: {e}")
            return -1

    def read(self, length):
        """
        C++: int Read(char* Packet, int Length)
        Python은 읽은 데이터를 반환 (bytes)
        """
        if self.m_FD == -1: return None
        try:
            return os.read(self.m_FD, length)
        except OSError as e:
            # Non-blocking 모드에서 데이터 없음 에러(EAGAIN) 처리 등은 상황에 따라 필요
            if e.errno == errno.EAGAIN or e.errno == errno.EWOULDBLOCK:
                return b""
            print(f"[FrRdFdSensor] Read Error: {e}")
            return None

    # ---------------------------------------------------
    # Socket Options
    # ---------------------------------------------------
    def set_block_mode(self, mode):
        """
        C++: SetBlockMode(bool Mode)
        """
        if self.m_FD == -1:
            print("[FrRdFdSensor] FD(-1) is invalid")
            return False

        try:
            flags = fcntl.fcntl(self.m_FD, fcntl.F_GETFL)
            if mode:
                # Blocking
                flags &= ~os.O_NONBLOCK
            else:
                # Non-Blocking
                flags |= os.O_NONBLOCK
            
            fcntl.fcntl(self.m_FD, fcntl.F_SETFL, flags)
            self.m_BlockMode = mode
            return True
        except OSError as e:
            print(f"[FrRdFdSensor] Fail to block mode change: {e}")
            return False

    def set_close_on_exec(self, mode):
        """
        C++: SetCloseOnExec(bool Mode)
        """
        if self.m_FD == -1: return False
        try:
            flags = fcntl.fcntl(self.m_FD, fcntl.F_GETFD)
            if mode:
                flags |= fcntl.FD_CLOEXEC
            else:
                flags &= ~fcntl.FD_CLOEXEC
            fcntl.fcntl(self.m_FD, fcntl.F_SETFD, flags)
            return True
        except OSError:
            return False

    def close(self):
        """
        C++: bool Close()
        """
        if self.m_FD == -1: return True
        
        try:
            os.close(self.m_FD)
        except OSError as e:
            print(f"[FrRdFdSensor] Close error: {e}")
            return False
        finally:
            self.m_FD = -1
            self.disable()
        return True

    def set_fd(self, new_fd):
        self.m_FD = new_fd

    def get_fd(self):
        return self.m_FD

    def is_block_mode(self):
        return self.m_BlockMode

    # ---------------------------------------------------
    # Timer Delegation (To FrRdFdSensorTimer)
    # ---------------------------------------------------
    def _ensure_timer(self):
        if self.m_frRdFdSensorTimer is None:
            self.m_frRdFdSensorTimer = FrRdFdSensorTimer(self)
            # 헬퍼 센서는 부모가 아님. 독립적으로 TimerSrc에 등록됨.
            # C++ 코드에서도 SetParentSensor는 주석처리 되어있거나 
            # Timer가 Sensor를 부모로 알게 하는 구조임.
            
    def set_timer(self, interval, reason, extra_reason=None):
        self._ensure_timer()
        return self.m_frRdFdSensorTimer.set_timer(interval, reason, extra_reason)

    def set_timer2(self, millisec, reason, extra_reason=None):
        self._ensure_timer()
        return self.m_frRdFdSensorTimer.set_timer2(millisec, reason, extra_reason)

    def cancel_timer(self, key):
        if not self.m_frRdFdSensorTimer: return False
        return self.m_frRdFdSensorTimer.cancel_timer(key)

    def cancel_all_timer(self):
        if self.m_frRdFdSensorTimer:
            self.m_frRdFdSensorTimer.cancel_all_timer()

    def kill_timer(self):
        """
        C++: KillTimer (delete timer object)
        """
        if self.m_frRdFdSensorTimer:
            # TimerSrc에서 등록 해제 등을 수행하기 위해 소멸자 유도 필요할 수 있음
            # Python에서는 참조를 끊으면 GC되나, 명시적 해제를 위해 unregister 호출
            self.m_frRdFdSensorTimer.unregister_sensor()
            self.m_frRdFdSensorTimer = None

    # ---------------------------------------------------
    # Virtual Function (For Override)
    # ---------------------------------------------------
    def receive_time_out(self, reason, extra_reason):
        """
        C++: virtual void ReceiveTimeOut(...)
        TimerHelper가 시간 만료 시 이 함수를 호출함.
        자식 클래스에서 오버라이딩하여 사용.
        """
        # print("[FrRdFdSensor] ReceiveTimeOut is virtual function")
        pass