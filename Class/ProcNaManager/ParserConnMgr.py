import sys
import os
import threading

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Try importing parent class based on availability
from Class.Common.SockMgrConnMgr import SockMgrConnMgr
from Class.ProcNaManager.ParserConnection import ParserConnection
from Class.Common.CommType import *
from Class.Common.AsUtil import AsUtil

class ParserConnMgr(SockMgrConnMgr):
    """
    Manages connections to Parser processes.
    Handles broadcasting rules, syncing DataHandler info, and routing commands.
    """
    def __init__(self):
        """
        C++: ParserConnMgr::ParserConnMgr()
        """
        super().__init__()
        self.m_SocketRemoveLock = threading.Lock()

    def __del__(self):
        """
        C++: ParserConnMgr::~ParserConnMgr()
        """
        super().__del__()

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        """
        parser_conn = ParserConnection(self)

        if not self.accept(parser_conn):
            print(f"[ParserConnMgr] Parser Socket Accept Error : {self.get_obj_err_msg()}")
            parser_conn.close()
            return

        self.add(parser_conn)

    def send_router_conn_info(self, router_name):
        """
        C++: void SendRouterConnInfo(string RouterName)
        (C++ source has this commented out, implemented here for reference)
        """
        # print(f"[ParserConnMgr] SendRouterConnInfo : {router_name}")
        # from AsciiManagerWorld import AsciiManagerWorld
        # world = AsciiManagerWorld._instance
        # socket_path = world.get_router_listen_socket_path("Router")
        
        # open_port = AsCmdOpenPortT()
        # open_port.ProtocolType = ROUTER_CONNECT
        # open_port.PortPath = socket_path
        
        # self.send_all_cmd_open_port_info(open_port)
        pass

    def parser_start(self, conn):
        """
        C++: void ParserStart(ParserConnection* Conn)
        Called when Parser finishes initialization.
        Syncs DataHandler info to the new Parser.
        """
        from AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance

        # 1. Update Process Status in World
        if world.set_parser_proc_status(conn.get_session_name()):
            # 2. Send all DataHandler Info to the Parser
            info_map = world.get_data_handler_info_map()
            
            for info in info_map.values():
                body = info.pack()
                # C++: if(!Conn->SendPacket(...)) return;
                if not conn.packet_send(PacketT(AS_DATA_HANDLER_INFO, len(body), body)):
                    return

    def send_data_handler_info(self, info):
        """
        C++: void SendDataHandlerInfo(AS_DATA_HANDLER_INFO_T* Info)
        Broadcasts DataHandler info update to ALL Parsers.
        """
        body = info.pack()
        
        # Iterate all connections and send
        for conn in self.m_SocketConnectionList:
            conn.packet_send(PacketT(AS_DATA_HANDLER_INFO, len(body), body))

    def process_dead(self, name, pid, status):
        """
        C++: void ProcessDead(string Name, int Pid, int Status)
        """
        self.send_process_info(name, STOP)

        from AsciiManagerWorld import AsciiManagerWorld
        world = AsciiManagerWorld._instance

        if status == ORDER_KILL:
            world.remove_pid(pid)
            world.send_ascii_error(1, f"{name} is killed normally.")
        else:
            world.process_dead(ASCII_PARSER, name, pid)

    def send_response_command(self, session_name, mmc_com):
        """
        C++: bool SendResponseCommand(const char* SessionName, AS_MMC_PUBLISH_T* MMCCom)
        Routes MMC response to the specific Parser that requested it.
        """
        with self.m_SocketRemoveLock:
            con = self.find_session(session_name)
            
            if con is None:
                # print(f"[ParserConnMgr] Can't Find Parser : {session_name}")
                return False
            
            # C++: con->SendResponseCommand(MMCCom)
            con.send_response_command(mmc_com)
            return True

    def socket_remove_lock(self):
        """
        C++: void SocketRemoveLock()
        """
        self.m_SocketRemoveLock.acquire()

    def socket_remove_unlock(self):
        """
        C++: void SocketRemoveUnLock()
        """
        self.m_SocketRemoveLock.release()

    def stop_process(self, session_name):
        """
        C++: bool StopProcess(string SessionName)
        """
        con = self.find_session(session_name)
        
        if con is None:
            print(f"[ParserConnMgr] Can't Find Parser : {session_name}")
            return False

        con.stop_process()
        
        # Physical kill via ProcConnectionMgr (or World helper)
        # return ProcConnectionMgr.stop_process(session_name)
        return True

    def send_process_info(self, session_name, status):
        """
        C++: void SendProcessInfo(const char* SessionName, int Status)
        """
        proc_info = AsProcessStatusT()
        proc_info.ProcessId = session_name
        proc_info.Status = status
        proc_info.ProcessType = ASCII_PARSER

        if proc_info.Status == START:
            if not self.get_process_info(session_name, proc_info):
                return

        from AsciiManagerWorld import AsciiManagerWorld
        AsciiManagerWorld._instance.send_process_info(proc_info)

    def send_cmd_rule_down(self):
        """
        C++: void SendCmdRuleDown()
        Broadcasts Rule Down command.
        """
        for conn in self.m_SocketConnectionList:
            conn.send_cmd_rule_down()

    def send_cmd_mapping_rule_down(self):
        """
        C++: void SendCmdMappingRuleDown()
        Broadcasts Mapping Rule Down command.
        """
        for conn in self.m_SocketConnectionList:
            conn.send_cmd_mapping_rule_down()

    def parser_rule_change(self, change_info):
        """
        C++: void ParserRuleChange(AS_RULE_CHANGE_INFO_T* ChangeInfo)
        Sends rule change command to a SPECIFIC Parser.
        """
        with self.m_SocketRemoveLock:
            con = self.find_session(change_info.ProcessId)
            
            if con is None:
                print(f"[ParserConnMgr] Can't Find Parser : {change_info.ProcessId}")
                return
            
            con.parser_rule_change(change_info)

    # -------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------
    def find_session(self, session_name):
        for conn in self.m_SocketConnectionList:
            if conn.get_session_name() == session_name:
                return conn
        return None

    def get_process_info(self, session_name, proc_info):
        from datetime import datetime
        proc_info.StartTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        proc_info.Pid = 0
        return True