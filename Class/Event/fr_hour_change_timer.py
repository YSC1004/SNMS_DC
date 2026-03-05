# -*- coding: utf-8 -*-
"""
frHourChangeTimer.h / frHourChangeTimer.C  →  fr_hour_change_timer.py
Python 3.11.10 버전

변환 설계:
  frHourChangeTimer → FrHourChangeTimer  (FrTimerSensor 상속)

C++ → Python 주요 변환 포인트:
  frTime::GetRemainHourSec() → remain_hour_time()  (datetime 으로 계산)
  frTimerSensor::SetTimer()  → super().set_timer()

변경 이력:
  v1 - 초기 변환
"""

import datetime
import logging

from fr_timer_sensor import FrTimerSensor

logger = logging.getLogger(__name__)


class FrHourChangeTimer(FrTimerSensor):
    """
    C++ frHourChangeTimer 대응 클래스.
    다음 정시(XX:00:00)까지 남은 초를 계산하여 타이머를 설정한다.
    정시가 되면 receive_time_out() 이 호출된다.

    사용 예:
        class MyHourChangeTimer(FrHourChangeTimer):
            def receive_time_out(self, reason, extra_reason=None):
                print('정시 도달 — 시간 변경 처리')
                self.set_timer()   # 다음 정시까지 재설정

        timer = MyHourChangeTimer()
        timer.set_timer()
    """

    def __init__(self) -> None:
        super().__init__()

    # ------------------------------------------------------------------ #
    # 타이머 설정
    # ------------------------------------------------------------------ #
    def set_timer(self) -> None:
        """
        C++ SetTimer() 대응.
        다음 정시까지 남은 초로 타이머 설정.
        reason=0 은 C++ 원본과 동일.
        """
        remain = self.remain_hour_time()
        if remain < 1:
            remain = 1   # 최소 1초 보장
        super().set_timer(remain, 0)

    # ------------------------------------------------------------------ #
    # 정시까지 남은 시간 계산
    # ------------------------------------------------------------------ #
    @staticmethod
    def remain_hour_time() -> int:
        """
        C++ RemainHourTime() / frTime::GetRemainHourSec() 대응.
        현재 시각 기준 다음 정시(XX:00:00)까지 남은 초(int) 반환.
        """
        now        = datetime.datetime.now()
        next_hour  = (now + datetime.timedelta(hours=1)).replace(
                         minute=0, second=0, microsecond=0)
        return int((next_hour - now).total_seconds())

    # ------------------------------------------------------------------ #
    # FrTimerSensor 순수 가상 함수 기본 구현
    # ------------------------------------------------------------------ #
    def receive_time_out(self, reason: int, extra_reason: object = None) -> None:
        """
        C++ ReceiveTimeOut() 대응.
        기본 구현은 로그만 출력.
        서브클래스에서 오버라이드하여 정시 변경 처리 로직을 구현한다.
        """
        logger.debug('FrHourChangeTimer.receive_time_out: hour changed (reason=%d)', reason)