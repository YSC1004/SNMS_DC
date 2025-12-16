import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.ConnectionMgr import ConnectionMgr
from Class.Common.CommType import AsDbSyncKindT, AS_DB_SYNC_KIND, PacketT

# ServerConnection 클래스 Import (다음 단계에서 구현 예정)
try:
    from Class.ProcNaServer.ServerConnection import ServerConnection
except ImportError:
    ServerConnection = None

# -------------------------------------------------------
# ServerConnMgr Class
# Active-Standby 서버 간 연결 관리자
# -------------------------------------------------------
class ServerConnMgr(ConnectionMgr):
    def __init__(self):
        """
        C++: ServerConnMgr()
        """
        super().__init__()
        self.m_StandbySvrConn = None # ServerConnection 객체

    def __del__(self):
        """
        C++: ~ServerConnMgr()
        """
        super().__del__()

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        Standby 서버의 연결 요청 수락
        """
        if ServerConnection is None:
            print("[ServerConnMgr] Error: ServerConnection class not found")
            return

        # 1. ServerConnection 객체 생성
        svr_conn = ServerConnection(self)

        # 2. Accept 수행
        if not self.accept(svr_conn):
            print(f"[ServerConnMgr] Another Server Accept Error : {self.get_obj_err_msg()}")
            return

        # 3. 관리 리스트에 추가
        self.add(svr_conn)
        
        # Peer IP 로깅 (FrSocketSensor의 메서드 활용)
        # print(f"[ServerConnMgr] Connection Another Server({svr_conn.get_peer_ip()})")

    def set_standby_server(self, svr_conn):
        """
        C++: void SetStandByServer(ServerConnection* SvrConn)
        연결된 세션 중 Standby 서버로 식별된 세션을 저장
        """
        self.m_StandbySvrConn = svr_conn

    def send_db_sync_kind(self, kind):
        """
        C++: void SendDbSyncKind(int Kind)
        Standby 서버에게 DB 동기화 종류(SyncKind) 전송
        """
        if self.m_StandbySvrConn:
            try:
                # 1. 구조체 생성 및 패킹
                req = AsDbSyncKindT(kind)
                body_data = req.pack()

                # 2. 패킷 생성
                packet = PacketT(AS_DB_SYNC_KIND, len(body_data), body_data)

                # 3. 전송
                self.m_StandbySvrConn.packet_send(packet)
                print(f"[ServerConnMgr] Send to DbSyncReq : {kind}")

            except Exception as e:
                print(f"[ServerConnMgr] SendDbSyncKind Error: {e}")
        else:
            # Standby 서버가 연결되지 않은 경우
            pass

    def is_standby_server(self):
        """
        C++: bool IsStandByServer()
        현재 Standby 서버와 연결되어 있는지 확인
        """
        return self.m_StandbySvrConn is not None