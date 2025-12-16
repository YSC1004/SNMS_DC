import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 부모 클래스 임포트
from Class.Common.SockMgrConnMgr import SockMgrConnMgr
from Class.ProcNaServer.RouterInfoConnection import RouterInfoConnection

class RouterInfoConnMgr(SockMgrConnMgr):
    """
    Manages connections for Router Information requests.
    Inherits from SockMgrConnMgr to handle socket acceptance and list management.
    """
    def __init__(self):
        """
        C++: RouterInfoConnMgr::RouterInfoConnMgr()
        """
        super().__init__()

    def __del__(self):
        """
        C++: RouterInfoConnMgr::~RouterInfoConnMgr()
        """
        super().__del__()

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        Overridden to create RouterInfoConnection instances.
        """
        # 1. 연결 객체 생성
        conn = RouterInfoConnection(self)

        # 2. Accept 수행 (부모 클래스 메서드 사용)
        if not self.accept(conn):
            print(f"[RouterInfoConnMgr] Router Info Socket Accept Error : {self.get_obj_err_msg()}")
            conn.close()
            return

        # 3. 리스트에 추가
        self.add(conn)
        
        # 4. 로그 출력
        print(f"[RouterInfoConnMgr] Router Connection Gui({conn.get_peer_ip()})")