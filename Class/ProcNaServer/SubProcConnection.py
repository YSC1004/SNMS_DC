import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.AsSocket import AsSocket
from Class.Common.CommType import *
from Class.Common.AsUtil import AsUtil

class SubProcConnection(AsSocket):
    """
    Handles connection with Sub Processes (ASCII_SUB_PROCESS).
    Manages lifecycle, keep-alive, and auto-restart on abnormal termination.
    """

    # Constants for Timer
    PROC_TERMINATE_WAIT = 1001
    PROC_TERMINATE_WAIT_TIMEOUT = 5  # seconds

    def __init__(self, conn_mgr):
        """
        C++: SubProcConnection(SubProcConnMgr* ConnMgr)
        """
        super().__init__()
        self.m_SubProcConnMgr = conn_mgr
        self.m_SubProcInfo = None  # Stores AsSubProcInfoT instance

    def __del__(self):
        """
        C++: ~SubProcConnection()
        """
        super().__del__()

    def receive_packet(self, packet, session_identify):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        if session_identify == ASCII_SUB_PROCESS:
            self.sub_proc_req_process(packet)
        else:
            print(f"[SubProcConnection] UnKnown Session : {session_identify}")

    def sub_proc_req_process(self, packet):
        """
        C++: void SubProcReqProcess(PACKET_T* Packet)
        """
        msg_id = packet.msg_id
        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        if msg_id == PROC_INIT_END:
            pass

        elif msg_id == ASCII_ERROR_MSG:
            error = AsAsciiErrorMsgT.unpack(packet.msg_body)
            if error:
                world.send_ascii_error(error)

        elif msg_id == PROCESS_INFO:
            proc_info = AsProcessStatusT.unpack(packet.msg_body)
            if proc_info:
                proc_info.ManagerId = world.get_proc_name()
                proc_info.ProcessId = self.get_session_name()
                
                self.m_SubProcConnMgr.receive_proc_info(proc_info)

        elif msg_id == AS_SYSTEM_INFO:
            sys_info = AsSystemInfoT.unpack(packet.msg_body)
            if sys_info:
                # Assuming recv_system_info is implemented in World
                # world.recv_system_info(sys_info)
                pass

        else:
            print(f"[SubProcConnection] UnKnown MsgId : {msg_id}")

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        Handles connection closure. If the process was supposed to be running (START),
        it triggers a restart routine.
        """
        print(f"[SubProcConnection] Socket Broken : {self.get_session_name()}")

        if self.m_SubProcInfo is None:
            self.m_SubProcConnMgr.remove(self)
            return

        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        # 1. Update Info Status to STOP
        self.m_SubProcInfo.CurStatus = STOP
        self.m_SubProcInfo.RequestStatus = WAIT_NO
        world.recv_info_change(self.m_SubProcInfo)

        # 2. Remove Session Name from Manager
        self.m_SubProcConnMgr.remove_session_name(self.get_session_name())

        # 3. Broadcast Process Status (STOP)
        proc_info = AsProcessStatusT()
        proc_info.ManagerId = world.get_proc_name()
        proc_info.ProcessId = self.get_session_name()
        proc_info.Status = STOP
        proc_info.ProcessType = ASCII_SUB_PROCESS
        world.update_process_info(proc_info)

        # 4. Check for Abnormal Termination
        if self.m_SubProcInfo.SettingStatus == START:
            # Abnormal Exit -> Restart
            msg = f"The SubProc({self.get_session_name()}) is killed abnormal."
            world.send_ascii_error(1, msg)

            self.m_SubProcConnMgr.execute_sub_proc(self.m_SubProcInfo)

            msg_reexec = f"SubProc({self.m_SubProcInfo.ProcIdStr}) is reexecuted."
            world.send_ascii_error(1, msg_reexec)
        else:
            # Normal Exit
            msg = f"The SubProc({self.get_session_name()}) is killed normally."
            world.send_ascii_error(1, msg)

        # 5. Remove Connection
        self.m_SubProcConnMgr.remove(self)

    def session_identify(self, session_type, session_name):
        """
        C++: void SessionIdentify(int SessionType, string SessionName)
        """
        # 1. Find Info
        self.m_SubProcInfo = self.m_SubProcConnMgr.find_sub_proc_info(session_name)

        if self.m_SubProcInfo is None:
            print(f"[SubProcConnection] [CORE_ERROR] Can't find SubProc : {session_name}")
            self.close()
            self.m_SubProcConnMgr.remove(self)
            return

        # 2. Register Session Name
        if not self.m_SubProcConnMgr.add_session_name(session_name):
            self.close()
            self.m_SubProcConnMgr.remove(self)
            return

        print(f"[SubProcConnection] SubProc Session Identify : Type({AsUtil.get_process_type_string(session_type)}), SessionName({session_name})")

        # 3. Manager Identification Logic
        self.m_SubProcConnMgr.sub_proc_session_identify(session_name)

        # 4. Update Status to START
        self.m_SubProcInfo.CurStatus = START
        self.m_SubProcInfo.RequestStatus = WAIT_NO

        from Server.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.recv_info_change(self.m_SubProcInfo)

        # 5. Start Keep-Alive
        world = AsciiServerWorld._instance
        self.start_alive_check(world.get_proc_alive_check_time(), world.get_alive_check_limit_cnt())

    def alive_check_fail(self, fail_count):
        """
        C++: void AliveCheckFail(int FailCount)
        """
        print(f"[SubProcConnection] AliveCheckFail({self.get_session_name()}) , Count : {fail_count}")

        msg = f"The SubProc({self.get_session_name()}) is killed on purpose for no reply."
        print(f"[SubProcConnection] {msg}")

        from Server.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.send_ascii_error(1, msg)

        if self.m_SubProcInfo:
            self.m_SubProcConnMgr.kill_sub_proc(self.m_SubProcInfo.ProcIdStr)

    def stop_sub_proc(self):
        """
        C++: void StopSubProc()
        Sends terminate command and starts timeout timer.
        """
        self.packet_send_msg(CMD_PROC_TERMINATE)
        self.set_timer(self.PROC_TERMINATE_WAIT_TIMEOUT, self.PROC_TERMINATE_WAIT)

    def receive_time_out(self, reason, extra_reason=None):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        """
        if reason == self.PROC_TERMINATE_WAIT:
            print("[SubProcConnection] [CORE_ERROR] SubProc Terminate TimeOut")
            print(f"[SubProcConnection] [CORE_ERROR] SubProc Kill Force!!! : {self.get_session_name()}")

            if self.m_SubProcInfo:
                self.m_SubProcConnMgr.kill_sub_proc(self.m_SubProcInfo.ProcIdStr)
            return

        else:
            print(f"[SubProcConnection] Unknown Timeout Reason {reason}")