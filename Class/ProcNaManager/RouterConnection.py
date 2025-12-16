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

class RouterConnection(AsSocket):
    """
    Handles connection with Router process (ASCII_ROUTER).
    Manages lifecycle, alive check, and error reporting.
    """
    
    # Constants for Timer
    PROC_TERMINATE_WAIT = 1001
    PROC_TERMINATE_WAIT_TIMEOUT = 5 # seconds

    def __init__(self, conn_mgr):
        """
        C++: RouterConnection(RouterConnMgr* ConMgr)
        """
        super().__init__()
        self.m_RouterConnMgr = conn_mgr
        self.m_RouterStatus = True

    def __del__(self):
        """
        C++: ~RouterConnection()
        """
        super().__del__()

    def receive_packet(self, packet, session_identify):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        if session_identify == ASCII_ROUTER:
            self.router_proc_req(packet)
        else:
            print(f"[RouterConnection] UnKnown Session : {session_identify}")

    def receive_time_out(self, reason, extra_reason=None):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        """
        if reason == self.PROC_TERMINATE_WAIT:
            self.close()
            self.send_log_status()
            self.m_RouterConnMgr.stop_process(self.get_session_name())
        else:
            print(f"[RouterConnection] UnKnown TimeOut Reason : {reason}")

    def stop_process(self):
        """
        C++: void StopProcess()
        Sends termination command and waits for graceful exit.
        """
        self.m_RouterStatus = False
        self.packet_send_msg(CMD_PROC_TERMINATE)
        self.set_timer(self.PROC_TERMINATE_WAIT_TIMEOUT, self.PROC_TERMINATE_WAIT)

    def send_log_status(self):
        """
        C++: void SendLogStatus()
        """
        log_status = AsLogStatusT()
        log_status.name = self.get_session_name()
        log_status.logs = f"{AsUtil.get_process_type_string(self.get_session_type())},{self.get_session_name()},"
        log_status.status = LOG_DEL
        
        from Server.AsciiManagerWorld import AsciiManagerWorld
        AsciiManagerWorld._instance.send_log_status(log_status)

    def router_proc_req(self, packet):
        """
        C++: void RouterProcReq(PACKET_T* Packet)
        """
        msg_id = packet.msg_id
        from Server.AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance

        if msg_id == AS_LOG_INFO:
            status = AsLogStatusT.unpack(packet.msg_body)
            if status: world.send_log_status(status)

        elif msg_id == ASCII_ERROR_MSG:
            error = AsAsciiErrorMsgT.unpack(packet.msg_body)
            if error: world.send_ascii_error(error)

        else:
            print(f"[RouterConnection] Unknown Msg Id : {msg_id}")

    def session_identify(self, session_type, session_name):
        """
        C++: void SessionIdentify(int SessionType, string SessionName)
        """
        if not self.m_RouterConnMgr.add_session_name(session_name):
            self.close()
            self.m_RouterConnMgr.remove(self)
            return

        print(f"[RouterConnection] SessionType : {AsUtil.get_process_type_string(session_type)}, SessionName : {session_name}")

        # Notify Manager
        self.m_RouterConnMgr.send_process_info(self.get_session_name(), START)

        # Start Alive Check
        from Server.AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance
        self.start_alive_check(world.get_proc_alive_check_time(), world.get_alive_check_limit_cnt())
        
        # Notify World
        world.router_start(self.get_session_name())

    def alive_check_fail(self, fail_count):
        """
        C++: void AliveCheckFail(int FailCount)
        """
        from Server.AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance
        
        if fail_count > world.get_alive_check_limit_cnt():
            print(f"[RouterConnection] Alive Check Fail(count : {fail_count}) Limite Over")
            msg = f"Alive Check Fail(count : {fail_count}) Limite Over"
            world.send_ascii_error(1, msg)

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        """
        print(f"[RouterConnection] Socket Broken Router SessionName : {self.get_session_name()}")
        self.send_log_status()

        if self.m_RouterStatus:
            self.m_RouterConnMgr.child_process_dead(self)
        else:
            self.m_RouterConnMgr.child_process_dead(self, ORDER_KILL)