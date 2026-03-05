# -*- coding: utf-8 -*-
"""
frTimerEventSrc.h / frTimerEventSrc.C  →  fr_timer_event_src.py
Python 3.11.10 버전

변환 설계:
  frTimerEventSrc  → FrTimerEventSrc  (FrEventSrc 상속)

C++ → Python 주요 변환 포인트:
  timeb / ftime()              → time.time()  (초+밀리초 동시 제공, float)
  time_t m_CurrentTimeSec      → current_time_sec  : float  (정수 초)
  int    m_CurrentTimeMiliSec  → current_time_msec : int    (밀리초)
  timeval* Time (in/out 파라미터)
    → make_select_request() 내부에서 계산 후 _next_timeout 에 저장
    → FrWorld._read_event() 가 _next_timeout 을 selector.select(timeout) 으로 사용
  fd_set 파라미터              → 제거 (fr_event_src 설계 동일)
  센서 없을 때 tv_sec=99999    → _next_timeout = 99999.0
  Time->tv_sec/tv_usec 계산    → float 초 단위로 통합

변경 이력:
  v1 - 초기 변환
"""

import logging
import time

from fr_event_src import FrEventSrc

logger = logging.getLogger(__name__)

_NO_SENSOR_TIMEOUT = 99999.0   # C++ tv_sec=99999 대응


class FrTimerEventSrc(FrEventSrc):
    """
    C++ frTimerEventSrc 대응 클래스.
    등록된 타이머 센서들의 만료 시각을 관리하고
    가장 가까운 만료까지의 대기 시간을 FrWorld 이벤트 루프에 제공한다.

    공개 멤버:
      current_time_sec  : float — 마지막 갱신 시각 (Unix 초, 정수부)
      current_time_msec : int   — 마지막 갱신 시각 (밀리초 부분, 0~999)

    내부 멤버:
      _next_timeout     : float — 다음 select() 까지의 대기 시간(초)
                                  FrWorld._read_event() 가 참조.
    """

    def __init__(self) -> None:
        super().__init__()
        self.current_time_sec:  float = 0.0
        self.current_time_msec: int   = 0
        self._next_timeout:     float = _NO_SENSOR_TIMEOUT

    # ------------------------------------------------------------------ #
    # 현재 시각 갱신 헬퍼  (C++ ftime(&curTime) 대응)
    # ------------------------------------------------------------------ #
    def _update_current_time(self) -> None:
        """
        time.time() 으로 현재 시각을 갱신.
        C++ : timeb.time (초) + timeb.millitm (밀리초) 분리 저장과 동일.
        """
        now = time.time()
        self.current_time_sec  = float(int(now))           # 정수 초
        self.current_time_msec = int((now % 1.0) * 1000)  # 밀리초 부분

    # ------------------------------------------------------------------ #
    # FrEventSrc 추상 메서드 구현
    # ------------------------------------------------------------------ #
    def make_select_request(self) -> dict:
        """
        C++ MakeSelectRequest(fd_set*, timeval*) 대응.

        C++ 동작:
          1. 센서 없으면 tv_sec=99999 (사실상 무한 대기)
          2. 각 활성 센서의 MakeSelectRequest() 로 가장 가까운 만료 절대시각 수집
          3. 현재 시각을 빼서 상대 대기시간(timeval) 계산

        Python 변환:
          센서의 make_select_request() 가 {'deadline': float(Unix초)} 를 반환하면
          그 중 최솟값에서 현재 시각을 뺀 값을 _next_timeout 으로 저장.
          FrWorld._read_event() 가 selector.select(timeout=_next_timeout) 에 사용.
        """
        if not self._sensor_list:
            self._next_timeout = _NO_SENSOR_TIMEOUT
            return {}

        self._update_current_time()
        now = self.current_time_sec + self.current_time_msec / 1000.0

        earliest_deadline = -1.0   # C++ Time->tv_sec = -1 초기값 대응

        for sensor in self._sensor_list:
            if sensor.is_enabled():
                req = {}
                try:
                    req = sensor.make_select_request()
                except Exception as e:
                    logger.error('make_select_request sensor error: %s', e)

                deadline = req.get('deadline', -1.0)
                if deadline > 0:
                    if earliest_deadline < 0 or deadline < earliest_deadline:
                        earliest_deadline = deadline

        # 상대 대기시간 계산 (C++ tv_sec/tv_usec 보정 로직 대응)
        if earliest_deadline < 0:
            self._next_timeout = _NO_SENSOR_TIMEOUT
        else:
            timeout = earliest_deadline - now
            if timeout < 0:
                timeout = 0.0
            self._next_timeout = timeout

        return {'timeout': self._next_timeout}

    def get_events(self) -> None:
        """
        C++ GetEvents(fd_set*, timeval*) 대응.
        현재 시각을 갱신한 뒤 활성 센서의 get_events() 를 순서대로 호출.
        각 타이머 센서는 내부에서 만료 여부를 판단하고
        insert_notify_sensor() 를 통해 디스패치 큐에 삽입한다.
        """
        self._update_current_time()

        for sensor in self._sensor_list:
            if sensor.is_enabled():
                try:
                    sensor.get_events()
                except Exception as e:
                    logger.error('get_events sensor error: %s', e)