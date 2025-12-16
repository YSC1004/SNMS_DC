import sys
import os
import errno

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrFdPipeSensor import FrFdPipeSensor

# -------------------------------------------------------
# FrPipeSensor Class
# 파이프 생성 및 읽기/쓰기 센서(FrFdPipeSensor) 관리자
# -------------------------------------------------------
class FrPipeSensor:
    def __init__(self):
        """
        C++: frPipeSensor()
        """
        # [0]: Read Sensor, [1]: Write Sensor
        self.m_PipeSensor = [None, None]

    def __del__(self):
        """
        C++: ~frPipeSensor()
        """
        self.close_pipe()

    def create_pipe(self):
        """
        C++: int CreatePipe()
        OS 파이프를 생성하고 두 개의 센서(Read/Write)를 연결함
        """
        self.close_pipe() # 기존 파이프 정리

        try:
            # os.pipe() -> (read_fd, write_fd)
            r_fd, w_fd = os.pipe()
            
            # 파이프 센서 생성 (자신(self)을 이벤트 수신자로 등록)
            # FrFdPipeSensor(sensor, file_des)
            self.m_PipeSensor[0] = FrFdPipeSensor(self, r_fd) # Read Pipe
            self.m_PipeSensor[1] = FrFdPipeSensor(self, w_fd) # Write Pipe
            
            # 쓰기용 파이프는 읽기 이벤트를 감시할 필요가 없으므로 Disable
            # (Select 루프에서 제외됨)
            self.m_PipeSensor[1].disable()
            
            return 1
            
        except OSError as e:
            print(f"[FrPipeSensor] Pipe create error: {e}")
            return -1

    def close_pipe(self):
        """
        C++: void ClosePipe()
        """
        if self.m_PipeSensor[0]:
            self.m_PipeSensor[0].close() # FD 닫기 및 Unregister
            self.m_PipeSensor[0] = None
            
        if self.m_PipeSensor[1]:
            self.m_PipeSensor[1].close()
            self.m_PipeSensor[1] = None

    def write(self, packet, length=0):
        """
        C++: int Write(char* Packet, int Length)
        쓰기용 파이프 센서를 통해 데이터 전송
        """
        if self.m_PipeSensor[1]:
            # Python에서는 length가 없어도 됨 (len(packet) 사용)
            return self.m_PipeSensor[1].write(packet)
        return -1

    def read(self, length):
        """
        C++: int Read(char* Packet, int Length)
        읽기용 파이프 센서를 통해 데이터 수신
        """
        if self.m_PipeSensor[0]:
            return self.m_PipeSensor[0].read(length)
        return None

    def receive_message(self):
        """
        C++: virtual int ReceiveMessage()
        FrFdPipeSensor가 데이터를 감지하면(SubjectChanged) 이 메서드를 호출함.
        자식 클래스에서 오버라이딩하여 비즈니스 로직 구현.
        """
        # print("[FrPipeSensor] ReceiveMessage is virtual function")
        return 1

    def get_world(self):
        """
        C++: frWorld* GetWorld()
        """
        if self.m_PipeSensor[0]:
            return self.m_PipeSensor[0].m_WorldPtr
        return None