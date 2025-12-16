import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrTimerSensor import FrTimerSensor

# -------------------------------------------------------
# FrFilePollingTimer Class
# 파일 센서(FrFileFdSensor)를 주기적으로 활성화(Enable)시키는 타이머
# -------------------------------------------------------
class FrFilePollingTimer(FrTimerSensor):
    def __init__(self, sensor):
        """
        C++: frFilePollingTimer(frFileFdSensor* SensorPtr)
        """
        # 부모 클래스(FrTimerSensor) 초기화
        super().__init__()
        
        # 제어 대상 센서 저장
        self.m_frFileFdSensor = sensor

    def __del__(self):
        """
        C++: ~frFilePollingTimer()
        """
        super().__del__()

    def receive_time_out(self, reason, extra_reason):
        """
        C++: void ReceiveTimeOut(...)
        타이머가 만료되면, 연결된 파일 센서를 다시 활성화(Enable) 시킴
        """
        if self.m_frFileFdSensor:
            # Duck Typing: enable 메서드가 있는지 확인
            if hasattr(self.m_frFileFdSensor, 'enable'):
                # 센서를 활성화하여 다시 I/O 감시 상태로 만듦
                self.m_frFileFdSensor.enable()
            else:
                print("[FrFilePollingTimer] Error: Target sensor has no 'enable' method")