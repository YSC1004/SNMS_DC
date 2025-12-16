import sys
import os
import threading

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 모듈 Import
from Class.Event.FrWorld import FrWorld
from Class.Event.FrMsgSensor import FrMsgSensor

# -------------------------------------------------------
# Global Error Message Helper
# C++의 전역 함수(SetGErrMsg) 대응
# -------------------------------------------------------
_GlobalErrMsg = ""

def set_g_err_msg(msg):
    global _GlobalErrMsg
    _GlobalErrMsg = msg

def get_g_err_msg():
    global _GlobalErrMsg
    return _GlobalErrMsg

# -------------------------------------------------------
# FrObject Class
# 모든 이벤트 처리 객체의 부모 클래스
# -------------------------------------------------------
class FrObject:
    def __init__(self, object_name=""):
        """
        C++: frObject(string ObjectName)
        """
        self.m_ObjectName = object_name
        self.m_ErrMsg = ""
        self.m_MsgSensor = None # FrMsgSensor

        self.m_ObjectType = -1
        self.m_ObjectTypeStr = ""

        # 현재 스레드 ID 저장 (어떤 World에 속하는지 알기 위함)
        self.m_TId = threading.get_ident()

    def __del__(self):
        """
        C++: ~frObject()
        """
        # 센서 해제
        self.m_MsgSensor = None

    # ---------------------------------------------------
    # Getters / Setters
    # ---------------------------------------------------
    def set_object_name(self, name):
        self.m_ObjectName = name

    def get_object_name(self):
        return self.m_ObjectName

    def set_obj_err_msg(self, msg):
        """
        C++: void SetObjErrMsg(const char *format, ...)
        Python에서는 호출자가 f-string으로 포맷팅해서 넘겨주는 것을 권장
        """
        self.m_ErrMsg = msg

    def get_obj_err_msg(self):
        return self.m_ErrMsg

    def get_object_type(self):
        return self.m_ObjectType
    
    def get_object_type_str(self):
        return self.m_ObjectTypeStr

    # ---------------------------------------------------
    # Message Sensor Initialization
    # ---------------------------------------------------
    def init_msg_sensor(self, arg=None):
        """
        C++ 오버로딩 2개를 하나로 통합:
        1. InitMsgSensor(THREAD_ID TId)
        2. InitMsgSensor(frWorld* WorldPtr)
        """
        # 기존 센서 정리
        self.m_MsgSensor = None

        target_world = None

        # 인자 타입 확인 (오버로딩 처리)
        if isinstance(arg, FrWorld):
            # Case 2: World 객체가 직접 넘어온 경우
            target_world = arg
        else:
            # Case 1: Thread ID(int)가 넘어오거나 None인 경우
            tid = arg if arg else self.m_TId
            target_world = FrWorld.find_world_info(tid)
            self.m_TId = tid # ID 갱신

        if target_world is None:
            print(f"[FrObject] Error: InitMsgSensor can't find world (TID: {self.m_TId})")
            return False

        # 메시지 센서 생성 (자신을 m_Object로 등록)
        self.m_MsgSensor = FrMsgSensor(self, target_world)
        return True

    # ---------------------------------------------------
    # Message Handling
    # ---------------------------------------------------
    def send_message(self, message, addition_info=None):
        """
        C++: bool SendMessage(int Message, void* AdditionInfo)
        """
        if self.m_MsgSensor:
            return self.m_MsgSensor.send_event(message, addition_info)
        else:
            # 센서가 없으면 초기화 시도 (Lazy Init)
            if self.init_msg_sensor():
                return self.m_MsgSensor.send_event(message, addition_info)
            else:
                # 초기화 실패
                # print("[FrObject] Please call InitMsgSensor first")
                return False

    def recv_message(self, message, addition_info):
        """
        C++: virtual void RecvMessage(...)
        자식 클래스에서 반드시 구현해야 함
        """
        print(f"[FrObject] Error: RecvMessage is a virtual function (Msg: {message})")