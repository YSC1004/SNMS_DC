"""
AsWorld.py - C++ AsWorld.h/.C 변환

"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from Common.CommType import (
    AsLogStatus, AsCmdLogControl, AsSystemInfoData, AsStatus,
    ARG_LOG_CYCLE, ARG_LOG_DAY, ARG_LOG_HOUR,
    STR_UNKNOWN_TYPE,
    ASCII_MMC_SCHEDULER, ASCII_MMC_GENERATOR, ASCII_JOB_MONITOR,
    ASCII_DATA_HANDLER, ASCII_MANAGER, ASCII_RULE_DOWNLOADER,
    ASCII_PARSER, ASCII_CONNECTOR, ASCII_DATA_ROUTER, ASCII_ROUTER,
    ASCII_LOG_ROUTER, ASCII_CM_CMD, SOAP_EMS_AGENT,
    SNMP_SWITCH_CMD, SNMP_ROIP_CMD, SNMP_UPS_CMD, TEST_PROCESS,
    SG_ASCII_CMD_NMS, SG_ASCII_CMD_OPER, HTTP_AGENT_CMD,
    ConnectionMgrVector, NETFINDER_SESSION as NETFINDER,
)
from Common.AsEnvrion import AsEnvrion
from Event.fr_world import FrWorld          # ← 실제 FrWorld 사용

if TYPE_CHECKING:
    from Common.AsWorldTimer import AsWorldTimer
    from Common.AsWorldLogTimer import AsWorldLogTimer
    from Common.ConnectionMgr import ConnectionMgr
    from Common.SockMgrConnMgr import SockMgrConnMgr

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# AsWorld
# ──────────────────────────────────────────────
class AsWorld(FrWorld):
    """
    C++ AsWorld 대응.
    프로세스 공통 환경정보, 디렉토리, 타이머, 로그 관리를 담당합니다.
    """

    # ── 클래스 변수 (C++ static 멤버) ─────────
    _start_dir:              str                     = ""
    _connection_mgr_vector:  ConnectionMgrVector | None = None
    _conn_mgr_vector_lock:   threading.Lock          = threading.Lock()

    def __init__(self) -> None:
        super().__init__(mode=0)   # FR_MODE.FR_MAIN = 0

        self._proc_name:    str  = ""
        self._host_name:    str  = ""
        self._process_type: int  = -1
        self._proc_type:    int  = -5
        self._user_account: str  = ""

        self._environ: AsEnvrion = AsEnvrion()

        self._as_world_timer:     AsWorldTimer | None     = None
        self._as_world_log_timer: AsWorldLogTimer | None  = None

        self._log_status: AsLogStatus = AsLogStatus()

        # 디렉토리 캐시
        self._root_dir:            str = ""
        self._bc_dir:              str = ""
        self._config_dir:          str = ""
        self._log_dir:             str = ""
        self._bin_dir:             str = ""
        self._unix_socket_dir:     str = ""
        self._parser_temp_dir:     str = ""
        self._script_dir:          str = ""
        self._raw_dir:             str = ""
        self._rule_dir:            str = ""
        self._main_rule_dir:       str = ""
        self._system_dir:          str = ""
        self._connector_temp_dir:  str = ""
        self._data_handler_dir:    str = ""
        self._job_monitor_dir:     str = ""

        self._alive_check_limit_cnt:    int = 5
        self._alive_check_interval_time: int = 100

        self._sock_mgr_conn_mgr: SockMgrConnMgr | None = None
        self._sock_mgr_world:    Any | None             = None

        self._system_info: AsSystemInfoData = AsSystemInfoData()

    def __del__(self) -> None:
        if self._as_world_timer:
            self._as_world_timer.cancel_timer()
        if self._as_world_log_timer:
            self._as_world_log_timer.cancel_timer()

    # ── 프로세스명 ────────────────────────────
    def set_proc_name(self, proc_name: str) -> None:
        self._proc_name = proc_name

    def get_proc_name(self) -> str:
        return self._proc_name

    # ── 로그 상태 ─────────────────────────────
    def get_log_status(self) -> AsLogStatus:
        return self._log_status

    def change_log_status(self, log_ctl: AsCmdLogControl) -> AsLogStatus:
        self._change_log_level(log_ctl.level, log_ctl.package, log_ctl.feature)
        self._set_log_status()
        return self._log_status

    def _change_log_level(self, level: int, package: str = "", feature: str = "") -> None:
        """로그 레벨 변경 (frLogger::Enable 대응 → Python logging 레벨 조정)."""
        root = logging.getLogger()
        if not package:
            root.setLevel(level)
        elif not feature:
            logging.getLogger(package).setLevel(level)
        else:
            logging.getLogger(f"{package}.{feature}").setLevel(level)

    def set_log_status(self, process_type: int = -1,
                       process_name: str = "",
                       host_name: str = "") -> None:
        """C++ SetLogStatus(int, string, string) 대응."""
        if process_type != -1:
            self._process_type = process_type
        if process_name:
            self._proc_name = process_name
        if host_name:
            self._host_name = host_name
        self._set_log_status()

    def _set_log_status(self) -> None:
        self._log_status.name   = self._proc_name
        self._log_status.status = AsStatus.LOG_ADD

    # ── 타이머 ───────────────────────────────
    def set_timer(self, interval: int, reason: int,
                  extra_reason: Any = None) -> int:
        """interval(초) 후 receive_timeout(reason) 호출."""
        from Common.AsWorldTimer import AsWorldTimer
        if self._as_world_timer is None:
            self._as_world_timer = AsWorldTimer(self)
        return self._as_world_timer.set_timer(interval, reason, extra_reason)

    def set_timer2(self, mili_sec: int, reason: int,
                   extra_reason: Any = None) -> int:
        """mili_sec(밀리초) 후 receive_timeout(reason) 호출."""
        from Common.AsWorldTimer import AsWorldTimer
        if self._as_world_timer is None:
            self._as_world_timer = AsWorldTimer(self)
        return self._as_world_timer.set_timer2(mili_sec, reason, extra_reason)

    def cancel_timer(self, key: int) -> bool:
        if self._as_world_timer:
            return self._as_world_timer.cancel_timer(key)
        return False

    def receive_timeout(self, reason: int, extra_reason: Any = None) -> None:
        """FrWorld.receive_timeout 오버라이드 — 서브클래스에서 추가 오버라이드 가능."""
        logger.debug("receive_timeout: reason=%d (virtual)", reason)

    # ── 환경 설정 초기화 ──────────────────────
    def init_config(self) -> bool:
        """
        C++ InitConfig() 대응.
        환경변수 NETADAPTER_CONFIG_FILE 로부터 설정을 읽습니다.
        """
        cfg_file = os.environ.get("NETADAPTER_CONFIG_FILE")
        if not cfg_file:
            logger.error("Can't find env NETADAPTER_CONFIG_FILE")
            return False

        if not self._environ.init_config(cfg_file, True):
            return False

        AsWorld._start_dir = self._get_env_value("COMMON", "netadapter_start_dir_name")
        if not AsWorld._start_dir:
            logger.error("Can't find Section:COMMON, SubSection:netadapter_start_dir_name")
            logger.error("Use default netadapter_start_dir_name: [NAA]")
            AsWorld._start_dir = "NAA"

        home = os.environ.get("HOME", "")
        if not home:
            logger.error("Can't find home dir (env: HOME)")
            return False

        self._root_dir = str(Path(home) / AsWorld._start_dir).rstrip("/")
        self._bin_dir  = self._root_dir + "/Bin"

        logger.debug("Root Dir: %s", self._root_dir)
        logger.debug("Bin  Dir: %s", self._bin_dir)

        cnt = self._get_env_value("COMMON", "alive_check_maxcount")
        self._alive_check_limit_cnt = max(int(cnt) if cnt.isdigit() else 0, 5)

        itv = self._get_env_value("COMMON", "alive_check_interval")
        self._alive_check_interval_time = max(int(itv) if itv.isdigit() else 0, 100)

        self._user_account = os.environ.get("USER") or os.environ.get("LOGNAME", "")
        if not self._user_account:
            logger.error("Can't Find env User Account Name")
            return False

        return True

    # ── 환경값 조회 ───────────────────────────
    def _get_env_value(self, section: str, sub_section: str,
                       env_values: list[str] | None = None) -> str:
        if env_values is not None:
            return self._environ.get_env_value_list(section, sub_section, env_values)
        return self._environ.get_env_value(section, sub_section)

    def get_env_value(self, section_or_type, sub_section: str,
                      env_values: list[str] | None = None):
        """
        section_or_type: str(섹션명) 또는 int(ProcessType)
        """
        if isinstance(section_or_type, int):
            section = self.get_process_name(section_or_type)
        else:
            section = section_or_type
        return self._get_env_value(section, sub_section, env_values)

    # ── 디렉토리 접근자 ───────────────────────
    @staticmethod
    def get_start_dir() -> str:
        return "/" + AsWorld._start_dir

    def get_root_dir(self)         -> str: return self._root_dir
    def get_bin_dir(self)          -> str: return self._bin_dir
    def get_proc_position(self)    -> str: return self._bin_dir + "/"
    def get_user_name(self)        -> str: return self._user_account

    def get_bc_dir(self)           -> str:
        self._bc_dir = self._root_dir + "/BC";          return self._bc_dir
    def get_config_dir(self)       -> str:
        self._config_dir = self._root_dir + "/Config";  return self._config_dir
    def get_log_dir(self)          -> str:
        if not self._log_dir:
            self._log_dir = self._root_dir + "/Log"
        return self._log_dir
    def set_log_dir(self, log_dir: str) -> None:
        self._log_dir = log_dir
    def get_raw_dir(self)          -> str:
        self._raw_dir = self._root_dir + "/Raw";        return self._raw_dir
    def get_rule_dir(self)         -> str:
        self._rule_dir = self._root_dir + "/Rule";      return self._rule_dir
    def get_main_rule_dir(self)    -> str:
        self._main_rule_dir = self._root_dir + "/MainRule"; return self._main_rule_dir
    def get_system_dir(self)       -> str:
        self._system_dir = self._root_dir + "/System";  return self._system_dir
    def get_unix_socket_dir(self)  -> str:
        self._unix_socket_dir = self.get_system_dir() + "/UnixSocket"; return self._unix_socket_dir
    def get_parser_temp_dir(self)  -> str:
        self._parser_temp_dir = self.get_system_dir() + "/Parser";     return self._parser_temp_dir
    def get_script_dir(self)       -> str:
        self._script_dir = f"~{self.get_user_name()}{self.get_start_dir()}/Script"
        return self._script_dir
    def get_connector_temp_dir(self) -> str:
        self._connector_temp_dir = self.get_system_dir() + "/Connector"; return self._connector_temp_dir
    def get_data_handler_dir(self) -> str:
        self._data_handler_dir = self.get_system_dir() + "/DataHandler"; return self._data_handler_dir
    def get_job_monitor_dir(self)  -> str:
        self._job_monitor_dir = self.get_system_dir() + "/JobMonitor";   return self._job_monitor_dir

    # ── Alive Check ───────────────────────────
    def get_alive_check_limit_cnt(self)  -> int: return self._alive_check_limit_cnt
    def get_proc_alive_check_time(self)  -> int: return self._alive_check_interval_time

    # ── 로그파일 관리 ─────────────────────────
    def set_log_file(self, proc_type: int = -5) -> None:
        self._proc_type = proc_type
        self.log_file_changed_event()

    def log_file_changed_event(self) -> None:
        """C++ LogFileChangedEvent 대응 — 날짜 기반 로그파일 경로 설정."""
        from Common.AsWorldLogTimer import AsWorldLogTimer

        now = datetime.now()
        log_dir = self.get_log_dir()

        # ARG_LOG_CYCLE 인자 파싱 (sys.argv 기반)
        import sys
        argv = sys.argv
        log_interval = ARG_LOG_DAY
        hour_str = ""
        try:
            idx = argv.index(ARG_LOG_CYCLE)
            log_interval = argv[idx + 1] if idx + 1 < len(argv) else ARG_LOG_DAY
        except ValueError:
            pass

        if log_interval == ARG_LOG_HOUR:
            hour_str = f"{now.hour:02d}"

        proc_type_str = self.get_process_type_string(self._proc_type)

        if proc_type_str == STR_UNKNOWN_TYPE:
            log_path = (f"{log_dir}/{self._proc_name}_"
                        f"{now.year:04d}{now.month:02d}{now.day:02d}{hour_str}.log")
        else:
            log_path = (f"{log_dir}/{proc_type_str}_{self._proc_name}_"
                        f"{now.year:04d}{now.month:02d}{now.day:02d}{hour_str}.log")

        # 파일 핸들러 교체
        root_logger = logging.getLogger()
        for h in root_logger.handlers[:]:
            if isinstance(h, logging.FileHandler):
                root_logger.removeHandler(h)
                h.close()
        fh = logging.FileHandler(log_path)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root_logger.addHandler(fh)
        logger.debug("log change: %s", log_path)

        # 다음 로그 전환 타이머 설정
        if self._as_world_log_timer is None:
            self._as_world_log_timer = AsWorldLogTimer(self)

        if log_interval == ARG_LOG_HOUR:
            remain = (60 - now.minute) * 60 - now.second
            remain = remain if remain > 0 else 3600
        else:
            remain = (24 - now.hour) * 3600 - now.minute * 60 - now.second
            remain = remain if remain > 0 else 86400

        logger.debug("Remain next log change second: %d", remain)
        self._as_world_log_timer.set_timer(remain + 20, 1)

    # ── 디렉토리 존재 확인 및 생성 ───────────
    def ascii_system_dir_check(self) -> bool:
        checks = [
            (self.get_log_dir(),           True),
            (self.get_bin_dir(),           False),
            (self.get_main_rule_dir(),     True),
            (self.get_system_dir(),        True),
            (self.get_unix_socket_dir(),   True),
            (self.get_parser_temp_dir(),   True),
            (self.get_connector_temp_dir(),True),
            (self.get_data_handler_dir(),  True),
            (self.get_job_monitor_dir(),   True),
            (self._root_dir + "/Script",   False),
            (self.get_raw_dir(),           True),
            (self.get_rule_dir(),          True),
        ]
        return all(self._dir_check(d, mk) for d, mk in checks)

    def _dir_check(self, dir_name: str, make_flag: bool = True) -> bool:
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

    # ── 프로세스 타입 → 이름 변환 ─────────────
    @staticmethod
    def get_process_name(proc_type: int) -> str:
        _MAP = {
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
        name = _MAP.get(proc_type)
        if name is None:
            logger.error("UnKnown Process Type: %d", proc_type)
            return "UnKnown_Process"
        return name

    @staticmethod
    def get_process_type_string(proc_type: int) -> str:
        """AsUtil.GetProcessTypeString 대응 — 미변환 시 STR_UNKNOWN_TYPE 반환."""
        try:
            from Common.AsUtil import AsUtil
            return AsUtil.get_process_type_string(proc_type)
        except ImportError:
            return STR_UNKNOWN_TYPE

    # ── ConnectionMgr 정적 관리 ───────────────
    @classmethod
    def get_connection_mgr_vector(cls) -> ConnectionMgrVector | None:
        return cls._connection_mgr_vector

    @classmethod
    def register_connection_mgr(cls, conn_mgr: "ConnectionMgr") -> None:
        with cls._conn_mgr_vector_lock:
            if cls._connection_mgr_vector is None:
                cls._connection_mgr_vector = []
            cls._connection_mgr_vector.append(conn_mgr)

    @classmethod
    def deregister_connection_mgr(cls, conn_mgr: "ConnectionMgr") -> bool:
        with cls._conn_mgr_vector_lock:
            if cls._connection_mgr_vector is None:
                return False
            try:
                cls._connection_mgr_vector.remove(conn_mgr)
                return True
            except ValueError:
                logger.error("DeRegisterConnectionMgr fail: %s",
                             getattr(conn_mgr, "get_object_name", lambda: "?")())
                return False

    # ── SockMgr 세션 활성화 ───────────────────
    def enable_sock_mgr_session(self, session_name: str, port: int) -> bool:
        from Common.SockMgrConnMgr import SockMgrConnMgr
        self._sock_mgr_conn_mgr = SockMgrConnMgr()

        if not self._sock_mgr_conn_mgr.create():
            logger.error("Socket Create Error for Sock Mgr Listen")
            self._sock_mgr_conn_mgr = None
            return False

        if not self._sock_mgr_conn_mgr.listen(port):
            logger.error("Listen Error For Sock Mgr Listen(port:%d)", port)
            self._sock_mgr_conn_mgr = None
            return False

        self._sock_mgr_conn_mgr.set_object_name(session_name)
        logger.debug("Enable SockMgr Session Success(port:%d)", port)
        return True

    # ── 시스템 정보 설정 ─────────────────────
    def set_system_info(self, proc_type: int, proc_id: str) -> None:
        from Common.AsSystemChecker import AsSystemChecker
        self._system_info.process_type = proc_type
        self._system_info.process_id   = proc_id
        AsSystemChecker.get_system_info(self._system_info)