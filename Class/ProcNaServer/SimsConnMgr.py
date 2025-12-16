import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 부모 클래스 임포트 (SockMgrConnMgr)
from Class.Common.SockMgrConnMgr import SockMgrConnMgr
from Class.ProcNaServer.ExternalConnection import ExternalConnection

class SimsConnMgr(SockMgrConnMgr):
    """
    Manages connections from SIMS.
    Acts as a listener but delegates connection management to ExternalConnMgr.
    """
    def __init__(self, ext_mgr):
        """
        C++: SimsConnMgr(ExternalConnMgr *extMgr)
        """
        super().__init__()
        self.m_ExtMgr = ext_mgr

    def __del__(self):
        """
        C++: ~SimsConnMgr()
        """
        super().__del__()

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        Overridden to create ExternalConnection and add it to ExternalConnMgr.
        """
        # 1. ExternalConnection 객체 생성 (관리는 ext_mgr이 하므로 인자로 전달)
        conn = ExternalConnection(self.m_ExtMgr)

        # 2. Accept 수행 (현재 SimsConnMgr의 리스닝 소켓 사용)
        if not self.accept(conn):
            print(f"[SimsConnMgr] Sims Connection Accept Error : {self.get_obj_err_msg()}")
            conn.close()
            return

        # 3. 연결 리스트 추가는 ExternalConnMgr에 위임
        # C++: m_ExtMgr->Add(conn);
        self.m_ExtMgr.add(conn)
        
        print(f"[SimsConnMgr] Connected with Sims({conn.get_peer_ip()})")