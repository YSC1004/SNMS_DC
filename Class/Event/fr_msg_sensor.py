# -*- coding: utf-8 -*-
"""
frMsgSensor.h / frMsgSensor.C  →  fr_msg_sensor.py
Python 3.11.10 버전

변환 설계:
  frMsgSensor      → FrMsgSensor  (FrSensor 상속)

C++ → Python 주요 변환 포인트:
  frSensor(WorldPtr) 위임 생성자  → super().__init__(world=world_ptr)
  frObject* m_Object              → _object : FrObject
  MakeSelectRequest / GetEvents   → 빈 구현 (메시지 센서는 fd 불필요)
  SendEvent(int, void*)           → send_event(message, addition_info)
    → m_WorldPtr->SendEvent(msg, this, info)
    → world_ptr.send_event(msg, self, info)
  RecvEvent(int, void*)           → recv_event(message, addition_info)
    → m_Object->RecvMessage(msg, info)
    → _object.recv_message(msg, info)

변경 이력:
  v1 - 초기 변환
"""

import logging
from typing import Optional, TYPE_CHECKING

from fr_sensor import FrSensor, SensorType

if TYPE_CHECKING:
    from fr_object import FrObject
    from fr_world  import FrWorld

logger = logging.getLogger(__name__)


class FrMsgSensor(FrSensor):
    """
    C++ frMsgSensor 대응 클래스.
    FrObject 간 메시지 전달을 위한 INPUT_SENSOR.

    FrWorldPipe 를 통해 메시지를 보내고(send_event),
    수신 시 recv_event() → FrObject.recv_message() 로 위임한다.

    멤버 매핑:
      m_Object → _object : FrObject
    """

    def __init__(self, obj: 'FrObject',
                 world_ptr: Optional['FrWorld'] = None) -> None:
        """
        C++ frMsgSensor(frObject* Obj, frWorld* WorldPtr) 대응.
        frSensor(WorldPtr) 위임 생성자 → super().__init__(world=world_ptr)
        """
        super().__init__(world=world_ptr)
        self.disable()
        self._sensor_type = SensorType.INPUT
        self._object: 'FrObject' = obj
        self.register_sensor()

    def __del__(self) -> None:
        self.unregister_sensor()

    # ------------------------------------------------------------------ #
    # FrSensor 추상 메서드 구현
    # ------------------------------------------------------------------ #
    def make_select_request(self) -> dict:
        """C++ MakeSelectRequest() 대응. 메시지 센서는 fd 불필요 → 빈 dict."""
        return {}

    def get_events(self) -> None:
        """C++ GetEvents() 대응. 메시지는 WorldPipe 경로로 처리 → pass."""
        pass

    # ------------------------------------------------------------------ #
    # 메시지 송신 / 수신
    # ------------------------------------------------------------------ #
    def send_event(self, message: int, addition_info: object = None) -> bool:
        """
        C++ SendEvent(int Message, void* AdditionInfo) 대응.
        world_ptr.send_event(message, self, addition_info) 로 위임.
        반환값 < 0 이면 False.
        """
        if self.world_ptr is None:
            logger.error('FrMsgSensor.send_event: world_ptr is None')
            return False

        ret = self.world_ptr.send_event(message, self, addition_info)
        return ret >= 0

    def recv_event(self, message: int, addition_info: object = None) -> None:
        """
        C++ RecvEvent(int Message, void* AdditionInfo) 대응.
        _object.recv_message() 로 위임.
        """
        if self._object is not None:
            self._object.recv_message(message, addition_info)
        else:
            logger.error('FrMsgSensor.recv_event: _object is None')