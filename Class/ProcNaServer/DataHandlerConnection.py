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

class DataHandlerConnection(AsSocket):
    """
    Handles connection with Data Handler processes (ASCII_DATA_HANDLER).
    """
    
    # Constants for Timer
    PROC_TERMINATE_WAIT = 1001
    PROC_TERMINATE_WAIT_TIMEOUT = 5 # seconds

    def __init__(self, conn_mgr):
        """
        C++: DataHandlerConnection(DataHandlerConnMgr* ConnMgr)
        """
        super().__init__()
        self.m_DataHandlerConnMgr = conn_mgr
        self.m_DataHandlerInfo = None # Stores AsDataHandlerInfoT instance

    def __del__(self):
        """
        C++: ~DataHandlerConnection()
        """
        super().__del__()

    def receive_packet(self, packet, session_identify):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        if session_identify == ASCII_DATA_HANDLER:
            self.data_handler_req_process(packet)
        else:
            print(f"[DataHandlerConnection] UnKnown Session : {session_identify}")

    def data_handler_req_process(self, packet):
        """
        C++: void DataHandlerReqProcess(PACKET_T* Packet)
        """
        msg_id = packet.msg_id
        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        if msg_id == PROC_INIT_END:
            pass

        elif msg_id == AS_LOG_INFO:
            status = AsLogStatusT.unpack(packet.msg_body)
            if status:
                self.receive_log_info(status)

        elif msg_id == ASCII_ERROR_MSG:
            error = AsAsciiErrorMsgT.unpack(packet.msg_body)
            if error:
                world.write_error_log(error)

        elif msg_id == PROCESS_INFO:
            proc_info = AsProcessStatusT.unpack(packet.msg_body)
            if proc_info:
                proc_info.ManagerId = world.get_proc_name()
                # ProcessId format: "ASCII_DATA_HANDLER_SessionName"
                proc_info.ProcessId = f"{AsUtil.get_process_type_string(ASCII_DATA_HANDLER)}_{self.get_session_name()}"
                
                self.m_DataHandlerConnMgr.receive_proc_info(proc_info)

        elif msg_id == AS_SYSTEM_INFO:
            sys_info = AsSystemInfoT.unpack(packet.msg_body)
            if sys_info:
                # Assuming RecvSystemInfo is implemented in World
                # world.recv_system_info(sys_info) 
                pass

        else:
            print(f"[DataHandlerConnection] UnKnown MsgId : {msg_id}")

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        """
        print(f"[DataHandlerConnection] Socket Broken : {self.get_session_name()}")
        
        if self.m_DataHandlerInfo is None:
            self.m_DataHandlerConnMgr.remove(self)
            return

        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        # Update Info Status
        self.m_DataHandlerInfo.CurStatus = STOP
        self.m_DataHandlerInfo.RequestStatus = WAIT_NO
        world.recv_info_change(self.m_DataHandlerInfo)

        # Log Status Update (Delete)
        log_status = AsLogStatusT()
        log_status.name = self.get_session_name()
        log_status.logs = f"sUn,{AsUtil.get_process_type_string(self.get_session_type())},{self.get_session_name()},"
        log_status.status = LOG_DEL
        
        self.m_DataHandlerConnMgr.update_data_handler_log_status(log_status)
        self.m_DataHandlerConnMgr.remove_session_name(self.get_session_name())

        # Process Info Update (STOP)
        proc_info = AsProcessStatusT()
        proc_info.ManagerId = world.get_proc_name()
        proc_info.ProcessId = f"{AsUtil.get_process_type_string(ASCII_DATA_HANDLER)}_{self.get_session_name()}"
        proc_info.Status = STOP
        proc_info.ProcessType = ASCII_DATA_HANDLER
        
        world.update_process_info(proc_info)

        # Abnormal Termination Handling
        if self.m_DataHandlerInfo.SettingStatus == START:
            msg = f"The DataHandler({self.get_session_name()}) is killed abnormal."
            world.send_ascii_error(1, msg)
            
            self.m_DataHandlerConnMgr.execute_data_handler(self.m_DataHandlerInfo)
            
            msg_reexec = f"DataHandler({self.m_DataHandlerInfo.DataHandlerId}) is reexecuted."
            world.send_ascii_error(1, msg_reexec)
        else:
            msg = f"The DataHandler({self.get_session_name()}) is killed normally."
            world.send_ascii_error(1, msg)

        self.m_DataHandlerConnMgr.remove(self)

    def session_identify(self, session_type, session_name):
        """
        C++: void SessionIdentify(int SessionType, string SessionName)
        """
        self.m_DataHandlerInfo = self.m_DataHandlerConnMgr.find_data_handler_info(session_name)

        if self.m_DataHandlerInfo is None:
            print(f"[DataHandlerConnection] [CORE_ERROR] Can't Find DataHandler : {session_name}")
            self.close()
            self.m_DataHandlerConnMgr.remove(self)
            return

        if not self.m_DataHandlerConnMgr.add_session_name(session_name):
            self.close()
            self.m_DataHandlerConnMgr.remove(self)
            return

        print(f"[DataHandlerConnection] DataHandler Session Identify : Type({AsUtil.get_process_type_string(session_type)}), SessionName({session_name})")

        self.m_DataHandlerConnMgr.data_handler_session_identify(session_name)

        # Send Info to DataHandler
        body = self.m_DataHandlerInfo.pack()
        self.packet_send(PacketT(AS_DATA_HANDLER_INFO, len(body), body))

        # Update Status
        self.m_DataHandlerInfo.CurStatus = START
        self.m_DataHandlerInfo.RequestStatus = WAIT_NO

        from AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.recv_info_change(self.m_DataHandlerInfo)
        
        # Start Alive Check
        world = AsciiServerWorld._instance
        self.start_alive_check(world.get_proc_alive_check_time(), world.get_alive_check_limit_cnt())

    def alive_check_fail(self, fail_count):
        """
        C++: void AliveCheckFail(int FailCount)
        """
        print(f"[DataHandlerConnection] AliveCheckFail({self.get_session_name()}) , Count : {fail_count}")
        msg = f"The DataHandler({self.get_session_name()}) is killed on purpose for no reply."
        print(f"[DataHandlerConnection] {msg}")
        
        from AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.send_ascii_error(1, msg)
        
        if self.m_DataHandlerInfo:
            self.m_DataHandlerConnMgr.kill_data_handler(self.m_DataHandlerInfo.DataHandlerId)

    def receive_log_info(self, status):
        """
        C++: void ReceiveLogInfo(AS_LOG_STATUS_T* Status)
        """
        self.m_DataHandlerConnMgr.update_data_handler_log_status(status)

    def stop_data_handler(self):
        """
        C++: void StopDataHandler()
        Sends terminate command and starts a wait timer.
        """
        self.packet_send_msg(CMD_PROC_TERMINATE)
        self.set_timer(self.PROC_TERMINATE_WAIT_TIMEOUT, self.PROC_TERMINATE_WAIT)

    def receive_time_out(self, reason, extra_reason=None):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        """
        if reason == self.PROC_TERMINATE_WAIT:
            print("[DataHandlerConnection] [CORE_ERROR] DataHandler Terminate TimeOut")
            print(f"[DataHandlerConnection] [CORE_ERROR] DataHandler Kill Force!!! : {self.get_session_name()}")
            
            if self.m_DataHandlerInfo:
                self.m_DataHandlerConnMgr.kill_data_handler(self.m_DataHandlerInfo.DataHandlerId)
            return
        
        else:
            print(f"[DataHandlerConnection] Unknown Timeout Reason {reason}")