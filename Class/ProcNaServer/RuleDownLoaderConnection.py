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

class RuleDownLoaderConnection(AsSocket):
    """
    Handles connection with RuleDownLoader process.
    Sends rule down commands and receives acknowledgments.
    """
    def __init__(self, conn_mgr):
        """
        C++: RuleDownLoaderConnection(RuleDownLoaderConnMgr* ConMgr)
        """
        super().__init__()
        self.m_RuleDownLoaderConnMgr = conn_mgr

    def __del__(self):
        """
        C++: ~RuleDownLoaderConnection()
        """
        super().__del__()

    def receive_packet(self, packet, session_identify):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        if session_identify == ASCII_RULE_DOWNLOADER:
            self.rule_down_loader_req(packet)
        else:
            print(f"[RuleDownLoaderConnection] UnKnown Session : {session_identify}")

    def session_identify(self, session_type, session_name):
        """
        C++: void SessionIdentify(int SessionType, string SessionName)
        """
        print(f"[RuleDownLoaderConnection] Session Identify : Type({AsUtil.get_process_type_string(session_type)}), SessionName({session_name})")

        if not self.m_RuleDownLoaderConnMgr.add_session_name(session_name):
            self.close()
            self.m_RuleDownLoaderConnMgr.remove(self)
            return

        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        
        # Alive Check Start
        self.start_alive_check(world.get_proc_alive_check_time(), world.get_alive_check_limit_cnt())
        
        # Notify Manager
        self.m_RuleDownLoaderConnMgr.send_process_info(session_name, START)
        self.m_RuleDownLoaderConnMgr.set_rule_down_conn(self)

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        """
        print(f"[RuleDownLoaderConnection] Socket Broken : {self.get_session_name()}")

        log_status = AsLogStatusT()
        log_status.name = self.get_session_name()
        log_status.status = LOG_DEL
        log_status.logs = f"sun,{AsUtil.get_process_type_string(self.get_session_type())},{self.get_session_name()},"

        # In C++, ChildProcessDead handles log update as well? 
        # C++ code doesn't call UpdateProcessLogStatus explicitly here, 
        # but sends logStatus struct via ... wait, it creates logStatus but doesn't use it?
        # Ah, ChildProcessDead might use it or it's dead code in C++.
        # Assuming ChildProcessDead needs the object, but C++ passed 'this'.
        
        self.m_RuleDownLoaderConnMgr.child_process_dead(self)

    def rule_down_loader_req(self, packet):
        """
        C++: void RuleDownLoaderReq(PACKET_T* Packet)
        """
        msg_id = packet.msg_id
        
        if msg_id == CMD_PARSING_RULE_DOWN_ACK:
            ack = AsAsciiAckT.unpack(packet.msg_body)
            if ack:
                self.m_RuleDownLoaderConnMgr.recv_rule_down_ack(ack)

        elif msg_id == CMD_MAPPING_RULE_DOWN_ACK:
            ack = AsAsciiAckT.unpack(packet.msg_body)
            if ack:
                self.m_RuleDownLoaderConnMgr.recv_mapping_rule_down_ack(ack)

        elif msg_id == AS_LOG_INFO:
            status = AsLogStatusT.unpack(packet.msg_body)
            if status:
                self.receive_log_info(status)

        else:
            print(f"[RuleDownLoaderConnection] Unknown Msg Id : {msg_id}")

    def send_cmd_parsing_rule_down(self):
        """
        C++: void SendCmdParsingRuleDown()
        """
        print("[RuleDownLoaderConnection] Send Rule Down Cmd")
        self.packet_send_msg(CMD_PARSING_RULE_DOWN)

    def send_cmd_mapping_rule_down(self):
        """
        C++: void SendCmdMappingRuleDown()
        """
        print("[RuleDownLoaderConnection] Send Mapping Rule Down Cmd")
        self.packet_send_msg(CMD_MAPPING_RULE_DOWN)

    def receive_log_info(self, status):
        """
        C++: void ReceiveLogInfo(AS_LOG_STATUS_T* Status)
        """
        self.m_RuleDownLoaderConnMgr.update_process_log_status(status)