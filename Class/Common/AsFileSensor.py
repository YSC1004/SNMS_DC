# -*- coding: utf-8 -*-
"""
AsFileSensor.h / AsFileSensor.C  →  AsFileSensor.py
Python 3.11.10 변환

변환 설계:
  AsFileSensor  → AsFileSensor  (FrFileFdSensor 상속)

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환 - FrFileFdSensor 상속, AdjustMsg() no-op 유지
"""

import logging
from abc import abstractmethod
from Event.fr_file_fd_sensor import FrFileFdSensor

logger = logging.getLogger(__name__)


class AsFileSensor(FrFileFdSensor):
    """
    C++ AsFileSensor 대응 클래스.

    FrFileFdSensor 의 경량 래퍼.
    AdjustMsg() 는 C++ 원본과 동일하게 no-op.
    """

    def __init__(self) -> None:
        """C++ AsFileSensor() 기본 생성자 대응."""
        super().__init__()

    def adjust_msg(self) -> None:
        """C++ AdjustMsg(){} 대응 — no-op."""
        pass

    @abstractmethod
    def file_event_read(self) -> None:
        """
        FrFileFdSensor.file_event_read() 추상 메서드 유지.
        AsFileSensor 를 상속하는 하위 클래스에서 구현.
        """
        ...