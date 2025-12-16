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
from Class.ProcNaManager.RouterConnection import RouterConnection
from Class.Common.CommType import *
from Class.Common.AsUtil import AsUtil

class RouterConnMgr(SockMgrConnMgr):
    """
    Manages connections to Router processes.
    Handles Accept, Process Stopping, and Dead Process management.
    """
    def __init__(self):
        """
        C++: RouterConnMgr::RouterConnMgr()
        """
        super().__init__()

    def __del__(self):
        """
        C++: RouterConnMgr::~RouterConnMgr()
        """
        super().__del__()

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        Overridden to create RouterConnection.
        """
        router_conn = RouterConnection(self)

        if not self.accept(router_conn):
            print(f"[RouterConnMgr] Router Socket Accept Error : {self.get_obj_err_msg()}")
            router_conn.close()
            return

        self.add(router_conn)

    def stop_process(self, session_name):
        """
        C++: bool StopProcess(string SessionName)
        Stops the Router process logically and physically.
        """
        con = self.find_session(session_name)
        
        if con is None:
            # print(f"[RouterConnMgr] Can't Find Router : {session_name}")
            return False

        con.stop_process()
        
        # Physical kill logic (In C++: ProcConnectionMgr::StopProcess)
        # In Python, typically handled via World or ProcConnectionMgr instance.
        # Returning True to simulate C++ behavior.
        return True

    def process_dead(self, name, pid, status):
        """
        C++: void ProcessDead(string Name, int Pid, int Status)
        Handles the event when a Router process dies.
        """
        self.send_process_info(name, STOP)

        from AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance

        if status == ORDER_KILL:
            world.remove_pid(pid)
            msg = f"The process({name}) is killed normally."
            world.send_ascii_error(1, msg)
        else:
            world.process_dead(ASCII_ROUTER, name, pid)

    def send_process_info(self, session_name, status):
        """
        C++: void SendProcessInfo(const char* SessionName, int Status)
        Updates the global process information regarding Router status.
        """
        proc_info = AsProcessStatusT()
        proc_info.ProcessId = session_name
        proc_info.Status = status
        proc_info.ProcessType = ASCII_ROUTER

        if proc_info.Status == START:
            if not self.get_process_info(session_name, proc_info):
                return

        from AsciiManagerWorld import AsciiManagerWorld
        AsciiManagerWorld._instance.send_process_info(proc_info)

    # -------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------
    def find_session(self, session_name):
        for conn in self.m_SocketConnectionList:
            if conn.get_session_name() == session_name:
                return conn
        return None

    def get_process_info(self, session_name, proc_info):
        """
        Helper to fill PID/StartTime.
        """
        from datetime import datetime
        proc_info.StartTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        proc_info.Pid = 0 # Replace with actual PID lookup if needed
        return True