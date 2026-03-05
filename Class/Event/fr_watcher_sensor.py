# -*- coding: utf-8 -*-
"""
frWatcherSensor.h / frWatcherSensor.C  →  fr_watcher_sensor.py
Python 3.11.10 버전

변환 설계:
  frWatcherSensor  → FrWatcherSensor  (FrRdFdSensor 상속, 추상 클래스)

C++ → Python 주요 변환 포인트:
  frRdFdSensor(0) 위임 생성자    → super().__init__(fd=0)  (stdin = fd 0)
  char m_InputBuffer[1024]       → _input_buffer : str  (os.read 디코딩)
  memset + Read(buf, sizeof(buf)) → os.read(fd, 1024) → decode
  m_InputBuffer[strlen-1] = '\0' → rstrip('\n') 로 개행 제거
  Watch(char*) 순수 가상함수     → @abstractmethod watch(input_str: str)
  PrintHeader() / frSTD_OUT      → print(flush=True)
  SetHeader()                    → set_header()
  Disable() in __init__          → self.disable()

변경 이력:
  v1 - 초기 변환
"""

import os
import sys
from abc import abstractmethod

from fr_rd_fd_sensor import FrRdFdSensor


class FrWatcherSensor(FrRdFdSensor):
    """
    C++ frWatcherSensor 대응 추상 클래스.
    표준 입력(fd=0, stdin) 을 감시하다가 입력이 들어오면
    watch() 를 호출한다.

    멤버 매핑:
      m_Header      → _header       : str
      m_InputBuffer → _input_buffer : str  (매 읽기마다 갱신)

    사용 예:
        class MyCli(FrWatcherSensor):
            def watch(self, input_str: str) -> None:
                print(f'입력: {input_str}')

        sensor = MyCli(header='> ')
    """

    _BUF_SIZE = 1024

    def __init__(self, header: str = '') -> None:
        """
        C++ frWatcherSensor(string Header) : frRdFdSensor(0) 대응.
        fd=0 (stdin) 으로 초기화 후 헤더 출력, Disable.
        """
        super().__init__(fd=0)   # stdin
        self._header:       str = header
        self._input_buffer: str = ''
        self._print_header()
        self.disable()

    # ------------------------------------------------------------------ #
    # subject_changed
    # ------------------------------------------------------------------ #
    def subject_changed(self) -> int:
        """
        C++ SubjectChanged() 대응.
        stdin 에서 최대 1024바이트를 읽어 개행을 제거한 뒤 watch() 호출.
        """
        try:
            raw = os.read(self._fd, self._BUF_SIZE)
        except OSError:
            raw = b''

        # 디코딩 + 개행 제거 (C++ strlen-1 '\0' 대입 대응)
        self._input_buffer = raw.decode('utf-8', errors='replace').rstrip('\n\r')

        self.watch(self._input_buffer)
        self._print_header()
        return 1

    # ------------------------------------------------------------------ #
    # 헤더 설정 / 출력
    # ------------------------------------------------------------------ #
    def set_header(self, header: str) -> None:
        """C++ SetHeader() 대응."""
        self._header = header

    def _print_header(self) -> None:
        """C++ PrintHeader() / frSTD_OUT() 대응."""
        print(self._header, end='', flush=True)

    # ------------------------------------------------------------------ #
    # 순수 가상 함수
    # ------------------------------------------------------------------ #
    @abstractmethod
    def watch(self, input_str: str) -> None:
        """
        C++ Watch(char* InputStr) 순수 가상함수 대응.
        stdin 입력 한 줄이 들어올 때마다 호출된다.
        """
        ...