import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.AsSocket import AsSocket
from Class.Common.CommType import *
from Class.Common.AsUtil import AsUtil
from Class.Common.AsciiServerType import *

# -------------------------------------------------------
# Constants
# -------------------------------------------------------
INIT_INFO_MANAGER_MASK              = 0x00000001
INIT_INFO_PROCESS_MASK              = 0x00000002
INIT_INFO_DATAHANDLER_MASK          = 0x00000004
INIT_INFO_COMMAND_AUTHORITY_MASK    = 0x00000008

# -------------------------------------------------------
# GuiConnection Class
# GUI 클라이언트와의 통신 담당
# -------------------------------------------------------
class GuiConnection(AsSocket):
    def __init__(self, conn_mgr):
        """
        C++: GuiConnection(GuiConnMgr* ConnMgr)
        """
        super().__init__()
        self.m_GuiConnMgr = conn_mgr

    def __del__(self):
        super().__del__()

    # ---------------------------------------------------
    # Packet Receiver
    # ---------------------------------------------------
    def receive_packet(self, packet, session_id):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        if session_id == GUI_RULE_EDITOR:
            self.rule_editor_req_process(packet)

        elif session_id in [GUI_ASCII_CONFIG_INFO, GUI_ASCII_STATUS_INFO]:
            self.gw_status_gui_req_process(packet)
            
        elif session_id == GUI_COMMAND_INFO:
            self.gw_command_gui_req_process(packet)
            
        else:
            print(f"[GuiConnection] Not Identify Session :{session_id}")

    def close_socket(self, err):
        """
        C++: void CloseSocket(int Errno)
        """
        print(f"[GuiConnection] Gui Connection Broken({self.get_peer_ip()},{self.get_session_name()})")
        # m_GuiConnMgr->RemoveRequestConn(this) 구현 필요 시 호출
        if hasattr(self.m_GuiConnMgr, 'remove_request_conn'):
            self.m_GuiConnMgr.remove_request_conn(self)
        
        self.m_GuiConnMgr.remove(self)

    # ---------------------------------------------------
    # Request Processors
    # ---------------------------------------------------
    def rule_editor_req_process(self, packet):
        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        
        if packet.msg_id == CMD_PARSING_RULE_DOWN:
            if not world.m_ParsingRuleDownLoading:
                self.send_ack(CMD_PARSING_RULE_DOWN_ACK, 1, 1, "Rule Down Load is start")
                if hasattr(self.m_GuiConnMgr, 'cmd_parsing_rule_down'):
                    self.m_GuiConnMgr.cmd_parsing_rule_down(self)
            else:
                self.send_ack(CMD_PARSING_RULE_DOWN_ACK, 1, 0, 
                              "Already Rule Down Load is start\nPlease retry some time later")

    def gw_command_gui_req_process(self, packet):
        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        
        if packet.msg_id == CMD_COMMAND_RULE_DOWN:
            if not world.m_CommandRuleDownLoading:
                self.send_ack(CMD_COMMAND_RULE_DOWN_ACK, 1, 1, "Command Rule Down Load is start")
                # m_GuiConnMgr->CmdCommandRuleDown(this)
            else:
                self.send_ack(CMD_COMMAND_RULE_DOWN_ACK, 1, 0, "Already Command Rule Down Load is start")

        elif packet.msg_id == CMD_SCHEDULER_RULE_DOWN:
            if not world.m_SchedulerRuleDownLoading:
                self.send_ack(CMD_SCHEDULER_RULE_DOWN_ACK, 1, 1, "Scheduler Rule Down Load is start")
                # m_GuiConnMgr->CmdSchedulerRuleDonw(this)
            else:
                self.send_ack(CMD_SCHEDULER_RULE_DOWN_ACK, 1, 0, "Already Scheduler Down Load is start")

    def gw_status_gui_req_process(self, packet):
        """
        GUI로부터 설정 변경(Modify)이나 제어 명령 수신
        """
        print(f"[GuiConnection] Recv Request Status GUI : {packet.msg_id}")
        
        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        ret = False
        result_msg = "" # Python에서는 참조로 문자열 변경 불가하므로 리턴값 등으로 처리 필요하지만 단순화
        
        msg_id = packet.msg_id

        # 1. Info Change Requests
        if msg_id == MANAGER_MODIFY:
            info = AsManagerInfoT.unpack(packet.msg_body)
            if info: ret = world.recv_info_change(info)
            self.send_ack(MANAGER_MODIFY_ACK, 0, 1 if ret else 0, "")

        elif msg_id == CONNECTOR_MODIFY:
            info = AsConnectorInfoT.unpack(packet.msg_body)
            if info: ret = world.recv_info_change(info)
            self.send_ack(CONNECTOR_MODIFY_ACK, 0, 1 if ret else 0, "")
            
        elif msg_id == CONNECTION_LIST_MODIFY:
            # 1. 리스트 구조체 언패킹
            info_list = AsConnectionInfoListT.unpack(packet.msg_body)
            
            ret = False
            if info_list:
                # 2. 월드로 전달 (AsciiServerWorld에서 리스트 순회 처리)
                ret = world.recv_info_change(info_list)
            
            # 3. 결과 응답
            self.send_ack(CONNECTION_LIST_MODIFY_ACK, 0, 1 if ret else 0, "")

        elif msg_id == CONNECTION_LIST_MODIFY:
            # List unpack 구현 필요 (복잡하므로 여기선 생략하거나 단일 처리)
            pass

        elif msg_id == DATAHANDLER_MODIFY:
            info = AsDataHandlerInfoT.unpack(packet.msg_body)
            if info: ret = world.recv_info_change(info)
            self.send_ack(DATAHANDLER_MODIFY_ACK, 0, 1 if ret else 0, "")

        elif msg_id == COMMAND_AUTHORITY_MODIFY:
            info = AsCommandAuthorityInfoT.unpack(packet.msg_body)
            if info: ret = world.recv_info_change(info)
            self.send_ack(COMMAND_AUTHORITY_MODIFY_ACK, 0, 1 if ret else 0, "")
            
        elif msg_id == SUB_PROC_MODIFY:
            info = AsSubProcInfoT.unpack(packet.msg_body)
            if info: ret = world.recv_info_change(info)
            self.send_ack(SUB_PROC_MODIFY_ACK, 0, 1 if ret else 0, "")

        # 2. Control & Etc
        elif msg_id == CMD_LOG_STATUS_CHANGE:
            ctl = AsCmdLogControlT.unpack(packet.msg_body)
            if ctl: self.receive_cmd_log_status_change(ctl)

        elif msg_id == PROC_CONTROL:
            ctl = AsProcControlT.unpack(packet.msg_body)
            if ctl: world.recv_process_control(ctl)

        elif msg_id == SESSION_CONTROL:
            ctl = AsSessionControlT.unpack(packet.msg_body)
            if ctl: world.recv_session_control(ctl)

        elif msg_id == CMD_PARSING_RULE_DOWN:
            self.rule_editor_req_process(packet) # 재사용

        elif msg_id == CMD_PARSING_RULE_CHANGE:
            info = AsRuleChangeInfoT.unpack(packet.msg_body)
            if info: world.parser_rule_change(info)

        elif msg_id == CMD_CONNECTOR_DESC_CHANGE:
            info = AsConnectorDescChangeInfoT.unpack(packet.msg_body)
            if info: world.connector_desc_change(info)

        elif msg_id == AS_MMC_REQ:
            req = AsMmcRequestT.unpack(packet.msg_body)
            if req: self.receive_mmc_req(req)

        # [추가] AS_MMC_REQ_OLD
        elif msg_id == AS_MMC_REQ_OLD:
            req_old = AsMmcRequestOldT.unpack(packet.msg_body)
            if req_old:
                req_new = AsMmcRequestT()
                AsUtil.convert_mmc_old_to_new(req_old, req_new)
                self.receive_mmc_req(req_new)

        # [추가] AS_DB_SYNC_INFO_REQ
        elif msg_id == AS_DB_SYNC_INFO_REQ:
            self.receive_db_sync_info_req()

        # [추가] AS_DATA_HANDLER_INIT
        elif msg_id == AS_DATA_HANDLER_INIT:
            info = AsDataHandlerInitT.unpack(packet.msg_body)
            if info: world.recv_init_info(info)

        # [추가] AS_DATA_ROUTING_INIT
        elif msg_id == AS_DATA_ROUTING_INIT:
            info = AsDataRoutingInitT.unpack(packet.msg_body)
            if info: world.recv_init_info(info)

        # [추가] AS_SESSION_CFG
        elif msg_id == AS_SESSION_CFG:
            cfg = AsSessionCfgT.unpack(packet.msg_body)
            if cfg:
                # AsciiServerWorld에 recv_session_cfg 구현 필요
                if hasattr(world, 'recv_session_cfg'):
                    world.recv_session_cfg(cfg)

        else:
            print(f"[GuiConnection] Unknow Status Gui Request : {packet.msg_id}")

    # ---------------------------------------------------
    # DB Sync Info Handler
    # ---------------------------------------------------
    def receive_db_sync_info_req(self):
        """
        C++: void ReceiveDbSyncInfoReq()
        DB 동기화 정보 요청 처리 -> Standby Server 여부 확인 후 응답
        """
        from AsciiServerWorld import AsciiServerWorld
        from Class.Common.CommType import AS_DB_SYNC_INFO_LIST, AS_DB_SYNC_INFO_REQ_ACK
        
        world = AsciiServerWorld._instance
        
        # 월드에서 동기화 정보 가져오기 (Standby Server일 때만 유효한 포인터 반환)
        info_list = world.get_db_sync_info() # AsDbSyncInfoListT 객체 반환 가정

        if info_list:
            body = info_list.pack()
            self.packet_send(PacketT(AS_DB_SYNC_INFO_LIST, len(body), body))
        else:
            # Standby Server가 아니거나 정보가 없음
            self.send_ack(AS_DB_SYNC_INFO_REQ_ACK, 1, 0, "StandBy Server is't running")

    # ---------------------------------------------------
    # Session Identification & Init
    # ---------------------------------------------------
    def session_identify(self, session_type, session_name):
        """
        세션 식별 후 초기 정보(Init Info) 전송
        """
        # MAINPTR->SessionCfg (구현 필요 시 호출)
        print(f"[GuiConnection] Session Identify : Type({AsUtil.get_process_type_string(session_type)},{session_name})")

        if session_type in [GUI_RULE_EDITOR, GUI_ASCII_CONFIG_INFO, GUI_ASCII_STATUS_INFO]:
            mask = 0
            if session_type == GUI_ASCII_STATUS_INFO:
                mask = (INIT_INFO_MANAGER_MASK | INIT_INFO_DATAHANDLER_MASK |
                        INIT_INFO_PROCESS_MASK | INIT_INFO_COMMAND_AUTHORITY_MASK)
                
                self.send_init_info(INIT_INFO_START, mask)
                self.send_all_manager_info()
                self.send_all_proc_status_info()
                self.send_all_data_handler_info()
                self.send_all_command_authority_info()
                self.send_all_etc_info()
                
            elif session_type == GUI_ASCII_CONFIG_INFO:
                mask = (INIT_INFO_MANAGER_MASK | INIT_INFO_COMMAND_AUTHORITY_MASK | INIT_INFO_DATAHANDLER_MASK)
                
                self.send_init_info(INIT_INFO_START, mask)
                self.send_all_manager_info()
                self.send_all_data_handler_info()
                self.send_all_command_authority_info()

            self.send_init_info(INIT_INFO_END, 0)

    # ---------------------------------------------------
    # Send Info Methods
    # ---------------------------------------------------
    def send_init_info(self, msg_id, mask):
        """
        C++: void SendInitInfo(int MsgId, unsigned int Mask)
        초기화 데이터 전송 전, 전송할 데이터의 총 개수를 계산하여 알림
        """
        from AsciiServerWorld import AsciiServerWorld
        from Class.Common.CommType import (
            PacketT, AsGuiInitInfoT,
            INIT_INFO_MANAGER_MASK, INIT_INFO_PROCESS_MASK,
            INIT_INFO_DATAHANDLER_MASK, INIT_INFO_COMMAND_AUTHORITY_MASK,
            GUI_ASCII_STATUS_INFO
        )

        world = AsciiServerWorld._instance
        count = 0

        # -------------------------------------------------------
        # 1. Manager, Connector, Connection, SubProc Count
        # -------------------------------------------------------
        if mask & INIT_INFO_MANAGER_MASK:
            # Manager Count
            mgr_map = world.m_ManagerConnMgr.get_manager_info_map()
            count += len(mgr_map)

            for mgr in mgr_map.values():
                # Connector Count
                count += len(mgr.m_ConnectorInfoMap)
                
                # Connection Count
                for conn in mgr.m_ConnectorInfoMap.values():
                    count += len(conn.m_ConnectionInfoList)

            # SubProc Count
            sub_proc_map = world.get_sub_proc_info_map()
            count += len(sub_proc_map)

        # -------------------------------------------------------
        # 2. Process Status Count
        # -------------------------------------------------------
        if mask & INIT_INFO_PROCESS_MASK:
            # print("[GuiConnection] Process Info Counting")
            proc_status_map = world.get_proc_status_map()
            # Map<ManagerId, Map<ProcId, Status>> 구조
            for sub_map in proc_status_map.values():
                count += len(sub_map)

        # -------------------------------------------------------
        # 3. DataHandler Count
        # -------------------------------------------------------
        if mask & INIT_INFO_DATAHANDLER_MASK:
            dh_map = world.get_data_handler_info_map()
            count += len(dh_map)

        # -------------------------------------------------------
        # 4. Command Authority Count
        # -------------------------------------------------------
        if mask & INIT_INFO_COMMAND_AUTHORITY_MASK:
            cmd_map = world.get_command_authority_info_map()
            count += len(cmd_map)

        # -------------------------------------------------------
        # 5. System Info & Session Cfg (Status Info 세션일 경우만)
        # -------------------------------------------------------
        if self.m_SessionIdentify == GUI_ASCII_STATUS_INFO:
            sys_map = world.get_as_system_info_map()
            count += len(sys_map)

            sess_map = world.get_as_session_cfg_map()
            count += len(sess_map)

        # -------------------------------------------------------
        # 6. 패킷 전송
        # -------------------------------------------------------
        # AsGuiInitInfoT 구조체 생성 및 전송
        init_info = AsGuiInitInfoT(count)
        body = init_info.pack()
        
        self.packet_send(PacketT(msg_id, len(body), body))

    def send_all_manager_info(self):
        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        
        # Manager Info
        for mgr_info in world.m_ManagerConnMgr.m_ManagerInfoMap.values():
            self.packet_send(PacketT(AS_MANAGER_INFO, len(mgr_info.m_ManagerInfo.pack()), mgr_info.m_ManagerInfo.pack()))
            
            # Connector & Connection Info
            for conn_info in mgr_info.m_ConnectorInfoMap.values():
                self.packet_send(PacketT(AS_CONNECTOR_INFO, len(conn_info.m_ConnectorInfo.pack()), conn_info.m_ConnectorInfo.pack()))
                
                for c in conn_info.m_ConnectionInfoList:
                    self.packet_send(PacketT(AS_CONNECTION_INFO, len(c.pack()), c.pack()))

    def send_all_data_handler_info(self):
        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        
        for info in world.m_DataHandlerConnMgr.get_data_handler_info_map().values():
            self.packet_send(PacketT(AS_DATA_HANDLER_INFO, len(info.pack()), info.pack()))

    def send_all_command_authority_info(self):
        """
        C++: void SendAllCommandAuthorityInfo()
        모든 명령어 권한 정보를 GUI로 전송
        """
        from AsciiServerWorld import AsciiServerWorld
        from Class.Common.CommType import AS_COMMAND_AUTHORITY_INFO, PacketT

        world = AsciiServerWorld._instance
        
        # 1. 맵 정보 가져오기
        # C++: MAINPTR->GetCommandAuthorityInfoMap()
        info_map = world.get_command_authority_info_map()

        if info_map:
            # 2. 순회하며 패킷 전송
            # C++: for(itr = info->begin() ; itr != info->end() ; itr++)
            for info in info_map.values():
                # C++: (char*)((*itr).second) -> Python: info.pack()
                body = info.pack()
                
                packet = PacketT(AS_COMMAND_AUTHORITY_INFO, len(body), body)
                
                # C++: if(!SendPacket(...)) return;
                if not self.packet_send(packet):
                    return
        
    def send_all_proc_status_info(self):
        """
        C++: void SendAllProcStatusInfo()
        전체 프로세스 상태 정보를 GUI로 전송
        구조: Map(ManagerId) -> Map(ProcessId) -> StatusObj
        """
        from AsciiServerWorld import AsciiServerWorld
        from Class.Common.CommType import AS_PROCESS_INFO, PacketT

        world = AsciiServerWorld._instance
        
        # 1. 전체 프로세스 맵 가져오기
        # C++: ProcStatusMap* info = MAINPTR->GetProcStatusMap();
        proc_map = world.get_proc_status_map()

        if proc_map:
            # 2. Outer Loop: 매니저 단위 순회
            # C++: for(itr = info->begin() ; itr != info->end() ; itr++)
            for sub_map in proc_map.values():
                
                # 3. Inner Loop: 개별 프로세스 단위 순회
                # C++: for(infoItr = infoMap->begin() ; infoItr != infoMap->end() ; infoItr++)
                for proc_status in sub_map.values():
                    
                    # 4. 패킷 전송
                    # C++: SendPacket(AS_PROCESS_INFO, (char*)((*infoItr).second), ...)
                    body = proc_status.pack()
                    packet = PacketT(AS_PROCESS_INFO, len(body), body)
                    
                    if not self.packet_send(packet):
                        return

    def send_all_etc_info(self):
        """
        C++: void SendAllEtcInfo()
        시스템 정보 및 세션 설정 정보 전송
        """
        from AsciiServerWorld import AsciiServerWorld
        from Class.Common.CommType import AS_SYSTEM_INFO, AS_SESSION_CFG, PacketT

        world = AsciiServerWorld._instance

        # 1. System Info 전송
        # C++: MAINPTR->GetAsSystemInfoMap(sysInfoMap)
        sys_info_map = world.get_as_system_info_map()
        
        if sys_info_map:
            for info in sys_info_map.values():
                body = info.pack()
                packet = PacketT(AS_SYSTEM_INFO, len(body), body)
                
                if not self.packet_send(packet):
                    return

        # 2. Session Config 전송
        # C++: MAINPTR->GetAsSessionCfgMap(sessioncfgMap)
        session_cfg_map = world.get_as_session_cfg_map()
        
        if session_cfg_map:
            for cfg in session_cfg_map.values():
                body = cfg.pack()
                packet = PacketT(AS_SESSION_CFG, len(body), body)
                
                if not self.packet_send(packet):
                    return

    # ---------------------------------------------------
    # MMC & Log Handling
    # ---------------------------------------------------
    def receive_mmc_req(self, mmc_req):
        """
        C++: void ReceiveMMCReq(AS_MMC_REQUEST_T* MMCReq)
        MMC 요청 처리 및 결과 전송
        """
        from AsciiServerWorld import AsciiServerWorld
        from Class.Common.CommType import (
            AsMmcPublishT, AsMmcResultT, PacketT,
            NO_RESPONSE, IMMEDIATE, R_ERROR, AS_MMC_RES
        )

        # 1. Publish 구조체 생성 및 데이터 복사
        # C++: AS_MMC_PUBLISH_T mmcCom; memset... strcpy...
        mmc_com = AsMmcPublishT()
        mmc_com.ne = mmc_req.ne
        mmc_com.mmc = mmc_req.mmc
        mmc_com.responseMode = NO_RESPONSE
        mmc_com.publishMode = IMMEDIATE

        # 2. 명령 실행 요청 (World -> Manager)
        # C++: MAINPTR->SendMMCCommandFromStatusGui(&mmcCom, errStr);
        # Python에서는 (bool, err_msg) 튜플 반환 방식으로 처리
        world = AsciiServerWorld._instance
        ret, err_str = world.send_mmc_command_from_status_gui(mmc_com)

        # 3. 실패 시 에러 응답 전송
        if not ret:
            # C++: AS_MMC_RESULT_T mmcRes; ...
            mmc_res = AsMmcResultT()
            mmc_res.id = 0
            mmc_res.resultMode = R_ERROR
            mmc_res.result = err_str

            # Packet 전송
            body = mmc_res.pack()
            self.packet_send(PacketT(AS_MMC_RES, len(body), body))

    def receive_cmd_log_status_change(self, log_ctl):
        if log_ctl.Type == GET_LOG_INFO:
            self.send_all_log_status()
        else:
            from AsciiServerWorld import AsciiServerWorld
            AsciiServerWorld._instance.receive_cmd_log_status_change(log_ctl)

    def send_all_log_status(self):
        """
        C++: void SendAllLogStatus()
        시스템의 모든 로그 상태 정보를 조회하여 GUI로 전송
        """
        from AsciiServerWorld import AsciiServerWorld
        
        # 1. 로그 상태 리스트 수집
        # C++: LogStatusVector logStatusList; MAINPTR->GetLogStatusList(&logStatusList);
        log_status_list = []
        AsciiServerWorld._instance.get_log_status_list(log_status_list)

        # 2. 순회하며 전송
        # C++: for(...) { SendLogStatus(...) }
        for status in log_status_list:
            if not self.send_log_status(status):
                return

        print("[GuiConnection] Send All Log Status To Gui")
    
    def send_log_status(self, status):
        body = status.pack()
        return self.packet_send(PacketT(AS_LOG_INFO, len(body), body))
    
    def receive_cmd_log_status_change(self, log_ctl):
        """
        C++: void ReceiveCmdLogStatusChange(AS_CMD_LOG_CONTROL_T* LogCtl)
        로그 제어 패킷 처리 (조회 vs 변경)
        """
        # 디버그 로그
        print(f"[GuiConnection] ReceiveCmdLogStatusChange : Type={log_ctl.Type}")

        # 필요한 상수 Import
        from Class.Common.CommType import GET_LOG_INFO
        from AsciiServerWorld import AsciiServerWorld

        # 1. 로그 정보 조회 요청 (GET_LOG_INFO)
        if log_ctl.Type == GET_LOG_INFO:
            self.send_all_log_status()

        # 2. 로그 상태 변경 요청 (SET) -> World로 위임
        else:
            AsciiServerWorld._instance.receive_cmd_log_status_change(log_ctl)
            
    def send_ascii_error(self, err_msg):
        """
        C++: bool SendAsciiError(AS_ASCII_ERROR_MSG_T* ErrMsg)
        에러 메시지를 GUI로 전송
        """
        from Class.Common.CommType import ASCII_ERROR_MSG, PacketT

        # 1. 구조체 직렬화
        # C++: (char*)ErrMsg
        body = err_msg.pack()

        # 2. 패킷 생성 및 전송
        # C++: SendNonBlockPacket(ASCII_ERROR_MSG, ...)
        # Python의 packet_send는 보통 쓰기 버퍼에 데이터를 넣고 즉시 반환되므로
        # Non-Blocking 전송과 유사한 효과를 냅니다.
        packet = PacketT(ASCII_ERROR_MSG, len(body), body)
        
        return self.packet_send(packet)
    
    def gw_command_gui_req_process(self, packet):
        """
        C++: void GwCommandGuiReqProcess(PACKET_T* Packet)
        명령어/스케줄러 룰 다운로드 요청 처리
        """
        print(f"[GuiConnection] Recv Request Cmd GUI : {packet.msg_id}")

        from AsciiServerWorld import AsciiServerWorld
        from Class.Common.CommType import (
            CMD_COMMAND_RULE_DOWN, CMD_COMMAND_RULE_DOWN_ACK,
            CMD_SCHEDULER_RULE_DOWN, CMD_SCHEDULER_RULE_DOWN_ACK
        )

        world = AsciiServerWorld._instance
        msg_id = packet.msg_id

        # 1. Command Rule Down 요청
        if msg_id == CMD_COMMAND_RULE_DOWN:
            # 진행 상태 확인 (C++: GetCommandRuleDownStatus)
            if not world.m_CommandRuleDownLoading:
                self.send_ack(CMD_COMMAND_RULE_DOWN_ACK, 1, 1, "Command Rule Down Load is start")
                # 매니저에게 요청 위임
                if self.m_GuiConnMgr:
                    self.m_GuiConnMgr.cmd_command_rule_down(self)
            else:
                self.send_ack(CMD_COMMAND_RULE_DOWN_ACK, 1, 0, "Already Command Rule Down Load is start")

        # 2. Scheduler Rule Down 요청
        elif msg_id == CMD_SCHEDULER_RULE_DOWN:
            # 진행 상태 확인 (C++: GetSchedulerRuleDownStatus)
            if not world.m_SchedulerRuleDownLoading:
                self.send_ack(CMD_SCHEDULER_RULE_DOWN_ACK, 1, 1, "Scheduler Rule Down Load is start")
                # 매니저에게 요청 위임 (C++ 오타 Donw -> Down 수정)
                if self.m_GuiConnMgr:
                    self.m_GuiConnMgr.cmd_scheduler_rule_down(self)
            else:
                self.send_ack(CMD_SCHEDULER_RULE_DOWN_ACK, 1, 0, "Already Scheduler Down Load is start")

        else:
            print(f"[GuiConnection] Unknown Cmd Gui Request : {msg_id}")
            
    def gw_status_gui_req_process(self, packet):
        """
        C++: void GwStatusGuiReqProcess(PACKET_T* Packet)
        GUI로부터의 상태/설정 변경 요청 처리
        """
        # 디버그 로그
        # print(f"[GuiConnection] Recv Request Status GUI : {packet.msg_id}")

        from AsciiServerWorld import AsciiServerWorld
        from Class.Common.CommType import (
            MANAGER_MODIFY, MANAGER_MODIFY_ACK,
            CONNECTOR_MODIFY, CONNECTOR_MODIFY_ACK,
            CONNECTION_MODIFY, CONNECTION_MODIFY_ACK,
            CONNECTION_LIST_MODIFY, CONNECTION_LIST_MODIFY_ACK,
            DATAHANDLER_MODIFY, DATAHANDLER_MODIFY_ACK,
            COMMAND_AUTHORITY_MODIFY, COMMAND_AUTHORITY_MODIFY_ACK,
            SUB_PROC_MODIFY, SUB_PROC_MODIFY_ACK,
            CMD_LOG_STATUS_CHANGE, PROC_CONTROL, SESSION_CONTROL,
            CMD_PARSING_RULE_DOWN, CMD_PARSING_RULE_DOWN_ACK,
            CMD_MAPPING_RULE_DOWN, CMD_MAPPING_RULE_DOWN_ACK,
            CMD_PARSING_RULE_CHANGE, CMD_CONNECTOR_DESC_CHANGE,
            AS_MMC_REQ, AS_MMC_REQ_OLD, AS_DB_SYNC_INFO_REQ,
            AS_DATA_HANDLER_INIT, AS_DATA_ROUTING_INIT, AS_SESSION_CFG,
            # 구조체들
            AsManagerInfoT, AsConnectorInfoT, AsConnectionInfoT,
            AsConnectionInfoListT, AsDataHandlerInfoT, AsCommandAuthorityInfoT,
            AsSubProcInfoT, AsCmdLogControlT, AsProcControlT, AsSessionControlT,
            AsRuleChangeInfoT, AsConnectorDescChangeInfoT,
            AsMmcRequestT, AsMmcRequestOldT,
            AsDataHandlerInitT, AsDataRoutingInitT, AsSessionCfgT
        )
        from Class.Common.AsUtil import AsUtil

        world = AsciiServerWorld._instance
        msg_id = packet.msg_id
        result_msg = "" # C++에서는 RecvInfoChange에서 채워짐 (여기선 단순화)

        # -------------------------------------------------------
        # 1. Info Modify Requests (설정 변경)
        # -------------------------------------------------------
        if msg_id == MANAGER_MODIFY:
            info = AsManagerInfoT.unpack(packet.msg_body)
            ret = world.recv_info_change(info) if info else False
            self.send_ack(MANAGER_MODIFY_ACK, 0, 1 if ret else 0, result_msg)

        elif msg_id == CONNECTOR_MODIFY:
            info = AsConnectorInfoT.unpack(packet.msg_body)
            ret = world.recv_info_change(info) if info else False
            self.send_ack(CONNECTOR_MODIFY_ACK, 0, 1 if ret else 0, result_msg)

        elif msg_id == CONNECTION_MODIFY:
            info = AsConnectionInfoT.unpack(packet.msg_body)
            ret = world.recv_info_change(info) if info else False
            self.send_ack(CONNECTION_MODIFY_ACK, 0, 1 if ret else 0, result_msg)

        elif msg_id == CONNECTION_LIST_MODIFY:
            info = AsConnectionInfoListT.unpack(packet.msg_body)
            ret = world.recv_info_change(info) if info else False
            self.send_ack(CONNECTION_LIST_MODIFY_ACK, 0, 1 if ret else 0, result_msg)

        elif msg_id == DATAHANDLER_MODIFY:
            info = AsDataHandlerInfoT.unpack(packet.msg_body)
            ret = world.recv_info_change(info) if info else False
            self.send_ack(DATAHANDLER_MODIFY_ACK, 0, 1 if ret else 0, result_msg)

        elif msg_id == COMMAND_AUTHORITY_MODIFY:
            info = AsCommandAuthorityInfoT.unpack(packet.msg_body)
            ret = world.recv_info_change(info) if info else False
            self.send_ack(COMMAND_AUTHORITY_MODIFY_ACK, 0, 1 if ret else 0, result_msg)

        elif msg_id == SUB_PROC_MODIFY:
            info = AsSubProcInfoT.unpack(packet.msg_body)
            ret = world.recv_info_change(info) if info else False
            self.send_ack(SUB_PROC_MODIFY_ACK, 0, 1 if ret else 0, result_msg)

        # -------------------------------------------------------
        # 2. Control & Status
        # -------------------------------------------------------
        elif msg_id == CMD_LOG_STATUS_CHANGE:
            ctl = AsCmdLogControlT.unpack(packet.msg_body)
            if ctl: self.receive_cmd_log_status_change(ctl)

        elif msg_id == PROC_CONTROL:
            ctl = AsProcControlT.unpack(packet.msg_body)
            if ctl: world.recv_process_control(ctl)

        elif msg_id == SESSION_CONTROL:
            ctl = AsSessionControlT.unpack(packet.msg_body)
            if ctl: world.recv_session_control(ctl)

        # -------------------------------------------------------
        # 3. Rule Down Load
        # -------------------------------------------------------
        elif msg_id == CMD_PARSING_RULE_DOWN:
            if not world.m_ParsingRuleDownLoading:
                self.send_ack(CMD_PARSING_RULE_DOWN_ACK, 1, 1, "Rule Down Load is start")
                if self.m_GuiConnMgr: self.m_GuiConnMgr.cmd_parsing_rule_down(self)
            else:
                self.send_ack(CMD_PARSING_RULE_DOWN_ACK, 1, 0, "Already Rule Down Load is start")

        elif msg_id == CMD_MAPPING_RULE_DOWN:
            if not world.m_MappingRuleDownLoading:
                self.send_ack(CMD_MAPPING_RULE_DOWN_ACK, 1, 1, "Mapping Rule Down Load is start")
                if self.m_GuiConnMgr: self.m_GuiConnMgr.cmd_mapping_rule_down(self)
            else:
                self.send_ack(CMD_MAPPING_RULE_DOWN_ACK, 1, 0, "Already Mapping Rule Down Load is start")

        # -------------------------------------------------------
        # 4. Other Changes
        # -------------------------------------------------------
        elif msg_id == CMD_PARSING_RULE_CHANGE:
            info = AsRuleChangeInfoT.unpack(packet.msg_body)
            if info: world.parser_rule_change(info)

        elif msg_id == CMD_CONNECTOR_DESC_CHANGE:
            info = AsConnectorDescChangeInfoT.unpack(packet.msg_body)
            if info: world.connector_desc_change(info)

        # -------------------------------------------------------
        # 5. MMC & Init
        # -------------------------------------------------------
        elif msg_id == AS_MMC_REQ:
            req = AsMmcRequestT.unpack(packet.msg_body)
            if req: self.receive_mmc_req(req)

        elif msg_id == AS_MMC_REQ_OLD:
            req_old = AsMmcRequestOldT.unpack(packet.msg_body)
            if req_old:
                req_new = AsMmcRequestT()
                AsUtil.convert_mmc_old_to_new(req_old, req_new)
                self.receive_mmc_req(req_new)

        elif msg_id == AS_DB_SYNC_INFO_REQ:
            self.receive_db_sync_info_req()

        elif msg_id == AS_DATA_HANDLER_INIT:
            info = AsDataHandlerInitT.unpack(packet.msg_body)
            if info: world.recv_init_info(info)

        elif msg_id == AS_DATA_ROUTING_INIT:
            info = AsDataRoutingInitT.unpack(packet.msg_body)
            if info: world.recv_init_info(info)

        elif msg_id == AS_SESSION_CFG:
            cfg = AsSessionCfgT.unpack(packet.msg_body)
            if cfg: world.recv_session_cfg(cfg)

        else:
            print(f"[GuiConnection] Unknown Status Gui Request : {msg_id}")
            
    def receive_mmc_req_old(self, mmc_req_old):
        """
        C++: void ReceiveMMCReq(AS_MMC_REQUEST_OLD_T* MMCReq)
        구형 MMC 요청을 신형으로 변환하여 처리
        """
        from Class.Common.CommType import AsMmcRequestT
        from Class.Common.AsUtil import AsUtil

        # 1. 신형 구조체 생성
        # C++: AS_MMC_REQUEST_T req; memset...
        req_new = AsMmcRequestT()

        # 2. 변환 (Old -> New)
        # C++: AsUtil::ConvertMMC_OldToNew(MMCReq, &req);
        AsUtil.convert_mmc_old_to_new(mmc_req_old, req_new)

        # 3. 신형 처리 함수 호출
        # C++: ReceiveMMCReq(&req);
        self.receive_mmc_req(req_new)
        
    # ---------------------------------------------------
    # Error & Shutdown Handling
    # ---------------------------------------------------
    def recv_shut_down_info(self, info):
        """
        C++: void RecvShutDownInfo(string Info)
        세션 강제 종료 알림 (블로킹 감지 등)
        """
        # C++: frCORE_ERROR(...)
        print(f"[GuiConnection] [CORE_ERROR] Closed session enforced(may be blocked) : {self.get_session_name()}")

    def recv_over_flow_data_buf_info(self, max_buf_size, cur_buf_size):
        """
        C++: void RecvOverFlowDataBufInfo(int MaxBufSize, int CurBufSize)
        송신 버퍼 오버플로우 감지 시 세션 강제 종료
        """
        # C++: frCORE_ERROR(...)
        msg = (f"Session may be blocked(MAX:{max_buf_size} byte, "
               f"CUR:{cur_buf_size} byte)[{self.get_session_name()}]")
        print(f"[GuiConnection] [CORE_ERROR] {msg}")
        
        # 소켓 강제 종료
        # C++: ShutDown(m_FD);
        self.shutdown()