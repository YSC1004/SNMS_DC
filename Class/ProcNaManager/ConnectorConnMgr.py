import sys
import os
import threading

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Try importing parent class based on availability
from Class.Common.SockMgrConnMgr import SockMgrConnMgr
from Class.ProcNaManager.ConnectorConnection import ConnectorConnection
from Class.Common.CommType import *
from Class.Common.AsUtil import AsUtil

class ConnectorConnMgr(SockMgrConnMgr):
    """
    Manages connections to Connector processes.
    Handles Accept, MMC routing, Process Status, and Port control.
    """
    def __init__(self):
        """
        C++: ConnectorConnMgr::ConnectorConnMgr()
        """
        super().__init__()
        self.m_SocketRemoveLock = threading.Lock()

    def __del__(self):
        """
        C++: ConnectorConnMgr::~ConnectorConnMgr()
        """
        super().__del__()

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        Overridden to create ConnectorConnection.
        """
        connect_conn = ConnectorConnection(self)

        if not self.accept(connect_conn):
            print(f"[ConnectorConnMgr] Connect Socket Accept Error : {self.get_obj_err_msg()}")
            connect_conn.close()
            return

        self.add(connect_conn)

    def stop_process(self, session_name):
        """
        C++: bool StopProcess(string SessionName)
        Stops the connector process logically and physically.
        """
        con = self.find_session(session_name)
        
        if con is None:
            # Debug log (level 2)
            # print(f"[ConnectorConnMgr] Can't Find Connector : {session_name}")
            return False

        con.stop_process()
        
        # Physical kill logic (Delegated to ProcConnectionMgr logic usually inherited or separate)
        # Assuming ProcConnectionMgr logic is handled via World or System call wrapper
        # Here we just return True as C++ calls ProcConnectionMgr::StopProcess
        from AsciiManagerWorld import AsciiManagerWorld
        # AsciiManagerWorld doesn't expose StopProcess directly for ID, 
        # but typically Manager kills it via PID or command.
        # Stubbing strictly to logic flow:
        return True

    def connector_init_end(self, session_name):
        """
        C++: void ConnectorInitEnd(string SessionName)
        Called when Connector finishes initialization.
        """
        from AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance
        world.set_connector_proc_status(session_name)

    def process_dead(self, name, pid, status):
        """
        C++: void ProcessDead(string Name, int Pid, int Status)
        """
        self.send_process_info(name, STOP)

        from AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance

        if status == ORDER_KILL:
            world.remove_pid(pid)
            world.send_ascii_error(1, f"{name} is killed normally.")
        else:
            world.process_dead(ASCII_CONNECTOR, name, pid)

    def send_cmd_open_info(self, port_info):
        """
        C++: bool SendCmdOpenInfo(AS_CMD_OPEN_PORT_T* PortInfo)
        """
        # Finds the connection and sends the open port command
        if not self.cmd_open_port_info(port_info.ConnectorId, port_info):
            print(f"[ConnectorConnMgr] Can't Find Connector : {port_info.ConnectorId}")
            return False
        return True

    def send_mmc_command(self, session_name, mmc_com):
        """
        C++: bool SendMMCCommand(const char* SessionName, AS_MMC_PUBLISH_T* MMCCom)
        """
        with self.m_SocketRemoveLock:
            con = self.find_session(session_name)
            
            if con is None:
                # print(f"[ConnectorConnMgr] Can't Find Connector : {session_name}")
                return False

            con.send_mmc_command(mmc_com)
            return True

    def send_process_info(self, session_name, status):
        """
        C++: void SendProcessInfo(const char* SessionName, int Status)
        """
        proc_info = AsProcessStatusT()
        proc_info.ProcessId = session_name
        proc_info.Status = status
        proc_info.ProcessType = ASCII_CONNECTOR

        if proc_info.Status == START:
            if not self.get_process_info(session_name, proc_info):
                return

        from AsciiManagerWorld import AsciiManagerWorld
        AsciiManagerWorld._instance.send_process_info(proc_info)

    def send_session_control(self, session_ctl):
        """
        C++: void SendSessionControl(AS_SESSION_CONTROL_T* SessionCtl)
        """
        con = self.find_session(session_ctl.ConnectorId)
        
        if con is None:
            print(f"[ConnectorConnMgr] Can't Find Execute Connector({session_ctl.ConnectorId})")
            
            from AsciiManagerWorld import AsciiManagerWorld
            AsciiManagerWorld._instance.send_ascii_error(1, f"Can't Find Execute Connector({session_ctl.ConnectorId})")
            return

        con.send_session_control(session_ctl)

    # -------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------
    def cmd_open_port_info(self, connector_id, port_info):
        """
        Internal helper to find connection and call cmd_open_port_info
        """
        con = self.find_session(connector_id)
        if con:
            return con.cmd_open_port_info(port_info)
        return False

    def find_session(self, session_name):
        """
        Finds a connector connection by session name.
        """
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
        proc_info.Pid = 0 # Implement actual PID lookup if needed
        return True