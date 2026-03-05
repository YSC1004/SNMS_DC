# -*- coding: utf-8 -*-
"""
frSignalSensor.h / frSignalSensor.C  →  fr_signal_sensor.py
Python 3.11.10 버전

변환 설계:
  frSignalSensor   → FrSignalSensor  (FrSensor 상속)

C++ → Python 주요 변환 포인트:
  frSignalSensor(int SigNo)          → __init__(sig_no: int)
  m_SensorType = SIGNAL_SENSOR       → self._sensor_type = SensorType.SIGNAL
  m_SignalNumber = SigNo             → self._signal_number = sig_no
  RegisterSensor() / UnRegSensor()   → register_sensor() / unregister_sensor()
  MakeSelectRequest / GetEvents      → 빈 구현 (시그널은 fd 불필요, C++ 원본 동일)
  SubjectChanged()                   → 서브클래스에서 오버라이드

변경 이력:
  v1 - 초기 변환
"""

import logging

from fr_sensor import FrSensor, SensorType

logger = logging.getLogger(__name__)


class FrSignalSensor(FrSensor):
    """
    C++ frSignalSensor 대응 클래스.
    특정 OS 시그널을 감시하는 SIGNAL_SENSOR.

    생성 시 sig_no 를 지정하면 FrSignalEventSrc 에 자동 등록되어
    해당 시그널 수신 시 subject_changed() 가 호출된다.

    사용 예:
        class SigTermSensor(FrSignalSensor):
            def subject_changed(self) -> int:
                print('SIGTERM received')
                self.world_ptr.exit(0)
                return 1

        sensor = SigTermSensor(signal.SIGTERM)
    """

    def __init__(self, sig_no: int) -> None:
        """C++ frSignalSensor(int SigNo) 대응."""
        super().__init__()
        self._sensor_type   = SensorType.SIGNAL
        self._signal_number = sig_no
        self.register_sensor()

    def __del__(self) -> None:
        self.unregister_sensor()

    # ------------------------------------------------------------------ #
    # FrSensor 추상 메서드 구현
    # ------------------------------------------------------------------ #
    def make_select_request(self) -> dict:
        """
        C++ MakeSelectRequest() 대응.
        시그널은 fd 감시가 필요 없으므로 빈 dict 반환 (C++ 원본도 return 1).
        """
        return {}

    def get_events(self) -> None:
        """
        C++ GetEvents() 대응.
        시그널 이벤트는 FrSignalEventSrc._signal_handler() 에서 직접 처리
        → 여기서는 아무 동작 없음 (C++ 원본도 return 1).
        """
        pass