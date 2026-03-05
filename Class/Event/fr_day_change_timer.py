# -*- coding: utf-8 -*-
"""
frDayChangeTimer.h / frDayChangeTimer.C  →  fr_day_change_timer.py
Python 3.11.10 버전

변환 설계:
  frDayChangeTimer → FrDayChangeTimer  (FrTimerSensor 상속)

C++ → Python 주요 변환 포인트:
  frTime::GetRemainDaySec()  → remain_day_time()  (datetime 으로 계산)
  frTimerSensor::SetTimer()  → super().set_timer()
  ReceiveTimeOut() 순수 가상 → 서브클래스에서 오버라이드 (여기서는 기본 로그)

변경 이력:
  v1 - 초기 변환
"""

import datetime
import logging

from fr_timer_sensor import FrTimerSensor

logger = logging.getLogger(__name__)


class FrDayChangeTimer(FrTimerSensor):
    """
    C++ frDayChangeTimer 대응 클래스.
    자정(00:00:00)까지 남은 초를 계산하여 타이머를 설정한다.
    자정이 되면 ReceiveTimeOut() 이 호출된다.

    사용 예:
        class MyDayChangeTimer(FrDayChangeTimer):
            def receive_time_out(self, reason, extra_reason=None):
                print('자정 도달 — 일자 변경 처리')
                self.set_timer()   # 다음 자정까지 재설정

        timer = MyDayChangeTimer()
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
        자정까지 남은 초로 타이머 설정.
        reason=0 은 C++ 원본과 동일.
        """
        remain = self.remain_day_time()
        if remain < 1:
            remain = 1   # 최소 1초 보장 (frTimerSensor.set_timer 조건)
        super().set_timer(remain, 0)

    # ------------------------------------------------------------------ #
    # 자정까지 남은 시간 계산
    # ------------------------------------------------------------------ #
    @staticmethod
    def remain_day_time() -> int:
        """
        C++ RemainDayTime() / frTime::GetRemainDaySec() 대응.
        현재 시각 기준 오늘 자정(00:00:00)까지 남은 초(int) 반환.
        """
        now       = datetime.datetime.now()
        midnight  = (now + datetime.timedelta(days=1)).replace(
                        hour=0, minute=0, second=0, microsecond=0)
        return int((midnight - now).total_seconds())

    # ------------------------------------------------------------------ #
    # FrTimerSensor 순수 가상 함수 기본 구현
    # (서브클래스에서 오버라이드하여 실제 일자 변경 처리 로직 작성)
    # ------------------------------------------------------------------ #
    def receive_time_out(self, reason: int, extra_reason: object = None) -> None:
        """
        C++ ReceiveTimeOut() 대응.
        기본 구현은 로그만 출력.
        서브클래스에서 오버라이드하여 일자 변경 처리 로직을 구현한다.
        """
        logger.debug('FrDayChangeTimer.receive_time_out: day changed (reason=%d)', reason)