import sys
import os
import threading

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrWorld import FrWorld

# -------------------------------------------------------
# Enums (Sensor Types & Modes)
# -------------------------------------------------------
class SENSOR_TYPE:
    INPUT_SENSOR = 0
    TIMER_SENSOR = 1
    SIGNAL_SENSOR = 2

class SENSOR_MODE:
    FR_NORMAL_SENSOR = 0
    FR_NO_SENSOR = 1

# -------------------------------------------------------
# FrSensor Class
# 모든 이벤트 핸들러(소켓, 타이머 등)의 부모 클래스
# -------------------------------------------------------
class FrSensor:
    # Static Members
    m_GlobalSensorList = []
    m_SensorMgrLock = threading.Lock()

    def __init__(self, world_ptr=None, sensor_mode=SENSOR_MODE.FR_NORMAL_SENSOR):
        """
        C++: frSensor(frWorld* WorldPtr) / frSensor(FR_SENSOR_MODE SensorMode)
        """
        self.m_frSensorMode = sensor_mode
        self.m_IsEnable = True
        self.m_Priority = 0
        self.m_SignalNumber = -1
        self.m_SensorType = -1
        self.m_ParentSensor = None
        self.m_ChildSensorList = []
        self.m_WorldPtr = None

        if self.m_frSensorMode == SENSOR_MODE.FR_NORMAL_SENSOR:
            if world_ptr is None:
                # 현재 스레드의 World 찾기
                current_tid = threading.get_ident()
                self.m_WorldPtr = FrWorld.find_world_info(current_tid)
                
                # 못 찾으면 메인 월드 할당 (C++ 로직)
                if self.m_WorldPtr is None:
                    print(f"[FrSensor] Can't Find World({current_tid}). Using Main World.")
                    self.m_WorldPtr = FrWorld.m_MainWorldPtr
            else:
                self.m_WorldPtr = world_ptr

            self.register_global_sensor(self)
        else:
            # NO_SENSOR 모드
            self.m_IsEnable = False

    def __del__(self):
        """
        C++: ~frSensor()
        """
        if self.m_frSensorMode == SENSOR_MODE.FR_NORMAL_SENSOR:
            self.unregister_global_sensor(self)
            
            # 자식 센서 정리
            for child in self.m_ChildSensorList:
                child.clear_parent_sensor()
            self.m_ChildSensorList.clear()

            if self.m_ParentSensor:
                self.unset_parent_sensor()

    # -------------------------------------------------------
    # Sensor Control (Enable/Disable)
    # -------------------------------------------------------
    def enable(self):
        if self.m_frSensorMode == SENSOR_MODE.FR_NORMAL_SENSOR:
            self.m_IsEnable = True

    def disable(self):
        if self.m_frSensorMode == SENSOR_MODE.FR_NORMAL_SENSOR:
            self.m_IsEnable = False

    def is_enabled(self):
        return self.m_IsEnable

    # -------------------------------------------------------
    # Hierarchy Management (Parent/Child)
    # -------------------------------------------------------
    def set_parent_sensor(self, parent_sensor):
        if self.m_ParentSensor:
            print("[FrSensor] Already Register Parent Sensor")
            return

        if parent_sensor in self.m_ChildSensorList:
            print("[FrSensor] Current Set Sensor is Child Sensor of this Sensor")
            return

        self.m_ParentSensor = parent_sensor
        self.m_ParentSensor.register_child_sensor(self)

    def unset_parent_sensor(self):
        if self.m_ParentSensor:
            self.m_ParentSensor.unregister_child_sensor(self)
            self.m_ParentSensor = None
        else:
            print("[FrSensor] Not yet Parent Sensor Set")

    def clear_parent_sensor(self):
        self.m_ParentSensor = None

    def register_child_sensor(self, sensor):
        if sensor in self.m_ChildSensorList:
            print("[FrSensor] Already Register Child Sensor")
            return False
        self.m_ChildSensorList.append(sensor)
        return True

    def unregister_child_sensor(self, sensor):
        if sensor in self.m_ChildSensorList:
            self.m_ChildSensorList.remove(sensor)
            return True
        print("[FrSensor] Can't Find ChildSensor")
        return False

    # -------------------------------------------------------
    # Event Handling (Virtual Methods)
    # -------------------------------------------------------
    def subject_changed(self):
        """
        C++: virtual int SubjectChanged()
        이벤트가 발생했을 때 호출되는 메인 핸들러
        """
        return 1

    def get_signal_number(self):
        return self.m_SignalNumber

    # -------------------------------------------------------
    # World Management
    # -------------------------------------------------------
    def change_world(self, new_world):
        if new_world == self.m_WorldPtr:
            return 1

        self.unregister_sensor()
        
        self.m_WorldPtr = new_world
        self.m_WorldPtr.attach_sensor(self) # attach_sensor 내부에서 register_sensor 호출됨

        # 자식 센서들도 월드 변경
        for child in self.m_ChildSensorList:
            child.change_world(self.m_WorldPtr)
            
        self.init_msg_sensor(new_world)
        return 1

    def init_msg_sensor(self, world):
        """C++ 코드에는 없으나 change_world에서 호출되어 추가함 (Stub)"""
        pass

    def release_world(self, world_ptr):
        if world_ptr != self.m_WorldPtr:
            print("[FrSensor] Error: World is different...")
        self.m_WorldPtr = None

    # -------------------------------------------------------
    # Registration (EventSrc)
    # -------------------------------------------------------
    def register_sensor(self):
        """
        자신을 World의 적절한 EventSrc에 등록
        """
        if self.m_frSensorMode != SENSOR_MODE.FR_NORMAL_SENSOR:
            return 1
        
        if not self.m_WorldPtr:
            return 1

        if self.m_SensorType == SENSOR_TYPE.INPUT_SENSOR:
            self.m_WorldPtr.m_InputEventSrc.register_sensor(self)
        elif self.m_SensorType == SENSOR_TYPE.TIMER_SENSOR:
            self.m_WorldPtr.m_TimerEventSrc.register_sensor(self)
        elif self.m_SensorType == SENSOR_TYPE.SIGNAL_SENSOR:
            self.m_WorldPtr.m_SignalEventSrc.register_sensor(self)
        else:
            print("[FrSensor] Unknown Defined SensorType")
        
        return 1

    def unregister_sensor(self):
        """
        자신을 World의 EventSrc에서 해제
        """
        if self.m_frSensorMode != SENSOR_MODE.FR_NORMAL_SENSOR:
            return 1
        
        if not self.m_WorldPtr:
            return 1

        if self.m_SensorType == SENSOR_TYPE.INPUT_SENSOR:
            self.m_WorldPtr.m_InputEventSrc.unregister_sensor(self)
        elif self.m_SensorType == SENSOR_TYPE.TIMER_SENSOR:
            self.m_WorldPtr.m_TimerEventSrc.unregister_sensor(self)
        elif self.m_SensorType == SENSOR_TYPE.SIGNAL_SENSOR:
            self.m_WorldPtr.m_SignalEventSrc.unregister_sensor(self)
        
        return 1

    # -------------------------------------------------------
    # Global Management (Static)
    # -------------------------------------------------------
    @classmethod
    def register_global_sensor(cls, sensor):
        with cls.m_SensorMgrLock:
            cls.m_GlobalSensorList.append(sensor)

    @classmethod
    def unregister_global_sensor(cls, sensor):
        with cls.m_SensorMgrLock:
            if sensor in cls.m_GlobalSensorList:
                cls.m_GlobalSensorList.remove(sensor)

    @classmethod
    def get_global_sensor_list(cls):
        return cls.m_GlobalSensorList

    # -------------------------------------------------------
    # Interface Methods for Select (Virtual)
    # -------------------------------------------------------
    def make_select_request(self, rd_list, wr_list, ex_list, world_ptr):
        pass

    def get_events(self, rd_list, wr_list, ex_list, world_ptr):
        pass