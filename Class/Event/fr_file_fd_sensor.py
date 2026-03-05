# -*- coding: utf-8 -*-
"""
frFileFdSensor.h / frFileFdSensor.C  →  fr_file_fd_sensor.py
Python 3.11.10 버전

변환 설계:
  frFileFdSensor   → FrFileFdSensor  (FrRdFdSensor 상속, 추상 클래스)

C++ → Python 주요 변환 포인트:
  open(O_RDWR|O_CREAT, 0644)   → os.open() 동일 플래그
  lseek(fd, 0, SEEK_END)       → os.lseek()
  lseek(fd, -1, SEEK_CUR)      → os.lseek()
  read(fd, &m_TmpBuf, 1)       → os.read(fd, 1)
  frFilePollingTimer*           → FrFilePollingTimer (지연 임포트)
  SignalsBlock(SIGPIPE)         → signal.signal(SIGPIPE, SIG_IGN)
  FileEventRead() 순수 가상    → @abstractmethod file_event_read()
  char m_TmpBuf                → _tmp_buf : bytes (1바이트)

변경 이력:
  v1 - 초기 변환
"""

import logging
import os
import signal
from abc import abstractmethod
from typing import Optional, TYPE_CHECKING

from fr_rd_fd_sensor import FrRdFdSensor

if TYPE_CHECKING:
    from fr_file_polling_timer import FrFilePollingTimer

logger = logging.getLogger(__name__)


class FrFileFdSensor(FrRdFdSensor):
    """
    C++ frFileFdSensor 대응 추상 클래스.
    파일 fd 를 폴링 타이머로 주기적으로 감시하다가
    읽을 데이터가 있으면 file_event_read() 를 호출한다.

    멤버 매핑:
      m_PollingTime → _polling_time : int  (초, 기본값 1)
      m_Timer       → _timer        : FrFilePollingTimer | None
      m_TmpBuf      → _tmp_buf      : bytes  (1바이트 probe 용)

    사용 예:
        class MyFileSensor(FrFileFdSensor):
            def file_event_read(self):
                data = os.read(self.get_fd(), 4096)
                print('file data:', data)

        sensor = MyFileSensor()
        sensor.open_file('/tmp/watch.log')
    """

    def __init__(self) -> None:
        super().__init__()          # fd=-1, FR_NORMAL_SENSOR
        self.disable()

        # SIGPIPE 무시 (C++ SignalsBlock(SIGPIPE) 대응, POSIX 전용)
        try:
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        except (AttributeError, OSError):
            pass

        self._polling_time: int                          = 1
        self._timer:        Optional['FrFilePollingTimer'] = None
        self._tmp_buf:      bytes                        = b''

    def __del__(self) -> None:
        self._timer = None

    # ------------------------------------------------------------------ #
    # 파일 열기 / 닫기
    # ------------------------------------------------------------------ #
    def open_file(self, file_name: str) -> bool:
        """
        C++ OpenFile(string FileName) 대응.
        O_RDWR | O_CREAT (0644) 로 파일을 열고 끝으로 seek 한 뒤
        폴링 타이머를 시작한다.
        """
        if self._fd != -1:
            self.close()

        try:
            self._fd = os.open(
                file_name,
                os.O_RDWR | os.O_CREAT,
                0o644,
            )
        except OSError as e:
            self.set_obj_err_msg('%s', e)
            return False

        if not self.set_close_on_exec(True):
            return False

        os.lseek(self._fd, 0, os.SEEK_END)   # 파일 끝으로 이동

        from fr_file_polling_timer import FrFilePollingTimer
        self._timer = FrFilePollingTimer(self)
        self._timer.set_timer(self._polling_time, 100)

        return True

    def close(self) -> bool:
        """C++ Close() 대응. 타이머 해제 후 부모 close() 호출."""
        self._timer = None
        return super().close()

    # ------------------------------------------------------------------ #
    # subject_changed
    # ------------------------------------------------------------------ #
    def subject_changed(self) -> int:
        """
        C++ SubjectChanged() 대응.
        1바이트 probe read 로 데이터 유무를 확인:
          읽힘 → lseek(-1, SEEK_CUR) 로 되돌린 뒤 file_event_read() 호출
        이후 Disable → 다음 폴링 타이머 재설정.
        """
        try:
            self._tmp_buf = os.read(self._fd, 1)
        except OSError:
            self._tmp_buf = b''

        if len(self._tmp_buf) == 1:
            os.lseek(self._fd, -1, os.SEEK_CUR)   # 읽기 위치 되돌리기
            self.file_event_read()

        self.disable()
        if self._timer:
            self._timer.set_timer(self._polling_time, 100)

        return 1

    # ------------------------------------------------------------------ #
    # 폴링 시간 설정 / 조회
    # ------------------------------------------------------------------ #
    def set_polling_time(self, sec: int) -> None:
        """C++ SetPollingTime(int Sec) 대응."""
        self._polling_time = sec

    def get_polling_time(self) -> int:
        """C++ GetPollingTime() 대응."""
        return self._polling_time

    # ------------------------------------------------------------------ #
    # 순수 가상 함수
    # ------------------------------------------------------------------ #
    @abstractmethod
    def file_event_read(self) -> None:
        """
        C++ FileEventRead() 순수 가상함수 대응.
        파일에 읽을 데이터가 생겼을 때 호출된다.
        서브클래스에서 os.read(self.get_fd(), size) 로 데이터를 읽는다.
        """
        ...