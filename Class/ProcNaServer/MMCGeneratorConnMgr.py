"""
MMCGeneratorConnMgr.py
C++ MMCGeneratorConnMgr.h/.C → Python 변환

MMC Generator/Scheduler/JobMonitor 연결 관리자.
  - ProcConnectionMgr 상속 (start_proc / process_dead)
  - MMCGenerator/Scheduler/JobMonitor 세션 관리
  - MMC 요청 전달, MMC 로그 전달
  - 프로세스 상태 / 로그 상태 관리
"""

import asyncio
import copy
import logging
import threading
from typing import Optional, Dict, TYPE_CHECKING

from Common.ProcConnectionMgr import ProcConnectionMgr  # start_proc/process_dead
from Common.CommTypeList import (
    AS_LOG_STATUS_T, AS_MMC_REQUEST_T, AS_MMC_LOG_T, AS_PROCESS_STATUS_T,
)
from Common.CommType import (
    ASCII_MMC_GENERATOR, ASCII_MMC_SCHEDULER, ASCII_JOB_MONITOR,
    START, STOP, LOG_ADD,
    ORDER_KILL,
    PROC_INIT_END, CMD_PROC_INIT,
    CMD_SCHEDULER_RULE_DOWN, CMD_COMMAND_RULE_DOWN,
    MMC_LOG,
)

if TYPE_CHECKING:
    from ProcNaServer.MMCGenConnection import MMCGenConnection

logger = logging.getLogger(__name__)

# LogStatusMap : name(str) → AS_LOG_STATUS_T
LogStatusMap = Dict[str, AS_LOG_STATUS_T]


class MMCGeneratorConnMgr(ProcConnectionMgr):
    """
    C++ MMCGeneratorConnMgr (ProcConnectionMgr 상속) 대응.

    뮤텍스:
      C++ pthread_mutex_t m_SocketRemoveLock
      → _socket_remove_lock() / _socket_remove_unlock() 오버라이드
    """

    def __init__(self) -> None:
        super().__init__()
        self._mmc_generator: Optional["MMCGenConnection"] = None
        self._mmc_scheduler: Optional["MMCGenConnection"] = None
        self._job_monitor:   Optional["MMCGenConnection"] = None
        self._mmc_generator_status: bool = False
        self._log_status_map: LogStatusMap = {}
        self._remove_lock = threading.Lock()    # C++: pthread_mutex_t

    def __del__(self) -> None:
        self._log_status_map.clear()

    # =========================================================================
    # ConnectionMgr 뮤텍스 오버라이드
    # =========================================================================

    def _socket_remove_lock(self) -> None:
        self._remove_lock.acquire()

    def _socket_remove_unlock(self) -> None:
        self._remove_lock.release()

    # =========================================================================
    # ProcConnectionMgr 추상 메서드 구현
    # =========================================================================

    def process_dead(self, name: str, pid: int, status: int = -1) -> None:
        """
        C++: ProcessDead(string Name, int Pid, int Status)
        ProcConnectionMgr.child_process_dead() 에서 호출.
        """
        self.SendProcessInfo(name, -1, STOP)

        if status != ORDER_KILL:
            from ProcNaServer.AsciiServerWorld import AsciiServerWorld
            AsciiServerWorld.m_WorldPtr.ProcessDead(name, pid)

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """C++: AcceptSocket()"""
        from ProcNaServer.MMCGenConnection import MMCGenConnection

        conn = MMCGenConnection(self)
        if not self.Accept(conn):
            logger.debug("MMCGenerator Socket Accept Error : %s",
                         self.GetObjErrMsg())
            return
        self.add(conn)                          # ConnectionMgr.add()

    # =========================================================================
    # SetMMCGeneratorSession
    # =========================================================================

    def SetMMCGeneratorSession(self, session_type: int,
                                mmc_con: Optional["MMCGenConnection"]) -> None:
        """C++: SetMMCGeneratorSession(int SessionType, MMCGenConnection*)"""
        if session_type == ASCII_MMC_GENERATOR:
            self._mmc_generator = mmc_con
            if mmc_con is None:
                self._mmc_generator_status = False

        elif session_type == ASCII_MMC_SCHEDULER:
            self._mmc_scheduler = mmc_con
            if mmc_con and self._mmc_generator_status:
                asyncio.ensure_future(mmc_con.SendPacket(CMD_PROC_INIT))

        elif session_type == ASCII_JOB_MONITOR:
            self._job_monitor = mmc_con

        else:
            logger.error("UnKnown SessionType : %d", session_type)

    # =========================================================================
    # SendMMCReqToMMCGen
    # =========================================================================

    def SendMMCReqToMMCGen(self, mmc_req: AS_MMC_REQUEST_T) -> None:
        """C++: SendMMCReqToMMCGen(AS_MMC_REQUEST_T*)"""
        self._socket_remove_lock()
        try:
            if self._mmc_generator and \
               self.is_valid_connection(self._mmc_generator):   # ConnectionMgr
                asyncio.ensure_future(
                    self._mmc_generator.SendMMCReqToMMCGen(mmc_req))
            else:
                logger.debug("MMCGenerator Is Not Connection")
        finally:
            self._socket_remove_unlock()

    # =========================================================================
    # SendMMCLog
    # =========================================================================

    def SendMMCLog(self, mmc_log: AS_MMC_LOG_T) -> None:
        """C++: SendMMCLog(AS_MMC_LOG_T*) — JobMonitor로 전송."""
        self._socket_remove_lock()
        try:
            if self._job_monitor and \
               self.is_valid_connection(self._job_monitor):
                asyncio.ensure_future(
                    self._job_monitor.SendMMCLog(mmc_log))
            else:
                logger.debug("Job Monitor is Not Connected")
        finally:
            self._socket_remove_unlock()

    # =========================================================================
    # UpdateMMCProcessLogStatus / GetLogStatusList
    # =========================================================================

    def UpdateMMCProcessLogStatus(self, status: AS_LOG_STATUS_T) -> None:
        """C++: UpdateMMCProcessLogStatus(AS_LOG_STATUS_T*)"""
        self._log_status_map.pop(status.name, None)

        if status.status == LOG_ADD:
            self._log_status_map[status.name] = copy.copy(status)

        from ProcNaServer.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld.m_WorldPtr.SendLogStatus(status)

    def GetLogStatusList(self, status_list: list) -> None:
        """C++: GetLogStatusList(LogStatusVector*)"""
        status_list.extend(self._log_status_map.values())

    # =========================================================================
    # SendProcessInfo
    # =========================================================================

    def SendProcessInfo(self, session_name: str,
                         process_type: int, status: int) -> None:
        """C++: SendProcessInfo(const char* SessionName, int ProcessType, int Status)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        proc_info = AS_PROCESS_STATUS_T()
        proc_info.ProcessId   = session_name
        proc_info.Status      = status

        if status == START:
            # ProcConnectionMgr.get_process_info_by_name()
            if not self.get_process_info_by_name(session_name, proc_info):
                return

        proc_info.ManagerId   = MAINPTR().GetProcName()
        proc_info.ProcessType = process_type
        MAINPTR().UpdateProcessInfo(proc_info)

    # =========================================================================
    # NotifyEvent
    # =========================================================================

    def NotifyEvent(self, session_type: int, msg_id: int) -> None:
        """C++: NotifyEvent(int sessionType, int msgId)"""
        if session_type == ASCII_MMC_GENERATOR:
            if msg_id == PROC_INIT_END:
                self._mmc_generator_status = True
                if self._mmc_scheduler:
                    if not asyncio.ensure_future(
                            self._mmc_scheduler.SendPacket(CMD_PROC_INIT)):
                        logger.error("MMCScheduler Socket Broken")
                        self.remove(self._mmc_scheduler)    # ConnectionMgr.remove()

        # ASCII_MMC_SCHEDULER / ASCII_JOB_MONITOR: C++ 원본 동일하게 처리 없음

    # =========================================================================
    # Rule Down 명령
    # =========================================================================

    def SendCmdSchedulerRuleDown(self) -> None:
        """C++: SendCmdSchedulerRuleDown() — Scheduler에 룰 다운 명령."""
        if self._mmc_scheduler:
            asyncio.ensure_future(
                self._mmc_scheduler.SendPacket(CMD_SCHEDULER_RULE_DOWN))

    def SendCmdCommandRuleDown(self) -> None:
        """C++: SendCmdCommandRuleDown() — Generator에 커맨드 룰 다운 명령."""
        if self._mmc_generator:
            asyncio.ensure_future(
                self._mmc_generator.SendPacket(CMD_COMMAND_RULE_DOWN))

    # =========================================================================
    # StartProc (ProcConnectionMgr.start_proc 위임)
    # =========================================================================

    def StartProc(self, name: str, args: list) -> int:
        """C++: StartProc() — ProcConnectionMgr.start_proc() 위임."""
        return self.start_proc(name, args)          # ProcConnectionMgr.start_proc()

    # =========================================================================
    # StopProcess
    # =========================================================================

    def StopProcess(self, session_name: str) -> bool:
        """C++: StopProcess(string SessionName) — 원본 항상 true 반환."""
        return True