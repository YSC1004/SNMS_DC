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

class ConnectorConnection(AsSocket):
    """
    Handles connection with Connector processes (ASCII_CONNECTOR).
    Manages port opening, MMC routing, and process monitoring.
    """
    def __init__(self, conn_mgr):
        """
        C++: ConnectorConnection(ConnectorConnMgr* ConMgr)
        """
        super().__init__()
        self.m_ConnectorConnMgr = conn_mgr
        self.m_ConnectorStatus = True

    def __del__(self):
        """
        C++: ~ConnectorConnection()
        """
        super().__del__()

    def receive_packet(self, packet, session_identify):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        if session_identify == ASCII_CONNECTOR:
            self.connector_proc_req(packet)
        else:
            print(f"[ConnectorConnection] UnKnown SessionType : {session_identify}")

    def session_identify(self, session_type, session_name):
        """
        C++: void SessionIdentify(int SessionType, string SessionName)
        """
        # Register session with Manager
        if not self.m_ConnectorConnMgr.add_session_name(session_name):
            self.close()
            self.m_ConnectorConnMgr.remove(self)
            return

        print(f"[ConnectorConnection] SessionType : {AsUtil.get_process_type_string(session_type)}, SessionName : {session_name}")

        # Notify Manager of Process Start
        self.m_ConnectorConnMgr.send_process_info(self.get_session_name(), START)

        # Start Alive Check
        from AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance
        self.start_alive_check(world.get_proc_alive_check_time(), world.get_alive_check_limit_cnt())

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Error)
        """
        print(f"[ConnectorConnection] Socket Broken SessionName : {self.get_session_name()}")

        # self.send_log_status() # C++ commented out
        
        if self.m_ConnectorStatus:
            self.m_ConnectorConnMgr.child_process_dead(self)
        else:
            self.m_ConnectorConnMgr.child_process_dead(self, ORDER_KILL)

    def stop_process(self):
        """
        C++: void StopProcess()
        """
        self.m_ConnectorStatus = False

    def cmd_open_port_info(self, port_info):
        """
        C++: bool CmdOpenPortInfo(AS_CMD_OPEN_PORT_T* PortInfo)
        Sends command to open a port on the connector.
        """
        body = port_info.pack()
        if not self.packet_send(PacketT(CMD_OPEN_PORT, len(body), body)):
            print(f"[ConnectorConnection] Connector Socket Broken : {self.get_session_name()}")
            return False
        return True

    def receive_time_out(self, reason, extra_reason=None):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        """
        print(f"[ConnectorConnection] [CORE_ERROR] Unknown Time Out Reason : {reason}")

    def connector_proc_req(self, packet):
        """
        C++: void ConnectorProcReq(PACKET_T* Packet)
        Dispatches requests received from the Connector process.
        """
        msg_id = packet.msg_id
        from AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance

        if msg_id == CMD_OPEN_PORT_ACK:
            ack = AsAsciiAckT.unpack(packet.msg_body)
            if ack: self.cmd_open_port_ack(ack)

        elif msg_id == PROC_INIT_END:
            self.m_ConnectorConnMgr.connector_init_end(self.get_session_name())

        elif msg_id == AS_LOG_INFO:
            status = AsLogStatusT.unpack(packet.msg_body)
            if status: world.send_log_status(status)

        elif msg_id == ASCII_ERROR_MSG:
            error = AsAsciiErrorMsgT.unpack(packet.msg_body)
            if error: world.send_ascii_error(error)

        elif msg_id == PORT_STATUS_INFO:
            status_info = AsPortStatusInfoT.unpack(packet.msg_body)
            if status_info: world.send_port_info(status_info)

        elif msg_id == MMC_RESPONSE_DATA:
            res = AsMmcResultT.unpack(packet.msg_body)
            if res: self.receive_response_command(res)

        else:
            print(f"[ConnectorConnection] [CORE_ERROR] Unknown Msg Id : {msg_id}")

    def cmd_open_port_ack(self, ack):
        """
        C++: void CmdOpenPortAck(AS_ASCII_ACK_T* Ack)
        """
        if not ack.ResultMode:
            # Error handling
            print(f"[ConnectorConnection] CmdOpen Error({self.get_session_name()}) : {ack.Result}")

    def send_mmc_command(self, mmc_com):
        """
        C++: bool SendMMCCommand(AS_MMC_PUBLISH_T* MMCCom)
        """
        body = mmc_com.pack()
        return self.packet_send(PacketT(CMD_MMC_PUBLISH_REQ, len(body), body))

    def send_log_status(self):
        """
        C++: void SendLogStatus()
        """
        log_status = AsLogStatusT()
        log_status.name = self.get_session_name()
        log_status.logs = f"{AsUtil.get_process_type_string(self.get_session_type())},{self.get_session_name()},"
        log_status.status = LOG_DEL
        
        from AsciiManagerWorld import AsciiManagerWorld
        AsciiManagerWorld._instance.send_log_status(log_status)

    def send_session_control(self, session_ctl):
        """
        C++: void SendSessionControl(AS_SESSION_CONTROL_T* SessionCtl)
        """
        body = session_ctl.pack()
        self.packet_send(PacketT(SESSION_CONTROL, len(body), body))

    def receive_response_command(self, mmc_result):
        """
        C++: void ReceiveResponseCommand(AS_MMC_RESULT_T* MmcResult)
        """
        print(f"[ConnectorConnection] Receive MMC Cmd Response From Connector({self.get_session_name()})")
        # print(f" msgid({mmc_result.id}), resultMode({mmc_result.resultMode})") # Debug log
        
        from AsciiManagerWorld import AsciiManagerWorld
        AsciiManagerWorld._instance.send_command_response(mmc_result)

    def alive_check_fail(self, fail_count):
        """
        C++: void AliveCheckFail(int FailCount)
        """
        print(f"[ConnectorConnection] AliveCheckFail({self.get_session_name()}) , Count : {fail_count}")
        
        from AsciiManagerWorld import AsciiManagerWorld
        msg = f"The process is killed on purpose for no reply from {self.get_session_name()}."
        AsciiManagerWorld._instance.send_ascii_error(1, msg)
        
        self.m_ConnectorConnMgr.various_ack_check_time_out(self)