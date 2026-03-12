"""
SubProcConnMgr.py
C++ SubProcConnMgr.h/.C → Python 변환

자식 프로세스(SubProc) 연결 관리자.
  - DB에서 SubProc 정보 로드 (Init)
  - 설정 상태 START인 프로세스 원격 실행 (ExecuteSubProc)
  - 프로세스 기동 타임아웃 감시 (ReceiveTimeOut / AsWorld.SetTimer)
  - SubProcConnection Accept/Remove 관리
  - InfoChange (CRUD) 처리
"""

import copy
import logging
import subprocess
from typing import Optional, Dict

from Common.ConnectionMgr import ConnectionMgr          # add/remove/find_session
from Common.CommTypeList import (
    AS_SUB_PROC_INFO_T,
    AS_PROC_CONTROL_T,
    AS_PROCESS_STATUS_T,
)
from Common.CommType import (
    ASCII_SUB_PROCESS,
    START, STOP, WAIT_NO, WAIT_START, WAIT_STOP,
    CREATE_DATA, UPDATE_DATA, DELETE_DATA,
    ARG_NAME, ARG_SVR_IP, ARG_SVR_PORT,
    ARG_LOG_CYCLE, ARG_LOG_HOUR,
)
from ProcNaServer.AsciiServerType import (
    WAIT_DATA_HANDLER_START_TIME,
    WAIT_DATA_HANDLER_START_TIMEOUT,
)

logger = logging.getLogger(__name__)

# SubProcInfoMap : ProcIdStr(str) → AS_SUB_PROC_INFO_T
SubProcInfoMap = Dict[str, AS_SUB_PROC_INFO_T]


class SubProcConnMgr(ConnectionMgr):
    """
    C++ SubProcConnMgr (ConnectionMgr 상속) 대응.

    타이머:
      AsWorld.SetTimer / CancelTimer (asyncio.Task 기반) 사용.
      _timer_key_map : ProcIdStr → timer_key(int)
    """

    def __init__(self) -> None:
        super().__init__()
        self._sub_proc_info_map: SubProcInfoMap   = {}
        # ProcIdStr → AsWorld.SetTimer 반환 key
        self._timer_key_map: Dict[str, int]       = {}

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """
        C++: AcceptSocket()
        새 SubProc 소켓 접속을 수락하여 SubProcConnection 생성.
        """
        from ProcNaServer.SubProcConnection import SubProcConnection

        conn = SubProcConnection(self)
        if not self.Accept(conn):
            logger.debug("SubProc Socket Accept Error : %s", self.GetObjErrMsg())
            return

        self.add(conn)          # ConnectionMgr.add()
        logger.debug("SubProc Connection")

    # =========================================================================
    # Init
    # =========================================================================

    def Init(self) -> bool:
        """
        C++: Init()
        DB에서 SubProc 정보 로드.
        """
        from ProcNaServer.AsciiServerWorld import DBPTR

        self._sub_proc_info_map.clear()
        if not DBPTR().GetSubProcInfo(self._sub_proc_info_map):
            logger.error("Get SubProc Info Error : %s", DBPTR().GetErrorMsg())
            return False
        return True

    # =========================================================================
    # ExecuteSubProc
    # =========================================================================

    def ExecuteSubProc(self, info: Optional[AS_SUB_PROC_INFO_T] = None,
                       wait_time: int = WAIT_DATA_HANDLER_START_TIME) -> bool:
        """
        C++ 오버로드 2종 통합:
          ExecuteSubProc()                         → 전체 SubProc 기동
          ExecuteSubProc(AS_SUB_PROC_INFO_T*, int) → 단일 SubProc 기동
        """
        if info is None:
            return self._execute_all()
        return self._execute_one(info, wait_time)

    def _execute_all(self) -> bool:
        """C++: ExecuteSubProc() – 전체 순회 기동."""
        if not self.Init():
            return False

        wait_offset = 50
        for proc_id, info in self._sub_proc_info_map.items():
            logger.debug("SubProcId : %s", info.ProcIdStr)
            if info.SettingStatus == START:
                self._execute_one(info, WAIT_DATA_HANDLER_START_TIME + wait_offset)
                wait_offset += 2
        return True

    def _execute_one(self, info: AS_SUB_PROC_INFO_T,
                     wait_time: int = WAIT_DATA_HANDLER_START_TIME) -> bool:
        """C++: ExecuteSubProc(AS_SUB_PROC_INFO_T*, int) – 단일 기동."""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        if info.RequestStatus != WAIT_NO:
            req_str = "Start" if info.RequestStatus == WAIT_START else "Stop"
            logger.info("Already Request SubProc: %s(%s)", info.ProcIdStr, req_str)
            MAINPTR().SendAsciiError(
                1, "Already Request SubProc: %s(%s)", info.ProcIdStr, req_str)
            return False

        # 기존 프로세스 Kill
        self.KillSubProc(info.ProcIdStr)

        # 로그 사이클 인자 (C++: logCycleBuf)
        log_cycle_buf = ""
        if info.LogCycle == 1:
            log_cycle_buf = f"{ARG_LOG_CYCLE} {ARG_LOG_HOUR}"

        # 실행 명령 조립
        # C++: ~/NAA/Bin/RunCommand CLIENT <ip> <port> '~<user><startdir>/Bin/<bin> ...'
        inner_cmd = (
            f"~{MAINPTR().GetUserName()}"
            f"{MAINPTR().GetStartDir()}/Bin/{info.BinaryName} "
            f"{ARG_NAME} {info.ProcIdStr} "
            f"{ARG_SVR_IP} {MAINPTR().GetServerIp()} "
            f"{ARG_SVR_PORT} {MAINPTR().GetListenPort(ASCII_SUB_PROCESS)} "
            f"{log_cycle_buf} {info.Args}"
        ).strip()

        exec_cmd = (
            f"~/NAA/Bin/RunCommand CLIENT "
            f"{info.IpAddress} {MAINPTR().m_RunCmdPort} "
            f"'{inner_cmd}'"
        )
        logger.debug("SubProc Execute: %s", exec_cmd)
        subprocess.Popen(exec_cmd, shell=True)

        info.RequestStatus = WAIT_START

        # ── 기동 대기 타이머 (AsWorld.SetTimer 사용) ──────────────────────
        # 기존 타이머가 있으면 취소
        old_key = self._timer_key_map.pop(info.ProcIdStr, None)
        if old_key is not None:
            self.CancelTimer(old_key)           # AsWorld.CancelTimer

        key = self.SetTimer(                    # AsWorld.SetTimer → asyncio.Task
            wait_time,
            WAIT_DATA_HANDLER_START_TIMEOUT,
            info.ProcIdStr,                     # C++ void* ExtraReason → str
        )
        self._timer_key_map[info.ProcIdStr] = key

        MAINPTR().SendInfoChange(info)
        return True

    # =========================================================================
    # StopSubProc
    # =========================================================================

    def StopSubProc(self, info: AS_SUB_PROC_INFO_T) -> bool:
        """C++: StopSubProc(AS_SUB_PROC_INFO_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR
        from ProcNaServer.SubProcConnection import SubProcConnection

        con: Optional[SubProcConnection] = self.find_session(info.ProcIdStr)  # ConnectionMgr.find_session()
        if con is None:
            logger.debug("Can't find the executed Subproc(%s).", info.ProcIdStr)
            MAINPTR().SendAsciiError(
                1, "Can't find the executed SubProc(%s).", info.ProcIdStr)
            return False

        info.RequestStatus = WAIT_STOP
        MAINPTR().SendInfoChange(info)
        con.StopSubProc()
        return True

    # =========================================================================
    # SubProcSessionIdentify
    # =========================================================================

    def SubProcSessionIdentify(self, proc_id_str: str) -> None:
        """
        C++: SubProcSessionIdentify(string ProcIdStr)
        SubProc 세션 식별 완료 → 기동 대기 타이머 취소 (AsWorld.CancelTimer).
        """
        key = self._timer_key_map.pop(proc_id_str, None)
        if key is None:
            logger.error("Can't Find SubProc(%s) in SubProcExecuteTimerMap",
                         proc_id_str)
            return
        self.CancelTimer(key)                   # AsWorld.CancelTimer
        logger.debug("SubProc(%s) start timer cancelled", proc_id_str)

    # =========================================================================
    # GetSubProcInfoMap
    # =========================================================================

    def GetSubProcInfoMap(self) -> SubProcInfoMap:
        return self._sub_proc_info_map

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

        info = self.FindSubProcInfo(proc_ctl.ProcessId)
        if info is None:
            logger.error("Can't Find SubProc : %s", proc_ctl.ProcessId)
            return False

        if info.RequestStatus != WAIT_NO:
            req_str = "Start" if info.RequestStatus == WAIT_START else "Stop"
            logger.info("Already Request Process: %s(%s)",
                        proc_ctl.ProcessId, req_str)
            MAINPTR().SendAsciiError(
                1, "Already Request Process: %s(%s)",
                proc_ctl.ProcessId, req_str)
            return False

        # 이미 같은 상태이면 무시
        if proc_ctl.Status == START and info.CurStatus == START:
            logger.info("Already Started SubProc : %s", proc_ctl.ProcessId)
            MAINPTR().SendAsciiError(
                1, "Already Started SubProc : %s", proc_ctl.ProcessId)
            return False

        if proc_ctl.Status == STOP and info.CurStatus == STOP:
            logger.info("Already Stop SubProc : %s", proc_ctl.ProcessId)
            MAINPTR().SendAsciiError(
                1, "Already Stop SubProc : %s", proc_ctl.ProcessId)
            return False

        # DB 상태 업데이트
        if not DBPTR().UpdateSubProcStatus(proc_ctl.ProcessId, proc_ctl.Status):
            logger.error("Update SubProc Status Error : %s", DBPTR().GetErrorMsg())
            return False

        info.SettingStatus = START if proc_ctl.Status == START else STOP

        if proc_ctl.Status == START:
            if self._execute_one(info):
                MAINPTR().SendAsciiError(
                    1, "The SubProc(%s) start successful", proc_ctl.ProcessId)
            else:
                MAINPTR().SendAsciiError(
                    1, "SubProc(%s) start failed", proc_ctl.ProcessId)
        elif proc_ctl.Status == STOP:
            self.StopSubProc(info)

        return True

    # =========================================================================
    # FindSubProcInfo
    # =========================================================================

    def FindSubProcInfo(self, proc_id_str: str) -> Optional[AS_SUB_PROC_INFO_T]:
        """C++: FindSubProcInfo(string ProcIdStr)"""
        return self._sub_proc_info_map.get(proc_id_str)

    # =========================================================================
    # ReceiveTimeOut  (AsWorld 가상함수 오버라이드)
    # =========================================================================

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """
        C++: ReceiveTimeOut(int Reason, void* ExtraReason)
        AsWorld.SetTimer 콜백. WAIT_DATA_HANDLER_START_TIMEOUT 처리.
        extra_reason = proc_id_str (str)
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR, DBPTR

        if reason == WAIT_DATA_HANDLER_START_TIMEOUT:
            proc_id_str: str = extra_reason if isinstance(extra_reason, str) else ""
            logger.debug("Recv Timeout WAIT_DATA_HANDLER_START_TIMEOUT : %s",
                         proc_id_str)
            MAINPTR().SendAsciiError(1, "SubProc(%s) Start Error", proc_id_str)

            # 타이머 맵에서 제거 (타이머 만료이므로 cancel 불필요)
            self._timer_key_map.pop(proc_id_str, None)

            info = self.FindSubProcInfo(proc_id_str)
            if info is None:
                logger.error("SubProc Info Can't Find : %s", proc_id_str)
                return

            logger.debug("SubProc %s Status is setting STOP", proc_id_str)

            if not DBPTR().UpdateSubProcStatus(proc_id_str, STOP):
                logger.error("Update SubProc Status Error : %s",
                             DBPTR().GetErrorMsg())
                return

            info.SettingStatus  = STOP
            info.CurStatus      = STOP
            info.RequestStatus  = WAIT_NO
            MAINPTR().SendInfoChange(info)

    # =========================================================================
    # KillSubProc
    # =========================================================================

    def KillSubProc(self, proc_id_str: str) -> None:
        """C++: KillSubProc(string ProcIdStr) – 원격 프로세스 강제 종료."""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        info = self.FindSubProcInfo(proc_id_str)
        if info is None:
            logger.error("Can't Find SubProc : %s", proc_id_str)
            return

        cmd = (
            f"~/NAA/Bin/RunCommand CLIENT "
            f"{info.IpAddress} {MAINPTR().m_RunCmdPort} "
            f"'~{MAINPTR().GetUserName()}"
            f"{MAINPTR().GetStartDir()}/Bin/KillProcess {info.ProcIdStr}'"
        )
        logger.debug("Kill SubProc : %s", cmd)
        subprocess.Popen(cmd, shell=True)

    # =========================================================================
    # RecvInfoChange
    # =========================================================================

    def RecvInfoChange(self, info: AS_SUB_PROC_INFO_T,
                       result_msg: list) -> bool:
        """
        C++: RecvInfoChange(AS_SUB_PROC_INFO_T* Info, char* ResultMsg)
        result_msg: [str] 1-원소 리스트 (C++ char* 출력 인자 대응).
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR

        if info.RequestStatus == CREATE_DATA:
            new_info = copy.copy(info)
            new_info.RequestStatus = WAIT_NO
            new_info.CurStatus     = STOP
            new_info.SettingStatus = STOP
            self._sub_proc_info_map[new_info.ProcIdStr] = new_info
            MAINPTR().SendInfoChange(info)
            return True

        if info.RequestStatus == UPDATE_DATA:
            if info.OldProcIdStr not in self._sub_proc_info_map:
                result_msg[0] = f"Can't Find SubProc : {info.OldProcIdStr}"
                return False
            del self._sub_proc_info_map[info.OldProcIdStr]
            new_info = copy.copy(info)
            new_info.CurStatus     = STOP
            new_info.SettingStatus = STOP
            new_info.RequestStatus = WAIT_NO
            new_info.OldProcIdStr  = ""
            self._sub_proc_info_map[new_info.ProcIdStr] = new_info
            MAINPTR().SendInfoChange(info)
            return True

        if info.RequestStatus == DELETE_DATA:
            if info.ProcIdStr not in self._sub_proc_info_map:
                result_msg[0] = f"Can't Find SubProc : {info.ProcIdStr}"
                return False
            del self._sub_proc_info_map[info.ProcIdStr]
            MAINPTR().SendInfoChange(info)
            return True

        return False