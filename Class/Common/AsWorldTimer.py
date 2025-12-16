import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrTimerSensor import FrTimerSensor

# -------------------------------------------------------
# AsWorldTimer Class
# AsWorld를 대신해 타이머 이벤트를 수신하고 전달하는 헬퍼
# -------------------------------------------------------
class AsWorldTimer(FrTimerSensor):
    def __init__(self, world):
        """
        C++: AsWorldTimer(AsWorld* World)
        """
        # 부모(FrTimerSensor) 초기화 -> 자동으로 TimerSrc에 등록됨
        super().__init__()
        
        # 원본 AsWorld 객체 저장
        self.m_AsWorld = world

    def __del__(self):
        """
        C++: ~AsWorldTimer()
        """
        super().__del__()

    def receive_time_out(self, reason, extra_reason):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        타이머가 만료되면 호출됨 -> AsWorld에게 전달
        """
        if self.m_AsWorld:
            # AsWorld에 receive_time_out 메서드가 있다고 가정 (Duck Typing)
            if hasattr(self.m_AsWorld, 'receive_time_out'):
                self.m_AsWorld.receive_time_out(reason, extra_reason)
            else:
                # 로그 혹은 디버깅용
                # print("[AsWorldTimer] Error: AsWorld has no receive_time_out method")
                pass