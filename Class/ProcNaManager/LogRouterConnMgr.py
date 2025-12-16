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
from Class.ProcNaManager.LogRouterConnection import LogRouterConnection
from Class.Common.CommType import *
from Class.Common.AsUtil import AsUtil

class LogRouterConnMgr(SockMgrConnMgr):
    """
    Manages connections to LogRouter processes.
    Handles Accept, Process Stop, and Dead Process handling.
    """
    def __init__(self):
        """
        C++: LogRouterConnMgr::LogRouterConnMgr()
        """
        super().__init__()

    def __del__(self):
        """
        C++: LogRouterConnMgr::~LogRouterConnMgr()
        """
        super().__del__()

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        Overridden to create LogRouterConnection.
        """
        conn = LogRouterConnection(self)

        if not self.accept(conn):
            print(f"[LogRouterConnMgr] Log Router Socket Accept Error : {self.get_obj_err_msg()}")
            conn.close()
            return

        self.add(conn)

    def stop_process(self, session_name):
        """
        C++: bool StopProcess(string SessionName)
        """
        con = self.find_session(session_name)
        
        if con is None:
            print(f"[LogRouterConnMgr] Can't Find Log Router : {session_name}")
            return False

        con.stop_process()
        return True

    def process_dead(self, name, pid, status):
        """
        C++: void ProcessDead(string Name, int Pid, int Status)
        """
        self.send_process_info(name, STOP)

        from Server.AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance

        if status == ORDER_KILL:
            world.remove_pid(pid)
            msg = f"The process({name}) is killed normally."
            world.send_ascii_error(1, msg)
        else:
            world.process_dead(ASCII_LOG_ROUTER, name, pid)

    def send_process_info(self, session_name, status):
        """
        C++: void SendProcessInfo(const char* SessionName, int Status)
        """
        proc_info = AsProcessStatusT()
        proc_info.ProcessId = session_name
        proc_info.Status = status
        proc_info.ProcessType = ASCII_LOG_ROUTER

        if proc_info.Status == START:
            if not self.get_process_info(session_name, proc_info):
                return

        from Server.AsciiManagerWorld import AsciiManagerWorld
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
        proc_info.Pid = 0 
        return True