# -*- coding: utf-8 -*-
"""
frSocket.h / frSocket.C  →  fr_socket.py
Python 3.11.10 버전

변환 설계:
  frSocket         → FrSocket  (FrSocketSensor 상속)

C++ → Python 주요 변환 포인트:
  frSocketSensor(FR_NO_SENSOR) 위임 생성자
    → FrSocketSensor.create_no_sensor() 팩토리 패턴 또는
       super().__init__(mode=SensorMode.FR_NO_SENSOR)

  frSocket 은 이벤트 루프 없이 동기 소켓 용도로 사용하는
  경량 래퍼 클래스 (FR_NO_SENSOR → 센서 등록 없음, Disable 상태).

변경 이력:
  v1 - 초기 변환
"""

from fr_sensor        import SensorMode
from fr_socket_sensor import FrSocketSensor


class FrSocket(FrSocketSensor):
    """
    C++ frSocket 대응 클래스.
    FR_NO_SENSOR 모드로 생성되어 이벤트 루프에 등록되지 않는
    동기 소켓 래퍼. frFtpSession 등에서 직접 사용.

    FR_NO_SENSOR 특성:
      - 전역 센서 목록에 등록되지 않음
      - FrInputEventSrc 에 등록되지 않음
      - is_enabled() == False (Disable 상태)
      - 소켓 생성/연결/읽기/쓰기는 FrSocketSensor 그대로 사용 가능
    """

    def __init__(self) -> None:
        """C++ frSocket() : frSocketSensor(FR_NO_SENSOR) 대응."""
        super().__init__(sensor_mode=SensorMode.FR_NO_SENSOR)