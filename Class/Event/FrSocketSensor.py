import sys
import os
import socket
import select
import threading
import time
import struct
import errno

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrRdFdSensor import FrRdFdSensor
from Class.Event.FrSensor import SENSOR_MODE
from Class.Event.FrSockFdManager import FrSocketInfo, SOCK_INFO_MODE, SOCK_INFO_USE_TYPE
from Class.Util.FrTime import FrTime
from Class.Util.FrUtilMisc import FrUtilMisc

# -------------------------------------------------------
# Constants
# -------------------------------------------------------
CONNECT_SOCKET = 0
LISTEN_SOCKET = 1
DEFAULT_SOCK_CHECK_TIME_OUT = 50000 # microseconds

# -------------------------------------------------------
# Helper Class: WriteData
# 비동기 전송을 위한 데이터 버퍼
# -------------------------------------------------------
class WriteData:
    def __init__(self, data):
        self.m_Data = data # bytes
        self.m_Length = len(data)

# -------------------------------------------------------
# FrSocketSensor Class
# 소켓 통신 (TCP/UDP/Unix) 및 버퍼링 관리
# -------------------------------------------------------
class FrSocketSensor(FrRdFdSensor):
    # Static Members
    m_SystemMaxSendSockBuf = -1
    m_SystemMaxRecvSockBuf = -1
    
    def __init__(self, fd=-1, sensor_mode=SENSOR_MODE.FR_NORMAL_SENSOR):
        super().__init__(fd, sensor_mode)
        
        self.m_UseFlag = CONNECT_SOCKET
        self.m_SocketMode = -1 # AF_INET etc
        self.m_SocketType = -1 # SOCK_STREAM etc
        self.m_SocketPath = ""
        
        self.m_ListenerName = ""
        self.m_PeerIp = ""
        self.m_PortNo = 0
        
        self.m_WriteTimerSensor = None
        self.m_WriterableCheck = False
        
        self.m_SessionTime = ""
        self.m_SessionTimeDetail = 0
        
        self.m_ObjectType = 5 # FrSocketSensor ID
        self.m_UseType = SOCK_INFO_USE_TYPE.UNKNOWN
        
        self.m_WriterableCheckTimeOut = DEFAULT_SOCK_CHECK_TIME_OUT
        
        self.m_CurDataBufSize = 0
        self.m_MaxDataBufSize = -1
        
        self.m_WriteDataList = [] # List[WriteData]
        self.m_WriteDataLock = threading.Lock()
        self.m_WriteLock = threading.Lock()

        # 초기에는 Disable 상태 (연결 후 Enable)
        self.disable()

    def __del__(self):
        self.close()
        # WriteData 정리
        with self.m_WriteDataLock:
            self.m_WriteDataList.clear()
        
        if self.m_WriteTimerSensor:
            self.m_WriteTimerSensor.kill_timer() # or unregister
            self.m_WriteTimerSensor = None
            
        super().__del__()

    # ---------------------------------------------------
    # Socket Creation & Control
    # ---------------------------------------------------
    def create(self, socket_mode=socket.AF_INET, socket_type=socket.SOCK_STREAM):
        """
        C++: bool Create(int SocketMode, int SocketType)
        """
        self.m_SocketMode = socket_mode
        self.m_SocketType = socket_type
        
        if self.m_FD != -1:
            self.close()
            
        try:
            sock = socket.socket(self.m_SocketMode, self.m_SocketType)
            self.m_FD = sock.fileno()
            # 소켓 객체를 유지해야 GC되지 않음 (Python 특성)
            self.m_SockObj = sock 
            return True
        except OSError as e:
            self.set_obj_err_msg(f"socket create error : {e}")
            return False

    def listen(self, port_or_path, backlog=5):
        """
        C++: Listen(int Port, ...) / Listen(string Path, ...)
        """
        self.m_UseType = SOCK_INFO_USE_TYPE.LISTEN
        
        if self.m_FD == -1:
            self.set_obj_err_msg("Must call Create() first")
            return False

        try:
            # SO_REUSEADDR 설정
            self.m_SockObj.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            self._set_sock_opt() # 버퍼 크기 등 설정

            if self.m_SocketMode == socket.AF_INET:
                # TCP/IP
                self.m_SockObj.bind(('0.0.0.0', port_or_path))
                self.m_PortNo = port_or_path
            elif self.m_SocketMode == socket.AF_UNIX:
                # Unix Domain Socket
                if os.path.exists(port_or_path):
                    os.unlink(port_or_path)
                self.m_SockObj.bind(port_or_path)
                self.m_SocketPath = port_or_path
            
            if self.m_SocketType == socket.SOCK_STREAM:
                self.m_SockObj.listen(backlog)
            
            self._set_session_time()
            self.set_close_on_exec(True)
            
            self.m_UseFlag = LISTEN_SOCKET
            self.enable()
            return True

        except OSError as e:
            self.set_obj_err_msg(f"Listen Error: {e}")
            return False

    def connect(self, address, port=0):
        """
        C++: Connect(Address, Port) / Connect(Path)
        """
        self.m_UseType = SOCK_INFO_USE_TYPE.CONNECT
        
        if self.m_FD != -1:
            self.close()
            
        # Create 호출이 안된 경우 자동 생성 (AF_INET 기본)
        if self.m_FD == -1:
            mode = socket.AF_UNIX if port == 0 else socket.AF_INET
            if not self.create(mode): return False

        try:
            self._set_sock_opt()
            
            if self.m_SocketMode == socket.AF_INET:
                self.m_PeerIp = address
                self.m_PortNo = port
                self.m_SockObj.connect((address, port))
            else:
                self.m_SocketPath = address
                self.m_SockObj.connect(address)
            
            self._set_session_time()
            self.set_close_on_exec(True)
            
            self.enable()
            self.m_UseFlag = CONNECT_SOCKET
            return True

        except OSError as e:
            self.set_obj_err_msg(f"Connect Error: {e}")
            self.close()
            return False

    def accept(self, client_sensor):
        """
        C++: bool Accept(frSocketSensor* SocketSensor)
        """
        try:
            conn, addr = self.m_SockObj.accept()
            
            # client_sensor 객체에 소켓 할당
            client_sensor.m_SockObj = conn
            client_sensor.m_FD = conn.fileno()
            client_sensor.m_SocketMode = self.m_SocketMode
            
            if self.m_SocketMode == socket.AF_INET:
                client_sensor.m_PeerIp = addr[0]
                client_sensor.m_PortNo = addr[1]
            else:
                client_sensor.m_PeerIp = "localhost"
                
            client_sensor._set_session_time()
            client_sensor.m_ListenerName = self.get_object_name()
            client_sensor.m_UseType = SOCK_INFO_USE_TYPE.CONNECTED
            
            client_sensor._set_sock_opt()
            client_sensor.set_close_on_exec(True)
            client_sensor.enable()
            
            return True
        except OSError as e:
            self.set_obj_err_msg(f"Accept Error: {e}")
            return False

    # ---------------------------------------------------
    # Event Handling
    # ---------------------------------------------------
    def subject_changed(self):
        """
        C++: int SubjectChanged()
        """
        if self.m_UseFlag == CONNECT_SOCKET:
            self.receive_message()
        elif self.m_UseFlag == LISTEN_SOCKET:
            if self.m_SocketType == socket.SOCK_STREAM:
                self.accept_socket()
            else:
                self.receive_message()
        return 1

    # Virtual Methods
    def accept_socket(self):
        print("[FrSocketSensor] AcceptSocket is virtual function")

    def receive_message(self):
        print("[FrSocketSensor] ReceiveMessage is virtual function")

    # ---------------------------------------------------
    # Data Send / Receive
    # ---------------------------------------------------
    def write(self, packet, length=0):
        """
        C++: int Write(char* Packet, int Length)
        Non-blocking 버퍼링 지원
        """
        if not self.m_WriterableCheck:
            # 일반 모드: 바로 전송
            return super().write(packet)
        else:
            # 버퍼링 모드
            # 1. 소켓이 쓰기 가능한지 확인
            if self.is_writerable(0, 0):
                # 2. 쌓여있는 데이터 먼저 전송
                with self.m_WriteLock:
                    while True:
                        data_obj = self.get_write_data()
                        if data_obj:
                            ret = self._write_socket(data_obj.m_Data)
                            if ret < 0: # 전송 실패 시 중단 (데이터 유실 가능성 있음, C++ 로직 따름)
                                break
                        else:
                            break
                    
                    # 3. 현재 데이터 전송 시도
                    return self._write_socket(packet)
            else:
                # 4. 쓰기 불가능하면 버퍼에 저장
                return self.put_write_data(packet)

    def _write_socket(self, data):
        return super().write(data)

    def is_writerable(self, sec=0, micro_sec=-1):
        """
        Select를 이용해 소켓이 쓰기 가능한지 확인
        """
        if micro_sec == -1: micro_sec = self.m_WriterableCheckTimeOut
        timeout = sec + (micro_sec / 1000000.0)
        
        try:
            _, w_list, _ = select.select([], [self.m_FD], [], timeout)
            return self.m_FD in w_list
        except:
            return False

    # ---------------------------------------------------
    # Buffering Logic
    # ---------------------------------------------------
    def set_writerable_check(self, flag):
        self.m_WriterableCheck = flag
        if flag and not self.m_WriteTimerSensor:
            # 타이머 센서 생성 (TimerHelper)
            from Class.Event.FrSocketSensorTimer import FrSocketSensorTimer
            self.m_WriteTimerSensor = FrSocketSensorTimer(self)
            self.m_WriteTimerSensor.set_timer(1, 1) # 1초 후 시작
        elif not flag and self.m_WriteTimerSensor:
            self.m_WriteTimerSensor.kill_timer()
            self.m_WriteTimerSensor = None

    def put_write_data(self, packet):
        """
        데이터를 버퍼(리스트)에 저장
        """
        data = packet.encode() if isinstance(packet, str) else packet
        w_data = WriteData(data)
        
        with self.m_WriteDataLock:
            self.m_WriteDataList.append(w_data)
            if self.m_MaxDataBufSize > 0:
                self.m_CurDataBufSize += w_data.m_Length
                if self.m_CurDataBufSize > self.m_MaxDataBufSize:
                    self.recv_overflow_data_buf_info(self.m_MaxDataBufSize, self.m_CurDataBufSize)
                    return -1
        return w_data.m_Length

    def get_write_data(self):
        with self.m_WriteDataLock:
            if self.m_WriteDataList:
                data = self.m_WriteDataList.pop(0)
                if self.m_MaxDataBufSize > 0:
                    self.m_CurDataBufSize -= data.m_Length
                return data
        return None

    def data_send_time(self):
        """
        타이머에 의해 호출됨: 버퍼에 쌓인 데이터를 전송 시도
        """
        with self.m_WriteDataLock:
            has_data = len(self.m_WriteDataList) > 0
            
        if has_data:
            with self.m_WriteLock:
                while self.is_writerable(0, 0):
                    data = self.get_write_data()
                    if data:
                        if self._write_socket(data.m_Data) < 0:
                            break
                    else:
                        break
                        
        # 타이머 재설정 (계속 감시)
        if self.m_WriteTimerSensor:
            self.m_WriteTimerSensor.set_timer2(350, 1) # 350ms 후

    # ---------------------------------------------------
    # Info & Utils
    # ---------------------------------------------------
    def get_socket_info(self):
        """
        C++: void GetSocketInfo(FR_SOCKET_INFO_T& Info)
        FrSocketInfo 객체 반환
        """
        info = FrSocketInfo()
        info.fd = self.m_FD
        info.session_name = self.get_object_name()
        info.listener_name = self.m_ListenerName
        info.session_time = self.m_SessionTime
        info.detail_time = self.m_SessionTimeDetail
        info.use_type = self.m_UseType
        
        if self.m_SocketMode == socket.AF_INET:
            info.socket_mode = SOCK_INFO_MODE.AF_INET_TCP # UDP 확인 필요시 수정
            if self.m_UseFlag == CONNECT_SOCKET:
                info.address = self.m_PeerIp
                info.port_no = self.m_PortNo
            else:
                info.address = "localhost"
                info.port_no = self.m_PortNo
        else:
            info.socket_mode = SOCK_INFO_MODE.AF_UNIX
            info.address = self.m_SocketPath
            
        return info

    def _set_sock_opt(self):
        # 버퍼 크기 등 설정 (Python 기본값 사용하되 필요 시 setsockopt 호출)
        try:
            # 예: self.m_SockObj.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65535)
            return True
        except:
            return False

    def _set_session_time(self):
        self.m_SessionTime = FrTime.get_current_time_string()
        # Detail(ms)는 string 파싱 혹은 별도 저장
        
    def recv_overflow_data_buf_info(self, max_size, cur_size):
        print(f"[FrSocketSensor] Buffer Overflow! Max:{max_size}, Cur:{cur_size}")

    def close(self):
        if self.m_SocketMode == socket.AF_UNIX and self.m_UseType == SOCK_INFO_USE_TYPE.LISTEN:
            if self.m_SocketPath and os.path.exists(self.m_SocketPath):
                try: os.unlink(self.m_SocketPath)
                except: pass
        
        # 타이머 정리
        if self.m_WriteTimerSensor:
            self.m_WriteTimerSensor.kill_timer()
            
        return super().close()