import sys
import os
import threading
import copy
import time

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Try importing parent class based on availability
from Class.Common.SockMgrConnMgr import SockMgrConnMgr
from Class.ProcNaServer.SubProcConnection import SubProcConnection
from Class.Common.CommType import *
from Class.Common.AsUtil import AsUtil

class SubProcConnMgr(SockMgrConnMgr):
    """
    Manages connections and lifecycle (Start/Stop/Kill) of Sub-Processes.
    Inherits from SockMgrConnMgr for socket management.
    """

    # Constants
    WAIT_DATA_HANDLER_START_TIME = 10
    WAIT_DATA_HANDLER_START_TIMEOUT = 1002

    def __init__(self):
        """
        C++: SubProcConnMgr::SubProcConnMgr()
        """
        super().__init__()
        
        # Key: ProcIdStr (str), Value: AsSubProcInfoT
        self.m_SubProcInfoMap = {}
        
        # Key: ProcIdStr (str), Value: threading.Timer
        self.m_SubProcExecuteTimerMap = {}

    def __del__(self):
        """
        C++: SubProcConnMgr::~SubProcConnMgr()
        """
        self.m_SubProcInfoMap.clear()
        
        # Cancel all running timers
        for timer in self.m_SubProcExecuteTimerMap.values():
            timer.cancel()
        self.m_SubProcExecuteTimerMap.clear()
        
        super().__del__()

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        """
        sub_proc_conn = SubProcConnection(self)

        if not self.accept(sub_proc_conn):
            print(f"[SubProcConnMgr] SubProc Socket Accept Error : {self.get_obj_err_msg()}")
            sub_proc_conn.close()
            return

        self.add(sub_proc_conn)
        print("[SubProcConnMgr] SubProc Connection")

    def init(self):
        """
        C++: bool Init()
        Loads SubProc info from DB.
        """
        self.m_SubProcInfoMap.clear()
        
        from Server.AsciiServerWorld import AsciiServerWorld
        db_mgr = AsciiServerWorld._instance.m_DbManager
        
        if db_mgr:
            if not db_mgr.get_sub_proc_info(self.m_SubProcInfoMap):
                print(f"[SubProcConnMgr] [CORE_ERROR] Get SubProc Info Error : {db_mgr.get_error_msg()}")
                return False
        return True

    def execute_sub_proc_all(self):
        """
        C++: void ExecuteSubProc()
        Iterates through all configured sub-processes and starts them if SettingStatus is START.
        """
        if not self.init():
            return

        wait_time = 50

        # Iterate over copy keys to allow modification if needed
        for info in self.m_SubProcInfoMap.values():
            print(f"[SubProcConnMgr] SubProcId : {info.ProcIdStr}")

            if info.SettingStatus == START:
                self.execute_sub_proc(info, self.WAIT_DATA_HANDLER_START_TIME + wait_time)
                wait_time += 2

    def execute_sub_proc(self, info, wait_time=0):
        """
        C++: bool ExecuteSubProc(AS_SUB_PROC_INFO_T* Info, int WaitTime)
        Constructs the command line and executes the sub-process via system call.
        """
        if info.RequestStatus == WAIT_NO:
            
            # 1. Kill existing instance first
            self.kill_sub_proc(info.ProcIdStr)

            # 2. Prepare Log Cycle Argument
            log_cycle_buf = ""
            if info.LogCycle == 1:
                # Constants ARG_LOG_CYCLE, ARG_LOG_HOUR assumed to be defined globally
                log_cycle_buf = f"{ARG_LOG_CYCLE} {ARG_LOG_HOUR}"

            # 3. Construct Command
            # Format: ~/NAA/Bin/RunCommand CLIENT Ip RunCmdPort User ~StartDir/Bin/BinaryName ...
            
            from Server.AsciiServerWorld import AsciiServerWorld
            world = AsciiServerWorld._instance
            
            user_name = world.get_user_name()
            start_dir = AsUtil.get_start_dir()
            server_ip = world.get_server_ip()
            listen_port = world.get_listen_port(ASCII_SUB_PROCESS)
            run_cmd_port = getattr(world, 'm_RunCmdPort', "10000") # Default or member

            # Python f-string equivalent of C++ sprintf
            cmd_exec = (
                f"~/NAA/Bin/RunCommand CLIENT {info.IpAddress} {run_cmd_port} {user_name} "
                f"'~{user_name}{start_dir}/Bin/{info.BinaryName} "
                f"{ARG_NAME} {info.ProcIdStr} "
                f"{ARG_SVR_IP} {server_ip} "
                f"{ARG_SVR_PORT} {listen_port} {log_cycle_buf} {info.Args}'"
            )

            print(f"[SubProcConnMgr] SubProc Execute: {cmd_exec}")
            
            # 4. Execute Command
            os.system(cmd_exec)
            
            # 5. Update Status & Set Timer
            info.RequestStatus = WAIT_START

            # Timer Setup
            timer = threading.Timer(wait_time / 1000.0 if wait_time > 1000 else wait_time, 
                                    self.receive_time_out, 
                                    args=[self.WAIT_DATA_HANDLER_START_TIMEOUT, info.ProcIdStr])
            timer.start()
            
            self.m_SubProcExecuteTimerMap[info.ProcIdStr] = timer
            
            world.send_info_change(info)
            return True

        else:
            status_str = "Start" if info.RequestStatus == WAIT_START else "Stop"
            msg = f"Already Rerquest SubProc: {info.ProcIdStr}({status_str})"
            print(f"[SubProcConnMgr] {msg}")
            
            from Server.AsciiServerWorld import AsciiServerWorld
            AsciiServerWorld._instance.send_ascii_error(1, msg)
            return False

    def stop_sub_proc(self, info):
        """
        C++: bool StopSubProc(AS_SUB_PROC_INFO_T* Info)
        """
        con = self.find_session(info.ProcIdStr)
        
        if con is None:
            msg = f"Can't find the executed SubProc({info.ProcIdStr})."
            print(f"[SubProcConnMgr] {msg}")
            
            from Server.AsciiServerWorld import AsciiServerWorld
            AsciiServerWorld._instance.send_ascii_error(1, msg)
            return False

        info.RequestStatus = WAIT_STOP
        
        from Server.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.send_info_change(info)
        
        con.stop_sub_proc()
        return True

    def sub_proc_session_identify(self, proc_id_str):
        """
        C++: void SubProcSessionIdentify(string ProcIdStr)
        Cancels the startup timer upon successful connection identification.
        """
        if proc_id_str in self.m_SubProcExecuteTimerMap:
            timer = self.m_SubProcExecuteTimerMap[proc_id_str]
            timer.cancel()
            del self.m_SubProcExecuteTimerMap[proc_id_str]
        else:
            print(f"[SubProcConnMgr] [CORE_ERROR] Can't Find SubProc({proc_id_str}) in SubProcExecuteTimerMap")

    def get_sub_proc_info_map(self):
        """
        C++: SubProcInfoMap* GetSubProcInfoMap()
        """
        return self.m_SubProcInfoMap

    def receive_proc_info(self, proc_info):
        """
        C++: void ReceiveProcInfo(AS_PROCESS_STATUS_T* ProcInfo)
        """
        from Server.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.update_process_info(proc_info)

    def recv_process_control(self, proc_ctl):
        """
        C++: bool RecvProcessControl(AS_PROC_CONTROL_T* ProcCtl)
        Handles administrative Start/Stop commands.
        """
        info = self.find_sub_proc_info(proc_ctl.ProcessId)
        
        if info is None:
            print(f"[SubProcConnMgr] [CORE_ERROR] Can't Find SubProc : {proc_ctl.ProcessId}")
            return False

        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        if info.RequestStatus == WAIT_NO:
            if proc_ctl.Status == START and info.CurStatus == START:
                msg = f"Already Started SubProc : {proc_ctl.ProcessId}"
                print(f"[SubProcConnMgr] {msg}")
                world.send_ascii_error(1, msg)
                return False
                
            elif proc_ctl.Status == STOP and info.CurStatus == STOP:
                msg = f"Already Stop SubProc : {proc_ctl.ProcessId}"
                print(f"[SubProcConnMgr] {msg}")
                world.send_ascii_error(1, msg)
                return False

            if world.m_DbManager and not world.m_DbManager.update_sub_proc_status(proc_ctl.ProcessId, proc_ctl.Status):
                 print(f"[SubProcConnMgr] [CORE_ERROR] Update SubProc Status Error : {world.m_DbManager.get_error_msg()}")
                 return False

            info.SettingStatus = START if proc_ctl.Status == START else STOP

            if proc_ctl.Status == START:
                if self.execute_sub_proc(info):
                    world.send_ascii_error(1, f"The SubProc({proc_ctl.ProcessId}) start successfull")
                else:
                    world.send_ascii_error(1, "Execute Fail") # GetGErrMsg stub
                    
            elif proc_ctl.Status == STOP:
                self.stop_sub_proc(info)

        else:
            status_str = "Start" if info.RequestStatus == WAIT_START else "Stop"
            msg = f"Already Rerquest Process: {proc_ctl.ProcessId}({status_str})"
            print(f"[SubProcConnMgr] {msg}")
            world.send_ascii_error(1, msg)
            return False
            
        return False

    def find_sub_proc_info(self, proc_id_str):
        """
        C++: AS_SUB_PROC_INFO_T* FindSubProcInfo(string ProcIdStr)
        """
        return self.m_SubProcInfoMap.get(proc_id_str)

    def receive_time_out(self, reason, extra_reason):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        """
        if reason == self.WAIT_DATA_HANDLER_START_TIMEOUT:
            proc_id = extra_reason
            print(f"[SubProcConnMgr] Recv Timeout WAIT_DATA_HANDLER_START_TIMEOUT : {proc_id}")

            from Server.AsciiServerWorld import AsciiServerWorld
            world = AsciiServerWorld._instance
            world.send_ascii_error(1, f"SubProc({proc_id}) Start Error")

            if proc_id in self.m_SubProcExecuteTimerMap:
                del self.m_SubProcExecuteTimerMap[proc_id]
            else:
                print(f"[SubProcConnMgr] [CORE_ERROR] Can't Find SubProc({proc_id}) in SubProcExecuteTimerMap")

            info = self.find_sub_proc_info(proc_id)
            if info is None:
                print(f"[SubProcConnMgr] [CORE_ERROR] SubProc Info Can't Find : {proc_id}")
                return

            print(f"[SubProcConnMgr] SubProc {proc_id} Status is setting STOP")

            if world.m_DbManager and not world.m_DbManager.update_sub_proc_status(proc_id, STOP):
                print(f"[SubProcConnMgr] [CORE_ERROR] Update SubProc Status Error : {world.m_DbManager.get_error_msg()}")
                return

            info.SettingStatus = STOP
            info.CurStatus = STOP
            info.RequestStatus = WAIT_NO

            world.send_info_change(info)

    def kill_sub_proc(self, proc_id_str):
        """
        C++: void KillSubProc(string ProcIdStr)
        """
        info = self.find_sub_proc_info(proc_id_str)

        if info is None:
            print(f"[SubProcConnMgr] [CORE_ERROR] Can't Find SubProc : {proc_id_str}")
            return

        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        
        user_name = world.get_user_name()
        start_dir = AsUtil.get_start_dir()
        run_cmd_port = getattr(world, 'm_RunCmdPort', "10000")

        # Format: ~/NAA/Bin/RunCommand CLIENT Ip RunCmdPort User ~StartDir/Bin/KillProcess ProcId
        cmd = (
            f"~/NAA/Bin/RunCommand CLIENT {info.IpAddress} {run_cmd_port} {user_name} "
            f"'~{user_name}{start_dir}/Bin/KillProcess {info.ProcIdStr}'"
        )

        print(f"[SubProcConnMgr] Kill SubProc : {cmd}")
        os.system(cmd)

    def recv_info_change(self, info, result_msg=""):
        """
        C++: bool RecvInfoChange(AS_SUB_PROC_INFO_T* Info, char* ResultMsg)
        """
        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        if info.RequestStatus == CREATE_DATA:
            new_info = copy.deepcopy(info)
            new_info.RequestStatus = WAIT_NO
            new_info.CurStatus = STOP
            new_info.SettingStatus = STOP
            
            self.m_SubProcInfoMap[new_info.ProcIdStr] = new_info
            world.send_info_change(info)
            return True

        elif info.RequestStatus == UPDATE_DATA:
            if info.OldProcIdStr not in self.m_SubProcInfoMap:
                print(f"Can't Find SubProc : {info.OldProcIdStr}")
                return False
            
            # Remove old
            del self.m_SubProcInfoMap[info.OldProcIdStr]
            
            # Insert new
            new_info = copy.deepcopy(info)
            new_info.CurStatus = STOP
            new_info.SettingStatus = STOP
            new_info.RequestStatus = WAIT_NO
            new_info.OldProcIdStr = ""
            
            self.m_SubProcInfoMap[new_info.ProcIdStr] = new_info
            
            world.send_info_change(info)
            return True

        elif info.RequestStatus == DELETE_DATA:
            if info.ProcIdStr not in self.m_SubProcInfoMap:
                print(f"Can't Find SubProc : {info.ProcIdStr}")
                return False
            
            del self.m_SubProcInfoMap[info.ProcIdStr]
            
            world.send_info_change(info)
            return True
            
        return False

    # ------------------------------------------------------------------
    # Helper to find session
    # ------------------------------------------------------------------
    def find_session(self, session_name):
        for conn in self.m_SocketConnectionList:
            if conn.get_session_name() == session_name:
                return conn
        return None