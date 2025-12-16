import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrTimerSensor import FrTimerSensor

# -------------------------------------------------------
# AsWorldLogTimer Class
# 로그 파일 변경 주기(예: 자정, 매시 정각 등)를 감지하여 AsWorld에 알림
# -------------------------------------------------------
class AsWorldLogTimer(FrTimerSensor):
    def __init__(self, world):
        """
        C++: AsWorldLogTimer(AsWorld* World)
        """
        # 부모(FrTimerSensor) 초기화 -> 자동으로 TimerSrc에 등록됨
        super().__init__()
        
        # 원본 AsWorld 객체 저장
        self.m_AsWorld = world

    def __del__(self):
        """
        C++: ~AsWorldLogTimer()
        """
        super().__del__()

    def receive_time_out(self, reason, extra_reason):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        타이머 만료 시 호출 -> AsWorld의 로그 변경 이벤트 핸들러 호출
        """
        if self.m_AsWorld:
            # AsWorld.log_file_changed_event 호출 (Duck Typing)
            if hasattr(self.m_AsWorld, 'log_file_changed_event'):
                self.m_AsWorld.log_file_changed_event()
            else:
                pass
                # print("[AsWorldLogTimer] Error: AsWorld has no log_file_changed_event method")