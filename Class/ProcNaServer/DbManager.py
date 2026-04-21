"""
DbManager.py
C++ DbManager.h/.C → Python 변환

테이블 상수(DC_CNF_MANAGER 등)는 CommDbType에 정의되어 있다고 가정합니다.
없을 경우 이 파일 하단의 _TABLE_NAMES 섹션에서 직접 정의하세요.
"""

from __future__ import annotations

import copy
from typing import Optional, TYPE_CHECKING

from Event.fr_object import FrObject
from Sql.fr_db_session import DbSession
from SqlType.fr_db_base_type import QueryDataType
from SqlType.fr_db_param import DbParam, DbRecord
from Common.CommType import (
    AS_COMMAND_AUTHORITY_INFO_T, AS_CONNECTION_INFO_T,
    AS_CONNECTOR_DESC_CHANGE_INFO_T, AS_CONNECTOR_INFO_T,
    AS_DATA_HANDLER_INFO_T, AS_DB_SYNC_INFO_LIST_T, AS_DB_SYNC_INFO_T,
    AS_MANAGER_INFO_T, AS_PORT_STATUS_INFO_T, AS_PROC_CONTROL_T,
    AS_RULE_CHANGE_INFO_T, AS_SESSION_CONTROL_T, AS_SUB_PROC_INFO_T,
    AS_TARGET_IP_INFO_LIST_T, AS_TARGET_IP_INFO_T,
)
from Common.CommTypeList import ProcControlMap
from AsciiServerType import (
    CommandAuthorityInfoMap, ConnectorInfo, ConnectorInfoMap,
    ManagerInfo, ManagerInfoMap, MMCResultStored,
)
from Util.fr_logger import make_log_def
from Util.fr_util_misc import FrUtilMisc

_log = make_log_def("AsciiServer", "DbManager")

# ──────────────────────────────────────────────
# 테이블 이름 상수 (C++ CommDbType.h 대응)
# 실제 환경에 맞게 수정하세요.
# ──────────────────────────────────────────────
DC_CNF_MANAGER           = "DC_CNF_MANAGER"
DC_CNF_CONNECTOR         = "DC_CNF_CONNECTOR"
DC_CNF_CONNECTOR_DELETED = "DC_CNF_CONNECTOR_DELETED"
DC_CNF_CONNECTION        = "DC_CNF_CONNECTION"
DC_CNF_SERVER            = "DC_CNF_SERVER"
DC_CNF_SUB_PROC          = "DC_CNF_SUB_PROC"
DC_EVENT_CONSUMER        = "DC_EVENT_CONSUMER"
DC_RUL_RULE              = "DC_RUL_RULE"
DC_CMD_SESSION_IDENT     = "DC_CMD_SESSION_IDENT"
DC_STATUS_CMD_PORT       = "DC_STATUS_CMD_PORT"
DC_MMC_RESULT            = "DC_MMC_RESULT"
TBD_EQP_HOSTHW           = "TBD_EQP_HOSTHW"

# Process / Status 상수 (AsciiServerWorld와 공유)
START     = 1
STOP      = 0
WAIT_NO   = 0
UNDEFINED = -1

CREATE_DATA = 1
UPDATE_DATA = 2
DELETE_DATA = 3

ASCII_MANAGER   = 3
ASCII_CONNECTOR = 31

CMD              = 1
LUCENT_ECP_CMD   = 2
LUCENT_DCS_CMD   = 3
PORT_ELIMINATION = 99

# Action type 문자열 (AsUtil.GetEnumTypeString 대응)
ACT_CREATE = "CREATE"
ACT_MODIFY = "MODIFY"
ACT_START  = "START"
ACT_STOP   = "STOP"

# 타입 별칭 (C++ typedef 대응)
IntStringMap     = dict   # map<int, string>
DataHandlerInfoMap = dict  # map<string, AS_DATA_HANDLER_INFO_T*>
SubProcInfoMap   = dict   # map<string, AS_SUB_PROC_INFO_T*>

NAME_LEN         = 64
DATE_STRING_LEN  = 32
MAX_DESC_LEN     = 256


# ──────────────────────────────────────────────
# DbManager
# ──────────────────────────────────────────────
class DbManager(FrObject):
    """
    C++ DbManager → Python 변환
    DB 세션을 관리하고, 설정/상태 정보를 조회·갱신하는 클래스
    """

    def __init__(self) -> None:
        super().__init__("DbManager")
        self._m_db_session: Optional[DbSession] = None
        self._m_db_param:   Optional[DbParam]   = None
        self._m_db_id:   str = ""
        self._m_db_pass: str = ""
        self._m_db_tns:  str = ""
        self._m_db_ip:   str = ""
        self._m_db_port: str = ""

    def __del__(self) -> None:
        self._m_db_session = None
        self._m_db_param   = None

    # ──────────────────────────────────────────
    # 초기화 / 연결
    # ──────────────────────────────────────────
    def init_db_manager(self, user: str, password: str, tns: str,
                        db_ip: str, db_port: str) -> bool:
        """C++: InitDbManager()"""
        self._m_db_session = None
        self._m_db_param   = DbParam()
        self._m_db_id   = user
        self._m_db_pass = password
        self._m_db_tns  = tns
        self._m_db_ip   = db_ip
        self._m_db_port = db_port

        port_int = int(db_port) if db_port else 0
        _log.error(f"db={user}, {password}, {tns}, {db_ip}, {port_int}")

        self._m_db_session = DbSession.get_instance()
        if not self._m_db_session.connect(user, password, tns, db_ip, port_int):
            _log.error(f"Can't connect DB({user}) : "
                       f"[{self._m_db_session.get_error_code()}] {self._m_db_session.get_error()}")
            self._m_db_session = None
            return False
        return True

    InitDbManager = init_db_manager

    def get_db_instance(self) -> bool:
        """C++: GetDBInstance() — DB 자동 재접속"""
        from AsciiServerWorld import AsciiServerWorld
        _log.error("try auto reconnect to db")
        _log.error("### GetDBInstance ###")
        AsciiServerWorld.m_WorldPtr.send_ascii_error(1, "try auto reconnect to db")

        self._m_db_session = None
        self._m_db_session = DbSession.get_instance()
        port_int = int(self._m_db_port) if self._m_db_port else 0

        if not self._m_db_session.connect(
                self._m_db_id, self._m_db_pass, self._m_db_tns, self._m_db_ip, port_int):
            _log.error("Reconnect to db Fail!!!!")
            self._m_db_session = None
            return False

        _log.debug(1, "Reconnect to db!!")
        return True

    GetDBInstance = get_db_instance

    # ──────────────────────────────────────────
    # 트랜잭션
    # ──────────────────────────────────────────
    def commit(self) -> None:
        if self._m_db_session:
            self._m_db_session.commit()

    def roll_back(self) -> None:
        if self._m_db_session:
            self._m_db_session.rollback()

    def dis_connection(self) -> None:
        if self._m_db_session:
            self._m_db_session.disconnect()

    Commit      = commit
    RollBack    = roll_back
    DisConnection = dis_connection

    # ──────────────────────────────────────────
    # 쿼리 실행 (두 가지 오버로드)
    # ──────────────────────────────────────────
    def execute_query(self, query_or_param, auto_commit: bool = True) -> bool:
        """
        C++: ExecuteQuery(char* Query) / ExecuteQuery(frDbParam*)
        query_or_param이 str이면 문자열 쿼리, DbParam이면 파라미터 기반 실행
        """
        from AsciiServerWorld import AsciiServerWorld

        def _reconnect_and_fail(label: str) -> bool:
            _log.debug(1, f"DB Query Error - {label}")
            self._m_db_session = None
            self.get_db_instance()
            AsciiServerWorld.m_WorldPtr.send_ascii_error(1, f"DB Query Error - {label}")
            return False

        if self._m_db_session is None:
            return _reconnect_and_fail("DB Error")

        if isinstance(query_or_param, str):
            _log.debug(3, query_or_param)
            result = self._m_db_session.execute_query(query_or_param,
                                                      auto_commit=auto_commit)
            if not result:
                return _reconnect_and_fail(query_or_param)
        else:
            # DbParam 기반
            param: DbParam = query_or_param
            result = self._m_db_session.execute(param)
            if not result:
                return _reconnect_and_fail(param.get_query())

        return True

    ExecuteQuery = execute_query

    def get_error_msg(self) -> str:
        if self._m_db_session:
            return self._m_db_session.get_error()
        return "ERROR DB"

    GetErrorMsg = get_error_msg

    # ──────────────────────────────────────────
    # MsgId
    # ──────────────────────────────────────────
    def get_current_msg_id(self) -> int:
        return 1

    GetCurrentMsgId = get_current_msg_id

    # ──────────────────────────────────────────
    # Manager 정보 조회
    # ──────────────────────────────────────────
    def get_manager_info_find_id(self, manager_info: ManagerInfo) -> bool:
        """C++: GetManagerInfoFindId()"""
        query = (f"SELECT ID, IP, STATUS, SSHID, SSHPW "
                 f"FROM {DC_CNF_MANAGER} "
                 f"WHERE ID = '{manager_info.m_ManagerInfo.ManagerId}'")
        self._m_db_param.set_query(query)
        if not self.execute_query(self._m_db_param):
            return False

        result_set = self._m_db_session.execute_rs(query)
        row = result_set.move_first()
        if row:
            manager_info.m_ManagerInfo.ManagerId     = row[0] or ""
            manager_info.m_ManagerInfo.IP            = row[1] or ""
            manager_info.m_ManagerInfo.SettingStatus = int(row[2] or 0)
            manager_info.m_ManagerInfo.SshID         = row[3] or ""
            manager_info.m_ManagerInfo.SshPass       = row[4] or ""
            manager_info.m_ManagerInfo.CurStatus     = STOP
            manager_info.m_ManagerInfo.RequestStatus = WAIT_NO
            _log.error(f"GetManagerInfoFindId FIND ID=({manager_info.m_ManagerInfo.SshID}), "
                       f"PASS=({manager_info.m_ManagerInfo.SshPass})")
        return True

    GetManagerInfoFindId = get_manager_info_find_id

    def get_manager_info(self, info_map: ManagerInfoMap) -> bool:
        """C++: GetManagerInfo() — Manager/Connector/Connection 전체 로드"""
        # ── 1단계: Manager 기본 정보
        query = f"SELECT ID, IP, STATUS, SSHID, SSHPW FROM {DC_CNF_MANAGER}"
        result_set = self._execute_select(query)
        if result_set is None:
            return False

        for row in result_set:
            mgr = ManagerInfo()
            mgr.m_ManagerInfo.ManagerId     = row[0] or ""
            mgr.m_ManagerInfo.IP            = row[1] or ""
            mgr.m_ManagerInfo.SettingStatus = int(row[2] or 0)
            mgr.m_ManagerInfo.SshID         = row[3] or ""
            mgr.m_ManagerInfo.SshPass       = row[4] or ""
            mgr.m_ManagerInfo.CurStatus     = STOP
            mgr.m_ManagerInfo.RequestStatus = WAIT_NO
            info_map[mgr.m_ManagerInfo.ManagerId] = mgr

        # ── 2단계: Connector + Connection 조인 쿼리
        query2 = (
            f"SELECT CR.GATEWAYID, CM.IP, CM.STATUS, CR.ID, CR.STATUS, CR.RULEID, "
            f"RI.IDENTIFICATIONTYPE, CR.JUNCTIONTYPE, "
            f"CC.SEQUENCE, CC.AGENTEQUIPID, CC.PROTOCOLTYPE, CC.PORTTYPE, CC.AGENTPORTNO, "
            f"CC.USERID, CC.PASSWORD, CC.GATFLAG, CC.COMMANDFLAG, CC.STATUS, "
            f"CR.CMDRESPONSETYPE, CR.LOGCYCLE, "
            f"DATE_FORMAT(CR.CREATE_DATE,    '%%Y/%%m/%%d %%H:%%i:%%s'), "
            f"DATE_FORMAT(CR.MODIFY_DATE,    '%%Y/%%m/%%d %%H:%%i:%%s'), "
            f"DATE_FORMAT(CR.LAST_ACTION_DATE,'%%Y/%%m/%%d %%H:%%i:%%s'), "
            f"CR.LAST_ACTION, CR.LAST_ACTION_DESC, CR.DESCRIPTION, HD.CURRENTEQUIPID "
            f"FROM {DC_CNF_CONNECTOR} CR "
            f"INNER JOIN {DC_CNF_MANAGER} CM ON CR.GATEWAYID = CM.ID "
            f"INNER JOIN {DC_RUL_RULE}    RI ON CR.RULEID    = RI.ID "
            f"INNER JOIN {TBD_EQP_HOSTHW} HD ON CR.ID        = HD.EQUIPID "
            f"LEFT  JOIN {DC_CNF_CONNECTION} CC ON CR.ID     = CC.CONNECTORID "
            f"ORDER BY CR.GATEWAYID, HD.CURRENTEQUIPID, CC.PROTOCOLTYPE, "
            f"CC.AGENTPORTNO, CC.PORTTYPE"
        )
        result_set2 = self._execute_select(query2)
        if result_set2 is None:
            return False

        for row in result_set2:
            manager_id       = row[0]  or ""
            connector_id     = row[3]  or ""
            rule_id          = row[5]  or ""
            mmc_ident_type   = int(row[6]  or 0)
            junction_type    = int(row[7]  or 0)
            seq              = int(row[8]  or 0)
            agent_equip_id   = row[9]  or ""
            protocol_type    = int(row[10] or 0)
            port_type        = int(row[11] or 0)
            port_no          = int(row[12] or 0)
            user_id          = row[13] or ""
            password         = row[14] or ""
            gat_flag         = int(row[15] or 0)
            cmd_flag         = int(row[16] or 0)
            setting_conn_st  = int(row[17] or 0)
            cmd_response_type = int(row[18] or 0)
            log_cycle        = int(row[19] or 0)
            create_date      = row[20] or ""
            modify_date      = row[21] or ""
            last_action_date = row[22] or ""
            last_action_type = row[23] or ""
            last_action_desc = row[24] or ""
            desc_            = row[25] or ""
            setting_mgr_st   = int(row[2]  or 0)
            setting_con_st   = int(row[4]  or 0)

            mgr_obj = info_map.get(manager_id)
            if mgr_obj is None:
                _log.error(f"Can't Find Manager : {manager_id}")
                continue

            con_info = mgr_obj.m_ConnectorInfoMap.get(connector_id)
            if con_info is None:
                con_info = ConnectorInfo()
                mgr_obj.m_ConnectorInfoMap[connector_id] = con_info

                con_info.m_ConnectorInfo.ManagerId       = mgr_obj.m_ManagerInfo.ManagerId
                con_info.m_ConnectorInfo.ConnectorId     = connector_id
                con_info.m_ConnectorInfo.RuleId          = rule_id
                con_info.m_ConnectorInfo.SettingStatus   = setting_con_st
                con_info.m_ConnectorInfo.CurStatus       = STOP
                con_info.m_ConnectorInfo.RequestStatus   = WAIT_NO
                con_info.m_ConnectorInfo.MmcIdentType    = mmc_ident_type
                con_info.m_ConnectorInfo.CmdResponseType = cmd_response_type
                con_info.m_ConnectorInfo.JunctionType    = junction_type
                con_info.m_ConnectorInfo.LogCycle        = log_cycle
                con_info.m_ConnectorInfo.CreateDate      = create_date
                con_info.m_ConnectorInfo.ModifyDate      = modify_date
                con_info.m_ConnectorInfo.LastActionDate  = last_action_date
                con_info.m_ConnectorInfo.LastActionType  = last_action_type
                con_info.m_ConnectorInfo.LastActionDesc  = last_action_desc
                con_info.m_ConnectorInfo.Desc            = desc_

                _log.debug(1, f"Connector Status : {con_info.m_ConnectorInfo.ManagerId}/"
                           f"{con_info.m_ConnectorInfo.ConnectorId}"
                           f"[{'START' if setting_con_st == START else 'STOP'}]")

            if seq == 0:
                continue

            conn_info = AS_CONNECTION_INFO_T()
            conn_info.ManagerId       = mgr_obj.m_ManagerInfo.ManagerId
            conn_info.ConnectorId     = connector_id
            conn_info.AgentEquipId    = agent_equip_id
            conn_info.UserId          = user_id
            conn_info.UserPassword    = password
            conn_info.Sequence        = seq
            conn_info.PortNo          = port_no
            conn_info.ProtocolType    = protocol_type
            conn_info.PortType        = port_type
            conn_info.GatFlag         = gat_flag
            conn_info.CommandPortFlag = cmd_flag
            conn_info.SettingStatus   = setting_conn_st
            conn_info.CurStatus       = UNDEFINED
            conn_info.RequestStatus   = WAIT_NO
            con_info.m_ConnectionInfoList.append(conn_info)

        return True

    GetManagerInfo = get_manager_info

    # ──────────────────────────────────────────
    # DataHandler 정보 조회
    # ──────────────────────────────────────────
    def get_data_handler_info(self, info_map: DataHandlerInfoMap) -> bool:
        """C++: GetDataHandlerInfo()"""
        query = (
            f"SELECT ID, DBUSERID, DBPASSWORD, DBTNS, HOSTNAME, TIMEMODE, LISTENPORT, "
            f"STATUS, LOGMODE, IPADDRESS, BYPASSLISTENPORT, LOADINGINTERVAL, "
            f"HANDLERMODE, TARGETINFO, RUNMODE, LOGCYCLE, SSHID, SSHPW "
            f"FROM {DC_EVENT_CONSUMER}"
        )
        rs = self._execute_select(query)
        if rs is None:
            return False

        for row in rs:
            info = AS_DATA_HANDLER_INFO_T()
            info.DataHandlerId    = row[0]  or ""
            info.DbUserId         = row[1]  or ""
            info.DbPassword       = row[2]  or ""
            info.DbName           = row[3]  or ""
            info.HostName         = row[4]  or ""
            info.TimeMode         = int(row[5]  or 0)
            info.ListenPort       = int(row[6]  or 0)
            info.SettingStatus    = int(row[7]  or 0)
            info.LogMode          = int(row[8]  or 0)
            info.IpAddress        = row[9]  or ""
            info.BypassListenPort = int(row[10] or 0)
            info.LoadingInterval  = int(row[11] or 0)
            info.OperMode         = int(row[12] or 0)
            target_info           = row[13] or ""
            info.RunMode          = int(row[14] or 0)
            info.LogCycle         = int(row[15] or 0)
            info.SshID            = row[16] or ""
            info.SshPass          = row[17] or ""
            info.CurStatus        = STOP
            info.RequestStatus    = WAIT_NO
            DbManager.get_string_to_ip_info(target_info, info.TargetIpInfoList)
            info_map[info.DataHandlerId] = info

        return True

    GetDataHandlerInfo = get_data_handler_info

    def get_data_handler_info_find_id(self, info: AS_DATA_HANDLER_INFO_T) -> bool:
        """C++: GetDataHandlerInfoFindId()"""
        query = (f"SELECT ID, SSHID, SSHPW FROM {DC_EVENT_CONSUMER} "
                 f"WHERE ID = '{info.DataHandlerId}'")
        rs = self._execute_select(query)
        if rs is None:
            return False
        row = rs.move_first()
        if row:
            info.SshID   = row[1] or ""
            info.SshPass = row[2] or ""
        return True

    GetDataHandlerInfoFindId = get_data_handler_info_find_id

    # ──────────────────────────────────────────
    # SubProc 정보 조회
    # ──────────────────────────────────────────
    def get_sub_proc_info(self, info_map: SubProcInfoMap) -> bool:
        """C++: GetSubProcInfo()"""
        query = (
            f"SELECT ID, ID_STR, PARENT, PARENTID, IPADDRESS, HOSTNAME, "
            f"STATUS, LOGCYCLE, DESCRIPTION, BIN_NAME, ARGS "
            f"FROM {DC_CNF_SUB_PROC}"
        )
        rs = self._execute_select(query)
        if rs is None:
            return False

        for row in rs:
            info = AS_SUB_PROC_INFO_T()
            info.ProcId       = int(row[0]  or 0)
            info.ProcIdStr    = row[1]  or ""
            info.ParentProc   = int(row[2]  or 0)
            info.ParentId     = row[3]  or ""
            info.IpAddress    = row[4]  or ""
            info.HostName     = row[5]  or ""
            info.SettingStatus = int(row[6] or 0)
            info.LogCycle     = int(row[7]  or 0)
            info.Description  = row[8]  or ""
            info.BinaryName   = row[9]  or ""
            info.Args         = row[10] or ""
            info.CurStatus    = STOP
            info.RequestStatus = WAIT_NO
            info_map[info.ProcIdStr] = info

        return True

    GetSubProcInfo = get_sub_proc_info

    # ──────────────────────────────────────────
    # CommandAuthority 정보 조회
    # ──────────────────────────────────────────
    def get_command_authority_info(self, info: CommandAuthorityInfoMap) -> None:
        """C++: GetCommandAuthorityInfo()"""
        query = (
            f"SELECT ID, MAXCMDQUEUE, PRIORITY, LOGMODE, ACKMODE, DESCRIPTION, MAX_SESSION_CNT "
            f"FROM {DC_CMD_SESSION_IDENT}"
        )
        rs = self._execute_select(query)
        if rs is None:
            return

        for row in rs:
            auth = AS_COMMAND_AUTHORITY_INFO_T()
            auth.Id           = row[0] or ""
            auth.MaxCmdQueue  = int(row[1] or 0)
            auth.Priority     = int(row[2] or 0)
            auth.LogMode      = int(row[3] or 0)
            auth.AckMode      = int(row[4] or 0)
            auth.Description  = row[5] or ""
            auth.MaxSessionCnt = int(row[6] or 0)
            info[auth.Id] = auth
            _log.debug(3, f"Cmd Session Ident : {auth.Id}, QueueSize : {auth.MaxCmdQueue}")

    GetCommandAuthorityInfo = get_command_authority_info

    # ──────────────────────────────────────────
    # Connection IP 정보 조회
    # ──────────────────────────────────────────
    def get_connection_ip_info(self, ip_info: IntStringMap,
                               connector_id: str, sequence: int = -1) -> bool:
        """C++: GetConnectionIpInfo()"""
        if sequence == -1:
            query = (
                f"SELECT DISTINCT CC.SEQUENCE, HW.IP "
                f"FROM {DC_CNF_CONNECTION} CC, {TBD_EQP_HOSTHW} HW "
                f"WHERE CC.AGENTEQUIPID = HW.AGENTEQUIPID "
                f"AND CC.CONNECTORID = '{connector_id}'"
            )
        else:
            query = (
                f"SELECT DISTINCT CC.SEQUENCE, HW.IP "
                f"FROM {DC_CNF_CONNECTION} CC, {TBD_EQP_HOSTHW} HW "
                f"WHERE CC.AGENTEQUIPID = HW.AGENTEQUIPID "
                f"AND CC.CONNECTORID = '{connector_id}' AND CC.SEQUENCE = {sequence}"
            )
        rs = self._execute_select(query)
        if rs is None:
            return False
        for row in rs:
            ip_info[int(row[0] or 0)] = row[1] or ""
        return True

    GetConnectionIpInfo = get_connection_ip_info

    # ──────────────────────────────────────────
    # RecvInfoChange (C++ 다중 오버로드 → 타입 분기)
    # ──────────────────────────────────────────
    def recv_info_change(self, info) -> bool:
        """C++: RecvInfoChange 오버로드 통합"""
        if isinstance(info, AS_MANAGER_INFO_T):
            return self._recv_manager_change(info)
        elif isinstance(info, AS_CONNECTOR_INFO_T):
            return self._recv_connector_change(info)
        elif isinstance(info, AS_CONNECTION_INFO_T):
            return self._recv_connection_change(info)
        elif isinstance(info, AS_DATA_HANDLER_INFO_T):
            return self._recv_data_handler_change(info)
        elif isinstance(info, AS_SUB_PROC_INFO_T):
            return self._recv_sub_proc_change(info)
        elif isinstance(info, AS_COMMAND_AUTHORITY_INFO_T):
            return self._recv_command_authority_change(info)
        elif isinstance(info, AS_RULE_CHANGE_INFO_T):
            return self._recv_rule_change(info)
        elif isinstance(info, AS_CONNECTOR_DESC_CHANGE_INFO_T):
            return self._recv_connector_desc_change(info)
        else:
            _log.error(f"Unknown info type : {type(info)}")
            return False

    RecvInfoChange = recv_info_change

    def _recv_manager_change(self, info: AS_MANAGER_INFO_T) -> bool:
        if info.RequestStatus == CREATE_DATA:
            q = (f"INSERT INTO {DC_CNF_MANAGER} (ID, IP, STATUS, SSHID, SSHPW) "
                 f"VALUES ('{info.ManagerId}', '{info.IP}', {info.SettingStatus}, "
                 f"'{info.SshID}', '{info.SshPass}')")
            if not self.execute_query(q):
                _log.error(f"Manager Create({info.ManagerId}) Error")
                return False
            return True

        elif info.RequestStatus == UPDATE_DATA:
            q1 = (f"UPDATE {DC_CNF_CONNECTOR} SET GATEWAYID = '{info.ManagerId}' "
                  f"WHERE GATEWAYID = '{info.OldManagerId}'")
            if not self.execute_query(q1, False):
                _log.error(f"Manager Update({info.OldManagerId}) Error")
                return False
            q2 = (f"UPDATE {DC_CNF_MANAGER} SET ID = '{info.ManagerId}', "
                  f"IP = '{info.IP}', STATUS = {info.SettingStatus}, "
                  f"SSHID = '{info.SshID}', SSHPW = '{info.SshPass}' "
                  f"WHERE ID = '{info.OldManagerId}'")
            if not self.execute_query(q2, False):
                self.roll_back()
                _log.error(f"Manager Update({info.OldManagerId}) Error")
                return False
            self.commit()
            return True

        elif info.RequestStatus == DELETE_DATA:
            for q, label in [
                (f"DELETE FROM {DC_CNF_CONNECTION} WHERE CONNECTORID IN "
                 f"(SELECT ID FROM {DC_CNF_CONNECTOR} WHERE GATEWAYID = '{info.ManagerId}')",
                 "Connection"),
                (f"DELETE FROM {DC_CNF_CONNECTOR} WHERE GATEWAYID = '{info.ManagerId}'",
                 "Connector"),
                (f"DELETE FROM {DC_CNF_MANAGER} WHERE ID = '{info.ManagerId}'",
                 "Manager"),
            ]:
                if not self.execute_query(q, False):
                    self.roll_back()
                    _log.error(f"{label} Delete({info.ManagerId}) Error")
                    return False
            self.commit()
            return True
        return False

    def _recv_connector_change(self, info: AS_CONNECTOR_INFO_T) -> bool:
        if self._m_db_session is None:
            _log.error("DB Connection Fail !!")
            self.get_db_instance()
            return False

        dt_query = self._m_db_session.make_insert_query(QueryDataType.DATE_TYPE, info.LastActionDate)

        if info.RequestStatus == CREATE_DATA:
            q = (f"INSERT INTO {DC_CNF_CONNECTOR} "
                 f"(ID, GATEWAYID, RULEID, STATUS, JUNCTIONTYPE, CMDRESPONSETYPE, LOGCYCLE, "
                 f"CREATE_DATE, MODIFY_DATE, LAST_ACTION_DATE, LAST_ACTION) "
                 f"VALUES ('{info.ConnectorId}', '{info.ManagerId}', '{info.RuleId}', "
                 f"{info.SettingStatus}, {info.JunctionType}, {info.CmdResponseType}, {info.LogCycle}, "
                 f"{dt_query}, {dt_query}, {dt_query}, '{ACT_CREATE}')")
            if not self.execute_query(q):
                _log.error(f"Connector Create({info.ConnectorId}) Error")
                return False
            return True

        elif info.RequestStatus == UPDATE_DATA:
            q = (f"UPDATE {DC_CNF_CONNECTOR} SET GATEWAYID = '{info.ManagerId}', "
                 f"RULEID = '{info.RuleId}', STATUS = {info.SettingStatus}, "
                 f"CMDRESPONSETYPE = {info.CmdResponseType}, LOGCYCLE = {info.LogCycle}, "
                 f"MODIFY_DATE = {dt_query}, LAST_ACTION_DATE = {dt_query}, "
                 f"LAST_ACTION = '{ACT_MODIFY}', DESCRIPTION = '{info.Desc}', "
                 f"LAST_ACTION_DESC = '{info.LastActionDesc}' "
                 f"WHERE ID = '{info.ConnectorId}'")
            if not self.execute_query(q):
                _log.error(f"Connector Update({info.ConnectorId}) Error")
                return False
            return True

        elif info.RequestStatus == DELETE_DATA:
            for q, label in [
                (f"DELETE FROM {DC_CNF_CONNECTION} WHERE CONNECTORID = '{info.ConnectorId}'",
                 "Connection"),
                (f"DELETE FROM {DC_CNF_CONNECTOR} WHERE ID = '{info.ConnectorId}'",
                 "Connector"),
            ]:
                if not self.execute_query(q, False):
                    self.roll_back()
                    _log.error(f"{label} Delete({info.ConnectorId}) Error")
                    return False
            self.commit()

            # Deleted 테이블에 이력 INSERT
            from AsciiServerWorld import AsciiServerWorld
            con_info = AsciiServerWorld.m_WorldPtr.get_connector_info(info.ConnectorId)
            if con_info:
                cdt = self._m_db_session.make_insert_query(
                    QueryDataType.DATE_TYPE, con_info.m_ConnectorInfo.CreateDate)
                mdt = self._m_db_session.make_insert_query(
                    QueryDataType.DATE_TYPE, con_info.m_ConnectorInfo.ModifyDate)
                q = (f"INSERT INTO {DC_CNF_CONNECTOR_DELETED} "
                     f"(ID, GATEWAYID, RULEID, DESCRIPTION, CREATE_DATE, MODIFY_DATE, DELETE_DATE) "
                     f"VALUES ('{con_info.m_ConnectorInfo.ConnectorId}', "
                     f"'{con_info.m_ConnectorInfo.ManagerId}', "
                     f"'{con_info.m_ConnectorInfo.RuleId}', '{info.Desc}', "
                     f"{cdt}, {mdt}, NOW())")
                if not self.execute_query(q):
                    _log.error(f"## ERROR Insert {DC_CNF_CONNECTOR_DELETED} : {info.ConnectorId}")
                    return False
            else:
                _log.error(f"## ERROR Insert {DC_CNF_CONNECTOR_DELETED}, "
                           f"Can't find connector info : {info.ConnectorId}")
            return True
        return False

    def _recv_connection_change(self, info: AS_CONNECTION_INFO_T) -> bool:
        if info.RequestStatus == CREATE_DATA:
            # MAX(SEQUENCE) 조회
            rs = self._execute_select(f"SELECT MAX(SEQUENCE) FROM {DC_CNF_CONNECTION}")
            max_seq = 0
            if rs:
                row = rs.move_first()
                if row and row[0] is not None:
                    max_seq = int(row[0])
            max_seq += 1
            info.Sequence = max_seq

            q = (f"INSERT INTO {DC_CNF_CONNECTION} "
                 f"(SEQUENCE, CONNECTORID, AGENTEQUIPID, PROTOCOLTYPE, PORTTYPE, "
                 f"AGENTPORTNO, USERID, PASSWORD, GATFLAG, STATUS, COMMANDFLAG) "
                 f"VALUES ({info.Sequence}, '{info.ConnectorId}', '{info.AgentEquipId}', "
                 f"{info.ProtocolType}, {info.PortType}, {info.PortNo}, "
                 f"'{info.UserId}', IF('{info.UserPassword}'='','','{info.UserPassword}'), "
                 f"{info.GatFlag}, {info.SettingStatus}, {info.CommandPortFlag})")
            if not self.execute_query(q):
                _log.error(f"Connection Create({max_seq}) Error")
                return False
            return True

        elif info.RequestStatus == UPDATE_DATA:
            q = (f"UPDATE {DC_CNF_CONNECTION} SET CONNECTORID = '{info.ConnectorId}', "
                 f"AGENTEQUIPID = '{info.AgentEquipId}', PROTOCOLTYPE = {info.ProtocolType}, "
                 f"PORTTYPE = {info.PortType}, AGENTPORTNO = {info.PortNo}, "
                 f"USERID = '{info.UserId}', PASSWORD = '{info.UserPassword}', "
                 f"GATFLAG = {info.GatFlag}, STATUS = {info.SettingStatus}, "
                 f"COMMANDFLAG = {info.CommandPortFlag} WHERE SEQUENCE = {info.Sequence}")
            if not self.execute_query(q):
                _log.error(f"Connection Update({info.Sequence}) Error")
                return False
            return True

        elif info.RequestStatus == DELETE_DATA:
            q = f"DELETE FROM {DC_CNF_CONNECTION} WHERE SEQUENCE = {info.Sequence}"
            if not self.execute_query(q):
                _log.error(f"Connection Delete({info.Sequence}) Error")
                return False
            return True
        return False

    def _recv_data_handler_change(self, info: AS_DATA_HANDLER_INFO_T) -> bool:
        target_info = DbManager.get_ip_info_to_string(info.TargetIpInfoList)

        if info.RequestStatus == CREATE_DATA:
            q = (f"INSERT INTO {DC_EVENT_CONSUMER} "
                 f"(ID, DBUSERID, DBPASSWORD, DBTNS, HOSTNAME, TIMEMODE, LISTENPORT, "
                 f"STATUS, LOGMODE, IPADDRESS, BYPASSLISTENPORT, LOADINGINTERVAL, "
                 f"HANDLERMODE, TARGETINFO, RUNMODE, LOGCYCLE, SSHID, SSHPW, MODIFY_DATE) "
                 f"VALUES ('{info.DataHandlerId}', '{info.DbUserId}', '{info.DbPassword}', "
                 f"'{info.DbName}', '{info.HostName}', {info.TimeMode}, {info.ListenPort}, "
                 f"{info.SettingStatus}, {info.LogMode}, '{info.IpAddress}', "
                 f"{info.BypassListenPort}, {info.LoadingInterval}, {info.OperMode}, "
                 f"'{target_info}', {info.RunMode}, {info.LogCycle}, "
                 f"'{info.SshID}', '{info.SshPass}', NOW())")
            if not self.execute_query(q):
                _log.error(f"Data Handler Create({info.DataHandlerId}) Error")
                return False
            return True

        elif info.RequestStatus == UPDATE_DATA:
            q = (f"UPDATE {DC_EVENT_CONSUMER} SET ID = '{info.DataHandlerId}', "
                 f"DBUSERID = '{info.DbUserId}', DBPASSWORD = '{info.DbPassword}', "
                 f"DBTNS = '{info.DbName}', HOSTNAME = '{info.HostName}', "
                 f"TIMEMODE = {info.TimeMode}, LISTENPORT = {info.ListenPort}, "
                 f"STATUS = {info.SettingStatus}, LOGMODE = {info.LogMode}, "
                 f"IPADDRESS = '{info.IpAddress}', BYPASSLISTENPORT = {info.BypassListenPort}, "
                 f"LOADINGINTERVAL = {info.LoadingInterval}, HANDLERMODE = {info.OperMode}, "
                 f"TARGETINFO = '{target_info}', RUNMODE = {info.RunMode}, "
                 f"LOGCYCLE = {info.LogCycle}, SSHID = '{info.SshID}', SSHPW = '{info.SshPass}', "
                 f"MODIFY_DATE = NOW() WHERE ID = '{info.OldDataHandlerId}'")
            if not self.execute_query(q):
                _log.error(f"Data Handler Update({info.OldDataHandlerId}) Error")
                return False
            return True

        elif info.RequestStatus == DELETE_DATA:
            q = f"DELETE FROM {DC_EVENT_CONSUMER} WHERE ID = '{info.DataHandlerId}'"
            if not self.execute_query(q):
                _log.error(f"Data Handler Delete({info.DataHandlerId}) Error")
                return False
            return True
        return False

    def _recv_sub_proc_change(self, info: AS_SUB_PROC_INFO_T) -> bool:
        if info.RequestStatus == CREATE_DATA:
            q = (f"INSERT INTO {DC_CNF_SUB_PROC} "
                 f"(ID, ID_STR, PARENT, PARENTID, IPADDRESS, HOSTNAME, "
                 f"STATUS, LOGCYCLE, DESCRIPTION, BIN_NAME, ARGS) "
                 f"VALUES (0, '{info.ProcIdStr}', {info.ParentProc}, '{info.ParentId}', "
                 f"'{info.IpAddress}', '{info.HostName}', {info.SettingStatus}, "
                 f"{info.LogCycle}, '{info.Description}', '{info.BinaryName}', '{info.Args}')")
            if not self.execute_query(q):
                _log.error(f"Sub Proc Create({info.ProcIdStr}) Error")
                return False
            return True

        elif info.RequestStatus == UPDATE_DATA:
            q = (f"UPDATE {DC_CNF_SUB_PROC} SET ID_STR = '{info.ProcIdStr}', "
                 f"PARENT = {info.ParentProc}, PARENTID = '{info.ParentId}', "
                 f"IPADDRESS = '{info.IpAddress}', HOSTNAME = '{info.HostName}', "
                 f"STATUS = {info.SettingStatus}, LOGCYCLE = {info.LogCycle}, "
                 f"DESCRIPTION = '{info.Description}', BIN_NAME = '{info.BinaryName}', "
                 f"ARGS = '{info.Args}' WHERE ID_STR = '{info.OldProcIdStr}'")
            if not self.execute_query(q):
                _log.error(f"Sub Proc Update({info.OldProcIdStr}) Error")
                return False
            return True

        elif info.RequestStatus == DELETE_DATA:
            q = f"DELETE FROM {DC_CNF_SUB_PROC} WHERE ID_STR = '{info.ProcIdStr}'"
            if not self.execute_query(q):
                _log.error(f"Sub Proc Delete({info.ProcIdStr}) Error")
                return False
            return True
        return False

    def _recv_command_authority_change(self, info: AS_COMMAND_AUTHORITY_INFO_T) -> bool:
        if info.RequestStatus == CREATE_DATA:
            q = (f"INSERT INTO {DC_CMD_SESSION_IDENT} "
                 f"(ID, MAXCMDQUEUE, PRIORITY, LOGMODE, ACKMODE, DESCRIPTION, MAX_SESSION_CNT) "
                 f"VALUES ('{info.Id}', {info.MaxCmdQueue}, {info.Priority}, "
                 f"{info.LogMode}, {info.AckMode}, '{info.Description}', {info.MaxSessionCnt})")
            if not self.execute_query(q):
                _log.error(f"Command Authority Create({info.Id}) Error")
                return False
            return True

        elif info.RequestStatus == UPDATE_DATA:
            q = (f"UPDATE {DC_CMD_SESSION_IDENT} SET ID = '{info.Id}', "
                 f"MAXCMDQUEUE = {info.MaxCmdQueue}, PRIORITY = {info.Priority}, "
                 f"DESCRIPTION = '{info.Description}', LOGMODE = {info.LogMode}, "
                 f"ACKMODE = {info.AckMode}, MAX_SESSION_CNT = {info.MaxSessionCnt} "
                 f"WHERE ID = '{info.OldId}'")
            if not self.execute_query(q):
                _log.error(f"Command Authority Update({info.OldId}) Error")
                return False
            return True

        elif info.RequestStatus == DELETE_DATA:
            q = f"DELETE FROM {DC_CMD_SESSION_IDENT} WHERE ID = '{info.Id}'"
            if not self.execute_query(q):
                _log.error(f"Command Authority Delete({info.Id}) Error")
                return False
            return True
        return False

    def _recv_rule_change(self, info: AS_RULE_CHANGE_INFO_T) -> bool:
        q = (f"UPDATE {DC_CNF_CONNECTOR} SET RULEID = '{info.RuleId}' "
             f"WHERE GATEWAYID = '{info.ManagerId}' AND ID = '{info.ProcessId}'")
        if not self.execute_query(q):
            _log.error(f"Parsing rule change({info.ProcessId}:{info.RuleId}) Error")
            return False
        return True

    def _recv_connector_desc_change(self, info: AS_CONNECTOR_DESC_CHANGE_INFO_T) -> bool:
        q = (f"UPDATE {DC_CNF_CONNECTOR} SET DESCRIPTION = '{info.Description}' "
             f"WHERE GATEWAYID = '{info.ManagerId}' AND ID = '{info.ConnectorId}'")
        if not self.execute_query(q):
            _log.error(f"Connector description change({info.ConnectorId}) Error")
            return False
        return True

    # ──────────────────────────────────────────
    # 상태 업데이트
    # ──────────────────────────────────────────
    def update_connector_status(self, proc_ctl: AS_PROC_CONTROL_T, time_str: str) -> bool:
        """C++: UpdateConnectorStatus()"""
        if self._m_db_session is None:
            return False
        dt_query = self._m_db_session.make_insert_query(QueryDataType.DATE_TYPE, time_str)
        self.update_connection_status_by_type(ASCII_CONNECTOR, proc_ctl.ProcessId)
        status = START if proc_ctl.Status == START else STOP
        action = ACT_START if proc_ctl.Status == START else ACT_STOP
        q = (f"UPDATE {DC_CNF_CONNECTOR} SET STATUS = {status}, "
             f"LAST_ACTION_DATE = {dt_query}, LAST_ACTION = '{action}', "
             f"LAST_ACTION_DESC = '{proc_ctl.Desc}' "
             f"WHERE GATEWAYID = '{proc_ctl.ManagerId}' AND ID = '{proc_ctl.ProcessId}'")
        return self.execute_query(q)

    UpdateConnectorStatus = update_connector_status

    def update_connection_status(self, session_ctl: AS_SESSION_CONTROL_T) -> bool:
        """C++: UpdateConnectionStatus(AS_SESSION_CONTROL_T*)"""
        self.update_connection_status_by_type(-1, "", session_ctl.Sequence)
        status = START if session_ctl.Status == START else STOP
        q = (f"UPDATE {DC_CNF_CONNECTION} SET STATUS = {status}, "
             f"DESCRIPTION = '{session_ctl.Desc}' WHERE SEQUENCE = {session_ctl.Sequence}")
        return self.execute_query(q)

    UpdateConnectionStatus = update_connection_status

    def update_connection_status_by_type(self, type_: int, id_: str,
                                          sequence: int = -1,
                                          info: Optional[AS_PORT_STATUS_INFO_T] = None) -> bool:
        """C++: UpdateConnectionStatus(int Type, string Id, int Sequence, AS_PORT_STATUS_INFO_T*)"""
        if type_ == ASCII_MANAGER:
            q = f"DELETE FROM {DC_STATUS_CMD_PORT} WHERE MANAGERID = '{id_}'"
            return self.execute_query(q)
        elif type_ == ASCII_CONNECTOR:
            q = f"DELETE FROM {DC_STATUS_CMD_PORT} WHERE CONNECTORID = '{id_}'"
            return self.execute_query(q)
        else:
            if info:
                if info.PortType in (CMD, LUCENT_ECP_CMD, LUCENT_DCS_CMD):
                    q = f"DELETE FROM {DC_STATUS_CMD_PORT} WHERE SEQUENCE = {sequence}"
                    if not self.execute_query(q):
                        return False
                    if info.Status != PORT_ELIMINATION:
                        q = (f"INSERT INTO {DC_STATUS_CMD_PORT} "
                             f"(SEQUENCE, MANAGERID, CONNECTORID, EQUIPID, STATUS) "
                             f"VALUES ({sequence}, '{info.ManagerId}', '{info.ConnectorId}', "
                             f"'{info.ConnectorId}', {info.Status})")
                        if not self.execute_query(q):
                            return False
            else:
                q = f"DELETE FROM {DC_STATUS_CMD_PORT} WHERE SEQUENCE = {sequence}"
                if not self.execute_query(q):
                    return False
        return True

    def update_manager_status(self, manager_id: str, status: int, desc: str) -> bool:
        """C++: UpdateManagerStatus()"""
        self.update_connection_status_by_type(ASCII_MANAGER, manager_id)
        s = START if status == START else STOP
        q = (f"UPDATE {DC_CNF_MANAGER} SET STATUS = {s}, "
             f"DESCRIPTION = '{desc}' WHERE ID = '{manager_id}'")
        return self.execute_query(q)

    UpdateManagerStatus = update_manager_status

    def update_data_handler_status(self, data_handler_id: str, status: int) -> bool:
        s = START if status == START else STOP
        q = (f"UPDATE {DC_EVENT_CONSUMER} SET STATUS = {s}, MODIFY_DATE = NOW() "
             f"WHERE ID = '{data_handler_id}'")
        return self.execute_query(q)

    UpdateDataHandlerStatus = update_data_handler_status

    def update_sub_proc_status(self, proc_id_str: str, status: int) -> bool:
        s = START if status == START else STOP
        q = f"UPDATE {DC_CNF_SUB_PROC} SET STATUS = {s} WHERE ID_STR = '{proc_id_str}'"
        return self.execute_query(q)

    UpdateSubProcStatus = update_sub_proc_status

    def delete_connection_status(self) -> bool:
        """C++: DeleteConnectionStatus()"""
        q = f"DELETE FROM {DC_STATUS_CMD_PORT}"
        if not self.execute_query(q):
            _log.error("DeleteConnectionStatus error")
            return False
        return True

    DeleteConnectionStatus = delete_connection_status

    def disable_manager_from_ip(self, manager_ip: str) -> bool:
        """C++: DisableManagerFromIp()"""
        q = (f"UPDATE {DC_CNF_MANAGER} SET STATUS = {STOP} "
             f"WHERE IP = '{manager_ip}'")
        return self.execute_query(q)

    DisableManagerFromIp = disable_manager_from_ip

    # ──────────────────────────────────────────
    # DB Sync 정보
    # ──────────────────────────────────────────
    def get_db_sync_info(self, info_list: AS_DB_SYNC_INFO_LIST_T) -> bool:
        """C++: GetDbSyncInfo()"""
        query = ("SELECT TABLENAME, TO_CHAR(SYNCTIME, 'YYYY/MM/DD HH24:MI:SS') "
                 "FROM DC_SYNCTB_INFO")
        rs = self._execute_select(query)
        if rs is None:
            return False
        info_list.Count = 0
        for row in rs:
            idx = info_list.Count
            info_list.InfoList[idx].TableName = row[0] or ""
            info_list.InfoList[idx].SyncTime  = row[1] or ""
            info_list.Count += 1
        return True

    GetDbSyncInfo = get_db_sync_info

    # ──────────────────────────────────────────
    # MMC 결과 저장
    # ──────────────────────────────────────────
    def insert_mmc_result(self, result: MMCResultStored) -> bool:
        """C++: InsertMMCResult()"""
        result.ResultMsg = result.ResultMsg.replace("'", "''")

        from Common.AsUtil import AsUtil
        q = (f"INSERT INTO {DC_MMC_RESULT} "
             f"(EQUIPID, GID, EXTID, RESULTMODE, USERID, IPADDRESS, "
             f"ISSUEDDATE, RESULTSTARTTIME, RESULTENDTIME, COMMAND) "
             f"VALUES ('{result.MmcInfo.ne}', {result.Gid}, {result.ExtId}, "
             f"'{AsUtil.GetEnumTypeString_RESULT_MODE(result.ResultMode)}', "
             f"'{result.MmcInfo.userid}', '{result.MmcInfo.display}', "
             f"TO_DATE('{result.IssuedTimeStr}',    'YYYY/MM/DD HH24:MI:SS'), "
             f"TO_DATE('{result.ResultStartTime}',  'YYYY/MM/DD HH24:MI:SS'), "
             f"TO_DATE('{result.ResultEndTime}',    'YYYY/MM/DD HH24:MI:SS'), "
             f"'{result.MmcInfo.mmc}')")

        if self.execute_query(q, False):
            where = (f"GID = {result.Gid} AND "
                     f"ISSUEDDATE = TO_DATE('{result.IssuedTimeStr}', 'YYYY/MM/DD HH24:MI:SS')")
            if self._m_db_session.update_long(
                    DC_MMC_RESULT, "RESULTMSG", result.ResultMsg, where):
                self.commit()
                return True
            else:
                _log.error(f"Fail to query [{self.get_error_msg()}]")
                self.roll_back()
                return False
        return False

    InsertMMCResult = insert_mmc_result

    # ──────────────────────────────────────────
    # ServerInfo 업데이트
    # ──────────────────────────────────────────
    def update_server_info(self, ip: str, gui_port: int, cmd_port: int,
                           log_port: int, sock_mgr_port: int,
                           net_finder_port: int) -> bool:
        """C++: UpdateServerInfo() — 현재 구현은 즉시 return true"""
        return True

    UpdateServerInfo = update_server_info

    # ──────────────────────────────────────────
    # IP 정보 변환 (static)
    # ──────────────────────────────────────────
    @staticmethod
    def get_string_to_ip_info(target_info: str,
                               info_list: AS_TARGET_IP_INFO_LIST_T) -> bool:
        """C++: GetStringToIpInfo() — 'ip:port|ip:port|...' 파싱"""
        if "|" not in target_info:
            return False

        info_list.Size = 0
        for token in target_info.split("|"):
            if not token:
                continue
            if ":" in token:
                ip_str, port_str = token.split(":", 1)
                port = int(port_str) if port_str.isdigit() else 0
                if port == 0:
                    _log.error(f"Invalid port : {port_str}")
                    continue
                entry = AS_TARGET_IP_INFO_T()
                entry.IpAddress = ip_str
                entry.PortNo    = port
                info_list.TargetIpInfo[info_list.Size] = entry
                info_list.Size += 1
            else:
                _log.error(f"Invalid ipinfo format : {token}")
        return True

    GetStringToIpInfo = staticmethod(get_string_to_ip_info)

    @staticmethod
    def get_ip_info_to_string(info_list: AS_TARGET_IP_INFO_LIST_T) -> str:
        """C++: GetIpInfoToString() — AS_TARGET_IP_INFO_LIST_T → 'ip:port|...' 문자열"""
        parts = []
        for i in range(info_list.Size):
            entry = info_list.TargetIpInfo[i]
            parts.append(f"{entry.IpAddress}:{entry.PortNo}|")
        return "".join(parts)

    GetIpInfoToString = staticmethod(get_ip_info_to_string)

    # ──────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────
    def _execute_select(self, query: str):
        """SELECT 쿼리 실행 후 ResultSet 반환. 실패 시 None."""
        if self._m_db_session is None:
            self.get_db_instance()
            if self._m_db_session is None:
                return None
        try:
            return self._m_db_session.execute_rs(query)
        except Exception as e:
            _log.error(f"execute_rs error : {e}")
            self.get_db_instance()
            return None