import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 모듈 Import
from Class.Sql.FrDbSession import FrDbSession
from Class.Sql.FrBaseType import EDB_TYPE, E_QUERY_DATA_TYPE
from Class.SqlType.FrDbParam import FrDbParam
from Class.Common.CommType import *
from Class.Common.AsciiServerType import *
from Class.Common.AsUtil import AsUtil
from Class.Common.CommDbType import * # DB 테이블 상수

# -------------------------------------------------------
# DbManager Class
# DB 연결 및 비즈니스 쿼리 수행
# -------------------------------------------------------
class DbManager:
    def __init__(self):
        self.m_DbSession = None
        self.m_DbId = ""
        self.m_DbPass = ""
        self.m_DbTns = ""
        self.m_DbIp = ""
        self.m_DbPort = 0

    def __del__(self):
        if self.m_DbSession:
            self.m_DbSession.disconnect()

    # ---------------------------------------------------
    # Connection Management
    # ---------------------------------------------------
    def init_db_manager(self, user, passwd, tns, ip, port):
        """
        C++: bool InitDbManager(...)
        """
        # DB 세션 생성 (Oracle/MySQL 선택 - 여기서는 Oracle 가정)
        self.m_DbSession = FrDbSession.get_instance(EDB_TYPE.ORACLE)
        
        self.m_DbId = user
        self.m_DbPass = passwd
        self.m_DbTns = tns
        self.m_DbIp = ip
        self.m_DbPort = int(port) if port else 1521

        if not self.m_DbSession.connect(user, passwd, tns, ip, self.m_DbPort):
            print(f"[DbManager] Connect Fail: {self.m_DbSession.get_error()}")
            return False
            
        return True

    def get_db_instance(self):
        """
        C++: bool GetDBInstance() -> Reconnect
        """
        print("[DbManager] Try auto reconnect to db")
        if self.m_DbSession:
            self.m_DbSession.disconnect()
            
        self.m_DbSession = FrDbSession.get_instance(EDB_TYPE.ORACLE)
        if not self.m_DbSession.connect(self.m_DbId, self.m_DbPass, self.m_DbTns, self.m_DbIp, self.m_DbPort):
            print("[DbManager] Reconnect Fail")
            return False
        
        print("[DbManager] Reconnect Success")
        return True

    def execute_query(self, query_or_param, auto_commit=True):
        """
        C++: bool ExecuteQuery(char* Query, bool AutoCommit)
        C++: bool ExecuteQuery(frDbParam* DbParam)
        
        통합 메서드: 입력 타입에 따라 처리
        """
        # 1. 쿼리 문자열 추출 (로깅용)
        query_str = ""
        if isinstance(query_or_param, str):
            query_str = query_or_param
        elif hasattr(query_or_param, 'GetQuery'):
            query_str = query_or_param.GetQuery()

        # print(f"[DbManager] Execute: {query_str}")

        # 2. 메인 서버 인스턴스 가져오기 (MAINPTR 대응)
        # 순환 참조 방지를 위해 내부 Import
        from AsciiServerWorld import AsciiServerWorld
        main_ptr = AsciiServerWorld._instance

        # 3. 세션 확인
        if self.m_DbSession is None:
            print("[DbManager] DB Query Error - DB Error")
            
            # MAINPTR->SendAsciiError(1, ...)
            if main_ptr and hasattr(main_ptr, 'send_ascii_error'):
                main_ptr.send_ascii_error(1, "DB Query Error - DB Error")
            
            # 재연결 시도
            self.get_db_instance()
            return False

        # 4. 실행 (FrDbSession::execute 호출)
        # FrDbSession은 내부적으로 query_or_param 타입을 확인하여 처리함
        if self.m_DbSession.execute(query_or_param, auto_commit=auto_commit):
            return True
        else:
            # 5. 실패 시 처리 로직 (C++ 원본 로직 반영)
            print(f"[DbManager] DB Query Error - {query_str}")
            
            # 재연결 시도
            self.get_db_instance()
            
            # 에러 보고
            if main_ptr and hasattr(main_ptr, 'send_ascii_error'):
                main_ptr.send_ascii_error(1, f"DB Query Error - {query_str}")
            
            # 세션 초기화 (재연결 실패 시 다음 시도에서 다시 접속하도록)
            self.m_DbSession = None
            return False
        
    def commit(self):
        if self.m_DbSession: self.m_DbSession.commit()

    def rollback(self):
        if self.m_DbSession: self.m_DbSession.rollback()
        
    def dis_connection(self):
        """
        C++: void DisConnection()
        DB 연결 해제
        """
        if self.m_DbSession:
            self.m_DbSession.disconnect()

    def get_error_msg(self):
        """
        C++: string GetErrorMsg()
        DB 세션의 에러 메시지 반환. 세션이 없으면 기본 에러 문자열 반환.
        """
        if self.m_DbSession:
            return self.m_DbSession.get_error()
        else:
            return "ERROR DB"

    def get_data_handler_info_find_id(self, info):
        """
        C++: bool GetDataHandlerInfoFindId(AS_DATA_HANDLER_INFO_T* Info)
        ID로 특정 DataHandler의 SSH 접속 정보를 조회하여 Info 객체에 업데이트
        """
        # 쿼리 생성 (DC_EVENT_CONSUMER는 CommDbType.py에 정의됨)
        query = (
            f"SELECT ID, SSHID, SSHPW "
            f"FROM {DC_EVENT_CONSUMER} "
            f"WHERE ID = '{info.DataHandlerId}'"
        )

        self.m_DbParam.SetQuery(query)

        # 쿼리 실행
        if not self.execute_query(self.m_DbParam):
            return False

        # 결과 Fetch
        # C++에서는 Bind 후 Next 루프를 돌고, 마지막 값을 strcpy 함.
        # Python에서는 루프를 돌며 값을 덮어쓰면 동일한 효과.
        while self.m_DbParam.Next():
            rec = self.m_DbParam.get_current_record()
            if rec:
                # SELECT 순서: 0:ID, 1:SSHID, 2:SSHPW
                # C++의 Bind(2, sshid), Bind(3, SshPass)에 대응
                info.SshID = rec.get_value(1)
                info.SshPass = rec.get_value(2)

        self.m_DbParam.Clear()
        return True
    
    # ---------------------------------------------------
    # Business Queries
    # ---------------------------------------------------
    def get_manager_info(self, info_map):
        """
        C++: bool GetManagerInfo(ManagerInfoMap* InfoMap)
        매니저, 커넥터, 커넥션 정보를 조회하여 계층 구조로 메모리에 적재
        """
        # -------------------------------------------------------
        # 1. 매니저 정보 조회 (DC_CNF_MANAGER)
        # -------------------------------------------------------
        query = f"SELECT ID, IP, STATUS, SSHID, SSHPW FROM {DC_CNF_MANAGER}"
        self.m_DbParam.SetQuery(query)

        if not self.execute_query(self.m_DbParam):
            return False

        # Python에서는 Bind 대신 Next 루프 내에서 get_value(index) 사용
        # 0:ID, 1:IP, 2:STATUS, 3:SSHID, 4:SSHPW
        self.m_DbParam.Rewind()
        while self.m_DbParam.Next():
            rec = self.m_DbParam.get_current_record()
            if not rec: continue

            mgr_id = rec.get_value(0)
            
            manager_info = ManagerInfo()
            # AsManagerInfoT 객체 (m_ManagerInfo는 멤버 변수)
            manager_info.m_ManagerInfo = AsManagerInfoT()
            manager_info.m_ManagerInfo.ManagerId = mgr_id
            manager_info.m_ManagerInfo.IP = rec.get_value(1)
            
            try: manager_info.m_ManagerInfo.SettingStatus = int(rec.get_value(2))
            except: manager_info.m_ManagerInfo.SettingStatus = 0
                
            manager_info.m_ManagerInfo.SshID = rec.get_value(3)
            manager_info.m_ManagerInfo.SshPass = rec.get_value(4)
            
            manager_info.m_ManagerInfo.CurStatus = STOP
            manager_info.m_ManagerInfo.RequestStatus = WAIT_NO

            # 맵에 등록
            info_map[mgr_id] = manager_info

        self.m_DbParam.Clear()

        # -------------------------------------------------------
        # 2. 커넥터 및 연결 정보 조회 (JOIN Query)
        # -------------------------------------------------------
        # 날짜 포맷은 DB 타입에 따라 달라질 수 있으나, 여기서는 원본 쿼리 구조를 따름
        # DATE_FORMAT 함수는 MySQL 전용일 수 있음. Oracle은 TO_CHAR 사용 필요.
        date_fmt = "'%Y/%m/%d %H:%i:%s'" # MySQL Style
        if self.m_DbSession.get_db_type() == EDB_TYPE.ORACLE:
            date_fmt = "'YYYY/MM/DD HH24:MI:SS'" # Oracle Style

        query = (
            f"SELECT CR.GATEWAYID, CM.IP, CM.STATUS, CR.ID, CR.STATUS, CR.RULEID, RI.IDENTIFICATIONTYPE, CR.JUNCTIONTYPE, "
            f"CC.SEQUENCE, CC.AGENTEQUIPID, CC.PROTOCOLTYPE, CC.PORTTYPE, CC.AGENTPORTNO, CC.USERID, "
            f"CC.PASSWORD, CC.GATFLAG, CC.COMMANDFLAG, CC.STATUS, CR.CMDRESPONSETYPE, CR.LOGCYCLE, "
            # 날짜 포맷팅 함수는 DB별로 다를 수 있어 추상화 필요하지만 여기서는 문자열 치환으로 처리
            f"TO_CHAR(CR.CREATE_DATE, {date_fmt}), "
            f"TO_CHAR(CR.MODIFY_DATE, {date_fmt}), "
            f"TO_CHAR(CR.LAST_ACTION_DATE, {date_fmt}), "
            f"CR.LAST_ACTION, CR.LAST_ACTION_DESC, CR.DESCRIPTION, HD.CURRENTEQUIPID "
            f"FROM {DC_CNF_CONNECTOR} CR "
            f"INNER JOIN {DC_CNF_MANAGER} CM ON CR.GATEWAYID = CM.ID "
            f"INNER JOIN {DC_RUL_RULE} RI ON CR.RULEID = RI.ID "
            f"INNER JOIN {TBD_EQP_HOSTHW} HD ON CR.ID = HD.EQUIPID "
            f"LEFT JOIN {DC_CNF_CONNECTION} CC ON CR.ID = CC.CONNECTORID "
            f"ORDER BY CR.GATEWAYID, HD.CURRENTEQUIPID, CC.PROTOCOLTYPE, CC.AGENTPORTNO, CC.PORTTYPE"
        )
        
        # MySQL인 경우 TO_CHAR -> DATE_FORMAT으로 변경 (간단한 호환성 처리)
        if self.m_DbSession.get_db_type() == EDB_TYPE.MYSQL:
            query = query.replace("TO_CHAR", "DATE_FORMAT")

        self.m_DbParam.SetQuery(query)

        if not self.execute_query(self.m_DbParam):
            return False

        self.m_DbParam.Rewind()
        while self.m_DbParam.Next():
            rec = self.m_DbParam.get_current_record()
            if not rec: continue

            # 인덱스 매핑
            # 0:MgrId, 1:IP, 2:MgrStatus, 3:ConnId, 4:ConnStatus, 5:RuleId, 6:MmcIdentType, 7:JunctionType
            # 8:Seq, 9:AgentEqId, 10:ProtoType, 11:PortType, 12:PortNo, 13:UserId, 
            # 14:Passwd, 15:GatFlag, 16:CmdFlag, 17:CcStatus, 18:CmdRespType, 19:LogCycle
            # 20:CreateDate, 21:ModDate, 22:LastActionDate, 23:LastAction, 24:LastActionDesc, 25:Desc
            
            mgr_id = rec.get_value(0)
            conn_id = rec.get_value(3)
            
            # 매니저 찾기
            if mgr_id not in info_map:
                print(f"[DbManager] Can't Find Manager : {mgr_id}")
                continue
            
            manager_info = info_map[mgr_id]

            # 커넥터 찾기 (없으면 생성)
            if conn_id not in manager_info.m_ConnectorInfoMap:
                connector_info = ConnectorInfo()
                
                # 기본 정보 설정
                connector_info.m_ConnectorInfo = AsConnectorInfoT()
                connector_info.m_ConnectorInfo.ManagerId = mgr_id
                connector_info.m_ConnectorInfo.ConnectorId = conn_id
                connector_info.m_ConnectorInfo.RuleId = rec.get_value(5)
                
                try: connector_info.m_ConnectorInfo.SettingStatus = int(rec.get_value(4))
                except: connector_info.m_ConnectorInfo.SettingStatus = 0
                
                connector_info.m_ConnectorInfo.CurStatus = STOP
                connector_info.m_ConnectorInfo.RequestStatus = WAIT_NO
                
                try: connector_info.m_ConnectorInfo.MmcIdentType = int(rec.get_value(6))
                except: connector_info.m_ConnectorInfo.MmcIdentType = 0

                try: connector_info.m_ConnectorInfo.JunctionType = int(rec.get_value(7))
                except: connector_info.m_ConnectorInfo.JunctionType = 0
                    
                try: connector_info.m_ConnectorInfo.CmdResponseType = int(rec.get_value(18))
                except: connector_info.m_ConnectorInfo.CmdResponseType = 0
                    
                try: connector_info.m_ConnectorInfo.LogCycle = int(rec.get_value(19))
                except: connector_info.m_ConnectorInfo.LogCycle = 0
                
                connector_info.m_ConnectorInfo.CreateDate = rec.get_value(20)
                connector_info.m_ConnectorInfo.ModifyDate = rec.get_value(21)
                connector_info.m_ConnectorInfo.LastActionDate = rec.get_value(22)
                connector_info.m_ConnectorInfo.LastActionType = rec.get_value(23)
                connector_info.m_ConnectorInfo.LastActionDesc = rec.get_value(24)
                connector_info.m_ConnectorInfo.Desc = rec.get_value(25)
                
                # 맵에 등록
                manager_info.m_ConnectorInfoMap[conn_id] = connector_info
                
                # 로그 출력
                # print(f"Connector Status : {mgr_id}/{conn_id}[{connector_info.m_ConnectorInfo.SettingStatus}]")

            else:
                connector_info = manager_info.m_ConnectorInfoMap[conn_id]

            # 연결 정보(Connection) 추가 (LEFT JOIN이므로 NULL일 수 있음)
            seq_str = rec.get_value(8)
            if not seq_str: # Sequence가 없으면 연결 정보 없음
                continue
                
            try: sequence = int(seq_str)
            except: sequence = 0
            
            if sequence == 0: continue

            connection_info = AsConnectionInfoT()
            connection_info.ManagerId = mgr_id
            connection_info.ConnectorId = conn_id
            connection_info.Sequence = sequence
            connection_info.AgentEquipId = rec.get_value(9)
            
            try: connection_info.ProtocolType = int(rec.get_value(10))
            except: connection_info.ProtocolType = 0
            
            try: connection_info.PortType = int(rec.get_value(11))
            except: connection_info.PortType = 0
                
            try: connection_info.PortNo = int(rec.get_value(12))
            except: connection_info.PortNo = 0
            
            connection_info.UserId = rec.get_value(13)
            connection_info.UserPassword = rec.get_value(14)
            
            try: connection_info.GatFlag = int(rec.get_value(15))
            except: connection_info.GatFlag = 0
                
            try: connection_info.CommandPortFlag = int(rec.get_value(16))
            except: connection_info.CommandPortFlag = 0
                
            try: connection_info.SettingStatus = int(rec.get_value(17))
            except: connection_info.SettingStatus = 0

            connection_info.CurStatus = UNDEFINED
            connection_info.RequestStatus = WAIT_NO

            # 리스트에 추가
            connector_info.m_ConnectionInfoList.append(connection_info)

        self.m_DbParam.Clear()
        return True
    
    # ---------------------------------------------------
    # Data Handler Info Logic
    # ---------------------------------------------------
    def get_data_handler_info(self, info_map):
        """
        C++: bool GetDataHandlerInfo(DataHandlerInfoMap* InfoMap)
        """
        # 쿼리 구성
        query = (
            f"SELECT ID, DBUSERID, DBPASSWORD , DBTNS, HOSTNAME, TIMEMODE, LISTENPORT, "
            f"STATUS, LOGMODE, IPADDRESS, BYPASSLISTENPORT, LOADINGINTERVAL, HANDLERMODE, "
            f"TARGETINFO, RUNMODE, LOGCYCLE, SSHID, SSHPW "
            f"FROM {DC_EVENT_CONSUMER}"
        )

        self.m_DbParam.SetQuery(query)

        if not self.execute_query(self.m_DbParam):
            return False

        # 파싱 루프
        self.m_DbParam.Rewind()
        while self.m_DbParam.Next():
            rec = self.m_DbParam.get_current_record()
            
            # CommType.py에 정의된 구조체 객체 생성
            info = AsDataHandlerInfoT()
            
            # 컬럼 인덱스별 매핑 (0부터 시작)
            info.DataHandlerId = rec.get_value(0)
            info.DbUserId = rec.get_value(1)
            info.DbPassword = rec.get_value(2)
            info.DbName = rec.get_value(3) # DBTNS -> DbName 매핑
            info.HostName = rec.get_value(4)
            
            # 정수형 변환 (Safe casting)
            try: info.TimeMode = int(rec.get_value(5))
            except: info.TimeMode = 0
                
            try: info.ListenPort = int(rec.get_value(6))
            except: info.ListenPort = 0
            
            try: info.SettingStatus = int(rec.get_value(7)) # STATUS
            except: info.SettingStatus = 0
            
            try: info.LogMode = int(rec.get_value(8))
            except: info.LogMode = 0
                
            info.IpAddress = rec.get_value(9)
            
            try: info.BypassListenPort = int(rec.get_value(10))
            except: info.BypassListenPort = 0
                
            try: info.LoadingInterval = int(rec.get_value(11))
            except: info.LoadingInterval = 0
                
            try: info.OperMode = int(rec.get_value(12)) # HANDLERMODE
            except: info.OperMode = 0
                
            target_info_str = rec.get_value(13)
            
            try: info.RunMode = int(rec.get_value(14))
            except: info.RunMode = 0
                
            try: info.LogCycle = int(rec.get_value(15))
            except: info.LogCycle = 0
                
            info.SshID = rec.get_value(16)
            info.SshPass = rec.get_value(17)

            # 기본값 설정 (C++ 로직)
            info.CurStatus = STOP
            info.RequestStatus = WAIT_NO

            # TargetInfo 파싱 (String -> Struct List)
            self.get_string_to_ip_info(target_info_str, info.TargetIpInfoList)

            # 맵에 삽입
            info_map[info.DataHandlerId] = info
            
        self.m_DbParam.Clear()
        return True

    # ---------------------------------------------------
    # Helper Methods for IP Info Parsing
    # ---------------------------------------------------
    def get_string_to_ip_info(self, target_info, info_list_obj):
        """
        C++: bool GetStringToIpInfo(string TargetInfo, AS_TARGET_IP_INFO_LIST_T& InfoList)
        Format: "IP:Port|IP:Port|" -> List 구조체로 변환
        """
        if not target_info: return False

        # 리스트 초기화
        info_list_obj.TargetIpInfo = []
        info_list_obj.Size = 0
        
        # 파이프(|)로 구분
        items = target_info.split('|')
        
        for item in items:
            item = item.strip()
            if not item: continue
            
            # 콜론(:)으로 IP/Port 구분
            if ':' in item:
                parts = item.split(':')
                if len(parts) >= 2:
                    ip = parts[0]
                    port_str = parts[1]
                    
                    try:
                        port = int(port_str)
                        
                        # AsTargetIpInfoT 객체 생성 및 추가
                        t_info = AsTargetIpInfoT()
                        t_info.IpAddress = ip
                        t_info.PortNo = port
                        
                        info_list_obj.TargetIpInfo.append(t_info)
                    except ValueError:
                        print(f"[DbManager] Invalid port in target info: {item}")

        # Size 갱신
        info_list_obj.Size = len(info_list_obj.TargetIpInfo)
        return True

    def get_ip_info_to_string(self, info_list_obj):
        """
        C++: string GetIpInfoToString(AS_TARGET_IP_INFO_LIST_T& InfoList)
        List 구조체 -> "IP:Port|..." 문자열로 변환
        (RecvInfoChange에서 사용됨)
        """
        result = ""
        # info_list_obj는 AsTargetIpInfoListT 객체
        for info in info_list_obj.TargetIpInfo:
            result += f"{info.IpAddress}:{info.PortNo}|"
        return result
    
    def update_manager_status(self, manager_id, status, desc):
        """
        C++: bool UpdateManagerStatus(...)
        """
        # Enum -> Int
        st_val = START if status == START else STOP
        
        query = (f"UPDATE {DC_CNF_MANAGER} SET STATUS = {st_val}, DESCRIPTION = '{desc}' "
                 f"WHERE ID = '{manager_id}'")
        return self.execute_query(query)

    def get_connection_ip_info(self, ip_info_map, connector_id, sequence=-1):
        """
        C++: bool GetConnectionIpInfo(...)
        """
        if sequence == -1:
            query = (f"SELECT DISTINCT CC.SEQUENCE, HW.IP "
                     f"FROM {DC_CNF_CONNECTION} CC, {TBD_EQP_HOSTHW} HW "
                     f"WHERE CC.AGENTEQUIPID = HW.AGENTEQUIPID AND CC.CONNECTORID = '{connector_id}'")
        else:
            query = (f"SELECT DISTINCT CC.SEQUENCE, HW.IP "
                     f"FROM {DC_CNF_CONNECTION} CC, {TBD_EQP_HOSTHW} HW "
                     f"WHERE CC.AGENTEQUIPID = HW.AGENTEQUIPID AND CC.CONNECTORID = '{connector_id}' "
                     f"AND CC.SEQUENCE = {sequence}")
                     
        param = FrDbParam(query)
        if not self.execute_query(param): return False
        
        param.Rewind()
        while param.Next():
            seq = int(param.get_str(0))
            ip = param.get_str(1)
            ip_info_map[seq] = ip
            
        return True

    def insert_mmc_result(self, result_stored):
        """
        C++: bool InsertMMCResult(MMCResultStored* Result)
        MMC 결과 저장 (BLOB 처리 포함)
        """
        # String Escape (' -> '')
        msg = result_stored.ResultMsg.replace("'", "''")
        
        query = (
            f"INSERT INTO {DC_MMC_RESULT} (EQUIPID, GID, EXTID, RESULTMODE, USERID, ... COMMAND) "
            f"VALUES ('{result_stored.MmcInfo.ne}', {result_stored.Gid}, {result_stored.ExtId}, ... )"
        )
        
        if self.execute_query(query, False): # AutoCommit=False
            # CLOB 업데이트 (UpdateLong)
            where_clause = f"GID = {result_stored.Gid}"
            if self.m_DbSession.update_long(DC_MMC_RESULT, "RESULTMSG", msg, where_clause):
                self.commit()
                return True
            else:
                self.rollback()
                return False
        return False

    # ---------------------------------------------------
    # Utils
    # ---------------------------------------------------
    def get_current_msg_id(self):
        """
        C++: bool GetCurrentMsgId()
        """
        return 1 # 시퀀스 조회 등 구현

    def delete_connection_status(self):
        """
        C++: bool DeleteConnectionStatus()
        DC_STATUS_CMD_PORT 테이블 전체 삭제 (초기화)
        """
        # DC_STATUS_CMD_PORT는 CommDbType.py에 정의됨
        query = f"DELETE FROM {DC_STATUS_CMD_PORT}"

        if not self.execute_query(query):
            print("[DbManager] DeleteConnectionStatus error")
            return False
            
        return True

    # ---------------------------------------------------
    # Info Change Handlers (Dispatch)
    # ---------------------------------------------------
    def recv_info_change(self, info):
        """
        C++: bool RecvInfoChange(...) 오버로딩 통합
        """
        # 타입에 따라 적절한 핸들러 호출
        if isinstance(info, AsConnectorInfoT):
            return self._recv_connector_info_change(info)
        elif isinstance(info, AsManagerInfoT):
            return self._recv_manager_info_change(info)
        # ... 다른 타입들 추가 ...
        
        return False

    # ---------------------------------------------------
    # Specific Handlers
    # ---------------------------------------------------
    def _recv_connector_info_change(self, info):
        """
        C++: bool RecvInfoChange(AS_CONNECTOR_INFO_T* Info)
        커넥터 정보 변경 처리 (Create / Update / Delete)
        """
        if not self.m_DbSession:
            print("[DbManager] DB Connection Fail !!")
            self.get_db_instance()
            return False

        # 날짜 포맷팅 (C++ MakeInsertQuery 대응)
        # E_QUERY_DATA_TYPE.DATE는 FrBaseType.py에 정의되어 있어야 함
        cur_time_query = self.m_DbSession.make_insert_query(E_QUERY_DATA_TYPE.DATE, info.LastActionDate)
        create_date_q = self.m_DbSession.make_insert_query(E_QUERY_DATA_TYPE.DATE, info.CreateDate)
        modify_date_q = self.m_DbSession.make_insert_query(E_QUERY_DATA_TYPE.DATE, info.ModifyDate)

        # ---------------------------------------------------
        # 1. CREATE (INSERT)
        # ---------------------------------------------------
        if info.RequestStatus == ACT_CREATE:
            action_str = AsUtil.get_action_type_string(ACT_CREATE)
            query = (
                f"INSERT INTO {DC_CNF_CONNECTOR} "
                f"(ID, GATEWAYID, RULEID, STATUS, JUNCTIONTYPE, CMDRESPONSETYPE, LOGCYCLE, "
                f"CREATE_DATE, MODIFY_DATE, LAST_ACTION_DATE, LAST_ACTION ) "
                f"VALUES "
                f"('{info.ConnectorId}', '{info.ManagerId}', '{info.RuleId}', "
                f"{info.SettingStatus}, {info.JunctionType}, {info.CmdResponseType}, {info.LogCycle}, "
                f"{create_date_q}, {modify_date_q}, {cur_time_query}, '{action_str}' )"
            )

            if not self.execute_query(query):
                print(f"[DbManager] Connector Create({info.ConnectorId}) Error")
                return False
            return True

        # ---------------------------------------------------
        # 2. UPDATE
        # ---------------------------------------------------
        elif info.RequestStatus == ACT_MODIFY:
            action_str = AsUtil.get_action_type_string(ACT_MODIFY)
            query = (
                f"UPDATE {DC_CNF_CONNECTOR} SET "
                f"GATEWAYID = '{info.ManagerId}', RULEID = '{info.RuleId}', "
                f"STATUS = {info.SettingStatus}, CMDRESPONSETYPE = {info.CmdResponseType}, "
                f"LOGCYCLE = {info.LogCycle}, "
                f"MODIFY_DATE = {modify_date_q}, LAST_ACTION_DATE = {cur_time_query}, "
                f"LAST_ACTION = '{action_str}', DESCRIPTION = '{info.Desc}', "
                f"LAST_ACTION_DESC = '{info.LastActionDesc}' "
                f"WHERE ID = '{info.ConnectorId}'"
            )

            if not self.execute_query(query):
                print(f"[DbManager] Connector Update({info.ConnectorId}) Error")
                return False
            return True

        # ---------------------------------------------------
        # 3. DELETE
        # ---------------------------------------------------
        elif info.RequestStatus == ACT_DELETE:
            # 3-1. 하위 연결(Connection) 삭제 (AutoCommit=False)
            q1 = f"DELETE FROM {DC_CNF_CONNECTION} WHERE CONNECTORID = '{info.ConnectorId}'"
            if not self.execute_query(q1, False):
                print(f"[DbManager] Connection Delete({info.ConnectorId}) Error")
                return False

            # 3-2. 커넥터 삭제
            q2 = f"DELETE FROM {DC_CNF_CONNECTOR} WHERE ID = '{info.ConnectorId}'"
            if not self.execute_query(q2, False):
                self.rollback()
                print(f"[DbManager] Connector Delete({info.ConnectorId}) Error")
                return False
            
            # 삭제 성공 시 커밋
            self.commit()

            # 3-3. 삭제 이력 저장 (DC_CNF_CONNECTOR_DELETED)
            # 메모리(AsciiServerWorld)에서 현재 정보를 가져옴
            from AsciiServerWorld import AsciiServerWorld
            world = AsciiServerWorld._instance
            
            # conInfo는 ConnectorInfo 객체
            con_info = world.get_connector_info(info.ConnectorId)

            if con_info:
                # 기존 정보의 날짜 쿼리 생성
                old_create_q = self.m_DbSession.make_insert_query(E_QUERY_DATA_TYPE.DATE, con_info.m_ConnectorInfo.CreateDate)
                old_mod_q = self.m_DbSession.make_insert_query(E_QUERY_DATA_TYPE.DATE, con_info.m_ConnectorInfo.ModifyDate)
                
                # 현재 시간 함수 (DB 종속성 처리)
                sysdate_q = "SYSDATE" if self.m_DbSession.get_db_type() == EDB_TYPE.ORACLE else "NOW()"

                history_query = (
                    f"INSERT INTO {DC_CNF_CONNECTOR_DELETED} "
                    f"(ID, GATEWAYID, RULEID, DESCRIPTION, CREATE_DATE, MODIFY_DATE, DELETE_DATE) "
                    f"VALUES "
                    f"('{con_info.m_ConnectorInfo.ConnectorId}', '{con_info.m_ConnectorInfo.ManagerId}', "
                    f"'{con_info.m_ConnectorInfo.RuleId}', '{info.Desc}', "
                    f"{old_create_q}, {old_mod_q}, {sysdate_q})"
                )

                if not self.execute_query(history_query):
                    print(f"[DbManager] ERROR Insert {DC_CNF_CONNECTOR_DELETED} : {info.ConnectorId}")
                    return False
            else:
                print(f"[DbManager] ERROR Insert {DC_CNF_CONNECTOR_DELETED} , Can't find connector info")
            
            return True

        return False

    def _recv_manager_info_change(self, info):
        """
        C++: bool RecvInfoChange(AS_MANAGER_INFO_T* Info)
        매니저 정보 변경에 따른 DB 업데이트 (Cascade 처리 포함)
        """
        if not self.m_DbSession:
            print("[DbManager] DB Connection Fail !!")
            self.get_db_instance()
            return False

        # 1. CREATE (INSERT)
        if info.RequestStatus == CREATE_DATA:
            query = (
                f"INSERT INTO {DC_CNF_MANAGER} (ID, IP, STATUS, SSHID, SSHPW) "
                f"VALUES "
                f"('{info.ManagerId}', '{info.IP}', {info.SettingStatus}, '{info.SshID}', '{info.SshPass}')"
            )

            if not self.execute_query(query):
                print(f"[DbManager] Manager Create({info.ManagerId}) Error")
                return False
            return True

        # 2. UPDATE
        elif info.RequestStatus == UPDATE_DATA:
            # 트랜잭션 시작 (AutoCommit=False)
            
            # 2-1. Connector 테이블의 GATEWAYID(ManagerId) 업데이트 (FK 관계 유지)
            q1 = (
                f"UPDATE {DC_CNF_CONNECTOR} SET GATEWAYID = '{info.ManagerId}' "
                f"WHERE GATEWAYID = '{info.OldManagerId}'"
            )

            if not self.execute_query(q1, False):
                print(f"[DbManager] Manager Update({info.OldManagerId}) Error - Connector Update Fail")
                return False

            # 2-2. Manager 테이블 본체 업데이트
            q2 = (
                f"UPDATE {DC_CNF_MANAGER} SET "
                f"ID = '{info.ManagerId}', IP = '{info.IP}', STATUS = {info.SettingStatus}, "
                f"SSHID = '{info.SshID}', SSHPW = '{info.SshPass}' "
                f"WHERE ID = '{info.OldManagerId}'"
            )

            if not self.execute_query(q2, False):
                self.rollback()
                print(f"[DbManager] Manager Update({info.OldManagerId}) Error - Manager Update Fail")
                return False
            
            self.commit()
            return True

        # 3. DELETE
        elif info.RequestStatus == DELETE_DATA:
            # 트랜잭션 시작 (AutoCommit=False)

            # 3-1. 해당 매니저 하위의 모든 Connection 삭제 (Cascade)
            # (Subquery 사용: Connector가 해당 Manager에 속한 경우)
            q1 = (
                f"DELETE FROM {DC_CNF_CONNECTION} "
                f"WHERE CONNECTORID IN (SELECT ID FROM {DC_CNF_CONNECTOR} WHERE GATEWAYID = '{info.ManagerId}')"
            )

            if not self.execute_query(q1, False):
                print(f"[DbManager] Connection Delete({info.ManagerId}) Error")
                return False

            # 3-2. 해당 매니저 하위의 모든 Connector 삭제
            q2 = f"DELETE FROM {DC_CNF_CONNECTOR} WHERE GATEWAYID = '{info.ManagerId}'"
            
            if not self.execute_query(q2, False):
                self.rollback()
                print(f"[DbManager] Connector Delete({info.ManagerId}) Error")
                return False

            # 3-3. Manager 삭제
            q3 = f"DELETE FROM {DC_CNF_MANAGER} WHERE ID = '{info.ManagerId}'"

            if not self.execute_query(q3, False):
                self.rollback()
                print(f"[DbManager] Manager Delete({info.ManagerId}) Error")
                return False
            
            self.commit()
            return True

        return False
    
    def _recv_connection_info_change(self, info):
        """
        C++: bool RecvInfoChange(AS_CONNECTION_INFO_T* Info)
        연결 정보(Connection) 변경 처리 (Create / Update / Delete)
        """
        if not self.m_DbSession:
            print("[DbManager] DB Connection Fail !!")
            self.get_db_instance()
            return False

        # ---------------------------------------------------
        # 1. CREATE (INSERT)
        # ---------------------------------------------------
        if info.RequestStatus == CREATE_DATA:
            # 1-1. Max Sequence 조회
            query = f"SELECT MAX(SEQUENCE) FROM {DC_CNF_CONNECTION}"
            
            # 임시 파라미터 객체 사용
            param = FrDbParam(query)
            if not self.execute_query(param):
                return False

            max_sequence = 0
            if param.Next():
                rec = param.get_current_record()
                if rec:
                    val = rec.get_value(0)
                    # DB에서 NULL이나 None이 올 경우 처리
                    if val and val.lower() != 'none':
                        try: max_sequence = int(val)
                        except: max_sequence = 0
            
            info.Sequence = max_sequence + 1

            # 1-2. Insert 쿼리
            # C++의 IF('%s'='','','%s') 로직은 Python f-string에서 직접 처리
            pwd_val = info.UserPassword if info.UserPassword else ""

            query = (
                f"INSERT INTO {DC_CNF_CONNECTION} "
                f"(SEQUENCE, CONNECTORID, AGENTEQUIPID, PROTOCOLTYPE, PORTTYPE, "
                f"AGENTPORTNO, USERID, PASSWORD, GATFLAG, STATUS, COMMANDFLAG ) "
                f"VALUES "
                f"({info.Sequence}, '{info.ConnectorId}', '{info.AgentEquipId}', "
                f"{info.ProtocolType}, {info.PortType}, {info.PortNo}, "
                f"'{info.UserId}', '{pwd_val}', {info.GatFlag}, "
                f"{info.SettingStatus}, {info.CommandPortFlag})"
            )

            if not self.execute_query(query):
                print(f"[DbManager] Connection Create({info.Sequence}) Error")
                return False
            
            return True

        # ---------------------------------------------------
        # 2. UPDATE
        # ---------------------------------------------------
        elif info.RequestStatus == UPDATE_DATA:
            query = (
                f"UPDATE {DC_CNF_CONNECTION} SET "
                f"CONNECTORID = '{info.ConnectorId}', "
                f"AGENTEQUIPID = '{info.AgentEquipId}', "
                f"PROTOCOLTYPE = {info.ProtocolType}, "
                f"PORTTYPE = {info.PortType}, "
                f"AGENTPORTNO = {info.PortNo}, "
                f"USERID = '{info.UserId}', "
                f"PASSWORD = '{info.UserPassword}', "
                f"GATFLAG = {info.GatFlag}, "
                f"STATUS = {info.SettingStatus}, "
                f"COMMANDFLAG = {info.CommandPortFlag} "
                f"WHERE SEQUENCE = {info.Sequence}"
            )

            if not self.execute_query(query):
                print(f"[DbManager] Connection Update({info.Sequence}) Error")
                return False
            return True

        # ---------------------------------------------------
        # 3. DELETE
        # ---------------------------------------------------
        elif info.RequestStatus == DELETE_DATA:
            query = f"DELETE FROM {DC_CNF_CONNECTION} WHERE SEQUENCE = {info.Sequence}"

            if not self.execute_query(query):
                print(f"[DbManager] Connection Delete({info.Sequence}) Error")
                return False
            return True

        return False
    
    def _recv_data_handler_info_change(self, info):
        """
        C++: bool RecvInfoChange(AS_DATA_HANDLER_INFO_T* Info)
        데이터 핸들러 정보 변경 (DC_EVENT_CONSUMER 테이블)
        """
        if not self.m_DbSession:
            print("[DbManager] DB Connection Fail !!")
            self.get_db_instance()
            return False

        # 1. 타겟 IP 리스트를 문자열로 변환 (127.0.0.1:8080|...)
        # (이미 구현된 get_ip_info_to_string 헬퍼 메서드 사용)
        target_info = self.get_ip_info_to_string(info.TargetIpInfoList)

        # 2. 현재 시간 함수 결정 (DB 타입에 따라 NOW() 또는 SYSDATE)
        time_func = "SYSDATE" if self.m_DbSession.get_db_type() == EDB_TYPE.ORACLE else "NOW()"

        # ---------------------------------------------------
        # 1. CREATE (INSERT)
        # ---------------------------------------------------
        if info.RequestStatus == CREATE_DATA:
            query = (
                f"INSERT INTO {DC_EVENT_CONSUMER} "
                f"(ID, DBUSERID, DBPASSWORD, DBTNS, HOSTNAME, TIMEMODE, LISTENPORT, "
                f"STATUS, LOGMODE, IPADDRESS, BYPASSLISTENPORT, LOADINGINTERVAL, "
                f"HANDLERMODE, TARGETINFO, RUNMODE, LOGCYCLE, SSHID, SSHPW, MODIFY_DATE) "
                f"VALUES "
                f"('{info.DataHandlerId}', '{info.DbUserId}', '{info.DbPassword}', '{info.DbName}', "
                f"'{info.HostName}', {info.TimeMode}, {info.ListenPort}, "
                f"{info.SettingStatus}, {info.LogMode}, '{info.IpAddress}', "
                f"{info.BypassListenPort}, {info.LoadingInterval}, {info.OperMode}, "
                f"'{target_info}', {info.RunMode}, {info.LogCycle}, "
                f"'{info.SshID}', '{info.SshPass}', {time_func})"
            )

            if not self.execute_query(query):
                print(f"[DbManager] Data Handler Create({info.DataHandlerId}) Error")
                return False
            return True

        # ---------------------------------------------------
        # 2. UPDATE
        # ---------------------------------------------------
        elif info.RequestStatus == UPDATE_DATA:
            query = (
                f"UPDATE {DC_EVENT_CONSUMER} SET "
                f"ID = '{info.DataHandlerId}', "
                f"DBUSERID = '{info.DbUserId}', "
                f"DBPASSWORD = '{info.DbPassword}', "
                f"DBTNS = '{info.DbName}', "
                f"HOSTNAME = '{info.HostName}', "
                f"TIMEMODE = {info.TimeMode}, "
                f"LISTENPORT = {info.ListenPort}, "
                f"STATUS = {info.SettingStatus}, "
                f"LOGMODE = {info.LogMode}, "
                f"IPADDRESS = '{info.IpAddress}', "
                f"BYPASSLISTENPORT = {info.BypassListenPort}, "
                f"LOADINGINTERVAL = {info.LoadingInterval}, "
                f"HANDLERMODE = {info.OperMode}, "
                f"TARGETINFO = '{target_info}', "
                f"RUNMODE = {info.RunMode}, "
                f"LOGCYCLE = {info.LogCycle}, "
                f"SSHID = '{info.SshID}', "
                f"SSHPW = '{info.SshPass}', "
                f"MODIFY_DATE = {time_func} "
                f"WHERE ID = '{info.OldDataHandlerId}'"
            )

            if not self.execute_query(query):
                print(f"[DbManager] Data Handler Update({info.OldDataHandlerId}) Error")
                return False
            return True

        # ---------------------------------------------------
        # 3. DELETE
        # ---------------------------------------------------
        elif info.RequestStatus == DELETE_DATA:
            query = f"DELETE FROM {DC_EVENT_CONSUMER} WHERE ID = '{info.DataHandlerId}'"
            
            if not self.execute_query(query):
                print(f"[DbManager] Data Handler Delete({info.DataHandlerId}) Error")
                return False
            return True

        return False
    
    def _recv_sub_proc_info_change(self, info):
        """
        C++: bool RecvInfoChange(AS_SUB_PROC_INFO_T* Info)
        서브 프로세스 정보 변경 (DC_CNF_SUB_PROC 테이블)
        """
        if not self.m_DbSession:
            print("[DbManager] DB Connection Fail !!")
            self.get_db_instance()
            return False

        # ---------------------------------------------------
        # 1. CREATE (INSERT)
        # ---------------------------------------------------
        if info.RequestStatus == CREATE_DATA:
            # ID 컬럼에는 0을 입력 (C++ 원본 로직: Auto Increment 혹은 Trigger 사용 추정)
            query = (
                f"INSERT INTO {DC_CNF_SUB_PROC} "
                f"(ID, ID_STR, PARENT, PARENTID, IPADDRESS, HOSTNAME, "
                f"STATUS, LOGCYCLE, DESCRIPTION, BIN_NAME, ARGS) "
                f"VALUES "
                f"(0, '{info.ProcIdStr}', {info.ParentProc}, '{info.ParentId}', "
                f"'{info.IpAddress}', '{info.HostName}', {info.SettingStatus}, "
                f"{info.LogCycle}, '{info.Description}', '{info.BinaryName}', '{info.Args}')"
            )

            if not self.execute_query(query):
                print(f"[DbManager] Sub Proc Create({info.ProcIdStr}) Error")
                return False
            return True

        # ---------------------------------------------------
        # 2. UPDATE
        # ---------------------------------------------------
        elif info.RequestStatus == UPDATE_DATA:
            # OldProcIdStr를 조건으로 사용하여 업데이트
            query = (
                f"UPDATE {DC_CNF_SUB_PROC} SET "
                f"ID_STR = '{info.ProcIdStr}', PARENT = {info.ParentProc}, "
                f"PARENTID = '{info.ParentId}', IPADDRESS = '{info.IpAddress}', "
                f"HOSTNAME = '{info.HostName}', STATUS = {info.SettingStatus}, "
                f"LOGCYCLE = {info.LogCycle}, DESCRIPTION = '{info.Description}', "
                f"BIN_NAME = '{info.BinaryName}', ARGS = '{info.Args}' "
                f"WHERE ID_STR = '{info.OldProcIdStr}'"
            )

            if not self.execute_query(query):
                print(f"[DbManager] Sub Proc Update({info.OldProcIdStr}) Error")
                return False
            return True

        # ---------------------------------------------------
        # 3. DELETE
        # ---------------------------------------------------
        elif info.RequestStatus == DELETE_DATA:
            query = f"DELETE FROM {DC_CNF_SUB_PROC} WHERE ID_STR = '{info.ProcIdStr}'"
            
            if not self.execute_query(query):
                print(f"[DbManager] Sub Proc Delete({info.ProcIdStr}) Error")
                return False
            return True

        return False
    
    def _recv_command_authority_info_change(self, info):
        """
        C++: bool RecvInfoChange(AS_COMMAND_AUTHORITY_INFO_T* Info)
        명령 권한 정보 변경 (DC_CMD_SESSION_IDENT 테이블)
        """
        if not self.m_DbSession:
            print("[DbManager] DB Connection Fail !!")
            self.get_db_instance()
            return False

        # ---------------------------------------------------
        # 1. CREATE (INSERT)
        # ---------------------------------------------------
        if info.RequestStatus == CREATE_DATA:
            query = (
                f"INSERT INTO {DC_CMD_SESSION_IDENT} "
                f"(ID, MAXCMDQUEUE, PRIORITY, LOGMODE, ACKMODE, DESCRIPTION, MAX_SESSION_CNT ) "
                f"VALUES "
                f"('{info.Id}', {info.MaxCmdQueue}, {info.Priority}, {info.LogMode}, "
                f"{info.AckMode}, '{info.Description}', {info.MaxSessionCnt}) "
            )

            if not self.execute_query(query):
                print(f"[DbManager] Command Authority Create({info.Id}) Error")
                return False
            return True

        # ---------------------------------------------------
        # 2. UPDATE
        # ---------------------------------------------------
        elif info.RequestStatus == UPDATE_DATA:
            query = (
                f"UPDATE {DC_CMD_SESSION_IDENT} SET "
                f"ID = '{info.Id}', MAXCMDQUEUE = {info.MaxCmdQueue}, PRIORITY = {info.Priority}, "
                f"DESCRIPTION = '{info.Description}', LOGMODE = {info.LogMode}, "
                f"ACKMODE = {info.AckMode}, MAX_SESSION_CNT = {info.MaxSessionCnt} "
                f"WHERE ID = '{info.OldId}'"
            )

            if not self.execute_query(query):
                print(f"[DbManager] Command Authority Update({info.OldId}) Error")
                return False
            return True

        # ---------------------------------------------------
        # 3. DELETE
        # ---------------------------------------------------
        elif info.RequestStatus == DELETE_DATA:
            query = f"DELETE FROM {DC_CMD_SESSION_IDENT} WHERE ID = '{info.Id}'"

            if not self.execute_query(query):
                print(f"[DbManager] Command Authority Delete({info.Id}) Error")
                return False
            return True

        return False
    
    def _recv_rule_change_info_change(self, info):
        """
        C++: bool RecvInfoChange(AS_RULE_CHANGE_INFO_T* Info)
        파싱 룰 변경 정보 업데이트 (DC_CNF_CONNECTOR 테이블)
        """
        if not self.m_DbSession:
            return False

        # 쿼리 생성
        query = (
            f"UPDATE {DC_CNF_CONNECTOR} "
            f"SET RULEID = '{info.RuleId}' "
            f"WHERE GATEWAYID = '{info.ManagerId}' AND ID = '{info.ProcessId}'"
        )

        if not self.execute_query(query):
            print(f"[DbManager] Parsing rule change({info.ProcessId}:{info.RuleId}) Error")
            return False
            
        return True
    
    def _recv_connector_desc_change_info_change(self, info):
        """
        C++: bool RecvInfoChange(AS_CONNECTOR_DESC_CHANGE_INFO_T* Info)
        커넥터 설명(Description) 업데이트
        """
        # 쿼리 생성
        query = (
            f"UPDATE {DC_CNF_CONNECTOR} "
            f"SET DESCRIPTION = '{info.Description}' "
            f"WHERE GATEWAYID = '{info.ManagerId}' AND ID = '{info.ConnectorId}'"
        )

        # 실행
        if not self.execute_query(query):
            print(f"[DbManager] Connector description change({info.ConnectorId}) Error")
            return False
            
        return True
    
    # ---------------------------------------------------
    # Command Authority Info Logic
    # ---------------------------------------------------
    def get_command_authority_info(self, info_map):
        """
        C++: void GetCommandAuthorityInfo(CommandAuthorityInfoMap* Info)
        DC_CMD_SESSION_IDENT 테이블을 조회하여 맵에 적재
        """
        # 쿼리 구성 (DC_CMD_SESSION_IDENT는 CommDbType.py에 정의됨)
        query = (
            f"SELECT ID, MAXCMDQUEUE, PRIORITY, LOGMODE, ACKMODE, DESCRIPTION, MAX_SESSION_CNT "
            f"FROM {DC_CMD_SESSION_IDENT}"
        )

        self.m_DbParam.SetQuery(query)

        if not self.execute_query(self.m_DbParam):
            return

        self.m_DbParam.Rewind()
        while self.m_DbParam.Next():
            rec = self.m_DbParam.get_current_record()
            if not rec: continue

            # CommType.py에 정의된 구조체 객체 생성
            info = AsCommandAuthorityInfoT()

            # 데이터 매핑 (인덱스는 SELECT 순서)
            # 0: ID, 1: MAXCMDQUEUE, 2: PRIORITY, 3: LOGMODE, 
            # 4: ACKMODE, 5: DESCRIPTION, 6: MAX_SESSION_CNT
            
            info.Id = rec.get_value(0)
            
            # 정수형 변환 (Safe conversion)
            try: info.MaxCmdQueue = int(rec.get_value(1))
            except: info.MaxCmdQueue = 0

            try: info.Priority = int(rec.get_value(2))
            except: info.Priority = 0

            try: info.LogMode = int(rec.get_value(3))
            except: info.LogMode = 0

            try: info.AckMode = int(rec.get_value(4))
            except: info.AckMode = 0
            
            info.Description = rec.get_value(5)

            try: info.MaxSessionCnt = int(rec.get_value(6))
            except: info.MaxSessionCnt = 0

            # 맵에 삽입 (Key: ID)
            info_map[info.Id] = info
            
            # 로그 출력 (선택사항)
            # print(f"[DbManager] Cmd Session Ident : {info.Id}, QueueSize : {info.MaxCmdQueue}")

        self.m_DbParam.Clear()
        
    # ---------------------------------------------------
    # Status Update Logic (Connector, Manager, SubProc, etc.)
    # ---------------------------------------------------
    def update_connector_status(self, proc_ctl, time_str):
        """
        C++: bool UpdateConnectorStatus(AS_PROC_CONTROL_T* ProcCtl, string TimeStr)
        커넥터 상태, 마지막 동작 시간/유형 업데이트
        """
        if not self.m_DbSession:
            return False

        # 1. 날짜 포맷팅 Query 생성 (TO_DATE 등)
        cur_time_query = self.m_DbSession.make_insert_query(E_QUERY_DATA_TYPE.DATE, time_str)
        
        # 2. 기존 포트 상태 정보 정리 (ASCII_CONNECTOR = 1203)
        # (이미 구현된 update_connection_status 호출)
        self.update_connection_status(ASCII_CONNECTOR, proc_ctl.ProcessId)

        # 3. 상태값 결정
        status = START if proc_ctl.Status == START else STOP
        
        # 4. 액션 문자열 (START -> ACT_START -> "START")
        act_type = ACT_START if proc_ctl.Status == START else ACT_STOP
        action_str = AsUtil.get_action_type_string(act_type)

        # 5. 쿼리 생성 & 실행
        query = (
            f"UPDATE {DC_CNF_CONNECTOR} SET "
            f"STATUS = {status}, "
            f"LAST_ACTION_DATE = {cur_time_query}, "
            f"LAST_ACTION = '{action_str}', "
            f"LAST_ACTION_DESC = '{proc_ctl.Desc}' "
            f"WHERE GATEWAYID = '{proc_ctl.ManagerId}' AND ID = '{proc_ctl.ProcessId}'"
        )

        return self.execute_query(query)
    
    def update_connection_status(self, type_val, id_val, sequence, info=None):
        """
        C++: bool UpdateConnectionStatus(int Type, string Id, int Sequence, AS_PORT_STATUS_INFO_T* Info)
        DC_STATUS_CMD_PORT 테이블 관리 (매니저/커넥터 단위 삭제 또는 개별 포트 상태 갱신)
        """
        
        # ---------------------------------------------------
        # 1. Manager 단위 일괄 삭제
        # ---------------------------------------------------
        if type_val == ASCII_MANAGER:
            query = f"DELETE FROM {DC_STATUS_CMD_PORT} WHERE MANAGERID = '{id_val}'"
            if not self.execute_query(query):
                print(f"[DbManager] UpdateConnectionStatus error({id_val}, {sequence})")
                return False
            return True

        # ---------------------------------------------------
        # 2. Connector 단위 일괄 삭제
        # ---------------------------------------------------
        elif type_val == ASCII_CONNECTOR:
            query = f"DELETE FROM {DC_STATUS_CMD_PORT} WHERE CONNECTORID = '{id_val}'"
            if not self.execute_query(query):
                print(f"[DbManager] UpdateConnectionStatus error({id_val}, {sequence})")
                return False
            return True

        # ---------------------------------------------------
        # 3. 개별 포트 상태 업데이트 (Sequence 기준)
        # ---------------------------------------------------
        else:
            if info:
                # 특정 Command Port 타입들만 상태 테이블에 기록 (C++ 로직)
                # CMD, LUCENT_ECP_CMD, LUCENT_DCS_CMD 상수는 CommType.py에 정의됨
                if info.PortType in [CMD, LUCENT_ECP_CMD, LUCENT_DCS_CMD]:
                    
                    # 3-1. 기존 데이터 삭제
                    del_query = f"DELETE FROM {DC_STATUS_CMD_PORT} WHERE SEQUENCE = {sequence}"
                    if not self.execute_query(del_query):
                        print(f"[DbManager] UpdateConnectionStatus error({id_val}, {sequence})")
                        return False

                    # 3-2. 상태가 '제거(ELIMINATION)'가 아니면 신규 상태 Insert
                    if info.Status != PORT_ELIMINATION:
                        # EQUIPID 컬럼에는 ConnectorId를 넣는 것이 C++ 원본 로직임
                        ins_query = (
                            f"INSERT INTO {DC_STATUS_CMD_PORT} "
                            f"(SEQUENCE, MANAGERID, CONNECTORID, EQUIPID, STATUS) "
                            f"VALUES ({sequence}, '{info.ManagerId}', '{info.ConnectorId}', "
                            f"'{info.ConnectorId}', {info.Status})"
                        )
                        
                        if not self.execute_query(ins_query):
                            print(f"[DbManager] UpdateConnectionStatus error({id_val}, {sequence})")
                            return False
            
            # Info가 없는 경우 (단순 삭제 요청)
            else:
                query = f"DELETE FROM {DC_STATUS_CMD_PORT} WHERE SEQUENCE = {sequence}"
                if not self.execute_query(query):
                    print(f"[DbManager] UpdateConnectionStatus error({id_val}, {sequence})")
                    return False

        return True

    def update_connection_status_by_ctl(self, session_ctl):
        """
        C++: bool UpdateConnectionStatus(AS_SESSION_CONTROL_T* SessionCtl)
        세션 제어 정보로 연결 상태 업데이트
        """
        # 기존 포트 상태 정리 (Sequence 기준)
        self.update_connection_status(-1, "", session_ctl.Sequence)

        status = START if session_ctl.Status == START else STOP

        query = (
            f"UPDATE {DC_CNF_CONNECTION} SET "
            f"STATUS = {status}, DESCRIPTION = '{session_ctl.Desc}' "
            f"WHERE SEQUENCE = {session_ctl.Sequence}"
        )

        return self.execute_query(query)

    def update_manager_status(self, manager_id, status, desc):
        """
        C++: bool UpdateManagerStatus(string ManagerId, int Status, string Desc)
        매니저 프로세스 상태 업데이트
        """
        # 매니저 관련 포트 상태 정리
        self.update_connection_status(ASCII_MANAGER, manager_id)

        st_val = START if status == START else STOP
        
        query = (
            f"UPDATE {DC_CNF_MANAGER} SET "
            f"STATUS = {st_val}, DESCRIPTION = '{desc}' "
            f"WHERE ID = '{manager_id}'"
        )
        
        return self.execute_query(query)

    def update_data_handler_status(self, data_handler_id, status):
        """
        C++: bool UpdateDataHandlerStatus(string DataHandlerId, int Status)
        데이터 핸들러 상태 업데이트
        """
        st_val = START if status == START else STOP
        
        # DB 타입에 따라 현재 시간 함수 결정 (Oracle: SYSDATE, MySQL: NOW())
        time_func = "SYSDATE" if self.m_DbSession.get_db_type() == EDB_TYPE.ORACLE else "NOW()"
        
        query = (
            f"UPDATE {DC_EVENT_CONSUMER} SET "
            f"STATUS = {st_val}, MODIFY_DATE = {time_func} "
            f"WHERE ID = '{data_handler_id}'"
        )
        
        return self.execute_query(query)

    def update_sub_proc_status(self, proc_id_str, status):
        """
        C++: bool UpdateSubProcStatus(string ProcIdStr, int Status)
        서브 프로세스 상태 업데이트
        """
        st_val = START if status == START else STOP
        
        query = (
            f"UPDATE {DC_CNF_SUB_PROC} SET "
            f"STATUS = {st_val} "
            f"WHERE ID_STR = '{proc_id_str}'"
        )
        
        return self.execute_query(query)
    
    def get_manager_info_find_id(self, manager_info):
        """
        C++: bool GetManagerInfoFindId(ManagerInfo* managerinfo)
        매니저 ID로 상세 정보(IP, SSH정보 등)를 조회하여 업데이트
        """
        # 쿼리 생성
        # DC_CNF_MANAGER는 CommDbType.py에 정의됨
        query = (
            f"SELECT ID, IP, STATUS, SSHID, SSHPW "
            f"FROM {DC_CNF_MANAGER} "
            f"WHERE ID = '{manager_info.m_ManagerInfo.ManagerId}'"
        )

        self.m_DbParam.SetQuery(query)

        if not self.execute_query(self.m_DbParam):
            return False

        # 결과 Fetch
        while self.m_DbParam.Next():
            rec = self.m_DbParam.get_current_record()
            if rec:
                # SELECT 순서: 0:ID, 1:IP, 2:STATUS, 3:SSHID, 4:SSHPW
                mgr_id = rec.get_value(0)
                ip = rec.get_value(1)
                
                try:
                    status = int(rec.get_value(2))
                except ValueError:
                    status = 0
                
                ssh_id = rec.get_value(3)
                ssh_pass = rec.get_value(4)

                # 디버그 로그 (C++ 코드의 frCORE_ERROR 대응)
                print(f"[DbManager] GetManagerInfoFindId FIND ID=({ssh_id}), PASS=({ssh_pass})")

                # 정보 업데이트
                # manager_info.m_ManagerInfo는 AsManagerInfoT 객체임
                manager_info.m_ManagerInfo.ManagerId = mgr_id
                manager_info.m_ManagerInfo.IP = ip
                manager_info.m_ManagerInfo.SshID = ssh_id
                manager_info.m_ManagerInfo.SshPass = ssh_pass
                manager_info.m_ManagerInfo.SettingStatus = status
                
                # 상태 초기화 (STOP, WAIT_NO는 CommType.py에 정의됨)
                manager_info.m_ManagerInfo.CurStatus = STOP
                manager_info.m_ManagerInfo.RequestStatus = WAIT_NO

        self.m_DbParam.Clear()
        return True
    
    def get_db_sync_info(self, info_list_obj):
        """
        C++: bool GetDbSyncInfo(AS_DB_SYNC_INFO_LIST_T& InfoList)
        DC_SYNCTB_INFO 테이블 조회
        """
        # 1. DB 타입별 날짜 변환 함수 설정
        # EDB_TYPE은 FrBaseType에서 Import 됨
        if self.m_DbSession.get_db_type() == EDB_TYPE.ORACLE:
            date_col = "TO_CHAR(SYNCTIME, 'YYYY/MM/DD HH24:MI:SS')"
        else:
            # MySQL Style
            date_col = "DATE_FORMAT(SYNCTIME, '%Y/%m/%d %H:%i:%s')"

        query = f"SELECT TABLENAME, {date_col} FROM DC_SYNCTB_INFO"

        self.m_DbParam.SetQuery(query)

        if not self.execute_query(self.m_DbParam):
            return False

        # 2. 리스트 초기화
        # info_list_obj는 AsDbSyncInfoListT 객체 (참조로 넘어옴)
        info_list_obj.InfoList = []
        info_list_obj.Count = 0

        # 3. 결과 Fetch
        self.m_DbParam.Rewind()
        while self.m_DbParam.Next():
            rec = self.m_DbParam.get_current_record()
            if not rec: continue

            # 0: TABLENAME, 1: SYNCTIME
            table_name = rec.get_value(0)
            sync_time = rec.get_value(1)

            # AsDbSyncInfoT 객체 생성 및 추가
            # (CommType.py에 정의된 구조체)
            info_item = AsDbSyncInfoT()
            info_item.TableName = table_name
            info_item.SyncTime = sync_time
            
            info_list_obj.InfoList.append(info_item)

        # 4. 개수 갱신
        info_list_obj.Count = len(info_list_obj.InfoList)

        self.m_DbParam.Clear()
        return True
    
    def disable_manager_from_ip(self, manager_ip):
        """
        C++: bool DisableManagerFromIp(string ManagerIp)
        특정 IP의 매니저 상태를 STOP으로 변경
        """
        # DC_CNF_MANAGER: 테이블 이름 (CommDbType.py)
        # STOP: 상태 상수 (CommType.py, 보통 2)
        
        query = (
            f"UPDATE {DC_CNF_MANAGER} "
            f"SET STATUS = {STOP} "
            f"WHERE IP = '{manager_ip}'"
        )

        return self.execute_query(query)
    
    def update_server_info(self, ip, gui_port, cmd_port, log_port, sock_mgr_port, net_finder_port):
        """
        C++: bool UpdateServerInfo(string Ip, int GuiPort, int CmdPort, 
                                   int LogPort, int SockMgrPort, int NetFinderPort)
        서버 접속 정보를 DC_CNF_SERVER 테이블에 갱신 (DELETE -> INSERT)
        """
        # C++ 원본에는 상단에 return true가 있어 로직이 비활성화되어 있었으나,
        # 실제 로직을 포팅합니다.
        
        # 1. 기존 정보 삭제
        # DC_CNF_SERVER는 CommDbType.py에 정의됨
        query = f"DELETE FROM {DC_CNF_SERVER}"

        # auto_commit=False로 설정하여 트랜잭션 시작
        if not self.execute_query(query, False):
            print(f"[DbManager] Update {DC_CNF_SERVER} Error (Delete)")
            return False

        # 2. 신규 정보 입력
        # 주의: NetFinderPort는 인자로 받지만 C++ 원본 쿼리에는 포함되지 않음 (의도된 것인지 확인 필요)
        # 원본 로직 그대로 구현함.
        query = (
            f"INSERT INTO {DC_CNF_SERVER} (IP, GUIPORT, CMDPORT, LOGPORT, SOCKMGRPORT) "
            f"VALUES ('{ip}', {gui_port}, {cmd_port}, {log_port}, {sock_mgr_port})"
        )

        if not self.execute_query(query, False):
            print(f"[DbManager] Update {DC_CNF_SERVER} Error (Insert)")
            self.rollback() # 실패 시 삭제 취소
            return False

        # 3. 트랜잭션 확정
        self.commit()
        return True
    
    def get_sub_proc_info(self, info_map):
        """
        C++: bool GetSubProcInfo(SubProcInfoMap* InfoMap)
        DC_CNF_SUB_PROC 테이블 조회 후 맵에 적재
        """
        # 쿼리 생성
        # 0:ID, 1:ID_STR, 2:PARENT, 3:PARENTID, 4:IPADDRESS, 5:HOSTNAME, 
        # 6:STATUS, 7:LOGCYCLE, 8:DESCRIPTION, 9:BIN_NAME, 10:ARGS
        query = (
            f"SELECT ID, ID_STR, PARENT, PARENTID, IPADDRESS, HOSTNAME, "
            f"STATUS, LOGCYCLE, DESCRIPTION, BIN_NAME, ARGS "
            f"FROM {DC_CNF_SUB_PROC}"
        )

        self.m_DbParam.SetQuery(query)

        if not self.execute_query(self.m_DbParam):
            return False

        self.m_DbParam.Rewind()
        while self.m_DbParam.Next():
            rec = self.m_DbParam.get_current_record()
            if not rec: continue

            # CommType.py의 AsSubProcInfoT 객체 생성
            info = AsSubProcInfoT()

            # 데이터 매핑
            try: info.ProcId = int(rec.get_value(0))
            except: info.ProcId = 0

            info.ProcIdStr = rec.get_value(1)

            try: info.ParentProc = int(rec.get_value(2))
            except: info.ParentProc = 0

            info.ParentId = rec.get_value(3)
            info.IpAddress = rec.get_value(4)
            info.HostName = rec.get_value(5)

            try: info.SettingStatus = int(rec.get_value(6))
            except: info.SettingStatus = 0

            try: info.LogCycle = int(rec.get_value(7))
            except: info.LogCycle = 0

            info.Description = rec.get_value(8)
            info.BinaryName = rec.get_value(9)
            info.Args = rec.get_value(10)

            # 기본 상태 설정
            info.CurStatus = STOP
            info.RequestStatus = WAIT_NO

            # 맵에 삽입 (Key: ProcIdStr)
            info_map[info.ProcIdStr] = info

        self.m_DbParam.Clear()
        return True
    
    