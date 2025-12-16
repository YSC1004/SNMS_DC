import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrTimerSensor import FrTimerSensor
from Class.Util.FrTime import FrTime

# -------------------------------------------------------
# FrHourChangeTimer Class
# 매 정시(XX:00:00)에 이벤트를 발생시키는 타이머 센서
# -------------------------------------------------------
class FrHourChangeTimer(FrTimerSensor):
    def __init__(self):
        """
        C++: frHourChangeTimer()
        """
        super().__init__()

    def __del__(self):
        """
        C++: ~frHourChangeTimer()
        """
        super().__del__()

    def remain_hour_time(self):
        """
        C++: time_t RemainHourTime()
        다음 정시까지 남은 시간(초) 계산
        """
        cur_time = FrTime()
        return cur_time.get_remain_hour_sec()

    def set_timer(self):
        """
        C++: void SetTimer()
        남은 시간만큼 타이머 설정 (Reason ID: 0)
        """
        remain = self.remain_hour_time()
        
        # 로그 출력 (선택 사항)
        # print(f"[FrHourChangeTimer] Timer set for next hour change ({remain} sec later)")
        
        # FrTimerSensor.set_timer(sec, reason, extra)
        super().set_timer(remain, 0, None)

    def receive_time_out(self, reason, extra_reason):
        """
        [추가 구현] 타이머 만료 시(정시) 호출되는 콜백
        """
        print(f"[FrHourChangeTimer] !!! Hour Changed !!!")
        
        # 정시 변경 시 수행할 비즈니스 로직 (예: 시간별 통계 저장 등)
        # ...
        
        # 다음 정시를 위해 타이머 재설정 (반복 동작)
        self.set_timer()