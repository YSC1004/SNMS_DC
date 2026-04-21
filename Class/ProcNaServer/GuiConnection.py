"""
GuiConnection.py
C++ GuiConnection.h/.C → Python 변환

GUI 클라이언트 개별 소켓 연결 처리.
  - 세션 타입별 패킷 분기 (RuleEditor / StatusGui / CommandGui)
  - 초기화 시 Manager/Connector/Connection/Process/DataHandler 정보 일괄 전송
  - MMC 요청 처리 (AS_MMC_REQ / AS_MMC_REQ_OLD)
  - Rule Down / InfoChange / LogStatus 처리
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from Common.AsSocket import AsSocket                    # 가상함수 오버라이드
from Common.AsUtil import AsUtil
from Common.CommTypeList import (
    AS_LOG_STATUS_T, AS_ASCII_ERROR_MSG_T, AS_ASCII_ACK_T,
    AS_CMD_LOG_CONTROL_T, AS_MMC_REQUEST_T, AS_MMC_REQUEST_OLD_T,
    AS_MMC_PUBLISH_T, AS_MMC_RESULT_T, AS_GUI_INIT_INFO_T,
    AS_RULE_CHANGE_INFO_T, AS_CONNECTOR_DESC_CHANGE_INFO_T,
    AS_PROC_CONTROL_T, AS_SESSION_CONTROL_T,
    AS_MANAGER_INFO_T, AS_CONNECTOR_INFO_T, AS_CONNECTION_INFO_T,
    AS_CONNECTION_INFO_LIST_T, AS_DATA_HANDLER_INFO_T,
    AS_COMMAND_AUTHORITY_INFO_T, AS_SUB_PROC_INFO_T,
    AS_DB_SYNC_INFO_LIST_T, AS_DATA_HANDLER_INIT_T,
    AS_DATA_ROUTING_INIT_T, AS_SESSION_CFG_T, AS_SYSTEM_INFO_T,
)
from Common.CommType import (
    GUI_RULE_EDITOR, GUI_ASCII_CONFIG_INFO, GUI_ASCII_STATUS_INFO,
    GUI_COMMAND_INFO,
    CMD_PARSING_RULE_DOWN, CMD_PARSING_RULE_DOWN_ACK,
    CMD_MAPPING_RULE_DOWN, CMD_MAPPING_RULE_DOWN_ACK,
    CMD_COMMAND_RULE_DOWN, CMD_COMMAND_RULE_DOWN_ACK,
    CMD_SCHEDULER_RULE_DOWN, CMD_SCHEDULER_RULE_DOWN_ACK,
    CMD_LOG_STATUS_CHANGE, CMD_PARSING_RULE_CHANGE,
    CMD_CONNECTOR_DESC_CHANGE,
    MANAGER_MODIFY, MANAGER_MODIFY_ACK,
    CONNECTOR_MODIFY, CONNECTOR_MODIFY_ACK,
    CONNECTION_MODIFY, CONNECTION_MODIFY_ACK,
    CONNECTION_LIST_MODIFY, CONNECTION_LIST_MODIFY_ACK,
    DATAHANDLER_MODIFY, DATAHANDLER_MODIFY_ACK,
    COMMAND_AUTHORITY_MODIFY, COMMAND_AUTHORITY_MODIFY_ACK,
    SUB_PROC_MODIFY, SUB_PROC_MODIFY_ACK,
    PROC_CONTROL, SESSION_CONTROL,
    AS_MMC_REQ, AS_MMC_REQ_OLD, AS_MMC_RES,
    AS_DB_SYNC_INFO_REQ, AS_DB_SYNC_INFO_LIST, AS_DB_SYNC_INFO_REQ_ACK,
    AS_DATA_HANDLER_INIT, AS_DATA_ROUTING_INIT, AS_SESSION_CFG,
    AS_MANAGER_INFO, AS_CONNECTOR_INFO, AS_CONNECTION_INFO,
    AS_PROCESS_INFO, AS_DATA_HANDLER_INFO, AS_COMMAND_AUTHORITY_INFO,
    AS_SYSTEM_INFO, AS_SUB_PROC_INFO,
    INIT_INFO_START, INIT_INFO_END,
    ASCII_ERROR_MSG, AS_LOG_INFO,
    GET_LOG_INFO,
    NO_RESPONSE, IMMEDIATE, R_ERROR,
)
from ProcNaServer.AsciiServerType import (
    SESSION_TYPE_GUI,
)

if TYPE_CHECKING:
    from ProcNaServer.GuiConnMgr import GuiConnMgr

logger = logging.getLogger(__name__)

# INIT_INFO 마스크 상수 (C++ #define)
INIT_INFO_MANAGER_MASK           = 0x00000001
INIT_INFO_PROCESS_MASK           = 0x00000002
INIT_INFO_DATAHANDLER_MASK       = 0x00000004
INIT_INFO_COMMAND_AUTHORITY_MASK = 0x00000008


class GuiConnection(AsSocket):
    """
    C++ GuiConnection (AsSocket 상속) 대응.

    AsSocket 가상 메서드 오버라이드:
      receive_packet()              ← C++ ReceivePacket()
      close_socket()                ← C++ CloseSocket()
      session_identify_callback()   ← C++ SessionIdentify()
    """

    def __init__(self, gui_conn_mgr: "GuiConnMgr") -> None:
        super().__init__()
        self._gui_conn_mgr: "GuiConnMgr" = gui_conn_mgr

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)"""
        if session_identify == GUI_RULE_EDITOR:
            asyncio.ensure_future(self._rule_editor_req_process(packet))

        elif session_identify in (GUI_ASCII_CONFIG_INFO, GUI_ASCII_STATUS_INFO):
            asyncio.ensure_future(self._gw_status_gui_req_process(packet))

        elif session_identify == GUI_COMMAND_INFO:
            asyncio.ensure_future(self._gw_command_gui_req_process(packet))

        else:
            logger.debug("Not Identify Session : %d", session_identify)

    def close_socket(self, errno_val: int) -> None:
        """C++: virtual CloseSocket(int Errno)"""
        logger.debug("Gui Connection Broken(%s,%s)",
                     self.get_peer_ip(), self.GetSessionName())
        self._gui_conn_mgr.RemoveRequestConn(self)
        self._gui_conn_mgr.remove(self)             # ConnectionMgr.remove()

    def session_identify_callback(self, session_type: int,
                                   session_name: str = "") -> None:
        """
        C++: virtual SessionIdentify(int SessionType, string SessionName)
        세션 타입에 따라 초기 정보 일괄 전송.
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR

        MAINPTR().SessionCfg(self, SESSION_TYPE_GUI)
        logger.debug("Session Identify : Type(%s,%s)",
                     AsUtil.GetProcessTypeString(session_type), session_name)

        if session_type in (GUI_RULE_EDITOR,
                            GUI_ASCII_CONFIG_INFO,
                            GUI_ASCII_STATUS_INFO):
            asyncio.ensure_future(
                self._send_initial_info(session_type))

    # =========================================================================
    # 초기 정보 전송
    # =========================================================================

    async def _send_initial_info(self, session_type: int) -> None:
        """C++: SessionIdentify() 내부 초기화 블록 → async 분리."""
        if session_type == GUI_ASCII_STATUS_INFO:
            mask = (INIT_INFO_MANAGER_MASK | INIT_INFO_DATAHANDLER_MASK |
                    INIT_INFO_PROCESS_MASK | INIT_INFO_COMMAND_AUTHORITY_MASK)
            await self.SendInitInfo(INIT_INFO_START, mask)
            await self.SendAllManagerInfo()
            await self.SendAllProcStatusInfo()
            await self.SendAllDataHandlerInfo()
            await self.SendAllCommandAuthorityInfo()
            await self.SendAllEtcInfo()

        elif session_type == GUI_ASCII_CONFIG_INFO:
            mask = (INIT_INFO_MANAGER_MASK | INIT_INFO_COMMAND_AUTHORITY_MASK |
                    INIT_INFO_DATAHANDLER_MASK)
            await self.SendInitInfo(INIT_INFO_START, mask)
            await self.SendAllManagerInfo()
            await self.SendAllDataHandlerInfo()
            await self.SendAllCommandAuthorityInfo()

        await self.SendInitInfo(INIT_INFO_END, 0)

    # =========================================================================
    # 패킷 처리 내부 메서드
    # =========================================================================

    async def _rule_editor_req_process(self, packet) -> None:
        """C++: RuleEditorReqProcess(PACKET_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        if packet.MsgId == CMD_PARSING_RULE_DOWN:
            if not MAINPTR().GetParsingRuleDownStatus():
                await self.SendAck(CMD_PARSING_RULE_DOWN_ACK, 1, 1,
                                   "Rule Down Load is start")
                self._gui_conn_mgr.CmdParsingRuleDown(self)
            else:
                await self.SendAck(CMD_PARSING_RULE_DOWN_ACK, 1, 0,
                                   "Already Rule Down Load is start\n"
                                   "Please retry some time later")

    async def _gw_command_gui_req_process(self, packet) -> None:
        """C++: GwCommandGuiReqProcess(PACKET_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        logger.debug("Recv Request Cmd GUI : %d", packet.MsgId)

        if packet.MsgId == CMD_COMMAND_RULE_DOWN:
            if not MAINPTR().GetCommandRuleDownStatus():
                await self.SendAck(CMD_COMMAND_RULE_DOWN_ACK, 1, 1,
                                   "Command Rule Down Load is start")
                self._gui_conn_mgr.CmdCommandRuleDown(self)
            else:
                await self.SendAck(CMD_COMMAND_RULE_DOWN_ACK, 1, 0,
                                   "Already Command Rule Down Load is start")

        elif packet.MsgId == CMD_SCHEDULER_RULE_DOWN:
            if not MAINPTR().GetSchedulerRuleDownStatus():
                await self.SendAck(CMD_SCHEDULER_RULE_DOWN_ACK, 1, 1,
                                   "Scheduler Rule Down Load is start")
                self._gui_conn_mgr.CmdSchedulerRuleDonw(self)
            else:
                await self.SendAck(CMD_SCHEDULER_RULE_DOWN_ACK, 1, 0,
                                   "Already Scheduler Down Load is start")

        else:
            logger.debug("Unknown Cmd Gui Request : %d", packet.MsgId)

    async def _gw_status_gui_req_process(self, packet) -> None:
        """C++: GwStatusGuiReqProcess(PACKET_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        logger.debug("Recv Request Status GUI : %d", packet.MsgId)
        msg_id = packet.MsgId
        msg    = packet.Msg

        # ── InfoChange (CRUD) ─────────────────────────────────────────────
        _info_map = {
            MANAGER_MODIFY:           (AS_MANAGER_INFO_T,          MANAGER_MODIFY_ACK),
            CONNECTOR_MODIFY:         (AS_CONNECTOR_INFO_T,        CONNECTOR_MODIFY_ACK),
            CONNECTION_MODIFY:        (AS_CONNECTION_INFO_T,       CONNECTION_MODIFY_ACK),
            CONNECTION_LIST_MODIFY:   (AS_CONNECTION_INFO_LIST_T,  CONNECTION_LIST_MODIFY_ACK),
            DATAHANDLER_MODIFY:       (AS_DATA_HANDLER_INFO_T,     DATAHANDLER_MODIFY_ACK),
            COMMAND_AUTHORITY_MODIFY: (AS_COMMAND_AUTHORITY_INFO_T,COMMAND_AUTHORITY_MODIFY_ACK),
            SUB_PROC_MODIFY:          (AS_SUB_PROC_INFO_T,         SUB_PROC_MODIFY_ACK),
        }
        if msg_id in _info_map:
            _, ack_id = _info_map[msg_id]
            result_msg = [""]
            ret = MAINPTR().RecvInfoChange(msg, result_msg)
            await self.SendAck(ack_id, 0, 1 if ret else 0, result_msg[0])
            return

        # ── 기타 요청 ─────────────────────────────────────────────────────
        if msg_id == CMD_LOG_STATUS_CHANGE:
            await self._recv_cmd_log_status_change(msg)

        elif msg_id == PROC_CONTROL:
            MAINPTR().RecvProcessControl(msg)

        elif msg_id == SESSION_CONTROL:
            MAINPTR().RecvSessionControl(msg)

        elif msg_id == CMD_PARSING_RULE_DOWN:
            if not MAINPTR().GetParsingRuleDownStatus():
                await self.SendAck(CMD_PARSING_RULE_DOWN_ACK, 1, 1,
                                   "Rule Down Load is start")
                self._gui_conn_mgr.CmdParsingRuleDown(self)
            else:
                await self.SendAck(CMD_PARSING_RULE_DOWN_ACK, 1, 0,
                                   "Already Rule Down Load is start")

        elif msg_id == CMD_MAPPING_RULE_DOWN:
            if not MAINPTR().GetMappingRuleDownStatus():
                await self.SendAck(CMD_MAPPING_RULE_DOWN_ACK, 1, 1,
                                   "Mapping Rule Down Load is start")
                self._gui_conn_mgr.CmdMappingRuleDown(self)
            else:
                await self.SendAck(CMD_MAPPING_RULE_DOWN_ACK, 1, 0,
                                   "Already Mapping Rule Down Load is start")

        elif msg_id == CMD_PARSING_RULE_CHANGE:
            MAINPTR().ParserRuleChange(msg)

        elif msg_id == CMD_CONNECTOR_DESC_CHANGE:
            MAINPTR().ConnectorDescChange(msg)

        elif msg_id == AS_MMC_REQ:
            await self._receive_mmc_req(msg)

        elif msg_id == AS_MMC_REQ_OLD:
            new_req = AS_MMC_REQUEST_T()
            AsUtil.ConvertMMC_OldToNew(msg, new_req)
            await self._receive_mmc_req(new_req)

        elif msg_id == AS_DB_SYNC_INFO_REQ:
            await self._receive_db_sync_info_req()

        elif msg_id == AS_DATA_HANDLER_INIT:
            MAINPTR().RecvInitInfo(msg)

        elif msg_id == AS_DATA_ROUTING_INIT:
            MAINPTR().RecvInitInfo(msg)

        elif msg_id == AS_SESSION_CFG:
            MAINPTR().RecvSessionCfg(msg)

        else:
            logger.debug("Unknown Status Gui Request : %d", msg_id)

    # =========================================================================
    # 초기 데이터 일괄 전송
    # =========================================================================

    async def SendAllManagerInfo(self) -> None:
        """C++: SendAllManagerInfo()"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        info_map = MAINPTR().GetManagerInfoMap()
        for mgr_info in info_map.values():
            if not await self.SendPacket(
                    AS_MANAGER_INFO, _pack(mgr_info.m_ManagerInfo),
                    _size(mgr_info.m_ManagerInfo)):
                return
            for con_info in mgr_info.m_ConnectorInfoMap.values():
                if not await self.SendPacket(
                        AS_CONNECTOR_INFO, _pack(con_info.m_ConnectorInfo),
                        _size(con_info.m_ConnectorInfo)):
                    return
                for conn in con_info.m_ConnectionInfoList:
                    if not await self.SendPacket(
                            AS_CONNECTION_INFO, _pack(conn), _size(conn)):
                        return

        sub_info_map = MAINPTR().GetSubProcInfoMap()
        for sub_info in sub_info_map.values():
            if not await self.SendPacket(
                    AS_SUB_PROC_INFO, _pack(sub_info), _size(sub_info)):
                return

    async def SendAllProcStatusInfo(self) -> None:
        """C++: SendAllProcStatusInfo()"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        proc_map = MAINPTR().GetProcStatusMap()
        for info_map in proc_map.values():
            for proc_info in info_map.values():
                if not await self.SendPacket(
                        AS_PROCESS_INFO, _pack(proc_info), _size(proc_info)):
                    return

    async def SendAllDataHandlerInfo(self) -> None:
        """C++: SendAllDataHandlerInfo()"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        for dh_info in MAINPTR().GetDataHandlerInfoMap().values():
            if not await self.SendPacket(
                    AS_DATA_HANDLER_INFO, _pack(dh_info), _size(dh_info)):
                return

    async def SendAllCommandAuthorityInfo(self) -> None:
        """C++: SendAllCommandAuthorityInfo()"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        for ca_info in MAINPTR().GetCommandAuthorityInfoMap().values():
            if not await self.SendPacket(
                    AS_COMMAND_AUTHORITY_INFO, _pack(ca_info), _size(ca_info)):
                return

    async def SendAllEtcInfo(self) -> None:
        """C++: SendAllEtcInfo() — SystemInfo + SessionCfg 전송."""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        sys_info_map = {}
        MAINPTR().GetAsSystemInfoMap(sys_info_map)
        for sys_info in sys_info_map.values():
            if not await self.SendPacket(
                    AS_SYSTEM_INFO, _pack(sys_info), _size(sys_info)):
                return

        session_cfg_map = {}
        MAINPTR().GetAsSessionCfgMap(session_cfg_map)
        for cfg in session_cfg_map.values():
            if not await self.SendPacket(
                    AS_SESSION_CFG, _pack(cfg), _size(cfg)):
                return

    async def SendAllLogStatus(self) -> None:
        """C++: SendAllLogStatus()"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        log_list = []
        MAINPTR().GetLogStatusList(log_list)
        for status in log_list:
            if not await self.SendLogStatus(status):
                return
        logger.debug("Send All Log Status To Gui")

    async def SendInitInfo(self, msg_id: int, mask: int) -> None:
        """C++: SendInitInfo(int MsgId, unsigned int Mask)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        init_info = AS_GUI_INIT_INFO_T()
        init_info.Count = 0

        if mask & INIT_INFO_MANAGER_MASK:
            info_map = MAINPTR().GetManagerInfoMap()
            init_info.Count += len(info_map)
            for mgr_info in info_map.values():
                init_info.Count += len(mgr_info.m_ConnectorInfoMap)
                for con_info in mgr_info.m_ConnectorInfoMap.values():
                    init_info.Count += len(con_info.m_ConnectionInfoList)
            init_info.Count += len(MAINPTR().GetSubProcInfoMap())

        if mask & INIT_INFO_PROCESS_MASK:
            logger.debug("Process Info Counting")
            for info_map in MAINPTR().GetProcStatusMap().values():
                init_info.Count += len(info_map)

        if mask & INIT_INFO_DATAHANDLER_MASK:
            init_info.Count += len(MAINPTR().GetDataHandlerInfoMap())

        if mask & INIT_INFO_COMMAND_AUTHORITY_MASK:
            init_info.Count += len(MAINPTR().GetCommandAuthorityInfoMap())

        if self.GetSessionType() == GUI_ASCII_STATUS_INFO:
            sys_map = {}
            MAINPTR().GetAsSystemInfoMap(sys_map)
            cfg_map = {}
            MAINPTR().GetAsSessionCfgMap(cfg_map)
            init_info.Count += len(sys_map) + len(cfg_map)

        await self.SendPacket(msg_id, _pack(init_info), _size(init_info))

    # =========================================================================
    # LogStatus / AsciiError
    # =========================================================================

    async def SendLogStatus(self, status: AS_LOG_STATUS_T) -> bool:
        """C++: SendLogStatus(const AS_LOG_STATUS_T*)"""
        return await self.SendPacket(AS_LOG_INFO, _pack(status), _size(status))

    async def SendAsciiError(self, err_msg: AS_ASCII_ERROR_MSG_T) -> bool:
        """
        C++: SendAsciiError() → SendNonBlockPacket (비블로킹)
        Python에서는 asyncio SendPacket 으로 대응.
        """
        return await self.SendPacket(
            ASCII_ERROR_MSG, _pack(err_msg), _size(err_msg))

    # =========================================================================
    # CmdLogStatusChange
    # =========================================================================

    async def _recv_cmd_log_status_change(self,
                                           log_ctl: AS_CMD_LOG_CONTROL_T) -> None:
        """C++: ReceiveCmdLogStatusChange(AS_CMD_LOG_CONTROL_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        logger.debug("ReceiveCmdLogStatusChange")
        if log_ctl.Type == GET_LOG_INFO:
            await self.SendAllLogStatus()
        else:
            MAINPTR().ReceiveCmdLogStatusChange(log_ctl)

    # =========================================================================
    # MMC 요청
    # =========================================================================

    async def _receive_mmc_req(self, mmc_req: AS_MMC_REQUEST_T) -> None:
        """C++: ReceiveMMCReq(AS_MMC_REQUEST_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        mmc_com = AS_MMC_PUBLISH_T()
        mmc_com.ne           = mmc_req.ne
        mmc_com.mmc          = mmc_req.mmc
        mmc_com.responseMode = NO_RESPONSE
        mmc_com.publishMode  = IMMEDIATE

        err_str = [""]
        ret = MAINPTR().SendMMCCommandFromStatusGui(mmc_com, err_str)

        if not ret:
            mmc_res = AS_MMC_RESULT_T()
            mmc_res.id         = 0
            mmc_res.resultMode = R_ERROR
            mmc_res.result     = err_str[0]
            await self.SendPacket(AS_MMC_RES, _pack(mmc_res), _size(mmc_res))

    # =========================================================================
    # DB Sync 정보 요청
    # =========================================================================

    async def _receive_db_sync_info_req(self) -> None:
        """C++: ReceiveDbSyncInfoReq()"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        info_list = MAINPTR().GetDbSyncInfo()
        if info_list:
            await self.SendPacket(
                AS_DB_SYNC_INFO_LIST, _pack(info_list), _size(info_list))
        else:
            await self.SendAck(AS_DB_SYNC_INFO_REQ_ACK, 1, 0,
                               "StandBy Server is't running")

    # =========================================================================
    # 소켓 오버플로 / 셧다운
    # =========================================================================

    def RecvShutDownInfo(self, info: str) -> None:
        """C++: RecvShutDownInfo(string Info)"""
        logger.error("Closed session enforced(may be blocked) : %s",
                     self.GetSessionName())

    def RecvOverFlowDataBufInfo(self, max_buf: int, cur_buf: int) -> None:
        """C++: RecvOverFlowDataBufInfo(int MaxBufSize, int CurBufSize)"""
        logger.error("Session may be blocked(MAX:%d byte, CUR:%d byte)[%s]",
                     max_buf, cur_buf, self.GetSessionName())
        # C++: ShutDown(m_FD) → writer 강제 종료
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''

def _size(obj) -> int:
    return len(_pack(obj))