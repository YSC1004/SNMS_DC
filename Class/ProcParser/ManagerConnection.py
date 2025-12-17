import sys
import os
import struct

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
    Handles connection to the Manager process.
    Receives commands (Rule Down, Open Port, etc.) and sends status/errors.
    """
    def __init__(self, conn_mgr):
        """
        C++: ManagerConnection()
        """
        super().__init__()
        # In C++, this class didn't have a ConnMgr member in the constructor, 
        # but inheriting AsSocket usually implies one. Kept generic here.
        self.m_ParentMgr = conn_mgr 

    def __del__(self):
        """
        C++: ~ManagerConnection()
        """
        super().__del__()

    def receive_packet(self, packet, session_identify=0):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        msg_id = packet.msg_id
        
        # Lazy Import to avoid circular dependency
        from ParserWorld import ParserWorld
        world = ParserWorld.get_instance()

        if msg_id == CMD_OPEN_PORT:
            info = AsCmdOpenPortT.unpack(packet.msg_body)
            if info: self.open_port(info)

        elif msg_id == CMD_LOG_STATUS_CHANGE:
            log_ctl = AsCmdLogControlT.unpack(packet.msg_body)
            if log_ctl: self.receive_cmd_log_status_change(log_ctl)

        elif msg_id == CMD_PARSING_RULE_DOWN:
            world.recv_cmd_init_parsing_rule()

        elif msg_id == CMD_MAPPING_RULE_DOWN:
            world.recv_cmd_init_ne_mapping_rule()

        elif msg_id == CMD_PARSING_RULE_CHANGE:
            change_info = AsRuleChangeInfoT.unpack(packet.msg_body)
            if change_info: world.rule_change(change_info)

        elif msg_id == AS_DATA_HANDLER_INFO:
            dh_info = AsDataHandlerInfoT.unpack(packet.msg_body)
            if dh_info: world.recv_data_handler_info(dh_info)

        else:
            print(f"[ManagerConnection] Unknown Msg Id : {msg_id}")

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        If Manager connection breaks, Parser should exit.
        """
        print("[ManagerConnection] [CORE_ERROR] Manager Connection Broken")
        sys.exit(0)

    def open_port(self, port_info):
        """
        C++: void OpenPort(PACKET_T* Packet) -> Logic moved to accept Struct
        """
        from ParserWorld import ParserWorld
        ParserWorld.get_instance().open_port(port_info)

    def receive_mmc_response_data_req(self, mmc_com):
        """
        C++: void ReceiveMMCResponDataReq(AS_MMC_PUBLISH_T* MMCCom)
        """
        from ParserWorld import ParserWorld
        ParserWorld.get_instance().receive_mmc_respon_data_req(mmc_com)

    def send_response_command_data(self, mmc_result):
        """
        C++: void SendResponseCommandData(AS_MMC_RESULT_T* MmcResult)
        """
        body = mmc_result.pack()
        self.packet_send(PacketT(MMC_RESPONSE_DATA, len(body), body))

    def send_log_status(self, status):
        """
        C++: void SendLogStatus(const AS_LOG_STATUS_T* Status)
        """
        body = status.pack()
        self.packet_send(PacketT(AS_LOG_INFO, len(body), body))

    def receive_cmd_log_status_change(self, log_ctl):
        """
        C++: void ReceiveCmdLogStatusChange(AS_CMD_LOG_CONTROL_T* LogCtl)
        """
        from ParserWorld import ParserWorld
        world = ParserWorld.get_instance()
        
        # ChangeLogStatus returns updated status, which is then sent back
        new_status = world.change_log_status(log_ctl)
        self.send_log_status(new_status)

    def send_ascii_error(self, priority, err_msg_str):
        """
        C++: void SendAsciiError(int Priority, char* ErrMsg)
        """
        from ParserWorld import ParserWorld
        world = ParserWorld.get_instance()

        err = AsAsciiErrorMsgT()
        err.Priority = priority
        err.ProcessId = world.get_proc_name()
        err.ProcessType = ASCII_PARSER
        err.ErrMsg = err_msg_str

        body = err.pack()
        self.packet_send(PacketT(ASCII_ERROR_MSG, len(body), body))