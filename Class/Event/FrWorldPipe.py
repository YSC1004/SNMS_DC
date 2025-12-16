import sys
import os
import threading
import queue
import struct

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrSensor import FrSensor, SENSOR_TYPE
from Class.Event.FrMsgSensor import FrMsgSensor

# -------------------------------------------------------
# Message Constants & Structure
# -------------------------------------------------------
class WORLD_MSG:
    SENSOR_ADD = 1
    WORLD_THREAD_CLEAR = 2
    DUMMY_FR_MESSAGE = 999

class FrMessageInfo:
    def __init__(self, message, sensor=None, addition_info=None):
        self.m_Message = message
        self.m_Sensor = sensor
        self.m_AdditionInfo = addition_info

# -------------------------------------------------------
# FrWorldPipe Class
# 이벤트 루프(select)를 깨우기 위한 Pipe와 데이터 전달용 Queue를 결합
# -------------------------------------------------------
class FrWorldPipe(FrSensor):
    def __init__(self, world_ptr):
        """
        C++: frWorldPipe()
        """
        super().__init__(world_ptr)
        self.m_SensorType = SENSOR_TYPE.INPUT_SENSOR
        
        # Pipe 생성 (Select 깨우기 용도)
        self.r_fd, self.w_fd = os.pipe()
        
        # Thread-safe Queue (데이터 객체 전달 용도)
        self.m_MsgQueue = queue.Queue()
        
        # Non-blocking 설정 (선택사항, 안전을 위해)
        os.set_blocking(self.r_fd, False)
        os.set_blocking(self.w_fd, False)

        # 자신을 InputSrc에 등록하여 Select 감시 대상이 되게 함
        self.register_sensor()

    def __del__(self):
        self.close()

    def close(self):
        self.unregister_sensor()
        if self.r_fd: os.close(self.r_fd)
        if self.w_fd: os.close(self.w_fd)
        self.r_fd = None
        self.w_fd = None

    # ---------------------------------------------------
    # Interface Methods (For Select)
    # ---------------------------------------------------
    def make_select_request(self, rd_list, wr_list, ex_list, world_ptr):
        """
        읽기 파이프(r_fd)를 감시 리스트에 추가
        """
        if self.r_fd is not None:
            rd_list.append(self.r_fd)
        return 1

    def get_events(self, rd_list, wr_list, ex_list, world_ptr):
        """
        읽기 파이프에 데이터가 들어오면(이벤트 발생) 처리
        """
        if self.r_fd in rd_list:
            self.receive_message()
        return 1

    # ---------------------------------------------------
    # Logic Implementation
    # ---------------------------------------------------
    def write(self, msg_info):
        """
        외부에서 호출: 큐에 데이터를 넣고 파이프에 신호를 보냄
        """
        self.m_MsgQueue.put(msg_info)
        try:
            # 1바이트를 써서 select를 깨움
            os.write(self.w_fd, b'1')
            return 1
        except OSError as e:
            print(f"[FrWorldPipe] Write Error: {e}")
            return -1

    def receive_message(self):
        """
        C++: int ReceiveMessage()
        큐에서 메시지를 꺼내 처리
        """
        try:
            # 파이프 버퍼 비우기 (깨우기 신호 제거)
            # 큐에 쌓인 만큼 읽거나, 단순히 1바이트 읽기
            # 여기서는 큐가 빌 때까지 처리하므로, 파이프는 큐 사이즈만큼 읽어주는게 좋음
            while True:
                try:
                    data = os.read(self.r_fd, 1024)
                    if not data: break
                except BlockingIOError:
                    break
        except OSError:
            pass

        # 큐에 쌓인 모든 메시지 처리
        while not self.m_MsgQueue.empty():
            try:
                info = self.m_MsgQueue.get_nowait()
            except queue.Empty:
                break

            self._process_single_message(info)
            
        return 1

    def _process_single_message(self, info):
        """개별 메시지 처리 로직"""
        
        # 1. Thread Clear Message
        if info.m_Message == WORLD_MSG.WORLD_THREAD_CLEAR:
            print("[FrWorldPipe] WORLD_THREAD_CLEAR TRY")
            
            # 순환 참조 방지: 함수 내부 Import
            from Class.Event.FrThreadWorld import FrThreadWorld
            
            ptr = info.m_AdditionInfo
            if isinstance(ptr, FrThreadWorld):
                # 스레드가 wait 상태일 수 있으므로 더미 이벤트 전송
                ptr.send_event(WORLD_MSG.DUMMY_FR_MESSAGE, None, None)
                
                if ptr.wait_finish():
                    print("[FrWorldPipe] WORLD_THREAD_CLEAR SUCCESS")
                    # Python은 delete 불필요, 참조 해제만
                else:
                    print("[FrWorldPipe] WORLD_THREAD_CLEAR FAIL")

        # 2. Dummy Message (Just Wake up)
        elif info.m_Message == WORLD_MSG.DUMMY_FR_MESSAGE:
            pass

        # 3. Normal Messages
        else:
            # C++: Lock -> GetGlobalSensorList -> Find Sensor -> Process -> Unlock
            # Python: Global List는 Thread-safe하지 않으므로 Lock 사용
            
            with FrSensor.m_SensorMgrLock:
                global_list = FrSensor.get_global_sensor_list()
                
                # 센서가 유효한지(살아있는지) 확인
                if info.m_Sensor in global_list:
                    sensor = info.m_Sensor
                    
                    # 월드 체크
                    if sensor.m_WorldPtr != self.m_WorldPtr:
                        print("[FrWorldPipe] Error: Different Event World")
                        return -1

                    # 메시지 분기
                    if info.m_Message == WORLD_MSG.SENSOR_ADD:
                        sensor.register_sensor()
                    else:
                        # MsgSensor로 캐스팅하여 처리 (Duck Typing)
                        if hasattr(sensor, 'recv_event'):
                            sensor.recv_event(info.m_Message, info.m_AdditionInfo)
                        else:
                            print(f"[FrWorldPipe] Sensor {sensor} has no recv_event")
                else:
                    # print(f"[FrWorldPipe] Can't Find Sensor : {info.m_Sensor}")
                    pass