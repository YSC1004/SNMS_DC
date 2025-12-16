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
from Class.ProcNaManager.DataRouterConnection import DataRouterConnection
from Class.Common.CommType import *
from Class.Common.AsUtil import AsUtil

class DataRouterConnMgr(SockMgrConnMgr):
    """
    Manages connections to DataRouter processes.
    Handles Accept, Process Dead/Stop, and Routing Init Info distribution.
    """
    def __init__(self):
        """
        C++: DataRouterConnMgr::DataRouterConnMgr()
        """
        super().__init__()

    def __del__(self):
        """
        C++: DataRouterConnMgr::~DataRouterConnMgr()
        """
        super().__del__()

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        Overridden to create DataRouterConnection.
        """
        conn = DataRouterConnection(self)

        if not self.accept(conn):
            print(f"[DataRouterConnMgr] Data Router Socket Accept Error : {self.get_obj_err_msg()}")
            conn.close()
            return

        self.add(conn)

    def process_dead(self, name, pid, status):
        """
        C++: void ProcessDead(string Name, int Pid, int Status)
        """
        self.send_process_info(name, STOP)

        from AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance

        if status == ORDER_KILL:
            world.remove_pid(pid)
            msg = f"The DataRouter({name}) is killed normally."
            world.send_ascii_error(1, msg)
        else:
            world.process_dead(ASCII_DATA_ROUTER, name, pid)

    def stop_process(self, data_handler_id):
        """
        C++: bool StopProcess(string DataHandlerId)
        """
        con = self.find_session(data_handler_id)
        
        if con is None:
            print(f"[DataRouterConnMgr] Can't Find Data Router : {data_handler_id}")
            return False

        con.stop_process()
        print(f"[DataRouterConnMgr] Data Router({data_handler_id}) Stop")
        
        # Physical process kill logic (usually handled by World/ProcConnectionMgr)
        return True

    def send_process_info(self, session_name, status):
        """
        C++: void SendProcessInfo(const char* SessionName, int Status)
        """
        proc_info = AsProcessStatusT()
        
        # C++: sprintf(procInfo.ProcessId, "%s_%s", AsUtil::GetProcessTypeString(ASCII_DATA_ROUTER), SessionName);
        type_str = AsUtil.get_process_type_string(ASCII_DATA_ROUTER)
        proc_info.ProcessId = f"{type_str}_{session_name}"
        
        proc_info.Status = status
        proc_info.ProcessType = ASCII_DATA_ROUTER

        if proc_info.Status == START:
            if not self.get_process_info(session_name, proc_info):
                return

        from AsciiManagerWorld import AsciiManagerWorld
        AsciiManagerWorld._instance.send_process_info(proc_info)

    def recv_init_info(self, init_info):
        """
        C++: void RecvInitInfo(AS_DATA_ROUTING_INIT_T* InitInfo)
        Forwards initialization info to the specific DataRouter connection.
        """
        con = self.find_session(init_info.DataHandlerId)
        
        if con is None:
            print(f"[DataRouterConnMgr] Can't Find Data Router : {init_info.DataHandlerId}")
            return

        body = init_info.pack()
        con.packet_send(PacketT(AS_DATA_ROUTING_INIT, len(body), body))

    # -------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------
    def find_session(self, session_name):
        for conn in self.m_SocketConnectionList:
            if conn.get_session_name() == session_name:
                return conn
        return None

    def get_process_info(self, session_name, proc_info):
        from datetime import datetime
        proc_info.StartTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        proc_info.Pid = 0 
        return True