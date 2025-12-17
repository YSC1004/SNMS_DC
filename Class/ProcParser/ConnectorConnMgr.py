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
from Class.ProcParser.ConnectorConnection import ConnectorConnection

class ConnectorConnMgr(SockMgrConnMgr):
    """
    Manages connections from Connector processes to the Parser.
    Handles socket acceptance.
    """
    def __init__(self):
        """
        C++: ConnectorConnMgr::ConnectorConnMgr()
        """
        super().__init__()

    def __del__(self):
        """
        C++: ConnectorConnMgr::~ConnectorConnMgr()
        """
        super().__del__()

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        Creates a new ConnectorConnection and accepts the incoming socket.
        """
        # 1. Create Connection Object
        connect_conn = ConnectorConnection(self)

        # 2. Perform Accept
        if not self.accept(connect_conn):
            print(f"[ConnectorConnMgr] Connect Socket Accept Error : {self.get_obj_err_msg()}")
            connect_conn.close()
            return

        # 3. Success Log & Add to List
        print("[ConnectorConnMgr] Connector Connected")
        self.add(connect_conn)