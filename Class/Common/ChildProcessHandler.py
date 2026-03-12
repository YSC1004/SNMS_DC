# -*- coding: utf-8 -*-
"""
ChildProcessHandler.h / ChildProcessHandler.C  →  ChildProcessHandler.py
Python 3.11.10 변환

변환 설계:
  ChildProcessHandler → ChildProcessHandler  (추상 클래스)

C++ → Python 주요 변환 포인트:
  new ClearSignalSensor(this)  → ClearSignalSensor(self) (GC 위임)
  ChildSignalSensor            → C++ 원본에서 주석 처리됨 → 미생성 유지
  KillAllProc() 순수 가상      → @abstractmethod kill_all_proc()
  WaitProc() virtual + TRACE   → wait_proc() logger.debug

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
from abc import ABC, abstractmethod

from Common.ClearSignalSensor import ClearSignalSensor

logger = logging.getLogger(__name__)


class ChildProcessHandler(ABC):
    """
    C++ ChildProcessHandler 대응 추상 클래스.
    SIGINT 수신 시 kill_all_proc() 을 호출하는 구조를 제공한다.
    하위 클래스에서 kill_all_proc() 을 반드시 구현해야 한다.

    사용 예:
        class MyProcHandler(ChildProcessHandler):
            def kill_all_proc(self):
                for pid in self._pids:
                    os.kill(pid, signal.SIGTERM)
    """

    def __init__(self) -> None:
        # C++ 원본에서 ChildSignalSensor 는 주석 처리 → 미생성 유지
        self._clear_signal_sensor = ClearSignalSensor(self)

    def process_all_kill(self) -> None:
        """C++ ProcessAllKill() 대응. kill_all_proc() 위임."""
        self.kill_all_proc()

    @abstractmethod
    def kill_all_proc(self) -> None:
        """C++ KillAllProc() 순수 가상함수 대응. 하위 클래스에서 구현."""
        ...

    def wait_proc(self) -> None:
        """C++ WaitProc() virtual 대응 — 기본 구현은 로그만 출력."""
        logger.debug("ChildProcessHandler.wait_proc virtual function")