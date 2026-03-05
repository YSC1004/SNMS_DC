# -*- coding: utf-8 -*-
"""
frFilePollingTimer.h / frFilePollingTimer.C  →  fr_file_polling_timer.py
Python 3.11.10 버전

변환 설계:
  frFilePollingTimer → FrFilePollingTimer  (FrTimerSensor 상속)

C++ → Python 주요 변환 포인트:
  frFileFdSensor* m_frFileFdSensor → _file_fd_sensor : FrFileFdSensor
  ReceiveTimeOut()                 → receive_time_out()
  SensorPtr->Enable()              → _file_fd_sensor.enable()

변경 이력:
  v1 - 초기 변환
"""

import logging
from typing import TYPE_CHECKING

from fr_timer_sensor import FrTimerSensor

if TYPE_CHECKING:
    from fr_file_fd_sensor import FrFileFdSensor

logger = logging.getLogger(__name__)


class FrFilePollingTimer(FrTimerSensor):
    """
    C++ frFilePollingTimer 대응 클래스.
    폴링 주기마다 타이머가 만료되면 FrFileFdSensor 를 Enable 시킨다.
    Enable 된 센서는 FrInputEventSrc 를 통해 읽기 이벤트 감시를 재개하고
    subject_changed() → file_event_read() 경로로 파일 데이터를 처리한다.
    """

    def __init__(self, sensor_ptr: 'FrFileFdSensor') -> None:
        """C++ frFilePollingTimer(frFileFdSensor* SensorPtr) 대응."""
        super().__init__()
        self._file_fd_sensor: 'FrFileFdSensor' = sensor_ptr

    # ------------------------------------------------------------------ #
    # FrTimerSensor 순수 가상 함수 구현
    # ------------------------------------------------------------------ #
    def receive_time_out(self, reason: int, extra_reason: object = None) -> None:
        """
        C++ ReceiveTimeOut() 대응.
        타이머 만료 시 감시 대상 FrFileFdSensor 를 Enable.
        """
        self._file_fd_sensor.enable()