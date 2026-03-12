"""
AsciiServerWorld.py
C++ AsciiServerWorld.h/.C → Python 변환
"""

from __future__ import annotations

import os
import threading
import time
import logging
from typing import Optional, TYPE_CHECKING

from Common.AsWorld import AsWorld
from Common.CommType import (
    AS_ASCII_ERROR_MSG_T, AS_CMD_LOG_CONTROL_T, AS_COMMAND_AUTHORITY_INFO_T,
    AS_CONNECTION_INFO_LIST_T, AS_CONNECTION_INFO_T, AS_CONNECTOR_DESC_CHANGE_INFO_T,
    AS_CONNECTOR_INFO_T, AS_DATA_HANDLER_INFO_T, AS_DATA_HANDLER_INIT_T,
    AS_DATA_ROUTING_INIT_T, AS_DB_SYNC_INFO_LIST_T, AS_LOG_STATUS_T,
    AS_MANAGER_INFO_T, AS_MMC_GEN_RESULT_T, AS_MMC_IDENT_REQ_T, AS_MMC_LOG_T,
    AS_MMC_PUBLISH_T, AS_MMC_REQUEST_T, AS_MMC_RESULT_T, AS_PROC_CONTROL_T,
    AS_PROCESS_STATUS_T, AS_RULE_CHANGE_INFO_T, AS_SESSION_CFG_T,
    AS_SESSION_CONTROL_T, AS_SUB_PROC_INFO_T, AS_SYSTEM_INFO_T,
    AS_ASCII_ACK_T, AS_ROUTER_INFO_REQ_T,
)
from Common.AsciiMmcType import AS_MMC_RESULT_MODE
from Common.AsSocket import AsSocket
from Common.ChildProcessManager import ChildProcessManager
from Common.CommTypeList import LogStatusVector

from AsciiServerType import (
    CommandAuthorityInfoMap, ExtMMCReqMap, ExtReqIndentify,
    ManagerInfoMap, MmcGenResultQueue, MmcPublishSet, MmcPublishSetQueue,
    MmcPublishSetQueueList, MmcRequestMap, MMCRequestQueueList,
    MMCResultStored, MMCResultStoredList, MMCResultStoredMap,
    ProcStatusInfoMap, ProcStatusMap, RouterInfoList,
    AsSessionCfgMap, AsSystemInfoMap,
    WAIT_MANAGER_START_TIMEOUT, WAIT_DATA_HANDLER_START_TIMEOUT,
    SESSION_TYPE_GUI, SESSION_TYPE_MMC, SESSION_TYPE_MGR,
)

from Util.fr_logger import make_log_def
from Util.fr_time import FrTime

# ── 아직 미변환인 ConnMgr 클래스들은 Forward import (추후 교체)
# from ManagerConnMgr        import ManagerConnMgr
# from GuiConnMgr            import GuiConnMgr
# from ExternalConnMgr       import ExternalConnMgr
# from DataHandlerConnMgr    import DataHandlerConnMgr
# from MMCGeneratorConnMgr   import MMCGeneratorConnMgr
# from RuleDownLoaderConnMgr import RuleDownLoaderConnMgr
# from RouterInfoConnMgr     import RouterInfoConnMgr
# from NetFinderConnMgr      import NetFinderConnMgr
# from SimsConnMgr           import SimsConnMgr
# from SubProcConnMgr        import SubProcConnMgr
# from ServerConnMgr         import ServerConnMgr
# from DbManager             import DbManager
# from MMCRequestQueue       import MMCRequestQueue
# from MMCRequestConnection  import MMCRequestConnection
# from ServerConnection      import ServerConnection

_log = make_log_def("AsciiServer", "AsciiServerWorld")

# ──────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────
SERVER_UNIX_MMC_LISTEN              = "SERVER_MMC_LISTEN"
SERVER_UNIX_RULE_DOWNLOADER_LISTEN  = "SERVER_RULE_DOWNLOADER_LISTEN"
SERVER_UNIX_NETFINDER_LISTEN        = "SERVER_NETFINDER_LISTEN"

MMCQUEUE_GABAGE_CLEAR               = 5000   # AsWorld 타이머 reason (기존 코드 참조)
MMCRESPONSE_GABAGE_CLEAR            = 5001

DEFAULT_GABAGE_CLEAR_INTERVAL       = 60 * 60 * 3  # 3 hours
DEFAULT_MAX_SOCK_BUF                = 1_000_000
DEFAULT_SESSION_BUF                 = 10_000_000
DEFAULT_SOCK_BUF_SIZE               = 65536         # 기본값 (AsWorld 참조)
DEFAULT_SOCK_CHECK_TIME_OUT         = 30            # 기본값

BUF_SIZE        = 1024
PING_PACKET_SIZE = 8
PING_ECHO_COUNT  = 1
PING_ALIVE       = " 0% packet loss"

# DB 연결 오류 문자열 목록
DB_CONN_ERRORS = [
    "ORA-03114", "ORA-03113", "ORA-12154", "ORA-01017",
    "ORA-01001", "ORA-01012", "ORA-00028",
]

# 인자 상수 (AppStart 파싱용)
ARG_TYPES           = "-type"
ARG_SVR_ACTIVE      = "active"
ARG_SVR_STANDBY     = "standby"
ARG_SVR_IP          = "-svrip"
ARG_PORT_NO         = "-port"
ARG_NAME            = "-name"
ARG_SVR_SOCKET_PATH = "-svrsock"
ARG_NET_FINDER_PORT = "-nfport"
ARG_LOG_HOUR        = "hour"
ARG_LOG_DAY         = "day"

# 섹션 이름 (설정 파일 키)
ASCII_SERVER    = "ASCII_SERVER"
ASCII_MANAGER   = "ASCII_MANAGER"

# ProcessType 상수 (CommType/AsWorld 정의 기준)
ASCII_MMC_SCHEDULER  = 10
ASCII_MMC_GENERATOR  = 11
ASCII_JOB_MONITOR    = 12
ASCII_RULE_DOWNLOADER = 13
NETFINDER            = 14
ASCII_DATA_HANDLER   = 20
ASCII_SUB_PROCESS    = 21
ASCII_CONNECTOR      = 31
ASCII_PARSER         = 32
ASCII_DATA_ROUTER    = 33
ASCII_ROUTER         = 34

# ProcessStatus 상수
START = 1
STOP  = 0

# ResponseMode 상수
RESPONSE            = 1
SAVE_AND_RESPONSE   = 2
ONLY_SAVE_RESPONSE  = 3
NOT_PUBLISH         = 0
R_ERROR             = 0
R_COMPLETE          = 1
R_CONTINUE          = 2
FAIL                = 0
RE_ISSUE            = 1
CMD_ID              = 2
CMD_SET_ID          = 3

# DB Sync Kind 상수
CMD_PARSING_RULE_DOWN    = 1
CMD_MAPPING_RULE_DOWN    = 2
CMD_SCHEDULER_RULE_DOWN  = 3
CMD_COMMAND_RULE_DOWN    = 4
MANAGER_MODIFY           = 10
CONNECTOR_MODIFY         = 11
CONNECTION_MODIFY        = 12
CONNECTION_LIST_MODIFY   = 13
DATAHANDLER_MODIFY       = 14
COMMAND_AUTHORITY_MODIFY = 15

# Request status 상수
CREATE_DATA = 1
UPDATE_DATA = 2
DELETE_DATA = 3
WAIT_NO     = 0


# ──────────────────────────────────────────────
# AsciiServerWorld
# ──────────────────────────────────────────────
class AsciiServerWorld(AsWorld):
    """
    C++ AsciiServerWorld → Python 변환
    AsWorld를 상속하며, ASCII 서버의 메인 월드 클래스
    """

    # ── 클래스 변수 (C++ static 멤버)
    m_DbManager:  Optional[object]          = None
    m_WorldPtr:   Optional["AsciiServerWorld"] = None

    def __init__(self) -> None:
        super().__init__()
        AsciiServerWorld.m_WorldPtr = self

        # ── 상태 플래그
        self._m_ParsingRuleDownLoading:    bool = False
        self._m_MappingRuleDownLoading:    bool = False
        self._m_CommandRuleDownLoading:    bool = False
        self._m_SchedulerRuleDownLoading:  bool = False
        self._m_UseNameServer:             bool = True
        self._m_IsActive:                  bool = False
        self._m_ThreadStatus:              bool = True
        self._m_MmcStoredFunctionStatus:   bool = False

        # ── DB 접속 정보
        self._m_DbUserId:    str = ""
        self._m_DbPassword:  str = ""
        self._m_DbTns:       str = ""
        self._m_DbIp:        str = ""
        self._m_DbPort:      str = ""
        self._m_MmcStoredDbUserId: str = ""
        self._m_MmcStoredDbPasswd: str = ""
        self._m_MmcStoredDbTns:    str = ""

        # ── 포트
        self._m_ServerPort:           int = 0
        self._m_GuiPort:              int = 0
        self._m_ExtPort:              int = 0
        self._m_DataHandlerPort:      int = 0
        self._m_RouterInfoListenPort: int = 0
        self._m_NetFinderListenPort:  int = 0
        self._m_SimsListenPort:       int = 0
        self._m_SubProcListenPort:    int = 0
        self._m_StandBySvrListenPort: int = 0

        # ── Active/Standby
        self._m_ActiveServerIp:   str = ""
        self._m_ActiveServerPort: int = 0

        # ── 버퍼 크기
        self._m_DefaultMaxSockBuf: int = DEFAULT_MAX_SOCK_BUF
        self._m_DefaultSessionBuf: int = DEFAULT_SESSION_BUF

        # ── 기타 설정
        self.m_RunCmdPort: str = ""

        # ── 에러 로그 파일
        self._m_ErrorLogFp = None

        # ── MMC 관련 큐/맵
        self._m_MMCRequestQueueList:    MMCRequestQueueList   = MMCRequestQueueList()
        self._m_MmcGenResultQueue:      MmcGenResultQueue     = MmcGenResultQueue()
        self._m_ExtMMCReqMap:           ExtMMCReqMap          = ExtMMCReqMap()
        self._m_ExtMMCReqWaitMap:       ExtMMCReqMap          = ExtMMCReqMap()
        self._m_MmcRequestMap:          MmcRequestMap         = MmcRequestMap()
        self._m_MmcPublishSetQueueList: MmcPublishSetQueueList = MmcPublishSetQueueList()

        # MmcPublishSetQueue 5개 초기화 (priority 0~4)
        for _ in range(5):
            self._m_MmcPublishSetQueueList.append(MmcPublishSetQueue())

        # ── Lock
        self._m_MsgIdLock                   = threading.Lock()
        self._m_MmcReqListLock              = threading.Lock()
        self._m_ExtMMCReqWaitMapLock        = threading.Lock()
        self._m_MmcPublishListLock          = threading.Lock()
        self._m_MMCReqQueueGarbageListLock  = threading.Lock()
        self._m_MMCResultStoredListLock     = threading.Lock()

        # ── MsgId 카운터
        self._m_MsgId: int = 0

        # ── 스레드 핸들
        self._m_MMCRequestThread:     Optional[threading.Thread] = None
        self._m_MMCGenResultThread:   Optional[threading.Thread] = None
        self._m_MMCPublishThread:     Optional[threading.Thread] = None
        self._m_MMCResultStoredThread: Optional[threading.Thread] = None

        # ── ConnMgr 인스턴스 (추후 실제 클래스로 교체)
        self._m_ManagerConnMgr       = None
        self._m_GuiConnMgr           = None
        self._m_ExternalConnMgr      = None
        self._m_DataHandlerConnMgr   = None
        self._m_MMCGeneratorConnMgr  = None
        self._m_RuleDownLoaderConnMgr = None
        self._m_RouterInfoConnMgr    = None
        self._m_NetFinderConnMgr     = None
        self._m_SimsConnMgr          = None
        self._m_SubProcConnMgr       = None
        self._m_ServerConnMgr        = None
        self._m_ServerConnection     = None
        self._m_MMCResultDbManager   = None
        self._m_ChildProcManager     = ChildProcessManager()

        # ── 상태 맵
        self._m_ProcStatusMap:           ProcStatusMap           = ProcStatusMap()
        self._m_CommandAuthorityInfoMap: CommandAuthorityInfoMap = CommandAuthorityInfoMap()
        self._m_MMCReqQueueGarbageList:  MMCRequestQueueList     = MMCRequestQueueList()
        self._m_MMCResultStoredMap:      dict                    = {}  # MMCResultStoredMap
        self._m_MMCResultStoredList:     list                    = []  # MMCResultStoredList
        self._m_DbSyncInfoList:          AS_DB_SYNC_INFO_LIST_T  = AS_DB_SYNC_INFO_LIST_T()
        self._m_AsSystemInfoMap:         dict                    = {}  # AsSystemInfoMap
        self._m_AsSessionCfgMap:         dict                    = {}  # AsSessionCfgMap

    # ──────────────────────────────────────────
    # 초기화 / 종료
    # ──────────────────────────────────────────
    def clean_up(self) -> None:
        """C++: CleanUp()"""
        _log.debug(1, "Netadapter Server Clean Up")
        self._m_ThreadStatus = False

        for t in (self._m_MMCRequestThread, self._m_MMCGenResultThread,
                  self._m_MMCPublishThread, self._m_MMCResultStoredThread):
            if t and t.is_alive():
                # Python은 pthread_cancel 없음 → daemon 스레드 + _m_ThreadStatus 플래그로 종료
                pass

        if self._m_SimsConnMgr:
            del self._m_SimsConnMgr
            self._m_SimsConnMgr = None

        if self._m_ErrorLogFp:
            self._m_ErrorLogFp.flush()
            self._m_ErrorLogFp.close()
            self._m_ErrorLogFp = None

        if AsciiServerWorld.m_DbManager:
            AsciiServerWorld.m_DbManager.delete_connection_status()
            AsciiServerWorld.m_DbManager = None

        if self._m_MMCResultDbManager:
            self._m_MMCResultDbManager = None

    CleanUp = clean_up

    def app_start(self, argv: list[str]) -> bool:
        """C++: AppStart(Argc, Argv)"""
        from Util.fr_arg_parser import ArgParser
        arg = ArgParser(argv)

        arg_ret = False
        val = arg.get_value(ARG_TYPES)
        if val:
            if val == ARG_SVR_ACTIVE:
                arg_ret = True
                self._m_IsActive = True
            elif val == ARG_SVR_STANDBY:
                self._m_IsActive = False
                svr_ip   = arg.get_value(ARG_SVR_IP)
                port_str = arg.get_value(ARG_PORT_NO)
                if svr_ip and port_str:
                    self._m_ActiveServerIp   = svr_ip
                    self._m_ActiveServerPort = int(port_str)
                    if self._m_ActiveServerPort != 0:
                        arg_ret = True

        if not arg_ret:
            print(f"\n[Usage] {argv[0]} {ARG_TYPES} [{ARG_SVR_ACTIVE}|{ARG_SVR_STANDBY}]"
                  f" {ARG_SVR_IP} 192.168.1.4 {ARG_PORT_NO} 3439\n")
            print(f"    {ARG_SVR_IP}, {ARG_PORT_NO} is optional, if -{ARG_TYPES} is {ARG_SVR_ACTIVE}\n")
            return False
        else:
            if self._m_IsActive:
                print(f"SERVER TYPE : {ARG_SVR_ACTIVE}")
            else:
                print(f"SERVER TYPE : {ARG_SVR_STANDBY}, "
                      f"Active Server Address : [{self._m_ActiveServerIp}:{self._m_ActiveServerPort}]")

        if arg.get_value("-nons"):
            self._m_UseNameServer = False
        self._m_UseNameServer = False

        if not self.init_config():
            _log.error("Env Init Error")
            return False

        if not self.ascii_system_dir_check():
            _log.error("Ascii system directorys check fail")
            return False

        # 로그 레벨 설정
        from Util.fr_logger import Logger
        Logger.enable("AsciiServer", 3)
        Logger.enable("Common", 1)
        Logger.enable("Event", "frWorld", 1)

        # 설정값 읽기
        self._m_ProcName     = self.get_env_value(ASCII_SERVER, "name")
        self._m_DbUserId     = self.get_env_value(ASCII_SERVER, "db_user")
        self._m_DbPassword   = self.get_env_value(ASCII_SERVER, "db_password")
        self._m_DbTns        = self.get_env_value(ASCII_SERVER, "db_tns")
        self.m_RunCmdPort    = self.get_env_value(ASCII_SERVER, "run_command_port")
        self._m_DbIp         = self.get_env_value(ASCII_SERVER, "db_ip")
        self._m_DbPort       = self.get_env_value(ASCII_SERVER, "db_port")

        self.set_system_info(ASCII_SERVER, self._m_ProcName)
        self.recv_system_info(self._m_SystemInfo)

        self._m_ServerPort           = int(self.get_env_value(ASCII_SERVER, "server_listen_port") or 0)
        self._m_GuiPort              = int(self.get_env_value(ASCII_SERVER, "gui_listen_port") or 0)
        self._m_ExtPort              = int(self.get_env_value(ASCII_SERVER, "external_system_listenport") or 0)
        self._m_DataHandlerPort      = int(self.get_env_value(ASCII_SERVER, "datahandler_listen_port") or 0)
        self._m_RouterInfoListenPort = int(self.get_env_value(ASCII_SERVER, "routerinfo_listen_port") or 0)
        self._m_SimsListenPort       = int(self.get_env_value(ASCII_SERVER, "sims_listen_port") or 0)
        self._m_NetFinderListenPort  = int(self.get_env_value(ASCII_SERVER, "netfinder_listen_port") or 0)
        self._m_StandBySvrListenPort = int(self.get_env_value(ASCII_SERVER, "standby_listen_port") or 0)
        self._m_SubProcListenPort    = int(self.get_env_value(ASCII_SERVER, "subproc_listen_port") or 0)

        self._m_MmcStoredDbUserId = self.get_env_value(ASCII_SERVER, "mmc_stored_db_userid")
        self._m_MmcStoredDbPasswd = self.get_env_value(ASCII_SERVER, "mmc_stored_db_passwd")
        self._m_MmcStoredDbTns    = self.get_env_value(ASCII_SERVER, "mmc_stored_db_dbtns")

        tmp = int(self.get_env_value(ASCII_SERVER, "max_socket_buf") or 0)
        if self._m_DefaultMaxSockBuf < tmp:
            self._m_DefaultMaxSockBuf = tmp

        tmp = int(self.get_env_value(ASCII_SERVER, "max_session_buf") or 0)
        if self._m_DefaultSessionBuf < tmp:
            self._m_DefaultSessionBuf = tmp

        _log.debug(1, f"NetAdapter Server({val}) Start(user:{self.get_user_name()})")

        self._init_session_cfg()
        if not self._config_value_check():
            return False

        self.set_log_file()
        self._error_file_changed()
        self.set_log_status(ASCII_SERVER, self._m_ProcName, self._get_host_name())

        if not self._init_common_server():
            _log.debug(1, "Server Init Fail")
            return False

        if self._m_IsActive:
            if not self._init_active_server():
                _log.debug(1, f"{ARG_SVR_ACTIVE} Server Init Fail")
                return False
        else:
            if not self._init_standby_server():
                _log.debug(1, f"{ARG_SVR_STANDBY} Server Init Fail")
                return False

        _log.debug(1, "Finish Ascii Server init..............")
        return True

    AppStart = app_start

    # ──────────────────────────────────────────
    # 서버 초기화 (Active / Standby / Common)
    # ──────────────────────────────────────────
    def _init_active_server(self) -> bool:
        """C++: InitActiveServer()"""
        # ── 소켓 생성 및 Listen (각 ConnMgr 구현 후 실제 호출로 교체)
        import socket as _socket

        def _fail(name: str, err: str) -> bool:
            _log.error(f"{name} Error : {err}")
            return False

        for mgr, port, proto, label in [
            (self._m_ExternalConnMgr,      self._m_ExtPort,              "TCP",  "External System"),
            (self._m_ManagerConnMgr,       self._m_ServerPort,           "TCP",  "Manager"),
            (self._m_DataHandlerConnMgr,   self._m_DataHandlerPort,      "TCP",  "DataHandler"),
            (self._m_SubProcConnMgr,       self._m_SubProcListenPort,    "TCP",  "SubProc"),
            (self._m_GuiConnMgr,           self._m_GuiPort,              "TCP",  "GUI"),
            (self._m_RouterInfoConnMgr,    self._m_RouterInfoListenPort, "TCP",  "RouterInfo"),
            (self._m_ServerConnMgr,        self._m_StandBySvrListenPort, "TCP",  "Standby Server"),
        ]:
            if mgr is None:
                continue
            if not mgr.create():
                return _fail(f"{label} Create", mgr.get_obj_err_msg())
            if not mgr.listen(port):
                return _fail(f"{label} Listen(port:{port})", mgr.get_obj_err_msg())

        # Unix Domain
        for mgr, path, label in [
            (self._m_MMCGeneratorConnMgr, self.get_mmc_listen_socket_path(),  "MMCGenerator"),
        ]:
            if mgr is None:
                continue
            if not mgr.create(_socket.AF_UNIX):
                return _fail(f"{label} Create", mgr.get_obj_err_msg())
            if not mgr.listen(path):
                return _fail(f"{label} Listen", mgr.get_obj_err_msg())

        # Sims
        if self._m_SimsConnMgr:
            if not self._m_SimsConnMgr.create():
                return _fail("Sims Create", self._m_SimsConnMgr.get_obj_err_msg())
            if self._m_SimsListenPort:
                if not self._m_SimsConnMgr.listen(self._m_SimsListenPort):
                    return _fail(f"Sims Listen(port:{self._m_SimsListenPort})",
                                 self._m_SimsConnMgr.get_obj_err_msg())
            else:
                _log.debug(1, "Sim port is not defined, so can't listen sim port")

        # ── MMC/GenResult/Publish 스레드 시작
        for target, attr, label in [
            (self._mmc_request_manager,   "_m_MMCRequestThread",   "MMCRequestManager"),
            (self._mmc_gen_result_manager,"_m_MMCGenResultThread",  "MMCGenResultManager"),
            (self._mmc_publish_manager,   "_m_MMCPublishThread",   "MMCPublishManager"),
        ]:
            t = threading.Thread(target=target, name=label, daemon=True)
            t.start()
            setattr(self, attr, t)
            _log.debug(1, f"Thread Create Success For {label}")

        # ── DbManager 초기화
        from DbManager import DbManager
        if AsciiServerWorld.m_DbManager:
            AsciiServerWorld.m_DbManager = None
        AsciiServerWorld.m_DbManager = DbManager()
        if not AsciiServerWorld.m_DbManager.init_db_manager(
                self._m_DbUserId, self._m_DbPassword, self._m_DbTns,
                self._m_DbIp, self._m_DbPort):
            _log.error(f"Db Connection Error : [{self._m_DbUserId}/{self._m_DbPassword}@{self._m_DbTns}]"
                       f"{AsciiServerWorld.m_DbManager.get_error_msg()}")
            return False

        # ── ObjectName 설정
        for mgr, name in [
            (self._m_ManagerConnMgr,       "ManagerConnListener"),
            (self._m_GuiConnMgr,           "GuiConnListener"),
            (self._m_ExternalConnMgr,      "ExternalConnListener"),
            (self._m_DataHandlerConnMgr,   "DataHandlerConnListener"),
            (self._m_MMCGeneratorConnMgr,  "MMCGeneratorConnListener"),
            (self._m_RouterInfoConnMgr,    "RouterInfoConnListener"),
            (self._m_SubProcConnMgr,       "SubProcConnListener"),
        ]:
            if mgr:
                mgr.set_object_name(name)
        if self._m_SimsConnMgr:
            self._m_SimsConnMgr.set_object_name("SimsConnListener")

        # ── Command Authority 정보 로드
        AsciiServerWorld.m_DbManager.get_command_authority_info(self._m_CommandAuthorityInfoMap)
        _log.debug(1, f"CommandAuthorityInfoMap Size : {len(self._m_CommandAuthorityInfoMap)}")

        dbm_msg_id = AsciiServerWorld.m_DbManager.get_current_msg_id()
        self._m_MsgId = 0 if dbm_msg_id < 0 else dbm_msg_id

        # ── 서브 프로세스 기동
        self._m_SubProcConnMgr.execute_sub_proc()
        self._m_DataHandlerConnMgr.execute_data_handler()
        self._m_ManagerConnMgr.execute_manager()

        # ── 타이머 설정
        self.set_timer(10,  MMCQUEUE_GABAGE_CLEAR)
        self.set_timer(120, MMCRESPONSE_GABAGE_CLEAR)

        # ── 프로세스 상태 등록
        proc_info = AS_PROCESS_STATUS_T()
        proc_info.ProcessId   = self._m_ProcName
        proc_info.ManagerId   = self._m_ProcName
        proc_info.Status      = START
        proc_info.ProcessType = ASCII_SERVER  # type: ignore
        self.update_process_info(proc_info)

        # ── SockMgr 세션
        sock_mgr_port = int(self.get_env_value(ASCII_SERVER, "sock_mgr_listen_port") or 0)
        if sock_mgr_port > 3000:
            self.enable_sock_mgr_session("ServerSockMgrListener", sock_mgr_port)

        self._m_ServerConnection = None

        log_router_port = int(self.get_env_value(ASCII_MANAGER, "log_router_listen_port") or 0)
        from Common.AsUtil import AsUtil
        return AsciiServerWorld.m_DbManager.update_server_info(
            AsUtil.GetLocalIp(), self._m_GuiPort, self._m_ExtPort,
            log_router_port, sock_mgr_port, self._m_NetFinderListenPort)

    def _init_standby_server(self) -> bool:
        """C++: InitStandbyServer()"""
        from DbManager import DbManager
        if AsciiServerWorld.m_DbManager:
            AsciiServerWorld.m_DbManager = None
        AsciiServerWorld.m_DbManager = DbManager()
        if not AsciiServerWorld.m_DbManager.init_db_manager(
                self._m_DbUserId, self._m_DbPassword, self._m_DbTns,
                self._m_DbIp, self._m_DbPort):
            _log.error(f"Db Connection Error : {AsciiServerWorld.m_DbManager.get_error_msg()}")
            return False

        from ServerConnection import ServerConnection
        self._m_ServerConnection = ServerConnection(None)
        if not self._m_ServerConnection.connect(self._m_ActiveServerIp, self._m_ActiveServerPort):
            _log.error(f"Active Server({self._m_ActiveServerIp}:{self._m_ActiveServerPort}) "
                       f"connect error : {self._m_ServerConnection.get_obj_err_msg()}")
            return False
        self._m_ServerConnection.set_session_identify(ASCII_SERVER, self._m_ProcName, 100, False)
        self.update_db_sync_time()
        return True

    def _init_common_server(self) -> bool:
        """C++: InitCommonServer()"""
        import socket as _socket
        if not self._m_RuleDownLoaderConnMgr.create(_socket.AF_UNIX):
            _log.error(f"RuleDownLoader Listener Create Error : {self._m_RuleDownLoaderConnMgr.get_obj_err_msg()}")
            return False
        if not self._m_RuleDownLoaderConnMgr.listen(self.get_rule_down_loader_listen_socket_path()):
            _log.error(f"Listen Error For RuleDownLoader : {self._m_RuleDownLoaderConnMgr.get_obj_err_msg()}")
            return False
        self._m_RuleDownLoaderConnMgr.set_object_name("RuleDownLoaderConnListener")
        self.start_proc(ASCII_RULE_DOWNLOADER)
        return True

    # ──────────────────────────────────────────
    # 경로/포트 헬퍼
    # ──────────────────────────────────────────
    def get_mmc_listen_socket_path(self) -> str:
        return f"{self.get_unix_socket_dir()}/{SERVER_UNIX_MMC_LISTEN}"

    def get_rule_down_loader_listen_socket_path(self) -> str:
        return f"{self.get_unix_socket_dir()}/{SERVER_UNIX_RULE_DOWNLOADER_LISTEN}"

    def get_net_finder_listen_socket_path(self) -> str:
        return f"{self.get_unix_socket_dir()}/{SERVER_UNIX_NETFINDER_LISTEN}"

    GetMmcListenSocketPath            = get_mmc_listen_socket_path
    GetRuleDownLoaderListenSocketPath = get_rule_down_loader_listen_socket_path
    GetNetFinderListenSocketPath      = get_net_finder_listen_socket_path

    def get_listen_port(self, proc_type: int) -> str:
        if proc_type == 3:   # ASCII_MANAGER
            return str(self._m_ServerPort)
        elif proc_type == ASCII_DATA_HANDLER:
            return str(self._m_DataHandlerPort)
        elif proc_type == ASCII_SUB_PROCESS:
            return str(self._m_SubProcListenPort)
        else:
            _log.error(f"Unknown Proc Type : {proc_type}")
            return ""

    GetListenPort = get_listen_port

    def get_server_ip(self) -> str:
        import socket as _socket
        return _socket.gethostbyname(_socket.gethostname())

    GetServerIp = get_server_ip

    def get_db_user_id(self)  -> str: return self._m_DbUserId
    def get_db_passwd(self)   -> str: return self._m_DbPassword
    def get_db_tns(self)      -> str: return self._m_DbTns
    GetDbUserId = get_db_user_id
    GetDbPasswd = get_db_passwd
    GetDbTns    = get_db_tns

    # ──────────────────────────────────────────
    # PID 관리
    # ──────────────────────────────────────────
    def add_pid(self, pid: int) -> None:
        self._m_ChildProcManager.add_pid(pid)

    def remove_pid(self, pid: int) -> None:
        self._m_ChildProcManager.remove_pid(pid)

    def kill_proc(self, pid: int) -> None:
        self._m_ChildProcManager.kill_proc(pid)

    AddPid    = add_pid
    RemovePid = remove_pid
    KillProc  = kill_proc

    # ──────────────────────────────────────────
    # 에러 로그
    # ──────────────────────────────────────────
    def send_ascii_error(self, priority_or_err, fmt: str = "", *args) -> None:
        """C++: SendAsciiError 두 버전 통합"""
        if isinstance(priority_or_err, AS_ASCII_ERROR_MSG_T):
            self._write_error_log(priority_or_err)
        else:
            priority: int = priority_or_err
            msg = (fmt % args) if args else fmt
            err = AS_ASCII_ERROR_MSG_T()
            err.ProcessType = ASCII_SERVER   # type: ignore
            err.ProcessId   = self.get_proc_name()
            err.ManagerId   = self.get_proc_name()
            err.Priority    = priority
            err.ErrMsg      = msg
            self._write_error_log(err)

    SendAsciiError = send_ascii_error

    def _write_error_log(self, ascii_error: AS_ASCII_ERROR_MSG_T) -> None:
        cur = FrTime()
        cur.set()
        buf = (f"({cur.get_month():02d}/{cur.get_day():02d} "
               f"{cur.get_hour():02d}:{cur.get_minute():02d}:{cur.get_second():02d}, "
               f"{ascii_error.ProcessId}) {ascii_error.ErrMsg}")
        if len(buf) > 4000:
            buf = buf[:3999]
        ascii_error.ErrMsg = buf

        if self._m_ErrorLogFp:
            self._m_ErrorLogFp.write(ascii_error.ErrMsg + "\n")
            self._m_ErrorLogFp.flush()

        if self._m_GuiConnMgr:
            self._m_GuiConnMgr.send_ascii_error(ascii_error)

    WriteErrorLog = _write_error_log

    # ──────────────────────────────────────────
    # MsgId
    # ──────────────────────────────────────────
    def get_msg_id(self) -> int:
        with self._m_MsgIdLock:
            msg_id = self._m_MsgId
            self._m_MsgId += 1
        return msg_id

    GetMsgId = get_msg_id

    # ──────────────────────────────────────────
    # 프로세스 기동
    # ──────────────────────────────────────────
    def start_proc(self, proc_type: int) -> None:
        """C++: StartProc()"""
        proc_name = self.get_process_name(proc_type)
        args = [
            self.get_proc_position() + proc_name,
            proc_name,
            "-name", proc_name,
            "-svrsock",
        ]

        if proc_type == ASCII_RULE_DOWNLOADER:
            args.append(self.get_rule_down_loader_listen_socket_path())
        elif proc_type == NETFINDER:
            args.append(self.get_net_finder_listen_socket_path())
            args += ["-nfport", str(self._m_NetFinderListenPort)]
        else:
            args.append(self.get_mmc_listen_socket_path())

        pid = -1
        if proc_type in (ASCII_MMC_SCHEDULER, ASCII_MMC_GENERATOR, ASCII_JOB_MONITOR):
            pid = self._m_MMCGeneratorConnMgr.start_proc(proc_name, args)
        elif proc_type == ASCII_RULE_DOWNLOADER:
            pid = self._m_RuleDownLoaderConnMgr.start_proc(proc_name, args)
        elif proc_type == NETFINDER:
            pid = self._m_NetFinderConnMgr.start_proc(proc_name, args)

        if pid == -1:
            self.send_ascii_error(1,
                f"The process {self.get_process_name(ASCII_SERVER)}({self.get_proc_name()}) "
                f"forking fails.")
        else:
            self.add_pid(pid)
            _log.debug(1, f"Process Execute : {proc_name}(pid:{pid})")

    StartProc = start_proc

    # ──────────────────────────────────────────
    # 인포 조회
    # ──────────────────────────────────────────
    def get_data_handler_info_map(self):
        return self._m_DataHandlerConnMgr.get_data_handler_info_map() if self._m_DataHandlerConnMgr else None

    def get_command_authority_info_map(self) -> CommandAuthorityInfoMap:
        return self._m_CommandAuthorityInfoMap

    def get_sub_proc_info_map(self):
        return self._m_SubProcConnMgr.get_sub_proc_info_map() if self._m_SubProcConnMgr else None

    GetDataHandlerInfoMap     = get_data_handler_info_map
    GetCommandAuthorityInfoMap = get_command_authority_info_map
    GetSubProcInfoMap         = get_sub_proc_info_map

    # ──────────────────────────────────────────
    # MMC 관련 외부 인터페이스
    # ──────────────────────────────────────────
    def send_ext_mmc_req_result(self, req_conn, res: AS_MMC_RESULT_T) -> None:
        if self._m_ExternalConnMgr:
            self._m_ExternalConnMgr.send_ext_mmc_req_result(req_conn, res)

    SendExtMMCReqResult = send_ext_mmc_req_result

    def mmc_res_from_mmc_gen(self, result: AS_MMC_GEN_RESULT_T) -> None:
        import copy
        new_result = copy.deepcopy(result)
        _log.debug(1, f"MmcGenResult push back to list id({result.id}), ne({result.ne})")
        self._m_MmcGenResultQueue.push_back(new_result)

    MMCResFromMMCGen = mmc_res_from_mmc_gen

    def get_mmc_gen_result_node(self) -> Optional[AS_MMC_GEN_RESULT_T]:
        return self._m_MmcGenResultQueue.get_mmc_gen_result_node()

    GetMmcGenResultNode = get_mmc_gen_result_node

    def register_mmc_req_conn(self, req_conn, max_queue_size: int = 100):
        """C++: RegisterMMCReqConn()"""
        from MMCRequestQueue import MMCRequestQueue
        req_queue = MMCRequestQueue(max_queue_size, req_conn)
        req_queue.set_queue_name(req_conn.get_session_name())
        with self._m_MmcReqListLock:
            self._m_MMCRequestQueueList.append(req_queue)
        return req_queue

    RegisterMMCReqConn = register_mmc_req_conn

    def insert_mmc_publish_set(self, mmc_publish_set: MmcPublishSet, priority: int = -1) -> None:
        _log.debug(1, f"Mmcpublish push to list ne({mmc_publish_set.m_MmcLog.ne})")
        with self._m_MmcPublishListLock:
            p = priority - 1
            q_len = len(self._m_MmcPublishSetQueueList)
            if p < 0 or p >= q_len:
                self._m_MmcPublishSetQueueList[-1].insert_mmc_publish_set(mmc_publish_set)
            else:
                self._m_MmcPublishSetQueueList[p].insert_mmc_publish_set(mmc_publish_set)

    InsertMMCPublishSet = insert_mmc_publish_set

    def ident_mmc_request_session(self,
                                  ident_req: AS_MMC_IDENT_REQ_T,
                                  info: AS_COMMAND_AUTHORITY_INFO_T) -> bool:
        found = self._m_CommandAuthorityInfoMap.get(ident_req.name)
        if found:
            info.__dict__.update(found.__dict__)
            return True
        return False

    IdentMMCRequestSession = ident_mmc_request_session

    # ──────────────────────────────────────────
    # MMC 스레드 루프 (C++ static void* → Python 인스턴스 메서드)
    # ──────────────────────────────────────────
    def _mmc_request_manager(self) -> None:
        """C++: MMCRequestManager(void* Arg)"""
        delete_queue: list = []

        while True:
            with self._m_MmcReqListLock:
                for q in delete_queue:
                    self._insert_garbage_mmc_queue(q)
            delete_queue.clear()

            sleep_flag = True
            while True:
                sleep_flag = True
                with self._m_MmcReqListLock:
                    cnt = len(self._m_MMCRequestQueueList)
                    snapshot = list(self._m_MMCRequestQueueList)

                i = 0
                remove_list = []
                for req_queue in snapshot[:cnt]:
                    mmc_req = req_queue.get_mmc_request()
                    if mmc_req is None:
                        req_queue.status_lock()
                        if not req_queue.get_status():
                            delete_queue.append(req_queue)
                            remove_list.append(req_queue)
                        req_queue.status_unlock()
                        continue

                    sleep_flag = False
                    msg_id = self.get_msg_id()

                    if mmc_req.type == RE_ISSUE:
                        mmc_log = AS_MMC_LOG_T()
                        mmc_log.id          = msg_id
                        mmc_log.previousId  = mmc_req.id
                        mmc_log.ne          = mmc_req.ne
                        mmc_log.interfaces  = mmc_req.interfaces
                        mmc_log.mmc         = mmc_req.mmc
                        mmc_log.userid      = mmc_req.userid
                        mmc_log.display     = mmc_req.display
                        mmc_log.collectMode = mmc_req.collectMode
                        mmc_log.responseMode = mmc_req.responseMode
                        mmc_log.publishMode = mmc_req.publishMode
                        mmc_log.logMode     = mmc_req.logMode
                        mmc_log.priority    = mmc_req.priority
                        mmc_log.cmdDelayTime = mmc_req.cmdDelayTime
                        self.insert_mmc_publish_set(MmcPublishSet(mmc_log, None), mmc_req.priority)

                    elif (mmc_req.type in (CMD_ID, CMD_SET_ID) or
                          mmc_req.responseMode in (RESPONSE, SAVE_AND_RESPONSE, ONLY_SAVE_RESPONSE)):
                        if mmc_req.responseMode in (RESPONSE, SAVE_AND_RESPONSE, ONLY_SAVE_RESPONSE):
                            ext_req = ExtReqIndentify()
                            ext_req.Id  = mmc_req.id
                            ext_req.GId = msg_id
                            ext_req.ReqConn = (req_queue.m_MMCRequestConnection
                                               if mmc_req.responseMode in (RESPONSE, SAVE_AND_RESPONSE)
                                               else None)
                            self._m_ExtMMCReqMap.insert(msg_id, ext_req)

                        _log.debug(3, f"Insert MMCRequest Map msgId : {msg_id}")
                        if not self._m_MmcRequestMap.insert(msg_id, mmc_req):
                            _log.error("Can't Insert MmcRequest of RECOLLECT or RESPONSE Request")

                        mmc_req.id = msg_id
                        self._m_MMCGeneratorConnMgr.send_mmc_req_to_mmc_gen(mmc_req)
                    else:
                        mmc_log = AS_MMC_LOG_T()
                        mmc_log.id          = msg_id
                        mmc_log.ne          = mmc_req.ne
                        mmc_log.interfaces  = mmc_req.interfaces
                        mmc_log.mmc         = mmc_req.mmc
                        mmc_log.userid      = mmc_req.userid
                        mmc_log.display     = mmc_req.display
                        mmc_log.collectMode = mmc_req.collectMode
                        mmc_log.responseMode = mmc_req.responseMode
                        mmc_log.publishMode = mmc_req.publishMode
                        mmc_log.logMode     = mmc_req.logMode
                        mmc_log.priority    = mmc_req.priority
                        mmc_log.cmdDelayTime = mmc_req.cmdDelayTime
                        self.insert_mmc_publish_set(MmcPublishSet(mmc_log, None), mmc_req.priority)

                with self._m_MmcReqListLock:
                    for q in remove_list:
                        try:
                            self._m_MMCRequestQueueList.remove(q)
                        except ValueError:
                            pass

                if sleep_flag:
                    break

            if sleep_flag:
                time.sleep(0.07)

    def _mmc_gen_result_manager(self) -> None:
        """C++: MMCGenResultManager(void* Arg)"""
        while True:
            sleep_flag = True
            while True:
                result = self.get_mmc_gen_result_node()
                if result is None:
                    break
                sleep_flag = False
                ext_req  = self._m_ExtMMCReqMap.find(result.id)
                mmc_req  = self._m_MmcRequestMap.find(result.id)

                if mmc_req is None:
                    _log.debug(1, f"Can't Find MMCRequest Id : {result.id}")
                    if ext_req:
                        self._m_ExtMMCReqMap.erase(result.id)
                    continue

                if result.resultMode == R_ERROR:
                    if ext_req:
                        mmc_res = AS_MMC_RESULT_T()
                        mmc_res.id         = ext_req.Id
                        mmc_res.resultMode = R_ERROR
                        mmc_res.result     = result.ErrMsg
                        self.send_ext_mmc_req_result(ext_req.ReqConn, mmc_res)
                        self._m_ExtMMCReqMap.erase(result.id)
                else:
                    for i in range(result.commandNo):
                        mmc_gen_com = result.commands[i]
                        ext_req_bak = None

                        if mmc_gen_com.resultMode == FAIL:
                            if ext_req:
                                mmc_res = AS_MMC_RESULT_T()
                                mmc_res.id         = ext_req.Id
                                mmc_res.resultMode = R_ERROR
                                mmc_res.result     = mmc_gen_com.key
                                self.send_ext_mmc_req_result(ext_req.ReqConn, mmc_res)
                            continue

                        mmc_log = AS_MMC_LOG_T()
                        mmc_log.id         = self.get_msg_id()
                        mmc_log.ne         = result.ne
                        mmc_log.cmdSetId   = mmc_gen_com.commandSetId
                        mmc_log.cmdId      = mmc_gen_com.commandId
                        mmc_log.interfaces = mmc_req.interfaces
                        mmc_log.mmc        = mmc_gen_com.mmc
                        mmc_log.idString   = mmc_gen_com.idString
                        mmc_log.userid     = mmc_req.userid
                        mmc_log.display    = mmc_req.display
                        mmc_log.retryNo    = mmc_req.retryNo
                        mmc_log.curRetryNo = mmc_req.curRetryNo
                        mmc_log.collectMode  = mmc_req.collectMode
                        mmc_log.responseMode = mmc_req.responseMode
                        mmc_log.publishMode  = mmc_req.publishMode
                        mmc_log.logMode      = mmc_req.logMode
                        mmc_log.priority     = mmc_req.priority
                        mmc_log.cmdDelayTime = mmc_req.cmdDelayTime
                        mmc_log.key          = mmc_gen_com.key

                        if ext_req:
                            import copy
                            ext_req_bak = copy.deepcopy(ext_req)

                        priority = (0 if mmc_log.responseMode in (RESPONSE, SAVE_AND_RESPONSE, ONLY_SAVE_RESPONSE)
                                    else mmc_req.priority)
                        self.insert_mmc_publish_set(MmcPublishSet(mmc_log, ext_req_bak), priority)

                    if result.resultMode != R_CONTINUE and ext_req:
                        self._m_ExtMMCReqMap.erase(result.id)

                if mmc_req and result.resultMode != R_CONTINUE:
                    self._m_MmcRequestMap.erase(result.id)

            if sleep_flag:
                time.sleep(0.07)

    def _mmc_publish_manager(self) -> None:
        """C++: MMCPublishManager(void* Arg)"""
        while True:
            while True:
                cnt = len(self._m_MmcPublishSetQueueList)
                queue_empty_cnt = cnt

                for mmc_com_set_queue in list(self._m_MmcPublishSetQueueList):
                    mmc_com_set = mmc_com_set_queue.get_mmc_publish_set()
                    if mmc_com_set is None:
                        queue_empty_cnt -= 1
                        continue

                    if mmc_com_set.m_MmcLog.logMode:
                        self._m_MMCGeneratorConnMgr.send_mmc_log(mmc_com_set.m_MmcLog)

                    if mmc_com_set.m_MmcLog.publishMode != NOT_PUBLISH:
                        mmc_com = AS_MMC_PUBLISH_T()
                        mmc_com.id           = mmc_com_set.m_MmcLog.id
                        mmc_com.responseMode = mmc_com_set.m_MmcLog.responseMode
                        mmc_com.publishMode  = mmc_com_set.m_MmcLog.publishMode
                        mmc_com.ne           = mmc_com_set.m_MmcLog.ne
                        mmc_com.mmc          = mmc_com_set.m_MmcLog.mmc
                        mmc_com.idString     = mmc_com_set.m_MmcLog.idString
                        mmc_com.key          = mmc_com_set.m_MmcLog.key
                        mmc_com.cmdDelayTime = mmc_com_set.m_MmcLog.cmdDelayTime

                        err_str = ""
                        tmp_res_mode = mmc_com.responseMode

                        if mmc_com.responseMode in (RESPONSE, SAVE_AND_RESPONSE, ONLY_SAVE_RESPONSE):
                            mmc_com.responseMode = RESPONSE

                        ok, err_str = self._m_ManagerConnMgr.send_mmc_command(mmc_com)
                        if not ok:
                            if mmc_com_set.m_ExtReq:
                                mmc_res = AS_MMC_RESULT_T()
                                mmc_res.id         = mmc_com_set.m_ExtReq.Id
                                mmc_res.resultMode = R_ERROR
                                mmc_res.result     = err_str
                                self.send_ext_mmc_req_result(mmc_com_set.m_ExtReq.ReqConn, mmc_res)

                            if tmp_res_mode in (SAVE_AND_RESPONSE, ONLY_SAVE_RESPONSE):
                                cur = FrTime(); cur.set()
                                tmp_r = MMCResultStored()
                                tmp_r.Gid             = mmc_com_set.m_MmcLog.id
                                tmp_r.IssuedTime      = cur.get_time()
                                tmp_r.IssuedTimeStr   = cur.get_time_string()
                                tmp_r.ResultStartTime = cur.get_time_string()
                                tmp_r.ResultEndTime   = cur.get_time_string()
                                tmp_r.ResultMode      = R_ERROR
                                tmp_r.ResultMsg       = err_str
                                tmp_r.MmcInfo.__dict__.update(mmc_com_set.m_MmcLog.__dict__)
                                self._insert_mmc_result_stored(tmp_r)
                        else:
                            mmc_com.responseMode = tmp_res_mode
                            if mmc_com.responseMode in (RESPONSE, SAVE_AND_RESPONSE, ONLY_SAVE_RESPONSE):
                                cur = FrTime(); cur.set()
                                import copy
                                ext_req_bak = ExtReqIndentify()
                                ext_req_bak.GId          = mmc_com.id
                                ext_req_bak.Id           = mmc_com_set.m_ExtReq.Id
                                ext_req_bak.IssuedTimeStr = cur.get_time_string()
                                ext_req_bak.IssuedTime   = cur.get_time()
                                ext_req_bak.MmcInfo.__dict__.update(mmc_com_set.m_MmcLog.__dict__)
                                ext_req_bak.ReqConn = (mmc_com_set.m_ExtReq.ReqConn
                                                       if mmc_com_set.m_ExtReq else None)
                                with self._m_ExtMMCReqWaitMapLock:
                                    self._m_ExtMMCReqWaitMap[mmc_com_set.m_MmcLog.id] = ext_req_bak

                if queue_empty_cnt == 0:
                    break

            time.sleep(0.07)

    # C++ static → 인스턴스 메서드 alias
    MMCRequestManager  = _mmc_request_manager
    MMCGenResultManager = _mmc_gen_result_manager
    MMCPublishManager  = _mmc_publish_manager

    # ──────────────────────────────────────────
    # MMC 결과 수신
    # ──────────────────────────────────────────
    def receive_mmc_result(self, mmc_result: AS_MMC_RESULT_T) -> None:
        _log.debug(1, f"Receive MMC Result : msgId({mmc_result.id})")
        with self._m_ExtMMCReqWaitMapLock:
            ext_req = self._m_ExtMMCReqWaitMap.get(mmc_result.id)
            if ext_req is None:
                _log.debug(1, f"Can't Find MmcResult id : {mmc_result.id}")
                return

            mmc_result.id = ext_req.Id
            if ext_req.ReqConn:
                self.send_ext_mmc_req_result(ext_req.ReqConn, mmc_result)

            if ext_req.MmcInfo.responseMode in (SAVE_AND_RESPONSE, ONLY_SAVE_RESPONSE):
                if self._m_MmcStoredFunctionStatus:
                    cur = FrTime(); cur.set()
                    result_stored = self._m_MMCResultStoredMap.get(ext_req.GId)
                    if result_stored is None:
                        result_stored = MMCResultStored()
                        result_stored.Gid           = ext_req.GId
                        result_stored.ExtId         = ext_req.Id
                        result_stored.MmcInfo.__dict__.update(ext_req.MmcInfo.__dict__)
                        result_stored.IssuedTimeStr = ext_req.IssuedTimeStr
                        result_stored.IssuedTime    = ext_req.IssuedTime
                        result_stored.ResultMode    = mmc_result.resultMode
                        result_stored.ResultStartTime = cur.get_time_string()
                        result_stored.ResultEndTime   = result_stored.ResultStartTime
                        self._m_MMCResultStoredMap[ext_req.GId] = result_stored
                    else:
                        result_stored.ResultMsg    += mmc_result.result
                        result_stored.ResultEndTime = cur.get_time_string()
                        result_stored.ResultMode    = mmc_result.resultMode

                        if mmc_result.resultMode in (R_COMPLETE, R_ERROR):
                            self._insert_mmc_result_stored(result_stored)
                            del self._m_MMCResultStoredMap[ext_req.GId]

            if mmc_result.resultMode in (R_COMPLETE, R_ERROR):
                del self._m_ExtMMCReqWaitMap[mmc_result.id]

    ReceiveMMCResult = receive_mmc_result

    # ──────────────────────────────────────────
    # 로그 상태
    # ──────────────────────────────────────────
    def send_log_status(self, status: AS_LOG_STATUS_T) -> None:
        pass  # not used

    def get_log_status_list(self, status_list: LogStatusVector) -> None:
        status_list.append(self.get_log_status())
        for mgr in (self._m_ManagerConnMgr, self._m_DataHandlerConnMgr,
                    self._m_MMCGeneratorConnMgr, self._m_RuleDownLoaderConnMgr):
            if mgr:
                mgr.get_log_status_list(status_list)

    def receive_cmd_log_status_change(self, log_ctl: AS_CMD_LOG_CONTROL_T) -> None:
        pt = log_ctl.ProcessType
        if pt == ASCII_SERVER:
            self.send_log_status(self.change_log_status(log_ctl))
        elif pt in (ASCII_MMC_GENERATOR, ASCII_MMC_SCHEDULER, ASCII_JOB_MONITOR):
            if self._m_MMCGeneratorConnMgr:
                self._m_MMCGeneratorConnMgr.send_cmd_log_status_change(log_ctl, log_ctl.ProcessId)
        elif pt == ASCII_DATA_HANDLER:
            if self._m_DataHandlerConnMgr:
                self._m_DataHandlerConnMgr.send_cmd_log_status_change(log_ctl, log_ctl.ProcessId)
        elif pt in (3, ASCII_PARSER, ASCII_CONNECTOR, ASCII_DATA_ROUTER, ASCII_ROUTER):  # ASCII_MANAGER=3
            if self._m_ManagerConnMgr:
                self._m_ManagerConnMgr.send_cmd_log_status_change(log_ctl, log_ctl.ManagerId)
        else:
            _log.debug(1, "Unknown Log Control Cmd")

    SendLogStatus             = send_log_status
    GetLogStatusList          = get_log_status_list
    ReceiveCmdLogStatusChange = receive_cmd_log_status_change

    # ──────────────────────────────────────────
    # 프로세스 사망 처리
    # ──────────────────────────────────────────
    def process_dead(self, proc_name: str, pid: int) -> None:
        _log.error(f"Process Dead {proc_name}")
        self.send_ascii_error(1, f"The process({proc_name}) is killed abnormally.")
        self.remove_pid(pid)

        if proc_name == self.get_process_name(ASCII_MMC_SCHEDULER):
            self._m_MMCGeneratorConnMgr.set_mmc_generator_session(ASCII_MMC_SCHEDULER, None)
            self.init_scheduler_rule_down_status()
            self.start_proc(ASCII_MMC_SCHEDULER)
        elif proc_name == self.get_process_name(ASCII_MMC_GENERATOR):
            self._m_MMCGeneratorConnMgr.set_mmc_generator_session(ASCII_MMC_GENERATOR, None)
            self.init_command_rule_down_status()
            self.start_proc(ASCII_MMC_GENERATOR)
        elif proc_name == self.get_process_name(ASCII_JOB_MONITOR):
            self._m_MMCGeneratorConnMgr.set_mmc_generator_session(ASCII_JOB_MONITOR, None)
            self.start_proc(ASCII_JOB_MONITOR)
        elif proc_name == self.get_process_name(ASCII_RULE_DOWNLOADER):
            self.init_parsing_rule_down_status()
            self.init_mapping_rule_down_status()
            self.start_proc(ASCII_RULE_DOWNLOADER)
        elif proc_name == self.get_process_name(NETFINDER):
            self.start_proc(NETFINDER)
        else:
            _log.error(f"Unknown ProcessName : {proc_name}")

    ProcessDead = process_dead

    # ──────────────────────────────────────────
    # SendInfoChange (overloaded → 타입으로 분기)
    # ──────────────────────────────────────────
    def send_info_change(self, info) -> None:
        if self._m_GuiConnMgr is None:
            return
        self._m_GuiConnMgr.send_info_change(info)

        if isinstance(info, AS_MANAGER_INFO_T) and info.SettingStatus == STOP:
            proc_info = AS_PROCESS_STATUS_T()
            proc_info.ProcessId   = info.ManagerId
            proc_info.ManagerId   = info.ManagerId
            proc_info.Status      = STOP
            proc_info.ProcessType = 3  # ASCII_MANAGER
            self.update_process_info(proc_info)

    SendInfoChange = send_info_change

    def send_data_handler_info_change(self, info: AS_DATA_HANDLER_INFO_T) -> None:
        if info.RunMode == 0 and self._m_ManagerConnMgr:
            self._m_ManagerConnMgr.send_data_handler_info_change(info)

    SendDataHandlerInfoChange = send_data_handler_info_change

    # ──────────────────────────────────────────
    # Rule Down 상태 관리
    # ──────────────────────────────────────────
    def get_parsing_rule_down_status(self)    -> bool: return self._m_ParsingRuleDownLoading
    def get_mapping_rule_down_status(self)    -> bool: return self._m_MappingRuleDownLoading
    def get_scheduler_rule_down_status(self)  -> bool: return self._m_SchedulerRuleDownLoading
    def get_command_rule_down_status(self)    -> bool: return self._m_CommandRuleDownLoading
    def init_parsing_rule_down_status(self)   -> None: self._m_ParsingRuleDownLoading   = False
    def init_mapping_rule_down_status(self)   -> None: self._m_MappingRuleDownLoading   = False
    def init_scheduler_rule_down_status(self) -> None: self._m_SchedulerRuleDownLoading = False
    def init_command_rule_down_status(self)   -> None: self._m_CommandRuleDownLoading   = False

    GetParsingRuleDownStatus   = get_parsing_rule_down_status
    GetMappingRuleDownStatus   = get_mapping_rule_down_status
    GetSchedulerRuleDownStatus = get_scheduler_rule_down_status
    GetCommandRuleDownStatus   = get_command_rule_down_status
    InitParsingRuleDownStatus   = init_parsing_rule_down_status
    InitMappingRuleDownStatus   = init_mapping_rule_down_status
    InitSchedulerRuleDownStatus = init_scheduler_rule_down_status
    InitCommandRuleDownStatus   = init_command_rule_down_status

    def cmd_parsing_rule_down(self) -> None:
        self._m_ParsingRuleDownLoading = True
        _log.debug(1, "Receive Parsing RuleDown Cmd")
        if self._m_RuleDownLoaderConnMgr:
            self._m_RuleDownLoaderConnMgr.send_cmd_parsing_rule_down()
        if self._m_IsActive and self._m_ServerConnMgr:
            self._m_ServerConnMgr.send_db_sync_kind(CMD_PARSING_RULE_DOWN)

    def recv_parsing_rule_down_result(self, ack: AS_ASCII_ACK_T) -> None:
        _log.debug(1, f"Receive Parsing Rule Down Ack Result : {'OK' if ack.ResultMode else 'Fail'}")
        self._m_ParsingRuleDownLoading = False
        if self._m_GuiConnMgr:
            self._m_GuiConnMgr.recv_parsing_rule_down_result(ack)
        if ack.ResultMode and self._m_ManagerConnMgr:
            self._m_ManagerConnMgr.send_cmd_parsing_rule_down()

    def cmd_mapping_rule_down(self) -> None:
        self._m_MappingRuleDownLoading = True
        _log.debug(1, "Receive MappingRuleDown Cmd")
        if self._m_RuleDownLoaderConnMgr:
            self._m_RuleDownLoaderConnMgr.send_cmd_mapping_rule_down()
        if self._m_IsActive and self._m_ServerConnMgr:
            self._m_ServerConnMgr.send_db_sync_kind(CMD_MAPPING_RULE_DOWN)

    def recv_mapping_rule_down_result(self, ack: AS_ASCII_ACK_T) -> None:
        _log.debug(1, f"Receive MappingRule Down Ack Result : {'OK' if ack.ResultMode else 'Fail'}")
        self._m_MappingRuleDownLoading = False
        if self._m_GuiConnMgr:
            self._m_GuiConnMgr.recv_mapping_rule_down_result(ack)
        if ack.ResultMode and self._m_ManagerConnMgr:
            self._m_ManagerConnMgr.send_cmd_mapping_rule_down()

    def cmd_scheduler_rule_down(self) -> None:
        _log.debug(1, "Receive Scheduler RuleDown Cmd")
        self._m_SchedulerRuleDownLoading = True
        if self._m_MMCGeneratorConnMgr:
            self._m_MMCGeneratorConnMgr.send_cmd_scheduler_rule_down()
        if self._m_IsActive and self._m_ServerConnMgr:
            self._m_ServerConnMgr.send_db_sync_kind(CMD_SCHEDULER_RULE_DOWN)

    def recv_scheduler_rule_down_result(self, ack: AS_ASCII_ACK_T) -> None:
        _log.debug(1, f"Receive Scheduler Rule Down Ack Result : {'OK' if ack.ResultMode else 'Fail'}")
        self._m_SchedulerRuleDownLoading = False
        if self._m_GuiConnMgr:
            self._m_GuiConnMgr.recv_scheduler_rule_down_result(ack)

    def cmd_command_rule_down(self) -> None:
        _log.debug(1, "Receive Command RuleDown Cmd")
        self._m_CommandRuleDownLoading = True
        if self._m_MMCGeneratorConnMgr:
            self._m_MMCGeneratorConnMgr.send_cmd_command_rule_down()
        if self._m_IsActive and self._m_ServerConnMgr:
            self._m_ServerConnMgr.send_db_sync_kind(CMD_COMMAND_RULE_DOWN)

    def recv_command_rule_down_result(self, ack: AS_ASCII_ACK_T) -> None:
        _log.debug(1, f"Receive Command Rule Down Ack Result : {'OK' if ack.ResultMode else 'Fail'}")
        self._m_CommandRuleDownLoading = False
        if self._m_GuiConnMgr:
            self._m_GuiConnMgr.recv_command_rule_down_result(ack)

    CmdParsingRuleDown        = cmd_parsing_rule_down
    RecvParsingRuleDownResult = recv_parsing_rule_down_result
    CmdMappingRuleDown        = cmd_mapping_rule_down
    RecvMappingRuleDownResult = recv_mapping_rule_down_result
    CmdSchedulerRuleDown      = cmd_scheduler_rule_down
    RecvSchedulerRuleDownResult = recv_scheduler_rule_down_result
    CmdCommandRuleDown        = cmd_command_rule_down
    RecvCommandRuleDownResult = recv_command_rule_down_result

    # ──────────────────────────────────────────
    # Garbage 정리
    # ──────────────────────────────────────────
    def _mmc_queue_garbage_clear(self) -> None:
        with self._m_MMCReqQueueGarbageListLock:
            _log.debug(5, f"Garbage Size : {len(self._m_MMCReqQueueGarbageList)}")
            self._m_MMCReqQueueGarbageList.clear()

    def _insert_garbage_mmc_queue(self, req_queue) -> None:
        with self._m_MMCReqQueueGarbageListLock:
            self._m_MMCReqQueueGarbageList.append(req_queue)

    MMCQueueGarbageClear = _mmc_queue_garbage_clear
    InsertGarbageMMCQueue = _insert_garbage_mmc_queue

    # ──────────────────────────────────────────
    # 타이머 콜백
    # ──────────────────────────────────────────
    def receive_time_out(self, reason: int, extra_reason=None) -> None:
        if reason == MMCQUEUE_GABAGE_CLEAR:
            self._mmc_queue_garbage_clear()
            self.set_timer(10, MMCQUEUE_GABAGE_CLEAR)
        elif reason == MMCRESPONSE_GABAGE_CLEAR:
            self._mmc_response_garbage_clear()
            self.set_timer(120, MMCRESPONSE_GABAGE_CLEAR)
        else:
            _log.debug(3, f"Unknown Time Out : {reason}")

    ReceiveTimeOut = receive_time_out

    def _mmc_response_garbage_clear(self) -> None:
        with self._m_ExtMMCReqWaitMapLock:
            cur = FrTime(); cur.set()
            now = cur.get_time()

            for gid in list(self._m_MMCResultStoredMap.keys()):
                stored = self._m_MMCResultStoredMap[gid]
                if stored.IssuedTime + DEFAULT_GABAGE_CLEAR_INTERVAL < now:
                    stored.ResultEndTime = cur.get_time_string()
                    stored.ResultMode    = R_ERROR
                    stored.ResultMsg    += "\nTimeOver"
                    ext = self._m_ExtMMCReqWaitMap.pop(stored.Gid, None)
                    self._insert_mmc_result_stored(stored)
                    del self._m_MMCResultStoredMap[gid]

            for mid in list(self._m_ExtMMCReqWaitMap.keys()):
                ext_req = self._m_ExtMMCReqWaitMap[mid]
                if ext_req.IssuedTime + DEFAULT_GABAGE_CLEAR_INTERVAL < now:
                    if ext_req.MmcInfo.responseMode in (SAVE_AND_RESPONSE, ONLY_SAVE_RESPONSE):
                        res = self._m_MMCResultStoredMap.pop(ext_req.GId, None)
                        if res is None:
                            res = MMCResultStored()
                            res.Gid           = ext_req.GId
                            res.ExtId         = ext_req.Id
                            res.IssuedTime    = ext_req.IssuedTime
                            res.IssuedTimeStr = ext_req.IssuedTimeStr
                            res.ResultStartTime = cur.get_time_string()
                            res.ResultEndTime   = cur.get_time_string()
                            res.ResultMode      = R_ERROR
                            res.MmcInfo.__dict__.update(ext_req.MmcInfo.__dict__)
                            res.ResultMsg = "TimeOver"
                        else:
                            res.ResultEndTime = cur.get_time_string()
                            res.ResultMode    = R_ERROR
                            res.ResultMsg    += "\nTimeOver"
                        self._insert_mmc_result_stored(res)
                    del self._m_ExtMMCReqWaitMap[mid]

    MMCResponseGabageClear = _mmc_response_garbage_clear

    # ──────────────────────────────────────────
    # Parser/Connector Rule Change
    # ──────────────────────────────────────────
    def parser_rule_change(self, change_info: AS_RULE_CHANGE_INFO_T) -> None:
        _log.debug(3, f"Receive Parser Rule Change : ({change_info.ManagerId}:{change_info.ProcessId}:"
                   f"{change_info.RuleId}:{change_info.MmcIdentType})")
        if not AsciiServerWorld.m_DbManager.recv_info_change(change_info):
            return
        self._m_ManagerConnMgr.parser_rule_change(change_info)

    def connector_desc_change(self, info: AS_CONNECTOR_DESC_CHANGE_INFO_T) -> None:
        if not AsciiServerWorld.m_DbManager.recv_info_change(info):
            return
        self._m_ManagerConnMgr.connector_desc_change(info)

    ParserRuleChange    = parser_rule_change
    ConnectorDescChange = connector_desc_change

    def get_router_info(self, req: AS_ROUTER_INFO_REQ_T, router_info: RouterInfoList) -> None:
        self._m_ManagerConnMgr.get_router_info(req, router_info)

    GetRouterInfo = get_router_info

    # ──────────────────────────────────────────
    # 프로세스 상태 업데이트
    # ──────────────────────────────────────────
    def update_process_info(self, proc_info: AS_PROCESS_STATUS_T) -> None:
        _log.debug(1, f"procName:{proc_info.ProcessId} managerName:{proc_info.ManagerId} "
                   f"status:{proc_info.Status}")

        info_map = self._m_ProcStatusMap.get(proc_info.ManagerId)

        if info_map is not None:
            old = info_map.pop(proc_info.ProcessId, None)
        else:
            info_map = ProcStatusInfoMap()
            self._m_ProcStatusMap[proc_info.ManagerId] = info_map

        if proc_info.Status == START:
            import copy
            info_map[proc_info.ProcessId] = copy.deepcopy(proc_info)
        elif proc_info.Status == STOP:
            if proc_info.ProcessType == 3:  # ASCII_MANAGER
                del self._m_ProcStatusMap[proc_info.ManagerId]

        if self._m_GuiConnMgr:
            self._m_GuiConnMgr.send_info_change(proc_info)

    UpdateProcessInfo = update_process_info

    # ──────────────────────────────────────────
    # RecvInfoChange (다형성 → 타입 분기)
    # ──────────────────────────────────────────
    def recv_info_change(self, info, result_msg_holder: list = None) -> bool:
        """
        result_msg_holder: [0] = result_msg str (C++ char* 대체)
        """
        msg = [""]
        ok = self._recv_info_change_impl(info, msg)
        if result_msg_holder is not None:
            result_msg_holder[0] = msg[0]
        return ok

    def _recv_info_change_impl(self, info, msg: list) -> bool:
        from Common.AsUtil import AsUtil

        def _db_change(info_obj):
            if not AsciiServerWorld.m_DbManager.recv_info_change(info_obj):
                msg[0] = AsciiServerWorld.m_DbManager.get_error_msg()
                return False
            return True

        if isinstance(info, AS_MANAGER_INFO_T):
            if info.RequestStatus not in (CREATE_DATA, UPDATE_DATA, DELETE_DATA):
                msg[0] = f"Unknown Manager Info Change Req Status : {info.RequestStatus}"
                return False
            if not _db_change(info): return False
            if not self._m_ManagerConnMgr.recv_info_change(info, msg): return False
            if self._m_IsActive and self._m_ServerConnMgr:
                self._m_ServerConnMgr.send_db_sync_kind(MANAGER_MODIFY)

        elif isinstance(info, AS_CONNECTOR_INFO_T):
            if info.RequestStatus not in (CREATE_DATA, UPDATE_DATA, DELETE_DATA):
                msg[0] = f"Unknown Connector Info Change Req Status : {info.RequestStatus}"
                return False
            cur = FrTime(); cur.set()
            if info.RequestStatus == CREATE_DATA:
                info.CreateDate = info.ModifyDate = info.LastActionDate = cur.get_time_string()
                info.LastActionType = AsUtil.GetEnumTypeString_ACTION(1)  # ACT_CREATE
            elif info.RequestStatus == UPDATE_DATA:
                info.ModifyDate = info.LastActionDate = cur.get_time_string()
                info.LastActionType = AsUtil.GetEnumTypeString_ACTION(2)  # ACT_MODIFY
            if not _db_change(info): return False
            if not self._m_ManagerConnMgr.recv_info_change(info, msg): return False
            if self._m_IsActive and self._m_ServerConnMgr:
                self._m_ServerConnMgr.send_db_sync_kind(CONNECTOR_MODIFY)

        elif isinstance(info, AS_CONNECTION_INFO_T):
            if info.RequestStatus not in (CREATE_DATA, UPDATE_DATA, DELETE_DATA):
                msg[0] = f"Unknown Connection Info Change Req Status : {info.RequestStatus}"
                return False
            if not _db_change(info): return False
            if not self._m_ManagerConnMgr.recv_info_change(info, msg): return False
            if self._m_IsActive and self._m_ServerConnMgr:
                self._m_ServerConnMgr.send_db_sync_kind(CONNECTION_MODIFY)

        elif isinstance(info, AS_CONNECTION_INFO_LIST_T):
            if info.RequestStatus != CREATE_DATA:
                msg[0] = f"Unknown Connection Info Change Req Status : {info.RequestStatus}"
                return False
            for item in info.InfoList[:info.Size]:
                if not _db_change(item): return False
                if not self._m_ManagerConnMgr.recv_info_change(item, msg): return False
            if self._m_IsActive and self._m_ServerConnMgr:
                self._m_ServerConnMgr.send_db_sync_kind(CONNECTION_LIST_MODIFY)

        elif isinstance(info, AS_DATA_HANDLER_INFO_T):
            if info.RequestStatus not in (CREATE_DATA, UPDATE_DATA, DELETE_DATA):
                msg[0] = f"Unknown Data Handler Info Change Req Status : {info.RequestStatus}"
                return False
            if not _db_change(info): return False
            if not self._m_DataHandlerConnMgr.recv_info_change(info, msg): return False
            if self._m_IsActive and self._m_ServerConnMgr:
                self._m_ServerConnMgr.send_db_sync_kind(DATAHANDLER_MODIFY)

        elif isinstance(info, AS_SUB_PROC_INFO_T):
            if info.RequestStatus not in (CREATE_DATA, UPDATE_DATA, DELETE_DATA):
                msg[0] = f"Unknown Sub ProcInfo Change Req Status : {info.RequestStatus}"
                return False
            if not _db_change(info): return False
            if not self._m_SubProcConnMgr.recv_info_change(info, msg): return False
            if self._m_IsActive and self._m_ServerConnMgr:
                self._m_ServerConnMgr.send_db_sync_kind(DATAHANDLER_MODIFY)

        elif isinstance(info, AS_COMMAND_AUTHORITY_INFO_T):
            if info.RequestStatus not in (CREATE_DATA, UPDATE_DATA, DELETE_DATA):
                msg[0] = f"Unknown Command Authority Info Change Req Status : {info.RequestStatus}"
                return False
            if not _db_change(info): return False
            if info.RequestStatus == CREATE_DATA:
                import copy
                tmp = copy.deepcopy(info)
                self._m_CommandAuthorityInfoMap[info.Id] = tmp
                tmp.RequestStatus = WAIT_NO
            elif info.RequestStatus == UPDATE_DATA:
                if info.OldId not in self._m_CommandAuthorityInfoMap:
                    msg[0] = f"Can't Find Command Authority Id : {info.OldId}"
                    return False
                del self._m_CommandAuthorityInfoMap[info.OldId]
                import copy
                tmp = copy.deepcopy(info)
                tmp.OldId = ""
                self._m_CommandAuthorityInfoMap[info.Id] = tmp
                tmp.RequestStatus = WAIT_NO
            elif info.RequestStatus == DELETE_DATA:
                if info.Id not in self._m_CommandAuthorityInfoMap:
                    msg[0] = f"Can't Find Command Authority Id : {info.Id}"
                    return False
                del self._m_CommandAuthorityInfoMap[info.Id]
            self.send_info_change(info)
            if self._m_IsActive and self._m_ServerConnMgr:
                self._m_ServerConnMgr.send_db_sync_kind(COMMAND_AUTHORITY_MODIFY)
        else:
            msg[0] = f"Unknown info type : {type(info)}"
            return False

        return True

    RecvInfoChange = recv_info_change

    # ──────────────────────────────────────────
    # 이벤트 알림
    # ──────────────────────────────────────────
    def notify_event(self, session_type: int, msg_id: int) -> None:
        if session_type in (ASCII_MMC_GENERATOR, ASCII_MMC_SCHEDULER, ASCII_JOB_MONITOR):
            if self._m_MMCGeneratorConnMgr:
                self._m_MMCGeneratorConnMgr.notify_event(session_type, msg_id)

    NotifyEvent = notify_event

    def recv_process_control(self, proc_ctl: AS_PROC_CONTROL_T) -> None:
        pt = proc_ctl.ProcessType
        if pt in (3, ASCII_CONNECTOR):   # ASCII_MANAGER
            if self._m_ManagerConnMgr:
                self._m_ManagerConnMgr.recv_process_control(proc_ctl)
        elif pt == ASCII_DATA_HANDLER:
            if self._m_DataHandlerConnMgr:
                self._m_DataHandlerConnMgr.recv_process_control(proc_ctl)
        elif pt == ASCII_SUB_PROCESS:
            if self._m_SubProcConnMgr:
                self._m_SubProcConnMgr.recv_process_control(proc_ctl)

    def recv_session_control(self, session_ctl: AS_SESSION_CONTROL_T) -> None:
        if self._m_ManagerConnMgr:
            self._m_ManagerConnMgr.send_session_control(session_ctl)

    RecvProcessControl = recv_process_control
    RecvSessionControl = recv_session_control

    # ──────────────────────────────────────────
    # DB Sync / Standby
    # ──────────────────────────────────────────
    def standby_server_run(self) -> None:
        self._m_ServerConnection = None
        self._m_IsActive = True
        _log.debug(1, "StandBy Server Run")
        if AsciiServerWorld.m_DbManager:
            AsciiServerWorld.m_DbManager.disable_manager_from_ip(self._m_ActiveServerIp)
        if not self._init_active_server():
            import sys
            sys.exit(0)

    StandByServerRun = standby_server_run

    def update_db_sync_time(self, info_list: Optional[AS_DB_SYNC_INFO_LIST_T] = None) -> None:
        if info_list:
            import copy
            self._m_DbSyncInfoList = copy.deepcopy(info_list)
            self._m_DbSyncInfoList.ActiveSvrName = self._m_ProcName
        else:
            if AsciiServerWorld.m_DbManager:
                AsciiServerWorld.m_DbManager.get_db_sync_info(self._m_DbSyncInfoList)
            if self._m_ServerConnection:
                self._m_DbSyncInfoList.StandbySvrName = self._m_ProcName
                self._m_DbSyncInfoList.StandbyDb = (
                    f"{self._m_DbUserId}/{self._m_DbPassword}@{self._m_DbTns}")
                self._m_ServerConnection.send_packet(
                    0x9999,  # AS_DB_SYNC_INFO_LIST msgid: 추후 실제 상수로 교체
                    self._m_DbSyncInfoList)

    UpdateDbSyncTime = update_db_sync_time

    def get_db_sync_info(self) -> Optional[AS_DB_SYNC_INFO_LIST_T]:
        if self._m_ServerConnMgr and self._m_ServerConnMgr.is_stand_by_server():
            return self._m_DbSyncInfoList
        return None

    GetDbSyncInfo = get_db_sync_info

    # ──────────────────────────────────────────
    # MMC Result 저장 (thread-safe)
    # ──────────────────────────────────────────
    def _insert_mmc_result_stored(self, result: MMCResultStored) -> None:
        with self._m_MMCResultStoredListLock:
            self._m_MMCResultStoredList.append(result)

    def _get_mmc_result_stored(self) -> Optional[MMCResultStored]:
        with self._m_MMCResultStoredListLock:
            if self._m_MMCResultStoredList:
                return self._m_MMCResultStoredList.pop(0)
        return None

    InsertMMCResultStored = _insert_mmc_result_stored
    GetMMCResultStored    = _get_mmc_result_stored

    def _mmc_result_stored_thread(self) -> None:
        """C++: MMCResultStoredThread()"""
        ptr: Optional[MMCResultStored] = None
        while self._m_ThreadStatus:
            if self._m_MMCResultDbManager:
                if ptr is None:
                    ptr = self._get_mmc_result_stored()
                if ptr:
                    if self._m_MMCResultDbManager.insert_mmc_result(ptr):
                        _log.debug(1, f"success saving mmc result([{ptr.MmcInfo.ne}]:[{ptr.MmcInfo.mmc}])")
                        ptr = None
                    else:
                        err = self._m_MMCResultDbManager.get_error_msg()
                        if self.is_db_conn_err(err):
                            _log.error("--- Fail to save mmc result(DB connection error)")
                            self._init_mmc_result_db_manager()
                            time.sleep(3)
                        else:
                            _log.error("--- Fail to save mmc result")
                            ptr.print()
                            ptr = None
                else:
                    time.sleep(1)
            else:
                time.sleep(50)
                self._init_mmc_result_db_manager()

    MMCResultStoredThread = _mmc_result_stored_thread

    def _init_mmc_result_db_manager(self) -> bool:
        self._m_MMCResultDbManager = None
        from DbManager import DbManager
        self._m_MMCResultDbManager = DbManager()
        if not self._m_MMCResultDbManager.init_db_manager(
                self._m_MmcStoredDbUserId, self._m_MmcStoredDbPasswd,
                self._m_MmcStoredDbTns, self._m_DbIp, self._m_DbPort):
            _log.error(f"Db Connection Error(MMC Result Stored DB) : "
                       f"[{self._m_MmcStoredDbUserId}/{self._m_MmcStoredDbPasswd}@{self._m_MmcStoredDbTns}]")
            self._m_MMCResultDbManager = None
            return False
        return True

    InitMMCResultDbManager = _init_mmc_result_db_manager

    def is_db_conn_err(self, ora_err_msg: str) -> bool:
        return any(code in ora_err_msg for code in DB_CONN_ERRORS)

    IsDbConnErr = is_db_conn_err

    # ──────────────────────────────────────────
    # DataHandler / DataRouter Init
    # ──────────────────────────────────────────
    def recv_init_info(self, init_info) -> None:
        if isinstance(init_info, AS_DATA_HANDLER_INIT_T):
            _log.debug(1, f"Recv DataHandler Init Cmd : {init_info.DataHandlerId}")
            if self._m_DataHandlerConnMgr:
                self._m_DataHandlerConnMgr.recv_init_info(init_info)
        elif isinstance(init_info, AS_DATA_ROUTING_INIT_T):
            _log.debug(1, f"Recv DataRouter Init Cmd : {init_info.DataHandlerId}")
            if self._m_ManagerConnMgr:
                self._m_ManagerConnMgr.recv_init_info(init_info)

    RecvInitInfo = recv_init_info

    # ──────────────────────────────────────────
    # ConnectorInfo 조회
    # ──────────────────────────────────────────
    def get_connector_info(self, connector_id: str):
        return self._m_ManagerConnMgr.find_connector_info(connector_id) if self._m_ManagerConnMgr else None

    GetConnectorInfo = get_connector_info

    # ──────────────────────────────────────────
    # Session 설정 조회
    # ──────────────────────────────────────────
    def _get_session_cfg(self, session_type: int) -> Optional[AS_SESSION_CFG_T]:
        return self._m_AsSessionCfgMap.get(session_type)

    def get_session_send_buf_size(self, t: int) -> int:
        cfg = self._get_session_cfg(t)
        return cfg.SocketSendBuf if cfg else -1

    def get_session_recv_buf_size(self, t: int) -> int:
        cfg = self._get_session_cfg(t)
        return cfg.SocketRecvBuf if cfg else -1

    def get_session_check_time_out(self, t: int) -> int:
        cfg = self._get_session_cfg(t)
        return cfg.SocketTimeout if cfg else -1

    def get_session_dis_con_count(self, t: int) -> int:
        cfg = self._get_session_cfg(t)
        return cfg.MaxDisConCount if cfg else -1

    def get_writerable_check(self, t: int) -> bool:
        cfg = self._get_session_cfg(t)
        return bool(cfg.CheckWriteFlag) if cfg else False

    def get_session_buf_size(self, t: int) -> int:
        cfg = self._get_session_cfg(t)
        return cfg.SessionBufSize if cfg else -1

    GetSessionSendBufSize  = get_session_send_buf_size
    GetSessionRecvBufSize  = get_session_recv_buf_size
    GetSessionCheckTimeOut = get_session_check_time_out
    GetSessionDisConCount  = get_session_dis_con_count
    GetWriterableCheck     = get_writerable_check
    GetSessionBufSize      = get_session_buf_size

    def get_as_system_info_map(self, info_map: dict) -> None:
        info_map.update(self._m_AsSystemInfoMap)

    def get_as_session_cfg_map(self, info_map: dict) -> None:
        info_map.update(self._m_AsSessionCfgMap)

    GetAsSystemInfoMap = get_as_system_info_map
    GetAsSessionCfgMap = get_as_session_cfg_map

    # ──────────────────────────────────────────
    # Session 설정 초기화
    # ──────────────────────────────────────────
    def _init_session_cfg(self) -> None:
        for s_type, buf_adj in [
            (SESSION_TYPE_GUI, 0),
            (SESSION_TYPE_MMC, 200),
            (SESSION_TYPE_MGR, 200),
        ]:
            cfg = AS_SESSION_CFG_T()
            cfg.SessionType       = s_type
            cfg.SessionBufSize    = self._m_DefaultSessionBuf - buf_adj
            cfg.SocketSendBuf     = self._m_DefaultMaxSockBuf - buf_adj
            cfg.SocketRecvBuf     = DEFAULT_SOCK_BUF_SIZE
            cfg.SocketTimeout     = DEFAULT_SOCK_CHECK_TIME_OUT
            cfg.MaxDisConCount    = -1
            cfg.CheckWriteFlag    = 1
            cfg.CheckDisConCntFlag = 0
            self._adjust_session_cfg(cfg)
            self._m_AsSessionCfgMap[s_type] = cfg

    InitSessionCfg = _init_session_cfg

    def _adjust_session_cfg(self, cfg: AS_SESSION_CFG_T) -> None:
        if cfg.CheckWriteFlag not in (0, 1):
            cfg.CheckWriteFlag = 0
        if cfg.CheckDisConCntFlag not in (0, 1):
            cfg.CheckDisConCntFlag = 0
        if cfg.SessionBufSize < self._m_DefaultSessionBuf:
            cfg.SessionBufSize = self._m_DefaultSessionBuf

        max_send = getattr(self._m_SystemInfo, 'm_MaxSendBuf', DEFAULT_MAX_SOCK_BUF)
        max_recv = getattr(self._m_SystemInfo, 'm_MaxRecvBuf', DEFAULT_MAX_SOCK_BUF)

        if cfg.SocketSendBuf > DEFAULT_SOCK_BUF_SIZE:
            if cfg.SocketSendBuf <= max_send:
                cfg.SocketSendBuf = min(cfg.SocketSendBuf, self._m_DefaultMaxSockBuf)
            else:
                cfg.SocketSendBuf = min(max_send, self._m_DefaultMaxSockBuf)
        else:
            cfg.SocketSendBuf = DEFAULT_SOCK_BUF_SIZE

        if cfg.SocketRecvBuf > DEFAULT_SOCK_BUF_SIZE:
            if cfg.SocketRecvBuf <= max_recv:
                cfg.SocketRecvBuf = min(cfg.SocketRecvBuf, self._m_DefaultMaxSockBuf)
            else:
                cfg.SocketRecvBuf = min(max_recv, self._m_DefaultMaxSockBuf)
        else:
            cfg.SocketRecvBuf = DEFAULT_SOCK_BUF_SIZE

        if not (0 <= cfg.SocketTimeout < 1_000_000):
            cfg.SocketTimeout = DEFAULT_SOCK_CHECK_TIME_OUT
        if cfg.MaxDisConCount < 500:
            cfg.MaxDisConCount = -1

    AdjustSessionCfg = _adjust_session_cfg

    def recv_session_cfg(self, cfg: AS_SESSION_CFG_T) -> None:
        if cfg.SessionType not in self._m_AsSessionCfgMap:
            return
        self._adjust_session_cfg(cfg)
        import copy
        self._m_AsSessionCfgMap[cfg.SessionType] = copy.deepcopy(cfg)
        if self._m_GuiConnMgr:
            self._m_GuiConnMgr.send_info_change(self._m_AsSessionCfgMap[cfg.SessionType])

    RecvSessionCfg = recv_session_cfg

    def recv_system_info(self, info: AS_SYSTEM_INFO_T) -> None:
        import copy
        self._m_AsSystemInfoMap[info.ProcessId] = copy.deepcopy(info)
        if self._m_GuiConnMgr:
            self._m_GuiConnMgr.send_info_change(info)

    RecvSystemInfo = recv_system_info

    def session_cfg(self, sock: AsSocket, session_type: int) -> None:
        if self.get_writerable_check(session_type):
            sock.set_send_sock_buf(self.get_session_send_buf_size(session_type))
            t = self.get_session_check_time_out(session_type)
            if t > 0:
                sock.set_write_check_time_out(t)
            sock.set_writerable_check(True)
            sock.set_max_data_buf_size(self.get_session_buf_size(session_type))

    SessionCfg = session_cfg

    # ──────────────────────────────────────────
    # 로그 파일 / 에러 파일
    # ──────────────────────────────────────────
    def log_file_changed_event(self) -> None:
        _log.debug(1, "Log File Change Event")
        super().log_file_changed_event()
        self._error_file_changed()

    LogFileChangedEvent = log_file_changed_event

    def _error_file_changed(self) -> None:
        cur = FrTime(); cur.set()
        fname = (f"{self.get_log_dir()}/{self._m_ProcName}Error_"
                 f"{cur.get_year():04d}{cur.get_month():02d}{cur.get_day():02d}.log")
        _log.debug(3, f"Error File Name : {fname}")
        if self._m_ErrorLogFp:
            self._m_ErrorLogFp.close()
        try:
            self._m_ErrorLogFp = open(fname, "a+", encoding="utf-8")
        except OSError as e:
            _log.error(f"Error Log File ({fname}) Open Error : {e}")

    ErrorFileChanged = _error_file_changed

    # ──────────────────────────────────────────
    # 기타 조회
    # ──────────────────────────────────────────
    def get_manager_info_map(self) -> Optional[ManagerInfoMap]:
        return self._m_ManagerConnMgr.get_manager_info_map() if self._m_ManagerConnMgr else None

    def get_proc_status_map(self) -> ProcStatusMap:
        return self._m_ProcStatusMap

    def get_alive_check_limit_cnt(self) -> int:
        cnt = int(self.get_env_value("SERVER", "alive_check_maxcount") or 0)
        if cnt == 0:
            cnt = 3
        _log.debug(1, f"GetAliveCheckLimitCnt : {cnt}")
        return cnt

    def send_mmc_command_from_status_gui(self, mmc_com: AS_MMC_PUBLISH_T, err_str: list) -> bool:
        return self._m_ManagerConnMgr.send_mmc_command(mmc_com) if self._m_ManagerConnMgr else False

    GetManagerInfoMap              = get_manager_info_map
    GetProcStatusMap               = get_proc_status_map
    GetAliveCheckLimitCnt          = get_alive_check_limit_cnt
    SendMMCCommandFromStatusGui    = send_mmc_command_from_status_gui

    # ──────────────────────────────────────────
    # Ping
    # ──────────────────────────────────────────
    def ping_check(self, ip: str) -> bool:
        import subprocess
        cmd = ["/bin/ping", "-s", str(PING_PACKET_SIZE), "-c", str(PING_ECHO_COUNT), ip]
        _log.debug(1, f"Ping - {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return PING_ALIVE in result.stdout
        except Exception as e:
            _log.error(f"ping_check error : {e}")
            return False

    PingCheck = ping_check

    # ──────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────
    def _config_value_check(self) -> bool:
        checks = [
            (self._m_ProcName,              ASCII_SERVER, "name"),
            (self._m_DbUserId,              ASCII_SERVER, "db_user"),
            (self._m_DbPassword,            ASCII_SERVER, "db_password"),
            (self._m_DbTns,                 ASCII_SERVER, "db_tns"),
        ]
        for val, sec, sub in checks:
            if not val:
                _log.error(f"Can't Find Config Value - Section:{sec}, SubSection:{sub}")
                return False

        int_checks = [
            (self._m_ServerPort,           "server_listen_port"),
            (self._m_GuiPort,              "gui_listen_port"),
            (self._m_ExtPort,              "external_system_listenport"),
            (self._m_DataHandlerPort,      "datahandler_listen_port"),
            (self._m_RouterInfoListenPort, "routerinfo_listen_port"),
            (self._m_NetFinderListenPort,  "netfinder_listen_port"),
            (self._m_StandBySvrListenPort, "standby_listen_port"),
            (self._m_SubProcListenPort,    "subproc_listen_port"),
        ]
        for val, sub in int_checks:
            if not val:
                _log.error(f"Can't Find Config Value - Section:{ASCII_SERVER}, SubSection:{sub}")
                return False
        return True

    def _get_host_name(self) -> str:
        import socket as _socket
        return _socket.gethostname()