import sys
import os
import threading

# -------------------------------------------------------
# 1. 프로젝트 경로 설정
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# 2. 모듈 Import
# -------------------------------------------------------
from Class.Event.FrSockFdManager import FrSockFdManager, FrSocketInfo, \
    SOCK_INFO_WRITERABLE_STATUS_OK, SOCK_INFO_WRITERABLE_STATUS_NOK

# [주의] AsWorld는 여기서 import 하지 않고 __init__ 내부에서 import 합니다.

# -------------------------------------------------------
# ConnectionMgr Class
# 연결된 모든 소켓 세션(AsSocket) 관리자
# -------------------------------------------------------
class ConnectionMgr(FrSockFdManager):
    def __init__(self):
        """
        C++: ConnectionMgr()
        """
        super().__init__()
        
        # 연결된 소켓 객체 리스트 (List of AsSocket)
        self.m_SocketConnectionList = []
        
        # 세션 이름 리스트 (List of str)
        self.m_CurrentSessionId = []
        
        # 동시성 제어용 락
        self.m_Lock = threading.Lock()
        
        # [수정] 순환 참조 방지를 위해 함수 내부에서 Import 후 등록
        # ConnectionMgr가 생성되면 자동으로 Global AsWorld 리스트에 등록됨
        from Class.Common.AsWorld import AsWorld
        AsWorld.register_connection_mgr(self)

    def __del__(self):
        """
        C++: ~ConnectionMgr()
        """
        # [수정] 소멸 시 AsWorld 목록에서 제거
        try:
            from Class.Common.AsWorld import AsWorld
            AsWorld.deregister_connection_mgr(self)
        except ImportError:
            pass
        
        self.socket_remove_lock()
        
        # 관리 중인 소켓 모두 닫기
        for socket in self.m_SocketConnectionList:
            if hasattr(socket, 'close'):
                socket.close()
        
        self.m_SocketConnectionList.clear()
        self.socket_remove_unlock()

    # ---------------------------------------------------
    # List Management
    # ---------------------------------------------------
    def add(self, socket_obj):
        """
        C++: void Add(AsSocket* Socket)
        """
        with self.m_Lock:
            self.m_SocketConnectionList.append(socket_obj)

    def remove(self, socket_obj):
        """
        C++: void Remove(AsSocket* Socket)
        소켓 객체를 리스트에서 제거하고 닫음
        """
        self.socket_remove_lock()
        
        try:
            session_name = socket_obj.get_session_name()
            if session_name in self.m_CurrentSessionId:
                self.m_CurrentSessionId.remove(session_name)
            
            if socket_obj in self.m_SocketConnectionList:
                self.m_SocketConnectionList.remove(socket_obj)
                
            # 소켓 닫기 (C++ delete Socket 대응)
            if hasattr(socket_obj, 'close'):
                socket_obj.close()
                
        except Exception as e:
            print(f"[ConnectionMgr] Remove Error: {e}")
            
        self.socket_remove_unlock()

    def find_session(self, session_name):
        """
        C++: AsSocket* FindSession(const string& SessionName)
        """
        with self.m_Lock:
            for socket in self.m_SocketConnectionList:
                if socket.get_session_name() == session_name:
                    return socket
        return None

    def is_valid_connection(self, socket_obj):
        with self.m_Lock:
            return socket_obj in self.m_SocketConnectionList

    # ---------------------------------------------------
    # Session Name Management
    # ---------------------------------------------------
    def add_session_name(self, session_name):
        with self.m_Lock:
            if session_name in self.m_CurrentSessionId:
                print(f"[ConnectionMgr] Already Register SessionName : {session_name}")
                return False
            self.m_CurrentSessionId.append(session_name)
            return True

    def remove_session_name(self, session_name):
        with self.m_Lock:
            if session_name in self.m_CurrentSessionId:
                self.m_CurrentSessionId.remove(session_name)
                return True
            return False

    # ---------------------------------------------------
    # Lock Helper (C++ 스타일)
    # ---------------------------------------------------
    def socket_remove_lock(self):
        self.m_Lock.acquire()

    def socket_remove_unlock(self):
        self.m_Lock.release()

    # ---------------------------------------------------
    # Command & Info
    # ---------------------------------------------------
    def cmd_open_port_info(self, session_name, port_info):
        """
        C++: bool CmdOpenPortInfo(...)
        특정 세션에 포트 정보 전송 명령
        """
        socket = self.find_session(session_name)
        if socket:
            # AsSocket.cmd_open_port_info 호출 (가상함수)
            socket.cmd_open_port_info(port_info)
            return True
        return False

    def send_all_cmd_open_port_info(self, port_info):
        """
        모든 세션에 포트 정보 전송
        """
        with self.m_Lock:
            for socket in self.m_SocketConnectionList:
                socket.cmd_open_port_info(port_info)

    def send_cmd_log_status_change(self, log_ctl, session_name=""):
        """
        특정 세션 또는 전체 세션에 로그 변경 명령 전송
        """
        if not session_name:
            # 전체 전송
            with self.m_Lock:
                for socket in self.m_SocketConnectionList:
                    if hasattr(socket, 'send_cmd_log_status_change'):
                        socket.send_cmd_log_status_change(log_ctl)
            return True
        else:
            # 특정 세션 전송
            socket = self.find_session(session_name)
            if socket and hasattr(socket, 'send_cmd_log_status_change'):
                socket.send_cmd_log_status_change(log_ctl)
                return True
            return False

    def get_con_sock_infos(self, info_vector, is_writable_check, sec, micro_sec):
        """
        C++: void GetConSockInfos(...)
        현재 관리 중인 모든 소켓의 정보를 수집하여 벡터(리스트)에 담음
        """
        self.socket_remove_lock()

        # 1. 자기 자신(ConnectionMgr)의 정보 (만약 소켓 기능을 겸한다면)
        # info = FrSocketInfo()
        # self.get_socket_info(info)
        # info_vector.append(info)

        # 2. 관리 중인 자식 소켓들의 정보 수집
        for socket in self.m_SocketConnectionList:
            if hasattr(socket, 'get_socket_info'):
                info = socket.get_socket_info()
                
                if is_writable_check:
                    # FrSockFdManager.socket_check 사용 (상속받았으므로 self.socket_check 가능)
                    is_writable = self.socket_check(info, sec, micro_sec)
                    info.writerable_status = SOCK_INFO_WRITERABLE_STATUS_OK if is_writable else SOCK_INFO_WRITERABLE_STATUS_NOK
                
                info_vector.append(info)

        self.socket_remove_unlock()

    def get_connection_list(self):
        return self.m_SocketConnectionList