import sys
import os
import time

# -------------------------------------------------------
# 1. 프로젝트 경로 설정
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrEventSrc import FrEventSrc

# -------------------------------------------------------
# FrTimerEventSrc Class
# 타이머 이벤트를 관리하는 소스 (등록된 타이머 중 가장 짧은 시간을 계산)
# -------------------------------------------------------
class FrTimerEventSrc(FrEventSrc):
    def __init__(self):
        """
        C++: frTimerEventSrc()
        """
        super().__init__()
        self.m_CurrentTimeSec = 0.0

    def make_select_request(self, rd_list, wr_list, ex_list, world_ptr):
        """
        C++: int MakeSelectRequest(...)
        
        등록된 타이머 센서들을 순회하며, 가장 급한(가까운) 타임아웃 시간을 찾아
        world_ptr.timeout에 설정합니다.
        """
        if not self.m_SensorList:
            # 등록된 타이머가 없으면 타임아웃에 영향을 주지 않음
            return 1

        # C++ 로직은 TimeVal 구조체에 절대 시간을 넣고 나중에 현재 시간을 빼는 방식이었으나,
        # Python FrTimerSensor 구현에서는 직접 (Target - Now)를 계산하여
        # world_ptr.timeout을 갱신하는 방식이 더 효율적입니다.
        
        # 현재 시간 (float seconds)
        # now = time.time() # or time.perf_counter()

        for sensor in self.m_SensorList:
            # 활성화된 센서만 처리
            if hasattr(sensor, 'is_enabled') and sensor.is_enabled():
                if hasattr(sensor, 'make_select_request'):
                    # 센서에게 위임 -> 센서 내부에서 world_ptr.timeout을 최소값으로 갱신
                    sensor.make_select_request(rd_list, wr_list, ex_list, world_ptr)
        
        # C++ 코드의 하단부 복잡한 시간 차감 계산(tv_usec < 0 보정 등)은
        # Python에서는 world_ptr.timeout이 float이므로 자동 처리됩니다.
        
        return 1

    def get_events(self, rd_list, wr_list, ex_list, world_ptr):
        """
        C++: int GetEvents(...)
        
        Select가 반환된 후(시간이 지났거나 I/O 발생),
        타이머 센서들에게 "시간 됐는지 확인해봐"라고 요청합니다.
        """
        # 현재 시간 갱신 (필요하다면 멤버 변수에 저장)
        self.m_CurrentTimeSec = time.time()

        for sensor in self.m_SensorList:
            if hasattr(sensor, 'is_enabled') and sensor.is_enabled():
                if hasattr(sensor, 'get_events'):
                    # 센서 내부에서 (현재시간 >= 목표시간) 체크 후 이벤트 발생
                    sensor.get_events(rd_list, wr_list, ex_list, world_ptr)
        
        return 1