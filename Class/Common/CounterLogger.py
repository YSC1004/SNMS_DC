# -*- coding: utf-8 -*-
"""
CounterLogger.h / CounterLogger.C  →  CounterLogger.py
Python 3.11.10 변환

변환 설계:
  CounterLogger → CounterLogger  (FrTimerSensor 상속)

C++ → Python 주요 변환 포인트:
  frTimerSensor                      → FrTimerSensor
  SetTimer(interval, 56789)          → set_timer(interval, 56789)
  frTime().GetDay() / GetTimeString() → datetime.now()
  frSTD_OUT(...)                      → logger.info(...)
  unsigned int m_GapCount/TotalCount → int (Python int 는 unsigned 무제한)

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
from datetime import datetime

from Event.fr_timer_sensor import FrTimerSensor

logger = logging.getLogger(__name__)

_TIMER_REASON = 56789


class CounterLogger(FrTimerSensor):
    """
    C++ CounterLogger 대응.
    주기적으로 카운트 현황을 출력하는 타이머 기반 로거.

    사용 예:
        cl = CounterLogger()
        cl.set_log_prefix("MyEvent")
        cl.set_log_interval(60)
        cl.start()
        ...
        cl.increase_count()
    """

    def __init__(self) -> None:
        super().__init__()
        self._interval:      int = 30
        self._cur_day:       int = datetime.now().day
        self._gap_count:     int = 0
        self._total_count:   int = 0
        self._prefix_string: str = ""
        self.reset_count()

    # ── 설정 ──────────────────────────────────

    def set_log_interval(self, interval: int = 30) -> None:
        """C++ SetLogInterval(int Interval=30) 대응."""
        self._interval = interval

    def set_log_prefix(self, prefix: str) -> None:
        """C++ SetLogPrefix(string Prefix) 대응."""
        self._prefix_string = prefix

    # ── 시작 ──────────────────────────────────

    def start(self) -> None:
        """C++ Start() 대응. 타이머를 시작한다."""
        self.set_timer(self._interval, _TIMER_REASON)

    # ── 카운트 조작 ───────────────────────────

    def increase_count(self) -> None:
        """C++ IncreaseCount() 대응."""
        self._gap_count   += 1
        self._total_count += 1

    def reset_count(self) -> None:
        """C++ ResetCount() 대응."""
        self._gap_count   = 0
        self._total_count = 0

    def get_total_count(self) -> int:
        """C++ GetTotalCount() 대응."""
        return self._total_count

    # ── 출력 ──────────────────────────────────

    def print(self) -> None:
        """
        C++ Print() 대응.
        구간 카운트 출력 후 gap_count 초기화.
        날짜가 바뀌면 total_count 도 초기화.
        """
        now = datetime.now()
        logger.info(
            "[%s - %s : During %d sec : %d ea, Today : %d ea]",
            now.strftime("%Y-%m-%d %H:%M:%S"),
            self._prefix_string,
            self._interval,
            self._gap_count,
            self._total_count,
        )
        self._gap_count = 0

        if self._cur_day != now.day:
            self._cur_day     = now.day
            self._total_count = 0

    # ── 타이머 콜백 ───────────────────────────

    def receive_time_out(self, reason: int, extra_reason: object = None) -> None:
        """C++ ReceiveTimeOut() 대응. 출력 후 타이머 재등록."""
        self.print()
        self.set_timer(self._interval, _TIMER_REASON)