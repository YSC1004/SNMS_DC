import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrTimerSensor import FrTimerSensor

# -------------------------------------------------------
# FrSocketSensorTimer Class
# 소켓 센서의 데이터 전송 재시도를 위한 타이머 헬퍼
# -------------------------------------------------------
class FrSocketSensorTimer(FrTimerSensor):
    def __init__(self, sensor):
        """
        C++: frSocketSensorTimer(frSocketSensor* Sensor)
        """
        # 부모 생성자 호출 (자동으로 TimerEventSrc에 등록됨)
        super().__init__()
        
        # 원본 소켓 센서 저장
        self.m_SocketSensor = sensor

    def __del__(self):
        """
        C++: ~frSocketSensorTimer()
        """
        super().__del__()

    def kill_timer(self):
        """
        명시적 종료를 위한 헬퍼 메서드
        """
        self.unregister_sensor()

    def receive_time_out(self, reason, extra_reason):
        """
        C++: void ReceiveTimeOut(...)
        타이머 만료 시 소켓 센서의 data_send_time() 호출
        """
        if self.m_SocketSensor:
            # Duck Typing: data_send_time 메서드가 있는지 확인
            if hasattr(self.m_SocketSensor, 'data_send_time'):
                # 버퍼에 남은 데이터를 다시 전송 시도
                self.m_SocketSensor.data_send_time()
            else:
                pass 
                # print("[FrSocketSensorTimer] Error: Sensor has no data_send_time")