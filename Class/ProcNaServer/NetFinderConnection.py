import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.AsSocket import AsSocket
from Class.Common.CommType import *
from Class.Common.AsUtil import AsUtil

class NetFinderConnection(AsSocket):
    """
    Handles connection with NetFinder process.
    Manages session identification and lifecycle.
    """
    def __init__(self, conn_mgr):
        """
        C++: NetFinderConnection(NetFinderConnMgr* ConMgr)
        """
        super().__init__()
        self.m_NetFinderConnMgr = conn_mgr

    def __del__(self):
        """
        C++: ~NetFinderConnection()
        """
        super().__del__()

    def receive_packet(self, packet, session_identify):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        # NETFINDER 상수가 CommType에 정의되어 있어야 함
        if session_identify == NETFINDER:
            self.net_finder_req(packet)
        else:
            print(f"[NetFinderConnection] UnKnown Session : {session_identify}")

    def session_identify(self, session_type, session_name):
        """
        C++: void SessionIdentify(int SessionType, string SessionName)
        """
        print(f"[NetFinderConnection] Session Identify : Type({AsUtil.get_process_type_string(session_type)}), SessionName({session_name})")

        if not self.m_NetFinderConnMgr.add_session_name(session_name):
            self.close()
            self.m_NetFinderConnMgr.remove(self)
            return

        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        
        # Start Alive Check
        self.start_alive_check(world.get_proc_alive_check_time(), world.get_alive_check_limit_cnt())
        
        # Notify Manager
        self.m_NetFinderConnMgr.send_process_info(session_name, START)
        self.m_NetFinderConnMgr.set_net_finder_conn(self)

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        """
        print(f"[NetFinderConnection] Socket Broken : {self.get_session_name()}")
        self.m_NetFinderConnMgr.child_process_dead(self)

    def net_finder_req(self, packet):
        """
        C++: void NetFinderReq(PACKET_T* Packet)
        """
        msg_id = packet.msg_id
        
        if msg_id == AS_LOG_INFO:
            # Currently does nothing in C++ code provided
            pass
        else:
            print(f"[NetFinderConnection] [CORE_ERROR] Unknown Msg Id : {msg_id}")