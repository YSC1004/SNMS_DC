import sys
import os
import struct

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.AsSocket import AsSocket
from Class.Common.CommType import *

class RouterInfoConnection(AsSocket):
    """
    Handles Router Information Requests.
    Receives request, queries World for info, and sends back the list.
    """
    def __init__(self, conn_mgr):
        """
        C++: RouterInfoConnection(RouterInfoConnMgr* ConnMgr)
        """
        super().__init__()
        self.m_RouterInfoConnMgr = conn_mgr
        self.m_RouterInfoList = [] # List of AsRouterInfoT

    def __del__(self):
        """
        C++: ~RouterInfoConnection()
        """
        super().__del__()

    def receive_packet(self, packet, session_identify=0):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        msg_id = packet.msg_id
        
        if msg_id == AS_ROUTER_INFO_REQ:
            req = AsRouterInfoReqT.unpack(packet.msg_body)
            if req:
                self.router_info_req_process(req)
        else:
            print(f"[RouterInfoConnection] Unknown Msg Id : {msg_id}")

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        """
        print(f"[RouterInfoConnection] Router Connection Broken({self.get_peer_ip()})")
        if self.m_RouterInfoConnMgr:
            self.m_RouterInfoConnMgr.remove(self)

    def router_info_req_process(self, req):
        """
        C++: void RouterInfoReqProcess(AS_ROUTER_INFO_REQ_T* Req)
        """
        print(f"[RouterInfoConnection] Receive Router Info Request : userid({req.userid}), passwd({req.password})")

        if req.equipNo > 50:
            print(f"[RouterInfoConnection] [CORE_ERROR] Invalid Router Info Req(equipNo over 50) {self.get_peer_ip()}")
            return

        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        
        # 1. Get Router Info List from World
        self.m_RouterInfoList.clear()
        
        # C++: world->GetRouterInfo(Req, &m_RouterInfoList)
        # Assuming get_router_info populates the list or returns it
        if hasattr(world, 'get_router_info'):
            world.get_router_info(req, self.m_RouterInfoList)
        
        print(f"[RouterInfoConnection] RouterInfo size {len(self.m_RouterInfoList)}")

        # 2. Prepare Response
        res = AsRouterInfoResT()
        res.routerNo = len(self.m_RouterInfoList)
        
        # C++ logic caps at whatever static array size or dynamic
        # Python list assignment
        res.routerInfos = self.m_RouterInfoList[:res.routerNo]
        
        # Clear local list after use
        self.m_RouterInfoList.clear()

        # 3. Send Response
        body = res.pack()
        self.packet_send(PacketT(AS_ROUTER_INFO_RES, len(body), body))