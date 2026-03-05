# -*- coding: utf-8 -*-
"""
frPipeSensor.h / frPipeSensor.C  →  fr_pipe_sensor.py
Python 3.11.10 버전

변환 설계:
  frPipeSensor     → FrPipeSensor  (FrObject 상속)

C++ → Python 주요 변환 포인트:
  pipe(des)                    → os.pipe()  → (read_fd, write_fd)
  frFdPipeSensor* m_PipeSensor[2]
                               → _pipe_sensor : list[FrFdPipeSensor | None]  (크기 2)
  m_PipeSensor[0]              → _pipe_sensor[0]  읽기 fd
  m_PipeSensor[1]              → _pipe_sensor[1]  쓰기 fd  (Disable)
  Write(char*, int)            → write(packet: bytes) → int
  Read(char*, int)             → read(length: int) → bytes
  ReceiveMessage() 가상함수    → receive_message()  (오버라이드 가능)
  GetWorld()                   → get_world()

변경 이력:
  v1 - 초기 변환
"""

import logging
import os
from typing import Optional, TYPE_CHECKING

from fr_object import FrObject

if TYPE_CHECKING:
    from fr_fd_pipe_sensor import FrFdPipeSensor
    from fr_world          import FrWorld

logger = logging.getLogger(__name__)


class FrPipeSensor(FrObject):
    """
    C++ frPipeSensor 대응 클래스.
    os.pipe() 로 생성한 Unix 파이프를 FrFdPipeSensor 쌍으로 래핑한다.

      _pipe_sensor[0] : 읽기 fd  (InputEventSrc 에 등록, Enable)
      _pipe_sensor[1] : 쓰기 fd  (EventSrc 미등록, Disable)
    """

    def __init__(self) -> None:
        super().__init__()
        self._pipe_sensor: list[Optional['FrFdPipeSensor']] = [None, None]

    def __del__(self) -> None:
        self.close_pipe()

    # ------------------------------------------------------------------ #
    # 파이프 생성 / 닫기
    # ------------------------------------------------------------------ #
    def create_pipe(self) -> int:
        """
        C++ CreatePipe() 대응.
        os.pipe() 로 (read_fd, write_fd) 를 생성하고
        각각 FrFdPipeSensor 로 래핑한다.
        반환: 1 성공 / -1 실패
        """
        from fr_fd_pipe_sensor import FrFdPipeSensor

        # 기존 파이프 정리
        self._pipe_sensor[0] = None
        self._pipe_sensor[1] = None

        try:
            read_fd, write_fd = os.pipe()
        except OSError as e:
            logger.error('create_pipe error: %s', e)
            return -1

        self._pipe_sensor[0] = FrFdPipeSensor(self, read_fd)   # 읽기 파이프
        self._pipe_sensor[1] = FrFdPipeSensor(self, write_fd)  # 쓰기 파이프
        self._pipe_sensor[1].disable()   # 쓰기 fd 는 이벤트 감시 불필요
        return 1

    def close_pipe(self) -> None:
        """C++ ClosePipe() 대응."""
        self._pipe_sensor[0] = None
        self._pipe_sensor[1] = None

    # ------------------------------------------------------------------ #
    # 읽기 / 쓰기
    # ------------------------------------------------------------------ #
    def write(self, packet: bytes) -> int:
        """C++ Write(char* Packet, int Length) 대응. 쓰기 fd 를 통해 전송."""
        if self._pipe_sensor[1] is None:
            logger.error('write: pipe not created')
            return -1
        return self._pipe_sensor[1].write(packet)

    def read(self, length: int) -> bytes:
        """C++ Read(char* Packet, int Length) 대응. 읽기 fd 에서 수신."""
        if self._pipe_sensor[0] is None:
            logger.error('read: pipe not created')
            return b''
        return self._pipe_sensor[0].read(length)

    # ------------------------------------------------------------------ #
    # 가상 함수
    # ------------------------------------------------------------------ #
    def receive_message(self) -> int:
        """
        C++ ReceiveMessage() 가상함수 대응.
        FrFdPipeSensor 의 subject_changed() 에서 호출된다.
        서브클래스에서 오버라이드하여 파이프 메시지 처리 로직을 구현한다.
        """
        logger.debug('FrPipeSensor.receive_message: virtual (override me)')
        return 1

    # ------------------------------------------------------------------ #
    # 월드 참조
    # ------------------------------------------------------------------ #
    def get_world(self) -> Optional['FrWorld']:
        """C++ GetWorld() 대응. 읽기 센서가 속한 FrWorld 반환."""
        if self._pipe_sensor[0] is None:
            return None
        return self._pipe_sensor[0].world_ptr