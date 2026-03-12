# -*- coding: utf-8 -*-
"""
ClearSignalSensor.h / ClearSignalSensor.C  →  ClearSignalSensor.py
Python 3.11.10 변환

변환 설계:
  ClearSignalSensor → ClearSignalSensor  (FrSignalSensor 상속)

C++ → Python 주요 변환 포인트:
  frSignalSensor(SIGINT)           → FrSignalSensor.__init__(signal.SIGINT)
  frSignalEventSrc::SignalsHold()  → FrSignalEventSrc.signals_hold()
  frWorld::m_MainWorldPtr->Exit(0) → FrWorld.m_MainWorldPtr.exit(0)
  ChildProcessHandler*             → 지연 임포트 (순환 참조 방지)

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
import signal
from typing import TYPE_CHECKING

from Event.fr_signal_sensor import FrSignalSensor
from Event.fr_signal_event_src import FrSignalEventSrc
from Event.fr_world import FrWorld

if TYPE_CHECKING:
    from Common.ChildProcessHandler import ChildProcessHandler

logger = logging.getLogger(__name__)


class ClearSignalSensor(FrSignalSensor):
    """
    C++ ClearSignalSensor 대응.
    SIGINT 수신 시 모든 자식 프로세스를 종료하고 메인 월드를 exit 한다.
    """

    def __init__(self, child_proc_handler: 'ChildProcessHandler') -> None:
        """C++ ClearSignalSensor(ChildProcessHandler*) : frSignalSensor(SIGINT) 대응."""
        super().__init__(signal.SIGINT)
        self._child_proc_handler = child_proc_handler

    def subject_changed(self) -> int:
        """
        C++ SubjectChanged() 대응.
        SIGINT 수신 → 시그널 홀드 → 자식 프로세스 전체 종료 → 메인 월드 exit.
        """
        FrSignalEventSrc.signals_hold()

        logger.debug("Recv SIGINT.....................")
        self._child_proc_handler.process_all_kill()
        FrWorld.m_MainWorldPtr.exit(0)
        return 1