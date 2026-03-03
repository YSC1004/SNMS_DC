"""
ElaspedTime.h / ElaspedTime.C  →  elapsed_time.py

변환 매핑:
  ElaspedTime               → ElapsedTime  (오타 수정: Elasped → Elapsed)
  ftime(&m_STime)           → time.time()  (float, 밀리초 포함)
  GetElaspedSec()           → get_elapsed_sec()
  GetElaspedMiliSec()       → get_elapsed_ms()

C++ 원본 동작:
  - 생성자에서 Start/End 모두 현재 시각으로 초기화
  - Start() : 시작 시각 기록 (End 도 동시에 초기화)
  - End()   : 종료 시각 기록
  - GetElaspedMiliSec() : (ETime - STime) 밀리초 반환
  - GetElaspedSec()     : 밀리초 / 1000 (정수 나눗셈)

추가 기능:
  - context manager 지원 (with ElapsedTime() as et:)
  - __repr__ : 현재 경과 시간 출력
"""

import time
from typing import Optional


class ElapsedTime:
    """
    경과 시간 측정 유틸리티 (ElaspedTime 대응).
    ftime()/timeb → time.time() (float) 으로 대체.
    """

    def __init__(self):
        now          = time.time()
        self._s_time: float = now   # m_STime 대응
        self._e_time: float = now   # m_ETime 대응

    # ------------------------------------------------------------------ #
    # 측정 제어
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """측정 시작 (Start). 시작/종료 시각을 현재로 초기화."""
        now          = time.time()
        self._s_time = now
        self._e_time = now

    def end(self) -> None:
        """측정 종료 (End). 종료 시각을 현재로 기록."""
        self._e_time = time.time()

    # ------------------------------------------------------------------ #
    # 경과 시간 조회
    # ------------------------------------------------------------------ #

    def get_elapsed_ms(self) -> int:
        """
        경과 시간을 밀리초(int)로 반환 (GetElaspedMiliSec).

        C++ 원본:
          float sSec = ETime.time  - STime.time;    // 초 차이
          float mSec = ETime.millitm - STime.millitm; // 밀리초 차이
          return (int)(sSec*1000.0 + mSec);
        """
        elapsed = self._e_time - self._s_time   # 초 단위 float (밀리초 포함)
        return int(elapsed * 1000.0)

    def get_elapsed_sec(self) -> int:
        """
        경과 시간을 초(int)로 반환 (GetElaspedSec).
        C++ 원본: GetElaspedMiliSec() / 1000 (정수 나눗셈).
        """
        return self.get_elapsed_ms() // 1000

    def get_elapsed_sec_f(self) -> float:
        """경과 시간을 초(float)로 반환 (Python 추가)."""
        return self._e_time - self._s_time

    # ------------------------------------------------------------------ #
    # context manager 지원 (Python 추가)
    # ------------------------------------------------------------------ #

    def __enter__(self) -> "ElapsedTime":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.end()

    def __repr__(self) -> str:
        return (
            f"ElapsedTime("
            f"{self.get_elapsed_ms()} ms / "
            f"{self.get_elapsed_sec()} sec)"
        )