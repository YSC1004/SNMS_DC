import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.ConnectionMgr import ConnectionMgr
from Class.ProcNaServer.GuiConnection import GuiConnection
from Class.Common.CommType import *

# -------------------------------------------------------
# GuiConnMgr Class
# GUI 연결 관리 및 브로드캐스팅
# -------------------------------------------------------
class GuiConnMgr(ConnectionMgr):
    def __init__(self):
        """
        C++: GuiConnMgr()
        """
        super().__init__()
        
        # Rule Download Request Connection Trackers
        self.m_ParsingRuleDownReqCon = None
        self.m_MappingRuleDownReqCon = None
        self.m_SchedulerRuleDownReqCon = None
        self.m_CommandRuleDownReqCon = None

    def __del__(self):
        """
        C++: ~GuiConnMgr()
        """
        super().__del__()

    # ---------------------------------------------------
    # Override Methods
    # ---------------------------------------------------
    def accept_socket(self):
        """
        C++: void AcceptSocket()
        """
        gui_conn = GuiConnection(self)

        if not self.accept(gui_conn):
            print(f"[GuiConnMgr] Gui Socket Accept Error : {self.get_obj_err_msg()}")
            return

        self.add(gui_conn)
        # print(f"[GuiConnMgr] Connection Gui({gui_conn.get_peer_ip()})")
        
    def send_log_status(self, status):
        """
        C++: void SendLogStatus(const AS_LOG_STATUS_T* Status)
        접속된 GUI(Status Info) 클라이언트들에게 로그 상태 브로드캐스팅
        """
        from Class.Common.CommType import GUI_ASCII_STATUS_INFO

        # 리스트를 순회하는 도중에 삭제(Remove)가 일어날 수 있으므로,
        # 원본 리스트의 복사본([:])을 사용하여 안전하게 순회합니다.
        for gui_con in self.m_SocketConnectionList[:]:
            
            # 세션 타입 확인 (GuiConnection의 멤버 변수 혹은 메서드 사용)
            if gui_con.m_SessionIdentify == GUI_ASCII_STATUS_INFO:
                
                # 전송 시도 (GuiConnection.send_log_status 호출)
                if not gui_con.send_log_status(status):
                    # 전송 실패 시 연결 관리자에서 제거
                    self.remove(gui_con)

    def send_ascii_error(self, err_msg):
        """
        C++: void SendAsciiError(AS_ASCII_ERROR_MSG_T* ErrMsg)
        에러 메시지를 GUI(Status Info) 클라이언트들에게 브로드캐스팅
        """
        from Class.Common.CommType import GUI_ASCII_STATUS_INFO

        # 리스트 순회 중 삭제가 발생할 수 있으므로 복사본([:])을 사용
        for gui_con in self.m_SocketConnectionList[:]:
            
            # 1. 세션 타입 확인 (Status Info만 대상)
            if gui_con.m_SessionIdentify == GUI_ASCII_STATUS_INFO:
                
                # 2. 에러 메시지 전송 (GuiConnection.send_ascii_error 호출)
                if not gui_con.send_ascii_error(err_msg):
                    # 전송 실패 시 연결 제거
                    self.remove(gui_con)
                    
    # ---------------------------------------------------
    # Rule Download Commands
    # ---------------------------------------------------
    def cmd_parsing_rule_down(self, req_con):
        """
        C++: void CmdParsingRuleDown(GuiConnection* ParsingRuleDownReqCon)
        """
        self.m_ParsingRuleDownReqCon = req_con
        print(f"[GuiConnMgr] Rule Down Request({req_con.get_peer_ip()})")
        
        from AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.cmd_parsing_rule_down()

    def recv_parsing_rule_down_result(self, ack):
        """
        C++: void RecvParsingRuleDownResult(AS_ASCII_ACK_T* Ack)
        """
        print("[GuiConnMgr] Send Parsing Rule Down Result to GUI")
        if self.m_ParsingRuleDownReqCon and self.is_valid_connection(self.m_ParsingRuleDownReqCon):
            # SendPacket(CMD_PARSING_RULE_DOWN_ACK, ...)
            body = ack.pack()
            self.m_ParsingRuleDownReqCon.packet_send(PacketT(CMD_PARSING_RULE_DOWN_ACK, len(body), body))
            
        self.m_ParsingRuleDownReqCon = None

    # ... (Mapping, Scheduler, Command Rule Down - Same Pattern) ...
    # 간소화를 위해 패턴이 동일한 나머지 Rule Down 함수들은 생략했습니다. 
    # 필요 시 위와 동일하게 구현하면 됩니다.

    def remove_request_conn(self, conn):
        """
        C++: void RemoveRequestConn(GuiConnection* Conn)
        연결이 끊어진 세션이 요청 대기 중이던 세션이면 참조 제거
        """
        if self.m_ParsingRuleDownReqCon == conn: self.m_ParsingRuleDownReqCon = None
        if self.m_MappingRuleDownReqCon == conn: self.m_MappingRuleDownReqCon = None
        if self.m_SchedulerRuleDownReqCon == conn: self.m_SchedulerRuleDownReqCon = None
        if self.m_CommandRuleDownReqCon == conn: self.m_CommandRuleDownReqCon = None

    # ---------------------------------------------------
    # Broadcast Info Change
    # ---------------------------------------------------
    def send_info_change(self, info):
        """
        C++: void SendInfoChange(Type* Info) (Overloaded methods combined)
        정보 변경 사항을 구독 중인 GUI 세션들에게 브로드캐스팅
        """
        from Class.Common.CommType import (
            # Message IDs
            AS_CONNECTION_INFO, AS_CONNECTOR_INFO, AS_MANAGER_INFO,
            AS_PROCESS_INFO, AS_DATA_HANDLER_INFO, AS_COMMAND_AUTHORITY_INFO,
            AS_SYSTEM_INFO, AS_SESSION_CFG, AS_SUB_PROC_INFO,
            # Session Types
            GUI_ASCII_STATUS_INFO, GUI_ASCII_CONFIG_INFO,
            # Data Structures
            AsConnectionInfoT, AsConnectorInfoT, AsManagerInfoT,
            AsProcessStatusT, AsDataHandlerInfoT, AsCommandAuthorityInfoT,
            AsSystemInfoT, AsSessionCfgT, AsSubProcInfoT,
            PacketT
        )

        msg_id = 0
        target_sessions = []

        # -------------------------------------------------------
        # 1. 객체 타입에 따른 MsgId 및 전송 대상 세션 설정
        # -------------------------------------------------------
        if isinstance(info, AsConnectionInfoT):
            msg_id = AS_CONNECTION_INFO
            target_sessions = [GUI_ASCII_STATUS_INFO, GUI_ASCII_CONFIG_INFO]
            
        elif isinstance(info, AsConnectorInfoT):
            msg_id = AS_CONNECTOR_INFO
            target_sessions = [GUI_ASCII_STATUS_INFO, GUI_ASCII_CONFIG_INFO]
            
        elif isinstance(info, AsManagerInfoT):
            msg_id = AS_MANAGER_INFO
            target_sessions = [GUI_ASCII_STATUS_INFO, GUI_ASCII_CONFIG_INFO]
            
        elif isinstance(info, AsProcessStatusT):
            msg_id = AS_PROCESS_INFO
            target_sessions = [GUI_ASCII_STATUS_INFO] # Only Status Info
            
        elif isinstance(info, AsDataHandlerInfoT):
            msg_id = AS_DATA_HANDLER_INFO
            target_sessions = [GUI_ASCII_STATUS_INFO, GUI_ASCII_CONFIG_INFO]
            
        elif isinstance(info, AsCommandAuthorityInfoT):
            msg_id = AS_COMMAND_AUTHORITY_INFO
            target_sessions = [GUI_ASCII_STATUS_INFO, GUI_ASCII_CONFIG_INFO]
            
        elif isinstance(info, AsSystemInfoT):
            msg_id = AS_SYSTEM_INFO
            target_sessions = [GUI_ASCII_STATUS_INFO] # Only Status Info
            
        elif isinstance(info, AsSessionCfgT):
            msg_id = AS_SESSION_CFG
            target_sessions = [GUI_ASCII_STATUS_INFO] # Only Status Info
            
        elif isinstance(info, AsSubProcInfoT):
            msg_id = AS_SUB_PROC_INFO
            target_sessions = [GUI_ASCII_STATUS_INFO, GUI_ASCII_CONFIG_INFO]

        else:
            print(f"[GuiConnMgr] Unknown Info Type: {type(info)}")
            return

        # -------------------------------------------------------
        # 2. 브로드캐스팅 (Safe Iteration)
        # -------------------------------------------------------
        # 리스트 순회 중 Remove 발생 가능하므로 복사본([:]) 사용
        for gui_con in self.m_SocketConnectionList[:]:
            
            # 세션 타입 체크 (구독 권한 확인)
            if gui_con.m_SessionIdentify in target_sessions:
                
                # 패킷 생성
                body = info.pack()
                packet = PacketT(msg_id, len(body), body)
                
                # 전송 시도
                if not gui_con.packet_send(packet):
                    # 전송 실패 시 연결 제거 (C++의 Remove 로직)
                    self.remove(gui_con)

    # ---------------------------------------------------
    # Log & Error Broadcast
    # ---------------------------------------------------
    def send_log_status(self, status):
        # AS_LOG_STATUS_T
        for socket in self.m_SocketConnectionList[:]:
            if socket.m_SessionIdentify == GUI_ASCII_STATUS_INFO:
                # GuiConnection.send_log_status 호출
                if not socket.send_log_status(status):
                    self.remove(socket)

    def send_ascii_error(self, err_msg):
        # AS_ASCII_ERROR_MSG_T
        for socket in self.m_SocketConnectionList[:]:
            if socket.m_SessionIdentify == GUI_ASCII_STATUS_INFO:
                # AsSocket.send_packet (NonBlock) 호출
                body = err_msg.pack()
                # C++: SendNonBlockPacket -> Python에서는 일반 send 사용 (비동기 I/O 복잡성 회피)
                if not socket.packet_send(PacketT(ASCII_ERROR_MSG, len(body), body)):
                    self.remove(socket)
                    
    # ---------------------------------------------------
    # Command & Scheduler Rule Down Handlers
    # ---------------------------------------------------
    def cmd_command_rule_down(self, req_con):
        """
        C++: void CmdCommandRuleDown(GuiConnection* CommandRuleDownReqCon)
        """
        self.m_CommandRuleDownReqCon = req_con
        
        from AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.cmd_command_rule_down()

    def recv_command_rule_down_result(self, ack):
        """
        C++: void RecvCommandRuleDownResult(AS_ASCII_ACK_T* Ack)
        결과를 요청한 GUI 세션에게 전송
        """
        print("[GuiConnMgr] Send Command Rule Down Result to GUI")
        if self.m_CommandRuleDownReqCon and self.is_valid_connection(self.m_CommandRuleDownReqCon):
            body = ack.pack()
            self.m_CommandRuleDownReqCon.packet_send(PacketT(CMD_COMMAND_RULE_DOWN_ACK, len(body), body))
        
        self.m_CommandRuleDownReqCon = None

    def cmd_scheduler_rule_down(self, req_con):
        """
        C++: void CmdSchedulerRuleDonw(GuiConnection* SchedulerRuleDownReqCon)
        """
        self.m_SchedulerRuleDownReqCon = req_con
        
        from AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.cmd_scheduler_rule_down()

    def recv_scheduler_rule_down_result(self, ack):
        """
        C++: void RecvSchedulerRuleDownResult(AS_ASCII_ACK_T* Ack)
        """
        print("[GuiConnMgr] Send Scheduler RuleDown Result to GUI")
        if self.m_SchedulerRuleDownReqCon and self.is_valid_connection(self.m_SchedulerRuleDownReqCon):
            body = ack.pack()
            self.m_SchedulerRuleDownReqCon.packet_send(PacketT(CMD_SCHEDULER_RULE_DOWN_ACK, len(body), body))
            
        self.m_SchedulerRuleDownReqCon = None
        
    # ... (기존 Rule Down 핸들러 아래에 추가) ...

    def cmd_mapping_rule_down(self, req_con):
        """
        C++: void CmdMappingRuleDown(GuiConnection* MappingRuleDownReqCon)
        """
        self.m_MappingRuleDownReqCon = req_con
        
        from AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.cmd_mapping_rule_down()

    def recv_mapping_rule_down_result(self, ack):
        """
        C++: void RecvMappingRuleDownResult(AS_ASCII_ACK_T* Ack)
        """
        print("[GuiConnMgr] Send MappingRuleDown Result to GUI")
        if self.m_MappingRuleDownReqCon and self.is_valid_connection(self.m_MappingRuleDownReqCon):
            body = ack.pack()
            self.m_MappingRuleDownReqCon.packet_send(PacketT(CMD_MAPPING_RULE_DOWN_ACK, len(body), body))
            
        self.m_MappingRuleDownReqCon = None