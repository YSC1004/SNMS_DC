# -*- coding: utf-8 -*-
"""
ProcConnectionMgrTimer.h / ProcConnectionMgrTimer.C  →  ProcConnectionMgrTimer.py
Python 3.11.10 변환

변환 설계:
  ProcConnectionMgrTimer → ProcConnectionMgrTimer  (FrTimerSensor 상속)

C++ → Python 주요 변환 포인트:
  ProcConnectionMgr*  → TYPE_CHECKING 전용 임포트 (순환 참조 방지)
  ReceiveTimeOut() 빈 구현 → receive_time_out() pass 유지

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
from typing import TYPE_CHECKING

from Event.fr_timer_sensor import FrTimerSensor

if TYPE_CHECKING:
    from Common.ProcConnectionMgr import ProcConnectionMgr

logger = logging.getLogger(__name__)


class ProcConnectionMgrTimer(FrTimerSensor):
    """
    C++ ProcConnectionMgrTimer 대응.
    ProcConnectionMgr 에 연결된 타이머. ReceiveTimeOut() 은 현재 빈 구현.
    하위 클래스 또는 향후 확장에서 override 하여 사용.
    """

    def __init__(self, mgr: 'ProcConnectionMgr') -> None:
        super().__init__()
        self._proc_connection_mgr = mgr

    def receive_time_out(self, reason: int, extra_reason: object = None) -> None:
        """C++ ReceiveTimeOut() 빈 구현 대응 — no-op."""
        pass