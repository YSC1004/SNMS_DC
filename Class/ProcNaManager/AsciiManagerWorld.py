"""
AsciiManagerWorld.py
C++ AsciiManagerWorld.h/.C → Python 변환

ProcNaManager 최상위 애플리케이션 클래스.
  - procNaServer TCP 접속
  - Parser/Connector/Router/DataRouter/LogRouter Unix Domain 소켓 리스닝
  - MMC 발행 스레드 (MMCPublishManager)
  - Connector/Parser 프로세스 기동/관리
  - 룰 복사 (ParsingRuleCopy / MappingRuleCopy)
"""

import asyncio
import logging
import os
import subprocess
import sys
import threading
from typing import Optional, ClassVar, Dict, List
from datetime import datetime

import paramiko                                         # C++: frSshUtil (치트시트)

from Common.AsWorld import AsWorld
from Common.AsUtil import AsUtil
from Common.ChildProcessManager import ChildProcessManager
from Common.CommTypeList import (
    AS_MMC_PUBLISH_T, AS_MMC_RESULT_T, AS_PROC_CONTROL_T,
    AS_SESSION_CONTROL_T, AS_PROCESS_STATUS_T, AS_PORT_STATUS_INFO_T,
    AS_LOG_STATUS_T, AS_CMD_LOG_CONTROL_T, AS_RULE_CHANGE_INFO_T,
    AS_CMD_OPEN_PORT_T, AS_DATA_HANDLER_INFO_T, AS_DATA_ROUTING_INIT_T,
    AS_ASCII_ERROR_MSG_T, AS_ROUTER_PORT_INFO_T,
)
from Common.CommType import (
    ASCII_MANAGER, ASCII_CONNECTOR, ASCII_PARSER,
    ASCII_ROUTER, ASCII_LOG_ROUTER, ASCII_DATA_ROUTER,
    START, STOP, UPDATE_DATA, DELETE_DATA,
    RESPONSE, R_ERROR,
    ARG_NAME, ARG_SVR_IP, ARG_SVR_PORT, ARG_PORT_NO,
    ARG_LOG_CYCLE, ARG_LOG_HOUR,
    MANAGER_INIT_END, ROUTER_PORT_INFO, AS_SYSTEM_INFO,
    PARSER_CONNECT,
)
from Common.ProcConnectionMgr import ProcConnectionMgr
from Util.fr_arg_parser import ArgParser

from ProcNaManager.AsciiManagerType import (
    MmcPublishSet, MmcPublishSetQueue, MmcPublishSetQueueList,
)

logger = logging.getLogger(__name__)

# ── Unix 소켓 경로 상수 (C++ #define) ────────────────────────────────────────
MGR_UNIX_PARSER         = "MGR_PARSER_LISTEN"
MGR_UNIX_CONNECTOR      = "MGR_CONNECTOR_LISTEN"
MGR_UNIX_ROUTER         = "MGR_ROUTER_LISTEN"
MGR_UNIX_LOG_ROUTER     = "MGR_LOG_ROUTER_LISTEN"
MGR_UNIX_DATAROUTER     = "MGR_DATAROUTER_LISTEN"
UNIX_PARSER_LISTEN_PREFIX   = "/PARSER_LISTEN_"
UNIX_ROUTER_LISTEN_PREFIX   = "/ROUTER_LISTEN_"
UNIX_DATAROUTER_LISTEN_PREFIX = "/DATAROUTER_LISTEN_"

# ── 인자 상수 ─────────────────────────────────────────────────────────────────
ARG_MANAGER_SOCKET_PATH = "-mgrsocketpath"
ARG_RULEID              = "-ruleid"
ARG_DELAY_TIME          = "-delaytime"
ARG_CMD_IDENT_TYPE      = "-cmdidenttype"
ARG_CMD_RESPONSE_TYPE   = "-cmdresponsetype"

MAX_ERR_MSG_BUF = 4096


def MAINPTR() -> "AsciiManagerWorld":
    return AsciiManagerWorld.m_WorldPtr


# =============================================================================
class AsciiManagerWorld(AsWorld):
    """
    C++ AsciiManagerWorld (AsWorld 상속) 대응.
    RUNTIME_EXEC(AsciiManagerWorld) → main.py 에서 직접 호출.
    """

    m_WorldPtr: ClassVar[Optional["AsciiManagerWorld"]] = None

    def __init__(self) -> None:
        super().__init__()
        AsciiManagerWorld.m_WorldPtr = self

        self._msg_id:              int  = 0          # C++: unsigned int m_MsgId (감소)
        self._server_address:      str  = ""
        self._server_port:         int  = 0
        self._router_listen_port:  int  = 0
        self._log_router_listen_port: int = 0
        self._process_start_delay: int  = 0

        # 우선순위 큐 2개 (index 0: RESPONSE, index 1: 그 외)
        self._mmc_publish_queue_list: MmcPublishSetQueueList = MmcPublishSetQueueList()
        for i in range(2):
            self._mmc_publish_queue_list.append(MmcPublishSetQueue(i))

        # MMC 발행 스레드
        self._mmc_publish_thread: Optional[threading.Thread] = None
        self._thread_running:     bool = True

        # 프로세스/포트 관리
        self._process_info:        Dict[str, AS_PROC_CONTROL_T] = {}
        self._cmd_open_port_list:  List[AS_CMD_OPEN_PORT_T]     = []
        self._data_handler_info_map: Dict[str, AS_DATA_HANDLER_INFO_T] = {}
        self._child_proc_manager:  ChildProcessManager           = ChildProcessManager()

        # ConnMgr (지연 임포트로 순환참조 방지)
        self._server_connection    = None
        self._parser_conn_mgr      = None
        self._connector_conn_mgr   = None
        self._router_conn_mgr      = None
        self._data_router_conn_mgr = None
        self._log_router_conn_mgr  = None

    def __del__(self) -> None:
        self._thread_running = False
        if self._mmc_publish_thread and self._mmc_publish_thread.is_alive():
            self._mmc_publish_thread.join(timeout=2.0)

    # =========================================================================
    # AppStart
    # =========================================================================

    def AppStart(self, argc: int, argv: list) -> bool:
        """C++: AppStart(int Argc, char** Argv)"""
        if not self.InitConfig():
            logger.error("Env Init Error")
            return False

        if not self.AsciiSystemDirCheck():
            logger.error("AsciiSystemDirCheck ERROR")
            return False

        if argc != 7:
            print(f"[Usage] {argv[0]} "
                  f"-name Manager1 -svrip 172.21.90.90 -svrport 3434")
            return False

        args = ArgParser(argv)
        self._proc_name       = args.get_value(ARG_NAME)
        self._server_address  = args.get_value(ARG_SVR_IP)
        self._server_port     = int(args.get_value(ARG_SVR_PORT) or 0)

        self._router_listen_port = int(
            self.GetEnvValue(ASCII_MANAGER, "router_listen_port") or 0)
        self._log_router_listen_port = int(
            self.GetEnvValue(ASCII_MANAGER, "log_router_listen_port") or 0)

        self.SetLogFile(ASCII_MANAGER)
        self.SetSystemInfo(ASCII_MANAGER, self._proc_name)

        logger.debug("Netadapter Manager Start..............")

        if not self.ConfigValueCheck():
            return False

        if not self._init_manager(argc, argv):
            logger.debug("Manager Init Fail")
            return False

        logger.debug("Alive Check Interval : %d", self.GetProcAliveCheckTime())
        logger.debug("Alive Check Limit Cnt : %d", self.GetAliveCheckLimitCnt())
        return True

    # =========================================================================
    # InitManager
    # =========================================================================

    def _init_manager(self, argc: int, argv: list) -> bool:
        """C++: InitManager(int Argc, char** Argv)"""
        import socket
        from ProcNaManager.ServerConnection import ServerConnection
        from ProcNaManager.ParserConnMgr import ParserConnMgr
        from ProcNaManager.ConnectorConnMgr import ConnectorConnMgr
        from ProcNaManager.RouterConnMgr import RouterConnMgr
        from ProcNaManager.DataRouterConnMgr import DataRouterConnMgr
        from ProcNaManager.LogRouterConnMgr import LogRouterConnMgr

        self._server_connection    = ServerConnection(None)
        self._parser_conn_mgr      = ParserConnMgr()
        self._connector_conn_mgr   = ConnectorConnMgr()
        self._router_conn_mgr      = RouterConnMgr()
        self._data_router_conn_mgr = DataRouterConnMgr()
        self._log_router_conn_mgr  = LogRouterConnMgr()

        # procNaServer TCP 접속
        if not self._server_connection.Connect(
                self._server_address, self._server_port):
            logger.error("Server(%s, %d), Connect Error : %s",
                         self._server_address, self._server_port,
                         self._server_connection.GetObjErrMsg())
            return False

        # Unix Domain 소켓 Listen
        unix_listens = [
            (self._data_router_conn_mgr, MGR_UNIX_DATAROUTER, 200, "DataHandler"),
            (self._parser_conn_mgr,      MGR_UNIX_PARSER,     200, "Parser"),
            (self._connector_conn_mgr,   MGR_UNIX_CONNECTOR,  200, "Connect"),
            (self._router_conn_mgr,      MGR_UNIX_ROUTER,     10,  "Router"),
            (self._log_router_conn_mgr,  MGR_UNIX_LOG_ROUTER, 10,  "Log Router"),
        ]
        for mgr, unix_name, backlog, label in unix_listens:
            if not mgr.Create(socket.AF_UNIX):
                logger.error("%s Listener Create Error : %s",
                             label, mgr.GetObjErrMsg())
                return False
            path = f"{self.GetUnixSocketDir()}/{unix_name}"
            if not mgr.Listen(path, backlog):
                logger.error("Listen Error For %s : %s",
                             label, mgr.GetObjErrMsg())
                return False

        # ObjectName 설정
        self._parser_conn_mgr.SetObjectName("ParserConnListener")
        self._connector_conn_mgr.SetObjectName("ConnectorConnListener")
        self._router_conn_mgr.SetObjectName("RouterConnListener")
        self._data_router_conn_mgr.SetObjectName("DataRouterConnListener")
        self._log_router_conn_mgr.SetObjectName("LogRouterConnListener")

        # Router / LogRouter 프로세스 기동
        self.StartProc(ASCII_ROUTER, "Router")
        self.StartProc(ASCII_LOG_ROUTER, "LogRouter")

        # MMC 발행 스레드
        self._mmc_publish_thread = threading.Thread(
            target=self._mmc_publish_manager,
            name="MMCPublishManager",
            daemon=True,
        )
        self._mmc_publish_thread.start()
        logger.info("Thread Create Success For MMCPublish Management")

        # 세션 식별 → Manager 초기화 완료 통보
        asyncio.ensure_future(
            self._server_connection.SetSessionIdentify(
                ASCII_MANAGER, self._proc_name,
                self.GetProcAliveCheckTime()))

        self.ParsingRuleCopy()
        self.MappingRuleCopy()

        asyncio.ensure_future(
            self._server_connection.SendAck(MANAGER_INIT_END, 1))

        # Router 포트 번호 전송
        router_port = AS_ROUTER_PORT_INFO_T()
        router_port.RouterPortNo = self._router_listen_port
        asyncio.ensure_future(
            self._server_connection.SendPacket(
                ROUTER_PORT_INFO, _pack(router_port), _size(router_port)))

        asyncio.ensure_future(
            self._server_connection.SendPacket(
                AS_SYSTEM_INFO, _pack(self._system_info),
                _size(self._system_info)))

        self.SetLogStatus(ASCII_MANAGER, self._proc_name)

        # 자신의 프로세스 상태 등록
        proc_info = AS_PROCESS_STATUS_T()
        ProcConnectionMgr.get_process_info_by_pid(os.getpid(), proc_info)
        proc_info.ProcessId   = self._proc_name
        proc_info.Status      = START
        proc_info.ProcessType = ASCII_MANAGER
        self.SendProcessInfo(proc_info)

        sock_mgr_port = int(
            self.GetEnvValue(ASCII_MANAGER, "sock_mgr_listen_port") or 0)
        if sock_mgr_port > 3000:
            asyncio.ensure_future(
                self.EnableSockMgrSession("ManagerSockMgrListener",
                                          sock_mgr_port))
        return True

    # =========================================================================
    # PID 관리
    # =========================================================================

    def AddPid(self, pid: int) -> None:
        self._child_proc_manager.add_pid(pid)       # ChildProcessManager.add_pid()

    def RemovePid(self, pid: int) -> None:
        self._child_proc_manager.remove_pid(pid)    # ChildProcessManager.remove_pid()

    # =========================================================================
    # 에러 전송
    # =========================================================================

    def SendAsciiError(self, priority_or_msg, fmt: str = "", *args) -> None:
        """
        C++ 오버로드 2종 통합:
          SendAsciiError(AS_ASCII_ERROR_MSG_T*)
          SendAsciiError(int Priority, const char* format, ...)
        """
        if isinstance(priority_or_msg, AS_ASCII_ERROR_MSG_T):
            err = priority_or_msg
            logger.debug(err.ErrMsg)
            asyncio.ensure_future(
                self._server_connection.SendAsciiError(err))
        else:
            msg = fmt % args if args else fmt
            err = AS_ASCII_ERROR_MSG_T()
            err.Priority    = priority_or_msg
            err.ProcessType = ASCII_MANAGER
            err.ErrMsg      = msg
            err.ProcessId   = self.GetProcName()
            self.SendAsciiError(err)

    # =========================================================================
    # StartProc
    # =========================================================================

    def StartProc(self, proc_type_or_ctl, name: str = "",
                  rule_id: str = "", mmc_ident_type: int = 1,
                  cmd_response_type: int = 0, delay_time: int = 0,
                  log_cycle: int = 0) -> None:
        """
        C++ 오버로드 2종 통합:
          StartProc(AS_PROC_CONTROL_T*)
          StartProc(int ProcType, string Name, ...)
        """
        if isinstance(proc_type_or_ctl, AS_PROC_CONTROL_T):
            ctl = proc_type_or_ctl
            logger.debug("Delay Time : %d", ctl.DelayTime)
            delay = ctl.DelayTime
            ctl.DelayTime = 0
            self._process_info[ctl.ProcessId] = ctl
            self.StartProc(ASCII_PARSER, ctl.ProcessId, ctl.RuleId,
                           ctl.MmcIdentType, ctl.CmdResponseType,
                           delay, ctl.LogCycle)
            return

        proc_type = proc_type_or_ctl
        args = [
            self.GetProcPosition() + self.GetProcessName(proc_type),
            self.GetProcessName(proc_type),
            ARG_NAME,
        ]

        if proc_type == ASCII_PARSER:
            enc_name = self._parser_id_encode(name)
            args += [enc_name, ARG_MANAGER_SOCKET_PATH,
                     f"{self.GetUnixSocketDir()}/{MGR_UNIX_PARSER}",
                     ARG_RULEID, rule_id,
                     ARG_DELAY_TIME, str(delay_time),
                     ARG_CMD_IDENT_TYPE, str(mmc_ident_type)]
            pid = self._parser_conn_mgr.start_proc(enc_name, args)

        elif proc_type == ASCII_CONNECTOR:
            enc_name = self._connector_id_encode(name)
            logger.debug("Connector Name : %s", enc_name)
            args += [enc_name, ARG_MANAGER_SOCKET_PATH,
                     f"{self.GetUnixSocketDir()}/{MGR_UNIX_CONNECTOR}",
                     ARG_CMD_RESPONSE_TYPE, str(cmd_response_type)]
            if log_cycle == 1:
                args += [ARG_LOG_CYCLE, ARG_LOG_HOUR]
            pid = self._connector_conn_mgr.start_proc(enc_name, args)

        elif proc_type == ASCII_ROUTER:
            args += [name, ARG_MANAGER_SOCKET_PATH,
                     f"{self.GetUnixSocketDir()}/{MGR_UNIX_ROUTER}",
                     "-portno", str(self._router_listen_port),
                     "-socketpathforparser",
                     self.GetRouterListenSocketPath(name)]
            pid = self._router_conn_mgr.start_proc(name, args)

        elif proc_type == ASCII_LOG_ROUTER:
            args += [name, ARG_MANAGER_SOCKET_PATH,
                     f"{self.GetUnixSocketDir()}/{MGR_UNIX_LOG_ROUTER}",
                     ARG_PORT_NO, str(self._log_router_listen_port)]
            pid = self._log_router_conn_mgr.start_proc(name, args)

        elif proc_type == ASCII_DATA_ROUTER:
            args += [name, ARG_MANAGER_SOCKET_PATH,
                     f"{self.GetUnixSocketDir()}/{MGR_UNIX_DATAROUTER}"]
            pid = self._data_router_conn_mgr.start_proc(name, args)

        else:
            logger.error("Unknown Process Type......%d", proc_type)
            return

        if pid == -1:
            self.SendAsciiError(
                1, "Forking the process in %s(%s) fails.",
                AsUtil.GetProcessTypeString(ASCII_MANAGER),
                self.GetProcName())
        else:
            self.AddPid(pid)
            logger.debug("Process Execute : %s(%s, pid:%d)",
                         AsUtil.GetProcessTypeString(proc_type), name, pid)

    # =========================================================================
    # MMC 발행 스레드
    # =========================================================================

    def _mmc_publish_manager(self) -> None:
        """C++: MMCPublishManager(void* Arg) — pthread → threading.Thread"""
        from Common.AsUtil import AsUtil as _AsUtil

        while self._thread_running:
            q_list = self._mmc_publish_queue_list
            queue_empty_cnt = len(q_list)

            for mmcSetQueue in q_list:
                mmc_set = mmcSetQueue.GetMmcPublishSet()
                if mmc_set is None:
                    queue_empty_cnt -= 1
                    continue

                logger.debug("MmcPublish Queue Send Command : ne(%s), mmc(%s)",
                             mmc_set.m_MmcPublish.ne,
                             mmc_set.m_MmcPublish.mmc)

                if self._connector_conn_mgr.SendMMCCommand(
                        mmc_set.m_ConnectorId, mmc_set.m_MmcPublish):
                    logger.debug("MMC(%s) Send Success(%s)",
                                 mmc_set.m_MmcPublish.mmc,
                                 mmc_set.m_MmcPublish.ne)

            if queue_empty_cnt == 0:
                _AsUtil.AsSleep(70000)              # C++: AsUtil::AsSleep(70000)

    def InsertMMCPublishSet(self, mmc_com_set: MmcPublishSet) -> None:
        """C++: InsertMMCPublishSet(MmcPublishSet*)"""
        if mmc_com_set.m_MmcPublish.responseMode == RESPONSE:
            logger.debug("Mmcpublish push back to list1 ne(%s), mmc(%s)",
                         mmc_com_set.m_MmcPublish.ne,
                         mmc_com_set.m_MmcPublish.mmc)
            self._mmc_publish_queue_list[0].InsertMMCPublishSet(mmc_com_set)
        else:
            logger.debug("Mmcpublish push back to list2 ne(%s), mmc(%s)",
                         mmc_com_set.m_MmcPublish.ne,
                         mmc_com_set.m_MmcPublish.mmc)
            self._mmc_publish_queue_list[1].InsertMMCPublishSet(mmc_com_set)

    # =========================================================================
    # MMC 명령 전송
    # =========================================================================

    def SendMMCCommand(self, mmc_com: AS_MMC_PUBLISH_T) -> None:
        """C++: SendMMCCommand(AS_MMC_PUBLISH_T*)"""
        # 특정 MMC 명령은 불허 (한글 메시지 → 영문 대체)
        blocked_prefixes = (
            "DIS-MS:", "DIS-3GMS:", "RTRV-MS-INF:", "DIS-MS MDN",
            "DIS-3G-MS MSISDN", "DIS-MSUB:", "DIS-MS-INFO:",
            "DIS-NSN=", "DIS-MS-INF:",
        )
        if any(mmc_com.mmc.startswith(p) for p in blocked_prefixes):
            res = AS_MMC_RESULT_T()
            res.id         = mmc_com.id
            res.resultMode = R_ERROR
            res.result     = "This command is not allowed for subscriber inquiry."
            self.SendCommandResponse(res)
            return

        result = False
        for port in self._cmd_open_port_list:
            if port.EquipId == mmc_com.ne:
                result = True
                if port.CommandPortFlag == 1:
                    import copy
                    mmcCom = copy.copy(mmc_com)
                    self.InsertMMCPublishSet(
                        MmcPublishSet(mmcCom, port.ConnectorId))
                    return

        res = AS_MMC_RESULT_T()
        res.id         = mmc_com.id
        res.resultMode = R_ERROR
        if result:
            res.result = f"The NE({mmc_com.ne}) is found, but has no command port."
        else:
            res.result = f"The NE({mmc_com.ne}) is not found."
        self.SendCommandResponse(res)

    def SendCommandResponse(self, mmc_result: AS_MMC_RESULT_T) -> None:
        asyncio.ensure_future(
            self._server_connection.SendCommandResponse(mmc_result))

    # =========================================================================
    # 프로세스 상태/포트 정보 전송
    # =========================================================================

    def SendProcessInfo(self, proc_info: AS_PROCESS_STATUS_T) -> None:
        proc_info.ManagerId = self._proc_name
        asyncio.ensure_future(
            self._server_connection.SendProcessInfo(proc_info))

    def SendProcessInfoList(self) -> None:
        """C++: SendProcessInfoList()"""
        proc_list = []
        for mgr in (self._parser_conn_mgr, self._connector_conn_mgr,
                    self._router_conn_mgr, self._data_router_conn_mgr):
            mgr.get_process_info_list(proc_list)
        for p in proc_list:
            p.ManagerId = self._proc_name
        asyncio.ensure_future(
            self._server_connection.SendProcessInfoList(proc_list))

    def SendPortInfo(self, status_info: AS_PORT_STATUS_INFO_T) -> None:
        status_info.ManagerId  = self._proc_name
        status_info.ConnectorId = self._connector_id_decode(
            status_info.ConnectorId)
        asyncio.ensure_future(
            self._server_connection.SendPortInfo(status_info))

    def SendLogStatus(self, status: AS_LOG_STATUS_T) -> None:
        log = AS_LOG_STATUS_T()
        log.name   = status.name
        log.status = status.status
        log.logs   = f"{self.GetProcName()},{status.logs}"
        asyncio.ensure_future(
            self._server_connection.SendLogStatus(log))

    # =========================================================================
    # 프로세스 상태 관리
    # =========================================================================

    def SetParserProcStatus(self, session_name: str) -> bool:
        """C++: SetParserProcStatus(string SessionName)"""
        name = self._parser_id_decode(session_name)
        info = self._process_info.get(name)
        if info is None:
            logger.error("Not Exist SessionName : %s", session_name)
            return False

        info.ParserStatus = True
        if info.ConnectorStatus:
            open_port = AS_CMD_OPEN_PORT_T()
            open_port.ProtocolType = PARSER_CONNECT
            enc_session = self._connector_id_encode(
                self._parser_id_decode(session_name))
            open_port.ConnectorId = enc_session
            open_port.PortPath    = self.GetParserListenSocketPath(enc_session)
            self._connector_conn_mgr.SendCmdOpenInfo(open_port)
        else:
            self.StartProc(
                ASCII_CONNECTOR,
                self._connector_id_decode(session_name),
                info.RuleId, info.MmcIdentType,
                info.CmdResponseType, 0, info.LogCycle)
        return True

    def SetConnectorProcStatus(self, session_name: str) -> bool:
        """C++: SetConnectorProcStatus(string SessionName)"""
        name = self._connector_id_decode(session_name)
        info = self._process_info.get(name)
        if info is None:
            logger.error("Not Exist SessionName : %s", session_name)
            return False

        info.ConnectorStatus = True
        if info.ParserStatus:
            open_port = AS_CMD_OPEN_PORT_T()
            open_port.ProtocolType = PARSER_CONNECT
            open_port.ConnectorId  = session_name
            open_port.PortPath     = self.GetParserListenSocketPath(session_name)
            self._connector_conn_mgr.SendCmdOpenInfo(open_port)

        asyncio.ensure_future(
            self._server_connection.ConnectorPortInfoRequest(
                self._connector_id_decode(session_name)))
        return True

    # =========================================================================
    # ProcessDead
    # =========================================================================

    def ProcessDead(self, process_type: int,
                    process_name: str, pid: int) -> None:
        """C++: ProcessDead(int ProcessType, string ProcessName, int Pid)"""
        self.SendAsciiError(
            1, "The %s(%s) is killed abnormal.",
            AsUtil.GetProcessTypeString(process_type), process_name)

        # core 파일 이름 변경
        cmd = f"mv ~/core ~/core_{pid}_{process_name}"
        logger.debug(cmd)
        subprocess.call(cmd, shell=True)

        self.RemovePid(pid)

        if process_type in (ASCII_CONNECTOR, ASCII_PARSER):
            name = self._connector_id_decode(process_name)
            info = self._process_info.get(name)
            if info is None:
                logger.error("Can't Find Process Info")
                return

            if process_type == ASCII_CONNECTOR:
                self._cmd_open_port_list = [
                    p for p in self._cmd_open_port_list
                    if p.ConnectorId != name
                ]
                info.ConnectorStatus = False
            else:
                info.ParserStatus = False

            self.StartProc(process_type, info.ProcessId, info.RuleId,
                           info.MmcIdentType, info.CmdResponseType,
                           0, info.LogCycle)

        elif process_type == ASCII_ROUTER:
            self.StartProc(ASCII_ROUTER, "Router")

        elif process_type == ASCII_LOG_ROUTER:
            self.StartProc(ASCII_LOG_ROUTER, "LogRouter")

        elif process_type == ASCII_DATA_ROUTER:
            info = self._data_handler_info_map.get(process_name)
            if info is None:
                logger.error("Can't Find DataHandler Info : %s", process_name)
                return
            if info.SettingStatus == START:
                self.StartProc(ASCII_DATA_ROUTER, info.DataHandlerId)
        else:
            logger.error("Unknown ProcessType : %d", process_type)

    # =========================================================================
    # RecvProcessControl / RecvSessionControl
    # =========================================================================

    def RecvProcessControl(self, proc_ctl: AS_PROC_CONTROL_T) -> None:
        """C++: RecvProcessControl(AS_PROC_CONTROL_T*)"""
        logger.debug("Receive Process Control ProcessType:%s ManagerId:%s "
                     "ProcessId:%s Status:%s",
                     AsUtil.GetProcessTypeString(proc_ctl.ProcessType),
                     proc_ctl.ManagerId, proc_ctl.ProcessId,
                     AsUtil.GetStatusString(proc_ctl.Status))

        if proc_ctl.ProcessType in (ASCII_PARSER, ASCII_CONNECTOR):
            if proc_ctl.Status == START:
                if proc_ctl.ProcessId in self._process_info:
                    self.SendAsciiError(
                        1, "The process(%s) has already been being executed.",
                        proc_ctl.ProcessId)
                    return
                self.StartProc(proc_ctl)

            elif proc_ctl.Status == STOP:
                if proc_ctl.ProcessId not in self._process_info:
                    self.SendAsciiError(
                        1, "The process(%s) has not been executed.",
                        proc_ctl.ProcessId)
                    return
                del self._process_info[proc_ctl.ProcessId]
                self._cmd_open_port_list = [
                    p for p in self._cmd_open_port_list
                    if p.ConnectorId != proc_ctl.ProcessId
                ]
                self._parser_conn_mgr.StopProcess(
                    self._parser_id_encode(proc_ctl.ProcessId))
                self._connector_conn_mgr.StopProcess(
                    self._connector_id_encode(proc_ctl.ProcessId))
        else:
            logger.debug("Unknown ProcessType : %d", proc_ctl.ProcessType)

    def RecvSessionControl(self, session_ctl: AS_SESSION_CONTROL_T) -> None:
        """C++: RecvSessionControl(AS_SESSION_CONTROL_T*)"""
        logger.debug("Receive Session Control ManagerId:%s ConnectorId:%s "
                     "Sequence:%d Status:%s",
                     session_ctl.ManagerId, session_ctl.ConnectorId,
                     session_ctl.Sequence,
                     AsUtil.GetStatusString(session_ctl.Status))

        if session_ctl.Status == STOP:
            session_ctl.ConnectorId = self._connector_id_encode(
                session_ctl.ConnectorId)
            self._cmd_open_port_list = [
                p for p in self._cmd_open_port_list
                if p.Sequence != session_ctl.Sequence
            ]
            asyncio.ensure_future(
                self._connector_conn_mgr.SendSessionControl(session_ctl))
        else:
            logger.error("Not allow Session Control Type....")

    # =========================================================================
    # 룰 다운 처리
    # =========================================================================

    def RecvCmdParsingRuleDown(self) -> None:
        logger.debug("Receive Cmd Rule Down")
        if self.ParsingRuleCopy():
            asyncio.ensure_future(self._parser_conn_mgr.SendCmdRuleDown())

    def RecvCmdMappingRuleDown(self) -> None:
        logger.debug("Receive MappingCmd Rule Down")
        if self.MappingRuleCopy():
            asyncio.ensure_future(
                self._parser_conn_mgr.SendCmdMappingRuleDown())

    def ParserRuleChange(self, change_info: AS_RULE_CHANGE_INFO_T) -> None:
        info = self._process_info.get(change_info.ProcessId)
        if info is None:
            logger.error("Can't Find Process Info")
            return
        info.RuleId       = change_info.RuleId
        info.MmcIdentType = change_info.MmcIdentType
        change_info.ProcessId = self._parser_id_encode(change_info.ProcessId)
        asyncio.ensure_future(
            self._parser_conn_mgr.ParserRuleChange(change_info))

    # =========================================================================
    # 룰 복사
    # =========================================================================

    def ParsingRuleCopy(self) -> bool:
        """C++: ParsingRuleCopy() — RuleCopy 외부 명령 실행."""
        cmd = "~/NAA/Bin/RuleCopy -name RuleCopy -type 0"
        return self._run_rule_copy(cmd, "PARSING RULE DOWN")

    def MappingRuleCopy(self) -> bool:
        """C++: MappingRuleCopy() — RuleCopy 외부 명령 실행."""
        cmd = "~/NAA/Bin/RuleCopy -name RuleCopy -type 1"
        return self._run_rule_copy(cmd, "Mapping Rule Copy")

    def _run_rule_copy(self, cmd: str, label: str) -> bool:
        logger.debug("%s : %s", label, cmd)
        for retry in range(2):
            ret = subprocess.call(cmd, shell=True)
            logger.debug("%s Result : %d", label, ret)
            if ret != -1:
                logger.debug("%s Success", label)
                return True
            logger.error("%s Fail", label)
        logger.error("%s RETRY FAIL", label)
        return True                                 # C++ 원본: 항상 true 반환

    # =========================================================================
    # SendCmdOpenInfo
    # =========================================================================

    def SendCmdOpenInfo(self, port_info: AS_CMD_OPEN_PORT_T) -> None:
        logger.debug("Receive CmdOpenInfo")
        AsUtil.CmdOpenPortDisplay(port_info)
        port_info.ConnectorId = self._connector_id_encode(
            port_info.ConnectorId)
        if self._connector_conn_mgr.SendCmdOpenInfo(port_info):
            self._cmd_open_port_list.append(port_info)

    # =========================================================================
    # DataHandler 관련
    # =========================================================================

    def RecvDataHandlerInfo(self, info: AS_DATA_HANDLER_INFO_T) -> None:
        """C++: RecvDataHandlerInfo(AS_DATA_HANDLER_INFO_T*)"""
        import copy
        logger.debug("Recv DataHandler Info DataHandlerId:%s "
                     "RequestStatus:%s SettingStatus:%s",
                     info.DataHandlerId,
                     AsUtil.GetRequestStatusString(info.RequestStatus),
                     AsUtil.GetStatusString(info.SettingStatus))

        if info.RequestStatus == "UPDATE_DATA":
            self._data_handler_info_map.pop(info.OldDataHandlerId, None)
            self._data_handler_info_map[info.DataHandlerId] = copy.copy(info)
        else:
            existing = self._data_handler_info_map.get(info.DataHandlerId)
            if existing is None:
                existing = copy.copy(info)
                self._data_handler_info_map[info.DataHandlerId] = existing
            else:
                existing.__dict__.update(info.__dict__)

            if existing.RequestStatus == "DELETE_DATA":
                del self._data_handler_info_map[info.DataHandlerId]
            elif info.SettingStatus == START:
                self.StartProc(ASCII_DATA_ROUTER, info.DataHandlerId)
            elif existing.SettingStatus == STOP:
                self._data_router_conn_mgr.StopProcess(info.DataHandlerId)

        asyncio.ensure_future(
            self._parser_conn_mgr.SendDataHandlerInfo(info))

    def RecvInitInfo(self, init_info: AS_DATA_ROUTING_INIT_T) -> None:
        logger.debug("Recv DataRouter Init Cmd DataRouter:%s Desc:%s",
                     init_info.DataHandlerId, init_info.Desc)
        self._data_router_conn_mgr.RecvInitInfo(init_info)

    def GetDataHandlerInfo(self, dh_id: str) -> Optional[AS_DATA_HANDLER_INFO_T]:
        return self._data_handler_info_map.get(dh_id)

    def GetDataHandlerInfoMap(self) -> dict:
        return self._data_handler_info_map

    # =========================================================================
    # 로그 상태 변경
    # =========================================================================

    def ReceiveCmdLogStatusChange(self,
                                   log_ctl: AS_CMD_LOG_CONTROL_T) -> None:
        dispatch = {
            ASCII_CONNECTOR:   (self._connector_conn_mgr,   log_ctl.ProcessId),
            ASCII_PARSER:      (self._parser_conn_mgr,      log_ctl.ProcessId),
            ASCII_DATA_ROUTER: (self._data_router_conn_mgr, log_ctl.ProcessId),
            ASCII_ROUTER:      (self._connector_conn_mgr,   log_ctl.ProcessId),
        }
        entry = dispatch.get(log_ctl.ProcessType)
        if entry:
            mgr, pid = entry
            mgr.send_cmd_log_status_change(log_ctl, pid)
        elif log_ctl.ProcessType == ASCII_MANAGER:
            pass                                    # C++ 원본 동일하게 처리 없음
        else:
            logger.debug("Unknown Log Control ProcessType : %d",
                         log_ctl.ProcessType)

    # =========================================================================
    # RouterStart
    # =========================================================================

    def RouterStart(self, router_name: str) -> None:
        asyncio.ensure_future(
            self._parser_conn_mgr.SendRouterConnInfo(router_name))

    # =========================================================================
    # 소켓 경로 헬퍼
    # =========================================================================

    def GetParserListenSocketPath(self, session_name: str) -> str:
        pos = session_name.find("_")
        name = session_name[pos + 1:] if pos != -1 else session_name
        return self.GetUnixSocketDir() + UNIX_PARSER_LISTEN_PREFIX + name

    def GetRouterListenSocketPath(self, session_name: str) -> str:
        return self.GetUnixSocketDir() + UNIX_ROUTER_LISTEN_PREFIX + session_name

    def GetDataRouterListenSocketPath(self, session_name: str) -> str:
        return (self.GetUnixSocketDir() +
                UNIX_DATAROUTER_LISTEN_PREFIX + session_name)

    def GetMsgId(self) -> int:
        self._msg_id -= 1
        return self._msg_id

    def GetAliveCheckLimitCnt(self) -> int:
        cnt = int(self.GetEnvValue("MANAGER", "alive_check_maxcount") or 0)
        return max(cnt, 5)

    # =========================================================================
    # ID 인코딩/디코딩
    # =========================================================================

    def _connector_id_encode(self, name: str) -> str:
        return f"CONNECTOR_{name}"

    def _connector_id_decode(self, session_name: str) -> str:
        pos = session_name.find("_")
        return session_name[pos + 1:] if pos != -1 else session_name

    def _parser_id_encode(self, name: str) -> str:
        return f"PARSER_{name}"

    def _parser_id_decode(self, session_name: str) -> str:
        pos = session_name.find("_")
        return session_name[pos + 1:] if pos != -1 else session_name

    # =========================================================================
    # ConfigValueCheck / ReceiveTimeOut
    # =========================================================================

    def ConfigValueCheck(self) -> bool:
        if not self._router_listen_port:
            logger.error("Can't Find Config Value "
                         "[ASCII_MANAGER:router_listen_port]")
            return False
        if not self._log_router_listen_port:
            logger.error("Can't Find Config Value "
                         "[ASCII_MANAGER:log_router_listen_port]")
            return False
        return True

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        logger.debug("Unknown TimeOut Reason : %d", reason)

    # =========================================================================
    # RunCommand (SSH — 치트시트: paramiko)
    # =========================================================================

    def RunCommand(self, ssh_id: str, ssh_pass: str,
                   ip: str, command: str) -> bool:
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, port=22, username=ssh_id,
                           password=ssh_pass, timeout=10)
            client.exec_command(command)
            client.close()
            logger.info("SSH Connect !!!!!! [%s@%s]", ssh_id, ip)
            return True
        except Exception as e:
            logger.info("SSH Connect Fail!!!!!! : %s", e)
            return False


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''

def _size(obj) -> int:
    return len(_pack(obj))