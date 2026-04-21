"""
DataHandlerConnMgr.py
C++ DataHandlerConnMgr.h/.C → Python 변환

DataHandler 연결 관리자.
  - DB에서 DataHandler 정보 로드 (Init)
  - SSH로 DataHandler 프로세스 원격 기동 (ExecuteDataHandler / RunCommand)
  - 기동 타임아웃 감시 (ReceiveTimeOut / AsWorld.SetTimer)
  - DataHandler InfoChange CRUD 처리
"""

import asyncio
import copy
import logging
import threading
import time
from typing import Optional, Dict

import paramiko                                         # C++: frSshUtil (치트시트)

from Common.ConnectionMgr import ConnectionMgr          # add/remove/find_session (치트시트)
from Common.CommTypeList import (
    AS_DATA_HANDLER_INFO_T, AS_PROC_CONTROL_T,
    AS_PROCESS_STATUS_T, AS_LOG_STATUS_T, AS_DATA_HANDLER_INIT_T,
)
from Common.CommType import (
    ASCII_DATA_HANDLER,
    START, STOP, WAIT_NO, WAIT_START, WAIT_STOP,
    CREATE_DATA, UPDATE_DATA, DELETE_DATA,
    LOG_ADD,
    ARG_NAME, ARG_SVR_IP, ARG_SVR_PORT,
    ARG_LOG_CYCLE, ARG_LOG_HOUR,
    AS_DATA_HANDLER_INIT,
)
from Common.AsWorld import AsWorld
from ProcNaServer.AsciiServerType import (
    WAIT_DATA_HANDLER_START_TIME,
    WAIT_DATA_HANDLER_START_TIMEOUT,
)

logger = logging.getLogger(__name__)

# DataHandlerInfoMap: DataHandlerId(str) → AS_DATA_HANDLER_INFO_T
DataHandlerInfoMap = Dict[str, AS_DATA_HANDLER_INFO_T]
# LogStatusMap: name(str) → AS_LOG_STATUS_T
LogStatusMap = Dict[str, AS_LOG_STATUS_T]


class DataHandlerConnMgr(ConnectionMgr):
    """
    C++ DataHandlerConnMgr (ConnectionMgr 상속) 대응.

    타이머:
      AsWorld.SetTimer / CancelTimer 사용.
      _timer_key_map: DataHandlerId(str) → timer_key(int)
    """

    def __init__(self) -> None:
        super().__init__()
        self._data_handler_info_map: DataHandlerInfoMap = {}
        self._log_status_map:        LogStatusMap       = {}
        self._timer_key_map:         Dict[str, int]     = {}

    def __del__(self) -> None:
        self._log_status_map.clear()
        self._data_handler_info_map.clear()

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """C++: AcceptSocket()"""
        from ProcNaServer.DataHandlerConnection import DataHandlerConnection

        conn = DataHandlerConnection(self)
        if not self.Accept(conn):
            logger.debug("Data Handler Socket Accept Error : %s",
                         self.GetObjErrMsg())
            return

        self.add(conn)                              # ConnectionMgr.add()
        logger.debug("DataHandler Connection")

    # =========================================================================
    # Init
    # =========================================================================

    def Init(self) -> bool:
        """C++: Init() — DB에서 DataHandler 정보 로드."""
        from ProcNaServer.AsciiServerWorld import DBPTR

        self._data_handler_info_map.clear()
        if not DBPTR().GetDataHandlerInfo(self._data_handler_info_map):
            logger.error("Get DataHandler Info Error : %s",
                         DBPTR().GetErrorMsg())
            return False
        return True

    # =========================================================================
    # ExecuteDataHandler
    # =========================================================================

    def ExecuteDataHandler(self, info: Optional[AS_DATA_HANDLER_INFO_T] = None,
                            wait_time: int = WAIT_DATA_HANDLER_START_TIME) -> bool:
        """
        C++ 오버로드 2종 통합:
          ExecuteDataHandler()                      → 전체 기동
          ExecuteDataHandler(AS_DATA_HANDLER_INFO_T*, int) → 단일 기동
        """
        if info is None:
            return self._execute_all()
        return self._execute_one(info, wait_time)

    def _execute_all(self) -> bool:
        """C++: ExecuteDataHandler() — 전체 순회 기동."""
        if not self.Init():
            return False

        wait_offset = 50
        for dh_id, info in self._data_handler_info_map.items():
            logger.debug("DataHandlerId : %s", info.DataHandlerId)
            if info.SettingStatus == START:
                self._execute_one(info,
                                  WAIT_DATA_HANDLER_START_TIME + wait_offset)
                wait_offset += 2
        return True

    def _execute_one(self, info: AS_DATA_HANDLER_INFO_T,
                     wait_time: int = WAIT_DATA_HANDLER_START_TIME) -> bool:
        """C++: ExecuteDataHandler(AS_DATA_HANDLER_INFO_T*, int) — SSH 실행."""
        from ProcNaServer.AsciiServerWorld import MAINPTR, DBPTR

        if info.RequestStatus != WAIT_NO:
            req_str = "Start" if info.RequestStatus == WAIT_START else "Stop"
            logger.info("Already Request DataHandler: %s(%s)",
                        info.DataHandlerId, req_str)
            MAINPTR().SendAsciiError(
                1, "Already Request DataHandler: %s(%s)",
                info.DataHandlerId, req_str)
            return False

        # 기존 프로세스 Kill
        self.KillDataHandler(info.DataHandlerId)

        # 로그 사이클 인자
        log_cycle_buf = ""
        if info.LogCycle == 1:
            log_cycle_buf = f"{ARG_LOG_CYCLE} {ARG_LOG_HOUR}"

        # SSH ID/PW 없으면 DB 재조회
        if not info.SshID:
            if not DBPTR().GetDataHandlerInfoFindId(info):
                logger.error("Get DataHandler Info Error : %s",
                             DBPTR().GetErrorMsg())
                return False
            if not info.SshID or not info.SshPass:
                logger.error("Can't Find SSHID, SshPass: %s",
                             info.DataHandlerId)
                return False

        # 실행 명령 조립
        exec_cmd = (
            f"~{info.SshID}{AsWorld.GetStartDir()}/Bin/"
            f"{MAINPTR().GetProcessName(ASCII_DATA_HANDLER)} "
            f"{ARG_NAME} {info.DataHandlerId} "
            f"{ARG_SVR_IP} {MAINPTR().GetServerIp()} "
            f"{ARG_SVR_PORT} {MAINPTR().GetListenPort(ASCII_DATA_HANDLER)} "
            f"{log_cycle_buf} &"
        ).strip()

        logger.debug("Data Handler Execute: %s", exec_cmd)
        time.sleep(5)                               # C++: sleep(5)

        if info.SshID or info.SshPass:
            self.RunCommand(info.SshID, info.SshPass, info.IpAddress, exec_cmd)

        info.RequestStatus = WAIT_START

        # 기동 대기 타이머 (AsWorld.SetTimer)
        old_key = self._timer_key_map.pop(info.DataHandlerId, None)
        if old_key is not None:
            self.CancelTimer(old_key)               # AsWorld.CancelTimer

        key = self.SetTimer(                        # AsWorld.SetTimer
            wait_time,
            WAIT_DATA_HANDLER_START_TIMEOUT,
            info.DataHandlerId,
        )
        self._timer_key_map[info.DataHandlerId] = key
        MAINPTR().SendInfoChange(info)
        return True

    # =========================================================================
    # RunCommand (SSH — 치트시트: paramiko)
    # =========================================================================

    def RunCommand(self, ssh_id: str, ssh_pass: str,
                   ip: str, command: str) -> bool:
        """C++: RunCommand(char* SshID, char* SshPass, char* IP, char* Command)"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, port=22, username=ssh_id,
                           password=ssh_pass, timeout=10)
            client.exec_command(command)
            client.close()
            logger.info("SSH Connect !!!!!! [%s@%s] %s", ssh_id, ip, command)
            return True
        except Exception as e:
            logger.info("SSH Connect Fail!!!!!! : %s", e)
            return False

    # =========================================================================
    # StopDataHandler
    # =========================================================================

    def StopDataHandler(self, info: AS_DATA_HANDLER_INFO_T) -> bool:
        """C++: StopDataHandler(AS_DATA_HANDLER_INFO_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR
        from ProcNaServer.DataHandlerConnection import DataHandlerConnection

        con: Optional[DataHandlerConnection] = self.find_session(
            info.DataHandlerId)                     # ConnectionMgr.find_session()
        if con is None:
            logger.debug("Can't find the executed DataHandler(%s).",
                         info.DataHandlerId)
            MAINPTR().SendAsciiError(
                1, "Can't find the executed DataHandler(%s).",
                info.DataHandlerId)
            return False

        info.RequestStatus = WAIT_STOP
        MAINPTR().SendInfoChange(info)
        asyncio.ensure_future(con.StopDataHandler())
        return True

    # =========================================================================
    # DataHandlerSessionIdentify
    # =========================================================================

    def DataHandlerSessionIdentify(self, data_handler_id: str) -> None:
        """C++: DataHandlerSessionIdentify — 기동 대기 타이머 취소."""
        key = self._timer_key_map.pop(data_handler_id, None)
        if key is None:
            logger.error("Can't Find DataHandler(%s) in "
                         "DataHandlerExecuteTimerMap", data_handler_id)
            return
        self.CancelTimer(key)                       # AsWorld.CancelTimer

    # =========================================================================
    # GetDataHandlerInfoMap / FindDataHandlerInfo
    # =========================================================================

    def GetDataHandlerInfoMap(self) -> DataHandlerInfoMap:
        return self._data_handler_info_map

    def FindDataHandlerInfo(self, data_handler_id: str
                             ) -> Optional[AS_DATA_HANDLER_INFO_T]:
        """C++: FindDataHandlerInfo(string DataHandlerId)"""
        return self._data_handler_info_map.get(data_handler_id)

    # =========================================================================
    # ReceiveProcInfo
    # =========================================================================

    def ReceiveProcInfo(self, proc_info: AS_PROCESS_STATUS_T) -> None:
        """C++: ReceiveProcInfo(AS_PROCESS_STATUS_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR
        MAINPTR().UpdateProcessInfo(proc_info)

    # =========================================================================
    # RecvProcessControl
    # =========================================================================

    def RecvProcessControl(self, proc_ctl: AS_PROC_CONTROL_T) -> bool:
        """C++: RecvProcessControl(AS_PROC_CONTROL_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR, DBPTR

        info = self.FindDataHandlerInfo(proc_ctl.ProcessId)
        if info is None:
            logger.error("Can't Find DataHandler : %s", proc_ctl.ProcessId)
            return False

        if info.RequestStatus != WAIT_NO:
            req_str = "Start" if info.RequestStatus == WAIT_START else "Stop"
            logger.info("Already Request Process: %s(%s)",
                        proc_ctl.ProcessId, req_str)
            MAINPTR().SendAsciiError(
                1, "Already Request Process: %s(%s)",
                proc_ctl.ProcessId, req_str)
            return False

        if proc_ctl.Status == START and info.CurStatus == START:
            logger.info("Already Started DataHandler : %s", proc_ctl.ProcessId)
            MAINPTR().SendAsciiError(
                1, "Already Started DataHandler : %s", proc_ctl.ProcessId)
            return False
        if proc_ctl.Status == STOP and info.CurStatus == STOP:
            logger.info("Already Stop DataHandler : %s", proc_ctl.ProcessId)
            MAINPTR().SendAsciiError(
                1, "Already Stop DataHandler : %s", proc_ctl.ProcessId)
            return False

        if not DBPTR().UpdateDataHandlerStatus(proc_ctl.ProcessId,
                                                proc_ctl.Status):
            logger.error("Update DataHandler Status Error : %s",
                         DBPTR().GetErrorMsg())
            return False

        info.SettingStatus = START if proc_ctl.Status == START else STOP

        # RunMode 0: 일반 모드 → Manager에도 변경 통지
        if info.RunMode == 0:
            MAINPTR().SendDataHandlerInfoChange(info)

        if proc_ctl.Status == START:
            if self._execute_one(info):
                MAINPTR().SendAsciiError(
                    1, "The DataHandler(%s) start successful",
                    proc_ctl.ProcessId)
            else:
                MAINPTR().SendAsciiError(
                    1, "DataHandler(%s) start failed", proc_ctl.ProcessId)
        elif proc_ctl.Status == STOP:
            self.StopDataHandler(info)

        return True

    # =========================================================================
    # ReceiveTimeOut (AsWorld 가상함수 오버라이드)
    # =========================================================================

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """
        C++: ReceiveTimeOut(int Reason, void* ExtraReason)
        WAIT_DATA_HANDLER_START_TIMEOUT: DataHandler 기동 타임아웃 처리.
        extra_reason = data_handler_id (str)
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR, DBPTR

        if reason == WAIT_DATA_HANDLER_START_TIMEOUT:
            dh_id: str = (extra_reason if isinstance(extra_reason, str)
                          else "")
            logger.debug(
                "Recv Timeout WAIT_DATA_HANDLER_START_TIMEOUT : %s", dh_id)
            MAINPTR().SendAsciiError(1, "DataHandler(%s) Start Error", dh_id)

            self._timer_key_map.pop(dh_id, None)

            info = self.FindDataHandlerInfo(dh_id)
            if info is None:
                logger.error("DataHandler Info Can't Find : %s", dh_id)
                return

            logger.debug("DataHandler %s Status is setting STOP", dh_id)

            if not DBPTR().UpdateDataHandlerStatus(dh_id, STOP):
                logger.error("Update DataHandler Status Error : %s",
                             DBPTR().GetErrorMsg())
                return

            info.SettingStatus  = STOP
            info.CurStatus      = STOP
            info.RequestStatus  = WAIT_NO

            MAINPTR().SendDataHandlerInfoChange(info)
            MAINPTR().SendInfoChange(info)

    # =========================================================================
    # KillDataHandler
    # =========================================================================

    def KillDataHandler(self, data_handler_id: str) -> None:
        """C++: KillDataHandler(string DataHandlerId) — KillDataHandler.sh SSH 실행."""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        info = self.FindDataHandlerInfo(data_handler_id)
        if info is None:
            logger.error("Can't Find DataHandler : %s", data_handler_id)
            return

        cmd = (f"~{MAINPTR().GetUserName()}{AsWorld.GetStartDir()}"
               f"/Script/KillDataHandler.sh {info.DataHandlerId}")
        logger.debug("Kill DataHandler : %s", cmd)
        self.RunCommand(info.SshID, info.SshPass, info.IpAddress, cmd)
        time.sleep(1)                               # C++: sleep(1)

    # =========================================================================
    # LogStatus
    # =========================================================================

    def UpdateDataHandlerLogStatus(self, status: AS_LOG_STATUS_T) -> None:
        """
        C++: UpdateDataHandlerLogStatus(AS_LOG_STATUS_T*)
        C++ 원본: 함수 진입 직후 return; 이 있어 실질적으로 no-op.
        그대로 구현하되 실제 동작 코드도 보존.
        """
        return                                      # C++ 원본: 즉시 return
        # ── 아래는 C++ 원본의 실제 로직 (현재 비활성화) ──
        self._log_status_map.pop(status.name, None)
        if status.status == LOG_ADD:
            self._log_status_map[status.name] = copy.copy(status)
        from ProcNaServer.AsciiServerWorld import MAINPTR
        MAINPTR().SendLogStatus(status)

    def GetLogStatusList(self, status_list: list) -> None:
        """C++: GetLogStatusList(LogStatusVector*)"""
        status_list.extend(self._log_status_map.values())

    def SendCmdLogStatusChange(self, log_ctl, session_name: str = "") -> bool:
        """C++: SendCmdLogStatusChange() — ConnectionMgr 위임."""
        return super().send_cmd_log_status_change(log_ctl, session_name)

    # =========================================================================
    # RecvInfoChange (CRUD)
    # =========================================================================

    def RecvInfoChange(self, info: AS_DATA_HANDLER_INFO_T,
                       result_msg: list) -> bool:
        """
        C++: RecvInfoChange(AS_DATA_HANDLER_INFO_T* Info, char* ResultMsg)
        result_msg: [str] 1-원소 리스트 (C++ char* 출력 인자 대응).
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR

        if info.RequestStatus == CREATE_DATA:
            new_info = copy.copy(info)
            new_info.RequestStatus = WAIT_NO
            new_info.CurStatus     = STOP
            new_info.SettingStatus = STOP
            self._data_handler_info_map[new_info.DataHandlerId] = new_info
            MAINPTR().SendInfoChange(info)
            return True

        if info.RequestStatus == UPDATE_DATA:
            if info.OldDataHandlerId not in self._data_handler_info_map:
                result_msg[0] = (f"Can't Find DataHandler : "
                                 f"{info.OldDataHandlerId}")
                return False
            del self._data_handler_info_map[info.OldDataHandlerId]
            new_info = copy.copy(info)
            new_info.CurStatus        = STOP
            new_info.SettingStatus    = STOP
            new_info.RequestStatus    = WAIT_NO
            new_info.OldDataHandlerId = ""
            self._data_handler_info_map[new_info.DataHandlerId] = new_info
            MAINPTR().SendDataHandlerInfoChange(info)
            MAINPTR().SendInfoChange(info)
            return True

        if info.RequestStatus == DELETE_DATA:
            existing = self._data_handler_info_map.get(info.DataHandlerId)
            if existing is None:
                result_msg[0] = (f"Can't Find DataHandler : "
                                 f"{info.DataHandlerId}")
                return False
            info.RunMode = existing.RunMode         # RunMode 보존
            del self._data_handler_info_map[info.DataHandlerId]
            MAINPTR().SendDataHandlerInfoChange(info)
            MAINPTR().SendInfoChange(info)
            return True

        return False

    # =========================================================================
    # RecvInitInfo
    # =========================================================================

    def RecvInitInfo(self, init_info: AS_DATA_HANDLER_INIT_T) -> None:
        """C++: RecvInitInfo(AS_DATA_HANDLER_INIT_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR
        from ProcNaServer.DataHandlerConnection import DataHandlerConnection

        con: Optional[DataHandlerConnection] = self.find_session(
            init_info.DataHandlerId)                # ConnectionMgr.find_session()
        if con is None:
            logger.debug("Can't find the DataHandler(%s) to init",
                         init_info.DataHandlerId)
            MAINPTR().SendAsciiError(
                1, "Can't find the DataHandler(%s) to init.",
                init_info.DataHandlerId)
            return

        payload = _pack(init_info)
        asyncio.ensure_future(
            con.SendPacket(AS_DATA_HANDLER_INIT, payload, len(payload)))
        MAINPTR().SendAsciiError(
            1, "Success notify to DataHandler(%s) for initialize.",
            init_info.DataHandlerId)


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''