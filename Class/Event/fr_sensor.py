# -*- coding: utf-8 -*-
"""
frRdFdSensor.h / frRdFdSensor.C  →  fr_rd_fd_sensor.py
Python 3.11.10 버전

변환 설계:
  frRdFdSensor     → FrRdFdSensor  (FrSensor 상속)

C++ → Python 주요 변환 포인트:
  fd_set FD_SET / FD_ISSET       → selectors.DefaultSelector 등록/이벤트 확인
  fcntl F_GETFL/F_SETFL O_NONBLOCK → os.set_blocking()  (Python 3.5+)
  fcntl F_GETFD/F_SETFD FD_CLOEXEC → fcntl.FD_CLOEXEC (POSIX 전용)
  write(m_FD, ...) / read(m_FD)  → os.write() / os.read()
  close(m_FD)                    → os.close()
  frRdFdSensor()                 → __init__(fd=-1)
  frRdFdSensor(int FileDes)      → __init__(fd=FileDes)
  frRdFdSensor(FR_SENSOR_MODE)   → classmethod create_no_sensor()  (FrSensor 상속)
  SetTimer / SetTimer2           → set_timer() / set_timer2()
  CancelTimer / CancelAllTimer   → cancel_timer() / cancel_all_timer()
  KillTimer                      → kill_timer()
  ReceiveTimeOut                 → receive_time_out()  (가상, 오버라이드 가능)
  SetFD / GetFD                  → set_fd() / get_fd()
  SetBlockMode / SetCloseOnExec  → set_block_mode() / set_close_on_exec()
  IsBlockMode                    → is_block_mode()

변경 이력:
  v1 - 초기 변환
"""

import fcntl
import logging
import os
import selectors
from typing import Optional, TYPE_CHECKING

from fr_sensor import FrSensor, SensorMode, SensorType

if TYPE_CHECKING:
    from fr_rd_fd_sensor_timer import FrRdFdSensorTimer

logger = logging.getLogger(__name__)


class FrRdFdSensor(FrSensor):
    """
    C++ frRdFdSensor 대응 클래스.
    파일 디스크립터(fd) 읽기 이벤트를 감시하는 INPUT_SENSOR.

    멤버 매핑:
      m_FD                → _fd                  : int  (-1 = 미설정)
      m_FcntlFlag         → _fcntl_flag           : int
      m_BlockMode         → _block_mode           : bool
      m_frRdFdSensorTimer → _rd_fd_sensor_timer   : FrRdFdSensorTimer | None

    fd_set 대체:
      MakeSelectRequest → selectors 에 fd 를 EVENT_READ 로 등록
      GetEvents         → selectors.select(timeout=0) 결과로 이벤트 확인
      FrWorld._read_event() 가 selector 를 직접 구동하므로,
      여기서는 selector 에 등록/해제만 담당한다.
    """

    def __init__(self, fd: int = -1) -> None:
        """
        C++ frRdFdSensor() / frRdFdSensor(int FileDes) 통합.
        fd=-1 이면 fd 미설정 상태로 초기화 (나중에 set_fd() 로 지정).
        """
        super().__init__()                      # FR_NORMAL_SENSOR, world 자동 탐색
        self._sensor_type = SensorType.INPUT

        self._fd:          int  = fd
        self._fcntl_flag:  int  = 0
        self._block_mode:  bool = True
        self._rd_fd_sensor_timer: Optional['FrRdFdSensorTimer'] = None

        # fd 가 유효하면 FD_CLOEXEC 설정 (C++ 생성자 동일)
        if self._fd > 0:
            self.set_close_on_exec(True)

        self.register_sensor()

    def __del__(self) -> None:
        if self._fd != -1:
            self.close()
        self._rd_fd_sensor_timer = None
        self.unregister_sensor()

    # ------------------------------------------------------------------ #
    # FrSensor 추상 메서드 구현
    # ------------------------------------------------------------------ #
    def make_select_request(self) -> dict:
        """
        C++ MakeSelectRequest() / FD_SET(m_FD, Rd) 대응.
        world 의 selector 에 fd 를 EVENT_READ 로 등록.
        이미 등록된 경우 중복 등록하지 않는다.
        """
        if self._fd == -1 or not self.world_ptr:
            return {}

        sel: selectors.DefaultSelector = self.world_ptr._selector
        try:
            # 이미 등록 여부 확인
            key = sel.get_key(self._fd)
            # 이미 등록돼 있으면 갱신 없이 통과
        except KeyError:
            sel.register(self._fd, selectors.EVENT_READ, data=self._on_read_ready)

        return {}   # fr_event_src 설계상 dict 반환 (내용은 selector 에 직접 등록)

    def get_events(self) -> None:
        """
        C++ GetEvents() / FD_ISSET(m_FD, Rd) 대응.
        selector 에서 이 fd 에 읽기 이벤트가 발생했는지 확인하고
        InsertNotifySensor() 로 디스패치 큐에 삽입.

        FrWorld._read_event() 가 selector.select()를 구동하면
        _on_read_ready() 콜백이 직접 호출되므로
        여기서는 추가 폴링 없이 pass 처리.
        """
        pass

    def _on_read_ready(self, fd: int, events: int) -> None:
        """
        selector 콜백 — FD_ISSET 후 InsertNotifySensor() 대응.
        FrWorld._read_event() 에서 호출된다.
        """
        if self.world_ptr and self.world_ptr.input_event_src:
            self.world_ptr.input_event_src.insert_notify_sensor(self)

    # ------------------------------------------------------------------ #
    # 읽기 / 쓰기 / 닫기
    # ------------------------------------------------------------------ #
    def write(self, packet: bytes) -> int:
        """C++ Write(char* Packet, int Length) 대응."""
        try:
            return os.write(self._fd, packet)
        except OSError as e:
            self.set_obj_err_msg('write error: %s', e)
            return -1

    def read(self, length: int) -> bytes:
        """C++ Read(char* Packet, int Length) 대응."""
        try:
            return os.read(self._fd, length)
        except OSError as e:
            self.set_obj_err_msg('read error: %s', e)
            return b''

    def close(self) -> bool:
        """C++ Close() 대응."""
        if self._fd == -1:
            return True

        # selector 에서 먼저 해제
        if self.world_ptr:
            try:
                self.world_ptr._selector.unregister(self._fd)
            except Exception:
                pass

        try:
            os.close(self._fd)
        except OSError as e:
            self.set_obj_err_msg('close error: %s', e)
            self._fd = -1
            return False

        self._fd = -1
        self.disable()
        return True

    # ------------------------------------------------------------------ #
    # fd 플래그 설정
    # ------------------------------------------------------------------ #
    def set_block_mode(self, mode: bool = True) -> bool:
        """
        C++ SetBlockMode() / fcntl O_NONBLOCK 대응.
        os.set_blocking() (Python 3.5+) 으로 대체.
        mode=True  → blocking
        mode=False → non-blocking
        """
        if self._fd == -1:
            self.set_obj_err_msg('FD(-1) is invalid')
            return False
        try:
            os.set_blocking(self._fd, mode)
            self._block_mode = mode
            return True
        except OSError as e:
            self.set_obj_err_msg('Fail to block mode change: %s', e)
            return False

    def set_close_on_exec(self, mode: bool = True) -> bool:
        """
        C++ SetCloseOnExec() / fcntl FD_CLOEXEC 대응.
        POSIX 전용 (Linux / macOS).
        """
        try:
            flag = fcntl.fcntl(self._fd, fcntl.F_GETFD)
            if mode:
                flag |= fcntl.FD_CLOEXEC
            else:
                flag &= ~fcntl.FD_CLOEXEC
            fcntl.fcntl(self._fd, fcntl.F_SETFD, flag)
            return True
        except OSError as e:
            self.set_obj_err_msg('set_close_on_exec error: %s', e)
            return False

    def is_block_mode(self) -> bool:
        """C++ IsBlockMode() 대응."""
        return self._block_mode

    # ------------------------------------------------------------------ #
    # fd 접근자
    # ------------------------------------------------------------------ #
    def set_fd(self, new_fd: int) -> None:
        """C++ SetFD() 대응."""
        self._fd = new_fd

    def get_fd(self) -> int:
        """C++ GetFD() 대응."""
        return self._fd

    # ------------------------------------------------------------------ #
    # 타이머
    # ------------------------------------------------------------------ #
    def _ensure_timer(self) -> 'FrRdFdSensorTimer':
        """타이머 인스턴스 지연 생성 (공통 헬퍼)."""
        if self._rd_fd_sensor_timer is None:
            from fr_rd_fd_sensor_timer import FrRdFdSensorTimer
            self._rd_fd_sensor_timer = FrRdFdSensorTimer(self)
            self._rd_fd_sensor_timer.set_parent_sensor(self)
        return self._rd_fd_sensor_timer

    def set_timer(self, interval: int, reason: int,
                  extra_reason: object = None) -> int:
        """C++ SetTimer(int Interval, int Reason, void*) 대응. 단위: 초."""
        return self._ensure_timer().set_timer(interval, reason, extra_reason)

    def set_timer2(self, milli_sec: int, reason: int,
                   extra_reason: object = None) -> int:
        """C++ SetTimer2(int MiliSec, int Reason, void*) 대응. 단위: 밀리초."""
        return self._ensure_timer().set_timer2(milli_sec, reason, extra_reason)

    def cancel_timer(self, key: int) -> bool:
        """C++ CancelTimer(int Key) 대응."""
        if not self._rd_fd_sensor_timer:
            return False
        return self._rd_fd_sensor_timer.cancel_timer(key)

    def cancel_all_timer(self) -> None:
        """C++ CancelAllTimer() 대응."""
        if self._rd_fd_sensor_timer:
            self._rd_fd_sensor_timer.cancel_all_timer()

    def kill_timer(self) -> None:
        """C++ KillTimer() 대응. 타이머 인스턴스 완전 제거."""
        self._rd_fd_sensor_timer = None

    def receive_time_out(self, reason: int, extra_reason: object = None) -> None:
        """C++ ReceiveTimeOut() 가상함수 대응. 서브클래스에서 오버라이드."""
        logger.debug('FrRdFdSensor.receive_time_out: virtual (override me)')