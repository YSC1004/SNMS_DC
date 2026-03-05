# -*- coding: utf-8 -*-
"""
frTimerSensor.h / frTimerSensor.C  →  fr_timer_sensor.py
Python 3.11.10 버전

변환 설계:
  frTimerSensor    → FrTimerSensor  (FrSensor 상속, 추상 클래스)

C++ → Python 주요 변환 포인트:
  TimerList* m_TimerList           → list[_TimeOut]  (정렬 삽입 유지)
  TimeOut 구조체                   → _TimeOut dataclass
  timeb / ftime()                  → time.time()
  time_t m_MinTimeOutSec           → _min_deadline : float  (Unix 절대 시각, 초+밀리초 통합)
  int    m_MinTimeOutMiliSec       → (통합, 별도 필드 불필요)
  timer_key (int typedef)          → int
  LONG_TIME (31536000 = 1년)       → _LONG_TIME
  MakeSelectRequest(fd_set*, tv*)  → make_select_request() → dict{'deadline': float}
  GetEvents(fd_set*, tv*)          → get_events()
  SubjectChanged()                 → subject_changed()
  SetTimer / SetTimer2             → set_timer() / set_timer2()
  SetTimeOut()                     → _set_timeout()
  CancelTimer / CancelAllTimer     → cancel_timer() / cancel_all_timer()
  GetTimerCount()                  → get_timer_count()
  ReceiveTimeOut() 순수 가상함수   → @abstractmethod receive_time_out()

변경 이력:
  v1 - 초기 변환
"""

import logging
import time
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from fr_sensor import FrSensor, SensorType

logger = logging.getLogger(__name__)

_LONG_TIME: int = 31536000   # 1년(초) — 더미 타이머용 C++ LONG_TIME 대응


# ─────────────────────────────────────────────────────────────────────────────
# _TimeOut  (C++ TimeOut 구조체 대응)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class _TimeOut:
    """
    C++ TimeOut 구조체 대응.
    deadline 을 float(Unix 초, 밀리초 포함) 으로 통합 저장.
      C++ m_TimeOutSec + m_TimeOutMiliSec  →  deadline : float
    """
    deadline:     float          # 절대 만료 시각 (Unix 초, 소수점 = 밀리초)
    reason:       int
    key:          int
    extra_reason: object = field(default=None, repr=False)


# ─────────────────────────────────────────────────────────────────────────────
# FrTimerSensor
# ─────────────────────────────────────────────────────────────────────────────
class FrTimerSensor(FrSensor):
    """
    C++ frTimerSensor 대응 추상 클래스.
    타이머 만료 시 ReceiveTimeOut() 을 호출하는 TIMER_SENSOR.

    TimerList 는 deadline 오름차순 정렬을 유지하며,
    항상 더미 타이머(1년 후)가 1개 이상 존재한다.

    멤버 매핑:
      m_TimerList          → _timer_list    : list[_TimeOut]
      m_KeySequence        → _key_sequence  : int
      m_MinTimeOutSec/Msec → _min_deadline  : float  (통합)
    """

    def __init__(self) -> None:
        super().__init__()
        self._sensor_type  = SensorType.TIMER
        self._timer_list:  list[_TimeOut] = []
        self._key_sequence: int           = 0
        self._min_deadline: float         = 0.0

        self.register_sensor()
        self._object_type = 3

        # 더미 타이머 (C++ SetTimer(LONG_TIME, 10000) 대응)
        self.set_timer(_LONG_TIME, 10000)

    def __del__(self) -> None:
        self._timer_list.clear()
        self.unregister_sensor()

    # ------------------------------------------------------------------ #
    # FrSensor 추상 메서드 구현
    # ------------------------------------------------------------------ #
    def make_select_request(self) -> dict:
        """
        C++ MakeSelectRequest(fd_set*, timeval*) 대응.

        C++ 동작:
          Time 이 -1/-1 이면 (첫 센서) 자신의 m_MinTimeout 으로 초기화.
          이미 값이 있으면 더 작은 쪽으로 갱신.

        Python 변환:
          FrTimerEventSrc 가 모든 센서의 deadline 최솟값을 직접 비교하므로
          여기서는 자신의 _min_deadline 을 {'deadline': float} 으로 반환.
        """
        if not self._timer_list:
            return {}
        return {'deadline': self._min_deadline}

    def get_events(self) -> None:
        """
        C++ GetEvents(fd_set*, timeval*) 대응.
        타이머 큐의 맨 앞 항목이 만료됐으면 InsertNotifySensor() 로 등록.
        """
        if not self._timer_list:
            return

        now = time.time()
        if now >= self._timer_list[0].deadline:
            if self.world_ptr and self.world_ptr.timer_event_src:
                self.world_ptr.timer_event_src.insert_notify_sensor(self)

    # ------------------------------------------------------------------ #
    # SubjectChanged  (C++ SubjectChanged() 대응)
    # ------------------------------------------------------------------ #
    def subject_changed(self) -> int:
        """
        C++ SubjectChanged() 대응.
        만료된 타이머를 큐에서 꺼내 receive_time_out() 을 호출한다.
        """
        if not self._timer_list:
            return 1

        now = time.time()
        entry = self._timer_list[0]

        if now >= entry.deadline:
            self._timer_list.pop(0)
            self.receive_time_out(entry.reason, entry.extra_reason)

            # receive_time_out() 안에서 unregister 됐을 수 있음
            if self.world_ptr and self.world_ptr.timer_event_src:
                if not self.world_ptr.timer_event_src.is_exist_instance(self):
                    return 1

        self._update_min_deadline()
        return 1

    # ------------------------------------------------------------------ #
    # 타이머 설정 / 취소
    # ------------------------------------------------------------------ #
    def set_timer(self, sec: int, reason: int,
                  extra_reason: object = None) -> int:
        """C++ SetTimer(int Sec, int Reason, void*) 대응. 단위: 초."""
        if sec < 1:
            logger.error('set_timer: invalid value %d sec', sec)
            return -1
        return self._set_timeout(sec, 0, reason, extra_reason)

    def set_timer2(self, milli_sec: int, reason: int,
                   extra_reason: object = None) -> int:
        """C++ SetTimer2(int MiliSec, int Reason, void*) 대응. 단위: 밀리초."""
        if milli_sec < 1:
            logger.error('set_timer2: invalid value %d ms', milli_sec)
            return -1
        sec      = milli_sec // 1000
        milli_sec = milli_sec  % 1000
        return self._set_timeout(sec, milli_sec, reason, extra_reason)

    def cancel_timer(self, key: int) -> bool:
        """C++ CancelTimer(timer_key) 대응."""
        for i, t in enumerate(self._timer_list):
            if t.key == key:
                self._timer_list.pop(i)
                self._restore_after_cancel()
                return True
        return False

    def cancel_all_timer(self) -> None:
        """C++ CancelAllTimer() 대응."""
        self._timer_list.clear()
        self._min_deadline = 0.0
        self.set_timer(_LONG_TIME, 10000)   # 더미 타이머 재등록

    def get_timer_count(self) -> int:
        """C++ GetTimerCount() 대응. 더미 타이머 1개 제외한 실제 타이머 수."""
        return max(0, len(self._timer_list) - 1)

    # ------------------------------------------------------------------ #
    # 순수 가상 함수
    # ------------------------------------------------------------------ #
    @abstractmethod
    def receive_time_out(self, reason: int, extra_reason: object = None) -> None:
        """C++ ReceiveTimeOut(int Reason, void*) 순수 가상함수 대응."""
        ...

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #
    def _set_timeout(self, sec: int, milli_sec: int,
                     reason: int, extra_reason: object = None) -> int:
        """
        C++ SetTimeOut(int Sec, int MiliSec, ...) 대응.
        deadline = 현재시각 + 지연시간 으로 계산 후 정렬 삽입.
        """
        now      = time.time()
        deadline = now + sec + milli_sec / 1000.0

        self._key_sequence += 1
        entry = _TimeOut(
            deadline     = deadline,
            reason       = reason,
            key          = self._key_sequence,
            extra_reason = extra_reason,
        )

        # 정렬 삽입 (deadline 오름차순)
        inserted = False
        for i, t in enumerate(self._timer_list):
            if t.deadline > deadline:
                self._timer_list.insert(i, entry)
                inserted = True
                break
        if not inserted:
            self._timer_list.append(entry)

        self._update_min_deadline()
        return self._key_sequence

    def _update_min_deadline(self) -> None:
        """_min_deadline 을 큐 맨 앞 항목으로 갱신."""
        if self._timer_list:
            self._min_deadline = self._timer_list[0].deadline
        else:
            self._min_deadline = 0.0

    def _restore_after_cancel(self) -> None:
        """
        cancel_timer() 후 처리.
        C++ : 빈 리스트면 더미 타이머 재등록, 아니면 _min 갱신.
        """
        if self._timer_list:
            self._update_min_deadline()
        else:
            self._min_deadline = 0.0
            self.set_timer(_LONG_TIME, 10000)