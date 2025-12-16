import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.AsSocket import AsSocket
from Class.Common.CommType import *
from Class.Event.FrSockFdManager import FrSockFdManager
from Class.Common.AsWorld import AsWorld

# -------------------------------------------------------
# Helper Structs for SockMgr
# -------------------------------------------------------
class AsSocketStatusReqT(BasePacket):
    FMT = "!III"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.IsWriterableCheck = 0
        self.CheckSec = 0
        self.CheckMiscroSec = 0

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        obj = cls()
        obj.IsWriterableCheck, obj.CheckSec, obj.CheckMiscroSec = t
        return obj

class AsSocketInfoListT(BasePacket):
    # int Size, int Status, char GroupName[40] (SOCK_INFO_LISTENER_NAME_MAX_LEN=40 가정)
    # List of FR_SOCKET_INFO_T[25]
    # 구조체 패킹 로직이 복잡하므로, 여기서는 직렬화 로직을 직접 구현해야 함
    pass

# -------------------------------------------------------
# SockMgrConnection Class
# 소켓 관리자 클라이언트(GUI) 연결 처리
# -------------------------------------------------------
class SockMgrConnection(AsSocket):
    def __init__(self, conn_mgr):
        """
        C++: SockMgrConnection(SockMgrConnMgr* ConnMgr)
        """
        super().__init__()
        self.m_SockMgrConnMgr = conn_mgr

    def __del__(self):
        """
        C++: ~SockMgrConnection()
        """
        super().__del__()

    # ---------------------------------------------------
    # Virtual Overrides
    # ---------------------------------------------------
    def receive_packet(self, packet, session_identify):
        """
        C++: void ReceivePacket(...)
        """
        self.gui_req_process(packet)

    def close_socket(self, err):
        """
        C++: void CloseSocket(int Errno)
        """
        print(f"[SockMgrConnection] Connection Broken ({self.m_PeerIp}, {self.get_session_name()})")
        if self.m_SockMgrConnMgr:
            # Manager에서 자신을 제거 (Remove는 Socket을 닫고 delete함)
            self.m_SockMgrConnMgr.remove(self)

    # ---------------------------------------------------
    # Request Processing
    # ---------------------------------------------------
    def gui_req_process(self, packet):
        print(f"[SockMgrConnection] Recv Request SockMgr GUI : {packet.msg_id}")

        if packet.msg_id in [AS_SOCKET_STATUS_REQ, FR_SOCKET_STATUS_REQ]:
            req = AsSocketStatusReqT.unpack(packet.msg_body)
            if req:
                self.recv_socket_status_req(packet.msg_id, req)

        elif packet.msg_id == FR_SOCKET_SHUTDOWN_REQ:
            # 구조체 파싱 필요 (FR_SOCKET_INFO_T)
            # 여기서는 생략 (구현 필요 시 FrSockFdManager 참조)
            # if FrSockFdManager.shut_down_sock(info): ...
            pass

        elif packet.msg_id == FR_SOCKET_CHECK_REQ:
            # 구조체 파싱 및 체크
            pass

        else:
            print(f"[SockMgrConnection] Unknown Request : {packet.msg_id}")

    def recv_socket_status_req(self, req_type, status_req):
        info_vector = [] # List of FrSocketInfo

        if req_type == AS_SOCKET_STATUS_REQ:
            # AsWorld의 ConnectionMgrVector를 순회하며 정보 수집
            with AsWorld.m_ConnectionMgrVectorLock:
                for mgr in AsWorld.m_ConnectionMgrVector:
                    mgr.get_con_sock_infos(info_vector, 
                                           bool(status_req.IsWriterableCheck), 
                                           status_req.CheckSec, 
                                           status_req.CheckMiscroSec)
            
            self.send_socket_status_info(AS_SOCKET_STATUS_RES, info_vector)

        elif req_type == FR_SOCKET_STATUS_REQ:
            # FrSockFdManager를 통해 전체 소켓 정보 수집
            mgr = FrSockFdManager()
            info_vector = mgr.get_sock_infos(bool(status_req.IsWriterableCheck),
                                             status_req.CheckSec, 
                                             status_req.CheckMiscroSec)
            
            self.send_socket_status_info(FR_SOCKET_STATUS_RES, info_vector)

    def send_socket_status_info(self, res_type, info_vector, group_name=""):
        # 1. 시작 알림
        # AS_GUI_INIT_INFO_T (int Count)
        init_info_pack = struct.pack("!I", len(info_vector))
        self.packet_send(PacketT(INIT_INFO_START, len(init_info_pack), init_info_pack))

        # 2. 데이터 분할 전송 (Pagination)
        # Python에서는 복잡한 memcpy 대신 JSON이나 Pickle을 쓰면 좋지만,
        # C++ 호환을 위해 바이트 패킹을 해야 한다면 반복문으로 처리해야 함.
        
        # (여기서는 로직 흐름만 구현하고, 실제 바이너리 패킹은 생략하거나 간소화함)
        # INFO_NO_SEG, INFO_START, INFO_ING, INFO_END 등 플래그 처리 필요
        
        # 예시: 간단히 전송했다고 가정
        print(f"[SockMgrConnection] Sending {len(info_vector)} socket infos...")

        # 3. 종료 알림
        self.packet_send(PacketT(INIT_INFO_END, len(init_info_pack), init_info_pack))
        return True