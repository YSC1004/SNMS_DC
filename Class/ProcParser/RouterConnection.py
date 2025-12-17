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

class RouterConnection(AsSocket):
    """
    Handles connection to the Router process from Parser.
    Currently acts as a placeholder or basic connection maintainer.
    """
    def __init__(self, conn_mgr):
        """
        C++: RouterConnection()
        """
        super().__init__()
        self.m_RouterConnMgr = conn_mgr

    def __del__(self):
        """
        C++: ~RouterConnection()
        """
        super().__del__()

    def receive_packet(self, packet, session_identify=0):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        print(f"[RouterConnection] Receive Message Msg Id: {packet.msg_id}")

        # Currently no specific message handling logic in C++ source
        if packet.msg_id == -1: # Placeholder
            pass
        else:
            pass

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        """
        err_msg = os.strerror(errno_val) if errno_val else "Unknown"
        print(f"[RouterConnection] [CORE_ERROR] Router Connection Broken : {errno_val}, {err_msg}")