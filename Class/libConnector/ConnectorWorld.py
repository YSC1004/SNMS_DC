"""
ConnectorWorld.py
C++ ConnectorWorld.h/.C → Python 변환

ProcNaConnector 최상위 애플리케이션 클래스.
  - procNaManager Unix 소켓 접속 (ManagerConnection)
  - Parser Unix 소켓 접속 (ParserConnection)
  - DCManager 생성 및 MMC 명령 위임
  - SimulFileHandler (시뮬레이션 데이터)
  - PARSER_CONNECT / 포트 오픈 처리
"""

import asyncio
import logging
import os
import shutil
import threading
from pathlib import Path
from typing import ClassVar, Optional

from Common.AsWorld import AsWorld                      # 치트시트: AsWorld
from Common.AsUtil import AsUtil
from Common.CommTypeList import (
    AS_CMD_OPEN_PORT_T, AS_MMC_PUBLISH_T, AS_MMC_RESULT_T,
    AS_PORT_STATUS_INFO_T, AS_SESSION_CONTROL_T,
    AS_CONNECTOR_DATA_T, AS_ASCII_ERROR_MSG_T,
)
from Common.CommType import (
    ASCII_CONNECTOR, ASCII_PARSER, ASCII_SERVER,
    PARSER_CONNECT,
    CMD_OPEN_PORT_ACK, PROC_INIT_END,
    MMC_RESPONSE_DATA, PORT_STATUS_INFO,
    START,
)
from Util.fr_arg_parser import ArgParser

# ── ConnectorType 상수 ────────────────────────────────────────────────────────
from ProcNaConnector.ConnectorType import (
    MANAGER_CONNECTION_TIME,
)

logger = logging.getLogger(__name__)

# 인자 상수
ARG_MANAGER_SOCKET_PATH = "-managersocketpath"
ARG_CMD_RESPONSE_TYPE   = "-cmdresponsetype"

MAX_ERR_MSG_BUF         = 4096
MANAGER_CONNECTION_TIME = 10001    # C++: #define MANAGER_CONNECTION_TIME


def MAINPTR() -> "ConnectorWorld":
    return ConnectorWorld.m_WorldPtr


class ConnectorWorld(AsWorld):
    """
    C++ ConnectorWorld (AsWorld 상속) 대응.
    KtfConWorld의 부모 클래스.
    RUNTIME_EXEC(KtfConWorld) → main.py 에서 직접 호출.
    """

    m_WorldPtr: ClassVar[Optional["ConnectorWorld"]] = None

    def __init__(self) -> None:
        super().__init__()
        ConnectorWorld.m_WorldPtr = self

        self._manager_connection = None     # ManagerConnection (지연 임포트)
        self._parser_connection  = None     # ParserConnection
        self._dc_manager         = None     # DCManager
        self._simul_file_handler = None     # SimulFileHandler

        self._manager_socket_path: str = ""
        self._tmp_dir_name:        str = ""
        self._tmp_dir_name_str:    str = ""
        self._response_type:       int = 1
        self._manager_con_retry:   int = 0
        self._is_test_con:         bool = False

        # C++: pthread_mutex_t m_ParserConnLock
        self._parser_conn_lock: threading.Lock = threading.Lock()

        # DCManager 생성
        self._set_dc_manager()

        # ManagerConnection 생성
        from ProcNaConnector.ManagerConnection import ManagerConnection
        self._manager_connection = ManagerConnection()

    def __del__(self) -> None:
        pass

    # =========================================================================
    # AppStart
    # =========================================================================

    def AppStart(self, argc: int, argv: list) -> bool:
        """C++: virtual AppStart(int Argc, char** Argv)"""
        if argc > 1 and argv[1] == "-show":
            from ProcNaConnector.DCManager import DCManager
            DCManager.ShowMediation()
            return False

        if not self.InitConfig():
            logger.error("Env Init Error")
            return False

        if argc < 7:
            print(f"[Usage] {argv[0]} "
                  f"-name Connector1 "
                  f"-managersocketpath /home/MANAGER_SOCKET "
                  f"-cmdresponsetype 0")
            logger.error("Argument is not correct")
            return False

        args = ArgParser(argv)
        self._proc_name           = args.get_value("-name")
        self._manager_socket_path = args.get_value(ARG_MANAGER_SOCKET_PATH)
        self._response_type       = int(
            args.get_value(ARG_CMD_RESPONSE_TYPE) or 1)

        if not self.GetLogDir():
            logger.error("Can't get Ascii Log Directory variable")
            return False

        self.SetLogFile()

        logger.debug("Connector(%s) Start.............", self._proc_name)

        if not self._init_connector():
            logger.debug("Connector Init Fail")
        return True

    # =========================================================================
    # InitConnector
    # =========================================================================

    def _init_connector(self) -> bool:
        """C++: InitConnector()"""
        # Manager에 접속될 때까지 재시도
        while True:
            if not self._manager_connection.Connect(
                    self._manager_socket_path):
                logger.error("Manager Connect Error : %s",
                             self._manager_connection.GetObjErrMsg())
                import time; time.sleep(1)
            else:
                break

        asyncio.ensure_future(
            self._manager_connection.SetSessionIdentify(
                ASCII_CONNECTOR, self._proc_name,
                self.GetProcAliveCheckTime()))

        asyncio.ensure_future(
            self._manager_connection.SendLogStatus(self.GetLogStatus()))

        self._init_tmp_dir()
        self._create_simul_data()
        self._send_proc_init_end()

        def_to = self.GetCmdResponseTimeOut()
        self._dc_manager.SetDefaultCmdResTimeOut(def_to)
        return True

    # =========================================================================
    # InitTmpDir
    # =========================================================================

    def _init_tmp_dir(self) -> bool:
        """C++: InitTmpDir() — 임시 디렉토리 초기화."""
        self._tmp_dir_name_str = (
            f"{self.GetConnectorTempDir()}/{self._proc_name}")
        tmp_path = Path(self._tmp_dir_name_str)

        if not tmp_path.exists():
            try:
                tmp_path.mkdir(parents=True, mode=0o777)
            except OSError as e:
                logger.error("Tmp Dir(%s) Create Error : %s",
                             self._tmp_dir_name_str, e)
                return False
        else:
            # .RAW 제외한 파일 삭제
            for f in tmp_path.iterdir():
                if ".RAW" not in f.name:
                    try:
                        f.unlink()
                    except OSError:
                        pass

        self._tmp_dir_name = self._tmp_dir_name_str
        return True

    # =========================================================================
    # OpenPort
    # =========================================================================

    def OpenPort(self, port_info: AS_CMD_OPEN_PORT_T) -> None:
        """C++: virtual OpenPort(AS_CMD_OPEN_PORT_T*)"""
        err_msg = ""

        if port_info.ProtocolType == PARSER_CONNECT:
            with self._parser_conn_lock:
                logger.debug("PARSER_CONNECT : %s", port_info.PortPath)

                from ProcNaConnector.ParserConnection import ParserConnection
                self._parser_connection = ParserConnection()

                if not self._parser_connection.Connect(port_info.PortPath):
                    err_msg = self._parser_connection.GetObjErrMsg()
                    asyncio.ensure_future(
                        self._manager_connection.SendAck(
                            CMD_OPEN_PORT_ACK, port_info.Id, 0, err_msg))
                    self._parser_connection = None
                    logger.error("Parser Connection Error: %s", err_msg)
                    return
        else:
            if not self.GetDCManager().OpenPort(port_info):
                asyncio.ensure_future(
                    self._manager_connection.SendAck(
                        CMD_OPEN_PORT_ACK, port_info.Id, 0, err_msg))
                logger.error("DCManager openport error")
                return

        asyncio.ensure_future(
            self._manager_connection.SendAck(
                CMD_OPEN_PORT_ACK, port_info.Id))

    # =========================================================================
    # 패킷 전송
    # =========================================================================

    def _send_proc_init_end(self) -> bool:
        """C++: SendProcInitEnd()"""
        asyncio.ensure_future(
            self._manager_connection.SendAck(PROC_INIT_END, 1))
        return True

    def SendMsgToParser(self, packet) -> bool:
        """C++: SendMsgToParser(PACKET_T*)"""
        with self._parser_conn_lock:
            if self._parser_connection:
                if not self._parser_connection.SendMsg(packet):
                    self._parser_connection = None
                    logger.error("Parser Connection Broken")
            else:
                self.SaveMsg(packet.Msg)
        return True

    def SaveMsg(self, data: AS_CONNECTOR_DATA_T) -> None:
        """C++: virtual SaveMsg() — Parser 미연결 시 처리 (기본 no-op)."""
        logger.debug("Parser is't Connected(%s)", self.GetProcName())

    def SendAsciiError(self, priority: int, fmt: str, *args) -> None:
        """C++: SendAsciiError(int Priority, const char* format, ...)"""
        msg = fmt % args if args else fmt
        if self._manager_connection:
            err = AS_ASCII_ERROR_MSG_T()
            err.Priority    = priority
            err.ProcessType = ASCII_CONNECTOR
            err.ProcessId   = self.GetProcName()
            err.ErrMsg      = msg
            asyncio.ensure_future(
                self._manager_connection.SendAsciiError(err))
        else:
            logger.error(msg)

    def SendCommandResult(self, mmc_result: AS_MMC_RESULT_T) -> None:
        """C++: SendCommandResult(AS_MMC_RESULT_T*)"""
        logger.debug("SendCommandResult")
        if self._manager_connection:
            payload = _pack(mmc_result)
            asyncio.ensure_future(
                self._manager_connection.SendPacket(
                    MMC_RESPONSE_DATA, payload, len(payload)))
        else:
            logger.error("SendCommandResult....")

    def SendPortStatus(self, psi: AS_PORT_STATUS_INFO_T) -> None:
        """C++: SendPortStatus(AS_PORT_STATUS_INFO_T*)"""
        if self._manager_connection:
            payload = _pack(psi)
            asyncio.ensure_future(
                self._manager_connection.SendPacket(
                    PORT_STATUS_INFO, payload, len(payload)))
        else:
            logger.error("SendPortStatus....")

    def SendResponseCommand(self, mmc_com: AS_MMC_PUBLISH_T) -> None:
        """C++: SendResponseCommand(AS_MMC_PUBLISH_T*)"""
        with self._parser_conn_lock:
            if self._parser_connection:
                asyncio.ensure_future(
                    self._parser_connection.SendResponseCommand(mmc_com))
            else:
                logger.error("SendResponseCommand...")

    # =========================================================================
    # MMC / 세션 제어
    # =========================================================================

    def ReceiveMMCCommand(self, mmc_com: AS_MMC_PUBLISH_T) -> None:
        """C++: ReceiveMMCCommand(AS_MMC_PUBLISH_T*)"""
        self.GetDCManager().ReceiveMMCCommand(mmc_com)

    def RecvSessionControl(self,
                            session_ctl: AS_SESSION_CONTROL_T) -> None:
        """C++: RecvSessionControl(AS_SESSION_CONTROL_T*)"""
        logger.debug(
            "Recv Session Control name(%s), sequence(%d), Status(%s)",
            session_ctl.ConnectorId, session_ctl.Sequence,
            "START" if session_ctl.Status == START else "STOP")
        self.GetDCManager().RecvSessionControl(session_ctl)

    def ParserConnectBroken(self) -> None:
        """C++: ParserConnectBroken()"""
        with self._parser_conn_lock:
            self._parser_connection = None

    # =========================================================================
    # ReceiveTimeOut (AsWorld 가상함수 오버라이드)
    # =========================================================================

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """C++: ReceiveTimeOut(int Reason, void* ExtraReason)"""
        if reason == MANAGER_CONNECTION_TIME:
            self._init_connector()
            self._manager_con_retry += 1
            logger.debug("ReConnect Manager")
            if self._manager_con_retry > 3:
                import sys; sys.exit(0)
        else:
            logger.debug("Unknown TimeOut Reason : %d", reason)

    # =========================================================================
    # RecvWatcherMsg (가상함수 — 기본 no-op)
    # =========================================================================

    def RecvWatcherMsg(self, input_str: str) -> None:
        """C++: virtual RecvWatcherMsg(char* InputStr)"""
        pass

    # =========================================================================
    # 접근자
    # =========================================================================

    def GetTemporaryDir(self) -> str:
        return self._tmp_dir_name

    def GetEnvValue(self, environ: str, env_values: list = None):
        """C++: GetEnvValue(string environ) / GetEnvValue(string, frStringVector&)"""
        if env_values is None:
            return AsWorld.GetEnvValue(self, ASCII_CONNECTOR, environ)
        result = AsWorld.GetEnvValueList(self, ASCII_CONNECTOR, environ)
        env_values.extend(result)
        return bool(result)

    def GetDBInfo(self) -> tuple:
        """C++: GetDBInfo(string& DBUser, string& DBPassword, string& DBTns)"""
        user   = AsWorld.GetEnvValue(self, ASCII_SERVER, "db_user")
        passwd = AsWorld.GetEnvValue(self, ASCII_SERVER, "db_password")
        tns    = AsWorld.GetEnvValue(self, ASCII_SERVER, "db_tns")
        return user, passwd, tns

    def GetMsgId(self) -> int:
        """C++: GetMsgId() → DCManager.GetMsgId()"""
        return self.GetDCManager().GetMsgId()

    def GetCmdResponseTimeOut(self) -> int:
        """C++: GetCmdResponseTimeOut()"""
        ret = int(AsWorld.GetEnvValue(
            self, ASCII_PARSER, "command_reponse_timeout") or 0)
        logger.debug("Default command timeout : %d sec", ret)
        if ret == 0:
            return 41
        return ret

    def GetCmdResponseType(self) -> int:
        return self._response_type

    def IsTestConnector(self) -> bool:
        return self._is_test_con

    def SetTestConnector(self, flag: bool) -> None:
        self._is_test_con = flag

    # =========================================================================
    # DCManager 관리
    # =========================================================================

    def _set_dc_manager(self, dc_manager=None) -> None:
        """C++: SetDCManager(DCManager* pDCManager = NULL)"""
        if self._dc_manager is None:
            if dc_manager:
                self._dc_manager = dc_manager
            else:
                from ProcNaConnector.DCManager import DCManager
                self._dc_manager = DCManager()
        else:
            logger.error("DCManager is already exist. so Can't Set DCManager")

    def SetDCManager(self, dc_manager=None) -> None:
        self._set_dc_manager(dc_manager)

    def GetDCManager(self):
        """C++: GetDCManager()"""
        if self._dc_manager is None:
            from ProcNaConnector.DCManager import DCManager
            self._dc_manager = DCManager()
        return self._dc_manager

    # =========================================================================
    # SimulFileHandler
    # =========================================================================

    def _create_simul_data(self) -> bool:
        """C++: CreateSimulData()"""
        from ProcConnector.SimulFileHandler import SimulFileHandler

        tmp = self._proc_name
        pos = tmp.find("_")
        if pos != -1:
            tmp = tmp[pos + 1:]

        self._simul_file_handler = SimulFileHandler()
        if self._simul_file_handler.Run(self._tmp_dir_name_str, tmp):
            logger.debug("SimulFileHandler Create success")
            return True
        logger.debug("SimulFileHandler Create fail")
        return False

    def CreateSimulData(self) -> bool:
        return self._create_simul_data()


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''