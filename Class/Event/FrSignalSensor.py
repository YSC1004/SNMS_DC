import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrSensor import FrSensor, SENSOR_TYPE

# -------------------------------------------------------
# FrSignalSensor Class
# OS 시그널(SIGINT, SIGTERM 등)을 감지하는 센서
# -------------------------------------------------------
class FrSignalSensor(FrSensor):
    def __init__(self, sig_no):
        """
        C++: frSignalSensor(int SigNo)
        """
        # 부모 생성자 호출 (자동으로 현재 World 찾음)
        super().__init__()
        
        self.m_SensorType = SENSOR_TYPE.SIGNAL_SENSOR
        self.m_SignalNumber = sig_no
        
        # World의 SignalEventSrc에 등록
        self.register_sensor()

    def __del__(self):
        """
        C++: ~frSignalSensor()
        """
        self.unregister_sensor()

    # ---------------------------------------------------
    # Interface Methods (For Select Loop)
    # ---------------------------------------------------
    def make_select_request(self, rd_list, wr_list, ex_list, world_ptr):
        """
        C++: int MakeSelectRequest(...)
        시그널은 select()의 파일 디스크립터 감시 대상이 아니므로 아무것도 하지 않음.
        (Python signal handler나 signalfd 방식에 따라 처리가 달라지지만, 
         C++ 원본 로직상 여기서는 관여하지 않음)
        """
        return 1

    def get_events(self, rd_list, wr_list, ex_list, world_ptr):
        """
        C++: int GetEvents(...)
        """
        return 1

    # ---------------------------------------------------
    # Event Handler (To be overridden)
    # ---------------------------------------------------
    def subject_changed(self):
        """
        시그널이 발생했을 때 FrSignalEventSrc에 의해 호출됨.
        사용자는 이 클래스를 상속받아 이 메서드에 시그널 처리 로직을 구현.
        """
        # print(f"[FrSignalSensor] Signal {self.m_SignalNumber} Received!")
        return 1