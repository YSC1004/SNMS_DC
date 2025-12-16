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
# FrDayChangeTimer Class
# 매일 자정(00:00:00)에 이벤트를 발생시키는 타이머 센서
# -------------------------------------------------------
class FrDayChangeTimer(FrTimerSensor):
    def __init__(self):
        """
        C++: frDayChangeTimer()
        """
        super().__init__()
        # 생성 시 자동으로 타이머를 시작하고 싶다면 여기서 set_timer() 호출
        # C++ 코드에서는 명시적으로 호출하는 구조이므로 비워둠

    def __del__(self):
        """
        C++: ~frDayChangeTimer()
        """
        super().__del__()

    def remain_day_time(self):
        """
        C++: time_t RemainDayTime()
        자정까지 남은 시간(초) 계산
        """
        cur_time = FrTime()
        return cur_time.get_remain_day_sec()

    def set_timer(self):
        """
        C++: void SetTimer()
        남은 시간만큼 타이머 설정 (Reason ID: 0)
        """
        remain = self.remain_day_time()
        
        # 로그 출력 (선택 사항)
        # print(f"[FrDayChangeTimer] Timer set for next day change ({remain} sec later)")
        
        # FrTimerSensor.set_timer(sec, reason, extra)
        super().set_timer(remain, 0, None)

    def receive_time_out(self, reason, extra_reason):
        """
        [추가 구현] 타이머 만료 시(자정) 호출되는 콜백
        C++ 소스에는 없으나, 센서로서 동작하려면 구현 필요
        """
        print("[FrDayChangeTimer] !!! Day Changed !!!")
        
        # 여기서 날짜 변경 시 필요한 비즈니스 로직 수행
        # ...
        
        # 다음 날 자정을 위해 타이머 재설정 (재귀적 호출 아님, 이벤트 루프에 등록)
        self.set_timer()