# -*- coding: utf-8 -*-
"""
ChildProcessManager.h / ChildProcessManager.C  →  ChildProcessManager.py
Python 3.11.10 변환

변환 설계:
  ChildProcessManager → ChildProcessManager  (ChildProcessHandler 상속)

C++ → Python 주요 변환 포인트:
  PidSet (set<int>)          → set[int]  (_pid_set)
  kill(pid, SIGKILL)         → os.kill(pid, signal.SIGKILL)
  waitpid(pid, WNOHANG)      → os.waitpid(pid, os.WNOHANG)
  set.insert().second        → pid not in / add()
  KillAllProc() 순수가상 구현 → kill_all_proc() override

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
import os
import signal

from Common.ChildProcessHandler import ChildProcessHandler

logger = logging.getLogger(__name__)


class ChildProcessManager(ChildProcessHandler):
    """
    C++ ChildProcessManager 대응.
    자식 프로세스 PID 집합을 관리하며 SIGKILL 송신 및 waitpid 처리를 담당.
    """

    def __init__(self) -> None:
        super().__init__()
        self._pid_set: set[int] = set()

    # ── PID 관리 ──────────────────────────────

    def add_pid(self, pid: int) -> bool:
        """
        C++ AddPid(int Pid) 대응.
        이미 존재하는 PID 이면 False 반환.
        """
        if pid in self._pid_set:
            return False
        self._pid_set.add(pid)
        return True

    def remove_pid(self, pid: int) -> bool:
        """
        C++ RemovePid(int Pid) 대응.
        존재하지 않는 PID 이면 에러 로그 후 False 반환.
        """
        if pid not in self._pid_set:
            logger.error("Can't Find Pid : %d", pid)
            return False
        self._pid_set.discard(pid)
        return True

    # ── 프로세스 종료 ──────────────────────────

    @staticmethod
    def kill_proc(pid: int) -> bool:
        """
        C++ KillProc(int Pid) 대응.
        단일 프로세스에 SIGKILL 전송. 실패 시 False 반환.
        """
        try:
            os.kill(pid, signal.SIGKILL)
            return True
        except OSError:
            return False

    def kill_all_proc(self) -> None:
        """
        C++ KillAllProc() 순수 가상함수 구현.
        PID 집합 전체에 SIGKILL 전송 후 집합 초기화.
        """
        logger.debug("Process All Kill...................")
        for pid in list(self._pid_set):
            try:
                os.kill(pid, signal.SIGKILL)
                logger.debug("Process Kill : %d", pid)
            except OSError:
                logger.debug("Process Kill Error(pid:%d)", pid)
        self._pid_set.clear()

    # ── 자식 프로세스 대기 ────────────────────

    def wait_proc(self) -> None:
        """
        C++ WaitProc() 대응.
        WNOHANG 으로 종료된 자식 PID 를 찾아 집합에서 제거.
        """
        for pid in list(self._pid_set):
            try:
                ret, _ = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                # 이미 회수된 프로세스
                self._pid_set.discard(pid)
                continue

            if ret == pid:
                logger.debug("Recv Child Signal OK...(PID:%d)", pid)
                self._pid_set.discard(pid)
                break