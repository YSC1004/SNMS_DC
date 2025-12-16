import sys
import os
import signal
import copy

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

class ServerConnection(AsSocket):
    """
    Handles the upstream connection to the Main Server (Active/Standby).
    Receives control commands and sends status updates/results.
    """
    def __init__(self, parent_mgr):
        """
        C++: ServerConnection() (Managed manually in World, not via ConnMgr usually)
        """
        super().__init__()
        self.m_ParentMgr = parent_mgr # Usually None or passed for structure

    def __del__(self):
        """
        C++: ~ServerConnection()
        """
        super().__del__()

    def receive_packet(self, packet, session_identify=0):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        msg_id = packet.msg_id
        
        from Server.AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance

        if msg_id == CMD_OPEN_PORT:
            info = AsCmdOpenPortT.unpack(packet.msg_body)
            if info: self.recv_cmd_open_port_req(info)

        elif msg_id == CMD_MMC_PUBLISH_REQ:
            mmc_pub = AsMmcPublishT.unpack(packet.msg_body)
            if mmc_pub: self.receive_mmc_command(mmc_pub)

        elif msg_id == CMD_LOG_STATUS_CHANGE:
            log_ctl = AsCmdLogControlT.unpack(packet.msg_body)
            if log_ctl: self.receive_cmd_log_status_change(log_ctl)

        elif msg_id == PROC_CONTROL:
            proc_ctl = AsProcControlT.unpack(packet.msg_body)
            if proc_ctl: world.recv_process_control(proc_ctl)

        elif msg_id == SESSION_CONTROL:
            sess_ctl = AsSessionControlT.unpack(packet.msg_body)
            if sess_ctl: world.recv_session_control(sess_ctl)

        elif msg_id == CMD_PROC_TERMINATE:
            print("[ServerConnection] RECV CMD_PROC_TERMINATE..............")
            self.close_socket(0)
            return

        elif msg_id == CMD_PARSING_RULE_DOWN:
            world.recv_cmd_parsing_rule_down()

        elif msg_id == CMD_MAPPING_RULE_DOWN:
            world.recv_cmd_mapping_rule_down()

        elif msg_id == CMD_PARSING_RULE_CHANGE:
            info = AsRuleChangeInfoT.unpack(packet.msg_body)
            if info: world.parser_rule_change(info)

        elif msg_id == AS_DATA_HANDLER_INFO:
            info = AsDataHandlerInfoT.unpack(packet.msg_body)
            if info: world.recv_data_handler_info(info)

        elif msg_id == AS_DATA_ROUTING_INIT:
            info = AsDataRoutingInitT.unpack(packet.msg_body)
            if info: world.recv_init_info(info)

        else:
            print(f"[ServerConnection] Unknown Msg Id : {msg_id}")

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        If the server connection breaks, the Manager process terminates itself
        to allow HA or restart mechanisms to take over.
        """
        print("[ServerConnection] [CORE_ERROR] Server Connection Broken")
        # C++: kill(getpid(), SIGINT)
        os.kill(os.getpid(), signal.SIGINT)

    def connector_port_info_request(self, connector_name):
        """
        C++: void ConnectorPortInfoRequest(string ConnectorName)
        """
        req = AsConnectorPortInfoReqT()
        req.ConnectorId = connector_name
        
        print(f"[ServerConnection] Send ConnectorPortInfoReq : {connector_name}")
        
        body = req.pack()
        self.packet_send(PacketT(CONNECTOR_PORT_INFO_REQ, len(body), body))

    def recv_cmd_open_port_req(self, port_info):
        """
        C++: void RecvCmdOpenPortReq(AS_CMD_OPEN_PORT_T* PortInfo)
        """
        from Server.AsciiManagerWorld import AsciiManagerWorld
        AsciiManagerWorld._instance.send_cmd_open_info(port_info)

    def receive_mmc_command(self, mmc_com):
        """
        C++: void ReceiveMMCCommand(AS_MMC_PUBLISH_T* MMCCom)
        """
        from Server.AsciiManagerWorld import AsciiManagerWorld
        AsciiManagerWorld._instance.send_mmc_command(mmc_com)

    def send_command_response(self, mmc_result):
        """
        C++: void SendCommandResponse(AS_MMC_RESULT_T* MmcResult)
        """
        body = mmc_result.pack()
        self.packet_send(PacketT(CMD_MMC_PUBLISH_RES, len(body), body))

    def send_log_status(self, status):
        """
        C++: void SendLogStatus(AS_LOG_STATUS_T* Status)
        """
        # C++ comment: not use
        # body = status.pack()
        # self.packet_send(PacketT(AS_LOG_INFO, len(body), body))
        pass

    def receive_cmd_log_status_change(self, log_ctl):
        """
        C++: void ReceiveCmdLogStatusChange(AS_CMD_LOG_CONTROL_T* LogCtl)
        """
        from Server.AsciiManagerWorld import AsciiManagerWorld
        AsciiManagerWorld._instance.receive_cmd_log_status_change(log_ctl)

    def send_ascii_error(self, err_msg):
        """
        C++: void SendAsciiError(AS_ASCII_ERROR_MSG_T* ErrMsg)
        """
        from Server.AsciiManagerWorld import AsciiManagerWorld
        # Set ManagerId before sending
        err_msg.ManagerId = AsciiManagerWorld._instance.get_proc_name()
        
        body = err_msg.pack()
        self.packet_send(PacketT(ASCII_ERROR_MSG, len(body), body))

    def send_process_info_list(self, proc_info_list):
        """
        C++: void SendProcessInfo(ProcessInfoList* ProcInfoList)
        Chunks the list into PROCESS_STATUS_LIST_MAX blocks and sends them.
        """
        # PROCESS_STATUS_LIST_MAX is defined in CommType, assume e.g., 50
        
        chunk_size = PROCESS_STATUS_LIST_MAX - 2 # Logic from C++: if pos > MAX-2
        
        # In Python, we can simply chunk the list
        for i in range(0, len(proc_info_list), chunk_size):
            chunk = proc_info_list[i : i + chunk_size]
            
            proc_status_list = AsProcessStatusListT()
            proc_status_list.ProcStatusNo = len(chunk)
            proc_status_list.ProcStatus = chunk # List of AsProcessStatusT
            
            # Pad with dummy if strict struct packing is used, 
            # or AsProcessStatusListT.pack() handles variable length.
            # Assuming CommType handles it.
            
            body = proc_status_list.pack()
            self.packet_send(PacketT(PROCESS_INFO_LIST, len(body), body))

        print(f"[ServerConnection] Process Info List Send Success(cnt : {len(proc_info_list)})")

    def send_process_info(self, proc_info):
        """
        C++: void SendProcessInfo(AS_PROCESS_STATUS_T* ProcInfo)
        """
        body = proc_info.pack()
        self.packet_send(PacketT(PROCESS_INFO, len(body), body))

    def send_port_info(self, status_info):
        """
        C++: void SendPortInfo(AS_PORT_STATUS_INFO_T* StatusInfo)
        """
        body = status_info.pack()
        self.packet_send(PacketT(PORT_STATUS_INFO, len(body), body))