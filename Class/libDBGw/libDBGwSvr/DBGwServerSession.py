import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import DBGwServer logic
# Note: The C++ code instantiates 'new DBGwServer'.
# In Python, we assume DBGwServer logic is imported here.

from Class.libDBGw.libDBGwSvr.DBGwServer import DBGwServer

# Assuming AsSocket base class exists
try:
    from Class.Common.AsSocket import AsSocket
except ImportError:
    class AsSocket:
        """Mock Base Class"""
        def close(self): pass
        def set_socket(self, sock, addr): pass

class DBGwServerSession(AsSocket):
    """
    C++: DBGwServerSession
    Represents a client session. Delegates packet processing to an internal DBGwServer instance.
    """
    def __init__(self, db_kind, default_db_user, default_db_passwd, default_db_name):
        """
        C++: DBGwServerSession(int DbKind, ...)
        """
        super().__init__()
        
        # In C++: m_DBGwSvr = new DBGwServer(this, ...);
        # We pass 'self' as the session pointer/reference
        self.m_DBGwSvr = DBGwServer(self, db_kind, default_db_user, default_db_passwd, default_db_name)
        
        self.m_IsAloneMode = False
        self.m_IsLoggingMode = False
        self.m_LogDir = "."

    def __del__(self):
        """
        C++: ~DBGwServerSession()
        """
        # Python GC automatically handles memory, 
        # but we can explicitly clean up the server instance if needed.
        self.m_DBGwSvr = None

    def set_socket(self, sock, addr):
        """
        Helper to set the socket from ServerMgr (mimics C++ Accept behavior)
        """
        self.client_socket = sock
        self.client_addr = addr
        # If DBGwServer needs the socket info, pass it here
        # self.m_DBGwSvr.set_socket(sock)

    def receive_packet(self, packet, session_identify):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        Delegates the packet to the server logic.
        """
        if self.m_DBGwSvr:
            self.m_DBGwSvr.receive_packet(packet)

    def close_socket(self, errno):
        """
        C++: void CloseSocket(int Errno)
        Handles session closure.
        """
        # Call base class Close()
        self.close() 
        
        # m_DBGwSvr->CloseSession(nErrorCode); (Commented out in C++)
        
        print("Closed Session", flush=True)

        if self.m_IsAloneMode:
            log_file = ""
            if self.m_DBGwSvr:
                log_file = self.m_DBGwSvr.get_log_file()
                
            pid = os.getpid()
            print(f"LOG FILE : [{log_file}], PID[{pid}]", flush=True)

            if log_file:
                try:
                    if os.path.exists(log_file):
                        os.remove(log_file) # remove and unlink are equivalent in Python
                except OSError as e:
                    print(f"Error removing log file: {e}")

            sys.exit(1)
        
        # C++: delete this;
        # In Python, "delete this" is not possible/valid.
        # The object will be garbage collected when no references remain.
        # It is the caller's responsibility (e.g., ServerMgr) to remove this session from its list.
        pass