import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrSensor import FrSensor, SENSOR_TYPE

# -------------------------------------------------------
# FrMsgSensor Class
# 객체 간 메시지 송수신을 중계하는 가상 센서
# -------------------------------------------------------
class FrMsgSensor(FrSensor):
    def __init__(self, obj, world_ptr=None):
        """
        C++: frMsgSensor(frObject* Obj, frWorld* WorldPtr)
        """
        # 부모 생성자 호출 (World 설정)
        super().__init__(world_ptr)
        
        # 기본적으로 비활성화 (필요시 enable 호출)
        self.disable()
        
        self.m_SensorType = SENSOR_TYPE.INPUT_SENSOR
        self.m_Object = obj # 메시지를 처리할 실제 객체 (FrObject)
        
        # EventSrc(InputEventSrc)에 등록
        self.register_sensor()

    def __del__(self):
        """
        C++: ~frMsgSensor()
        """
        self.unregister_sensor()
        # 부모 소멸자는 Python GC가 자동 호출하지만, 명시적 정리 필요 시 super().__del__() 호출 고려

    # ---------------------------------------------------
    # Interface Implementation (Dummy)
    # ---------------------------------------------------
    def make_select_request(self, rd_list, wr_list, ex_list, world_ptr):
        """
        물리적 소켓이 없으므로 아무것도 하지 않음
        """
        return 1

    def get_events(self, rd_list, wr_list, ex_list, world_ptr):
        """
        물리적 이벤트가 없으므로 아무것도 하지 않음
        """
        return 1

    # ---------------------------------------------------
    # Message Handling
    # ---------------------------------------------------
    def send_event(self, message, addition_info=None):
        """
        C++: bool SendEvent(int Message, void* AdditionInfo)
        월드를 통해 메시지 큐에 이벤트를 넣음
        """
        if self.m_WorldPtr:
            # SendEvent 반환값이 1이면 성공, -1이면 실패
            ret = self.m_WorldPtr.send_event(message, self, addition_info)
            return ret >= 0
        return False

    def recv_event(self, message, addition_info):
        """
        C++: void RecvEvent(int Message, void* AdditionInfo)
        월드로부터 메시지를 받으면 연결된 객체(m_Object)에게 전달
        """
        if self.m_Object:
            # m_Object는 RecvMessage 메서드를 가지고 있어야 함 (Duck Typing)
            if hasattr(self.m_Object, 'recv_message'):
                self.m_Object.recv_message(message, addition_info)
            else:
                print(f"[FrMsgSensor] Error: m_Object has no 'recv_message' method.")
        else:
            print("[FrMsgSensor] Error: m_Object is None")