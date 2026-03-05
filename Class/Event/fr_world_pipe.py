# -*- coding: utf-8 -*-
"""
frWorldPipe.h / frWorldPipe.C  →  fr_world_pipe.py
Python 3.11.10 버전

변환 설계:
  frWorldPipe      → FrWorldPipe  (FrPipeSensor 상속)

C++ → Python 주요 변환 포인트:
  memset + Read((char*)&info, sizeof(frMessageInfo))
                               → pipe_sensor.read() 로 _MessageInfo 수신
                                 (fr_world.py 의 FrWorldPipe 는 queue 기반이므로
                                  여기서는 FrPipeSensor 기반 실제 파이프 구현)
  WORLD_THREAD_CLEAR           → MessageType.WORLD_THREAD_CLEAR
  DUMMY_FR_MESSAGE             → MessageType.DUMMY_FR_MESSAGE
  SENSOR_ADD                   → MessageType.SENSOR_ADD
  frThreadWorld* ptr           → FrThreadWorld (지연 임포트)
  ptr->WaitFinish() / delete   → thread_world.wait_finish()
  frSensor::m_SensorMgrLock    → FrSensor._sensor_mgr_lock
  frSensor::GetGlobalSensorList() → FrSensor.get_global_sensor_list()
  ((frMsgSensor*)sensor)->RecvEvent() → msg_sensor.recv_event()
  info.m_Sensor->m_WorldPtr    → sensor.world_ptr

변경 이력:
  v1 - 초기 변환
"""

import logging
import pickle
import struct
from typing import TYPE_CHECKING

from fr_pipe_sensor import FrPipeSensor
from fr_world       import MessageType

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# DUMMY_FR_MESSAGE — C++ 원본에 정의된 내부 메시지 상수
_DUMMY_FR_MESSAGE = -1


class FrWorldPipe(FrPipeSensor):
    """
    C++ frWorldPipe 대응 클래스.
    FrWorld 의 스레드 간 이벤트 파이프 수신 측.

    C++ 에서는 frMessageInfo 구조체를 raw bytes 로 파이프에 쓰고 읽었으나,
    Python 에서는 pickle 직렬화로 _MessageInfo 객체를 전송한다.

    ReceiveMessage() 처리 분기:
      WORLD_THREAD_CLEAR → FrThreadWorld 종료 대기 후 정리
      DUMMY_FR_MESSAGE   → 무시 (스레드 깨우기 용도)
      SENSOR_ADD         → sensor.register_sensor()
      그 외              → FrMsgSensor.recv_event()
    """

    # 패킷 헤더: 데이터 길이(4바이트 unsigned int)
    _HDR_FMT  = '!I'
    _HDR_SIZE = struct.calcsize(_HDR_FMT)

    def __init__(self) -> None:
        super().__init__()

    # ------------------------------------------------------------------ #
    # 파이프 쓰기 — _MessageInfo 직렬화
    # ------------------------------------------------------------------ #
    def write_message(self, info) -> int:
        """
        C++ frWorldPipe::Write((char*)&info, sizeof(frMessageInfo)) 대응.
        _MessageInfo 를 pickle 직렬화 후 길이-헤더와 함께 파이프에 기록.
        """
        try:
            payload = pickle.dumps(info)
            header  = struct.pack(self._HDR_FMT, len(payload))
            return self.write(header + payload)
        except Exception as e:
            logger.error('write_message error: %s', e)
            return -1

    # ------------------------------------------------------------------ #
    # ReceiveMessage 오버라이드
    # ------------------------------------------------------------------ #
    def receive_message(self) -> int:
        """
        C++ ReceiveMessage() 대응.
        파이프에서 _MessageInfo 를 읽어 메시지 종류에 따라 처리.
        """
        # 헤더 읽기 (길이)
        hdr_bytes = self.read(self._HDR_SIZE)
        if len(hdr_bytes) < self._HDR_SIZE:
            logger.error('receive_message: header read failed')
            return -1

        (payload_len,) = struct.unpack(self._HDR_FMT, hdr_bytes)

        # 페이로드 읽기
        payload = self.read(payload_len)
        if len(payload) < payload_len:
            logger.error('receive_message: payload read failed')
            return -1

        try:
            info = pickle.loads(payload)
        except Exception as e:
            logger.error('receive_message: deserialize error: %s', e)
            return -1

        return self._dispatch(info)

    # ------------------------------------------------------------------ #
    # 내부 디스패치
    # ------------------------------------------------------------------ #
    def _dispatch(self, info) -> int:
        """C++ ReceiveMessage() 분기 로직 대응."""

        # ── WORLD_THREAD_CLEAR ────────────────────────────────────────── #
        if info.message == MessageType.WORLD_THREAD_CLEAR:
            logger.error('WORLD_THREAD_CLEAR TRY')
            try:
                from fr_thread_world import FrThreadWorld
                ptr: FrThreadWorld = info.addition_info

                # 실행 중 여부와 무관하게 DUMMY 이벤트 전송 (C++ 원본 동일)
                ptr.send_event(_DUMMY_FR_MESSAGE, None, None)

                if ptr.wait_finish():
                    logger.error('WORLD_THREAD_CLEAR SUCCESS')
                    # C++ delete ptr → Python GC 위임 (참조 해제)
                    del ptr
                else:
                    logger.error('WORLD_THREAD_CLEAR FAIL')
            except Exception as e:
                logger.error('WORLD_THREAD_CLEAR error: %s', e)
            return 1

        # ── DUMMY_FR_MESSAGE — 무시 ───────────────────────────────────── #
        if info.message == _DUMMY_FR_MESSAGE:
            return 1

        # ── 일반 센서 메시지 ─────────────────────────────────────────── #
        from fr_sensor    import FrSensor
        from fr_msg_sensor import FrMsgSensor

        with FrSensor._sensor_mgr_lock:
            sensor_list = FrSensor.get_global_sensor_list()

            for sensor in sensor_list:
                if sensor is not info.sensor:
                    continue

                # 월드 일치 확인
                if sensor.world_ptr is not self.get_world():
                    logger.error('_dispatch: different event world')
                    return -1

                if info.message == MessageType.SENSOR_ADD:
                    sensor.register_sensor()

                else:
                    # frMsgSensor 로 캐스팅 후 RecvEvent 호출
                    if isinstance(sensor, FrMsgSensor):
                        sensor.recv_event(info.message, info.addition_info)
                    else:
                        logger.error('_dispatch: sensor is not FrMsgSensor')

                return 1

        # 센서를 찾지 못한 경우 (C++ 주석 처리된 에러와 동일하게 조용히 통과)
        return 1