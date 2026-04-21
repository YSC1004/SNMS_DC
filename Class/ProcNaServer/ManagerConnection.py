"""
ManagerConnection.py
C++ ManagerConnection.h/.C → Python 변환

개별 Manager(ProcNaManager) 소켓 연결 처리.
  - 패킷 수신 분기 (MANAGER_INIT_END / CONNECTOR_PORT_INFO_REQ / ...)
  - 초기화 완료 후 Connector 기동 명령 전송 (ManagerInitEnd)
  - 세션 종료 시 재기동 또는 정상 종료 (close_socket)
  - MMC 명령 전송 / AliveCheck / 타이머
"""

import asyncio
import logging
from typing import Optional, Dict, Set, TYPE_CHECKING

from Common.AsSocket import AsSocket                    # 가상함수 오버라이드
from Common.AsUtil import AsUtil
from Common.CommTypeList import (
    AS_MANAGER_INFO_T, AS_CONNECTOR_INFO_T, AS_CONNECTION_INFO_T,
    AS_PROC_CONTROL_T, AS_PROCESS_STATUS_T, AS_PORT_STATUS_INFO_T,
    AS_MMC_PUBLISH_T, AS_SESSION_CONTROL_T, AS_RULE_CHANGE_INFO_T,
    AS_LOG_STATUS_T, AS_CMD_OPEN_PORT_T, AS_SYSTEM_INFO_T,
    AS_ASCII_ERROR_MSG_T, AS_CONNECTOR_PORT_INFO_REQ_T, AS_MMC_RESULT_T,
    AS_ROUTER_PORT_INFO_T,
)
from Common.CommType import (
    ASCII_MANAGER, ASCII_CONNECTOR,
    START, STOP, WAIT_NO, WAIT_START, WAIT_STOP, UNDEFINED,
    NOT_ASSIGN, LOG_ADD,
    MANAGER_INIT_END, CONNECTOR_PORT_INFO_REQ,
    CMD_MMC_PUBLISH_RES, AS_LOG_INFO, ASCII_ERROR_MSG,
    PROCESS_INFO, PORT_STATUS_INFO, ROUTER_PORT_INFO, AS_SYSTEM_INFO,
    PROC_CONTROL, SESSION_CONTROL, CMD_OPEN_PORT,
    CMD_MMC_PUBLISH_REQ, CMD_PARSING_RULE_CHANGE,
    CMD_PROC_TERMINATE, AS_DATA_HANDLER_INFO,
    PROC_TERMINATE_WAIT, PROC_TERMINATE_WAIT_TIMEOUT,
    ARG_LOG_HOUR, ARG_LOG_DAY,
)
from ProcNaServer.AsciiServerType import (
    ManagerInfo, ConnectorInfo, ConnectorInfoMap, ConnectionInfoList,
    SESSION_TYPE_MGR,
)

if TYPE_CHECKING:
    from ProcNaServer.ManagerConnMgr import ManagerConnMgr

logger = logging.getLogger(__name__)


class ManagerConnection(AsSocket):
    """
    C++ ManagerConnection (AsSocket 상속) 대응.

    AsSocket 가상 메서드 오버라이드:
      receive_packet()              ← C++ ReceivePacket()
      close_socket()                ← C++ CloseSocket()
      session_identify_callback()   ← C++ SessionIdentify()
      alive_check_fail()            ← C++ AliveCheckFail()

    타이머:
      AsWorld.SetTimer / CancelTimer 사용.
      _terminate_timer_key: int | None
    """

    def __init__(self, mgr_conn_mgr: "ManagerConnMgr") -> None:
        super().__init__()
        self._mgr_conn_mgr:          "ManagerConnMgr"              = mgr_conn_mgr
        self._manager_info:          Optional[ManagerInfo]         = None
        self._connector_info_map:    Optional[ConnectorInfoMap]    = None
        self._router_port_no:        int                           = -1
        self._has_cmd_port_ne_set:   Set[str]                      = set()
        # LogStatusMap: name(str) → AS_LOG_STATUS_T
        self._log_status_map:        Dict[str, AS_LOG_STATUS_T]    = {}
        self._terminate_timer_key:   Optional[int]                 = None

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)"""
        if session_identify == ASCII_MANAGER:
            self._manager_req_process(packet)
        else:
            logger.debug("UnKnown Session : %d(%s)", session_identify,
                         "NOT_ASSIGN" if session_identify == NOT_ASSIGN else "UnKnown")

    def close_socket(self, errno_val: int) -> None:
        """
        C++: virtual CloseSocket(int Errno)
        소켓 종료 시 Manager/Connector/Connection 상태 초기화 및 재기동.
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR

        session_name = self.GetSessionName()
        logger.debug("Manager Socket Broken : %s", session_name)

        if self._manager_info is None:
            self._mgr_conn_mgr.remove(self)        # ConnectionMgr.remove()
            return

        mgr = self._manager_info.m_ManagerInfo
        mgr.CurStatus     = STOP
        mgr.RequestStatus = WAIT_NO

        # 모든 Connector/Connection 상태 초기화
        for con_info in self._connector_info_map.values():
            con_info.m_ConnectorInfo.CurStatus     = STOP
            con_info.m_ConnectorInfo.RequestStatus = WAIT_NO
            logger.debug("Change Connector(%s) Status(%d)",
                         con_info.m_ConnectorInfo.ConnectorId,
                         con_info.m_ConnectorInfo.CurStatus)
            for conn in con_info.m_ConnectionInfoList:
                conn.RequestStatus = WAIT_NO
                conn.CurStatus     = UNDEFINED

        MAINPTR().SendInfoChange(mgr)

        # 프로세스 상태 업데이트
        proc_info = AS_PROCESS_STATUS_T()
        proc_info.ProcessId   = session_name
        proc_info.Status      = STOP
        proc_info.ProcessType = ASCII_MANAGER
        MAINPTR().UpdateProcessInfo(proc_info)

        # 설정 상태 START → 비정상 종료 → 재기동
        if mgr.SettingStatus == START:
            MAINPTR().SendAsciiError(
                1, "The MANAGER(%s) is killed abnormal.", session_name)
            logger.info("The MANAGER(%s) is killed abnormal.", session_name)
            if self._mgr_conn_mgr.ExecuteManager(self._manager_info):
                logger.error("The MANAGER(%s) is reexecuted.", session_name)
                MAINPTR().SendAsciiError(
                    1, "The MANAGER(%s) is reexecuted.", session_name)
            else:
                MAINPTR().SendAsciiError(1, "Manager reexecute failed.")
        else:
            logger.debug("The MANAGER(%s) is killed normally.", session_name)
            MAINPTR().SendAsciiError(
                1, "The MANAGER(%s) is killed normally.", session_name)

        self._mgr_conn_mgr.remove(self)            # ConnectionMgr.remove()

    def session_identify_callback(self, session_type: int,
                                   session_name: str = "") -> None:
        """
        C++: virtual SessionIdentify(int SessionType, string SessionName)
        Manager 세션 식별 완료 → 타이머 취소 → AliveCheck 시작.
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR

        self._manager_info = self._mgr_conn_mgr.FindManagerInfo(session_name)
        if self._manager_info is None:
            logger.error("Can't Find ManagerInfo : %s", session_name)
            self._close()
            self._mgr_conn_mgr.remove(self)
            return

        if self._manager_info.m_ManagerInfo.SettingStatus == STOP:
            logger.error("Manager(%s) Connection is invalid(timeover etc...)",
                         session_name)
            self._close()
            self._mgr_conn_mgr.remove(self)
            return

        self._connector_info_map = self._manager_info.m_ConnectorInfoMap

        logger.debug("Session Identify : Type(%s), SessionName(%s)",
                     AsUtil.GetProcessTypeString(session_type), session_name)

        # 기동 대기 타이머 취소
        self._mgr_conn_mgr.ManagerSessionIdentify(
            self._manager_info.m_ManagerInfo.ManagerId)

        # 세션 설정 (소켓 버퍼 등)
        MAINPTR().SessionCfg(self, SESSION_TYPE_MGR)

        # AliveCheck 시작 (AsSocket.StartAliveCheck)
        self.StartAliveCheck(
            MAINPTR().GetProcAliveCheckTime(),      # AsWorld.GetProcAliveCheckTime()
            MAINPTR().GetAliveCheckLimitCnt(),      # AsWorld.GetAliveCheckLimitCnt()
        )

        MAINPTR().SendAsciiError(
            1, "The MANAGER(%s) is start successfully.", session_name)

    def alive_check_fail(self, fail_count: int) -> None:
        """C++: virtual AliveCheckFail(int FailCount)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        session_name = self.GetSessionName()
        logger.debug("AliveCheckFail(%s) , Count : %d", session_name, fail_count)
        logger.debug("The MANAGER(%s) is killed on purpose for no reply.",
                     session_name)
        MAINPTR().SendAsciiError(
            1, "The MANAGER(%s) is killed on purpose for no reply.", session_name)

        if self._manager_info:
            self._mgr_conn_mgr.KillManager(
                self._manager_info.m_ManagerInfo.ManagerId)

    # =========================================================================
    # ReceiveTimeOut (AsWorld 가상함수 오버라이드)
    # =========================================================================

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """C++: ReceiveTimeOut — PROC_TERMINATE_WAIT: 강제 Kill."""
        if reason == PROC_TERMINATE_WAIT:
            session_name = self.GetSessionName()
            logger.error("Manager Terminate TimeOut")
            logger.error("Manager Kill Force!!! : %s", session_name)
            self._terminate_timer_key = None
            if self._manager_info:
                self._mgr_conn_mgr.KillManager(
                    self._manager_info.m_ManagerInfo.ManagerId)
        else:
            logger.debug("Unknown Timeout Reason %d", reason)

    # =========================================================================
    # 패킷 처리 내부 메서드
    # =========================================================================

    def _manager_req_process(self, packet) -> None:
        """C++: ManagerReqProcess(PACKET_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        msg_id = packet.MsgId

        if msg_id == MANAGER_INIT_END:
            asyncio.ensure_future(self._manager_init_end())

        elif msg_id == CONNECTOR_PORT_INFO_REQ:
            asyncio.ensure_future(
                self._send_connector_port_info(packet.Msg))

        elif msg_id == CMD_MMC_PUBLISH_RES:
            MAINPTR().ReceiveMMCResult(packet.Msg)

        elif msg_id == AS_LOG_INFO:
            self._receive_log_info(packet.Msg)

        elif msg_id == ASCII_ERROR_MSG:
            MAINPTR().SendAsciiError(packet.Msg)

        elif msg_id == PROCESS_INFO:
            proc_info: AS_PROCESS_STATUS_T = packet.Msg
            self._mgr_conn_mgr.ReceiveProcInfo(proc_info)

            # Connector STOP 시 CmdNeList 제거
            if proc_info.ProcessType == ASCII_CONNECTOR:
                if proc_info.Status == STOP:
                    process_id = proc_info.ProcessId
                    pos = process_id.find("_")
                    if pos != -1:
                        process_id = process_id[pos + 1:]
                    self.RemoveCmdNeList(process_id)

        elif msg_id == PORT_STATUS_INFO:
            self._mgr_conn_mgr.ReceivePortInfo(packet.Msg)

        elif msg_id == ROUTER_PORT_INFO:
            rp: AS_ROUTER_PORT_INFO_T = packet.Msg
            self._router_port_no = rp.RouterPortNo
            logger.debug("Router PortNo (%s:%d)",
                         self.GetSessionName(), self._router_port_no)

        elif msg_id == AS_SYSTEM_INFO:
            from ProcNaServer.AsciiServerWorld import MAINPTR
            MAINPTR().RecvSystemInfo(packet.Msg)

        else:
            logger.debug("UnKnown MsgId : %d", msg_id)

    # =========================================================================
    # ManagerInitEnd
    # =========================================================================

    async def _manager_init_end(self) -> None:
        """
        C++: ManagerInitEnd()
        Manager 초기화 완료 → DataHandlerInfo 전송 → Connector 기동 명령 전송.
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR

        logger.debug("Manager(%s) Init End", self.GetSessionName())

        if self._manager_info is None:
            logger.error("Manager(%s) Info not init...", self.GetSessionName())
            self._close()
            self._mgr_conn_mgr.remove(self)
            return

        mgr = self._manager_info.m_ManagerInfo
        mgr.CurStatus     = START
        mgr.RequestStatus = WAIT_NO

        await self._send_data_handler_info()

        delay_time = 0
        logger.debug("Connector size : %d", len(self._connector_info_map))

        for con_info in self._connector_info_map.values():
            ci = con_info.m_ConnectorInfo
            if ci.SettingStatus == STOP:
                continue

            proc_ctl = AS_PROC_CONTROL_T()
            proc_ctl.ProcessType     = ASCII_CONNECTOR
            proc_ctl.ManagerId       = ci.ManagerId
            proc_ctl.Status          = START
            proc_ctl.RuleId          = ci.RuleId
            proc_ctl.ProcessId       = ci.ConnectorId
            proc_ctl.MmcIdentType    = ci.MmcIdentType
            proc_ctl.CmdResponseType = ci.CmdResponseType
            proc_ctl.JunctionType    = ci.JunctionType
            proc_ctl.LogCycle        = ci.LogCycle
            proc_ctl.DelayTime       = delay_time

            logger.debug(
                "ConnectorId : %s, JunctionType : %s, RuleId : %s, "
                "MmcIdentType : %d, CmdResponseType : %d, LogCycle : %s",
                proc_ctl.ProcessId,
                AsUtil.GetJunctionTypeString(proc_ctl.JunctionType),
                proc_ctl.RuleId,
                proc_ctl.MmcIdentType,
                proc_ctl.CmdResponseType,
                ARG_LOG_HOUR if proc_ctl.LogCycle else ARG_LOG_DAY,
            )

            payload = _pack_struct(proc_ctl)
            if not await self.SendPacket(PROC_CONTROL, payload, len(payload)):
                return

            ci.RequestStatus = WAIT_START
            MAINPTR().SendInfoChange(ci)
            delay_time += 1

        MAINPTR().SendInfoChange(mgr)

    # =========================================================================
    # SendConnectorPortInfo
    # =========================================================================

    async def _send_connector_port_info(self,
                                         con_info_req: AS_CONNECTOR_PORT_INFO_REQ_T
                                         ) -> None:
        """C++: SendConnectorPortInfo(AS_CONNECTOR_PORT_INFO_REQ_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR, DBPTR

        logger.debug("SendConnectorPortInfo : %s", con_info_req.ConnectorId)

        con_info = self._mgr_conn_mgr.FindConnectorInfo(
            self.GetSessionName(), con_info_req.ConnectorId)
        if con_info is None:
            logger.error("Can't Find Connector : %s", con_info_req.ConnectorId)
            return

        ip_list: Dict[int, str] = {}
        if not DBPTR().GetConnectionIpInfo(ip_list, con_info_req.ConnectorId):
            return

        for conn in con_info.m_ConnectionInfoList:
            ip = ip_list.get(conn.Sequence)
            if ip is None:
                logger.error("Can't Find Ip for connection sequence : %d",
                             conn.Sequence)
                continue

            if conn.SettingStatus != START:
                continue

            cmd_port = AS_CMD_OPEN_PORT_T()
            cmd_port.Id              = MAINPTR().GetMsgId()
            cmd_port.Sequence        = conn.Sequence
            cmd_port.EquipId         = conn.ConnectorId
            cmd_port.AgentEquipId    = conn.AgentEquipId
            cmd_port.ConnectorId     = conn.ConnectorId
            cmd_port.IpAddress       = ip
            cmd_port.PortNo          = conn.PortNo
            cmd_port.UserId          = conn.UserId
            cmd_port.Password        = conn.UserPassword
            cmd_port.ProtocolType    = conn.ProtocolType
            cmd_port.PortType        = conn.PortType
            cmd_port.GatFlag         = conn.GatFlag
            cmd_port.CommandPortFlag = conn.CommandPortFlag
            cmd_port.Name = (f"{cmd_port.Sequence}_"
                             f"{AsUtil.GetPortTypeString(cmd_port.PortType)}")

            AsUtil.CmdOpenPortDisplay(cmd_port)
            await self.CmdOpenPortInfo(cmd_port)

            if cmd_port.CommandPortFlag:
                logger.debug("Insert HasCmdPortNeListSet : %s(%s)",
                             conn.ConnectorId, self.GetSessionName())
                self._has_cmd_port_ne_set.add(conn.ConnectorId)

            conn.RequestStatus = WAIT_START

    # =========================================================================
    # SendDataHandlerInfo
    # =========================================================================

    async def _send_data_handler_info(self) -> None:
        """C++: SendDataHandlerInfo() — RunMode==0, SettingStatus==START인 것만 전송."""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        info_map = MAINPTR().GetDataHandlerInfoMap()
        for dh_info in info_map.values():
            if dh_info.RunMode == 0 and dh_info.SettingStatus == START:
                payload = _pack_struct(dh_info)
                if not await self.SendPacket(AS_DATA_HANDLER_INFO, payload, len(payload)):
                    return

    # =========================================================================
    # CmdOpenPortInfo (AsSocket 가상함수 오버라이드)
    # =========================================================================

    async def CmdOpenPortInfo(self, port_info: AS_CMD_OPEN_PORT_T) -> bool:
        """C++: CmdOpenPortInfo(AS_CMD_OPEN_PORT_T*) → CMD_OPEN_PORT 패킷 전송."""
        payload = _pack_struct(port_info)
        return await self.SendPacket(CMD_OPEN_PORT, payload, len(payload))

    # =========================================================================
    # SendMMCCommand
    # =========================================================================

    async def SendMMCCommand(self, mmc_com: AS_MMC_PUBLISH_T) -> bool:
        """C++: SendMMCCommand(AS_MMC_PUBLISH_T*) → CMD_MMC_PUBLISH_REQ 전송."""
        payload = _pack_struct(mmc_com)
        return await self.SendPacket(CMD_MMC_PUBLISH_REQ, payload, len(payload))

    # =========================================================================
    # StopManager
    # =========================================================================

    async def StopManager(self) -> None:
        """C++: StopManager() — CMD_PROC_TERMINATE 전송 + 타임아웃 타이머."""
        await self.SendPacket(CMD_PROC_TERMINATE)

        if self._terminate_timer_key is not None:
            self.CancelTimer(self._terminate_timer_key)  # AsWorld.CancelTimer

        self._terminate_timer_key = self.SetTimer(   # AsWorld.SetTimer
            PROC_TERMINATE_WAIT_TIMEOUT,
            PROC_TERMINATE_WAIT,
        )

    # =========================================================================
    # SendSessionControl
    # =========================================================================

    def SendSessionControl(self, session_ctl: AS_SESSION_CONTROL_T) -> bool:
        """C++: SendSessionControl(AS_SESSION_CONTROL_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR, DBPTR

        conn = self._mgr_conn_mgr.FindConnectionInfo(
            session_ctl.ManagerId, session_ctl.ConnectorId, session_ctl.Sequence)
        if conn is None:
            logger.error("Can't Find Session : %d", session_ctl.Sequence)
            MAINPTR().SendAsciiError(
                1, "Can't Find Session : %d", session_ctl.Sequence)
            return False

        if conn.RequestStatus != WAIT_NO:
            req_str = "Start" if conn.RequestStatus == WAIT_START else "Stop"
            logger.info("Already Request Connection: %d(%s)",
                        session_ctl.Sequence, req_str)
            MAINPTR().SendAsciiError(
                1, "Already Request Process: %d(%s)",
                session_ctl.Sequence, req_str)
            return False

        if not DBPTR().UpdateConnectionStatus(session_ctl):
            logger.error("Update Connection Error : %s", DBPTR().GetErrorMsg())
            return False

        if session_ctl.Status == START and conn.SettingStatus == START:
            logger.info("Already Start Connection : %d", session_ctl.Sequence)
            MAINPTR().SendAsciiError(
                1, "Already Start Connection : %d", session_ctl.Sequence)
            return False
        if session_ctl.Status == STOP and conn.SettingStatus == STOP:
            logger.info("Already Stop Connection : %d", session_ctl.Sequence)
            MAINPTR().SendAsciiError(
                1, "Already Stop Connection : %d", session_ctl.Sequence)
            return False

        conn.SettingStatus = START if session_ctl.Status == START else STOP
        conn.RequestStatus = WAIT_START if session_ctl.Status == START else WAIT_STOP
        MAINPTR().SendInfoChange(conn)

        if session_ctl.Status != START:
            conn.RequestStatus = WAIT_STOP
            if conn.CommandPortFlag:
                self.RemoveCmdNeList(session_ctl.ConnectorId)
            asyncio.ensure_future(self.SendPacket(
                SESSION_CONTROL, _pack_struct(session_ctl), 0))
        else:
            ip_list: Dict[int, str] = {}
            if DBPTR().GetConnectionIpInfo(
                    ip_list, session_ctl.ConnectorId, session_ctl.Sequence):
                ip = ip_list.get(conn.Sequence)
                if ip is None:
                    logger.error("Can't Find Ip for connection sequence : %s,%d",
                                 session_ctl.ConnectorId, conn.Sequence)
                    MAINPTR().SendAsciiError(
                        1, "Can't Find Ip for connection sequence : %s,%d",
                        session_ctl.ConnectorId, conn.Sequence)
                    return False

                cmd_port = AS_CMD_OPEN_PORT_T()
                cmd_port.Id              = MAINPTR().GetMsgId()
                cmd_port.Sequence        = conn.Sequence
                cmd_port.EquipId         = conn.ConnectorId
                cmd_port.AgentEquipId    = conn.AgentEquipId
                cmd_port.ConnectorId     = conn.ConnectorId
                cmd_port.IpAddress       = ip
                cmd_port.PortNo          = conn.PortNo
                cmd_port.UserId          = conn.UserId
                cmd_port.Password        = conn.UserPassword
                cmd_port.ProtocolType    = conn.ProtocolType
                cmd_port.PortType        = conn.PortType
                cmd_port.GatFlag         = conn.GatFlag
                cmd_port.CommandPortFlag = conn.CommandPortFlag
                cmd_port.Name = (f"{cmd_port.Sequence}_"
                                 f"{AsUtil.GetPortTypeString(cmd_port.PortType)}")

                AsUtil.CmdOpenPortDisplay(cmd_port)
                asyncio.ensure_future(self.CmdOpenPortInfo(cmd_port))

                if conn.CommandPortFlag:
                    logger.debug("Insert HasCmdPortNeListSet : %s(%s)",
                                 conn.ConnectorId, self.GetSessionName())
                    self._has_cmd_port_ne_set.add(conn.ConnectorId)

            conn.RequestStatus = WAIT_START

        return True

    # =========================================================================
    # ParserRuleChange
    # =========================================================================

    async def ParserRuleChange(self, change_info: AS_RULE_CHANGE_INFO_T) -> None:
        """C++: ParserRuleChange(AS_RULE_CHANGE_INFO_T*)"""
        payload = _pack_struct(change_info)
        await self.SendPacket(CMD_PARSING_RULE_CHANGE, payload, len(payload))

    # =========================================================================
    # SendCmdParsingRuleDown / SendCmdMappingRuleDown
    # =========================================================================

    async def SendCmdParsingRuleDown(self) -> None:
        from Common.CommType import CMD_PARSING_RULE_DOWN
        await self.SendPacket(CMD_PARSING_RULE_DOWN)

    async def SendCmdMappingRuleDown(self) -> None:
        from Common.CommType import CMD_MAPPING_RULE_DOWN
        await self.SendPacket(CMD_MAPPING_RULE_DOWN)

    # =========================================================================
    # LogStatus
    # =========================================================================

    def _receive_log_info(self, status: AS_LOG_STATUS_T) -> None:
        """C++: ReceiveLogInfo(AS_LOG_STATUS_T*)"""
        from ProcNaServer.AsciiServerWorld import AsciiServerWorld

        self._log_status_map.pop(status.name, None)
        if status.status == LOG_ADD:
            import copy
            self._log_status_map[status.name] = copy.copy(status)

        AsciiServerWorld.m_WorldPtr.SendLogStatus(status)

    def GetLogStatusList(self, log_status_list: list) -> None:
        """C++: GetLogStatusList(LogStatusVector*)"""
        log_status_list.extend(self._log_status_map.values())

    # =========================================================================
    # 접근자
    # =========================================================================

    def IsHasCmdPortNeName(self, ne_name: str) -> bool:
        """C++: IsHasCmdPortNeName(char* NeName)"""
        return ne_name in self._has_cmd_port_ne_set

    def RemoveCmdNeList(self, connector_id: str) -> None:
        """C++: RemoveCmdNeList(string ConnectorId)"""
        logger.debug("Remove HasCmdPortNeListSet : %s(%s)",
                     connector_id, self.GetSessionName())
        self._has_cmd_port_ne_set.discard(connector_id)

    def GetRouterPortNo(self) -> int:
        """C++: GetRouterPortNo()"""
        return self._router_port_no


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack_struct(obj) -> bytes:
    """CommTypeList 구조체 → bytes. pack() 메서드가 있으면 사용."""
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''