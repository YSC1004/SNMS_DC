"""
[변경이력]
2014.07.08  초기 작성
Python 변환: AsWorld.h/.C → AsWorld.py

역할: 프로세스 전역 환경/설정/디렉토리/타이머/로그 관리 클래스
  - C++ frWorld 상속 → Python 독립 클래스 (이벤트루프 asyncio 대응)
  - pthread_mutex → threading.Lock
  - static 멤버 → 클래스 변수
  - frLogger → Python logging 모듈
  - AsWorldTimer/AsWorldLogTimer → asyncio.Task 기반 타이머
"""

import asyncio
import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, TYPE_CHECKING

from Common.AsEnvrion import AsEnvrion
from Common.AsUtil import AsUtil
from Common.CommType import (
    AS_LOG_STATUS_T, AS_CMD_LOG_CONTROL_T, AS_SYSTEM_INFO_T,
    AS_STATUS,
    ASCII_MMC_SCHEDULER, ASCII_MMC_GENERATOR, ASCII_JOB_MONITOR,
    ASCII_DATA_HANDLER, ASCII_MANAGER, ASCII_RULE_DOWNLOADER,
    ASCII_PARSER, ASCII_CONNECTOR, ASCII_DATA_ROUTER, ASCII_ROUTER,
    ASCII_LOG_ROUTER, NETFINDER, ASCII_CM_CMD, SOAP_EMS_AGENT,
    SNMP_SWITCH_CMD, SNMP_ROIP_CMD, SNMP_UPS_CMD, TEST_PROCESS,
    SG_ASCII_CMD_NMS, SG_ASCII_CMD_OPER, HTTP_AGENT_CMD,
    ARG_LOG_DAY, ARG_LOG_HOUR, ARG_LOG_CYCLE,
    STR_UNKNOWN_TYPE,
)

if TYPE_CHECKING:
    from Common.ConnectionMgr import ConnectionMgr

logger = logging.getLogger(__name__)

# 프로세스 타입 → 프로세스명 매핑
_PROC_NAME_MAP: Dict[int, str] = {
    ASCII_MMC_SCHEDULER:  "MmcScheduler",
    ASCII_MMC_GENERATOR:  "MmcGenerator",
    ASCII_JOB_MONITOR:    "JobMonitor",
    ASCII_DATA_HANDLER:   "DataHandler",
    ASCII_MANAGER:        "procNaManager",
    ASCII_RULE_DOWNLOADER:"RuleDownLoader",
    ASCII_PARSER:         "Parser",
    ASCII_CONNECTOR:      "Connector",
    ASCII_DATA_ROUTER:    "DataRouter",
    ASCII_ROUTER:         "Router",
    ASCII_LOG_ROUTER:     "LogRouter",
    NETFINDER:            "NetFinder",
    ASCII_CM_CMD:         "AsciiCmCmd",
    SOAP_EMS_AGENT:       "SoapEMSAgent",
    SNMP_SWITCH_CMD:      "SNMP_SWITCH_CMD",
    SNMP_ROIP_CMD:        "SNMP_ROIP_CMD",
    SNMP_UPS_CMD:         "SNMP_UPS_CMD",
    TEST_PROCESS:         "TEST_PROCESS",
    SG_ASCII_CMD_NMS:     "SG_ASCII_CMD_NMS",
    SG_ASCII_CMD_OPER:    "SG_ASCII_CMD_OPER",
    HTTP_AGENT_CMD:       "HTTP_AGENT_CMD",
}


class AsWorld:
    """
    C++: class AsWorld : public frWorld

    프로세스 전역 싱글턴 역할을 하는 환경 관리 클래스.

    주요 책임:
      - 설정 파일 로드 (AsEnvrion)
      - 디렉토리 경로 관리
      - 타이머 스케줄링 (asyncio.Task)
      - 로그 파일 관리
      - ConnectionMgr 등록/해제 (전역 벡터)
    """

    # ── 클래스(static) 변수 ──────────────────
    _m_start_dir:              str                    = ""
    _m_connection_mgr_vector:  Optional[List["ConnectionMgr"]] = None
    _m_conn_mgr_lock:          threading.Lock         = threading.Lock()

    def __init__(self):
        self._proc_name:          str  = ""
        self._host_name:          str  = ""
        self._process_type:       int  = -1
        self._proc_type:          int  = -5   # 로그 파일용
        self._user_account:       str  = ""

        self._root_dir:           str  = ""
        self._bc_dir:             str  = ""
        self._config_dir:         str  = ""
        self._log_dir:            str  = ""
        self._bin_dir:            str  = ""
        self._unix_socket_dir:    str  = ""
        self._parser_temp_dir:    str  = ""
        self._script_dir:         str  = ""
        self._raw_dir:            str  = ""
        self._rule_dir:           str  = ""
        self._main_rule_dir:      str  = ""
        self._system_dir:         str  = ""
        self._connector_temp_dir: str  = ""
        self._data_handler_dir:   str  = ""
        self._job_monitor_dir:    str  = ""

        self._alive_check_limit:  int  = 5
        self._alive_check_interval: int = 100  # ms

        self._log_status:         AS_LOG_STATUS_T  = AS_LOG_STATUS_T()
        self._system_info:        AS_SYSTEM_INFO_T = AS_SYSTEM_INFO_T()
        self._envrion:            AsEnvrion        = AsEnvrion()

        # 타이머 태스크: {key: asyncio.Task}
        self._timer_tasks:        Dict[int, asyncio.Task] = {}
        self._timer_key_counter:  int = 0

        # 로그 타이머
        self._log_timer_task:     Optional[asyncio.Task] = None

        # SockMgr (미변환 — 플레이스홀더)
        self._sock_mgr_conn_mgr = None
        self._sock_mgr_world    = None

    def __del__(self):
        # 타이머 태스크 취소
        for task in self._timer_tasks.values():
            task.cancel()
        if self._log_timer_task:
            self._log_timer_task.cancel()

    # ──────────────────────────────────────────
    # 프로세스명
    # ──────────────────────────────────────────

    def SetProcName(self, proc_name: str) -> None:
        self._proc_name = proc_name

    def GetProcName(self) -> str:
        return self._proc_name

    # ──────────────────────────────────────────
    # 설정 초기화
    # ──────────────────────────────────────────

    def InitConfig(self) -> bool:
        """
        C++: InitConfig()
        환경변수 NETADAPTER_CONFIG_FILE 에서 설정 파일 경로를 읽어 초기화.
        """
        env = os.environ.get("NETADAPTER_CONFIG_FILE")
        if not env:
            logger.error("Can't find env NETADAPTER_CONFIG_FILE")
            return False

        if not self._envrion.InitConfig(env, True):
            return False

        # start_dir
        AsWorld._m_start_dir = self._envrion.GetEnvValue(
            "COMMON", "netadapter_start_dir_name")
        if not AsWorld._m_start_dir:
            logger.error("Can't find Section: COMMON, SubSection: netadapter_start_dir_name")
            logger.error("Use default netadapter_start_dir_name: [NAA]")
            AsWorld._m_start_dir = "NAA"

        # root_dir
        self._root_dir = AsUtil.GetHomeDir()
        if not self._root_dir:
            logger.error("Can't find home dir (env: HOME)")
            return False
        self._root_dir = str(Path(self._root_dir) / AsWorld._m_start_dir)
        self._root_dir = self._root_dir.rstrip("/")
        self._bin_dir  = self._root_dir + "/Bin"

        logger.debug("Root Dir: %s", self._root_dir)
        logger.debug("Bin Dir : %s", self._bin_dir)

        # alive check 설정
        val = self._envrion.GetEnvValue("COMMON", "alive_check_maxcount")
        self._alive_check_limit = max(int(val) if val.isdigit() else 0, 5)

        val = self._envrion.GetEnvValue("COMMON", "alive_check_interval")
        self._alive_check_interval = max(int(val) if val.isdigit() else 0, 100)

        self._user_account = AsUtil.GetUserName()
        if not self._user_account:
            logger.error("Can't Find env User Account Name")
            return False

        return True

    # ──────────────────────────────────────────
    # 환경 값 조회 (AsEnvrion 위임)
    # ──────────────────────────────────────────

    def GetEnvValue(self, section: str, sub_section: str) -> str:
        return self._envrion.GetEnvValue(section, sub_section)

    def GetEnvValueByType(self, process_type: int, sub_section: str) -> str:
        return self._envrion.GetEnvValue(
            AsUtil.GetProcessTypeString(process_type), sub_section)

    def GetEnvValueList(self, section: str, sub_section: str) -> List[str]:
        return self._envrion.GetEnvValueList(section, sub_section)

    def GetEnvValueListByType(self, process_type: int,
                               sub_section: str) -> List[str]:
        return self._envrion.GetEnvValueList(
            AsUtil.GetProcessTypeString(process_type), sub_section)

    # ──────────────────────────────────────────
    # 디렉토리 경로
    # ──────────────────────────────────────────

    @classmethod
    def GetStartDir(cls) -> str:
        return "/" + cls._m_start_dir

    def GetRootDir(self)          -> str: return self._root_dir
    def GetBinDir(self)           -> str: return self._bin_dir
    def GetBCDir(self)            -> str: return self._root_dir + "/BC"
    def GetConfigDir(self)        -> str: return self._root_dir + "/Config"
    def GetRawDir(self)           -> str: return self._root_dir + "/Raw"
    def GetRuleDir(self)          -> str: return self._root_dir + "/Rule"
    def GetMainRuleDir(self)      -> str: return self._root_dir + "/MainRule"
    def GetProcPosition(self)     -> str: return self.GetBinDir() + "/"
    def GetUserName(self)         -> str: return self._user_account

    def GetLogDir(self) -> str:
        if not self._log_dir:
            self._log_dir = self._root_dir + "/Log"
        return self._log_dir

    def SetLogDir(self, log_dir: str) -> None:
        self._log_dir = log_dir

    def GetSystemDir(self)        -> str: return self._root_dir + "/System"
    def GetUnixSocketDir(self)    -> str: return self.GetSystemDir() + "/UnixSocket"
    def GetParserTempDir(self)    -> str: return self.GetSystemDir() + "/Parser"
    def GetConnectorTempDir(self) -> str: return self.GetSystemDir() + "/Connector"
    def GetDataHandlerDir(self)   -> str: return self.GetSystemDir() + "/DataHandler"
    def GetJobMonitorDir(self)    -> str: return self.GetSystemDir() + "/JobMonitor"

    def GetScriptDir(self) -> str:
        return f"~{self.GetUserName()}{self.GetStartDir()}/Script"

    # ──────────────────────────────────────────
    # 디렉토리 존재 확인 / 생성
    # ──────────────────────────────────────────

    def DirCheck(self, dir_name: str, make_flag: bool = True) -> bool:
        """C++: DirCheck() — 디렉토리 존재 확인, 없으면 생성(make_flag=True)"""
        p = Path(dir_name)
        if p.is_dir():
            return True
        logger.error("Can't Find Dir(%s)", dir_name)
        if make_flag:
            try:
                p.mkdir(parents=True, mode=0o755, exist_ok=True)
                logger.error("Create Dir(%s)", dir_name)
                return True
            except OSError as e:
                logger.error("Dir(%s) Create Error: %s", dir_name, e)
                return False
        else:
            logger.error("Dir(%s) Find Error", dir_name)
            return False

    def AsciiSystemDirCheck(self) -> bool:
        """C++: AsciiSystemDirCheck() — 필수 디렉토리 일괄 점검"""
        checks = [
            (self.GetLogDir(),          True),
            (self.GetBinDir(),          False),
            (self.GetMainRuleDir(),     True),
            (self.GetSystemDir(),       True),
            (self.GetUnixSocketDir(),   True),
            (self.GetParserTempDir(),   True),
            (self.GetConnectorTempDir(),True),
            (self.GetDataHandlerDir(),  True),
            (self.GetJobMonitorDir(),   True),
            (self._root_dir + "/Script", False),
            (self.GetRawDir(),          True),
            (self.GetRuleDir(),         True),
        ]
        for dir_name, make in checks:
            if not self.DirCheck(dir_name, make):
                return False
        return True

    # ──────────────────────────────────────────
    # 타이머 (frWorld::SetTimer → asyncio.Task)
    # ──────────────────────────────────────────

    def SetTimer(self, interval_sec: int, reason: int,
                 extra_reason: object = None) -> int:
        """
        C++: SetTimer(int Interval, int Reason, void* ExtraReason)
        interval_sec 초 후 ReceiveTimeOut(reason, extra_reason) 호출.
        Returns: 타이머 키(int)
        """
        return self._create_timer(interval_sec, reason, extra_reason)

    def SetTimer2(self, mili_sec: int, reason: int,
                  extra_reason: object = None) -> int:
        """C++: SetTimer2(int MiliSec, ...) — 밀리초 단위"""
        return self._create_timer(mili_sec / 1000.0, reason, extra_reason)

    def _create_timer(self, delay_sec: float, reason: int,
                      extra_reason: object) -> int:
        self._timer_key_counter += 1
        key = self._timer_key_counter
        task = asyncio.create_task(
            self._timer_coroutine(delay_sec, reason, extra_reason, key))
        self._timer_tasks[key] = task
        return key

    async def _timer_coroutine(self, delay: float, reason: int,
                                extra_reason: object, key: int) -> None:
        try:
            await asyncio.sleep(delay)
            self._timer_tasks.pop(key, None)
            self.ReceiveTimeOut(reason, extra_reason)
        except asyncio.CancelledError:
            pass

    def CancelTimer(self, key: int) -> bool:
        """C++: CancelTimer(int Key)"""
        task = self._timer_tasks.pop(key, None)
        if task:
            task.cancel()
            return True
        return False

    def ReceiveTimeOut(self, reason: int, extra_reason: object = None) -> None:
        """C++: virtual ReceiveTimeOut() — 하위 클래스에서 오버라이드"""
        logger.debug("ReceiveTimeOut is virtual function (reason=%d)", reason)

    # ──────────────────────────────────────────
    # 로그 파일 관리
    # ──────────────────────────────────────────

    def SetLogFile(self, proc_type: int = -5) -> None:
        """C++: SetLogFile()"""
        self._proc_type = proc_type
        self.LogFileChangedEvent()

    def LogFileChangedEvent(self) -> None:
        """
        C++: LogFileChangedEvent()
        로그 파일명 생성 후 Python logging FileHandler 로 연결.
        ARG_LOG_CYCLE 환경변수로 DAY/HOUR 주기 결정.
        """
        now = datetime.now()
        log_dir = self.GetLogDir()

        log_cycle = os.environ.get(ARG_LOG_CYCLE, ARG_LOG_DAY).upper()
        hour_suffix = f"{now.hour:02d}" if log_cycle == ARG_LOG_HOUR else ""

        proc_type_str = AsUtil.GetProcessTypeString(self._proc_type)
        if proc_type_str == STR_UNKNOWN_TYPE:
            log_file = (f"{log_dir}/{self._proc_name}_"
                        f"{now.year:04d}{now.month:02d}{now.day:02d}"
                        f"{hour_suffix}.log")
        else:
            log_file = (f"{log_dir}/{proc_type_str}_{self._proc_name}_"
                        f"{now.year:04d}{now.month:02d}{now.day:02d}"
                        f"{hour_suffix}.log")

        logger.debug("log change: %s", log_file)
        self._setup_file_handler(log_file)

        # 다음 로그 파일 교체 타이머
        if log_cycle == ARG_LOG_HOUR:
            next_dt = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            next_dt = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        remain_sec = max(int((next_dt - now).total_seconds()) + 20, 1)

        logger.debug("Remain next log change second: %d", remain_sec)

        if self._log_timer_task:
            self._log_timer_task.cancel()
        try:
            self._log_timer_task = asyncio.create_task(
                self._log_timer_coroutine(remain_sec))
        except RuntimeError:
            pass  # 이벤트 루프 없을 때 (초기화 전 호출 등)

    async def _log_timer_coroutine(self, delay: int) -> None:
        try:
            await asyncio.sleep(delay)
            self.LogFileChangedEvent()
        except asyncio.CancelledError:
            pass

    @staticmethod
    def _setup_file_handler(log_file: str) -> None:
        """Python root logger 에 FileHandler 추가"""
        root = logging.getLogger()
        # 기존 FileHandler 교체
        for h in root.handlers[:]:
            if isinstance(h, logging.FileHandler):
                root.removeHandler(h)
                h.close()
        try:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
            root.addHandler(fh)
        except OSError as e:
            logger.error("Log file open error: %s", e)

    # ──────────────────────────────────────────
    # 로그 상태
    # ──────────────────────────────────────────

    def GetLogStatus(self) -> AS_LOG_STATUS_T:
        return self._log_status

    def SetLogStatus(self, process_type: int = -1,
                     process_name: str = "",
                     host_name: str = "") -> None:
        """C++: SetLogStatus(int, string, string)"""
        if process_name:
            self._proc_name     = process_name
            self._host_name     = host_name
            self._process_type  = process_type

        self._log_status.name   = self._proc_name
        self._log_status.status = AS_STATUS.LOG_ADD
        # logs 필드: 현재 logging 레벨 정보 요약
        self._log_status.logs = (
            f"{self._host_name},{AsUtil.GetProcessTypeString(self._process_type)}"
            f"({self._process_type}),{self._proc_name},"
        )

    def ChangeLogStatus(self, log_ctl: AS_CMD_LOG_CONTROL_T) -> AS_LOG_STATUS_T:
        """C++: ChangeLogStatus(AS_CMD_LOG_CONTROL_T*)"""
        self._apply_log_level(log_ctl.Level, log_ctl.Package, log_ctl.Feature)
        self.SetLogStatus()
        return self._log_status

    def _apply_log_level(self, level: int,
                          package: str = "",
                          feature: str = "") -> None:
        """
        C++: frLogger::Enable(Level) → Python logging 레벨 설정.
        level: 0=DEBUG, 1=INFO, 2=WARNING, 3=ERROR, 4=CRITICAL (C++ 관례 매핑)
        """
        py_levels = {0: logging.DEBUG, 1: logging.INFO,
                     2: logging.WARNING, 3: logging.ERROR, 4: logging.CRITICAL}
        py_level = py_levels.get(level, logging.DEBUG)

        if not package:
            logging.getLogger().setLevel(py_level)
        elif not feature:
            logging.getLogger(package).setLevel(py_level)
        else:
            logging.getLogger(f"{package}.{feature}").setLevel(py_level)

    # ──────────────────────────────────────────
    # Alive Check 설정
    # ──────────────────────────────────────────

    def GetAliveCheckLimitCnt(self) -> int:
        return self._alive_check_limit

    def GetProcAliveCheckTime(self) -> int:
        return self._alive_check_interval

    # ──────────────────────────────────────────
    # 프로세스명 조회
    # ──────────────────────────────────────────

    @staticmethod
    def GetProcessName(proc_type: int) -> str:
        return _PROC_NAME_MAP.get(proc_type, "UnKnown_Process")

    # ──────────────────────────────────────────
    # 시스템 정보
    # ──────────────────────────────────────────

    def SetSystemInfo(self, proc_type: int, proc_id: str) -> None:
        """C++: SetSystemInfo() — AsSystemChecker 는 별도 변환 후 연동"""
        self._system_info.ProcessType = proc_type
        self._system_info.ProcessId   = proc_id
        # AsSystemChecker.GetSystemInfo(self._system_info) — 미변환 플레이스홀더
        try:
            from Common.AsSystemChecker import AsSystemChecker
            AsSystemChecker.GetSystemInfo(self._system_info)
        except ImportError:
            logger.debug("AsSystemChecker not yet available")

    # ──────────────────────────────────────────
    # SockMgr 세션 (미변환 플레이스홀더)
    # ──────────────────────────────────────────

    async def EnableSockMgrSession(self, session_name: str, port: int) -> bool:
        """
        C++: EnableSockMgrSession()
        SockMgrConnMgr 변환 완료 후 구현 예정.
        """
        logger.debug("EnableSockMgrSession: session=%s port=%d", session_name, port)
        # TODO: SockMgrConnMgr 변환 후 연동
        return False

    # ──────────────────────────────────────────
    # ConnectionMgr 전역 등록 (static)
    # ──────────────────────────────────────────

    @classmethod
    def GetConnectionMgrVector(cls) -> Optional[List["ConnectionMgr"]]:
        return cls._m_connection_mgr_vector

    @classmethod
    def RegisterConnectionMgr(cls, conn_mgr: "ConnectionMgr") -> None:
        """C++: RegisterConnectionMgr() — pthread_mutex → threading.Lock"""
        with cls._m_conn_mgr_lock:
            if cls._m_connection_mgr_vector is None:
                cls._m_connection_mgr_vector = []
            cls._m_connection_mgr_vector.append(conn_mgr)

    @classmethod
    def DeRegisterConnectionMgr(cls, conn_mgr: "ConnectionMgr") -> bool:
        """C++: DeRegisterConnectionMgr()"""
        if cls._m_connection_mgr_vector is None:
            return False
        with cls._m_conn_mgr_lock:
            try:
                cls._m_connection_mgr_vector.remove(conn_mgr)
                return True
            except ValueError:
                logger.error("DeRegisterConnectionMgr fail: %s",
                             conn_mgr.GetSessionName())
                return False