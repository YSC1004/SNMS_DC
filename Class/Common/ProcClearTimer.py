# -*- coding: utf-8 -*-
"""
ProcClearTimer.h / ProcClearTimer.C  →  ProcClearTimer.py
Python 3.11.10 변환

변환 설계:
  ProcClearTimer → ProcClearTimer  (FrTimerSensor 상속)

C++ → Python 주요 변환 포인트:
  waitpid(Reason, &status, WNOHANG) → os.waitpid(reason, os.WNOHANG)
  Reason (int) 은 PID 로 사용됨    → reason 파라미터를 pid 로 처리

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
import os

from Event.fr_timer_sensor import FrTimerSensor

logger = logging.getLogger(__name__)


class ProcClearTimer(FrTimerSensor):
    """
    C++ ProcClearTimer 대응.
    타이머 만료 시 reason 값을 PID 로 사용하여 WNOHANG waitpid 를 수행한다.
    좀비 프로세스 회수 용도.
    """

    def __init__(self) -> None:
        super().__init__()

    def receive_time_out(self, reason: int, extra_reason: object = None) -> None:
        """
        C++ ReceiveTimeOut(int Reason, void* ExtraReason) 대응.
        reason 을 PID 로 간주하여 WNOHANG waitpid 호출.
        """
        try:
            ret, _ = os.waitpid(reason, os.WNOHANG)
        except ChildProcessError:
            ret = -1

        logger.debug("WaitPid(%d) Result : %d", reason, ret)