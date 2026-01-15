import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import Parent Class
# DBClientSocket usually inherits from DBGwBaseSocket (for byte swapping) 
# or AsSocket (base socket). Based on Makefile dependency, likely DBGwBaseSocket.
try:
    from libDBGw.libDBGwBase.DBGwBaseSocket import DBGwBaseSocket
except ImportError:
    # Fallback for compilation/linting if dependencies aren't perfect
    class DBGwBaseSocket:
        def disable(self): pass
        def close(self): pass

class DBClientSocket(DBGwBaseSocket):
    """
    C++: DBClientSocket
    Handles client-side socket operations.
    Acts as a wrapper that delegates actual processing to DBGwUser.
    """
    def __init__(self, gw_user):
        """
        C++: DBClientSocket(DBGwUser* GwUser)
        """
        super().__init__()
        
        # Pointer to the User/Session logic that owns this socket
        self.m_DbGwUser = gw_user
        
        # Start in disabled state (as per C++ source)
        self.disable()

    def __del__(self):
        """
        C++: ~DBClientSocket()
        """
        self.m_DbGwUser = None

    def receive_packet(self, packet, session_identify=0):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        Delegates packet processing to the DBGwUser instance.
        """
        if self.m_DbGwUser:
            self.m_DbGwUser.receive_packet(packet)

    def close_socket(self, n_error_code):
        """
        C++: void CloseSocket(int nErrorCode)
        Handles socket closure and notifies the user.
        """
        # Close the physical socket (Parent method)
        self.close()
        
        # Notify the user logic that the session is closed
        if self.m_DbGwUser:
            self.m_DbGwUser.close_session(n_error_code)