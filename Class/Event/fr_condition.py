# -*- coding: utf-8 -*-
"""
frCondition.h / frCondition.C  →  fr_condition.py
Python 3.11.10 버전

변환 설계:
  frCondition      → FrCondition

C++ → Python 주요 변환 포인트:
  pthread_cond_t          → threading.Condition 내부 관리
  pthread_cond_init()     → threading.Condition(lock) 생성
  pthread_cond_destroy()  → Python GC 자동 처리
  pthread_cond_wait(cond, mutex)
                          → condition.wait()
                            (Condition 이 mutex 의 Lock 을 내포하여 관리)
  pthread_cond_signal()   → condition.notify()
  frMutex* Mutex          → FrMutex  (내부 _lock 을 Condition 에 전달)

설계 결정:
  C++ 에서 frCondition 은 pthread_cond_t 만 보유하고
  Wait() 호출 시 외부 frMutex 를 함께 넘기는 패턴이었다.
  Python threading.Condition 은 Lock 을 생성 시 고정하므로,
  Wait() 첫 호출 시 FrMutex._lock 으로 Condition 을 초기화한다.
  (이후 다른 FrMutex 로 Wait 호출 시 경고)

변경 이력:
  v1 - 초기 변환
"""

import logging
import threading
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fr_mutex import FrMutex

logger = logging.getLogger(__name__)


class FrCondition:
    """
    C++ frCondition / pthread_cond_t 대응 클래스.

    멤버 매핑:
      m_Cond → _cond : threading.Condition  (FrMutex._lock 내포)

    C++ 사용 패턴:
        frMutex lock;
        frCondition cond;

        // 대기 스레드
        lock.Lock();
        cond.Wait(&lock);
        lock.UnLock();

        // 신호 스레드
        cond.Signal();

    Python 대응:
        mutex = FrMutex()
        cond  = FrCondition()

        # 대기 스레드
        with mutex:
            cond.wait(mutex)

        # 신호 스레드
        cond.signal()
    """

    def __init__(self) -> None:
        """C++ frCondition() → pthread_cond_init() 대응."""
        # Condition 은 Wait() 첫 호출 시 FrMutex._lock 으로 초기화
        self._cond: Optional[threading.Condition] = None
        self._bound_lock: Optional[threading.Lock] = None

    # ------------------------------------------------------------------ #
    # Wait
    # ------------------------------------------------------------------ #
    def wait(self, mutex: 'FrMutex') -> bool:
        """
        C++ Wait(frMutex* Mutex) / pthread_cond_wait(&m_Cond, &mutex) 대응.

        mutex 는 이미 Lock 된 상태로 전달되어야 한다.
        Condition 이 처음 사용되는 경우 mutex._lock 으로 초기화.
        내부적으로 wait() 동안 mutex 를 해제하고, 깨어나면 재획득한다.
        """
        self._ensure_cond(mutex)

        if self._bound_lock is not mutex._lock:
            logger.warning('FrCondition.wait: called with different mutex')
            return False

        try:
            self._cond.wait()
            return True
        except RuntimeError as e:
            logger.error('FrCondition.wait error: %s', e)
            return False

    # ------------------------------------------------------------------ #
    # Signal
    # ------------------------------------------------------------------ #
    def signal(self) -> bool:
        """
        C++ Signal() / pthread_cond_signal() 대응.
        대기 중인 스레드 하나를 깨운다.
        Condition 이 초기화되지 않은 경우 False 반환.
        """
        if self._cond is None:
            logger.error('FrCondition.signal: condition not initialized')
            return False
        try:
            with self._cond:
                self._cond.notify()
            return True
        except RuntimeError as e:
            logger.error('FrCondition.signal error: %s', e)
            return False

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #
    def _ensure_cond(self, mutex: 'FrMutex') -> None:
        """Condition 지연 초기화 — 첫 Wait() 호출 시 FrMutex._lock 바인딩."""
        if self._cond is None:
            self._bound_lock = mutex._lock
            self._cond = threading.Condition(mutex._lock)