import sys
import os
import select
import errno

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrSensor import FrSensor, SENSOR_TYPE

SOCK_INFO_WRITERABLE_STATUS_OK = 1
SOCK_INFO_WRITERABLE_STATUS_NOK = 0
SOCK_INFO_WRITERABLE_STATUS_UNKNOWN = -1

# -------------------------------------------------------
# Socket Info Constants & Structure
# -------------------------------------------------------
class SOCK_INFO_MODE:
    AF_INET_TCP = 0
    AF_INET_UDP = 1
    AF_UNIX = 2
    UNKNOWN = 99

class SOCK_INFO_USE_TYPE:
    LISTEN = 0
    CONNECT = 1
    CONNECTED = 2
    UNKNOWN = 99

class FrSocketInfo:
    def __init__(self):
        self.session_name = ""
        self.listener_name = ""
        self.fd = -1
        self.socket_mode = SOCK_INFO_MODE.UNKNOWN
        self.use_type = SOCK_INFO_USE_TYPE.UNKNOWN
        self.address = ""
        self.port_no = 0
        self.session_time = ""
        self.detail_time = 0
        self.writerable_status = True

    def __str__(self):
        return (f"Session: {self.session_name}, FD: {self.fd}, "
                f"Addr: {self.address}:{self.port_no}, "
                f"Writable: {self.writerable_status}")

# -------------------------------------------------------
# FrSockFdManager Class
# 전체 소켓 센서 상태 모니터링 및 관리
# -------------------------------------------------------
class FrSockFdManager:
    def __init__(self):
        pass

    def __del__(self):
        pass

    # ---------------------------------------------------
    # Monitoring Logic
    # ---------------------------------------------------
    def get_sock_infos(self, check_writable=False, sec=0, micro_sec=0):
        """
        C++: void GetSockInfos(...)
        전체 센서 중 소켓 센서만 골라내어 정보를 수집함
        """
        info_list = []
        
        # Global Sensor List 접근 시 Lock 필요
        with FrSensor.m_SensorMgrLock:
            global_list = FrSensor.get_global_sensor_list()
            
            for sensor in global_list:
                # FrSocketSensor인지 확인 (Duck Typing: get_socket_info 메서드 유무)
                if hasattr(sensor, 'get_socket_info'):
                    info = sensor.get_socket_info() # FrSocketInfo 반환 가정
                    
                    if info:
                        if check_writable:
                            info.writerable_status = self.socket_check(info, sec, micro_sec)
                        
                        info_list.append(info)
        
        return info_list

    def show_sock_fd_status(self):
        """
        C++: void ShowSockFdStatus()
        콘솔에 전체 소켓 상태 출력
        """
        infos = self.get_sock_infos()
        for info in infos:
            self.print_fr_socket_info(info)

    def print_fr_socket_info(self, info):
        """
        C++: void PrintFrSocketInfo(...)
        """
        print("Display Socket Info")
        print(f"SessionName\t\t: {info.session_name}")
        print(f"ListenerName\t\t: {info.listener_name}")
        print(f"FD\t\t\t: {info.fd}")
        
        mode_str = "UNKNOWN"
        if info.socket_mode == SOCK_INFO_MODE.AF_INET_TCP: mode_str = "AF_INET_TCP"
        elif info.socket_mode == SOCK_INFO_MODE.AF_INET_UDP: mode_str = "AF_INET_UDP"
        
        print(f"SocketMode\t\t: {mode_str}")
        
        use_str = "UNKNOWN"
        if info.use_type == SOCK_INFO_USE_TYPE.LISTEN: use_str = "LISTEN"
        elif info.use_type == SOCK_INFO_USE_TYPE.CONNECT: use_str = "CONNECT"
        elif info.use_type == SOCK_INFO_USE_TYPE.CONNECTED: use_str = "CONNECTED"
        
        print(f"UseType\t\t\t: {use_str}")
        print(f"Address\t\t\t: {info.address}")
        print(f"PortNo\t\t\t: {info.port_no}")
        
        status_str = "OK" if info.writerable_status else "NOK"
        print(f"SessionTime\t\t: {info.session_time}.{info.detail_time}")
        print(f"WriterableStatus\t: {status_str}")
        print("-" * 40)

    # ---------------------------------------------------
    # Socket Health Check
    # ---------------------------------------------------
    def socket_check(self, info, sec, micro_sec):
        """
        C++: bool SocketCheck(...)
        Select를 이용해 해당 소켓이 쓰기 가능한지(Writable) 확인
        """
        if info.use_type == SOCK_INFO_USE_TYPE.LISTEN:
            return True
            
        if info.fd < 0:
            return False

        timeout = sec + (micro_sec / 1000000.0)
        
        try:
            # select([], [fd], [], timeout) -> 쓰기 가능 여부 확인
            _, w_list, _ = select.select([], [info.fd], [], timeout)
            
            if info.fd in w_list:
                return True
            
            # Timeout case
            # print(f"[FrSockFdManager] Socket Write Timeout: {info.session_name}")
            return False
            
        except OSError as e:
            print(f"[FrSockFdManager] Check Error: {e}")
            return False

    # ---------------------------------------------------
    # Socket Control
    # ---------------------------------------------------
    def shut_down_sock(self, target_info):
        """
        C++: bool ShutDownSock(...)
        정보가 일치하는 소켓을 찾아 강제로 shutdown 시킴
        """
        ret = False
        
        with FrSensor.m_SensorMgrLock:
            global_list = FrSensor.get_global_sensor_list()
            
            for sensor in global_list:
                if hasattr(sensor, 'get_socket_info'):
                    info = sensor.get_socket_info()
                    
                    if self._compare_info(target_info, info):
                        # 소켓 센서라면 shutdown 메서드가 있을 것임
                        if hasattr(sensor, 'shutdown'):
                            sensor.shutdown()
                            ret = True
                        elif hasattr(sensor, 'close'): # Fallback
                            sensor.close()
                            ret = True
                        break
        return ret

    def _compare_info(self, info1, info2):
        return (info1.fd == info2.fd and
                info1.port_no == info2.port_no and
                info1.session_name == info2.session_name)