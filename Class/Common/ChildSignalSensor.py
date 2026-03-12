# -*- coding: utf-8 -*-
"""
ChildSignalSensor.h / ChildSignalSensor.C  →  ChildSignalSensor.py
Python 3.11.10 변환

변환 설계:
  ChildSignalSensor → ChildSignalSensor  (FrSignalSensor 상속)

C++ → Python 주요 변환 포인트:
  frSignalSensor(SIGCHLD)      → FrSignalSensor.__init__(signal.SIGCHLD)
  m_ChildProcHandler->WaitProc → self._child_proc_handler.wait_proc()
  ChildProcessHandler*         → TYPE_CHECKING 전용 임포트 (순환 참조 방지)

비고:
  C++ ChildProcessHandler 에서 ChildSignalSensor 생성이 주석 처리되어 있음.
  현재는 미사용 상태이나 향후 활성화를 위해 변환 유지.

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
import signal
from typing import TYPE_CHECKING

from Event.fr_signal_sensor import FrSignalSensor

if TYPE_CHECKING:
    from Common.ChildProcessHandler import ChildProcessHandler

logger = logging.getLogger(__name__)


class ChildSignalSensor(FrSignalSensor):
    """
    C++ ChildSignalSensor 대응.
    SIGCHLD 수신 시 child_proc_handler.wait_proc() 을 호출한다.

    비고: ChildProcessHandler 생성자에서 현재 주석 처리되어 있음.
    """

    def __init__(self, child_proc_handler: 'ChildProcessHandler') -> None:
        """C++ ChildSignalSensor(ChildProcessHandler*) : frSignalSensor(SIGCHLD) 대응."""
        super().__init__(signal.SIGCHLD)
        self._child_proc_handler = child_proc_handler

    def subject_changed(self) -> int:
        """C++ SubjectChanged() 대응. SIGCHLD 수신 → wait_proc() 호출."""
        self._child_proc_handler.wait_proc()
        return 1