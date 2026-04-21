"""
ManagerConnMgr.py
C++ ManagerConnMgr.h/.C → Python 변환

Manager(ProcNaManager) 연결 관리자.
  - DB에서 Manager 정보 로드 (Init)
  - SSH로 Manager 프로세스 원격 기동 (ExecuteManager / RunCommand)
  - Manager 기동 타임아웃 감시 (ReceiveTimeOut / AsWorld.SetTimer)
  - MMC 명령 전송, 포트/프로세스 상태 수신
  - Connector/Connection InfoChange CRUD
"""

import copy
import logging
import threading
from datetime import datetime
from typing import Optional, Dict

import paramiko                                         # C++: frSshUtil

from Common.ConnectionMgr import ConnectionMgr          # add/remove/find_session (소문자)
from Common.CommTypeList import (
    AS_MANAGER_INFO_T, AS_CONNECTOR_INFO_T, AS_CONNECTION_INFO_T,
    AS_PROC_CONTROL_T, AS_PROCESS_STATUS_T, AS_PORT_STATUS_INFO_T,
    AS_MMC_PUBLISH_T, AS_SESSION_CONTROL_T, AS_RULE_CHANGE_INFO_T,
    AS_CONNECTOR_DESC_CHANGE_INFO_T, AS_DATA_HANDLER_INFO_T,
    AS_ROUTER_INFO_REQ_T, AS_DATA_ROUTING_INIT_T, AS_LOG_STATUS_T,
)
from Common.CommType import (
    ASCII_MANAGER, ASCII_CONNECTOR,
    START, STOP, WAIT_NO, WAIT_START, WAIT_STOP, UNDEFINED,
    CREATE_DATA, UPDATE_DATA, DELETE_DATA,
    ACT_START, ACT_STOP,
    ARG_NAME, ARG_SVR_IP, ARG_SVR_PORT,
    ARG_LOG_HOUR, ARG_LOG_DAY,
    PROC_CONTROL, SESSION_CONTROL,
    AS_DATA_HANDLER_INFO, AS_DATA_ROUTING_INIT,
    CMD_PARSING_RULE_DOWN, CMD_MAPPING_RULE_DOWN,
)
from Common.AsUtil import AsUtil

from ProcNaServer.AsciiServerType import (
    ManagerInfo, ManagerInfoMap,
    ConnectorInfo, ConnectorInfoMap,
    ConnectionInfoList,
    RouterInfoList,
    WAIT_MANAGER_START_TIME, WAIT_MANAGER_START_TIMEOUT,
)

logger = logging.getLogger(__name__)


class ManagerConnMgr(ConnectionMgr):
    """
    C++ ManagerConnMgr (ConnectionMgr 상속) 대응.

    타이머:
      AsWorld.SetTimer / CancelTimer (asyncio.Task 기반) 사용.
      _timer_key_map : ManagerId(str) → timer_key(int)

    뮤텍스:
      C++ pthread_mutex_t m_SocketRemoveLock
      → ConnectionMgr._socket_remove_lock() / _socket_remove_unlock() 오버라이드
    """

    def __init__(self) -> None:
        super().__init__()
        self._manager_info_map: ManagerInfoMap  = {}
        self._timer_key_map:    Dict[str, int]  = {}
        self._remove_lock = threading.Lock()    # C++: pthread_mutex_t

    # =========================================================================
    # ConnectionMgr 뮤텍스 오버라이드
    # =========================================================================

    def _socket_remove_lock(self) -> None:
        """C++: SocketRemoveLock() → pthread_mutex_lock"""
        self._remove_lock.acquire()

    def _socket_remove_unlock(self) -> None:
        """C++: SocketRemoveUnLock() → pthread_mutex_unlock"""
        self._remove_lock.release()

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """C++: AcceptSocket()"""
        from ProcNaServer.ManagerConnection import ManagerConnection

        conn = ManagerConnection(self)
        if not self.Accept(conn):
            logger.debug("Manager Socket Accept Error : %s", self.GetObjErrMsg())
            return

        self.add(conn)                          # ConnectionMgr.add()
        conn.SetReReadCheck(True)               # AsSocket.SetReReadCheck()
        logger.debug("Manager Connection")

    # =========================================================================
    # Init
    # =========================================================================

    def Init(self) -> bool:
        """C++: Init() — DB에서 Manager/Connector/Connection 정보 로드."""
        from ProcNaServer.AsciiServerWorld import DBPTR

        self._manager_info_map.clear()
        if not DBPTR().GetManagerInfo(self._manager_info_map):
            logger.error("Get Manager Info Error : %s", DBPTR().GetErrorMsg())
            return False
        logger.debug("m_ManagerInfoMap size : %d", len(self._manager_info_map))
        return True

    # =========================================================================
    # ExecuteManager
    # =========================================================================

    def ExecuteManager(self, info: Optional[ManagerInfo] = None,
                       wait_time: int = WAIT_MANAGER_START_TIME) -> bool:
        """
        C++ 오버로드 2종 통합:
          ExecuteManager()              → 전체 Manager 기동
          ExecuteManager(ManagerInfo*)  → 단일 Manager 기동
        """
        if info is None:
            return self._execute_all()
        return self._execute_one(info, wait_time)

    def _execute_all(self) -> bool:
        """C++: ExecuteManager() — 전체 순회 기동."""
        if not self.Init():
            return False

        wait_offset = 30
        logger.debug("Manager Count : %d", len(self._manager_info_map))
        for mgr_id, info in self._manager_info_map.items():
            if info.m_ManagerInfo.SettingStatus == START:
                self._execute_one(info, WAIT_MANAGER_START_TIME + wait_offset)
                wait_offset += 2
        return True

    def _execute_one(self, info: ManagerInfo,
                     wait_time: int = WAIT_MANAGER_START_TIME) -> bool:
        """C++: ExecuteManager(ManagerInfo*, int) — 단일 기동 (SSH)."""
        from ProcNaServer.AsciiServerWorld import MAINPTR, DBPTR
        from Common.AsWorld import AsWorld

        mgr = info.m_ManagerInfo

        if mgr.RequestStatus != WAIT_NO:
            req_str = "Start" if mgr.RequestStatus == WAIT_START else "Stop"
            logger.info("Already Request Manager: %s(%s)", mgr.ManagerId, req_str)
            MAINPTR().SendAsciiError(
                1, "Already Request Manager: %s(%s)", mgr.ManagerId, req_str)
            return False

        logger.debug("ManagerId : %s, IP : %s", mgr.ManagerId, mgr.IP)

        # Ping 확인
        if not MAINPTR().PingCheck(mgr.IP):
            logger.info("Ping - No Answer from MANAGER(%s)", mgr.ManagerId)
            MAINPTR().SendAsciiError(
                1, "Ping - No Answer from MANAGER(%s)", mgr.ManagerId)
            return False

        # SSH ID/PW 없으면 DB에서 조회
        if not mgr.SshID:
            logger.debug("Manager IP,ID,PW Get")
            if not DBPTR().GetManagerInfoFindId(info):
                logger.error("Get Manager Info Error : %s", DBPTR().GetErrorMsg())
                return False
            if not mgr.SshID or not mgr.SshPass:
                logger.error("Can't Find SSHID, SshPass: %s", mgr.ManagerId)
                return False

        # 기존 프로세스 Kill
        self.KillManager(mgr.ManagerId)

        # 실행 명령 조립
        exec_cmd = (
            f"~{MAINPTR().GetUserName()}{AsWorld.GetStartDir()}/Bin/"
            f"{MAINPTR().GetProcessName(ASCII_MANAGER)} "
            f"{ARG_NAME} {mgr.ManagerId} "
            f"{ARG_SVR_IP} {MAINPTR().GetServerIp()} "
            f"{ARG_SVR_PORT} {MAINPTR().GetListenPort(ASCII_MANAGER)} &"
        )
        logger.debug("Manager Execute : %s", exec_cmd)
        logger.debug("Manager ID=%s, PW=%s", mgr.SshID, mgr.SshPass)

        self.RunCommand(mgr.SshID, mgr.SshPass, mgr.IP, exec_cmd)

        mgr.RequestStatus = WAIT_START

        # 기동 대기 타이머 (AsWorld.SetTimer)
        old_key = self._timer_key_map.pop(mgr.ManagerId, None)
        if old_key is not None:
            self.CancelTimer(old_key)           # AsWorld.CancelTimer

        key = self.SetTimer(                    # AsWorld.SetTimer → asyncio.Task
            wait_time,
            WAIT_MANAGER_START_TIMEOUT,
            mgr.ManagerId,                      # C++ void* → str
        )
        self._timer_key_map[mgr.ManagerId] = key
        MAINPTR().SendInfoChange(mgr)
        return True

    # =========================================================================
    # RunCommand (SSH)
    # =========================================================================

    def RunCommand(self, ssh_id: str, ssh_pass: str,
                   ip: str, command: str) -> bool:
        """
        C++: RunCommand(char* SshID, char* SshPass, char* IP, char* Command)
        frSshUtil → paramiko.SSHClient
        """
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, port=22, username=ssh_id, password=ssh_pass, timeout=10)
            client.exec_command(command)
            client.close()
            logger.info("SSH Connect !!!!!! [%s@%s] %s", ssh_id, ip, command)
            return True
        except Exception as e:
            logger.info("SSH Connect Fail!!!!!! : %s", e)
            return False

    # =========================================================================
    # StopManager
    # =========================================================================

    def StopManager(self, info: ManagerInfo) -> bool:
        """C++: StopManager(ManagerInfo*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR
        from ProcNaServer.ManagerConnection import ManagerConnection

        con: Optional[ManagerConnection] = self.find_session(  # ConnectionMgr.find_session()
            info.m_ManagerInfo.ManagerId)
        if con is None:
            logger.debug("The Manager(%s) executed is not found.",
                         info.m_ManagerInfo.ManagerId)
            MAINPTR().SendAsciiError(
                1, "The Manager(%s) executed is not found.",
                info.m_ManagerInfo.ManagerId)
            return False

        info.m_ManagerInfo.RequestStatus = WAIT_STOP
        MAINPTR().SendInfoChange(info.m_ManagerInfo)
        con.StopManager()
        return True

    # =========================================================================
    # KillManager
    # =========================================================================

    def KillManager(self, manager_id: str) -> None:
        """C++: KillManager(string ManagerId) — KillProcess.sh SSH 실행."""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        info = self.FindManagerInfo(manager_id)
        if info is None:
            logger.error("Can't Find Manager : %s", manager_id)
            return

        cmd = f"{MAINPTR().GetScriptDir()}/KillProcess.sh"
        logger.debug("Kill Manager : %s", cmd)
        self.RunCommand(
            info.m_ManagerInfo.SshID,
            info.m_ManagerInfo.SshPass,
            info.m_ManagerInfo.IP,
            cmd,
        )

    # =========================================================================
    # ReceiveTimeOut (AsWorld 가상함수 오버라이드)
    # =========================================================================

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """
        C++: ReceiveTimeOut(int Reason, void* ExtraReason)
        WAIT_MANAGER_START_TIMEOUT: Manager 기동 타임아웃 처리.
        extra_reason = manager_id (str)
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR, DBPTR

        if reason == WAIT_MANAGER_START_TIMEOUT:
            mgr_id: str = extra_reason if isinstance(extra_reason, str) else ""
            logger.debug("Recv Timeout WAIT_MANAGER_START_TIMEOUT : %s", mgr_id)
            MAINPTR().SendAsciiError(1, "Manager(%s) Start Error", mgr_id)

            self._timer_key_map.pop(mgr_id, None)

            info = self.FindManagerInfo(mgr_id)
            if info is None:
                logger.error("Manager Info Can't Find : %s", mgr_id)
                return

            if not DBPTR().UpdateManagerStatus(mgr_id, STOP,
                                                "Error during trying start."):
                logger.error("Update Manager Status Error : %s",
                             DBPTR().GetErrorMsg())
                return

            logger.debug("Manager(%s) is setting STOP", mgr_id)
            info.m_ManagerInfo.SettingStatus  = STOP
            info.m_ManagerInfo.CurStatus      = STOP
            info.m_ManagerInfo.RequestStatus  = WAIT_NO
            MAINPTR().SendInfoChange(info.m_ManagerInfo)

    # =========================================================================
    # ManagerSessionIdentify
    # =========================================================================

    def ManagerSessionIdentify(self, manager_id: str) -> None:
        """C++: ManagerSessionIdentify — Manager 세션 식별 완료 → 타이머 취소."""
        key = self._timer_key_map.pop(manager_id, None)
        if key is None:
            logger.error("Can't Find Manager(%s) in ManagerExecuteTimerMap",
                         manager_id)
            return
        self.CancelTimer(key)                   # AsWorld.CancelTimer

    # =========================================================================
    # RecvProcessControl
    # =========================================================================

    def RecvProcessControl(self, proc_ctl: AS_PROC_CONTROL_T) -> bool:
        """C++: RecvProcessControl(AS_PROC_CONTROL_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR, DBPTR
        from ProcNaServer.ManagerConnection import ManagerConnection

        mgr_info = self.FindManagerInfo(proc_ctl.ManagerId)
        if mgr_info is None:
            logger.error("Can't Find Manager : %s", proc_ctl.ManagerId)
            MAINPTR().SendAsciiError(
                1, "Can't Find Manager : %s", proc_ctl.ManagerId)
            return False

        # ── ASCII_MANAGER ──────────────────────────────────────────────────
        if proc_ctl.ProcessType == ASCII_MANAGER:
            mgr = mgr_info.m_ManagerInfo
            if mgr.RequestStatus != WAIT_NO:
                req_str = "Start" if mgr.RequestStatus == WAIT_START else "Stop"
                logger.info("Already Request Process: %s(%s)",
                            proc_ctl.ManagerId, req_str)
                MAINPTR().SendAsciiError(
                    1, "Already Request Process: %s(%s)",
                    proc_ctl.ManagerId, req_str)
                return False

            if proc_ctl.Status == START and mgr.SettingStatus == START:
                logger.info("Already Started Manager : %s", proc_ctl.ManagerId)
                MAINPTR().SendAsciiError(
                    1, "Already Started Manager : %s", proc_ctl.ManagerId)
                return False
            if proc_ctl.Status == STOP and mgr.SettingStatus == STOP:
                logger.info("Already Stop Manager : %s", proc_ctl.ManagerId)
                MAINPTR().SendAsciiError(
                    1, "Already Stop Manager : %s", proc_ctl.ManagerId)
                return False

            if not MAINPTR().PingCheck(mgr.IP):
                logger.info("Ping - No Answer from MANAGER(%s)", mgr.ManagerId)
                MAINPTR().SendAsciiError(
                    1, "Ping - No Answer from MANAGER(%s)", mgr.ManagerId)
                if proc_ctl.Status == START:
                    return False

            if not DBPTR().UpdateManagerStatus(
                    proc_ctl.ManagerId, proc_ctl.Status, proc_ctl.Desc):
                logger.error("Update Manager Status Error : %s",
                             DBPTR().GetErrorMsg())
                return False

            mgr.SettingStatus = START if proc_ctl.Status == START else STOP

            if proc_ctl.Status == START:
                if self._execute_one(mgr_info):
                    MAINPTR().SendAsciiError(
                        1, "The MANAGER(%s) start trying.", proc_ctl.ManagerId)
                    return True
                return False
            elif proc_ctl.Status == STOP:
                self.StopManager(mgr_info)
                return True
            return False

        # ── ASCII_CONNECTOR ────────────────────────────────────────────────
        elif proc_ctl.ProcessType == ASCII_CONNECTOR:
            mgr = mgr_info.m_ManagerInfo
            if mgr.RequestStatus == WAIT_START:
                logger.info("The Manager(%s) is trying execute.", proc_ctl.ManagerId)
                MAINPTR().SendAsciiError(
                    1, "The Manager(%s) is trying execute.", proc_ctl.ManagerId)
                return False
            if mgr.CurStatus == STOP:
                logger.info("The Manager(%s) is not execute.", proc_ctl.ManagerId)
                MAINPTR().SendAsciiError(
                    1, "The Manager(%s) is not execute.", proc_ctl.ManagerId)
                return False

            con_info = self.FindConnectorInfo(proc_ctl.ManagerId, proc_ctl.ProcessId)
            if con_info is None:
                logger.error("The Connector(%s) Can't Find", proc_ctl.ProcessId)
                MAINPTR().SendAsciiError(
                    1, "The Connector(%s) Can't Find", proc_ctl.ProcessId)
                return False

            if con_info.m_ConnectorInfo.RequestStatus != WAIT_NO:
                req_str = ("Start" if con_info.m_ConnectorInfo.RequestStatus == WAIT_START
                           else "Stop")
                logger.info("Already Request Process: %s(%s)",
                            proc_ctl.ProcessId, req_str)
                MAINPTR().SendAsciiError(
                    1, "Already Request Process: %s(%s)",
                    proc_ctl.ProcessId, req_str)
                return False

            con: Optional[ManagerConnection] = self.find_session(proc_ctl.ManagerId)
            if con is None:
                logger.error("The Manager Session(%s) is not found.", proc_ctl.ManagerId)
                MAINPTR().SendAsciiError(
                    1, "The Manager Session(%s) is not found.", proc_ctl.ManagerId)
                return False

            if proc_ctl.Status == START and con_info.m_ConnectorInfo.SettingStatus == START:
                logger.info("Already Started Connector : %s", proc_ctl.ProcessId)
                MAINPTR().SendAsciiError(
                    1, "Already Started Connector : %s", proc_ctl.ProcessId)
                return False
            if proc_ctl.Status == STOP and con_info.m_ConnectorInfo.SettingStatus == STOP:
                logger.info("Already Stop Connector : %s", proc_ctl.ProcessId)
                MAINPTR().SendAsciiError(
                    1, "Already Stop Connector : %s", proc_ctl.ProcessId)
                return False

            now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            if not DBPTR().UpdateConnectorStatus(proc_ctl, now_str):
                logger.error("Update Connector Status Error : %s",
                             DBPTR().GetErrorMsg())
                return False

            ci = con_info.m_ConnectorInfo
            ci.SettingStatus  = START if proc_ctl.Status == START else STOP
            ci.RequestStatus  = WAIT_START if proc_ctl.Status == START else WAIT_STOP
            ci.LastActionDate = now_str
            ci.LastActionDesc = proc_ctl.Desc
            ci.LastActionType = AsUtil.GetEnumTypeString(
                ACT_START if proc_ctl.Status == START else ACT_STOP)

            proc_ctl.RuleId          = ci.RuleId
            proc_ctl.MmcIdentType    = ci.MmcIdentType
            proc_ctl.CmdResponseType = ci.CmdResponseType
            proc_ctl.JunctionType    = ci.JunctionType
            proc_ctl.LogCycle        = ci.LogCycle

            MAINPTR().SendInfoChange(ci)
            import asyncio, struct
            # SendPacket은 async이므로 이벤트 루프에 예약
            asyncio.ensure_future(con.SendPacket(
                PROC_CONTROL,
                _pack_proc_control(proc_ctl),
                _sizeof_proc_control(),
            ))
            logger.debug("Send ProcControl Success...")
            return True

        return False

    # =========================================================================
    # ReceiveProcInfo
    # =========================================================================

    def ReceiveProcInfo(self, proc_info: AS_PROCESS_STATUS_T) -> None:
        """C++: ReceiveProcInfo(AS_PROCESS_STATUS_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        if proc_info.ProcessType == ASCII_MANAGER:
            info = self.FindManagerInfo(proc_info.ManagerId)
            if info:
                info.m_ManagerInfo.CurStatus     = proc_info.Status
                info.m_ManagerInfo.RequestStatus = WAIT_NO
            else:
                logger.error("Can't Find Manager : %s", proc_info.ManagerId)

        elif proc_info.ProcessType == ASCII_CONNECTOR:
            # prefix 제거: "CONNECTOR_xxx" → "xxx"
            process_id = proc_info.ProcessId
            pos = process_id.find("_")
            if pos != -1:
                process_id = process_id[pos + 1:]

            con_info = self.FindConnectorInfo(proc_info.ManagerId, process_id)
            if con_info:
                con_info.m_ConnectorInfo.CurStatus     = proc_info.Status
                con_info.m_ConnectorInfo.RequestStatus = WAIT_NO

                if con_info.m_ConnectorInfo.CurStatus == STOP:
                    for conn in con_info.m_ConnectionInfoList:
                        conn.RequestStatus = WAIT_NO
                        conn.CurStatus     = UNDEFINED

                MAINPTR().SendInfoChange(con_info.m_ConnectorInfo)
            else:
                logger.error("Can't Find Connector : %s:%s",
                             proc_info.ManagerId, process_id)

        MAINPTR().UpdateProcessInfo(proc_info)

    # =========================================================================
    # ReceivePortInfo
    # =========================================================================

    def ReceivePortInfo(self, port_status: AS_PORT_STATUS_INFO_T) -> None:
        """C++: ReceivePortInfo(AS_PORT_STATUS_INFO_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR, DBPTR

        info = self.FindConnectionInfo(
            port_status.ManagerId, port_status.ConnectorId, port_status.Sequence)
        if info is None:
            logger.error("Can't Find Connection : %s:%s:%d",
                         port_status.ManagerId, port_status.ConnectorId,
                         port_status.Sequence)
            return

        info.CurStatus     = port_status.Status
        info.RequestStatus = WAIT_NO
        MAINPTR().SendInfoChange(info)
        DBPTR().UpdateConnectionStatus_by_type(
            -1, "", port_status.Sequence, port_status)

    # =========================================================================
    # SendMMCCommand
    # =========================================================================

    def SendMMCCommand(self, mmc_com: AS_MMC_PUBLISH_T,
                       err_str: list) -> bool:
        """
        C++: SendMMCCommand(AS_MMC_PUBLISH_T*, char* ErrStr)
        err_str: [str] 1-원소 리스트 (출력 인자 대응).
        """
        import asyncio
        from ProcNaServer.ManagerConnection import ManagerConnection

        if not mmc_com.mmc:
            err_str[0] = (f"{mmc_com.ne} : Command is empty, "
                          f"therefore can't execute command")
            logger.debug(err_str[0])
            return False

        for sock in self._socket_connection_list:
            mgr_con: ManagerConnection = sock
            if mgr_con.IsHasCmdPortNeName(mmc_com.ne):
                self._socket_remove_lock()
                if self.is_valid_connection(mgr_con):   # ConnectionMgr.is_valid_connection()
                    asyncio.ensure_future(mgr_con.SendMMCCommand(mmc_com))
                else:
                    logger.debug("invalid Mgr Connection : %s",
                                 mgr_con.GetSessionName())
                    self._socket_remove_unlock()
                    break
                self._socket_remove_unlock()
                return True

        err_str[0] = (" The Command (8286)port on NMS connected to the "
                      "Network Element does not exist or has been shut down.")
        logger.debug(err_str[0])
        return False

    # =========================================================================
    # SendCmdParsingRuleDown / SendCmdMappingRuleDown
    # =========================================================================

    def SendCmdParsingRuleDown(self) -> None:
        """C++: SendCmdParsingRuleDown() — 전체 Manager에 파싱룰 다운 명령."""
        import asyncio
        for sock in self._socket_connection_list:
            asyncio.ensure_future(sock.SendPacket(CMD_PARSING_RULE_DOWN))

    def SendCmdMappingRuleDown(self) -> None:
        """C++: SendCmdMappingRuleDown() — 전체 Manager에 매핑룰 다운 명령."""
        import asyncio
        for sock in self._socket_connection_list:
            asyncio.ensure_future(sock.SendPacket(CMD_MAPPING_RULE_DOWN))

    # =========================================================================
    # SendSessionControl
    # =========================================================================

    def SendSessionControl(self, session_ctl: AS_SESSION_CONTROL_T) -> None:
        """C++: SendSessionControl(AS_SESSION_CONTROL_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR
        from ProcNaServer.ManagerConnection import ManagerConnection

        con: Optional[ManagerConnection] = self.find_session(session_ctl.ManagerId)
        if con:
            con.SendSessionControl(session_ctl)
        else:
            MAINPTR().SendAsciiError(
                1, "The Manager(%s) does not start.", session_ctl.ManagerId)

    # =========================================================================
    # ParserRuleChange / ConnectorDescChange
    # =========================================================================

    def ParserRuleChange(self, change_info: AS_RULE_CHANGE_INFO_T) -> bool:
        """C++: ParserRuleChange(AS_RULE_CHANGE_INFO_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR
        from ProcNaServer.ManagerConnection import ManagerConnection

        con: Optional[ManagerConnection] = self.find_session(change_info.ManagerId)
        if con is None:
            MAINPTR().SendAsciiError(
                1, "The Manager(%s) does not start.", change_info.ManagerId)
            return False

        info = self.FindConnectorInfo(change_info.ManagerId, change_info.ProcessId)
        if info is None:
            logger.error("Can't find connector : %s", change_info.ProcessId)
            return False

        if info.m_ConnectorInfo.SettingStatus != START:
            logger.error("Connector(%s) Status is STOP", change_info.ProcessId)
            return False

        info.m_ConnectorInfo.RuleId = change_info.RuleId
        con.ParserRuleChange(change_info)
        MAINPTR().SendInfoChange(info.m_ConnectorInfo)
        return True

    def ConnectorDescChange(self, info: AS_CONNECTOR_DESC_CHANGE_INFO_T) -> bool:
        """C++: ConnectorDescChange(AS_CONNECTOR_DESC_CHANGE_INFO_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        con_info = self.FindConnectorInfo(info.ManagerId, info.ConnectorId)
        if con_info is None:
            logger.error("Can't Find Connector Info : %s", info.ConnectorId)
            return False
        con_info.m_ConnectorInfo.Desc = info.Description
        MAINPTR().SendInfoChange(con_info.m_ConnectorInfo)
        return True

    # =========================================================================
    # GetRouterInfo
    # =========================================================================

    def GetRouterInfo(self, req: AS_ROUTER_INFO_REQ_T,
                      router_info: RouterInfoList) -> None:
        """C++: GetRouterInfo(AS_ROUTER_INFO_REQ_T*, RouterInfoList*)"""
        from Common.CommTypeList import AS_ROUTER_INFO_T
        from ProcNaServer.ManagerConnection import ManagerConnection

        for i in range(req.equipNo):
            equip_id = req.equipIds[i]
            info = AS_ROUTER_INFO_T()
            info.equipId    = equip_id
            info.resultMode = 0
            found = False

            for sock in self._socket_connection_list:
                mgr_con: ManagerConnection = sock
                logger.debug("Find Equip Id: %s", equip_id)
                if mgr_con.IsHasCmdPortNeName(equip_id):
                    info.resultMode = 1
                    info.ipaddress  = mgr_con.get_peer_ip()    # AsSocket.get_peer_ip()
                    info.portNo     = mgr_con.GetRouterPortNo()
                    found = True
                    break

            router_info.append(info)

    # =========================================================================
    # GetLogStatusList / SendDataHandlerInfoChange / RecvInitInfo
    # =========================================================================

    def GetLogStatusList(self, log_status_list: list) -> None:
        """C++: GetLogStatusList(LogStatusVector*)"""
        from ProcNaServer.ManagerConnection import ManagerConnection
        for sock in self._socket_connection_list:
            sock.GetLogStatusList(log_status_list)

    def SendDataHandlerInfoChange(self, info: AS_DATA_HANDLER_INFO_T) -> None:
        """C++: SendDataHandlerInfoChange(AS_DATA_HANDLER_INFO_T*)"""
        import asyncio
        for sock in self._socket_connection_list:
            asyncio.ensure_future(sock.SendPacket(
                AS_DATA_HANDLER_INFO,
                _pack_data_handler_info(info),
                _sizeof_data_handler_info(),
            ))

    def RecvInitInfo(self, init_info: AS_DATA_ROUTING_INIT_T) -> None:
        """C++: RecvInitInfo(AS_DATA_ROUTING_INIT_T*)"""
        import asyncio
        for sock in self._socket_connection_list:
            asyncio.ensure_future(sock.SendPacket(
                AS_DATA_ROUTING_INIT,
                _pack_data_routing_init(init_info),
                _sizeof_data_routing_init(),
            ))

    def SendCmdLogStatusChange(self, log_ctl, session_name: str = "") -> bool:
        """C++: SendCmdLogStatusChange() — ConnectionMgr 위임."""
        return super().send_cmd_log_status_change(log_ctl, session_name)

    # =========================================================================
    # Find 메서드
    # =========================================================================

    def GetManagerInfoMap(self) -> ManagerInfoMap:
        return self._manager_info_map

    def FindManagerInfo(self, manager_id: str) -> Optional[ManagerInfo]:
        """C++: FindManagerInfo(string ManagerId)"""
        return self._manager_info_map.get(manager_id)

    def FindConnectorInfo(self, manager_id: str,
                           connector_id: str = "") -> Optional[ConnectorInfo]:
        """
        C++ 오버로드 2종 통합:
          FindConnectorInfo(ManagerId, ConnectorId) → 특정 Manager에서 검색
          FindConnectorInfo(ConnectorId)             → 전체 Manager에서 검색
        """
        if connector_id:
            mgr_info = self.FindManagerInfo(manager_id)
            if mgr_info is None:
                return None
            return mgr_info.GetConnectorInfo(connector_id)
        else:
            # ConnectorId만 전달된 경우 (manager_id가 실제로 connector_id)
            for mgr_info in self._manager_info_map.values():
                tmp = mgr_info.GetConnectorInfo(manager_id)
                if tmp:
                    return tmp
            return None

    def FindConnectionInfo(self, manager_id: str,
                            connector_id: str = "",
                            sequence: int = -1) -> Optional[AS_CONNECTION_INFO_T]:
        """
        C++ 오버로드 2종 통합:
          FindConnectionInfo(ManagerId, ConnectorId, Sequence)
          FindConnectionInfo(Sequence)
        """
        if connector_id:
            con_info = self.FindConnectorInfo(manager_id, connector_id)
            if con_info is None:
                return None
            return con_info.GetConnectionInfo(sequence)
        else:
            # sequence만으로 전체 검색 (manager_id가 실제 sequence)
            seq = int(manager_id) if isinstance(manager_id, (int, str)) else sequence
            for mgr_info in self._manager_info_map.values():
                for con_info in mgr_info.m_ConnectorInfoMap.values():
                    result = con_info.GetConnectionInfo(seq)
                    if result:
                        return result
            return None

    # =========================================================================
    # RecvInfoChange (CRUD)
    # =========================================================================

    def RecvInfoChange(self, info, result_msg: list) -> bool:
        """C++ 오버로드 3종 → 타입 분기."""
        dispatch = {
            AS_MANAGER_INFO_T:    self._recv_manager,
            AS_CONNECTOR_INFO_T:  self._recv_connector,
            AS_CONNECTION_INFO_T: self._recv_connection,
        }
        handler = dispatch.get(type(info))
        if handler:
            return handler(info, result_msg)
        result_msg[0] = f"Unknown type: {type(info)}"
        return False

    def _recv_manager(self, info: AS_MANAGER_INFO_T, result_msg: list) -> bool:
        from ProcNaServer.AsciiServerWorld import MAINPTR

        if info.RequestStatus == CREATE_DATA:
            new_mgr = ManagerInfo()
            new_mgr.m_ManagerInfo.ManagerId     = info.ManagerId
            new_mgr.m_ManagerInfo.IP            = info.IP
            new_mgr.m_ManagerInfo.SshID         = info.SshID
            new_mgr.m_ManagerInfo.SshPass       = info.SshPass
            new_mgr.m_ManagerInfo.CurStatus     = STOP
            new_mgr.m_ManagerInfo.SettingStatus = info.SettingStatus
            new_mgr.m_ManagerInfo.RequestStatus = WAIT_NO
            self._manager_info_map[info.ManagerId] = new_mgr
            MAINPTR().SendInfoChange(new_mgr.m_ManagerInfo)
            return True

        if info.RequestStatus == UPDATE_DATA:
            mgr_info = self._manager_info_map.pop(info.OldManagerId, None)
            if mgr_info is None:
                result_msg[0] = f"Can't Find Manager : {info.OldManagerId}"
                return False
            mgr = mgr_info.m_ManagerInfo
            mgr.ManagerId     = info.ManagerId
            mgr.IP            = info.IP
            mgr.SshID         = info.SshID
            mgr.SshPass       = info.SshPass
            mgr.CurStatus     = STOP
            mgr.SettingStatus = info.SettingStatus
            mgr.RequestStatus = WAIT_NO
            self._manager_info_map[info.ManagerId] = mgr_info

            # ManagerId 변경 시 하위 Connector/Connection도 업데이트
            if info.ManagerId != info.OldManagerId:
                for con_info in mgr_info.m_ConnectorInfoMap.values():
                    con_info.m_ConnectorInfo.ManagerId = info.ManagerId
                    for conn in con_info.m_ConnectionInfoList:
                        conn.ManagerId = info.ManagerId

            MAINPTR().SendInfoChange(info)
            return True

        if info.RequestStatus == DELETE_DATA:
            if info.ManagerId not in self._manager_info_map:
                result_msg[0] = f"Can't Find Manager : {info.ManagerId}"
                return False
            del self._manager_info_map[info.ManagerId]
            MAINPTR().SendInfoChange(info)
            return True

        return False

    def _recv_connector(self, info: AS_CONNECTOR_INFO_T, result_msg: list) -> bool:
        from ProcNaServer.AsciiServerWorld import MAINPTR

        mgr_info = self.FindManagerInfo(info.ManagerId)
        if mgr_info is None:
            result_msg[0] = f"Can't Find Manager : {info.ManagerId}"
            return False

        if info.RequestStatus == CREATE_DATA:
            new_con = ConnectorInfo()
            ci = new_con.m_ConnectorInfo
            ci.ManagerId       = info.ManagerId
            ci.ConnectorId     = info.ConnectorId
            ci.RuleId          = info.RuleId
            ci.JunctionType    = info.JunctionType
            ci.MmcIdentType    = info.MmcIdentType
            ci.CmdResponseType = info.CmdResponseType
            ci.LogCycle        = info.LogCycle
            ci.CreateDate      = info.CreateDate
            ci.ModifyDate      = info.ModifyDate
            ci.LastActionDate  = info.LastActionDate
            ci.LastActionType  = info.LastActionType
            ci.LastActionDesc  = info.LastActionDesc
            ci.Desc            = info.Desc
            ci.SettingStatus   = info.SettingStatus
            ci.CurStatus       = STOP
            ci.RequestStatus   = WAIT_NO
            mgr_info.m_ConnectorInfoMap[info.ConnectorId] = new_con
            MAINPTR().SendInfoChange(ci)
            return True

        if info.RequestStatus == UPDATE_DATA:
            con_info = self.FindConnectorInfo(info.ConnectorId)
            if con_info is None:
                result_msg[0] = f"Can't Find Connector : {info.ConnectorId}"
                return False

            ci = con_info.m_ConnectorInfo
            ci.RuleId          = info.RuleId
            ci.MmcIdentType    = info.MmcIdentType
            ci.SettingStatus   = info.SettingStatus
            ci.CmdResponseType = info.CmdResponseType

            # Manager 변경
            if ci.ManagerId != info.ManagerId:
                old_mgr = self.FindManagerInfo(ci.ManagerId)
                if old_mgr is None:
                    result_msg[0] = (f"Can't Find Manager({ci.ManagerId}) "
                                     f"for Connector({info.ConnectorId})")
                    return False
                old_mgr.m_ConnectorInfoMap.pop(info.ConnectorId, None)
                ci.ManagerId = info.ManagerId
                for conn in con_info.m_ConnectionInfoList:
                    conn.ManagerId = info.ManagerId
                mgr_info.m_ConnectorInfoMap[info.ConnectorId] = con_info

            ci.LogCycle        = info.LogCycle
            ci.ModifyDate      = info.ModifyDate
            ci.LastActionDate  = info.LastActionDate
            ci.LastActionType  = info.LastActionType
            ci.LastActionDesc  = info.LastActionDesc
            ci.Desc            = info.Desc
            info.CreateDate    = ci.CreateDate
            MAINPTR().SendInfoChange(info)
            return True

        if info.RequestStatus == DELETE_DATA:
            if info.ConnectorId not in mgr_info.m_ConnectorInfoMap:
                result_msg[0] = f"Can't Find Connector : {info.ConnectorId}"
                return False
            del mgr_info.m_ConnectorInfoMap[info.ConnectorId]
            MAINPTR().SendInfoChange(info)
            return True

        return False

    def _recv_connection(self, info: AS_CONNECTION_INFO_T, result_msg: list) -> bool:
        from ProcNaServer.AsciiServerWorld import MAINPTR

        if info.RequestStatus == CREATE_DATA:
            con_info = self.FindConnectorInfo(info.ManagerId, info.ConnectorId)
            if con_info is None:
                result_msg[0] = f"Can't Find Connector Info : {info.ConnectorId}"
                return False
            new_conn = copy.copy(info)
            new_conn.CurStatus     = STOP
            new_conn.RequestStatus = WAIT_NO
            con_info.m_ConnectionInfoList.append(new_conn)
            MAINPTR().SendInfoChange(info)
            return True

        if info.RequestStatus == UPDATE_DATA:
            conn = self.FindConnectionInfo(sequence=info.Sequence)
            if conn is None:
                result_msg[0] = f"Can't Find Connection Info : Sequence({info.Sequence})"
                return False
            con_info = self.FindConnectorInfo(conn.ConnectorId)
            if con_info is None:
                result_msg[0] = f"Can't Find Connector Info : {conn.ConnectorId}"
                return False

            # Connector 변경
            if info.ConnectorId != con_info.m_ConnectorInfo.ConnectorId:
                con_info.DeleteConnectionInfo(info.Sequence)
                con_info = self.FindConnectorInfo(info.ConnectorId)
                if con_info is None:
                    result_msg[0] = f"Can't Find Connector Info : {info.ConnectorId}"
                    return False

            new_conn = copy.copy(info)
            new_conn.CurStatus     = STOP
            new_conn.RequestStatus = WAIT_NO
            con_info.m_ConnectionInfoList.append(new_conn)
            MAINPTR().SendInfoChange(info)
            return True

        if info.RequestStatus == DELETE_DATA:
            con_info = self.FindConnectorInfo(info.ManagerId, info.ConnectorId)
            if con_info is None:
                result_msg[0] = f"Can't Find Connector Info : {info.ConnectorId}"
                return False
            con_info.DeleteConnectionInfo(info.Sequence)
            MAINPTR().SendInfoChange(info)
            return True

        return False


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼 (struct.pack 기반)
# 실제 구조체 크기/레이아웃은 CommTypeList 직렬화 모듈과 맞춰야 함
# ─────────────────────────────────────────────────────────────────────────────

def _pack_proc_control(ctl: AS_PROC_CONTROL_T) -> bytes:
    """AS_PROC_CONTROL_T → bytes. CommTypeList.pack() 메서드가 있으면 대체."""
    if hasattr(ctl, 'pack'):
        return ctl.pack()
    return b''

def _sizeof_proc_control() -> int:
    return 0  # pack() 결과 len으로 대체

def _pack_data_handler_info(info: AS_DATA_HANDLER_INFO_T) -> bytes:
    if hasattr(info, 'pack'):
        return info.pack()
    return b''

def _sizeof_data_handler_info() -> int:
    return 0

def _pack_data_routing_init(info: AS_DATA_ROUTING_INIT_T) -> bytes:
    if hasattr(info, 'pack'):
        return info.pack()
    return b''

def _sizeof_data_routing_init() -> int:
    return 0