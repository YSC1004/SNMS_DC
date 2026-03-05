# -*- coding: utf-8 -*-
"""
frThread.h / frThread.C  →  fr_thread.py
Python 3.11.10 버전

변환 설계:
  frThread         → FrThread

C++ → Python 주요 변환 포인트:
  pthread_create   → threading.Thread
  pthread_cancel   → _thread.cancel() 대응 없음 → stop 플래그 + join()
  pthread_join     → thread.join()
  pthread_detach   → thread.daemon = True
  pthread_self     → threading.get_ident()
  THREAD_ID        → int  (threading.get_ident() 반환값)
  T_STATUS enum    → FrThread.Status(IntEnum)
  void*(*FuncPtr)(void*), void* Arg
                   → Callable + args tuple → threading.Thread(target, args)

변경 이력:
  v1 - 초기 변환
"""

import logging
import threading
from enum import IntEnum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class FrThread:
    """
    C++ frThread 대응 클래스.
    pthread 래퍼를 threading.Thread 로 대체.

    멤버 매핑:
      m_Id             → _thread       : threading.Thread | None
                         _id           : int (ident, 시작 후 갱신)
      m_RunningStatus  → _status       : FrThread.Status
      m_FuncPtr        → _func_ptr     : Callable | None
      m_Arg            → _arg          : Any

    주의:
      pthread_cancel 은 Python 에 직접 대응이 없다.
      Terminite() 는 threading 레벨에서 스레드 강제 종료가 불가능하므로
      _stop_event 를 set 하고 join() 으로 종료를 유도한다.
      (스레드 함수가 _stop_event 를 확인하지 않으면 즉시 종료되지 않음)
    """

    class Status(IntEnum):
        T_START   = 0
        T_SUSPEND = 1
        T_STOP    = 2

    def __init__(self) -> None:
        self._thread:  Optional[threading.Thread] = None
        self._id:      int                        = 0
        self._status:  FrThread.Status            = FrThread.Status.T_STOP
        self._func_ptr: Optional[Callable]        = None
        self._arg:     Any                        = None
        self._stop_event: threading.Event         = threading.Event()

    # ------------------------------------------------------------------ #
    # Start
    # ------------------------------------------------------------------ #
    def start(self, func_ptr: Callable, arg: Any = None) -> bool:
        """
        C++ Start(void*(*FuncPtr)(void*), void* Arg) 대응.
        func_ptr 과 arg 를 저장 후 스레드 시작.
        """
        self._func_ptr = func_ptr
        self._arg      = arg
        return self._start()

    def _start(self) -> bool:
        """C++ private Start() 대응."""
        if self._func_ptr is None:
            logger.error('FrThread: func_ptr is not set')
            return False

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._func_ptr,
            args=(self._arg,),
        )
        try:
            self._thread.start()
            self._id     = self._thread.ident or 0
            self._status = FrThread.Status.T_START
            return True
        except RuntimeError as e:
            logger.error('FrThread._start error: %s', e)
            return False

    # ------------------------------------------------------------------ #
    # Stop / Terminite
    # ------------------------------------------------------------------ #
    def stop(self) -> None:
        """C++ Stop() 대응. 상태만 T_STOP 으로 변경."""
        self._status = FrThread.Status.T_STOP

    def terminite(self) -> bool:
        """
        C++ Terminite() / pthread_cancel() 대응.
        Python 은 스레드 강제 종료 불가 → stop_event set + join() 으로 유도.
        스레드 함수가 stop_event 를 확인하지 않으면 즉시 종료되지 않는다.
        """
        if self._thread is None:
            return True

        self._stop_event.set()
        self._status = FrThread.Status.T_STOP
        self._id     = 0
        return True

    # ------------------------------------------------------------------ #
    # Join / Detach
    # ------------------------------------------------------------------ #
    def join(self) -> bool:
        """C++ Join() / pthread_join() 대응."""
        if self._thread is None or not self._thread.is_alive():
            return False
        try:
            self._thread.join()
            self._status = FrThread.Status.T_STOP
            return True
        except RuntimeError as e:
            logger.error('FrThread.join error: %s', e)
            return False

    def detach(self) -> None:
        """
        C++ Detach() / pthread_detach() 대응.
        daemon=True 로 설정 — 메인 스레드 종료 시 자동 종료.
        스레드 시작 전에 설정해야 하므로, 시작 전이면 설정하고
        이미 시작됐으면 경고 로그만 출력.
        """
        if self._thread is None:
            return
        if not self._thread.is_alive():
            self._thread.daemon = True
        else:
            logger.warning('FrThread.detach: cannot set daemon after start')

    # ------------------------------------------------------------------ #
    # 상태 / ID 조회
    # ------------------------------------------------------------------ #
    def get_status(self) -> 'FrThread.Status':
        """C++ GetStatus() 대응."""
        return self._status

    def get_thread_id(self) -> int:
        """C++ GetThreadId() 대응."""
        return self._id

    def get_stop_event(self) -> threading.Event:
        """Terminite() 에서 set 되는 stop 이벤트 — 스레드 함수에서 참조 가능."""
        return self._stop_event

    @staticmethod
    def get_thread_self_id() -> int:
        """C++ GetThreadSelfId() / pthread_self() 대응."""
        return threading.get_ident()