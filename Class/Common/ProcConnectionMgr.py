# -*- coding: utf-8 -*-
"""
ProcConnectionMgr.h / ProcConnectionMgr.C  →  ProcConnectionMgr.py
Python 3.11.10 변환

변환 설계:
  ProcConnectionMgr → ProcConnectionMgr  (ConnectionMgr 상속, 추상 클래스)

C++ → Python 주요 변환 포인트:
  fork() / execv()                   → subprocess.Popen()
  ProcPidInfoMap (map<string,int>)   → dict[str, int]
  frStringVector (vector<string>)    → list[str]
  ProcessInfoList (list<AS_PROCESS_STATUS_T>) → list[AsProcessStatusT]
  frTime()                           → datetime.now()
  SetGErrMsg(...)                    → logger.error(...)
  frSignalEventSrc::SignalsRelease() → FrSignalEventSrc.signals_release()
  ProcessDead() 순수 가상            → @abstractmethod process_dead()
  PROCESS_WAIT_TIME = 5              → 모듈 상수
  ORDER_KILL                         → CommType 상수 참조

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
import os
import subprocess
from abc import abstractmethod
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from Common.ConnectionMgr import ConnectionMgr
from Common.ProcClearTimer import ProcClearTimer
from Common.ChildProcessManager import ChildProcessManager
from Common.CommType import AsProcessStatusT
from Common.AsSocket import AsSocket

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

PROCESS_WAIT_TIME = 5   # C++ #define PROCESS_WAIT_TIME 5


class ProcConnectionMgr(ConnectionMgr):
    """
    C++ ProcConnectionMgr 대응 추상 클래스.
    자식 프로세스 기동/종료/상태 관리 및 ConnectionMgr 소켓 관리를 통합.
    하위 클래스에서 process_dead() 를 반드시 구현해야 한다.
    """

    def __init__(self) -> None:
        super().__init__()
        self._proc_pid_info:  dict[str, int] = {}   # ProcPidInfoMap
        self._proc_clear_timer = ProcClearTimer()

    # ── PID 맵 조회 / 제거 ───────────────────

    def get_proc_name(self, pid: int) -> str:
        """C++ GetProcName(int Pid) 대응. 없으면 "" 반환."""
        for name, p in self._proc_pid_info.items():
            if p == pid:
                return name
        logger.debug("Can't Find Process Name Pid(%d)", pid)
        return ""

    def get_proc_pid(self, proc_name: str) -> int:
        """C++ GetProcPid(string ProcName) 대응. 없으면 -1 반환."""
        pid = self._proc_pid_info.get(proc_name, -1)
        if pid == -1:
            logger.debug("Can't Find Process Pid : %s", proc_name)
        return pid

    def remove_pid(self, proc_name: str) -> bool:
        """C++ RemovePid(string ProcName) 대응. 없으면 에러 로그 후 False 반환."""
        if proc_name not in self._proc_pid_info:
            logger.error("Can't Find Process Pid : %s", proc_name)
            return False
        del self._proc_pid_info[proc_name]
        return True

    # ── 프로세스 기동 / 종료 ─────────────────

    def start_proc(self, name: str, args: list[str]) -> int:
        """
        C++ StartProc(string Name, frStringVector Args) 대응.
        fork/execv 대신 subprocess.Popen 사용.
        args[0] = 실행 파일 경로, args[1:] = 인자.
        성공 시 PID 반환, 실패 시 -1 반환.
        """
        if not args:
            logger.error("start_proc: empty args (name=%s)", name)
            return -1

        try:
            proc = subprocess.Popen(args)
        except OSError as e:
            logger.error("Process Fork/Exec Error(Name:%s) : %s", name, e)
            return -1

        pid = proc.pid
        if name in self._proc_pid_info:
            logger.error(
                "Process Info Insert Error : Name(%s), pid(%d)", name, pid
            )
        else:
            self._proc_pid_info[name] = pid

        return pid

    def stop_process_by_name(self, name: str) -> bool:
        """C++ StopProcess(string Name) 대응."""
        pid = self._proc_pid_info.get(name, -1)
        if pid == -1:
            logger.error("Can't Find Process Name : %s", name)
            return True   # C++ 원본도 못 찾으면 true 반환
        return ChildProcessManager.kill_proc(pid)

    def stop_process_by_pid(self, pid: int) -> bool:
        """C++ StopProcess(int Pid) 대응."""
        for p in self._proc_pid_info.values():
            if p == pid:
                return ChildProcessManager.kill_proc(pid)
        return False

    # ── 프로세스 상태 조회 ────────────────────

    @staticmethod
    def get_process_info_by_pid(
        pid: int, process: AsProcessStatusT
    ) -> bool:
        """
        C++ static GetProcessInfo(int Pid, AS_PROCESS_STATUS_T*) 대응.
        PID 와 현재 시각을 process 에 채워 넣는다.
        """
        now = datetime.now()
        process.pid = pid
        process.start_time = now.strftime("%Y/%m/%d %H:%M:%S")
        return True

    def get_process_info_by_name(
        self, proc_name: str, process: AsProcessStatusT
    ) -> bool:
        """C++ GetProcessInfo(string ProcName, AS_PROCESS_STATUS_T*) 대응."""
        pid = self.get_proc_pid(proc_name)
        if pid == -1:
            return False
        return ProcConnectionMgr.get_process_info_by_pid(pid, process)

    def get_process_info_list(
        self, proc_info_list: list[AsProcessStatusT]
    ) -> None:
        """C++ GetProcessInfo(ProcessInfoList&) 대응. 전체 프로세스 상태를 리스트에 추가."""
        for name, pid in self._proc_pid_info.items():
            status = AsProcessStatusT()
            status.process_id = name
            ProcConnectionMgr.get_process_info_by_pid(pid, status)
            proc_info_list.append(status)

    # ── 이벤트 처리 ───────────────────────────

    def various_ack_check_time_out(self, socket: AsSocket) -> None:
        """C++ VariousAckCheckTimeOut(AsSocket*) 대응."""
        logger.error(
            "Process Ack Check TimeOut : %s", socket.get_session_name()
        )
        self.stop_process_by_name(socket.get_session_name())

    def child_process_dead(self, socket: AsSocket, status: int = -1) -> None:
        """
        C++ ChildProcessDead(AsSocket*, int Status) 대응.
        PID 맵 제거 → 소켓 제거 → ClearTimer 등록 → ProcessDead() 호출.
        """
        from Common.CommType import ORDER_KILL

        name = socket.get_session_name()
        pid  = self.get_proc_pid(name)

        self.remove_pid(name)
        self.remove(socket)

        logger.debug(
            "%s(%d) Process Dead(%s)",
            name, pid,
            "NORMAL" if status == ORDER_KILL else "ABNORMAL",
        )

        self._proc_clear_timer.set_timer(PROCESS_WAIT_TIME, pid)
        self.process_dead(name, pid, status)

    # ── 순수 가상함수 ─────────────────────────

    @abstractmethod
    def process_dead(self, name: str, pid: int, status: int = -1) -> None:
        """C++ ProcessDead() 순수 가상함수 대응. 하위 클래스에서 구현."""
        ...