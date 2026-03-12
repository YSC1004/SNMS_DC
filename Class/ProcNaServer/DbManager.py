"""
DbManager.py
C++ DbManager.h/.C → Python 변환

ProcNaServer DB 접근 클래스.
  - MySQLSession (fr_mysql_session.py) 래핑
  - Manager / Connector / Connection / DataHandler / SubProc 정보 조회·변경
  - MMC 결과 저장, 서버 정보 업데이트
  - 자동 재접속 (GetDBInstance)
"""

import logging
from typing import Optional

from Class.Sql.fr_db_session import DbSession
from Class.Sql.fr_mysql_session import MySQLSession
from Class.SqlType.fr_db_param import DbParam

# ── Common / Type 모듈 ────────────────────────────────────────────────────────
from Common.CommTypeList import (
    AS_MANAGER_INFO_T, AS_CONNECTOR_INFO_T, AS_CONNECTION_INFO_T,
    AS_DATA_HANDLER_INFO_T, AS_SUB_PROC_INFO_T,
    AS_COMMAND_AUTHORITY_INFO_T, AS_RULE_CHANGE_INFO_T,
    AS_CONNECTOR_DESC_CHANGE_INFO_T, AS_SESSION_CONTROL_T,
    AS_PROC_CONTROL_T, AS_PORT_STATUS_INFO_T,
    AS_DB_SYNC_INFO_LIST_T, AS_TARGET_IP_INFO_LIST_T, AS_TARGET_IP_INFO_T,
)
from Common.CommType import (
    ASCII_MANAGER, ASCII_CONNECTOR,
    START, STOP, WAIT_NO, UNDEFINED,
    CREATE_DATA, UPDATE_DATA, DELETE_DATA,
    ACT_START, ACT_STOP, ACT_CREATE, ACT_MODIFY,
    CMD, LUCENT_ECP_CMD, LUCENT_DCS_CMD,
    PORT_ELIMINATION,
)
from Common.AsUtil import AsUtil

# ── ProcNaServer 내부 타입 ────────────────────────────────────────────────────
from ProcNaServer.AsciiServerType import (
    ManagerInfo, ManagerInfoMap,
    ConnectorInfo, ConnectorInfoMap,
    CommandAuthorityInfoMap,
    MMCResultStored,
)

# ── DB 테이블 명 상수 ──────────────────────────────────────────────────────────
DC_CNF_MANAGER           = "DC_CNF_MANAGER"
DC_CNF_CONNECTOR         = "DC_CNF_CONNECTOR"
DC_CNF_CONNECTOR_DELETED = "DC_CNF_CONNECTOR_DELETED"
DC_CNF_CONNECTION        = "DC_CNF_CONNECTION"
DC_CNF_SERVER            = "DC_CNF_SERVER"
DC_CNF_SUB_PROC          = "DC_CNF_SUB_PROC"
DC_EVENT_CONSUMER        = "DC_EVENT_CONSUMER"
DC_STATUS_CMD_PORT       = "DC_STATUS_CMD_PORT"
DC_CMD_SESSION_IDENT     = "DC_CMD_SESSION_IDENT"
DC_RUL_RULE              = "DC_RUL_RULE"
DC_MMC_RESULT            = "DC_MMC_RESULT"
TBD_EQP_HOSTHW           = "TBD_EQP_HOSTHW"

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
class DbManager:
    """
    ProcNaServer DB 접근 관리자.
    C++ DbManager (frDbSession 래핑) → MySQLSession 래핑.

    사용 예:
        db = DbManager()
        if db.InitDbManager("user", "pass", "dbname", "127.0.0.1", "3306"):
            db.GetManagerInfo(info_map)
    """

    def __init__(self) -> None:
        self._session: Optional[MySQLSession] = None
        self._db_id:   str = ""
        self._db_pass: str = ""
        self._db_tns:  str = ""   # MySQL에서는 database name
        self._db_ip:   str = ""
        self._db_port: str = ""

    def __del__(self) -> None:
        if self._session:
            self._session.disconnect()
        self._db_id = self._db_pass = self._db_tns = ""
        self._db_ip = self._db_port = ""

    # =========================================================================
    # 연결 관리
    # =========================================================================

    def InitDbManager(self, user_name: str, password: str, tns_name: str,
                      db_ip: str, db_port: str) -> bool:
        """
        DB 초기 연결.
        C++: InitDbManager(char* UserName, char* PassWord, char* TnsName,
                           char* DbIp, char* DbPort)
        """
        if self._session:
            self._session.disconnect()
            self._session = None

        self._db_id   = user_name
        self._db_pass = password
        self._db_tns  = tns_name
        self._db_ip   = db_ip
        self._db_port = db_port

        port = int(db_port) if db_port else 3306
        logger.error("db=%s, %s, %s, %s, %d",
                     user_name, password, tns_name, db_ip, port)

        self._session = MySQLSession()
        if not self._session.connect(user_name, password, tns_name, db_ip, port):
            logger.error("Can't connect DB(%s) : [%d] %s",
                         user_name,
                         self._session.get_error_code(),
                         self._session.get_error())
            self._session = None
            return False
        return True

    def GetDBInstance(self) -> bool:
        """
        자동 재접속.
        C++: GetDBInstance()
        """
        logger.error("try auto reconnect to db")
        logger.error("### GetDBInstance ###")

        try:
            from ProcNaServer.AsciiServerWorld import MAINPTR
            MAINPTR().SendAsciiError(1, "try auto reconnect to db")
        except Exception:
            pass

        if self._session:
            self._session.disconnect()
            self._session = None

        port = int(self._db_port) if self._db_port else 3306
        self._session = MySQLSession()
        if not self._session.connect(
                self._db_id, self._db_pass, self._db_tns, self._db_ip, port):
            logger.error("Reconnect to db Fail!!!!")
            self._session = None
            return False

        logger.debug("Reconnect to db!!")
        return True

    def DisConnection(self) -> None:
        """C++: DisConnection()"""
        if self._session:
            self._session.disconnect()

    def Commit(self) -> None:
        if self._session:
            self._session.commit()

    def RollBack(self) -> None:
        if self._session:
            self._session.rollback()

    def GetErrorMsg(self) -> str:
        """C++: GetErrorMsg()"""
        if self._session:
            return self._session.get_error()
        return "ERROR DB"

    # =========================================================================
    # 쿼리 실행 (내부)
    # =========================================================================

    def ExecuteQuery(self, query: str, auto_commit: bool = True) -> bool:
        """
        DML 문자열 쿼리 실행.
        C++: ExecuteQuery(char* Query, bool AutoCommit = true)
        """
        logger.debug("[SQL] %s", query)

        if self._session is None:
            logger.debug("DB Query Error - DB Error")
            self.GetDBInstance()
            self._notify_error("DB Query Error - DB Error")
            return False

        if not self._session.execute_query(query, auto_commit=auto_commit):
            logger.debug("DB Query Error - %s", query)
            self.GetDBInstance()
            self._notify_error(f"DB Query Error - {query}")
            return False
        return True

    def _execute_select(self, query: str) -> Optional[DbParam]:
        """
        SELECT 쿼리를 실행하고 결과가 담긴 DbParam 반환. 실패 시 None.
        C++: ExecuteQuery(frDbParam*) 대응.
        """
        logger.debug("[SQL] %s", query)

        if self._session is None:
            self.GetDBInstance()
            return None

        param = DbParam()
        param.set_query(query)
        if not self._session.execute(param):
            logger.debug("DB Query Error - %s", query)
            self.GetDBInstance()
            self._notify_error(f"DB Query Error - {query}")
            return None
        return param

    def _notify_error(self, msg: str) -> None:
        """C++: MAINPTR->SendAsciiError() 대응."""
        try:
            from ProcNaServer.AsciiServerWorld import MAINPTR
            MAINPTR().SendAsciiError(1, msg)
        except Exception:
            pass

    # =========================================================================
    # 정보 조회
    # =========================================================================

    def GetCurrentMsgId(self) -> int:
        """
        C++: GetCurrentMsgId()
        원본 C++ 구현이 항상 1을 반환하므로 동일하게 유지.
        """
        return 1

    def GetCommandAuthorityInfo(self, info_map: CommandAuthorityInfoMap) -> None:
        """
        C++: GetCommandAuthorityInfo(CommandAuthorityInfoMap* Info)
        DC_CMD_SESSION_IDENT 테이블에서 명령 권한 정보 조회.
        """
        query = (
            f"SELECT ID, MAXCMDQUEUE, PRIORITY, LOGMODE, ACKMODE, "
            f"DESCRIPTION, MAX_SESSION_CNT FROM {DC_CMD_SESSION_IDENT}"
        )
        param = self._execute_select(query)
        if param is None:
            return

        while param.next():
            info = AS_COMMAND_AUTHORITY_INFO_T()
            info.Id            = param.get_value_str(0)
            info.MaxCmdQueue   = param.get_value_int(1)
            info.Priority      = param.get_value_int(2)
            info.LogMode       = param.get_value_int(3)
            info.AckMode       = param.get_value_int(4)
            info.Description   = param.get_value_str(5)
            info.MaxSessionCnt = param.get_value_int(6)
            logger.debug("Cmd Session Ident : %s, QueueSize : %d",
                         info.Id, info.MaxCmdQueue)
            info_map[info.Id] = info

    def GetManagerInfo(self, info_map: ManagerInfoMap) -> bool:
        """
        C++: GetManagerInfo(ManagerInfoMap* InfoMap)
        1) DC_CNF_MANAGER        → ManagerInfo 목록 구성
        2) Connector+Connection  → 하위 구조 채움
        """
        # ── 1단계: Manager 기본 정보 ─────────────────────────────────────
        q1 = f"SELECT ID, IP, STATUS, SSHID, SSHPW FROM {DC_CNF_MANAGER}"
        param = self._execute_select(q1)
        if param is None:
            return False

        while param.next():
            mgr = ManagerInfo()
            mgr.m_ManagerInfo.ManagerId     = param.get_value_str(0)
            mgr.m_ManagerInfo.IP            = param.get_value_str(1)
            mgr.m_ManagerInfo.SettingStatus = param.get_value_int(2)
            mgr.m_ManagerInfo.SshID         = param.get_value_str(3)
            mgr.m_ManagerInfo.SshPass       = param.get_value_str(4)
            mgr.m_ManagerInfo.CurStatus     = STOP
            mgr.m_ManagerInfo.RequestStatus = WAIT_NO
            info_map[mgr.m_ManagerInfo.ManagerId] = mgr

        # ── 2단계: Connector + Connection 상세 ───────────────────────────
        q2 = (
            f"SELECT CR.GATEWAYID, CM.IP, CM.STATUS, CR.ID, CR.STATUS, CR.RULEID, "
            f"RI.IDENTIFICATIONTYPE, CR.JUNCTIONTYPE, "
            f"CC.SEQUENCE, CC.AGENTEQUIPID, CC.PROTOCOLTYPE, CC.PORTTYPE, CC.AGENTPORTNO, "
            f"CC.USERID, CC.PASSWORD, CC.GATFLAG, CC.COMMANDFLAG, CC.STATUS, "
            f"CR.CMDRESPONSETYPE, CR.LOGCYCLE, "
            f"DATE_FORMAT(CR.CREATE_DATE, '%Y/%m/%d %H:%i:%s'), "
            f"DATE_FORMAT(CR.MODIFY_DATE, '%Y/%m/%d %H:%i:%s'), "
            f"DATE_FORMAT(CR.LAST_ACTION_DATE, '%Y/%m/%d %H:%i:%s'), "
            f"CR.LAST_ACTION, CR.LAST_ACTION_DESC, CR.DESCRIPTION, HD.CURRENTEQUIPID "
            f"FROM {DC_CNF_CONNECTOR} CR "
            f"INNER JOIN {DC_CNF_MANAGER} CM ON CR.GATEWAYID = CM.ID "
            f"INNER JOIN {DC_RUL_RULE} RI ON CR.RULEID = RI.ID "
            f"INNER JOIN {TBD_EQP_HOSTHW} HD ON CR.ID = HD.EQUIPID "
            f"LEFT JOIN {DC_CNF_CONNECTION} CC ON CR.ID = CC.CONNECTORID "
            f"ORDER BY CR.GATEWAYID, HD.CURRENTEQUIPID, "
            f"CC.PROTOCOLTYPE, CC.AGENTPORTNO, CC.PORTTYPE"
        )
        param = self._execute_select(q2)
        if param is None:
            return False

        while param.next():
            manager_id        = param.get_value_str(0)
            connector_id      = param.get_value_str(3)
            conn_status       = param.get_value_int(4)
            rule_id           = param.get_value_str(5)
            mmc_ident_type    = param.get_value_int(6)
            junction_type     = param.get_value_int(7)
            seq               = param.get_value_int(8)
            agent_equip_id    = param.get_value_str(9)
            protocol_type     = param.get_value_int(10)
            port_type         = param.get_value_int(11)
            port_no           = param.get_value_int(12)
            user_id           = param.get_value_str(13)
            password          = param.get_value_str(14)
            gat_flag          = param.get_value_int(15)
            cmd_flag          = param.get_value_int(16)
            setting_conn_st   = param.get_value_int(17)
            cmd_response_type = param.get_value_int(18)
            log_cycle         = param.get_value_int(19)
            create_date       = param.get_value_str(20)
            modify_date       = param.get_value_str(21)
            last_action_date  = param.get_value_str(22)
            last_action_type  = param.get_value_str(23)
            last_action_desc  = param.get_value_str(24)
            desc_             = param.get_value_str(25)

            mgr_info = info_map.get(manager_id)
            if mgr_info is None:
                logger.error("Can't Find Manager : %s", manager_id)
                continue

            # ConnectorInfo 없으면 생성
            con_info = mgr_info.m_ConnectorInfoMap.get(connector_id)
            if con_info is None:
                con_info = ConnectorInfo()
                mgr_info.m_ConnectorInfoMap[connector_id] = con_info
                con_info.m_ConnectorInfo.ManagerId       = manager_id
                con_info.m_ConnectorInfo.ConnectorId     = connector_id
                con_info.m_ConnectorInfo.RuleId          = rule_id
                con_info.m_ConnectorInfo.SettingStatus   = conn_status
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
                logger.debug("Connector Status : %s/%s[%s]",
                             manager_id, connector_id,
                             "START" if conn_status == START else "STOP")

            # seq == 0 이면 Connection 없음 (C++ 원본 동일)
            if not seq:
                continue

            conn = AS_CONNECTION_INFO_T()
            conn.ManagerId       = manager_id
            conn.ConnectorId     = connector_id
            conn.AgentEquipId    = agent_equip_id
            conn.UserId          = user_id
            conn.UserPassword    = password
            conn.Sequence        = seq
            conn.PortNo          = port_no
            conn.ProtocolType    = protocol_type
            conn.PortType        = port_type
            conn.GatFlag         = gat_flag
            conn.CommandPortFlag = cmd_flag
            conn.SettingStatus   = setting_conn_st
            conn.CurStatus       = UNDEFINED
            conn.RequestStatus   = WAIT_NO
            con_info.m_ConnectionInfoList.append(conn)

        return True

    def GetManagerInfoFindId(self, manager_info: ManagerInfo) -> bool:
        """C++: GetManagerInfoFindId(ManagerInfo* managerinfo)"""
        mgr_id = manager_info.m_ManagerInfo.ManagerId
        query = (
            f"SELECT ID, IP, STATUS, SSHID, SSHPW "
            f"FROM {DC_CNF_MANAGER} WHERE ID = '{mgr_id}'"
        )
        param = self._execute_select(query)
        if param is None:
            return False

        if not param.next():
            return False

        logger.error("GetManagerInfoFindId FIND ID=(%s), PASS=(%s)",
                     param.get_value_str(3), param.get_value_str(4))
        manager_info.m_ManagerInfo.ManagerId     = param.get_value_str(0)
        manager_info.m_ManagerInfo.IP            = param.get_value_str(1)
        manager_info.m_ManagerInfo.SettingStatus = param.get_value_int(2)
        manager_info.m_ManagerInfo.SshID         = param.get_value_str(3)
        manager_info.m_ManagerInfo.SshPass       = param.get_value_str(4)
        manager_info.m_ManagerInfo.CurStatus     = STOP
        manager_info.m_ManagerInfo.RequestStatus = WAIT_NO
        return True

    def GetDataHandlerInfo(self, info_map: dict) -> bool:
        """C++: GetDataHandlerInfo(DataHandlerInfoMap* InfoMap)"""
        query = (
            f"SELECT ID, DBUSERID, DBPASSWORD, DBTNS, HOSTNAME, TIMEMODE, LISTENPORT, "
            f"STATUS, LOGMODE, IPADDRESS, BYPASSLISTENPORT, LOADINGINTERVAL, HANDLERMODE, "
            f"TARGETINFO, RUNMODE, LOGCYCLE, SSHID, SSHPW "
            f"FROM {DC_EVENT_CONSUMER}"
        )
        param = self._execute_select(query)
        if param is None:
            return False

        while param.next():
            info = AS_DATA_HANDLER_INFO_T()
            info.DataHandlerId    = param.get_value_str(0)
            info.DbUserId         = param.get_value_str(1)
            info.DbPassword       = param.get_value_str(2)
            info.DbName           = param.get_value_str(3)
            info.HostName         = param.get_value_str(4)
            info.TimeMode         = param.get_value_int(5)
            info.ListenPort       = param.get_value_int(6)
            info.SettingStatus    = param.get_value_int(7)
            info.LogMode          = param.get_value_int(8)
            info.IpAddress        = param.get_value_str(9)
            info.BypassListenPort = param.get_value_int(10)
            info.LoadingInterval  = param.get_value_int(11)
            info.OperMode         = param.get_value_int(12)
            target_info_str       = param.get_value_str(13)
            info.RunMode          = param.get_value_int(14)
            info.LogCycle         = param.get_value_int(15)
            info.SshID            = param.get_value_str(16)
            info.SshPass          = param.get_value_str(17)
            info.CurStatus        = STOP
            info.RequestStatus    = WAIT_NO
            self.GetStringToIpInfo(target_info_str, info.TargetIpInfoList)
            info_map[info.DataHandlerId] = info

        return True

    def GetDataHandlerInfoFindId(self, info: AS_DATA_HANDLER_INFO_T) -> bool:
        """C++: GetDataHandlerInfoFindId(AS_DATA_HANDLER_INFO_T* Info)"""
        query = (
            f"SELECT ID, SSHID, SSHPW "
            f"FROM {DC_EVENT_CONSUMER} WHERE ID = '{info.DataHandlerId}'"
        )
        param = self._execute_select(query)
        if param is None:
            return False

        if param.next():
            info.SshID  = param.get_value_str(1)
            info.SshPass = param.get_value_str(2)
        return True

    def GetSubProcInfo(self, info_map: dict) -> bool:
        """C++: GetSubProcInfo(SubProcInfoMap* InfoMap)"""
        query = (
            f"SELECT ID, ID_STR, PARENT, PARENTID, IPADDRESS, HOSTNAME, "
            f"STATUS, LOGCYCLE, DESCRIPTION, BIN_NAME, ARGS "
            f"FROM {DC_CNF_SUB_PROC}"
        )
        param = self._execute_select(query)
        if param is None:
            return False

        while param.next():
            info = AS_SUB_PROC_INFO_T()
            info.ProcId        = param.get_value_int(0)
            info.ProcIdStr     = param.get_value_str(1)
            info.ParentProc    = param.get_value_int(2)
            info.ParentId      = param.get_value_str(3)
            info.IpAddress     = param.get_value_str(4)
            info.HostName      = param.get_value_str(5)
            info.SettingStatus = param.get_value_int(6)
            info.LogCycle      = param.get_value_int(7)
            info.Description   = param.get_value_str(8)
            info.BinaryName    = param.get_value_str(9)
            info.Args          = param.get_value_str(10)
            info.CurStatus     = STOP
            info.RequestStatus = WAIT_NO
            info_map[info.ProcIdStr] = info

        return True

    def GetConnectionIpInfo(self, ip_info: dict,
                             connector_id: str, sequence: int = -1) -> bool:
        """C++: GetConnectionIpInfo(IntStringMap&, string ConnectorId, int Sequence=-1)"""
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
                f"AND CC.CONNECTORID = '{connector_id}' "
                f"AND CC.SEQUENCE = {sequence}"
            )
        param = self._execute_select(query)
        if param is None:
            return False

        while param.next():
            ip_info[param.get_value_int(0)] = param.get_value_str(1)
        return True

    def GetDbSyncInfo(self, info_list: AS_DB_SYNC_INFO_LIST_T) -> bool:
        """C++: GetDbSyncInfo(AS_DB_SYNC_INFO_LIST_T& InfoList)"""
        query = (
            "SELECT TABLENAME, "
            "DATE_FORMAT(SYNCTIME, '%Y/%m/%d %H:%i:%s') "
            "FROM DC_SYNCTB_INFO"
        )
        param = self._execute_select(query)
        if param is None:
            return False

        info_list.Count = 0
        while param.next():
            if info_list.Count >= len(info_list.InfoList):
                break
            entry = info_list.InfoList[info_list.Count]
            entry.TableName = param.get_value_str(0)
            entry.SyncTime  = param.get_value_str(1)
            info_list.Count += 1

        return True

    # =========================================================================
    # 상태 업데이트
    # =========================================================================

    def UpdateManagerStatus(self, manager_id: str, status: int, desc: str) -> bool:
        """C++: UpdateManagerStatus(string ManagerId, int Status, string Desc)"""
        self.UpdateConnectionStatus_by_type(ASCII_MANAGER, manager_id)
        st = START if status == START else STOP
        query = (
            f"UPDATE {DC_CNF_MANAGER} SET STATUS = {st}, DESCRIPTION = '{desc}' "
            f"WHERE ID = '{manager_id}'"
        )
        return self.ExecuteQuery(query)

    def UpdateConnectorStatus(self, proc_ctl: AS_PROC_CONTROL_T,
                               time_str: str) -> bool:
        """C++: UpdateConnectorStatus(AS_PROC_CONTROL_T* ProcCtl, string TimeStr)"""
        if self._session is None:
            return False

        self.UpdateConnectionStatus_by_type(ASCII_CONNECTOR, proc_ctl.ProcessId)
        st     = START if proc_ctl.Status == START else STOP
        action = AsUtil.GetEnumTypeString(
            ACT_START if proc_ctl.Status == START else ACT_STOP)
        query = (
            f"UPDATE {DC_CNF_CONNECTOR} "
            f"SET STATUS = {st}, LAST_ACTION_DATE = NOW(), "
            f"LAST_ACTION = '{action}', LAST_ACTION_DESC = '{proc_ctl.Desc}' "
            f"WHERE GATEWAYID = '{proc_ctl.ManagerId}' "
            f"AND ID = '{proc_ctl.ProcessId}'"
        )
        return self.ExecuteQuery(query)

    def UpdateConnectionStatus(self, session_ctl: AS_SESSION_CONTROL_T) -> bool:
        """C++: UpdateConnectionStatus(AS_SESSION_CONTROL_T* SessionCtl)"""
        self.UpdateConnectionStatus_by_type(-1, "", session_ctl.Sequence)
        st = START if session_ctl.Status == START else STOP
        query = (
            f"UPDATE {DC_CNF_CONNECTION} "
            f"SET STATUS = {st}, DESCRIPTION = '{session_ctl.Desc}' "
            f"WHERE SEQUENCE = {session_ctl.Sequence}"
        )
        return self.ExecuteQuery(query)

    def UpdateConnectionStatus_by_type(self, type_: int, id_: str,
                                        sequence: int = -1,
                                        info: Optional[AS_PORT_STATUS_INFO_T] = None
                                        ) -> bool:
        """
        C++: UpdateConnectionStatus(int Type, string Id, int Sequence,
                                    AS_PORT_STATUS_INFO_T*)
        Sims용 커맨드 포트 상태 업데이트.
        """
        if type_ == ASCII_MANAGER:
            return self.ExecuteQuery(
                f"DELETE FROM {DC_STATUS_CMD_PORT} WHERE MANAGERID = '{id_}'")

        if type_ == ASCII_CONNECTOR:
            return self.ExecuteQuery(
                f"DELETE FROM {DC_STATUS_CMD_PORT} WHERE CONNECTORID = '{id_}'")

        # 개별 시퀀스 처리
        if info:
            if info.PortType in (CMD, LUCENT_ECP_CMD, LUCENT_DCS_CMD):
                if not self.ExecuteQuery(
                        f"DELETE FROM {DC_STATUS_CMD_PORT} WHERE SEQUENCE = {sequence}"):
                    return False
                if info.Status != PORT_ELIMINATION:
                    return self.ExecuteQuery(
                        f"INSERT INTO {DC_STATUS_CMD_PORT} "
                        f"(SEQUENCE, MANAGERID, CONNECTORID, EQUIPID, STATUS) "
                        f"VALUES ({sequence}, '{info.ManagerId}', "
                        f"'{info.ConnectorId}', '{info.ConnectorId}', {info.Status})")
        else:
            return self.ExecuteQuery(
                f"DELETE FROM {DC_STATUS_CMD_PORT} WHERE SEQUENCE = {sequence}")

        return True

    def UpdateDataHandlerStatus(self, data_handler_id: str, status: int) -> bool:
        """C++: UpdateDataHandlerStatus(string DataHandlerId, int Status)"""
        st = START if status == START else STOP
        return self.ExecuteQuery(
            f"UPDATE {DC_EVENT_CONSUMER} "
            f"SET STATUS = {st}, MODIFY_DATE = NOW() "
            f"WHERE ID = '{data_handler_id}'"
        )

    def UpdateSubProcStatus(self, proc_id_str: str, status: int) -> bool:
        """C++: UpdateSubProcStatus(string ProcIdStr, int Status)"""
        st = START if status == START else STOP
        return self.ExecuteQuery(
            f"UPDATE {DC_CNF_SUB_PROC} SET STATUS = {st} "
            f"WHERE ID_STR = '{proc_id_str}'"
        )

    def DeleteConnectionStatus(self) -> bool:
        """C++: DeleteConnectionStatus() → DC_STATUS_CMD_PORT 전체 삭제."""
        if not self.ExecuteQuery(f"DELETE FROM {DC_STATUS_CMD_PORT}"):
            logger.error("DeleteConnectionStatus error")
            return False
        return True

    def DisableManagerFromIp(self, manager_ip: str) -> bool:
        """C++: DisableManagerFromIp(string ManagerIp)"""
        return self.ExecuteQuery(
            f"UPDATE {DC_CNF_MANAGER} SET STATUS = {STOP} "
            f"WHERE IP = '{manager_ip}'"
        )

    def UpdateServerInfo(self, ip: str, gui_port: int, cmd_port: int,
                          log_port: int, sock_mgr_port: int,
                          net_finder_port: int) -> bool:
        """
        C++: UpdateServerInfo(...)
        원본 C++ 구현이 즉시 return true 이므로 동일하게 유지.
        """
        return True

    # =========================================================================
    # InfoChange (CRUD)
    # =========================================================================

    def RecvInfoChange(self, info) -> bool:
        """C++ 오버로드 6종 → 타입 분기."""
        dispatch = {
            AS_MANAGER_INFO_T:               self._recv_manager,
            AS_CONNECTOR_INFO_T:             self._recv_connector,
            AS_CONNECTION_INFO_T:            self._recv_connection,
            AS_DATA_HANDLER_INFO_T:          self._recv_data_handler,
            AS_SUB_PROC_INFO_T:              self._recv_sub_proc,
            AS_COMMAND_AUTHORITY_INFO_T:     self._recv_command_authority,
            AS_RULE_CHANGE_INFO_T:           self._recv_rule_change,
            AS_CONNECTOR_DESC_CHANGE_INFO_T: self._recv_connector_desc_change,
        }
        handler = dispatch.get(type(info))
        if handler:
            return handler(info)
        logger.error("RecvInfoChange: Unknown type %s", type(info))
        return False

    # ── Manager ───────────────────────────────────────────────────────────────
    def _recv_manager(self, info: AS_MANAGER_INFO_T) -> bool:
        if info.RequestStatus == CREATE_DATA:
            return self.ExecuteQuery(
                f"INSERT INTO {DC_CNF_MANAGER} (ID, IP, STATUS, SSHID, SSHPW) "
                f"VALUES ('{info.ManagerId}', '{info.IP}', {info.SettingStatus}, "
                f"'{info.SshID}', '{info.SshPass}')"
            )

        if info.RequestStatus == UPDATE_DATA:
            if not self.ExecuteQuery(
                    f"UPDATE {DC_CNF_CONNECTOR} SET GATEWAYID = '{info.ManagerId}' "
                    f"WHERE GATEWAYID = '{info.OldManagerId}'",
                    auto_commit=False):
                logger.error("Manager Update(%s) Error", info.OldManagerId)
                return False
            if not self.ExecuteQuery(
                    f"UPDATE {DC_CNF_MANAGER} "
                    f"SET ID = '{info.ManagerId}', IP = '{info.IP}', "
                    f"STATUS = {info.SettingStatus}, "
                    f"SSHID = '{info.SshID}', SSHPW = '{info.SshPass}' "
                    f"WHERE ID = '{info.OldManagerId}'",
                    auto_commit=False):
                self.RollBack()
                logger.error("Manager Update(%s) Error", info.OldManagerId)
                return False
            self.Commit()
            return True

        if info.RequestStatus == DELETE_DATA:
            if not self.ExecuteQuery(
                    f"DELETE FROM {DC_CNF_CONNECTION} "
                    f"WHERE CONNECTORID IN "
                    f"(SELECT ID FROM {DC_CNF_CONNECTOR} "
                    f"WHERE GATEWAYID = '{info.ManagerId}')",
                    auto_commit=False):
                return False
            if not self.ExecuteQuery(
                    f"DELETE FROM {DC_CNF_CONNECTOR} "
                    f"WHERE GATEWAYID = '{info.ManagerId}'",
                    auto_commit=False):
                self.RollBack(); return False
            if not self.ExecuteQuery(
                    f"DELETE FROM {DC_CNF_MANAGER} WHERE ID = '{info.ManagerId}'",
                    auto_commit=False):
                self.RollBack()
                logger.error("Manager Delete(%s) Error", info.ManagerId)
                return False
            self.Commit()
            return True

        return False

    # ── Connector ─────────────────────────────────────────────────────────────
    def _recv_connector(self, info: AS_CONNECTOR_INFO_T) -> bool:
        if self._session is None:
            logger.error("DB Connection Fail !!")
            self.GetDBInstance()
            return False

        if info.RequestStatus == CREATE_DATA:
            return self.ExecuteQuery(
                f"INSERT INTO {DC_CNF_CONNECTOR} "
                f"(ID, GATEWAYID, RULEID, STATUS, JUNCTIONTYPE, CMDRESPONSETYPE, LOGCYCLE, "
                f"CREATE_DATE, MODIFY_DATE, LAST_ACTION_DATE, LAST_ACTION) "
                f"VALUES ('{info.ConnectorId}', '{info.ManagerId}', '{info.RuleId}', "
                f"{info.SettingStatus}, {info.JunctionType}, {info.CmdResponseType}, "
                f"{info.LogCycle}, NOW(), NOW(), NOW(), "
                f"'{AsUtil.GetEnumTypeString(ACT_CREATE)}')"
            )

        if info.RequestStatus == UPDATE_DATA:
            return self.ExecuteQuery(
                f"UPDATE {DC_CNF_CONNECTOR} "
                f"SET GATEWAYID = '{info.ManagerId}', RULEID = '{info.RuleId}', "
                f"STATUS = {info.SettingStatus}, "
                f"CMDRESPONSETYPE = {info.CmdResponseType}, "
                f"LOGCYCLE = {info.LogCycle}, "
                f"MODIFY_DATE = NOW(), LAST_ACTION_DATE = NOW(), "
                f"LAST_ACTION = '{AsUtil.GetEnumTypeString(ACT_MODIFY)}', "
                f"DESCRIPTION = '{info.Desc}', "
                f"LAST_ACTION_DESC = '{info.LastActionDesc}' "
                f"WHERE ID = '{info.ConnectorId}'"
            )

        if info.RequestStatus == DELETE_DATA:
            if not self.ExecuteQuery(
                    f"DELETE FROM {DC_CNF_CONNECTION} "
                    f"WHERE CONNECTORID = '{info.ConnectorId}'",
                    auto_commit=False):
                logger.error("Connection Delete(%s) Error", info.ConnectorId)
                return False
            if not self.ExecuteQuery(
                    f"DELETE FROM {DC_CNF_CONNECTOR} WHERE ID = '{info.ConnectorId}'",
                    auto_commit=False):
                self.RollBack()
                logger.error("Connector Delete(%s) Error", info.ConnectorId)
                return False
            self.Commit()

            # 이력 테이블 삽입
            try:
                from ProcNaServer.AsciiServerWorld import MAINPTR
                con_info = MAINPTR().GetConnectorInfo(info.ConnectorId)
            except Exception:
                con_info = None

            if con_info:
                return self.ExecuteQuery(
                    f"INSERT INTO {DC_CNF_CONNECTOR_DELETED} "
                    f"(ID, GATEWAYID, RULEID, DESCRIPTION, "
                    f"CREATE_DATE, MODIFY_DATE, DELETE_DATE) "
                    f"VALUES ('{con_info.m_ConnectorInfo.ConnectorId}', "
                    f"'{con_info.m_ConnectorInfo.ManagerId}', "
                    f"'{con_info.m_ConnectorInfo.RuleId}', '{info.Desc}', "
                    f"'{con_info.m_ConnectorInfo.CreateDate}', "
                    f"'{con_info.m_ConnectorInfo.ModifyDate}', NOW())"
                )
            else:
                logger.error("## ERROR Insert %s, Can't find connector info : %s",
                             DC_CNF_CONNECTOR_DELETED, info.ConnectorId)
            return True

        return False

    # ── Connection ────────────────────────────────────────────────────────────
    def _recv_connection(self, info: AS_CONNECTION_INFO_T) -> bool:
        if info.RequestStatus == CREATE_DATA:
            param = self._execute_select(
                f"SELECT MAX(SEQUENCE) FROM {DC_CNF_CONNECTION}")
            if param is None:
                return False
            param.next()
            max_seq = param.get_value_int(0) + 1
            info.Sequence = max_seq

            pw = info.UserPassword
            return self.ExecuteQuery(
                f"INSERT INTO {DC_CNF_CONNECTION} "
                f"(SEQUENCE, CONNECTORID, AGENTEQUIPID, PROTOCOLTYPE, PORTTYPE, "
                f"AGENTPORTNO, USERID, PASSWORD, GATFLAG, STATUS, COMMANDFLAG) "
                f"VALUES ({info.Sequence}, '{info.ConnectorId}', '{info.AgentEquipId}', "
                f"{info.ProtocolType}, {info.PortType}, {info.PortNo}, "
                f"'{info.UserId}', IF('{pw}'='','','{pw}'), "
                f"{info.GatFlag}, {info.SettingStatus}, {info.CommandPortFlag})"
            )

        if info.RequestStatus == UPDATE_DATA:
            return self.ExecuteQuery(
                f"UPDATE {DC_CNF_CONNECTION} "
                f"SET CONNECTORID = '{info.ConnectorId}', "
                f"AGENTEQUIPID = '{info.AgentEquipId}', "
                f"PROTOCOLTYPE = {info.ProtocolType}, PORTTYPE = {info.PortType}, "
                f"AGENTPORTNO = {info.PortNo}, USERID = '{info.UserId}', "
                f"PASSWORD = '{info.UserPassword}', GATFLAG = {info.GatFlag}, "
                f"STATUS = {info.SettingStatus}, "
                f"COMMANDFLAG = {info.CommandPortFlag} "
                f"WHERE SEQUENCE = {info.Sequence}"
            )

        if info.RequestStatus == DELETE_DATA:
            return self.ExecuteQuery(
                f"DELETE FROM {DC_CNF_CONNECTION} WHERE SEQUENCE = {info.Sequence}")

        return False

    # ── DataHandler ───────────────────────────────────────────────────────────
    def _recv_data_handler(self, info: AS_DATA_HANDLER_INFO_T) -> bool:
        target_info = self.GetIpInfoToString(info.TargetIpInfoList)

        if info.RequestStatus == CREATE_DATA:
            return self.ExecuteQuery(
                f"INSERT INTO {DC_EVENT_CONSUMER} "
                f"(ID, DBUSERID, DBPASSWORD, DBTNS, HOSTNAME, TIMEMODE, LISTENPORT, "
                f"STATUS, LOGMODE, IPADDRESS, BYPASSLISTENPORT, LOADINGINTERVAL, "
                f"HANDLERMODE, TARGETINFO, RUNMODE, LOGCYCLE, SSHID, SSHPW, MODIFY_DATE) "
                f"VALUES ('{info.DataHandlerId}', '{info.DbUserId}', '{info.DbPassword}', "
                f"'{info.DbName}', '{info.HostName}', {info.TimeMode}, {info.ListenPort}, "
                f"{info.SettingStatus}, {info.LogMode}, '{info.IpAddress}', "
                f"{info.BypassListenPort}, {info.LoadingInterval}, {info.OperMode}, "
                f"'{target_info}', {info.RunMode}, {info.LogCycle}, "
                f"'{info.SshID}', '{info.SshPass}', NOW())"
            )

        if info.RequestStatus == UPDATE_DATA:
            return self.ExecuteQuery(
                f"UPDATE {DC_EVENT_CONSUMER} "
                f"SET ID = '{info.DataHandlerId}', DBUSERID = '{info.DbUserId}', "
                f"DBPASSWORD = '{info.DbPassword}', DBTNS = '{info.DbName}', "
                f"HOSTNAME = '{info.HostName}', TIMEMODE = {info.TimeMode}, "
                f"LISTENPORT = {info.ListenPort}, STATUS = {info.SettingStatus}, "
                f"LOGMODE = {info.LogMode}, IPADDRESS = '{info.IpAddress}', "
                f"BYPASSLISTENPORT = {info.BypassListenPort}, "
                f"LOADINGINTERVAL = {info.LoadingInterval}, "
                f"HANDLERMODE = {info.OperMode}, TARGETINFO = '{target_info}', "
                f"RUNMODE = {info.RunMode}, LOGCYCLE = {info.LogCycle}, "
                f"SSHID = '{info.SshID}', SSHPW = '{info.SshPass}', "
                f"MODIFY_DATE = NOW() "
                f"WHERE ID = '{info.OldDataHandlerId}'"
            )

        if info.RequestStatus == DELETE_DATA:
            return self.ExecuteQuery(
                f"DELETE FROM {DC_EVENT_CONSUMER} WHERE ID = '{info.DataHandlerId}'"
            )

        return False

    # ── SubProc ───────────────────────────────────────────────────────────────
    def _recv_sub_proc(self, info: AS_SUB_PROC_INFO_T) -> bool:
        if info.RequestStatus == CREATE_DATA:
            return self.ExecuteQuery(
                f"INSERT INTO {DC_CNF_SUB_PROC} "
                f"(ID, ID_STR, PARENT, PARENTID, IPADDRESS, HOSTNAME, "
                f"STATUS, LOGCYCLE, DESCRIPTION, BIN_NAME, ARGS) "
                f"VALUES (0, '{info.ProcIdStr}', {info.ParentProc}, '{info.ParentId}', "
                f"'{info.IpAddress}', '{info.HostName}', "
                f"{info.SettingStatus}, {info.LogCycle}, '{info.Description}', "
                f"'{info.BinaryName}', '{info.Args}')"
            )

        if info.RequestStatus == UPDATE_DATA:
            return self.ExecuteQuery(
                f"UPDATE {DC_CNF_SUB_PROC} "
                f"SET ID_STR = '{info.ProcIdStr}', PARENT = {info.ParentProc}, "
                f"PARENTID = '{info.ParentId}', IPADDRESS = '{info.IpAddress}', "
                f"HOSTNAME = '{info.HostName}', STATUS = {info.SettingStatus}, "
                f"LOGCYCLE = {info.LogCycle}, DESCRIPTION = '{info.Description}', "
                f"BIN_NAME = '{info.BinaryName}', ARGS = '{info.Args}' "
                f"WHERE ID_STR = '{info.OldProcIdStr}'"
            )

        if info.RequestStatus == DELETE_DATA:
            return self.ExecuteQuery(
                f"DELETE FROM {DC_CNF_SUB_PROC} WHERE ID_STR = '{info.ProcIdStr}'"
            )

        return False

    # ── CommandAuthority ──────────────────────────────────────────────────────
    def _recv_command_authority(self, info: AS_COMMAND_AUTHORITY_INFO_T) -> bool:
        if info.RequestStatus == CREATE_DATA:
            return self.ExecuteQuery(
                f"INSERT INTO {DC_CMD_SESSION_IDENT} "
                f"(ID, MAXCMDQUEUE, PRIORITY, LOGMODE, ACKMODE, "
                f"DESCRIPTION, MAX_SESSION_CNT) "
                f"VALUES ('{info.Id}', {info.MaxCmdQueue}, {info.Priority}, "
                f"{info.LogMode}, {info.AckMode}, '{info.Description}', "
                f"{info.MaxSessionCnt})"
            )

        if info.RequestStatus == UPDATE_DATA:
            return self.ExecuteQuery(
                f"UPDATE {DC_CMD_SESSION_IDENT} "
                f"SET ID = '{info.Id}', MAXCMDQUEUE = {info.MaxCmdQueue}, "
                f"PRIORITY = {info.Priority}, DESCRIPTION = '{info.Description}', "
                f"LOGMODE = {info.LogMode}, ACKMODE = {info.AckMode}, "
                f"MAX_SESSION_CNT = {info.MaxSessionCnt} "
                f"WHERE ID = '{info.OldId}'"
            )

        if info.RequestStatus == DELETE_DATA:
            return self.ExecuteQuery(
                f"DELETE FROM {DC_CMD_SESSION_IDENT} WHERE ID = '{info.Id}'"
            )

        return False

    # ── RuleChange ────────────────────────────────────────────────────────────
    def _recv_rule_change(self, info: AS_RULE_CHANGE_INFO_T) -> bool:
        return self.ExecuteQuery(
            f"UPDATE {DC_CNF_CONNECTOR} SET RULEID = '{info.RuleId}' "
            f"WHERE GATEWAYID = '{info.ManagerId}' AND ID = '{info.ProcessId}'"
        )

    # ── ConnectorDescChange ───────────────────────────────────────────────────
    def _recv_connector_desc_change(self,
                                     info: AS_CONNECTOR_DESC_CHANGE_INFO_T) -> bool:
        return self.ExecuteQuery(
            f"UPDATE {DC_CNF_CONNECTOR} SET DESCRIPTION = '{info.Description}' "
            f"WHERE GATEWAYID = '{info.ManagerId}' AND ID = '{info.ConnectorId}'"
        )

    # =========================================================================
    # MMC 결과 저장
    # =========================================================================

    def InsertMMCResult(self, result: MMCResultStored) -> bool:
        """C++: InsertMMCResult(MMCResultStored* Result)"""
        result.ResultMsg = result.ResultMsg.replace("'", "''")
        result_mode_str  = AsUtil.GetEnumTypeString(result.ResultMode)

        query = (
            f"INSERT INTO {DC_MMC_RESULT} "
            f"(EQUIPID, GID, EXTID, RESULTMODE, USERID, IPADDRESS, "
            f"ISSUEDDATE, RESULTSTARTTIME, RESULTENDTIME, COMMAND) "
            f"VALUES "
            f"('{result.MmcInfo.ne}', {result.Gid}, {result.ExtId}, "
            f"'{result_mode_str}', '{result.MmcInfo.userid}', "
            f"'{result.MmcInfo.display}', "
            f"STR_TO_DATE('{result.IssuedTimeStr}', '%Y/%m/%d %H:%i:%s'), "
            f"STR_TO_DATE('{result.ResultStartTime}', '%Y/%m/%d %H:%i:%s'), "
            f"STR_TO_DATE('{result.ResultEndTime}', '%Y/%m/%d %H:%i:%s'), "
            f"'{result.MmcInfo.mmc}')"
        )
        if not self.ExecuteQuery(query, auto_commit=False):
            return False

        # RESULTMSG BLOB 컬럼 별도 업데이트 (C++: UpdateLong)
        where = (
            f"GID = {result.Gid} AND "
            f"ISSUEDDATE = STR_TO_DATE('{result.IssuedTimeStr}', '%Y/%m/%d %H:%i:%s')"
        )
        if not self._session.update_long(
                DC_MMC_RESULT, "RESULTMSG", result.ResultMsg, where):
            logger.error("Fail to query [%s]", self.GetErrorMsg())
            self.RollBack()
            return False

        self.Commit()
        return True

    # =========================================================================
    # IP 정보 변환 유틸 (static)
    # =========================================================================

    @staticmethod
    def GetStringToIpInfo(target_info: str,
                           info_list: AS_TARGET_IP_INFO_LIST_T) -> bool:
        """
        C++: GetStringToIpInfo(string TargetInfo, AS_TARGET_IP_INFO_LIST_T&)
        "IP:PORT|IP:PORT|" → AS_TARGET_IP_INFO_LIST_T
        """
        if "|" not in target_info:
            return False

        info_list.Size = 0
        for part in target_info.split("|"):
            part = part.strip()
            if not part or ":" not in part:
                if part:
                    logger.error("Invalid ipinfo format : %s", part)
                continue
            ip, _, port_str = part.partition(":")
            port = int(port_str) if port_str.isdigit() else 0
            if port == 0:
                logger.error("Invalid port : %s", port_str)
                continue
            entry = AS_TARGET_IP_INFO_T()
            entry.IpAddress = ip
            entry.PortNo    = port
            if info_list.Size < len(info_list.TargetIpInfo):
                info_list.TargetIpInfo[info_list.Size] = entry
            else:
                info_list.TargetIpInfo.append(entry)
            info_list.Size += 1

        return True

    @staticmethod
    def GetIpInfoToString(info_list: AS_TARGET_IP_INFO_LIST_T) -> str:
        """
        C++: GetIpInfoToString(AS_TARGET_IP_INFO_LIST_T&)
        AS_TARGET_IP_INFO_LIST_T → "IP:PORT|IP:PORT|"
        """
        return "".join(
            f"{info_list.TargetIpInfo[i].IpAddress}:"
            f"{info_list.TargetIpInfo[i].PortNo}|"
            for i in range(info_list.Size)
        )