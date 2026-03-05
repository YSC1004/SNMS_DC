# -*- coding: utf-8 -*-
"""
frRdFdSensorTimer.h / frRdFdSensorTimer.C  →  fr_rd_fd_sensor_timer.py
Python 3.11.10 버전

변환 설계:
  frRdFdSensorTimer → FrRdFdSensorTimer  (FrTimerSensor 상속)

C++ → Python 주요 변환 포인트:
  frRdFdSensor* m_frRdFdSensor → _rd_fd_sensor : FrRdFdSensor
  ReceiveTimeOut()             → receive_time_out()
    → m_frRdFdSensor->ReceiveTimeOut(Reason, ExtraReason)
    → _rd_fd_sensor.receive_time_out(reason, extra_reason)

변경 이력:
  v1 - 초기 변환
"""

from typing import TYPE_CHECKING

from fr_timer_sensor import FrTimerSensor

if TYPE_CHECKING:
    from fr_rd_fd_sensor import FrRdFdSensor


class FrRdFdSensorTimer(FrTimerSensor):
    """
    C++ frRdFdSensorTimer 대응 클래스.
    타이머 만료 시 FrRdFdSensor.receive_time_out() 을 위임 호출한다.

    타이머 브리지 클래스 비교:
      FrRdFdSensorTimer   → FrRdFdSensor.receive_time_out()  (타임아웃 콜백)
      FrSocketSensorTimer → FrSocketSensor.data_send_time()  (송신 버퍼 플러시)
      FrFilePollingTimer  → FrFileFdSensor.enable()          (파일 폴링 재개)
    """

    def __init__(self, sensor: 'FrRdFdSensor') -> None:
        """C++ frRdFdSensorTimer(frRdFdSensor* Sensor) 대응."""
        super().__init__()
        self._rd_fd_sensor: 'FrRdFdSensor' = sensor

    # ------------------------------------------------------------------ #
    # FrTimerSensor 순수 가상 함수 구현
    # ------------------------------------------------------------------ #
    def receive_time_out(self, reason: int, extra_reason: object = None) -> None:
        """
        C++ ReceiveTimeOut() 대응.
        타이머 만료 시 FrRdFdSensor.receive_time_out() 위임 호출.
        """
        self._rd_fd_sensor.receive_time_out(reason, extra_reason)