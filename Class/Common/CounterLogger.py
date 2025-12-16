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
# CounterLogger Class
# 일정 주기로 횟수를 집계하여 출력하는 로거
# -------------------------------------------------------
class CounterLogger(FrTimerSensor):
    # Timer Reason ID
    COUNTER_LOG_TIMER = 56789

    def __init__(self):
        """
        C++: CounterLogger()
        """
        super().__init__()
        
        self.m_Interval = 30
        self.m_PrefixString = ""
        self.m_GapCount = 0
        self.m_TotalCount = 0
        
        # 현재 날짜 저장 (일자 변경 감지용)
        cur_time = FrTime()
        self.m_CurDay = cur_time.get_day()
        
        self.reset_count()

    def __del__(self):
        """
        C++: ~CounterLogger()
        """
        super().__del__()

    def start(self):
        """
        C++: void Start()
        타이머 시작
        """
        self.set_timer(self.m_Interval, self.COUNTER_LOG_TIMER)

    def set_log_interval(self, interval):
        """
        C++: void SetLogInterval(int Interval)
        """
        self.m_Interval = interval

    def set_log_prefix(self, prefix):
        """
        C++: void SetLogPrefix(string Prefix)
        """
        self.m_PrefixString = prefix

    def print_stats(self):
        """
        C++: void Print()
        통계 출력 및 카운터 리셋 로직
        """
        cur_time = FrTime()
        time_str = cur_time.get_time_string()
        
        # 로그 출력
        # [Time - Prefix : During 30 sec : 10 ea, Today : 100 ea]
        print(f"[{time_str} - {self.m_PrefixString} : During {self.m_Interval} sec : {self.m_GapCount} ea, Today : {self.m_TotalCount} ea]")
        
        # 구간 카운트 초기화
        self.m_GapCount = 0

        # 날짜 변경 체크 (일일 카운트 초기화)
        if self.m_CurDay != cur_time.get_day():
            self.m_CurDay = cur_time.get_day()
            self.m_TotalCount = 0

    def receive_time_out(self, reason, extra_reason):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        타이머 만료 시 호출
        """
        if reason == self.COUNTER_LOG_TIMER:
            self.print_stats()
            # 타이머 재설정 (반복)
            self.set_timer(self.m_Interval, self.COUNTER_LOG_TIMER)

    def increase_count(self):
        """
        C++: void IncreaseCount()
        외부에서 이벤트 발생 시 호출
        """
        self.m_GapCount += 1
        self.m_TotalCount += 1

    def reset_count(self):
        """
        C++: void ResetCount()
        """
        self.m_GapCount = 0
        self.m_TotalCount = 0

    def get_total_count(self):
        """
        C++: int GetTotalCount()
        """
        return self.m_TotalCount