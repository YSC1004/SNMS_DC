import sys
import os
import threading
import time

# -------------------------------------------------------
# 1. 프로젝트 경로 설정
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# 2. 모듈 Import
# -------------------------------------------------------
from Class.Common.ConnectionMgr import ConnectionMgr
from Class.Common.AsciiServerType import ManagerInfo, ConnectorInfo, ConnectionInfoList
from Class.Common.CommType import *
from Class.Common.AsUtil import AsUtil
from Class.ProcNaServer.ManagerConnection import ManagerConnection
from Class.Util.FrSshUtil import FrSshUtil
from Class.Event.FrTimerSensor import FrTimerSensor
from Class.Util.FrBaseList import StringIntKey
from Class.Util.FrTime import FrTime

# -------------------------------------------------------
# ManagerConnMgr Class
# 매니저 프로세스 연결 관리, 실행 제어, 정보 동기화
# -------------------------------------------------------
class ManagerConnMgr(ConnectionMgr):
    WAIT_MANAGER_START_TIME = 10
    WAIT_MANAGER_START_TIMEOUT = 1001

    def __init__(self):
        """
        C++: ManagerConnMgr()
        """
        super().__init__()
        
        self.m_ManagerInfoMap = {} # Dict[ManagerId, ManagerInfo]
        self.m_ManagerExecuteTimerMap = {} # Dict[ManagerId, StringIntKey]
        
        # ConnectionMgr의 Lock을 사용하거나 별도 Lock 사용
        self.m_SocketRemoveLock = threading.Lock()

    def __del__(self):
        """
        C++: ~ManagerConnMgr()
        """
        super().__del__()

    # ---------------------------------------------------
    # Socket Accept
    # ---------------------------------------------------
    def accept_socket(self):
        """
        C++: void AcceptSocket()
        """
        mgr_conn = ManagerConnection(self)

        if not self.accept(mgr_conn):
            print(f"[ManagerConnMgr] Manager Socket Accept Error : {self.get_obj_err_msg()}")
            return

        self.add(mgr_conn)
        mgr_conn.set_writerable_check(True)

        print("[ManagerConnMgr] Manager Connection Accepted")

    # ---------------------------------------------------
    # Initialization & Execution
    # ---------------------------------------------------
    def init(self):
        """
        C++: bool Init()
        DB에서 매니저 정보를 로드
        """
        self.m_ManagerInfoMap.clear()
        
        # AsciiServerWorld -> DbManager 접근
        from AsciiServerWorld import AsciiServerWorld
        db_mgr = AsciiServerWorld._instance.m_DbManager
        
        if not db_mgr.get_manager_info(self.m_ManagerInfoMap):
            print(f"[ManagerConnMgr] Get Manager Info Error : {db_mgr.get_error_msg()}")
            return False
            
        print(f"[ManagerConnMgr] Manager Count : {len(self.m_ManagerInfoMap)}")
        return True

    def execute_manager(self, info=None, wait_time=30):
        """
        C++: void ExecuteManager() / bool ExecuteManager(...)
        """
        # 1. 전체 실행 (인자 없음)
        if info is None:
            if not self.init(): return
            
            wait_t = 30
            for mgr_info in self.m_ManagerInfoMap.values():
                if mgr_info.m_ManagerInfo.SettingStatus == START:
                    self.execute_manager(mgr_info, self.WAIT_MANAGER_START_TIME + wait_t)
                    wait_t += 2
            return

        # 2. 개별 실행
        if info.m_ManagerInfo.RequestStatus == WAIT_NO:
            from AsciiServerWorld import AsciiServerWorld
            world = AsciiServerWorld._instance

            print(f"[ManagerConnMgr] ManagerId : {info.m_ManagerInfo.ManagerId}, IP : {info.m_ManagerInfo.IP}")

            # Ping Check
            if not world.ping_check(info.m_ManagerInfo.IP):
                msg = f"Ping - No Answer from MANAGER({info.m_ManagerInfo.ManagerId})"
                print(f"[ManagerConnMgr] {msg}")
                # world.send_ascii_error(1, msg)
                return False

            # SSH Info Check
            if not info.m_ManagerInfo.SshID:
                # DB에서 다시 조회
                if not world.m_DbManager.get_manager_info_find_id(info):
                    return False
                
                if not info.m_ManagerInfo.SshID or not info.m_ManagerInfo.SshPass:
                    print(f"[ManagerConnMgr] Can't Find SSHID/Pass: {info.m_ManagerInfo.ManagerId}")
                    return False

            # Kill Old Process
            self.kill_manager(info.m_ManagerInfo.ManagerId)

            # Execute Command
            # "~User/NAA/Bin/ManagerName -name ID -svrip IP -svrport Port ..."
            cmd = (f"~{world.get_user_name()}{world.get_start_dir()}/Bin/{world.get_process_name(ASCII_MANAGER)} "
                   f"{ARG_NAME} {info.m_ManagerInfo.ManagerId} {ARG_SVR_IP} {world.get_server_ip()} "
                   f"{ARG_SVR_PORT} {world.get_listen_port(ASCII_MANAGER)} &")

            print(f"[ManagerConnMgr] Manager Execute : {cmd}")
            
            if self.run_command(info.m_ManagerInfo.SshID, info.m_ManagerInfo.SshPass, 
                                info.m_ManagerInfo.IP, cmd):
                
                info.m_ManagerInfo.RequestStatus = WAIT_START
                
                # Timer Setting
                key = StringIntKey()
                key.m_Id = info.m_ManagerInfo.ManagerId
                
                # TimerSensor 생성 및 등록 (self가 FrTimerSensor 상속이 아니므로 별도 관리 필요하거나 Mixin)
                # 여기서는 set_timer 메서드가 있다고 가정 (FrSocketSensor 상속 계열이므로 가능)
                timer_key = self.set_timer(wait_time, self.WAIT_MANAGER_START_TIMEOUT, key)
                key.m_Key = timer_key
                
                self.m_ManagerExecuteTimerMap[key.m_Id] = key
                
                world.send_info_change(info.m_ManagerInfo)
                return True
            return False
        else:
            print(f"[ManagerConnMgr] Already Request: {info.m_ManagerInfo.ManagerId}")
            return False

    def run_command(self, ssh_id, ssh_pass, ip, command):
        ssh = FrSshUtil()
        if ssh.ssh_connect(ip, 22, ssh_id, ssh_pass, command):
            return True
        return False

    def kill_manager(self, manager_id):
        info = self.find_manager_info(manager_id)
        if not info: return
        
        from AsciiServerWorld import AsciiServerWorld
        cmd = f"{AsciiServerWorld._instance.get_script_dir()}/KillProcess.sh"
        self.run_command(info.m_ManagerInfo.SshID, info.m_ManagerInfo.SshPass, info.m_ManagerInfo.IP, cmd)

    def stop_manager(self, info):
        con = self.find_session(info.m_ManagerInfo.ManagerId)
        if not con:
            return False
            
        info.m_ManagerInfo.RequestStatus = WAIT_STOP
        
        from AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.send_info_change(info.m_ManagerInfo)
        
        if hasattr(con, 'stop_manager'):
            con.stop_manager()
        return True
    
    def get_log_status_list(self, log_status_list):
        """
        C++: void GetLogStatusList(LogStatusVector* LogStatusList)
        연결된 모든 매니저의 로그 상태를 수집하여 리스트에 추가
        """
        # 동시성 제어를 위해 Lock 사용 (부모 클래스 ConnectionMgr의 m_Lock)
        with self.m_Lock:
            for socket in self.m_SocketConnectionList:
                # ManagerConnection 객체인지 확인 (Duck Typing)
                if hasattr(socket, 'get_log_status_list'):
                    # 각 연결(Session)이 가지고 있는 로그 상태들을 
                    # log_status_list(레퍼런스)에 추가함
                    socket.get_log_status_list(log_status_list)
                    
    def send_mmc_command(self, mmc_pub):
        """
        C++: bool SendMMCCommand(AS_MMC_PUBLISH_T* MMCCom, char* ErrStr)
        Python: (bool success, str error_message) 튜플 반환
        """
        # 1. 명령어 유무 확인
        if not mmc_pub.mmc:
            err_msg = f"{mmc_pub.ne} : Command is empty, therefore can't execute command"
            print(f"[ManagerConnMgr] {err_msg}")
            return False, err_msg

        # 2. 연결 리스트 순회
        # 리스트가 변경될 수 있으므로 복사본을 뜨거나 락을 걸어야 안전하지만,
        # C++ 원본 로직(검색 시 락 안 걸고, 찾으면 락)을 따르기 위해 
        # Python에서는 리스트 복사본(slice)을 순회합니다.
        for socket in self.m_SocketConnectionList[:]:
            
            # 해당 커넥션이 이 NE를 담당하는지 확인
            # ManagerConnection.is_has_cmd_port_ne_name 호출
            if hasattr(socket, 'is_has_cmd_port_ne_name') and \
               socket.is_has_cmd_port_ne_name(mmc_pub.ne):
                   
                self.socket_remove_lock()

                # 락을 건 상태에서 유효성 재확인
                if self.is_valid_connection(socket):
                    # 명령 전송 (ManagerConnection.send_mmc_command)
                    if hasattr(socket, 'send_mmc_command'):
                        socket.send_mmc_command(mmc_pub)
                else:
                    print(f"[ManagerConnMgr] invalid Mgr Connection : {socket.get_session_name()}")
                    self.socket_remove_unlock()
                    break # 루프 탈출
                
                self.socket_remove_unlock()
                return True, "" # 성공

        # 3. 실패 처리 (담당 매니저를 찾지 못함)
        err_msg = " The Command (8286)port on NMS connected to the Network Element does not exist or has been shut down."
        print(f"[ManagerConnMgr] {err_msg}")
        return False, err_msg

    # ---------------------------------------------------
    # Process & Session Control
    # ---------------------------------------------------
    def recv_process_control(self, proc_ctl):
        """
        C++: bool RecvProcessControl(AS_PROC_CONTROL_T* ProcCtl)
        """
        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        db_mgr = world.m_DbManager

        # 1. Manager Control
        if proc_ctl.ProcessType == ASCII_MANAGER:
            info = self.find_manager_info(proc_ctl.ManagerId)
            if not info: return False

            if info.m_ManagerInfo.RequestStatus != WAIT_NO:
                return False

            # DB Update
            if not db_mgr.update_manager_status(proc_ctl.ManagerId, proc_ctl.Status, proc_ctl.Desc):
                return False
            
            info.m_ManagerInfo.SettingStatus = proc_ctl.Status
            
            if proc_ctl.Status == START:
                return self.execute_manager(info)
            else:
                return self.stop_manager(info)

        # 2. Connector Control
        elif proc_ctl.ProcessType == ASCII_CONNECTOR:
            info = self.find_manager_info(proc_ctl.ManagerId)
            if not info: return False
            
            if info.m_ManagerInfo.RequestStatus == WAIT_START or info.m_ManagerInfo.CurStatus == STOP:
                return False
                
            conn_info = info.get_connector_info(proc_ctl.ProcessId)
            if not conn_info: return False

            if conn_info.m_ConnectorInfo.RequestStatus == WAIT_NO:
                # Session Find
                con = self.find_session(proc_ctl.ManagerId)
                if not con: return False

                # DB Update
                time_str = FrTime.get_current_time_string()
                if not db_mgr.update_connector_status(proc_ctl, time_str):
                    return False
                
                # Update Memory Info
                conn_info.m_ConnectorInfo.SettingStatus = proc_ctl.Status
                conn_info.m_ConnectorInfo.RequestStatus = WAIT_START if proc_ctl.Status == START else WAIT_STOP
                conn_info.m_ConnectorInfo.LastActionDate = time_str
                conn_info.m_ConnectorInfo.LastActionDesc = proc_ctl.Desc
                conn_info.m_ConnectorInfo.LastActionType = AsUtil.get_action_type_string(
                    ACT_START if proc_ctl.Status == START else ACT_STOP
                )
                
                # Copy attributes for Command
                proc_ctl.RuleId = conn_info.m_ConnectorInfo.RuleId
                proc_ctl.MmcIdentType = conn_info.m_ConnectorInfo.MmcIdentType
                # ... 기타 속성 복사 ...

                world.send_info_change(conn_info.m_ConnectorInfo)
                
                # Send Packet
                con.send_packet(PROC_CONTROL, proc_ctl.pack()) # PROC_CONTROL Message ID 사용 가정
                return True

        return False

    def send_session_control(self, session_ctl):
        con = self.find_session(session_ctl.ManagerId)
        if con:
            if hasattr(con, 'send_session_control'):
                con.send_session_control(session_ctl)

    # ---------------------------------------------------
    # Info Change Handlers
    # ---------------------------------------------------
    def recv_info_change(self, info, result_msg=""):
        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        # 1. Manager Info
        if isinstance(info, AsManagerInfoT):
            if info.RequestStatus == ACT_CREATE:
                new_mgr = ManagerInfo()
                new_mgr.m_ManagerInfo = info
                new_mgr.m_ManagerInfo.CurStatus = STOP
                new_mgr.m_ManagerInfo.RequestStatus = WAIT_NO
                self.m_ManagerInfoMap[info.ManagerId] = new_mgr
                world.send_info_change(new_mgr.m_ManagerInfo)
                return True

            elif info.RequestStatus == ACT_MODIFY:
                mgr = self.find_manager_info(info.OldManagerId)
                if not mgr: return False
                
                del self.m_ManagerInfoMap[info.OldManagerId]
                mgr.m_ManagerInfo = info
                mgr.m_ManagerInfo.CurStatus = STOP
                mgr.m_ManagerInfo.RequestStatus = WAIT_NO
                self.m_ManagerInfoMap[info.ManagerId] = mgr
                
                if info.ManagerId != info.OldManagerId:
                    for c_info in mgr.m_ConnectorInfoMap.values():
                        c_info.m_ConnectorInfo.ManagerId = info.ManagerId
                        for conn in c_info.m_ConnectionInfoList:
                            conn.ManagerId = info.ManagerId
                
                world.send_info_change(info)
                return True

            elif info.RequestStatus == ACT_DELETE:
                if info.ManagerId in self.m_ManagerInfoMap:
                    del self.m_ManagerInfoMap[info.ManagerId]
                    world.send_info_change(info)
                    return True

        # 2. Connector Info
        elif isinstance(info, AsConnectorInfoT):
            mgr = self.find_manager_info(info.ManagerId)
            if not mgr: return False
            
            if info.RequestStatus == ACT_CREATE:
                new_conn = ConnectorInfo()
                new_conn.m_ConnectorInfo = info
                new_conn.m_ConnectorInfo.CurStatus = STOP
                new_conn.m_ConnectorInfo.RequestStatus = WAIT_NO
                mgr.m_ConnectorInfoMap[info.ConnectorId] = new_conn
                world.send_info_change(new_conn.m_ConnectorInfo)
                return True
            
            elif info.RequestStatus == ACT_MODIFY:
                conn = self.find_connector_info(info.ConnectorId)
                if not conn: return False
                
                # Manager Change Check
                if conn.m_ConnectorInfo.ManagerId != info.ManagerId:
                    old_mgr = self.find_manager_info(conn.m_ConnectorInfo.ManagerId)
                    if old_mgr and info.ConnectorId in old_mgr.m_ConnectorInfoMap:
                        del old_mgr.m_ConnectorInfoMap[info.ConnectorId]
                    
                    conn.m_ConnectorInfo.ManagerId = info.ManagerId
                    for c in conn.m_ConnectionInfoList:
                        c.ManagerId = info.ManagerId
                    
                    mgr.m_ConnectorInfoMap[info.ConnectorId] = conn
                
                # 필드 업데이트
                conn.m_ConnectorInfo.RuleId = info.RuleId
                conn.m_ConnectorInfo.Desc = info.Desc
                # ...
                world.send_info_change(info)
                return True

            elif info.RequestStatus == ACT_DELETE:
                if info.ConnectorId in mgr.m_ConnectorInfoMap:
                    del mgr.m_ConnectorInfoMap[info.ConnectorId]
                    world.send_info_change(info)
                    return True

        # 3. Connection Info
        elif isinstance(info, AsConnectionInfoT):
            if info.RequestStatus == ACT_CREATE:
                conn_info = self.find_connector_info(info.ManagerId, info.ConnectorId)
                if not conn_info: return False
                
                new_c = AsConnectionInfoT()
                # Deep Copy
                new_c.ManagerId = info.ManagerId
                new_c.ConnectorId = info.ConnectorId
                new_c.Sequence = info.Sequence
                # ...
                new_c.CurStatus = STOP
                new_c.RequestStatus = WAIT_NO
                
                conn_info.m_ConnectionInfoList.append(new_c)
                world.send_info_change(info)
                return True
            
            elif info.RequestStatus == ACT_MODIFY:
                target = self.find_connection_info(info.Sequence)
                if not target: return False
                
                old_cid = target.ConnectorId
                if info.ConnectorId != old_cid:
                    old_c_info = self.find_connector_info(old_cid)
                    if old_c_info: old_c_info.delete_connection_info(info.Sequence)
                    
                    new_c_info = self.find_connector_info(info.ConnectorId)
                    if new_c_info: new_c_info.m_ConnectionInfoList.append(target)
                
                # Update Fields
                target.AgentEquipId = info.AgentEquipId
                # ...
                world.send_info_change(info)
                return True
            
            elif info.RequestStatus == ACT_DELETE:
                conn_info = self.find_connector_info(info.ManagerId, info.ConnectorId)
                if conn_info:
                    conn_info.delete_connection_info(info.Sequence)
                    world.send_info_change(info)
                    return True

        return False

    def parser_rule_change(self, change_info):
        con = self.find_session(change_info.ManagerId)
        if con:
            conn_info = self.find_connector_info(change_info.ManagerId, change_info.ProcessId)
            if conn_info and conn_info.m_ConnectorInfo.SettingStatus == START:
                conn_info.m_ConnectorInfo.RuleId = change_info.RuleId
                
                if hasattr(con, 'parser_rule_change'):
                    con.parser_rule_change(change_info)
                
                from AsciiServerWorld import AsciiServerWorld
                AsciiServerWorld._instance.send_info_change(conn_info.m_ConnectorInfo)
                return True
        return False

    def connector_desc_change(self, info):
        conn_info = self.find_connector_info(info.ManagerId, info.ConnectorId)
        if not conn_info: return False
        
        conn_info.m_ConnectorInfo.Desc = info.Description
        from AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.send_info_change(conn_info.m_ConnectorInfo)
        return True

    # ---------------------------------------------------
    # Status Updates from Manager
    # ---------------------------------------------------
    def receive_proc_info(self, proc_info):
        """
        C++: void ReceiveProcInfo(AS_PROCESS_STATUS_T* ProcInfo)
        """
        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        
        if proc_info.ProcessType == ASCII_MANAGER:
            info = self.find_manager_info(proc_info.ManagerId)
            if info:
                info.m_ManagerInfo.CurStatus = proc_info.Status
                info.m_ManagerInfo.RequestStatus = WAIT_NO
                
        elif proc_info.ProcessType == ASCII_CONNECTOR:
            # ProcessId에 PREFIX 제거 로직 등 필요 시 구현
            p_id = proc_info.ProcessId.split('_')[-1] # 예시
            
            info = self.find_connector_info(proc_info.ManagerId, p_id)
            if info:
                info.m_ConnectorInfo.CurStatus = proc_info.Status
                info.m_ConnectorInfo.RequestStatus = WAIT_NO
                
                if info.m_ConnectorInfo.CurStatus == STOP:
                    for c in info.m_ConnectionInfoList:
                        c.RequestStatus = WAIT_NO
                        c.CurStatus = UNDEFINED
                        
                world.send_info_change(info.m_ConnectorInfo)

        world.update_process_info(proc_info)

    def receive_port_info(self, port_status):
        """
        C++: void ReceivePortInfo(AS_PORT_STATUS_INFO_T* PortStatus)
        """
        conn_info = self.find_connection_info(port_status.ManagerId, port_status.ConnectorId, port_status.Sequence)
        if conn_info:
            conn_info.CurStatus = port_status.Status
            conn_info.RequestStatus = WAIT_NO
            
            from AsciiServerWorld import AsciiServerWorld
            world = AsciiServerWorld._instance
            world.send_info_change(conn_info)
            
            # DB Update
            world.m_DbManager.update_connection_status(-1, "", port_status.Sequence, port_status)

    # ---------------------------------------------------
    # Utils
    # ---------------------------------------------------
    def find_manager_info(self, manager_id):
        return self.m_ManagerInfoMap.get(manager_id)

    def find_connector_info(self, manager_id, connector_id=None):
        if connector_id is None:
            # connector_id만으로 검색
            for mgr in self.m_ManagerInfoMap.values():
                if manager_id in mgr.m_ConnectorInfoMap:
                    return mgr.m_ConnectorInfoMap[manager_id]
            return None
        
        mgr = self.find_manager_info(manager_id)
        if mgr:
            return mgr.m_ConnectorInfoMap.get(connector_id)
        return None

    def find_connection_info(self, *args):
        """
        Overload: (Sequence) or (ManagerId, ConnectorId, Sequence)
        """
        if len(args) == 1: # Sequence only
            seq = args[0]
            for mgr in self.m_ManagerInfoMap.values():
                for conn_info in mgr.m_ConnectorInfoMap.values():
                    for c in conn_info.m_ConnectionInfoList:
                        if c.Sequence == seq: return c
            return None
            
        elif len(args) == 3:
            mgr_id, conn_id, seq = args
            conn_info = self.find_connector_info(mgr_id, conn_id)
            if conn_info:
                return conn_info.get_connection_info(seq)
            return None

    def get_manager_info_map(self):
        return self.m_ManagerInfoMap

    def socket_remove_lock(self):
        self.m_SocketRemoveLock.acquire()

    def socket_remove_unlock(self):
        self.m_SocketRemoveLock.release()

    def receive_time_out(self, reason, extra_reason):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        매니저 실행 타임아웃 처리 (WAIT_MANAGER_START_TIMEOUT)
        """
        # 필요한 상수 Import (CommType에 정의됨)
        from Class.Common.CommType import STOP, WAIT_NO

        if reason == self.WAIT_MANAGER_START_TIMEOUT:
            # extra_reason은 StringIntKey 객체임 (execute_manager에서 전달)
            key = extra_reason 
            manager_id = key.m_Id

            print(f"[ManagerConnMgr] Recv Timeout WAIT_MANAGER_START_TIMEOUT : {manager_id}")

            # MAINPTR / DBPTR 접근을 위한 싱글톤 가져오기
            # 순환 참조 방지를 위해 내부 Import
            from AsciiServerWorld import AsciiServerWorld
            world = AsciiServerWorld._instance
            db_mgr = world.m_DbManager

            # 1. 에러 메시지 전송
            world.send_ascii_error(1, f"Manager({manager_id}) Start Error")

            # 2. 타이머 관리 맵에서 제거
            if manager_id in self.m_ManagerExecuteTimerMap:
                del self.m_ManagerExecuteTimerMap[manager_id]
            else:
                print(f"[ManagerConnMgr] Can't Find Manager({manager_id}) in ManagerExecuteTimerMap")

            # 3. 매니저 정보 조회
            info = self.find_manager_info(manager_id)
            if info is None:
                print(f"[ManagerConnMgr] Manager Info Can't Find : {manager_id}")
                return

            # 4. DB 업데이트 (상태를 STOP으로 변경)
            if not db_mgr.update_manager_status(manager_id, STOP, "Error during trying start."):
                print(f"[ManagerConnMgr] Update Manager Status Error : {db_mgr.get_error_msg()}")
                return

            print(f"[ManagerConnMgr] Manager({manager_id}) is setting STOP")

            # 5. 메모리 상의 상태 정보 갱신
            info.m_ManagerInfo.SettingStatus = STOP
            info.m_ManagerInfo.CurStatus = STOP
            info.m_ManagerInfo.RequestStatus = WAIT_NO

            # 6. 변경 정보 전파 (GUI 등)
            world.send_info_change(info.m_ManagerInfo)

            # C++의 'delete key'는 Python GC가 자동으로 처리하므로 불필요
        
    def send_cmd_parsing_rule_down(self):
        """
        C++: void SendCmdParsingRuleDown()
        모든 매니저 연결 세션에 CMD_PARSING_RULE_DOWN 명령 전송
        """
        with self.m_Lock:
            for socket in self.m_SocketConnectionList:
                # ManagerConnection 객체인지 확인 (또는 해당 메서드가 있는지 확인)
                if hasattr(socket, 'send_cmd_parsing_rule_down'):
                    socket.send_cmd_parsing_rule_down()
                    
    def send_cmd_mapping_rule_down(self):
        """
        C++: void SendCmdMappingRuleDown()
        모든 매니저 연결 세션에 CMD_MAPPING_RULE_DOWN 명령 전송
        """
        with self.m_Lock:
            for socket in self.m_SocketConnectionList:
                # ManagerConnection 객체인지 확인 (Duck Typing)
                if hasattr(socket, 'send_cmd_mapping_rule_down'):
                    socket.send_cmd_mapping_rule_down()
                    
    def send_session_control(self, session_ctl):
        """
        C++: void SendSessionControl(AS_SESSION_CONTROL_T* SessionCtl)
        특정 매니저 세션을 찾아 세션 제어 명령을 전송
        """
        # 1. 세션 찾기 (부모 클래스 ConnectionMgr의 find_session 사용)
        con = self.find_session(session_ctl.ManagerId)

        if con:
            # 2. 연결된 세션(ManagerConnection)으로 명령 위임
            # ManagerConnection.send_session_control 메서드 호출 (구현 필요)
            if hasattr(con, 'send_session_control'):
                con.send_session_control(session_ctl)
        else:
            # 3. 세션을 못 찾은 경우 에러 보고 (MAINPTR->SendAsciiError)
            # 순환 참조 방지를 위해 내부 Import
            from AsciiServerWorld import AsciiServerWorld
            world = AsciiServerWorld._instance
            
            if world:
                msg = f"The Manager({session_ctl.ManagerId}) does not start."
                # send_ascii_error(priority, msg)
                world.send_ascii_error(1, msg)
                
    def parser_rule_change(self, change_info):
        """
        C++: bool ParserRuleChange(AS_RULE_CHANGE_INFO_T* ChangeInfo)
        파싱 룰 변경 처리: 매니저 세션 확인 -> 커넥터 상태 확인 -> 룰 ID 갱신 -> 명령 전송
        """
        # 순환 참조 방지를 위한 내부 Import
        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        # 1. 매니저 세션(Connection) 찾기
        con = self.find_session(change_info.ManagerId)
        
        if con:
            # 2. 커넥터 정보 찾기
            conn_info = self.find_connector_info(change_info.ManagerId, change_info.ProcessId)
            
            if conn_info is None:
                print(f"[ManagerConnMgr] Can't find connector : {change_info.ProcessId}")
                # C++ 원본은 여기서 리턴하지 않고 진행하다가 크래시 날 수 있음 -> Python에서는 안전하게 리턴
                return False

            # 3. 커넥터 상태 확인 (START 상태일 때만 변경 가능)
            # START 상수는 CommType.py에 정의됨
            if conn_info.m_ConnectorInfo.SettingStatus == START:
                # 3-1. 룰 ID 메모리 갱신
                conn_info.m_ConnectorInfo.RuleId = change_info.RuleId
                
                # 3-2. 매니저 프로세스로 명령 전송 (ManagerConnection에 위임)
                if hasattr(con, 'parser_rule_change'):
                    con.parser_rule_change(change_info)
                
                # 3-3. 변경된 정보 전파 (GUI 등)
                if world:
                    world.send_info_change(conn_info.m_ConnectorInfo)
                
                return True
            else:
                print(f"[ManagerConnMgr] Connector({change_info.ProcessId}) Status is STOP")
                return False
        else:
            # 매니저가 연결되어 있지 않음
            msg = f"The Manager({change_info.ManagerId}) does not start."
            if world:
                world.send_ascii_error(1, msg)
            return False
        
    def kill_manager(self, manager_id):
        """
        C++: void KillManager(string ManagerId)
        매니저 프로세스를 SSH를 통해 원격으로 종료 (KillProcess.sh 실행)
        """
        # 1. 매니저 정보 조회
        info = self.find_manager_info(manager_id)

        if info is None:
            print(f"[ManagerConnMgr] Can't Find Manager : {manager_id}")
            return

        # 2. 메인 월드 인스턴스 접근 (스크립트 경로 획득용)
        # 순환 참조 방지를 위해 내부 Import
        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        # 3. 커맨드 생성
        # 예: /home/user/NAA/Script/KillProcess.sh
        cmd = f"{world.get_script_dir()}/KillProcess.sh"

        print(f"[ManagerConnMgr] Kill Manager : {cmd}")

        # 4. SSH 명령 실행 (RunCommand는 이미 구현됨)
        # info.m_ManagerInfo는 AsManagerInfoT 객체임
        self.run_command(
            info.m_ManagerInfo.SshID,
            info.m_ManagerInfo.SshPass,
            info.m_ManagerInfo.IP,
            cmd
        )
        
    def get_router_info(self, req, router_info_list):
        """
        C++: void GetRouterInfo(AS_ROUTER_INFO_REQ_T* Req, RouterInfoList* RouterInfo)
        요청된 장비 ID들에 대한 라우팅 정보(IP, Port)를 수집하여 리스트에 담음
        """
        # req: AsRouterInfoReqT 객체
        # router_info_list: 결과를 담을 리스트 (Reference)

        # 요청된 장비 개수만큼 반복
        # req.equipNo와 actual list length 중 안전한 범위 내에서 순회
        count = min(req.equipNo, len(req.equipIds))

        for i in range(count):
            equip_id = req.equipIds[i]
            
            # 응답 객체 생성 (CommType.py의 AsRouterInfoT)
            info = AsRouterInfoT()
            info.equipId = equip_id
            info.resultMode = 0 # 기본값: 실패(0)

            found = False

            # 연결 리스트 순회 (Thread Safety를 위해 Lock 사용 권장)
            with self.m_Lock:
                for socket in self.m_SocketConnectionList:
                    # 해당 매니저가 이 장비의 커맨드 포트를 가지고 있는지 확인
                    # ManagerConnection.is_has_cmd_port_ne_name
                    if hasattr(socket, 'is_has_cmd_port_ne_name') and \
                       socket.is_has_cmd_port_ne_name(equip_id):
                        
                        print(f"[ManagerConnMgr] Find Equip Id: {equip_id}")
                        
                        info.resultMode = 1 # 성공(1)
                        
                        # IP 주소 (FrSocketSensor.get_peer_ip)
                        # 부모 클래스(FrRdFdSensor)에 m_PeerIp가 있으나 메서드로 접근 권장
                        if hasattr(socket, 'm_PeerIp'):
                            info.ipaddress = socket.m_PeerIp
                        
                        # 라우터 포트 번호 (ManagerConnection.m_RouterPortNo)
                        if hasattr(socket, 'm_RouterPortNo'):
                            info.portNo = socket.m_RouterPortNo
                        
                        router_info_list.append(info)
                        found = True
                        break
            
            # 찾지 못한 경우에도 실패 정보를 담은 객체를 리스트에 추가
            if not found:
                router_info_list.append(info)
                
    def manager_session_identify(self, manager_id):
        """
        C++: void ManagerSessionIdentify(string ManagerId)
        매니저 접속 성공 시: 실행 감시 타이머 취소 및 정리
        """
        # 1. 타이머 맵에서 검색
        if manager_id in self.m_ManagerExecuteTimerMap:
            key_obj = self.m_ManagerExecuteTimerMap[manager_id]
            
            # 2. 타이머 취소
            # (ManagerConnMgr가 FrTimerSensor 기능을 상속받거나 Mixin으로 가지고 있다고 가정)
            if hasattr(self, 'cancel_timer'):
                self.cancel_timer(key_obj.m_Key)
            
            # 3. 맵에서 제거 (C++ delete는 Python GC가 처리)
            del self.m_ManagerExecuteTimerMap[manager_id]
            
        else:
            # 타이머 맵에 없다는 것은 타임아웃이 이미 발생했거나, 
            # 관리되지 않는 매니저가 접속했다는 의미일 수 있음
            print(f"[ManagerConnMgr] Can't Find Manager({manager_id}) in ManagerExecute Timer Map")
            
    def send_data_handler_info_change(self, info):
        """
        C++: void SendDataHandlerInfoChange(AS_DATA_HANDLER_INFO_T* Info)
        모든 매니저 세션에게 데이터 핸들러 정보 변경 알림 전송
        """
        # 1. 패킷 생성 (루프 밖에서 한 번만 직렬화)
        try:
            # info는 AsDataHandlerInfoT 객체 (CommType.py)
            body_data = info.pack()
            
            # AS_DATA_HANDLER_INFO (CommType.py 상수)
            packet = PacketT(AS_DATA_HANDLER_INFO, len(body_data), body_data)
            
            # 2. 브로드캐스팅
            with self.m_Lock:
                for socket in self.m_SocketConnectionList:
                    # AsSocket.packet_send 호출
                    if hasattr(socket, 'packet_send'):
                        socket.packet_send(packet)
                        
        except Exception as e:
            print(f"[ManagerConnMgr] SendDataHandlerInfoChange Error: {e}")
            
    def _recv_manager_info_change(self, info, result_msg=""):
        """
        C++: bool RecvInfoChange(AS_MANAGER_INFO_T* Info, char* ResultMsg)
        매니저 정보 변경 처리 (메모리 갱신)
        """
        # 순환 참조 방지 Import
        from AsciiServerWorld import AsciiServerWorld
        from Class.Common.AsciiServerType import ManagerInfo

        world = AsciiServerWorld._instance

        # ---------------------------------------------------
        # 1. CREATE (INSERT)
        # ---------------------------------------------------
        if info.RequestStatus == CREATE_DATA:
            # 새 매니저 객체 생성
            manager_info = ManagerInfo()
            
            # 정보 복사 (참조 할당)
            manager_info.m_ManagerInfo = info
            
            # 상태 초기화
            manager_info.m_ManagerInfo.CurStatus = STOP
            manager_info.m_ManagerInfo.RequestStatus = WAIT_NO
            
            # 맵에 삽입
            self.m_ManagerInfoMap[info.ManagerId] = manager_info
            
            # GUI 알림
            if world:
                world.send_info_change(manager_info.m_ManagerInfo)
            return True

        # ---------------------------------------------------
        # 2. UPDATE
        # ---------------------------------------------------
        elif info.RequestStatus == UPDATE_DATA:
            # 기존 ID로 검색
            if info.OldManagerId not in self.m_ManagerInfoMap:
                print(f"[ManagerConnMgr] Can't Find Manager : {info.OldManagerId}")
                return False
            
            # 기존 객체 가져오기
            manager_info = self.m_ManagerInfoMap[info.OldManagerId]
            
            # 맵에서 기존 키 삭제 (ID가 바뀔 수 있으므로)
            del self.m_ManagerInfoMap[info.OldManagerId]

            # 정보 갱신
            manager_info.m_ManagerInfo = info
            manager_info.m_ManagerInfo.CurStatus = STOP
            manager_info.m_ManagerInfo.RequestStatus = WAIT_NO
            
            # 새 키로 맵에 삽입
            self.m_ManagerInfoMap[info.ManagerId] = manager_info

            # ID가 변경된 경우, 하위 자식들의 ID도 갱신 (Cascade Update)
            if info.ManagerId != info.OldManagerId:
                # 커넥터 맵 순회
                for conn_info in manager_info.m_ConnectorInfoMap.values():
                    # 커넥터의 ManagerId 갱신
                    conn_info.m_ConnectorInfo.ManagerId = info.ManagerId
                    
                    # 커넥터 하위의 연결(Connection) 리스트 순회
                    for connection in conn_info.m_ConnectionInfoList:
                        connection.ManagerId = info.ManagerId

            # GUI 알림
            if world:
                world.send_info_change(info)
            return True

        # ---------------------------------------------------
        # 3. DELETE
        # ---------------------------------------------------
        elif info.RequestStatus == DELETE_DATA:
            if info.ManagerId not in self.m_ManagerInfoMap:
                print(f"[ManagerConnMgr] Can't Find Manager : {info.ManagerId}")
                return False
            
            # 맵에서 삭제
            # Python GC가 객체를 정리하므로 delete 호출 불필요
            del self.m_ManagerInfoMap[info.ManagerId]
            
            # GUI 알림
            if world:
                world.send_info_change(info)
            return True

        return False
    
    def _recv_connector_info_change(self, info, result_msg):
        """
        C++: bool RecvInfoChange(AS_CONNECTOR_INFO_T* Info, char* ResultMsg)
        커넥터 정보 변경 처리 (메모리 갱신)
        """
        # 순환 참조 방지
        from AsciiServerWorld import AsciiServerWorld
        from Class.Common.AsciiServerType import ConnectorInfo
        
        world = AsciiServerWorld._instance

        # 1. 매니저 찾기
        mgr_info = self.find_manager_info(info.ManagerId)
        if mgr_info is None:
            print(f"[ManagerConnMgr] Can't Find Manager : {info.ManagerId}")
            return False

        # ---------------------------------------------------
        # 1. CREATE
        # ---------------------------------------------------
        if info.RequestStatus == CREATE_DATA:
            # 새 커넥터 객체 생성
            connector_info = ConnectorInfo()
            
            # 정보 복사 (참조 할당 또는 속성 복사)
            # Python은 객체 할당 시 참조가 넘어가므로, 
            # 독립적인 객체가 필요하다면 deepcopy를 고려해야 하나
            # 여기서는 통신 패킷(info)이 임시 객체라고 가정하고 필드를 복사하거나 할당함.
            connector_info.m_ConnectorInfo = info
            
            # 초기 상태 설정
            connector_info.m_ConnectorInfo.CurStatus = STOP
            connector_info.m_ConnectorInfo.RequestStatus = WAIT_NO
            
            # 맵에 삽입
            mgr_info.m_ConnectorInfoMap[info.ConnectorId] = connector_info

            # GUI 알림
            if world:
                world.send_info_change(connector_info.m_ConnectorInfo)
            return True

        # ---------------------------------------------------
        # 2. UPDATE
        # ---------------------------------------------------
        elif info.RequestStatus == UPDATE_DATA:
            # 기존 커넥터 찾기 (전체 검색 혹은 ID 검색)
            connector_info = self.find_connector_info(info.ConnectorId)

            if connector_info is None:
                print(f"[ManagerConnMgr] Can't Find Connector : {info.ConnectorId}")
                return False

            # 기본 정보 갱신
            connector_info.m_ConnectorInfo.RuleId = info.RuleId
            connector_info.m_ConnectorInfo.MmcIdentType = info.MmcIdentType
            connector_info.m_ConnectorInfo.SettingStatus = info.SettingStatus
            connector_info.m_ConnectorInfo.CmdResponseType = info.CmdResponseType

            # [중요] 매니저 이동 로직 (Change Manager)
            # 커넥터가 소속된 매니저가 변경된 경우
            if connector_info.m_ConnectorInfo.ManagerId != info.ManagerId:
                # 1. 이전 매니저 찾기
                old_mgr_info = self.find_manager_info(connector_info.m_ConnectorInfo.ManagerId)
                
                if old_mgr_info is None:
                    print(f"[ManagerConnMgr] Can't Find Manager({connector_info.m_ConnectorInfo.ManagerId})")
                    return False

                # 2. 이전 매니저 맵에서 삭제
                if info.ConnectorId in old_mgr_info.m_ConnectorInfoMap:
                    del old_mgr_info.m_ConnectorInfoMap[info.ConnectorId]
                else:
                    print(f"[ManagerConnMgr] Can't Find Connector in Old Manager map")
                    return False

                # 3. 커넥터 정보의 ManagerID 갱신
                connector_info.m_ConnectorInfo.ManagerId = info.ManagerId

                # 4. 하위 Connection 리스트들의 ManagerID도 일괄 갱신
                for conn in connector_info.m_ConnectionInfoList:
                    conn.ManagerId = info.ManagerId

                # 5. 새 매니저 맵에 삽입 (위에서 찾은 mgr_info 사용)
                mgr_info.m_ConnectorInfoMap[info.ConnectorId] = connector_info

            # 나머지 필드 갱신
            connector_info.m_ConnectorInfo.LogCycle = info.LogCycle
            connector_info.m_ConnectorInfo.ModifyDate = info.ModifyDate
            connector_info.m_ConnectorInfo.LastActionDate = info.LastActionDate
            connector_info.m_ConnectorInfo.LastActionType = info.LastActionType
            connector_info.m_ConnectorInfo.LastActionDesc = info.LastActionDesc
            connector_info.m_ConnectorInfo.Desc = info.Desc
            
            # C++: strcpy(Info->CreateDate, ...); (원본 요청 객체에 생성일자 동기화)
            info.CreateDate = connector_info.m_ConnectorInfo.CreateDate

            # GUI 알림
            if world:
                world.send_info_change(info)
            return True

        # ---------------------------------------------------
        # 3. DELETE
        # ---------------------------------------------------
        elif info.RequestStatus == DELETE_DATA:
            # 맵에서 삭제
            if info.ConnectorId in mgr_info.m_ConnectorInfoMap:
                # Python GC가 객체 메모리 해제를 담당하므로 del만 수행
                del mgr_info.m_ConnectorInfoMap[info.ConnectorId]
                
                # GUI 알림
                if world:
                    world.send_info_change(info)
                return True
            else:
                print(f"[ManagerConnMgr] Can't Find Connector : {info.ConnectorId}")
                return False

        return False
    
    def _recv_connection_info_change(self, info, result_msg=""):
        """
        C++: bool RecvInfoChange(AS_CONNECTION_INFO_T* Info, char* ResultMsg)
        연결 정보 변경 처리 (메모리 갱신)
        """
        # 순환 참조 방지
        from AsciiServerWorld import AsciiServerWorld
        from Class.Common.CommType import AsConnectionInfoT
        
        world = AsciiServerWorld._instance

        # ---------------------------------------------------
        # 1. CREATE
        # ---------------------------------------------------
        if info.RequestStatus == ACT_CREATE:
            # 상위 커넥터 찾기
            connector_info = self.find_connector_info(info.ManagerId, info.ConnectorId)

            if connector_info is None:
                print(f"[ManagerConnMgr] Can't Find Connector Info : {info.ConnectorId}")
                return False

            # 새 연결 객체 생성
            connection_info = AsConnectionInfoT()
            
            # 정보 복사 (memcpy 대체)
            self._copy_connection_info(connection_info, info)
            
            # 초기 상태 설정
            connection_info.CurStatus = STOP
            connection_info.RequestStatus = WAIT_NO
            
            # 리스트에 추가
            connector_info.m_ConnectionInfoList.append(connection_info)
            
            # GUI 알림
            if world:
                world.send_info_change(info)
            return True

        # ---------------------------------------------------
        # 2. UPDATE
        # ---------------------------------------------------
        elif info.RequestStatus == ACT_MODIFY:
            # 기존 연결 정보 찾기 (Sequence로 검색)
            # find_connection_info는 ConnectionMgr에 구현되어 있어야 함
            connection_info = self.find_connection_info(info.Sequence)

            if connection_info is None:
                print(f"[ManagerConnMgr] Can't Find Connection Info : Sequence({info.Sequence})")
                return False

            # 현재 소속된 커넥터 정보 찾기
            connector_info = self.find_connector_info(connection_info.ConnectorId)

            if connector_info is None:
                print(f"[ManagerConnMgr] Can't Find Connector Info : {connection_info.ConnectorId}")
                return False

            # [중요] 커넥터 이동 로직 (Change Connector)
            # 요청 정보의 ConnectorId와 현재 소속된 ConnectorId가 다르면 이동 처리
            if info.ConnectorId != connector_info.m_ConnectorInfo.ConnectorId:
                # 1. 기존 커넥터 리스트에서 삭제
                connector_info.delete_connection_info(info.Sequence)

                # 2. 새로운 커넥터 찾기
                connector_info = self.find_connector_info(info.ConnectorId)
                if connector_info is None:
                    print(f"[ManagerConnMgr] Can't Find Connector Info : {info.ConnectorId}")
                    return False

                # 3. 새 객체 생성 (이동 시 새 리스트에 넣기 위함)
                connection_info = AsConnectionInfoT()
                # 이동된 경우 리스트에 새로 추가해야 함
                connector_info.m_ConnectionInfoList.append(connection_info)

            # 정보 갱신 (memcpy 대체)
            self._copy_connection_info(connection_info, info)
            
            # 상태 초기화
            connection_info.CurStatus = STOP
            connection_info.RequestStatus = WAIT_NO
            
            # GUI 알림
            if world:
                world.send_info_change(info)
            return True

        # ---------------------------------------------------
        # 3. DELETE
        # ---------------------------------------------------
        elif info.RequestStatus == ACT_DELETE:
            # 커넥터 찾기
            connector_info = self.find_connector_info(info.ManagerId, info.ConnectorId)

            if connector_info is None:
                print(f"[ManagerConnMgr] Can't Find Connector Info : {info.ConnectorId}")
                return False

            # 리스트에서 삭제 (Sequence 기준)
            connector_info.delete_connection_info(info.Sequence)
            
            # GUI 알림
            if world:
                world.send_info_change(info)
            return True

        return False

    def _copy_connection_info(self, dest, src):
        """Helper to copy attributes like memcpy"""
        dest.ManagerId = src.ManagerId
        dest.ConnectorId = src.ConnectorId
        dest.AgentEquipId = src.AgentEquipId
        dest.Sequence = src.Sequence
        dest.PortNo = src.PortNo
        dest.ProtocolType = src.ProtocolType
        dest.PortType = src.PortType
        dest.UserId = src.UserId
        dest.UserPassword = src.UserPassword
        dest.GatFlag = src.GatFlag
        dest.CommandPortFlag = src.CommandPortFlag
        # RequestStatus, SettingStatus, CurStatus는 로직에 따라 별도 설정
        
    def connector_desc_change(self, info):
        """
        C++: bool ConnectorDescChange(AS_CONNECTOR_DESC_CHANGE_INFO_T* Info)
        커넥터 설명 정보 변경
        """
        # 순환 참조 방지를 위해 내부 Import
        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        # 1. 커넥터 정보 찾기
        connector_info = self.find_connector_info(info.ManagerId, info.ConnectorId)

        if connector_info is None:
            print(f"[ManagerConnMgr] Can't Find Connector Info : {info.ConnectorId}")
            return False

        # 2. 설명(Desc) 업데이트
        # C++ strcpy 대응
        connector_info.m_ConnectorInfo.Desc = info.Description
        
        # 3. 변경 정보 전파 (GUI 등)
        if world:
            world.send_info_change(connector_info.m_ConnectorInfo)
            
        return True
    
    def recv_init_info(self, init_info):
        """
        C++: void RecvInitInfo(AS_DATA_ROUTING_INIT_T* InitInfo)
        데이터 라우팅 초기화 정보를 모든 매니저 세션에게 브로드캐스트
        (Handler Init은 DataHandlerConnMgr 등 다른 곳에서 처리하므로 제외)
        """
        # 순환 참조 방지를 위해 내부 Import
        from Class.Common.CommType import AsDataRoutingInitT, AS_DATA_ROUTING_INIT, PacketT

        # 타입 확인: 라우팅 초기화 정보가 아니면 무시
        if not isinstance(init_info, AsDataRoutingInitT):
            return

        try:
            # 1. 패킷 생성
            body_data = init_info.pack()
            packet = PacketT(AS_DATA_ROUTING_INIT, len(body_data), body_data)
            
            # 2. 브로드캐스팅 (Thread Safe)
            with self.m_Lock:
                for socket in self.m_SocketConnectionList:
                    if hasattr(socket, 'packet_send'):
                        socket.packet_send(packet)
                        
        except Exception as e:
            print(f"[ManagerConnMgr] RecvInitInfo Error: {e}")
            
    def get_log_status_list(self, log_status_list):
        """
        관리 중인 모든 ManagerConnection에서 로그 상태 수집
        """
        # m_SocketConnectionList는 ConnectionMgr(부모)의 멤버 변수
        for conn in self.m_SocketConnectionList:
            # ManagerConnection 객체인지 확인 후 호출
            if hasattr(conn, 'get_log_status_list'):
                conn.get_log_status_list(log_status_list)
                
    def send_mmc_command_from_status_gui(self, mmc_pub):
        """
        MMC 명령을 적절한 Manager에게 라우팅하거나 처리
        """
        # 예시 구현: 적절한 Manager를 찾아 전송하거나,
        # broadcast 하거나, 특정 로직 수행.
        # C++ 원본 로직에 따라 다르지만, 기본적으로 성공으로 가정하거나 
        # 실제 전송 로직을 구현해야 함.
        
        # 여기서는 임시로 항상 성공 반환
        # 실제로는 find_manager(mmc_pub.ne) -> send_packet(...) 로직 필요
        
        # 예: 타겟 NE가 없으면 에러 반환
        # mgr = self.find_manager_by_ne(mmc_pub.ne)
        # if not mgr: return False, f"Unknown NE: {mmc_pub.ne}"
        
        # mgr.send_mmc_packet(mmc_pub)
        return True, ""