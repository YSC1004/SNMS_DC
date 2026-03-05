# -*- coding: utf-8 -*-
"""
frSocketSensorTimer.h / frSocketSensorTimer.C  →  fr_socket_sensor_timer.py
Python 3.11.10 버전

변환 설계:
  frSocketSensorTimer → FrSocketSensorTimer  (FrTimerSensor 상속)

C++ → Python 주요 변환 포인트:
  frSocketSensor* m_SocketSensor → _socket_sensor : FrSocketSensor
  ReceiveTimeOut()               → receive_time_out()
    → m_SocketSensor->DataSendTime() → _socket_sensor.data_send_time()

변경 이력:
  v1 - 초기 변환
"""

from typing import TYPE_CHECKING

from fr_timer_sensor import FrTimerSensor

if TYPE_CHECKING:
    from fr_socket_sensor import FrSocketSensor


class FrSocketSensorTimer(FrTimerSensor):
    """
    C++ frSocketSensorTimer 대응 클래스.
    타이머 만료 시 FrSocketSensor.data_send_time() 을 호출하여
    쓰기 버퍼에 쌓인 데이터를 소켓으로 전송한다.
    """

    def __init__(self, sensor: 'FrSocketSensor') -> None:
        """C++ frSocketSensorTimer(frSocketSensor* Sensor) 대응."""
        super().__init__()
        self._socket_sensor: 'FrSocketSensor' = sensor

    # ------------------------------------------------------------------ #
    # FrTimerSensor 순수 가상 함수 구현
    # ------------------------------------------------------------------ #
    def receive_time_out(self, reason: int, extra_reason: object = None) -> None:
        """
        C++ ReceiveTimeOut() 대응.
        타이머 만료 시 소켓 센서의 data_send_time() 위임 호출.
        """
        self._socket_sensor.data_send_time()