import sys
import os
import time
import copy
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
from Class.ProcNaServer.DataHandlerConnection import DataHandlerConnection
from Class.Common.CommType import *
from Class.Common.AsUtil import AsUtil
from Class.Util.FrSshUtil import FrSshUtil 

class DataHandlerConnMgr(SockMgrConnMgr):
    """
    Manages connections and lifecycle of DataHandler processes.
    Inherits from SockMgrConnMgr for socket management.
    """
    
    # Constants
    WAIT_DATA_HANDLER_START_TIME = 10 # Adjust as needed
    WAIT_DATA_HANDLER_START_TIMEOUT = 1002

    def __init__(self):
        """
        C++: DataHandlerConnMgr::DataHandlerConnMgr()
        """
        super().__init__()
        
        # Key: DataHandlerId (str), Value: AsDataHandlerInfoT
        self.m_DataHandlerInfoMap = {}
        
        # Key: DataHandlerId (str), Value: AsLogStatusT
        self.m_LogStatusMap = {}
        
        # Key: DataHandlerId (str), Value: TimerKey (Dummy in Python usually, or Timer Object)
        self.m_DataHandlerExecuteTimerMap = {}

        # Ssh Utility
        self.m_SshUtil = FrSshUtil()

    def __del__(self):
        """
        C++: DataHandlerConnMgr::~DataHandlerConnMgr()
        """
        self.m_LogStatusMap.clear()
        self.m_DataHandlerInfoMap.clear()
        super().__del__()

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        Overridden to create DataHandlerConnection
        """
        dh_conn = DataHandlerConnection(self)

        if not self.accept(dh_conn):
            print(f"[DataHandlerConnMgr] Data Handler Socket Accept Error : {self.get_obj_err_msg()}")
            dh_conn.close()
            return

        self.add(dh_conn)
        print("[DataHandlerConnMgr] DataHandler Connection")

    def init(self):
        """
        C++: bool Init()
        Loads DataHandler info from DB.
        """
        self.m_DataHandlerInfoMap.clear()
        
        from Server.AsciiServerWorld import AsciiServerWorld
        db_mgr = AsciiServerWorld._instance.m_DbManager
        
        if db_mgr:
            if not db_mgr.get_data_handler_info(self.m_DataHandlerInfoMap):
                print(f"[DataHandlerConnMgr] [CORE_ERROR] Get DataHandler Info Error : {db_mgr.get_error_msg()}")
                return False
        return True

    def execute_manager(self):
        """
        C++: void ExecuteDataHandler() (Renamed to fit Python naming convention/polymorphism)
        """
        if not self.init():
            return

        wait_time = 50

        # Iterate over copy to allow modification if needed, though usually safe here
        for info in self.m_DataHandlerInfoMap.values():
            print(f"[DataHandlerConnMgr] DataHandlerId : {info.DataHandlerId}")

            if info.SettingStatus == START:
                self.execute_data_handler(info, self.WAIT_DATA_HANDLER_START_TIME + wait_time)
                wait_time += 2

    def execute_data_handler(self, info, wait_time=0):
        """
        C++: bool ExecuteDataHandler(AS_DATA_HANDLER_INFO_T* Info, int WaitTime)
        """
        if info.RequestStatus == WAIT_NO:
            # 1. Kill existing process
            self.kill_data_handler(info.DataHandlerId)

            # 2. Prepare Log Cycle Argument
            log_cycle_buf = ""
            if info.LogCycle == 1:
                # Constants ARG_LOG_CYCLE, ARG_LOG_HOUR assumed to be defined in CommType/AsUtil
                log_cycle_buf = f"{ARG_LOG_CYCLE} {ARG_LOG_HOUR}"

            # 3. Fetch Info from DB if needed
            from Server.AsciiServerWorld import AsciiServerWorld
            world = AsciiServerWorld._instance
            
            if not info.SshID: # Empty string check
                if world.m_DbManager and not world.m_DbManager.get_data_handler_info_find_id(info):
                     print(f"[DataHandlerConnMgr] [CORE_ERROR] Get DataHandler Info Error : {world.m_DbManager.get_error_msg()}")
                     return False
                
                if not info.SshID or not info.SshPass:
                     print(f"[DataHandlerConnMgr] [CORE_ERROR] Can't Find SSHID, SshPass: {info.DataHandlerId}")
                     return False

            # 4. Construct Command
            # Format: ~SshID/StartDir/Bin/ProcessName -name Id -svrip Ip -svrport Port ...
            start_dir = AsUtil.get_start_dir()
            proc_name = world.get_process_name(ASCII_DATA_HANDLER)
            server_ip = world.get_server_ip()
            listen_port = world.get_listen_port(ASCII_DATA_HANDLER)
            
            cmd_exec = (
                f"~{info.SshID}{start_dir}/Bin/{proc_name} "
                f"{ARG_NAME} {info.DataHandlerId} "
                f"{ARG_SVR_IP} {server_ip} "
                f"{ARG_SVR_PORT} {listen_port} {log_cycle_buf} &"
            )

            print(f"[DataHandlerConnMgr] Data Handler Execute: {cmd_exec}")
            
            # 5. Execute via SSH
            time.sleep(5) # As per C++ code
            
            if info.SshID and info.SshPass:
                self.run_command(info.SshID, info.SshPass, info.IpAddress, cmd_exec)
            
            info.RequestStatus = WAIT_START

            # 6. Set Timer
            # Python timer implementation needs to be adapted. 
            # Storing timer reference in map.
            timer = threading.Timer(wait_time / 1000.0 if wait_time > 1000 else wait_time, 
                                    self.receive_time_out, 
                                    args=[self.WAIT_DATA_HANDLER_START_TIMEOUT, info.DataHandlerId])
            timer.start()
            
            self.m_DataHandlerExecuteTimerMap[info.DataHandlerId] = timer
            
            world.send_info_change(info)
            return True

        else:
            status_str = "Start" if info.RequestStatus == WAIT_START else "Stop"
            msg = f"Already Rerquest DataHandler: {info.DataHandlerId}({status_str})"
            print(f"[DataHandlerConnMgr] {msg}")
            
            from Server.AsciiServerWorld import AsciiServerWorld
            AsciiServerWorld._instance.send_ascii_error(1, msg)
            return False

    def run_command(self, ssh_id, ssh_pass, ip, command):
        """
        C++: bool RunCommand(...)
        """
        # Using FrSshUtil (assumed to be implemented similarly to C++)
        ret = self.m_SshUtil.ssh_connect(ip, 22, ssh_id, ssh_pass, command)
        
        if not ret:
            print("[DataHandlerConnMgr] SSH Connect Fail!!!!!!")
            return False
        else:
            print("[DataHandlerConnMgr] SSH Connect !!!!!!")
            return True

    def stop_data_handler(self, info):
        """
        C++: bool StopDataHandler(AS_DATA_HANDLER_INFO_T* Info)
        """
        # FindSession is in SockMgrConnMgr/ConnectionMgr
        # Need to cast to DataHandlerConnection (Python acts dynamically)
        con = self.find_session(info.DataHandlerId)
        
        if con is None:
            msg = f"Can't find the executed DataHandler({info.DataHandlerId})."
            print(f"[DataHandlerConnMgr] {msg}")
            from Server.AsciiServerWorld import AsciiServerWorld
            AsciiServerWorld._instance.send_ascii_error(1, msg)
            return False

        info.RequestStatus = WAIT_STOP
        
        from Server.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.send_info_change(info)
        
        con.stop_data_handler()
        return True

    def data_handler_session_identify(self, data_handler_id):
        """
        C++: void DataHandlerSessionIdentify(string DataHandlerId)
        Cancels the start timeout timer.
        """
        if data_handler_id in self.m_DataHandlerExecuteTimerMap:
            timer = self.m_DataHandlerExecuteTimerMap[data_handler_id]
            timer.cancel()
            del self.m_DataHandlerExecuteTimerMap[data_handler_id]
        else:
            print(f"[DataHandlerConnMgr] [CORE_ERROR] Can't Find DataHandler({data_handler_id}) in DataHandlerExecuteTimerMap")

    def get_data_handler_info_map(self):
        """
        C++: DataHandlerInfoMap* GetDataHandlerInfoMap()
        """
        return self.m_DataHandlerInfoMap

    def update_data_handler_log_status(self, status):
        """
        C++: void UpdateDataHandlerLogStatus(AS_LOG_STATUS_T* Status)
        """
        # Original C++ code has 'return;' at the start, essentially disabled?
        # Implementing logic assuming it should work based on other managers.
        # If C++ had 'return', maybe keep it disabled or comment out.
        # Uncomment below to enable logic:
        """
        if status.name in self.m_LogStatusMap:
            del self.m_LogStatusMap[status.name]

        if status.status == LOG_ADD:
            self.m_LogStatusMap[status.name] = copy.deepcopy(status)
            
        from Server.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.send_log_status(status)
        """
        pass # Following C++ 'return;'

    def get_log_status_list(self, status_list):
        """
        C++: void GetLogStatusList(LogStatusVector* StatusList)
        """
        for status in self.m_LogStatusMap.values():
            status_list.append(status)

    def receive_proc_info(self, proc_info):
        """
        C++: void ReceiveProcInfo(AS_PROCESS_STATUS_T* ProcInfo)
        """
        from Server.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.update_process_info(proc_info)

    def recv_process_control(self, proc_ctl):
        """
        C++: bool RecvProcessControl(AS_PROC_CONTROL_T* ProcCtl)
        """
        info = self.find_data_handler_info(proc_ctl.ProcessId)
        
        if info is None:
            print(f"[DataHandlerConnMgr] [CORE_ERROR] Can't Find DataHandler : {proc_ctl.ProcessId}")
            return False

        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        if info.RequestStatus == WAIT_NO:
            if proc_ctl.Status == START and info.CurStatus == START:
                msg = f"Already Started DataHandler : {proc_ctl.ProcessId}"
                print(f"[DataHandlerConnMgr] {msg}")
                world.send_ascii_error(1, msg)
                return False
                
            elif proc_ctl.Status == STOP and info.CurStatus == STOP:
                msg = f"Already Stop DataHandler : {proc_ctl.ProcessId}"
                print(f"[DataHandlerConnMgr] {msg}")
                world.send_ascii_error(1, msg)
                return False

            if world.m_DbManager and not world.m_DbManager.update_data_handler_status(proc_ctl.ProcessId, proc_ctl.Status):
                 print(f"[DataHandlerConnMgr] [CORE_ERROR] Update DataHandler Status Error : {world.m_DbManager.get_error_msg()}")
                 return False

            info.SettingStatus = START if proc_ctl.Status == START else STOP

            if info.RunMode == 0:
                # Normal Mode logic
                # SendDataHandlerInfoChange -> likely meant for DataRouter sync?
                # Assuming not implemented or stub needed
                pass

            if proc_ctl.Status == START:
                if self.execute_data_handler(info):
                    world.send_ascii_error(1, f"The DataHandler({proc_ctl.ProcessId}) start successfull")
                else:
                    # GetGErrMsg equivalent
                    world.send_ascii_error(1, "Execute Fail")
                    
            elif proc_ctl.Status == STOP:
                self.stop_data_handler(info)

        else:
            status_str = "Start" if info.RequestStatus == WAIT_START else "Stop"
            msg = f"Already Rerquest Process: {proc_ctl.ProcessId}({status_str})"
            print(f"[DataHandlerConnMgr] {msg}")
            world.send_ascii_error(1, msg)
            return False
            
        return False

    def find_data_handler_info(self, data_handler_id):
        """
        C++: AS_DATA_HANDLER_INFO_T* FindDataHandlerInfo(string DataHandlerId)
        """
        return self.m_DataHandlerInfoMap.get(data_handler_id)

    def receive_time_out(self, reason, extra_reason):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        """
        if reason == self.WAIT_DATA_HANDLER_START_TIMEOUT:
            # extra_reason is DataHandlerId (str) in Python context
            dh_id = extra_reason
            print(f"[DataHandlerConnMgr] Recv Timeout WAIT_DATA_HANDLER_START_TIMEOUT : {dh_id}")

            from Server.AsciiServerWorld import AsciiServerWorld
            world = AsciiServerWorld._instance
            world.send_ascii_error(1, f"DataHandler({dh_id}) Start Error")

            if dh_id in self.m_DataHandlerExecuteTimerMap:
                del self.m_DataHandlerExecuteTimerMap[dh_id]
            else:
                print(f"[DataHandlerConnMgr] [CORE_ERROR] Can't Find DataHandler({dh_id}) in DataHandlerExecuteTimerMap")

            info = self.find_data_handler_info(dh_id)
            if info is None:
                print(f"[DataHandlerConnMgr] [CORE_ERROR] DataHandler Info Can't Find : {dh_id}")
                return

            print(f"[DataHandlerConnMgr] DataHandler {dh_id} Status is setting STOP")

            if world.m_DbManager and not world.m_DbManager.update_data_handler_status(dh_id, STOP):
                print(f"[DataHandlerConnMgr] [CORE_ERROR] Update Datahandler Status Error : {world.m_DbManager.get_error_msg()}")
                return

            info.SettingStatus = STOP
            info.CurStatus = STOP
            info.RequestStatus = WAIT_NO

            # Send Info Changes
            world.send_info_change(info)

    def kill_data_handler(self, data_handler_id):
        """
        C++: void KillDataHandler(string DataHandlerId)
        """
        info = self.find_data_handler_info(data_handler_id)

        if info is None:
            print(f"[DataHandlerConnMgr] [CORE_ERROR] Can't Find DataHandler : {data_handler_id}")
            return

        from Server.AsciiServerWorld import AsciiServerWorld
        user_name = AsciiServerWorld._instance.get_user_name()
        start_dir = AsUtil.get_start_dir()
        
        cmd = f"~{user_name}{start_dir}/Script/KillDataHandler.sh {info.DataHandlerId}"
        
        print(f"[DataHandlerConnMgr] Kill DataHandler : {cmd}")
        self.run_command(info.SshID, info.SshPass, info.IpAddress, cmd)
        time.sleep(1)

    def recv_info_change(self, info, result_msg=""):
        """
        C++: bool RecvInfoChange(AS_DATA_HANDLER_INFO_T* Info, char* ResultMsg)
        """
        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        if info.RequestStatus == CREATE_DATA:
            new_info = copy.deepcopy(info)
            new_info.RequestStatus = WAIT_NO
            new_info.CurStatus = STOP
            new_info.SettingStatus = STOP
            
            self.m_DataHandlerInfoMap[new_info.DataHandlerId] = new_info
            world.send_info_change(info)
            return True

        elif info.RequestStatus == UPDATE_DATA:
            if info.OldDataHandlerId not in self.m_DataHandlerInfoMap:
                # Python string assignment cannot act as char* return, logic simplified
                print(f"Can't Find DataHandler : {info.OldDataHandlerId}")
                return False
            
            # Remove old
            del self.m_DataHandlerInfoMap[info.OldDataHandlerId]
            
            # Insert new
            new_info = copy.deepcopy(info)
            new_info.CurStatus = STOP
            new_info.SettingStatus = STOP
            new_info.RequestStatus = WAIT_NO
            new_info.OldDataHandlerId = ""
            
            self.m_DataHandlerInfoMap[new_info.DataHandlerId] = new_info
            
            # Send changes (Sync if needed)
            world.send_info_change(info)
            return True

        elif info.RequestStatus == DELETE_DATA:
            if info.DataHandlerId not in self.m_DataHandlerInfoMap:
                print(f"Can't Find DataHandler : {info.DataHandlerId}")
                return False
            
            # Preserve RunMode before delete (from C++ logic)
            existing = self.m_DataHandlerInfoMap[info.DataHandlerId]
            info.RunMode = existing.RunMode
            
            del self.m_DataHandlerInfoMap[info.DataHandlerId]
            
            world.send_info_change(info)
            return True
            
        return False

    def recv_init_info(self, init_info):
        """
        C++: void RecvInitInfo(AS_DATA_HANDLER_INIT_T* InitInfo)
        """
        con = self.find_session(init_info.DataHandlerId)
        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        if con is None:
            msg = f"Can't find the DataHandler({init_info.DataHandlerId}) to init."
            print(f"[DataHandlerConnMgr] {msg}")
            world.send_ascii_error(1, msg)
            return

        body = init_info.pack()
        con.packet_send(PacketT(AS_DATA_HANDLER_INIT, len(body), body))
        
        world.send_ascii_error(1, f"Success notify to DataHandler({init_info.DataHandlerId}) for initialize.")

    # ------------------------------------------------------------------
    # Helper to find session from SockMgrConnMgr list by name
    # ------------------------------------------------------------------
    def find_session(self, session_name):
        # Assuming SockMgrConnMgr has a list and connections have get_session_name()
        for conn in self.m_SocketConnectionList:
            if conn.get_session_name() == session_name:
                return conn
        return None