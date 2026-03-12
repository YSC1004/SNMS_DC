"""
[변경이력]
2014.07.08  초기 작성
Python 변환: AsWorldLogTimer.h/.C → AsWorldLogTimer.py

역할: 로그 파일 교체 주기 타이머
  - 만료 시 AsWorld.LogFileChangedEvent() 호출
  - AsWorldTimer 와 구조 동일, 콜백 대상만 다름
  - AsWorld.LogFileChangedEvent() 내에서 다음 교체 시각까지
    SetTimer() 를 재호출하여 1회성 타이머로 연쇄 동작
"""

import asyncio
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from Common.AsWorld import AsWorld

logger = logging.getLogger(__name__)


class AsWorldLogTimer:
    """
    C++: class AsWorldLogTimer : public frTimerSensor

    로그 파일 교체 전용 1회성 타이머.
    SetTimer(delay_sec) 호출 → delay_sec 후 AsWorld.LogFileChangedEvent() 실행.
    LogFileChangedEvent() 내부에서 다음 주기로 SetTimer() 를 재호출하므로
    연속 동작이 보장된다.

    Args:
        world: 콜백 대상 AsWorld 인스턴스
    """

    def __init__(self, world: "AsWorld"):
        self._world: "AsWorld"            = world
        self._task:  Optional[asyncio.Task] = None

    def __del__(self):
        self.cancel()

    # ──────────────────────────────────────────
    # 타이머 등록 / 취소
    # ──────────────────────────────────────────

    def SetTimer(self, delay_sec: int, reason: int = 1,
                 extra_reason: object = None) -> None:
        """
        C++: frTimerSensor::SetTimer(int Interval, int Reason)
        delay_sec 초 후 LogFileChangedEvent() 를 1회 호출.
        기존 타이머가 있으면 취소 후 재등록.
        """
        self.cancel()
        try:
            self._task = asyncio.create_task(self._fire(float(delay_sec)))
        except RuntimeError:
            logger.debug("AsWorldLogTimer: no running event loop")

    def cancel(self) -> None:
        """대기 중인 타이머 취소"""
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    # ──────────────────────────────────────────
    # 타이머 만료 콜백
    # ──────────────────────────────────────────

    async def _fire(self, delay: float) -> None:
        """
        C++: ReceiveTimeOut(int Reason, void* ExtraReason)
        → m_AsWorld->LogFileChangedEvent() 위임
        """
        try:
            await asyncio.sleep(delay)
            self._task = None
            self._world.LogFileChangedEvent()
        except asyncio.CancelledError:
            pass