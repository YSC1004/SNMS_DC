import sys
import os
import time

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrSensor import FrSensor, SENSOR_TYPE, SENSOR_MODE

# -------------------------------------------------------
# Timer Object Class
# 개별 타이머 정보를 저장하는 구조체
# -------------------------------------------------------
class TimeOut:
    def __init__(self, target_time, reason, key, extra_reason=None):
        self.m_TargetTime = target_time  # 만료 예정 시간 (float timestamp)
        self.m_Reason = reason
        self.m_Key = key
        self.m_ExtraReason = extra_reason

# -------------------------------------------------------
# FrTimerSensor Class
# 타이머 기능을 제공하는 센서 (사용자는 이를 상속받아 ReceiveTimeOut 구현)
# -------------------------------------------------------
class FrTimerSensor(FrSensor):
    LONG_TIME = 31536000.0 # 1년 (초 단위)

    def __init__(self):
        """
        C++: frTimerSensor()
        """
        super().__init__()
        self.m_SensorType = SENSOR_TYPE.TIMER_SENSOR
        
        # 타이머 목록 (TimeOut 객체 리스트), 시간순 정렬 유지
        self.m_TimerList = [] 
        self.m_KeySequence = 0
        
        # 가장 빠른 타임아웃 시간 (최적화용 캐시)
        self.m_MinTimeOut = 0.0
        
        # 센서 등록
        self.register_sensor()
        
        # Dummy Timer (C++ 로직 유지: 리스트가 비지 않도록)
        self.set_timer(int(self.LONG_TIME), 10000)

    def __del__(self):
        """
        C++: ~frTimerSensor()
        """
        self.unregister_sensor()
        self.m_TimerList.clear()

    # ---------------------------------------------------
    # Interface Methods (From FrEventSrc/FrWorld)
    # ---------------------------------------------------
    def make_select_request(self, rd_list, wr_list, ex_list, world_ptr):
        """
        C++: MakeSelectRequest(...)
        가장 급한 타이머까지 남은 시간을 계산하여 world_ptr.timeout 갱신
        """
        if not self.m_TimerList:
            return 1

        # 현재 시간
        now = time.time()
        
        # 리스트의 첫 번째가 가장 빠른 시간 (정렬 유지됨)
        min_timeout = self.m_TimerList[0].m_TargetTime
        
        # 남은 시간 계산 (최소 0초)
        remain = max(0.0, min_timeout - now)
        
        # World의 타임아웃보다 더 짧으면 갱신 (더 빨리 깨어나야 함)
        if world_ptr.timeout is None or remain < world_ptr.timeout:
            world_ptr.timeout = remain
            
        return 1

    def get_events(self, rd_list, wr_list, ex_list, world_ptr):
        """
        C++: GetEvents(...)
        만료된 타이머가 있는지 확인하고 알림 요청
        """
        if not self.m_TimerList:
            return 1

        # FrTimerEventSrc가 갱신해둔 현재 시간 사용 (또는 직접 조회)
        # world_ptr.m_TimerEventSrc.m_CurrentTimeSec 등을 쓸 수 있으나,
        # 여기서는 직접 조회하여 정확도 높임
        now = time.time()
        
        # 첫 번째 타이머가 만료되었는지 확인
        if now >= self.m_TimerList[0].m_TargetTime:
            # 이벤트 발생 알림 (자신의 subject_changed가 호출되도록 함)
            # FrWorld -> TimerEventSrc -> insert_notify_sensor -> dispatch -> subject_changed
            if self.m_WorldPtr and self.m_WorldPtr.m_TimerEventSrc:
                self.m_WorldPtr.m_TimerEventSrc.insert_notify_sensor(self)
        
        return 1

    def subject_changed(self):
        """
        C++: SubjectChanged()
        실제 타이머 만료 처리 및 콜백 호출
        """
        if not self.m_TimerList:
            return 1

        now = time.time()
        
        # 만료된 타이머들을 순차적으로 처리 (리스트 앞부분부터)
        # 주의: 루프 도중 리스트가 변경될 수 있으므로 복사본이나 while 사용
        
        while self.m_TimerList:
            timer = self.m_TimerList[0]
            
            # 아직 시간이 안 된 타이머를 만나면 중단 (정렬되어 있으므로)
            # 약간의 오차(0.001초) 허용
            if timer.m_TargetTime > (now + 0.001):
                break
                
            # 만료된 타이머 제거
            self.m_TimerList.pop(0)
            
            # 사용자 콜백 호출 (자식 클래스에서 구현)
            self.receive_time_out(timer.m_Reason, timer.m_ExtraReason)
            
            # 만료 처리 후 센서가 해제되었는지 확인 (C++ 로직 반영)
            if self.m_WorldPtr and self.m_WorldPtr.m_TimerEventSrc:
                if not self.m_WorldPtr.m_TimerEventSrc.is_exist_instance(self):
                    return 1

        return 1

    # ---------------------------------------------------
    # Timer Management
    # ---------------------------------------------------
    def set_timer(self, sec, reason, extra_reason=None):
        """
        C++: SetTimer(int Sec, int Reason, void* ExtraReason)
        초 단위 타이머 설정
        """
        if sec < 0: # 0초도 허용 (즉시 실행)
            print(f"[FrTimerSensor] Invalid SetTimer Value : {sec}")
            return -1
        
        return self.set_time_out(sec, 0, reason, extra_reason)

    def set_timer2(self, millisec, reason, extra_reason=None):
        """
        C++: SetTimer2(int MiliSec, ...)
        밀리초 단위 타이머 설정
        """
        if millisec < 0:
            print(f"[FrTimerSensor] Invalid SetTimer2 Value : {millisec}")
            return -1
            
        return self.set_time_out(0, millisec, reason, extra_reason)

    def set_time_out(self, sec, millisec, reason, extra_reason):
        """
        내부 구현: 목표 시간 계산 및 리스트 삽입
        """
        now = time.time()
        duration = sec + (millisec / 1000.0)
        target_time = now + duration
        
        self.m_KeySequence += 1
        new_timer = TimeOut(target_time, reason, self.m_KeySequence, extra_reason)
        
        # 시간순 정렬 삽입 (Insertion Sort)
        inserted = False
        for i, timer in enumerate(self.m_TimerList):
            if timer.m_TargetTime > target_time:
                self.m_TimerList.insert(i, new_timer)
                inserted = True
                break
        
        if not inserted:
            self.m_TimerList.append(new_timer)
            
        return self.m_KeySequence

    def cancel_timer(self, key):
        """
        C++: bool CancelTimer(timer_key Key)
        """
        for i, timer in enumerate(self.m_TimerList):
            if timer.m_Key == key:
                del self.m_TimerList[i]
                
                # 리스트가 비면 더미 타이머 추가 (C++ 로직)
                if not self.m_TimerList:
                    self.set_timer(int(self.LONG_TIME), 10000)
                return True
        return False

    def cancel_all_timer(self):
        self.m_TimerList.clear()
        self.set_timer(int(self.LONG_TIME), 10000)

    def get_timer_count(self):
        # 더미 타이머 1개를 제외한 개수 반환
        return max(0, len(self.m_TimerList) - 1)

    # ---------------------------------------------------
    # Virtual Method (User should override)
    # ---------------------------------------------------
    def receive_time_out(self, reason, extra_reason):
        """
        C++: virtual void ReceiveTimeOut(...)
        사용자가 상속받아 구현해야 함
        """
        print(f"[FrTimerSensor] TimeOut Occurred! Reason: {reason}")