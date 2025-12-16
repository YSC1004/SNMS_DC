import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Try importing parent class based on availability
from Class.Common.SockMgrConnMgr import SockMgrConnMgr
from Class.ProcLogRouter.LogGuiConnection import LogGuiConnection

class LogGuiConnMgr(SockMgrConnMgr):
    """
    Manages connections from LogGui clients.
    Handles socket acceptance and maintains the list of active GUI connections.
    """
    def __init__(self):
        """
        C++: LogGuiConnMgr::LogGuiConnMgr()
        """
        super().__init__()

    def __del__(self):
        """
        C++: LogGuiConnMgr::~LogGuiConnMgr()
        """
        super().__del__()

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        Overridden to create LogGuiConnection instances.
        """
        # 1. Create Connection Object
        gui_conn = LogGuiConnection(self)

        # 2. Perform Accept
        if not self.accept(gui_conn):
            print(f"[LogGuiConnMgr] Log Gui Socket Accept Error : {self.get_obj_err_msg()}")
            gui_conn.close()
            return

        # 3. Add to Management List
        self.add(gui_conn)
        
        # 4. Logging
        print(f"[LogGuiConnMgr] Connection Log Gui({gui_conn.get_peer_ip()})")
        
        # m_SocketConnectionList is inherited from SockMgrConnMgr/ConnectionMgr
        print(f"[LogGuiConnMgr] Connection Log Total Cnt({len(self.m_SocketConnectionList)})")