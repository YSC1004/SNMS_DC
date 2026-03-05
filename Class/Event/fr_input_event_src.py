# -*- coding: utf-8 -*-
"""
frInputEventSrc.h / frInputEventSrc.C  →  fr_input_event_src.py
Python 3.11.10 버전

변환 설계:
  frInputEventSrc  → FrInputEventSrc  (FrEventSrc 상속)

C++ → Python 주요 변환 포인트:
  MakeSelectRequest(fd_set*, ...) → make_select_request() : dict
  GetEvents(fd_set*, ...)         → get_events()
  m_SensorListitr 루프            → for sensor in self._sensor_list
  IsEnabled()                     → sensor.is_enabled()
  sensor->MakeSelectRequest(...)  → sensor.make_select_request()
  sensor->GetEvents(...)          → sensor.get_events()

변경 이력:
  v1 - 초기 변환
"""

import logging
from typing import TYPE_CHECKING

from fr_event_src import FrEventSrc

if TYPE_CHECKING:
    from fr_sensor import FrSensor

logger = logging.getLogger(__name__)


class FrInputEventSrc(FrEventSrc):
    """
    C++ frInputEventSrc 대응 클래스.

    등록된 센서들의 make_select_request() / get_events() 를
    순서대로 위임 호출한다. IsEnabled() == True 인 센서만 대상.

    fd_set 파라미터는 fr_event_src.py 설계에 따라 제거:
      make_select_request() → 각 센서의 결과를 병합한 dict 반환
      get_events()          → 각 센서의 get_events() 호출
    """

    def __init__(self) -> None:
        super().__init__()

    # ------------------------------------------------------------------ #
    # FrEventSrc 추상 메서드 구현
    # ------------------------------------------------------------------ #
    def make_select_request(self) -> dict:
        """
        C++ MakeSelectRequest(fd_set*, fd_set*, fd_set*, timeval*) 대응.
        활성화된 센서별 make_select_request() 결과를 병합해 반환.
        각 센서는 {'fd': ..., 'events': ..., 'timeout': ...} 형태의 dict 를 반환.
        """
        merged: dict = {}
        for sensor in self._sensor_list:
            if sensor.is_enabled():
                try:
                    req = sensor.make_select_request()
                    if req:
                        merged.update(req)
                except Exception as e:
                    logger.error('make_select_request sensor error: %s', e)
        return merged

    def get_events(self) -> None:
        """
        C++ GetEvents(fd_set*, fd_set*, fd_set*, timeval*) 대응.
        활성화된 센서별 get_events() 를 순서대로 호출.
        이벤트가 발생한 센서는 내부에서 insert_notify_sensor() 를 호출한다.
        """
        for sensor in self._sensor_list:
            if sensor.is_enabled():
                try:
                    sensor.get_events()
                except Exception as e:
                    logger.error('get_events sensor error: %s', e)