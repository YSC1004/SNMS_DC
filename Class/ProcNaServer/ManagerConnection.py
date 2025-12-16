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

# -------------------------------------------------------
# ManagerConnection Class
# 매니저 프로세스와의 통신 채널
# -------------------------------------------------------
class ManagerConnection(AsSocket):
    def __init__(self, mgr_conn_mgr):
        """
        C++: ManagerConnection(ManagerConnMgr* MgrConnMgr)
        """
        super().__init__()
        
        self.m_ManagerConnMgr = mgr_conn_mgr
        self.m_ManagerInfo = None
        self.m_ConnectorInfoMap = {}
        self.m_RouterPortNo = -1
        
        # 로그 상태 맵 { "LogName": AsLogStatusT }
        self.m_LogStatusMap = {}
        
        # 커맨드 포트를 가진 NE 목록 (Set)
        self.m_HasCmdPortNeListSet = set()

    def __del__(self):
        """
        C++: ~ManagerConnection()
        """
        super().__del__()

    # ---------------------------------------------------
    # Packet Handling (Virtual Override)
    # ---------------------------------------------------
    def receive_packet(self, packet, session_id):
        """
        C++: void ReceivePacket(...)
        """
        if session_id == ASCII_MANAGER:
            self.manager_req_process(packet)
        else:
            print(f"[ManagerConnection] Unknown Session ID: {session_id}")

    def manager_req_process(self, packet):
        """
        C++: void ManagerReqProcess(PACKET_T* Packet)
        """
        msg_id = packet.msg_id
        
        if msg_id == MANAGER_INIT_END:
            # 매니저 초기화 완료 -> 하위 프로세스 정보 동기화 시작
            # C++: ManagerInitEnd() -> Python 구현은 아래 별도 메서드로
            pass 

        elif msg_id == CONNECTOR_PORT_INFO_REQ:
            # AS_CONNECTOR_PORT_INFO_REQ_T 구조체 파싱 필요 (CommType에 추가 필요)
            # req = AsConnectorPortInfoReqT.unpack(packet.msg_body)
            # self.send_connector_port_info(req)
            pass

        elif msg_id == CMD_MMC_PUBLISH_RES:
            # MMC 결과 수신
            # MAINPTR->ReceiveMMCResult(...)
            pass
            
        elif msg_id == AS_LOG_INFO:
            status = AsLogStatusT.unpack(packet.msg_body)
            if status:
                self.receive_log_info(status)

        elif msg_id == ASCII_ERROR_MSG:
            # 에러 메시지 수신 -> 메인 서버로 전달
            pass

        elif msg_id == PROCESS_INFO:
            status = AsProcessStatusT.unpack(packet.msg_body)
            if status:
                # 매니저 관리자에게 전달
                self.m_ManagerConnMgr.recv_process_info(status)
                
                # 커넥터가 STOP되면 해당 NE 목록 제거
                if status.ProcessType == ASCII_CONNECTOR and status.Status == STOP:
                    proc_id = status.ProcessId
                    if "_" in proc_id:
                        proc_id = proc_id.split("_", 1)[1] # PREFIX 제거
                    self.remove_cmd_ne_list(proc_id)

        elif msg_id == PORT_STATUS_INFO:
            # 포트 상태 정보 -> 매니저 관리자에게 전달
            pass

        elif msg_id == ROUTER_PORT_INFO:
            # 라우터 포트 정보 갱신
            # info = AsRouterPortInfoT.unpack(packet.msg_body)
            # self.m_RouterPortNo = info.RouterPortNo
            pass

        elif msg_id == AS_SYSTEM_INFO:
            info = AsSystemInfoT.unpack(packet.msg_body)
            if info:
                # MAINPTR->RecvSystemInfo(info)
                pass
        
        else:
            print(f"[ManagerConnection] Unknown MsgId : {msg_id}")

    # ---------------------------------------------------
    # Close Handling
    # ---------------------------------------------------
    def close_socket(self, err):
        """
        C++: void CloseSocket(int Errno)
        소켓 연결 종료 처리 및 자동 복구 로직
        """
        session_name = self.get_session_name()
        print(f"[ManagerConnection] Manager Socket Broken : {session_name}")

        if self.m_ManagerInfo is None:
            self.m_ManagerConnMgr.remove(self)
            return

        # 순환 참조 방지를 위해 내부 Import
        from Server.AsciiServerWorld import AsciiServerWorld
        from Class.Common.CommType import STOP, START, WAIT_NO, UNDEFINED, ASCII_MANAGER, AsProcessStatusT
        
        world = AsciiServerWorld._instance

        # 1. 매니저 상태 업데이트 (메모리)
        self.m_ManagerInfo.m_ManagerInfo.CurStatus = STOP
        self.m_ManagerInfo.m_ManagerInfo.RequestStatus = WAIT_NO

        # 2. 하위 커넥터 및 연결 상태 일괄 업데이트
        for connector_info in self.m_ConnectorInfoMap.values():
            connector_info.m_ConnectorInfo.CurStatus = STOP
            connector_info.m_ConnectorInfo.RequestStatus = WAIT_NO
            
            print(f"[ManagerConnection] Change Connector({connector_info.m_ConnectorInfo.ConnectorId}) "
                  f"Status({connector_info.m_ConnectorInfo.CurStatus})")

            # 하위 Connection 리스트 업데이트
            for conn in connector_info.m_ConnectionInfoList:
                conn.RequestStatus = WAIT_NO
                conn.CurStatus = UNDEFINED

        # 3. 매니저 정보 변경 알림 (GUI 등)
        if world:
            world.send_info_change(self.m_ManagerInfo.m_ManagerInfo)

        # 4. 프로세스 상태 정보 업데이트 (시스템 모니터링용)
        proc_info = AsProcessStatusT()
        proc_info.ProcessId = session_name
        proc_info.Status = STOP
        proc_info.ProcessType = ASCII_MANAGER
        
        if world:
            world.update_process_info(proc_info)

        # 5. 자동 복구 로직 (Auto Restart)
        # 설정상으로는 START인데 연결이 끊겼다면 비정상 종료로 간주
        if self.m_ManagerInfo.m_ManagerInfo.SettingStatus == START:
            if world:
                world.send_ascii_error(1, f"The MANAGER({session_name}) is killed abnormal.")
            
            print(f"[ManagerConnection] The MANAGER({session_name}) is killed abnormal.")

            # 매니저 재실행 시도
            if self.m_ManagerConnMgr.execute_manager(self.m_ManagerInfo):
                if world:
                    world.send_ascii_error(1, f"The MANAGER({session_name}) is reexecuted.")
                print(f"[ManagerConnection] The MANAGER({session_name}) is reexecuted.")
            else:
                # 재실행 실패 시 (Global Error Msg 등 활용 가능)
                if world:
                    world.send_ascii_error(1, "Manager Re-execution Failed")

        else:
            # 정상 종료 (사용자가 Stop 명령을 내린 경우)
            print(f"[ManagerConnection] The MANAGER({session_name}) is killed normally.")
            if world:
                world.send_ascii_error(1, f"The MANAGER({session_name}) is killed normally.")

        # 6. 리스트에서 제거 및 소켓 정리
        self.m_ManagerConnMgr.remove(self)

    # ---------------------------------------------------
    # Session Identification & Init
    # ---------------------------------------------------
    def session_identify(self, session_type, session_name):
        """
        C++: void SessionIdentify(int SessionType, string SessionName)
        세션 식별: DB/메모리에 있는 매니저 정보와 연결하고 AliveCheck 시작
        """
        # 1. 매니저 정보 조회
        self.m_ManagerInfo = self.m_ManagerConnMgr.find_manager_info(session_name)

        if self.m_ManagerInfo is None:
            print(f"[ManagerConnection] Can't Find ManagerInfo : {session_name}")
            self.close()
            self.m_ManagerConnMgr.remove(self)
            return

        # 2. 상태 체크
        if self.m_ManagerInfo.m_ManagerInfo.SettingStatus == STOP:
            print(f"[ManagerConnection] Manager({session_name}) Connection is invalid(timeover etc...)")
            self.close()
            self.m_ManagerConnMgr.remove(self)
            return

        # 3. 커넥터 정보 맵 연결
        self.m_ConnectorInfoMap = self.m_ManagerInfo.m_ConnectorInfoMap

        print(f"[ManagerConnection] Session Identify : Type({AsUtil.get_process_type_string(session_type)}), Name({session_name})")

        # 4. 매니저 실행 감시 타이머 해제 (성공적으로 붙었으므로)
        self.m_ManagerConnMgr.manager_session_identify(self.m_ManagerInfo.m_ManagerInfo.ManagerId)

        # 5. 세션 설정 (버퍼 크기 등 - AsciiServerWorld 위임)
        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        # world.session_cfg(self, SESSION_TYPE_MGR) # 구현 필요 시 주석 해제

        # 6. Alive Check 시작 (Timer)
        # self.start_alive_check(world.get_proc_alive_check_time(), world.get_alive_check_limit_cnt())
        
        world.send_ascii_error(1, f"The MANAGER({self.get_session_name()}) is start successfully.")

    def manager_init_end(self):
        """
        C++: void ManagerInitEnd()
        매니저 프로세스 초기화 완료 신호 처리
        """
        print(f"[ManagerConnection] Manager({self.get_session_name()}) Init End")

        if not self.m_ManagerInfo:
            print(f"[ManagerConnection] Manager({self.get_session_name()}) Info not init...")
            self.close()
            self.m_ManagerConnMgr.remove(self)
            return

        # 상태 업데이트
        self.m_ManagerInfo.m_ManagerInfo.CurStatus = START
        self.m_ManagerInfo.m_ManagerInfo.RequestStatus = WAIT_NO

        # 데이터 핸들러 정보 전송 (ManagerConnMgr 위임)
        self.send_data_handler_info()

        # 현재 설정된 Connector 정보 전송 (루프)
        delay_time = 0
        
        for conn_info in self.m_ConnectorInfoMap.values():
            if conn_info.m_ConnectorInfo.SettingStatus == STOP:
                continue
            
            proc_ctrl = AsProcControlT()
            proc_ctrl.ProcessType = ASCII_CONNECTOR
            proc_ctrl.ManagerId = conn_info.m_ConnectorInfo.ManagerId
            proc_ctrl.Status = START
            proc_ctrl.RuleId = conn_info.m_ConnectorInfo.RuleId
            proc_ctrl.ProcessId = conn_info.m_ConnectorInfo.ConnectorId
            proc_ctrl.MmcIdentType = conn_info.m_ConnectorInfo.MmcIdentType
            proc_ctrl.CmdResponseType = conn_info.m_ConnectorInfo.CmdResponseType
            proc_ctrl.JunctionType = conn_info.m_ConnectorInfo.JunctionType
            proc_ctrl.LogCycle = conn_info.m_ConnectorInfo.LogCycle
            
            proc_ctrl.DelayTime = delay_time
            
            # PROC_CONTROL 패킷 전송
            if not self.packet_send(PacketT(PROC_CONTROL, len(proc_ctrl.pack()), proc_ctrl.pack())):
                return

            conn_info.m_ConnectorInfo.RequestStatus = WAIT_START
            
            # GUI 알림
            from Server.AsciiServerWorld import AsciiServerWorld
            AsciiServerWorld._instance.send_info_change(conn_info.m_ConnectorInfo)
            
            delay_time += 1
            
        # 매니저 상태 변경 알림
        AsciiServerWorld._instance.send_info_change(self.m_ManagerInfo.m_ManagerInfo)
        
    def alive_check_fail(self, fail_count):
        """
        C++: void AliveCheckFail(int FailCount)
        Alive Check 실패 시 호출됨 -> 매니저 강제 종료
        """
        session_name = self.get_session_name()
        
        # 1. 로그 출력
        print(f"[ManagerConnection] AliveCheckFail({session_name}) , Count : {fail_count}")
        print(f"[ManagerConnection] The MANAGER({session_name}) is killed on purpose for no reply.")

        # 2. 메인 서버 에러 보고
        # 순환 참조 방지를 위해 내부 Import
        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        
        if world:
            world.send_ascii_error(1, f"The MANAGER({session_name}) is killed on purpose for no reply.")

        # 3. 매니저 프로세스 강제 종료 (Kill)
        # m_ManagerInfo.m_ManagerInfo는 AsManagerInfoT 객체
        if self.m_ManagerConnMgr and self.m_ManagerInfo:
            manager_id = self.m_ManagerInfo.m_ManagerInfo.ManagerId
            self.m_ManagerConnMgr.kill_manager(manager_id)
        
    def send_connector_port_info(self, con_info_req):
        """
        C++: void SendConnectorPortInfo(AS_CONNECTOR_PORT_INFO_REQ_T* ConInfoReq)
        커넥터의 연결(Connection) 정보를 조회하여 포트 오픈 명령 전송
        """
        print("-----------------------------------------------------------")
        print(f"[ManagerConnection] SendConnectorPortInfo : {con_info_req.ConnectorId}")
        print("-----------------------------------------------------------")

        session_name = self.get_session_name()

        # 1. 메모리에서 커넥터 정보 찾기
        connector_info = self.m_ManagerConnMgr.find_connector_info(session_name, con_info_req.ConnectorId)
        
        if connector_info is None:
            print(f"[ManagerConnection] Can't Find Connector : {con_info_req.ConnectorId}")
            return

        info_list = connector_info.m_ConnectionInfoList

        # 2. DB에서 IP 정보 조회 (Sequence -> IP 매핑)
        # 순환 참조 방지 Import
        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        db_mgr = world.m_DbManager
        
        # ip_list = { sequence: ip_string }
        ip_list = {}
        
        # GetConnectionIpInfo 구현 필요 (DbManager에 이미 추가됨)
        if db_mgr.get_connection_ip_info(ip_list, con_info_req.ConnectorId):
            
            # 3. 연결 정보 리스트 순회
            for info_itr in info_list:
                
                # IP 정보 매칭 확인
                if info_itr.Sequence not in ip_list:
                    print(f"[ManagerConnection] Can't Find Ip for connection sequence : {info_itr.Sequence}")
                    continue
                
                ip_addr = ip_list[info_itr.Sequence]

                # 4. 상태가 START인 경우에만 명령 전송
                if info_itr.SettingStatus == START:
                    cmd_open_port = AsCmdOpenPortT()
                    
                    # Msg ID 발급
                    cmd_open_port.Id = world.get_msg_id()
                    
                    # 데이터 채우기
                    cmd_open_port.Sequence = info_itr.Sequence
                    cmd_open_port.EquipId = info_itr.ConnectorId
                    cmd_open_port.AgentEquipId = info_itr.AgentEquipId
                    cmd_open_port.ConnectorId = info_itr.ConnectorId
                    cmd_open_port.IpAddress = ip_addr
                    cmd_open_port.PortNo = info_itr.PortNo
                    cmd_open_port.UserId = info_itr.UserId
                    cmd_open_port.Password = info_itr.UserPassword
                    cmd_open_port.ProtocolType = info_itr.ProtocolType
                    cmd_open_port.PortType = info_itr.PortType
                    cmd_open_port.GatFlag = info_itr.GatFlag
                    cmd_open_port.CommandPortFlag = info_itr.CommandPortFlag
                    
                    # Name 생성: "Sequence_PortTypeStr"
                    type_str = AsUtil.get_port_type_string(cmd_open_port.PortType)
                    cmd_open_port.Name = f"{cmd_open_port.Sequence}_{type_str}"
                    
                    # 디버깅 출력 & 전송
                    AsUtil.cmd_open_port_display(cmd_open_port)
                    self.cmd_open_port_info(cmd_open_port)
                    
                    # 커맨드 포트 관리 목록 업데이트
                    if cmd_open_port.CommandPortFlag:
                        print(f"[ManagerConnection] Insert HasCmdPortNeListSet : {info_itr.ConnectorId}({session_name})")
                        self.m_HasCmdPortNeListSet.add(info_itr.ConnectorId)
                        
                    # 요청 상태 변경
                    info_itr.RequestStatus = WAIT_START

    def cmd_open_port_info(self, port_info):
        """
        C++: bool CmdOpenPortInfo(AS_CMD_OPEN_PORT_T* PortInfo)
        CMD_OPEN_PORT 패킷 전송 헬퍼
        """
        # PacketT 생성 (MsgId: CMD_OPEN_PORT)
        body_data = port_info.pack()
        packet = PacketT(CMD_OPEN_PORT, len(body_data), body_data)
        return self.packet_send(packet)

    # ---------------------------------------------------
    # Packet Sending & Control
    # ---------------------------------------------------
    def send_data_handler_info(self):
        """
        C++: void SendDataHandlerInfo()
        실행 중인 모든 DataHandler 정보를 현재 매니저 세션에 전송
        """
        # 순환 참조 방지 및 상수 Import
        from Server.AsciiServerWorld import AsciiServerWorld
        from Class.Common.CommType import START, AS_DATA_HANDLER_INFO, PacketT

        world = AsciiServerWorld._instance
        
        # 메인 서버에서 DataHandler 맵(Dict) 가져오기
        # key: HandlerId, value: AsDataHandlerInfoT 객체
        info_map = world.get_data_handler_info_map()

        for info in info_map.values():
            # 조건: RunMode가 0(Normal)이고 Status가 START인 경우만 전송
            if info.RunMode == 0:
                if info.SettingStatus == START:
                    try:
                        # 1. 구조체 직렬화
                        body_data = info.pack()
                        
                        # 2. 패킷 생성
                        packet = PacketT(AS_DATA_HANDLER_INFO, len(body_data), body_data)
                        
                        # 3. 전송 (AsSocket.packet_send)
                        if not self.packet_send(packet):
                            return # 전송 실패 시 중단
                            
                    except Exception as e:
                        print(f"[ManagerConnection] SendDataHandlerInfo Error: {e}")
                        return
                    
    def send_mmc_command(self, mmc_com):
        """
        C++: bool SendMMCCommand(AS_MMC_PUBLISH_T* MMCCom)
        MMC 발행 요청 전송
        """
        # 1. 필요한 상수/클래스 확인 (CommType.py)
        # CMD_MMC_PUBLISH_REQ, PacketT
        
        try:
            # 2. 구조체 직렬화 (AsMmcPublishT -> bytes)
            # mmc_com은 AsMmcPublishT 객체여야 함
            body_data = mmc_com.pack()

            # 3. 패킷 생성 (Header + Body)
            packet = PacketT(CMD_MMC_PUBLISH_REQ, len(body_data), body_data)

            # 4. 전송 (AsSocket.packet_send)
            # 로그는 주석 처리됨 (C++ 원본 따름)
            # print(f"Send Mmcpublish({mmc_com.id}), ne({mmc_com.ne}) ...")

            return self.packet_send(packet)
            
        except Exception as e:
            print(f"[ManagerConnection] SendMMCCommand Error: {e}")
            return False
        
    def receive_time_out(self, reason, extra_reason):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        타임아웃 처리 (프로세스 종료 대기 실패 시 강제 종료 등)
        """
        # PROC_TERMINATE_WAIT 상수는 CommType.py에 정의되어 있어야 함
        from Class.Common.CommType import PROC_TERMINATE_WAIT

        if reason == PROC_TERMINATE_WAIT:
            print("[ManagerConnection] Manager Terminate TimeOut")
            print(f"[ManagerConnection] Manager Kill Force!!! : {self.get_session_name()}")
            
            if self.m_ManagerConnMgr and self.m_ManagerInfo:
                # 매니저 정보에서 ID를 가져와 강제 종료
                manager_id = self.m_ManagerInfo.m_ManagerInfo.ManagerId
                self.m_ManagerConnMgr.kill_manager(manager_id)
        
        else:
            print(f"[ManagerConnection] Unknown Timeout Reason {reason}")

    def is_has_cmd_port_ne_name(self, ne_name):
        """
        C++: bool IsHasCmdPortNeName(char* NeName)
        해당 NE 이름이 관리 목록(Set)에 있는지 확인
        """
        # Python의 Set은 'in' 연산자로 O(1) 조회가 가능합니다.
        # C++ 코드의 find() != end() 로직과 동일합니다.
        
        # parkbosun need lock...IsNeName (C++ 주석 참고: 필요시 락 추가)
        # 여기서는 읽기 작업이므로 GIL 덕분에 atomic할 수 있으나, 
        # 엄격한 스레드 안전성이 필요하다면 self.m_Lock 등을 고려해야 함.
        
        if ne_name in self.m_HasCmdPortNeListSet:
            return True
        else:
            return False
        
    def receive_log_info(self, status):
        """
        C++: void ReceiveLogInfo(AS_LOG_STATUS_T* Status)
        로그 상태 정보 수신 및 맵 갱신 (LOG_ADD / LOG_DEL 처리)
        """
        # 필요한 상수 및 클래스 Import
        from Class.Common.CommType import LOG_ADD, AsLogStatusT
        from Server.AsciiServerWorld import AsciiServerWorld
        
        # 1. 기존 로그 정보 제거
        # C++: map.find() -> delete -> erase
        # Python: 키가 존재하면 del
        if status.name in self.m_LogStatusMap:
            del self.m_LogStatusMap[status.name]

        # 2. 추가 모드인 경우 맵에 등록
        # C++: if(LOG_ADD) { new -> memcpy -> insert }
        if status.status == LOG_ADD:
            # 객체 복사 (Deep Copy 유사 동작)
            new_log_status = AsLogStatusT()
            new_log_status.name = status.name
            new_log_status.status = status.status
            new_log_status.logs = status.logs
            
            self.m_LogStatusMap[status.name] = new_log_status

        # 3. 메인 월드로 상태 전파
        # C++: AsciiServerWorld::m_WorldPtr->SendLogStatus(Status);
        world = AsciiServerWorld._instance
        if world and hasattr(world, 'send_log_status'):
            world.send_log_status(status)
            
    def get_log_status_list(self, log_status_list):
        """
        C++: void GetLogStatusList(LogStatusVector* LogStatusList)
        현재 세션의 로그 상태 맵(Map)에 있는 값들을 리스트에 추가
        """
        # self.m_LogStatusMap은 { "LogName": AsLogStatusT_Object } 형태의 딕셔너리
        for log_status in self.m_LogStatusMap.values():
            log_status_list.append(log_status)
            
    def stop_manager(self):
        """
        C++: void StopManager()
        매니저 프로세스 종료 명령 전송 및 종료 대기 타이머 설정
        """
        # 필요한 상수 Import (CommType.py에 정의되어 있어야 함)
        # 만약 PROC_TERMINATE_WAIT_TIMEOUT이 없다면 20으로 대체
        from Class.Common.CommType import CMD_PROC_TERMINATE, PROC_TERMINATE_WAIT, PacketT
        
        try:
            from Class.Common.CommType import PROC_TERMINATE_WAIT_TIMEOUT
        except ImportError:
            PROC_TERMINATE_WAIT_TIMEOUT = 20

        print(f"[ManagerConnection] Sending Stop Command to {self.get_session_name()}")

        # 1. 종료 명령 패킷 전송
        packet = PacketT(CMD_PROC_TERMINATE)
        self.packet_send(packet)

        # 2. 종료 대기 타이머 설정 (기본 20초)
        # 이 시간 내에 연결이 끊기지 않으면 receive_time_out에서 강제 종료(Kill)함
        self.set_timer(PROC_TERMINATE_WAIT_TIMEOUT, PROC_TERMINATE_WAIT)

    def send_cmd_parsing_rule_down(self):
        """
        C++: void SendCmdParsingRuleDown()
        파싱 룰 다운로드 명령 전송
        """
        from Class.Common.CommType import CMD_PARSING_RULE_DOWN, PacketT
        
        packet = PacketT(CMD_PARSING_RULE_DOWN)
        self.packet_send(packet)

    def send_cmd_mapping_rule_down(self):
        """
        C++: void SendCmdMappingRuleDown()
        매핑 룰 다운로드 명령 전송
        """
        from Class.Common.CommType import CMD_MAPPING_RULE_DOWN, PacketT
        
        packet = PacketT(CMD_MAPPING_RULE_DOWN)
        self.packet_send(packet)

    def send_session_control(self, session_ctl):
        """
        C++: bool SendSessionControl(AS_SESSION_CONTROL_T* SessionCtl)
        세션(Connection) 제어 명령 처리 (DB 업데이트 -> 패킷 전송)
        """
        # 순환 참조 방지 및 상수 Import
        from Server.AsciiServerWorld import AsciiServerWorld
        from Class.Common.CommType import (
            START, STOP, WAIT_NO, WAIT_START, WAIT_STOP,
            SESSION_CONTROL, AsCmdOpenPortT, PacketT
        )

        world = AsciiServerWorld._instance
        db_mgr = world.m_DbManager

        # 1. 연결 정보 메모리 조회
        connection_info = self.m_ManagerConnMgr.find_connection_info(
            session_ctl.ManagerId, session_ctl.ConnectorId, session_ctl.Sequence
        )

        if connection_info is None:
            msg = f"Can't Find Session : {session_ctl.Sequence}"
            print(f"[ManagerConnection] {msg}")
            world.send_ascii_error(1, msg)
            return False

        # 2. 요청 상태 확인 (중복 요청 방지)
        if connection_info.RequestStatus == WAIT_NO:
            
            # 2-1. DB 업데이트
            # update_connection_status_by_ctl 메서드는 DbManager.py에 구현됨
            if not db_mgr.update_connection_status_by_ctl(session_ctl):
                err_msg = f"Update Connection Error : {db_mgr.get_error_msg()}"
                print(f"[ManagerConnection] {err_msg}")
                return False

            # 2-2. 현재 상태와 요청 상태 비교
            if session_ctl.Status == START and connection_info.SettingStatus == START:
                msg = f"Already Start Connection : {session_ctl.Sequence}"
                print(f"[ManagerConnection] {msg}")
                world.send_ascii_error(1, msg)
                return False
            elif session_ctl.Status == STOP and connection_info.SettingStatus == STOP:
                msg = f"Already Stop Connection : {session_ctl.Sequence}"
                print(f"[ManagerConnection] {msg}")
                world.send_ascii_error(1, msg)
                return False

            # 2-3. 메모리 상태 갱신
            connection_info.SettingStatus = START if session_ctl.Status == START else STOP
            connection_info.RequestStatus = WAIT_START if session_ctl.Status == START else WAIT_STOP
            
            # GUI 등에 변경 알림
            world.send_info_change(connection_info)

            # ---------------------------------------------------
            # 3-A. STOP 처리
            # ---------------------------------------------------
            if session_ctl.Status != START:
                connection_info.RequestStatus = WAIT_STOP
                
                if connection_info.CommandPortFlag:
                    self.remove_cmd_ne_list(session_ctl.ConnectorId)
                
                # SESSION_CONTROL 패킷 전송
                body = session_ctl.pack()
                packet = PacketT(SESSION_CONTROL, len(body), body)
                self.packet_send(packet)

            # ---------------------------------------------------
            # 3-B. START 처리 (Open Port 명령 전송)
            # ---------------------------------------------------
            else:
                print("-----------------------------------------------------------")
                print(f"[ManagerConnection] SendConnectorPortInfo : {session_ctl.ConnectorId}")
                print("-----------------------------------------------------------")

                ip_list = {} # {sequence: ip}
                
                # DB에서 IP 조회
                if db_mgr.get_connection_ip_info(ip_list, session_ctl.ConnectorId, session_ctl.Sequence):
                    
                    if connection_info.Sequence not in ip_list:
                        msg = f"Can't Find Ip for connection sequence : {session_ctl.ConnectorId},{connection_info.Sequence}"
                        print(f"[ManagerConnection] {msg}")
                        world.send_ascii_error(1, msg)
                        return False
                    
                    ip_addr = ip_list[connection_info.Sequence]

                    # CMD_OPEN_PORT 패킷 구성
                    cmd_open = AsCmdOpenPortT()
                    cmd_open.Id = world.get_msg_id()
                    cmd_open.Sequence = connection_info.Sequence
                    cmd_open.EquipId = connection_info.ConnectorId
                    cmd_open.AgentEquipId = connection_info.AgentEquipId
                    cmd_open.ConnectorId = connection_info.ConnectorId
                    cmd_open.IpAddress = ip_addr
                    cmd_open.PortNo = connection_info.PortNo
                    cmd_open.UserId = connection_info.UserId
                    cmd_open.Password = connection_info.UserPassword
                    cmd_open.ProtocolType = connection_info.ProtocolType
                    cmd_open.PortType = connection_info.PortType
                    cmd_open.GatFlag = connection_info.GatFlag
                    cmd_open.CommandPortFlag = connection_info.CommandPortFlag
                    
                    # Name 생성 (예: "1_CMD")
                    p_type_str = AsUtil.get_port_type_string(cmd_open.PortType)
                    cmd_open.Name = f"{cmd_open.Sequence}_{p_type_str}"
                    
                    # 디버깅 및 전송
                    AsUtil.cmd_open_port_display(cmd_open)
                    self.cmd_open_port_info(cmd_open) # AsSocket Helper 호출

                    if connection_info.CommandPortFlag:
                        print(f"[ManagerConnection] Insert HasCmdPortNeListSet : {connection_info.ConnectorId}({self.get_session_name()})")
                        self.m_HasCmdPortNeListSet.add(connection_info.ConnectorId)
                
                connection_info.RequestStatus = WAIT_START
            
            return True

        else:
            # 이미 처리 중인 요청이 있음
            req_str = "Start" if connection_info.RequestStatus == WAIT_START else "Stop"
            msg = f"Already Request Connection: {session_ctl.Sequence}({req_str})"
            print(f"[ManagerConnection] {msg}")
            world.send_ascii_error(1, msg)
            return False

    def parser_rule_change(self, change_info):
        """
        C++: void ParserRuleChange(AS_RULE_CHANGE_INFO_T* ChangeInfo)
        """
        # CMD_PARSING_RULE_CHANGE 전송
        packet = PacketT(CMD_PARSING_RULE_CHANGE, len(change_info.pack()), change_info.pack())
        self.packet_send(packet)

    def remove_cmd_ne_list(self, connector_id):
        """
        C++: void RemoveCmdNeList(string ConnectorId)
        관리 목록(Set)에서 해당 ConnectorId(NE 이름) 제거
        """
        # 로그 출력
        # C++: frDEBUG(("Remove HasCmdPortNeListSet : %s(%s)", ...))
        print(f"[ManagerConnection] Remove HasCmdPortNeListSet : {connector_id}({self.get_session_name()})")
        
        # Set에서 제거
        # C++ set::erase는 요소가 없으면 무시하므로, Python set.discard가 동일한 동작을 함
        # (set.remove는 요소가 없으면 KeyError 발생)
        self.m_HasCmdPortNeListSet.discard(connector_id)
        
    def get_router_port_no(self):
        """
        C++: int GetRouterPortNo()
        라우터 포트 번호 반환
        """
        return self.m_RouterPortNo

