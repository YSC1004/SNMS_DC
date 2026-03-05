# -*- coding: utf-8 -*-
"""
frFdPipeSensor.h / frFdPipeSensor.C  →  fr_fd_pipe_sensor.py
Python 3.11.10 버전

변환 설계:
  frFdPipeSensor   → FrFdPipeSensor  (FrRdFdSensor 상속)

C++ → Python 주요 변환 포인트:
  frFdPipeSensor(frPipeSensor*, int FileDes) → __init__(pipe_sensor, fd)
  frRdFdSensor(FileDes) 위임 생성자          → super().__init__(fd=file_des)
  frPipeSensor* m_frPipeSensor               → _pipe_sensor : FrPipeSensor
  SubjectChanged()                           → subject_changed()
    → m_frPipeSensor->ReceiveMessage()       → _pipe_sensor.receive_message()

변경 이력:
  v1 - 초기 변환
"""

import logging
from typing import TYPE_CHECKING

from fr_rd_fd_sensor import FrRdFdSensor

if TYPE_CHECKING:
    from fr_pipe_sensor import FrPipeSensor

logger = logging.getLogger(__name__)


class FrFdPipeSensor(FrRdFdSensor):
    """
    C++ frFdPipeSensor 대응 클래스.
    os.pipe() 로 생성된 fd 하나를 FrRdFdSensor 로 래핑하고,
    읽기 이벤트 발생 시 부모 FrPipeSensor.receive_message() 를 호출한다.

    멤버 매핑:
      m_frPipeSensor → _pipe_sensor : FrPipeSensor
    """

    def __init__(self, pipe_sensor: 'FrPipeSensor', file_des: int) -> None:
        """
        C++ frFdPipeSensor(frPipeSensor* Sensor, int FileDes) 대응.
        frRdFdSensor(FileDes) 위임 생성자 → super().__init__(fd=file_des)
        """
        super().__init__(fd=file_des)
        self._pipe_sensor: 'FrPipeSensor' = pipe_sensor

    # ------------------------------------------------------------------ #
    # subject_changed
    # ------------------------------------------------------------------ #
    def subject_changed(self) -> int:
        """
        C++ SubjectChanged() 대응.
        읽기 fd 에 데이터가 도착하면 FrPipeSensor.receive_message() 위임.
        """
        self._pipe_sensor.receive_message()
        return 1