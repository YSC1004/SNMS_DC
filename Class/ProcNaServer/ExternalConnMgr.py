import sys
import os
import threading

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 부모 클래스 임포트 (경로에 맞게 수정)
from Class.Common.SockMgrConnMgr import SockMgrConnMgr
from Class.ProcNaServer.ExternalConnection import ExternalConnection

class ExternalConnMgr(SockMgrConnMgr):
    """
    Manages connections from External Systems.
    Handles Accept, MMC Result forwarding, and session counting.
    """
    def __init__(self):
        """
        C++: ExternalConnMgr::ExternalConnMgr()
        """
        super().__init__()
        # 리스트 접근 보호를 위한 뮤텍스
        self.m_SocketRemoveLock = threading.Lock()

    def __del__(self):
        """
        C++: ExternalConnMgr::~ExternalConnMgr()
        """
        super().__del__()

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        """
        # 1. ExternalConnection 객체 생성
        ext_conn = ExternalConnection(self)

        # 2. Accept 수행 (부모 클래스 메서드 활용)
        if not self.accept(ext_conn):
            print(f"[ExternalConnMgr] Ext Socket Accept Error : {self.get_obj_err_msg()}")
            ext_conn.close()
            return

        # 3. 관리 리스트에 추가
        # C++ 코드에서는 Lock을 Add 내부나 별도로 처리할 수 있으나, 
        # 여기서는 Add 호출 (SockMgrConnMgr 구현에 따름)
        self.add(ext_conn)

        # C++: extConn->SetWriterableCheck(true);
        # Python AsSocket 구현에 따라 필요 시 호출. (여기서는 생략 또는 스텁)
        # ext_conn.set_writable_check(True) 

        print(f"[ExternalConnMgr] External System Connection({ext_conn.get_peer_ip()})")

    def send_ext_mmc_req_result(self, ext_con, res):
        """
        C++: void SendExtMMCReqResult(MMCRequestConnection* ExtCon, AS_MMC_RESULT_T* Res)
        ExternalConnection(또는 부모인 MMCRequestConnection)에게 결과 전송
        """
        with self.m_SocketRemoveLock:
            # 연결 유효성 확인 (SockMgrConnMgr의 메서드)
            if self.is_valid_connection(ext_con):
                # 로그 출력 (필요 시 주석 해제)
                # print(f"[ExternalConnMgr] Send MMC Result to [{ext_con.get_session_name()}][{ext_con.get_peer_ip()}]")
                
                # 결과 전송
                ext_con.send_mmc_result(res)
            else:
                print("[ExternalConnMgr] Send MMC Result Error : Disconnected Session Or Invalid Session...")

    def get_cur_session_cnt(self, session_id):
        """
        C++: int GetCurSessionCnt(string SessionID)
        특정 SessionID를 가진 연결의 개수를 반환
        """
        cnt = 0
        with self.m_SocketRemoveLock:
            # m_SocketConnectionList는 부모 클래스(SockMgrConnMgr/ConnectionMgr) 멤버
            for conn in self.m_SocketConnectionList:
                if session_id == conn.get_session_name():
                    cnt += 1
        return cnt

    def socket_remove_lock(self):
        """
        C++: void SocketRemoveLock()
        """
        self.m_SocketRemoveLock.acquire()

    def socket_remove_unlock(self):
        """
        C++: void SocketRemoveUnLock()
        """
        self.m_SocketRemoveLock.release()