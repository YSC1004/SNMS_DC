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

class ManagerConnection(AsSocket):
    """
    Handles the connection to the Manager process.
    Processes log status changes and reports errors.
    """
    def __init__(self):
        """
        C++: ManagerConnection()
        """
        super().__init__()

    def __del__(self):
        """
        C++: ~ManagerConnection()
        """
        super().__del__()

    def receive_packet(self, packet, session_identify=0):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        print(f"[ManagerConnection] Receive Message Msg Id: {packet.msg_id}")

        if packet.msg_id == CMD_LOG_STATUS_CHANGE:
            log_ctl = AsCmdLogControlT.unpack(packet.msg_body)
            if log_ctl:
                self.receive_cmd_log_status_change(log_ctl)
        else:
            # Default case
            pass

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        Manager connection loss is critical for LogRouter.
        """
        print("[ManagerConnection] [CORE_ERROR] Manager Connection Broken")
        
        # Access World to exit
        from LogRouterWorld import LogRouterWorld
        # C++: MAINPTR->Exit(0);
        # Since AsWorld.exit() might not be fully implemented in Python context, 
        # we generally use sys.exit() or a World helper.
        sys.exit(0)

    def send_log_status(self, status):
        """
        C++: void SendLogStatus(const AS_LOG_STATUS_T* Status)
        """
        body = status.pack()
        self.packet_send(PacketT(AS_LOG_INFO, len(body), body))

    def receive_cmd_log_status_change(self, log_ctl):
        """
        C++: void ReceiveCmdLogStatusChange(AS_CMD_LOG_CONTROL_T* LogCtl)
        Updates log status in World and sends the new status back to Manager.
        """
        from LogRouterWorld import LogRouterWorld
        world = LogRouterWorld.get_instance()
        
        # C++: MAINPTR->ChangeLogStatus(LogCtl)
        # Assuming ChangeLogStatus is implemented in AsWorld/LogRouterWorld
        # and returns the updated AS_LOG_STATUS_T object
        new_status = world.change_log_status(log_ctl)
        
        if new_status:
            self.send_log_status(new_status)

    def send_ascii_error(self, arg1, arg2=None):
        """
        Overloaded method for SendAsciiError.
        1. send_ascii_error(priority: int, err_msg: str)
        2. send_ascii_error(err_msg_struct: AsAsciiErrorMsgT)
        """
        # Case 1: (int, str)
        if isinstance(arg1, int) and isinstance(arg2, str):
            priority = arg1
            msg_str = arg2
            
            from LogRouterWorld import LogRouterWorld
            world = LogRouterWorld.get_instance()

            err = AsAsciiErrorMsgT()
            err.Priority = priority
            err.ErrMsg = msg_str
            err.ProcessType = ASCII_LOG_ROUTER
            err.ProcessId = world.get_proc_name()
            
            self.send_ascii_error(err) # Call Case 2

        # Case 2: (AsAsciiErrorMsgT)
        elif hasattr(arg1, 'pack'): 
            err_msg = arg1
            body = err_msg.pack()
            
            if not self.packet_send(PacketT(ASCII_ERROR_MSG, len(body), body)):
                self.close_socket()