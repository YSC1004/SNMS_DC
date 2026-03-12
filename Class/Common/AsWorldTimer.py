"""
[변경이력]
2014.07.08  초기 작성
Python 변환: AsWorldTimer.h/.C → AsWorldTimer.py

역할: AsWorld 의 타이머 위임(delegate) 클래스
  - C++: frTimerSensor 상속 → asyncio.Task 기반
  - SetTimer / SetTimer2 로 1회성 또는 지연 타이머 등록
  - 만료 시 AsWorld.ReceiveTimeOut(reason, extra_reason) 호출
  - CancelTimer 로 특정 키의 타이머 취소

※ AsWorld.SetTimer() 가 내부적으로 이 클래스를 사용한다.
   AsWorld 에서 직접 asyncio.Task 로 처리해도 되지만,
   C++ 원본 구조(AsWorldTimer 분리)를 유지하기 위해 독립 클래스로 변환.
"""

import asyncio
import logging
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from Common.AsWorld import AsWorld

logger = logging.getLogger(__name__)


class AsWorldTimer:
    """
    C++: class AsWorldTimer : public frTimerSensor

    AsWorld 로부터 타이머 등록 요청을 받아
    asyncio.Task 로 관리하고, 만료 시 AsWorld.ReceiveTimeOut() 을 호출한다.

    Args:
        world: 콜백 대상 AsWorld 인스턴스
    """

    def __init__(self, world: "AsWorld"):
        self._world:   "AsWorld"            = world
        self._tasks:   Dict[int, asyncio.Task] = {}   # key → Task
        self._key_seq: int                  = 0

    def __del__(self):
        self._cancel_all()

    # ──────────────────────────────────────────
    # 타이머 등록
    # ──────────────────────────────────────────

    def SetTimer(self, interval_sec: int, reason: int,
                 extra_reason: object = None) -> int:
        """
        C++: frTimerSensor::SetTimer(int Interval, int Reason, void*)
        interval_sec 초 후 AsWorld.ReceiveTimeOut(reason) 호출.
        Returns: 타이머 키 (CancelTimer 에 사용)
        """
        return self._schedule(float(interval_sec), reason, extra_reason)

    def SetTimer2(self, mili_sec: int, reason: int,
                  extra_reason: object = None) -> int:
        """밀리초 단위 타이머"""
        return self._schedule(mili_sec / 1000.0, reason, extra_reason)

    def _schedule(self, delay: float, reason: int,
                  extra_reason: object) -> int:
        self._key_seq += 1
        key = self._key_seq
        try:
            task = asyncio.create_task(
                self._fire(delay, reason, extra_reason, key))
            self._tasks[key] = task
        except RuntimeError:
            logger.debug("AsWorldTimer: no running event loop (key=%d)", key)
        return key

    async def _fire(self, delay: float, reason: int,
                    extra_reason: object, key: int) -> None:
        """C++: ReceiveTimeOut(int Reason, void* ExtraReason)"""
        try:
            await asyncio.sleep(delay)
            self._tasks.pop(key, None)
            self._world.ReceiveTimeOut(reason, extra_reason)
        except asyncio.CancelledError:
            pass

    # ──────────────────────────────────────────
    # 타이머 취소
    # ──────────────────────────────────────────

    def CancelTimer(self, key: int) -> bool:
        task = self._tasks.pop(key, None)
        if task:
            task.cancel()
            return True
        return False

    def _cancel_all(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()