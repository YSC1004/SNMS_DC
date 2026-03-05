# -*- coding: utf-8 -*-
"""
frMutex.h / frMutex.C  →  fr_mutex.py
Python 3.11.10 버전

변환 설계:
  frMutex          → FrMutex

C++ → Python 주요 변환 포인트:
  pthread_mutex_t        → threading.Lock
  pthread_mutex_init()   → threading.Lock() 생성
  pthread_mutex_destroy  → Python GC 자동 처리
  pthread_mutex_lock()   → lock.acquire()
  pthread_mutex_unlock() → lock.release()
  THREAD_ID m_TId        → tid : int  (threading.get_ident())
  friend class frCondition → FrCondition 이 _mutex 에 직접 접근 (지연 임포트)

변경 이력:
  v1 - 초기 변환
"""

import threading


class FrMutex:
    """
    C++ frMutex / pthread_mutex_t 대응 클래스.

    멤버 매핑:
      m_Mutex → _lock : threading.Lock
      m_TId   → tid   : int  (마지막 Lock 호출 스레드 ID, 참고용)

    Python 관용 사용법:
        mutex = FrMutex()

        # C++ 포팅 방식
        mutex.lock()
        ...
        mutex.unlock()

        # Python 권장 방식 (with 문)
        with mutex:
            ...
    """

    def __init__(self) -> None:
        """C++ frMutex() → Init() 대응."""
        self._lock: threading.Lock = threading.Lock()
        self.tid:   int            = 0

    # ------------------------------------------------------------------ #
    # Lock / UnLock
    # ------------------------------------------------------------------ #
    def lock(self) -> None:
        """C++ Lock() / pthread_mutex_lock() 대응."""
        self._lock.acquire()
        self.tid = threading.get_ident()

    def unlock(self) -> None:
        """C++ UnLock() / pthread_mutex_unlock() 대응."""
        self.tid = 0
        self._lock.release()

    def init(self) -> bool:
        """
        C++ Init() / pthread_mutex_init() 대응.
        Python 에서는 Lock 재생성으로 처리.
        이미 잠긴 상태에서 호출하면 False 반환.
        """
        if self._lock.locked():
            return False
        self._lock = threading.Lock()
        return True

    # ------------------------------------------------------------------ #
    # 컨텍스트 매니저 지원 (Python 관용 with 문)
    # ------------------------------------------------------------------ #
    def __enter__(self) -> 'FrMutex':
        self.lock()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.unlock()
        return False