import sys
import os
from collections import deque

# -------------------------------------------------------
# 프로젝트 경로 설정
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# FrEventSrc Class
# 이벤트 소스 기본 클래스 (Observer Pattern - Subject)
# -------------------------------------------------------
class FrEventSrc:
    def __init__(self):
        """
        C++: frEventSrc()
        """
        self.m_SensorList = []          # 등록된 모든 센서 리스트
        self.m_NotifySensorList = deque() # 알림 대기 중인 센서 큐 (Efficient Pop)

    def __del__(self):
        """
        C++: ~frEventSrc()
        """
        self.release_sensor(None)
        self.m_SensorList.clear()
        self.m_NotifySensorList.clear()

    # ---------------------------------------------------
    # Sensor Management (Register / Unregister)
    # ---------------------------------------------------
    def register_sensor(self, sensor):
        """
        C++: int RegisterSensor(frSensor* Sensor)
        """
        if sensor not in self.m_SensorList:
            self.m_SensorList.append(sensor)
        return 1

    def unregister_sensor(self, sensor):
        """
        C++: int UnRegisterSensor(frSensor* Sensor)
        """
        if sensor in self.m_SensorList:
            self.m_SensorList.remove(sensor)
        
        # 알림 대기열에서도 제거
        if sensor in self.m_NotifySensorList:
            self.m_NotifySensorList.remove(sensor)
        return 1

    def is_exist_instance(self, sensor):
        """
        C++: bool IsExistInstance(frSensor* Sensor)
        """
        return sensor in self.m_SensorList

    # ---------------------------------------------------
    # Event Dispatching logic
    # ---------------------------------------------------
    def insert_notify_sensor(self, sensor):
        """
        C++: void InsertNotifySensor(frSensor* Sensor)
        이벤트가 발생하여 처리가 필요한 센서를 대기열에 추가
        """
        self.m_NotifySensorList.append(sensor)

    def dispatch_sensor(self):
        """
        C++: int DisPatchSensor()
        대기열에 있는 센서들의 핸들러(SubjectChanged)를 호출
        """
        while self.m_NotifySensorList:
            # FIFO (First-In-First-Out) 처리
            sensor = self.m_NotifySensorList.popleft()
            
            # 센서가 활성화 상태인지 확인 후 실행
            # (Python에서는 FrSensor 구현에 따라 메서드 이름 확인 필요)
            if hasattr(sensor, 'is_enabled') and sensor.is_enabled():
                if hasattr(sensor, 'subject_changed'):
                    sensor.subject_changed()
        
        return 1

    def release_sensor(self, world_ptr):
        """
        C++: void ReleaseSensor(frWorld* WorldPtr)
        종료 시 센서들에게 자원 해제 알림
        """
        for sensor in self.m_SensorList:
            if hasattr(sensor, 'release_world'):
                sensor.release_world(world_ptr)
        
        self.m_SensorList.clear()

    # ---------------------------------------------------
    # Virtual Methods for Select Loop (From FrWorld interface)
    # C++ 헤더에는 선언되어 있을 가상 함수들
    # ---------------------------------------------------
    def make_select_request(self, rd_list, wr_list, ex_list, world_ptr):
        """
        자식 클래스(InputSrc, TimerSrc 등)에서 구현
        """
        pass

    def get_events(self, rd_list, wr_list, ex_list, world_ptr):
        """
        자식 클래스에서 구현
        """
        pass