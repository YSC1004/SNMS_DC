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

class DataRouterConnection(AsSocket):
    """
    Handles connection with DataRouter process (ASCII_DATA_ROUTER).
    Manages socket paths, connection to DataHandler, and lifecycle monitoring.
    """
    def __init__(self, conn_mgr):
        """
        C++: DataRouterConnection(DataRouterConnMgr* ConMgr)
        """
        super().__init__()
        self.m_DataRouterConnMgr = conn_mgr
        self.m_DataRouterStatus = True

    def __del__(self):
        """
        C++: ~DataRouterConnection()
        """
        super().__del__()

    def receive_packet(self, packet, session_identify):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        if session_identify == ASCII_DATA_ROUTER:
            self.data_router_proc_req(packet)
        else:
            print(f"[DataRouterConnection] UnKnown Session : {session_identify}")

    def data_router_proc_req(self, packet):
        """
        C++: void DataRouterProcReq(PACKET_T* Packet)
        """
        msg_id = packet.msg_id
        from Server.AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance

        if msg_id == CMD_OPEN_PORT_ACK:
            ack = AsAsciiAckT.unpack(packet.msg_body)
            if ack: self.cmd_open_port_ack(ack)

        elif msg_id == AS_LOG_INFO:
            status = AsLogStatusT.unpack(packet.msg_body)
            if status: world.send_log_status(status)

        elif msg_id == ASCII_ERROR_MSG:
            error = AsAsciiErrorMsgT.unpack(packet.msg_body)
            if error: world.send_ascii_error(error)

        elif msg_id == PROC_INIT_END:
            pass

        else:
            print(f"[DataRouterConnection] [CORE_ERROR] Unknown Msg Id : {msg_id}")

    def session_identify(self, session_type, session_name):
        """
        C++: void SessionIdentify(int SessionType, string SessionName)
        This is critical: It tells the DataRouter where to listen (Unix Socket)
        and where to connect (DataHandler IP/Port).
        """
        if not self.m_DataRouterConnMgr.add_session_name(session_name):
            self.close()
            self.m_DataRouterConnMgr.remove(self)
            return

        print(f"[DataRouterConnection] SessionType : {AsUtil.get_process_type_string(session_type)}, SessionName : {session_name}")

        self.m_DataRouterConnMgr.send_process_info(self.get_session_name(), START)

        from Server.AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance

        # 1. Send DATAROUTER_LISTEN info (Unix Domain Socket)
        open_port = AsCmdOpenPortT()
        open_port.ProtocolType = DATAROUTER_LISTEN
        open_port.Name = session_name
        
        socket_path = world.get_data_router_listen_socket_path(self.get_session_name())
        open_port.PortPath = socket_path
        
        self.cmd_open_port_info(open_port)

        # 2. Send DATAHANDLER_CONNECT info (TCP Connection to DataHandler)
        info = world.get_data_handler_info(session_name)
        
        if info:
            open_port_con = AsCmdOpenPortT()
            open_port_con.ProtocolType = DATAHANDLER_CONNECT
            open_port_con.Consumer = info.DataHandlerId
            open_port_con.IpAddress = info.IpAddress
            open_port_con.PortNo = info.ListenPort
            
            self.cmd_open_port_info(open_port_con)
        else:
            print(f"[DataRouterConnection] [WARNING] Can't find DataHandler info for {session_name}")

        # Start Alive Check
        self.start_alive_check(world.get_proc_alive_check_time(), world.get_alive_check_limit_cnt())

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        """
        print(f"[DataRouterConnection] Socket Broken SessionName : {self.get_session_name()}")
        self.send_log_status()

        if self.m_DataRouterStatus:
            self.m_DataRouterConnMgr.child_process_dead(self)
        else:
            self.m_DataRouterConnMgr.child_process_dead(self, ORDER_KILL)

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
        print(f"[DataRouterConnection] Unknown Time Out Reason : {reason}")

    def alive_check_fail(self, fail_count):
        """
        C++: void AliveCheckFail(int FailCount)
        """
        print(f"[DataRouterConnection] Alive Check Fail(count : {fail_count}) Limite Over")
        
        from Server.AsciiManagerWorld import AsciiManagerWorld
        msg = f"The process is killed on purpose for no reply from {self.get_session_name()}."
        AsciiManagerWorld._instance.send_ascii_error(1, msg)
        
        self.m_DataRouterConnMgr.various_ack_check_time_out(self)

    def cmd_open_port_ack(self, ack):
        """
        C++: void CmdOpenPortAck(AS_ASCII_ACK_T* Ack)
        """
        print(f"[DataRouterConnection] Receive CmdOpenPortAck : {self.get_session_name()}, MsgId : {ack.Id}")

        if not ack.ResultMode:
            print(f"[DataRouterConnection] CmdOpen Error({self.get_session_name()}) : {ack.Result}")

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

    def stop_process(self):
        """
        C++: void StopProcess()
        """
        self.m_DataRouterStatus = False