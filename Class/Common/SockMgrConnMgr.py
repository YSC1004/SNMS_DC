import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrSocketSensor import FrSocketSensor
from Class.Common.ConnectionMgr import ConnectionMgr

# SockMgrConnection은 이 클래스에 의해 생성되는 자식 연결 객체입니다.
# 아직 코드가 제공되지 않았으므로, 파일이 있을 경우 import 하도록 처리합니다.
try:
    from Class.Common.SockMgrConnection import SockMgrConnection
except ImportError:
    SockMgrConnection = None

# -------------------------------------------------------
# SockMgrConnMgr Class
# 소켓 관리자용 서버 리스너 (Accept 담당 + 연결 관리)
# -------------------------------------------------------
class SockMgrConnMgr(FrSocketSensor, ConnectionMgr):
    def __init__(self):
        """
        C++: SockMgrConnMgr()
        """
        # 다중 상속 초기화
        # 1. FrSocketSensor: 소켓 기능 초기화
        FrSocketSensor.__init__(self)
        
        # 2. ConnectionMgr: 리스트 관리 기능 초기화
        ConnectionMgr.__init__(self)

    def __del__(self):
        """
        C++: ~SockMgrConnMgr()
        """
        FrSocketSensor.__del__(self)
        ConnectionMgr.__del__(self)

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        FrSocketSensor의 가상 함수 오버라이딩.
        클라이언트 연결 요청이 오면 호출됨.
        """
        if SockMgrConnection is None:
            print("[SockMgrConnMgr] Error: SockMgrConnection class not found")
            return

        # 1. 새로운 연결 객체 생성 (this 포인터 전달)
        mgr_conn = SockMgrConnection(self)
        
        # 2. Accept 수행 (FrSocketSensor.accept)
        if not self.accept(mgr_conn):
            print(f"[SockMgrConnMgr] Mgr Socket Accept Error : {self.get_obj_err_msg()}")
            # Python은 GC가 처리하므로 delete 불필요
            return

        # 3. 관리 리스트에 추가 (ConnectionMgr.add)
        self.add(mgr_conn)
        
        # 4. 로그 출력 (FrSocketSensor.get_peer_ip 사용)
        # peer_ip = mgr_conn.get_peer_ip() if hasattr(mgr_conn, 'get_peer_ip') else 'Unknown'
        # print(f"[SockMgrConnMgr] Connection Mgr Sock({peer_ip})")