# -*- coding: utf-8 -*-
"""
frMutexGuard.h / frMutexGuard.C  →  fr_mutex_guard.py
Python 3.11.10 버전

변환 설계:
  frMutexGuard     → FrMutexGuard  (컨텍스트 매니저)

C++ → Python 주요 변환 포인트:
  생성자에서 Lock()    → __enter__ 또는 __init__ 에서 acquire()
  소멸자에서 UnLock()  → __exit__ 에서 release()
  frMutex*             → threading.Lock | threading.RLock

  Python 에서는 with 문으로 직접 Lock 을 사용하는 것이 관용적이지만,
  C++ 코드 포팅 맥락에서 frMutexGuard 패턴을 유지할 경우를 위해
  컨텍스트 매니저 래퍼로 구현.

사용 예:
    lock = threading.Lock()

    # Python 관용 방식 (권장)
    with lock:
        ...

    # C++ frMutexGuard 포팅 방식 (기존 코드 구조 유지 시)
    with FrMutexGuard(lock):
        ...

변경 이력:
  v1 - 초기 변환
"""

import threading
from typing import Optional


class FrMutexGuard:
    """
    C++ frMutexGuard RAII 패턴 대응 컨텍스트 매니저.

    생성자에서 Lock 을 획득하고 소멸자(with 블록 종료)에서 해제한다.
    threading.Lock / threading.RLock 모두 지원.

    C++ 사용 패턴:
        {
            frMutexGuard guard(&someMutex);
            // 임계 구역
        }  // 소멸자에서 자동 UnLock

    Python 대응:
        with FrMutexGuard(some_lock):
            # 임계 구역
        # __exit__ 에서 자동 release
    """

    def __init__(self,
                 lock: Optional[threading.Lock | threading.RLock] = None) -> None:
        """
        C++ frMutexGuard(frMutex* MutexLock) 대응.
        lock 이 None 이면 아무 동작도 하지 않는다 (C++ null 체크 동일).
        """
        self._lock = lock
        if self._lock is not None:
            self._lock.acquire()

    def __del__(self) -> None:
        """C++ ~frMutexGuard() 소멸자 대응."""
        self._release()

    def __enter__(self) -> 'FrMutexGuard':
        """with 문 진입 — __init__ 에서 이미 acquire 했으므로 pass."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """with 블록 종료 시 자동 release."""
        self._release()
        return False   # 예외를 억제하지 않음

    def _release(self) -> None:
        """Lock 해제 (중복 해제 방지)."""
        if self._lock is not None:
            try:
                self._lock.release()
            except RuntimeError:
                pass   # 이미 해제된 경우 무시
            self._lock = None