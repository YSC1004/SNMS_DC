import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrTimerSensor import FrTimerSensor

# -------------------------------------------------------
# FrRdFdSensorTimer Class
# RdFdSensor를 대신해 타이머 이벤트를 수신하고 전달하는 헬퍼 클래스
# -------------------------------------------------------
class FrRdFdSensorTimer(FrTimerSensor):
    def __init__(self, sensor):
        """
        C++: frRdFdSensorTimer(frRdFdSensor* Sensor)
        """
        # 부모(FrTimerSensor) 초기화 -> 자동으로 World의 TimerSrc에 등록됨
        super().__init__()
        
        # 원본 센서 (FrRdFdSensor) 객체 저장
        self.m_frRdFdSensor = sensor

    def __del__(self):
        """
        C++: ~frRdFdSensorTimer()
        """
        super().__del__()

    def receive_time_out(self, reason, extra_reason):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        타이머가 만료되면 호출됨 -> 원본 센서에게 전달
        """
        if self.m_frRdFdSensor:
            # Duck Typing: 원본 센서에 receive_time_out 메서드가 있다고 가정
            if hasattr(self.m_frRdFdSensor, 'receive_time_out'):
                self.m_frRdFdSensor.receive_time_out(reason, extra_reason)
            else:
                # 로그 혹은 디버깅용 (선택사항)
                # print("[FrRdFdSensorTimer] Error: Target sensor has no receive_time_out")
                pass