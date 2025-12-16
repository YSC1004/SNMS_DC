import sys
import os
import copy

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 부모 클래스 임포트 (SockMgrConnMgr)
from Class.Common.SockMgrConnMgr import SockMgrConnMgr
from Class.ProcNaServer.RuleDownLoaderConnection import RuleDownLoaderConnection
from Class.Common.CommType import *

class RuleDownLoaderConnMgr(SockMgrConnMgr):
    """
    Manages the connection to the Rule Downloader process.
    Handles rule download commands, process status, and log status updates.
    Inherits from SockMgrConnMgr for socket management capabilities.
    """
    def __init__(self):
        """
        C++: RuleDownLoaderConnMgr::RuleDownLoaderConnMgr()
        """
        super().__init__()
        self.m_RuleDownLoaderConnection = None
        
        # Key: Name (str), Value: AsLogStatusT
        self.m_LogStatusMap = {}

    def __del__(self):
        """
        C++: RuleDownLoaderConnMgr::~RuleDownLoaderConnMgr()
        """
        self.m_LogStatusMap.clear()
        super().__del__()

    def process_dead(self, name, pid, status):
        """
        C++: void ProcessDead(string Name, int Pid, int Status)
        """
        self.send_process_info(name, STOP)
        
        if status == ORDER_KILL:
            pass
        else:
            self.m_RuleDownLoaderConnection = None
            from Server.AsciiServerWorld import AsciiServerWorld
            AsciiServerWorld._instance.process_dead(name, pid)

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        Overridden to create RuleDownLoaderConnection.
        """
        con = RuleDownLoaderConnection(self)

        if not self.accept(con):
            print(f"[RuleDownLoaderConnMgr] RuleDownLoaderConnMgr Socket Accept Error : {self.get_obj_err_msg()}")
            con.close()
            return

        self.add(con)

    def send_cmd_parsing_rule_down(self):
        """
        C++: void SendCmdParsingRuleDown()
        """
        if self.m_RuleDownLoaderConnection:
            self.m_RuleDownLoaderConnection.send_cmd_parsing_rule_down()

    def send_cmd_mapping_rule_down(self):
        """
        C++: void SendCmdMappingRuleDown()
        """
        if self.m_RuleDownLoaderConnection:
            self.m_RuleDownLoaderConnection.send_cmd_mapping_rule_down()

    def set_rule_down_conn(self, con):
        """
        C++: void SetRuleDownConn(RuleDownLoaderConnection* Con)
        """
        self.m_RuleDownLoaderConnection = con

    def recv_rule_down_ack(self, ack):
        """
        C++: void RecvRuleDownAck(AS_ASCII_ACK_T* Ack)
        """
        from Server.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.recv_parsing_rule_down_result(ack)

    def recv_mapping_rule_down_ack(self, ack):
        """
        C++: void RecvMappingRuleDownAck(AS_ASCII_ACK_T* Ack)
        """
        from Server.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.recv_mapping_rule_down_result(ack)

    def send_process_info(self, session_name, status):
        """
        C++: void SendProcessInfo(const char* SessionName, int Status)
        """
        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        
        proc_info = AsProcessStatusT()
        proc_info.ProcessId = session_name
        proc_info.Status = status

        if proc_info.Status == START:
            if not self.get_process_info(session_name, proc_info):
                return

        proc_info.ManagerId = world.get_proc_name()
        proc_info.ProcessType = ASCII_RULE_DOWNLOADER
        
        world.update_process_info(proc_info)

    def update_process_log_status(self, status):
        """
        C++: void UpdateProcessLogStatus(AS_LOG_STATUS_T* Status)
        """
        if status.name in self.m_LogStatusMap:
            del self.m_LogStatusMap[status.name]

        if status.status == LOG_ADD:
            self.m_LogStatusMap[status.name] = copy.deepcopy(status)

        from Server.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.send_log_status(status)

    def get_log_status_list(self, status_list):
        """
        C++: void GetLogStatusList(LogStatusVector* StatusList)
        """
        for status in self.m_LogStatusMap.values():
            status_list.append(status)

    def get_process_info(self, session_name, proc_info):
        """
        Helper method to fill process info (PID, StartTime).
        Should be implemented similarly to other ConnMgrs.
        """
        from datetime import datetime
        proc_info.StartTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        proc_info.Pid = 0 # Replace with actual PID lookup if needed
        return True