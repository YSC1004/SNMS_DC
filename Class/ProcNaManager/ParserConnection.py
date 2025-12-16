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

class ParserConnection(AsSocket):
    """
    Handles connection with Parser processes (ASCII_PARSER).
    Manages socket path exchange, MMC routing, and lifecycle monitoring.
    """
    def __init__(self, conn_mgr):
        """
        C++: ParserConnection(ParserConnMgr* ConMgr)
        """
        super().__init__()
        self.m_ParserConnMgr = conn_mgr
        self.m_ParserStatus = True

    def __del__(self):
        """
        C++: ~ParserConnection()
        """
        super().__del__()

    def receive_packet(self, packet, session_identify):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        if session_identify == ASCII_PARSER:
            self.parser_proc_req(packet)
        else:
            print(f"[ParserConnection] UnKnown Session : {session_identify}")

    def parser_proc_req(self, packet):
        """
        C++: void ParserProcReq(PACKET_T* Packet)
        Dispatches incoming packets from the Parser process.
        """
        msg_id = packet.msg_id
        from Server.AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance

        if msg_id == CMD_OPEN_PORT_ACK:
            ack = AsAsciiAckT.unpack(packet.msg_body)
            if ack: self.cmd_open_port_ack(ack)

        elif msg_id == MMC_RESPONSE_DATA:
            res = AsMmcResultT.unpack(packet.msg_body)
            if res: self.receive_response_command(res)

        elif msg_id == AS_LOG_INFO:
            status = AsLogStatusT.unpack(packet.msg_body)
            if status: world.send_log_status(status)

        elif msg_id == ASCII_ERROR_MSG:
            error = AsAsciiErrorMsgT.unpack(packet.msg_body)
            if error: world.send_ascii_error(error)

        elif msg_id == PROC_INIT_END:
            self.m_ParserConnMgr.parser_start(self)

        else:
            print(f"[ParserConnection] Unknown Msg Id : {msg_id}")

    def session_identify(self, session_type, session_name):
        """
        C++: void SessionIdentify(int SessionType, string SessionName)
        Registers the session, determines the listening socket path, 
        and instructs the Parser to open that port.
        """
        if not self.m_ParserConnMgr.add_session_name(session_name):
            self.close()
            self.m_ParserConnMgr.remove(self)
            return

        print(f"[ParserConnection] SessionType : {AsUtil.get_process_type_string(session_type)}, SessionName : {session_name}")

        from Server.AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance

        # Prepare Open Port Command
        open_port = AsCmdOpenPortT()
        open_port.ProtocolType = PARSER_LISTEN
        
        # Get Socket Path from World
        socket_path = world.get_parser_listen_socket_path(self.get_session_name())
        print(f"[ParserConnection] socketPath : {socket_path}")
        
        open_port.PortPath = socket_path
        
        # Send Command
        self.cmd_open_port_info(open_port)

        # Notify Manager
        self.m_ParserConnMgr.send_process_info(self.get_session_name(), START)

        # Start Alive Check
        self.start_alive_check(world.get_proc_alive_check_time(), world.get_alive_check_limit_cnt())

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        """
        print(f"[ParserConnection] Socket Broken SessionName : {self.get_session_name()}")
        
        self.send_log_status()

        if self.m_ParserStatus:
            self.m_ParserConnMgr.child_process_dead(self)
        else:
            self.m_ParserConnMgr.child_process_dead(self, ORDER_KILL)

    def stop_process(self):
        """
        C++: void StopProcess()
        """
        self.m_ParserStatus = False

    def cmd_open_port_info(self, port_info):
        """
        C++: bool CmdOpenPortInfo(AS_CMD_OPEN_PORT_T* PortInfo)
        """
        body = port_info.pack()
        self.packet_send(PacketT(CMD_OPEN_PORT, len(body), body))
        return True

    def receive_time_out(self, reason, extra_reason=None):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        """
        print(f"[ParserConnection] [CORE_ERROR] Unknown Time Out Reason : {reason}")

    def cmd_open_port_ack(self, ack):
        """
        C++: void CmdOpenPortAck(AS_ASCII_ACK_T* Ack)
        """
        if not ack.ResultMode:
            print(f"[ParserConnection] CmdOpen Error({self.get_session_name()}) : {ack.Result}")

    def send_response_command(self, mmc_com):
        """
        C++: void SendResponseCommand(AS_MMC_PUBLISH_T* MMCCom)
        """
        body = mmc_com.pack()
        self.packet_send(PacketT(MMC_RESPONSE_DATA_REQ, len(body), body))

    def receive_response_command(self, mmc_result):
        """
        C++: void ReceiveResponseCommand(AS_MMC_RESULT_T* MmcResult)
        """
        print(f"[ParserConnection] Receive MMC Cmd Response : msgid({mmc_result.id}), resultMode({AsUtil.get_enum_type_string(mmc_result.resultMode)})")
        
        from Server.AsciiManagerWorld import AsciiManagerWorld
        AsciiManagerWorld._instance.send_command_response(mmc_result)

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

    def send_cmd_rule_down(self):
        """
        C++: void SendCmdRuleDown()
        """
        self.packet_send_msg(CMD_PARSING_RULE_DOWN)

    def send_cmd_mapping_rule_down(self):
        """
        C++: void SendCmdMappingRuleDown()
        """
        self.packet_send_msg(CMD_MAPPING_RULE_DOWN)

    def alive_check_fail(self, fail_count):
        """
        C++: void AliveCheckFail(int FailCount)
        """
        print(f"[ParserConnection] AliveCheckFail({self.get_session_name()}) , Count : {fail_count}")
        
        from Server.AsciiManagerWorld import AsciiManagerWorld
        msg = f"The Process is killed on purpose for no reply from {self.get_session_name()}."
        AsciiManagerWorld._instance.send_ascii_error(1, msg)
        
        self.m_ParserConnMgr.various_ack_check_time_out(self)

    def parser_rule_change(self, change_info):
        """
        C++: void ParserRuleChange(AS_RULE_CHANGE_INFO_T* ChangeInfo)
        """
        body = change_info.pack()
        self.packet_send(PacketT(CMD_PARSING_RULE_CHANGE, len(body), body))