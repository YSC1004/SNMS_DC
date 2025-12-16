import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 부모 클래스 임포트
from Class.Common.SockMgrConnMgr import SockMgrConnMgr
from Class.ProcNaServer.NetFinderConnection import NetFinderConnection
from Class.Common.CommType import *

class NetFinderConnMgr(SockMgrConnMgr):
    """
    Manages the connection with the NetFinder process.
    Handles socket acceptance and process status updates.
    """
    def __init__(self):
        """
        C++: NetFinderConnMgr::NetFinderConnMgr()
        """
        super().__init__()
        self.m_NetFinderConnection = None

    def __del__(self):
        """
        C++: NetFinderConnMgr::~NetFinderConnMgr()
        """
        super().__del__()

    def process_dead(self, name, pid, status):
        """
        C++: void ProcessDead(string Name, int Pid, int Status)
        Handles the event when the NetFinder process terminates.
        """
        self.send_process_info(name, STOP)
        
        if status == ORDER_KILL:
            pass
        else:
            self.m_NetFinderConnection = None
            from Server.AsciiServerWorld import AsciiServerWorld
            AsciiServerWorld._instance.process_dead(name, pid)

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        Overridden to create NetFinderConnection instances.
        """
        con = NetFinderConnection(self)

        if not self.accept(con):
            print(f"[NetFinderConnMgr] NetFinderConnMgr Socket Accept Error : {self.get_obj_err_msg()}")
            con.close()
            return

        print("[NetFinderConnMgr] Connection success Netfinder")
        self.add(con)

    def set_net_finder_conn(self, con):
        """
        C++: void SetNetFinderConn(NetFinderConnection* Con)
        """
        self.m_NetFinderConnection = con

    def send_process_info(self, session_name, status):
        """
        C++: void SendProcessInfo(const char* SessionName, int Status)
        Updates the global process information (World) regarding NetFinder status.
        """
        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        
        proc_info = AsProcessStatusT()
        proc_info.ProcessId = session_name
        proc_info.Status = status

        if proc_info.Status == START:
            if not self.get_process_info(session_name, proc_info):
                return

        proc_info.ManagerId = world.get_proc_name()
        proc_info.ProcessType = NETFINDER
        
        world.update_process_info(proc_info)

    def get_process_info(self, session_name, proc_info):
        """
        Helper method to fill process info (PID, StartTime).
        (Matches logic from other Managers)
        """
        from datetime import datetime
        # C++ GetProcessInfo typically fills StartTime and PID
        proc_info.StartTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        proc_info.Pid = 0 # Replace with actual PID lookup if available/needed
        return True