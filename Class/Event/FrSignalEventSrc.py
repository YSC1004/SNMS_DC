import sys
import os
import signal

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrEventSrc import FrEventSrc

# -------------------------------------------------------
# FrSignalEventSrc Class
# 시그널(Signal) 이벤트를 감지하고 분배하는 클래스
# -------------------------------------------------------
class FrSignalEventSrc(FrEventSrc):
    _instance = None # Singleton pattern for signal handler

    def __init__(self):
        """
        C++: frSignalEventSrc()
        """
        super().__init__()
        
        # 싱글톤 인스턴스 설정 (Python signal handler는 전역 함수여야 하므로 필요)
        if FrSignalEventSrc._instance is None:
            FrSignalEventSrc._instance = self
        
        # 모든 시그널을 기본값(Default)으로 초기화하는 로직은 
        # Python에서는 굳이 필요 없거나 위험할 수 있음 (시스템 기본 동작 유지 권장)

    def __del__(self):
        """
        C++: ~frSignalEventSrc()
        """
        pass

    # ---------------------------------------------------
    # Sensor Management
    # ---------------------------------------------------
    def register_sensor(self, sensor):
        """
        C++: int RegisterSensor(frSensor* Sensor)
        특정 시그널에 대한 핸들러를 등록
        """
        sig_no = sensor.get_signal_number()
        
        # 유효성 검사
        if not self._is_valid_signal(sig_no):
            print(f"[FrSignalEventSrc] Invalid Signal Number : {sig_no}")
            return -1

        # 중복 체크 (이미 등록된 센서인지)
        for s in self.m_SensorList:
            if hasattr(s, 'get_signal_number') and s.get_signal_number() == sig_no:
                print(f"[FrSignalEventSrc] Already Register Signal : {sig_no}")
                return -1

        # 부모 클래스(EventSrc) 리스트에 추가
        super().register_sensor(sensor)

        # 실제 OS 시그널 핸들러 등록
        try:
            signal.signal(sig_no, self._signal_handler_wrapper)
            print(f"[FrSignalEventSrc] Register Signal : {self.signal_to_string(sig_no)}")
        except ValueError as e:
            # SIGKILL(9) 등은 핸들링 불가
            print(f"[FrSignalEventSrc] Failed to register signal {sig_no}: {e}")
            return -1
            
        return 1

    def unregister_sensor(self, sensor):
        """
        C++: int UnRegisterSensor(frSensor* Sensor)
        """
        sig_no = sensor.get_signal_number()
        
        super().unregister_sensor(sensor)
        
        # 기본 핸들러로 복구
        try:
            signal.signal(sig_no, signal.SIG_DFL)
        except:
            pass
            
        return 1

    # ---------------------------------------------------
    # Interface Methods (Select Loop)
    # ---------------------------------------------------
    def make_select_request(self, rd_list, wr_list, ex_list, world_ptr):
        # 시그널은 Select 루프와 무관함
        return 1

    def get_events(self, rd_list, wr_list, ex_list, world_ptr):
        # 시그널은 비동기적으로 발생하므로 여기서 polling 하지 않음
        return 1

    # ---------------------------------------------------
    # Signal Handling Logic
    # ---------------------------------------------------
    @staticmethod
    def _signal_handler_wrapper(signum, frame):
        """
        Python signal.signal()에 등록될 콜백 함수
        """
        if FrSignalEventSrc._instance:
            FrSignalEventSrc._instance.signal_handler(signum)

    def signal_handler(self, signum):
        """
        C++: void SignalHandler(int Signal)
        발생한 시그널에 해당하는 센서를 찾아 subject_changed 호출
        """
        # print(f"[FrSignalEventSrc] Receive Signal : {self.signal_to_string(signum)}")
        
        for sensor in self.m_SensorList:
            if hasattr(sensor, 'get_signal_number') and sensor.get_signal_number() == signum:
                if hasattr(sensor, 'is_enabled') and sensor.is_enabled():
                    if hasattr(sensor, 'subject_changed'):
                        sensor.subject_changed()
                    return

    # ---------------------------------------------------
    # Utilities
    # ---------------------------------------------------
    def _is_valid_signal(self, sig_no):
        try:
            signal.Signals(sig_no)
            return True
        except ValueError:
            return False

    @staticmethod
    def signal_to_string(sig_no):
        """
        C++: string SignalToString(int SigNo)
        """
        try:
            return signal.Signals(sig_no).name
        except ValueError:
            return f"UNKNOWN({sig_no})"