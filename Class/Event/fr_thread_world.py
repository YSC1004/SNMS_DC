# -*- coding: utf-8 -*-
"""
frThreadWorld.h / frThreadWorld.C  →  fr_thread_world.py
Python 3.11.10 버전

변환 설계:
  frThreadWorld    → FrThreadWorld  (FrWorld 상속)

C++ → Python 주요 변환 포인트:
  frWorld(FR_THREAD) 위임 생성자  → super().__init__(mode=FrWorld.Mode.FR_THREAD)
  frThread*                       → threading.Thread
  frMutex* m_ThreadStartLock      → threading.Lock
  frCondition* m_ThreadCond       → threading.Condition  (Lock 내포)
  frThread::Start(Start, this)    → Thread(target=_start, args=(self,))
  frThread::GetThreadId()         → thread.ident
  RegisterWorld(this, tid)        → FrWorld._register_world()
  m_ThreadCond->Wait(lock)        → condition.wait()
  m_ThreadCond->Signal()          → condition.notify()
  ptr->CreateWorldPipe()          → self._create_world_pipe()
  frThread::GetThreadSelfId()     → threading.get_ident()
  m_frThread->Join()              → thread.join()
  AppStart() 가상함수             → app_start() (기본 True 반환, 오버라이드 가능)

변경 이력:
  v1 - 초기 변환
"""

import logging
import threading
from typing import Optional

from fr_world import FrWorld

logger = logging.getLogger(__name__)


class FrThreadWorld(FrWorld):
    """
    C++ frThreadWorld 대응 클래스.
    별도 스레드에서 이벤트 루프를 실행하는 FrWorld 서브클래스.

    사용 예:
        class MyThreadWorld(FrThreadWorld):
            def app_start(self, argv):
                # 스레드 초기화 작업
                return True

        tw = MyThreadWorld()
        if tw.run():
            # 스레드 월드가 준비 완료된 상태
            ...
        tw.stop()
    """

    def __init__(self) -> None:
        """C++ frThreadWorld() : frWorld(FR_THREAD) 대응."""
        super().__init__(mode=FrWorld.Mode.FR_THREAD)
        self._thread:            Optional[threading.Thread] = None
        # C++ frMutex + frCondition 통합 → threading.Condition (내부 Lock 포함)
        self._start_condition:   threading.Condition        = threading.Condition()

    def __del__(self) -> None:
        self._thread = None

    # ------------------------------------------------------------------ #
    # Run  (스레드 시작 + 초기화 완료 대기)
    # ------------------------------------------------------------------ #
    def run(self) -> bool:
        """
        C++ Run() 대응.
        스레드를 시작하고 CreateWorldPipe + AppStart 완료까지 대기.
        AppStart() 가 False 를 반환하면 WaitFinish() 로 스레드 종료 대기 후 False 반환.
        """
        self._thread = threading.Thread(
            target=FrThreadWorld._start,
            args=(self,),
            daemon=True,
        )

        with self._start_condition:
            self._thread.start()
            # 스레드가 CreateWorldPipe + AppStart 완료 후 notify() 할 때까지 대기
            self._start_condition.wait()

        # _event_thread_id / RegisterWorld 는 _start() 내부에서 처리됨

        if not self._run_status:
            self.wait_finish()

        return self._run_status

    # ------------------------------------------------------------------ #
    # AppStart  (가상 함수 — 기본 구현)
    # ------------------------------------------------------------------ #
    def app_start(self, argv: list[str]) -> bool:
        """
        C++ AppStart() 가상함수 기본 구현.
        서브클래스에서 오버라이드하여 스레드 초기화 로직을 구현한다.
        """
        return True

    # ------------------------------------------------------------------ #
    # WaitFinish  (스레드 join)
    # ------------------------------------------------------------------ #
    def wait_finish(self) -> bool:
        """
        C++ WaitFinish() / frThread::Join() 대응.
        스레드 종료를 대기한다.
        """
        if self._thread is None:
            return True
        try:
            self._thread.join()
            logger.debug('wait_finish: success (world_id=%d)', self._world_id)
            return True
        except Exception as e:
            logger.error('wait_finish: fail (world_id=%d): %s', self._world_id, e)
            return False

    # ------------------------------------------------------------------ #
    # 스레드 엔트리 포인트  (C++ static Start(void* Arg) 대응)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _start(ptr: 'FrThreadWorld') -> None:
        """
        C++ static Start(void* Arg) 대응.
        스레드 내부 실행 흐름:
          1. CreateWorldPipe()
          2. 메인 스레드에 Signal (notify)
          3. AppStart()
          4. RunWorld() (AppStart 성공 시)
        """
        with ptr._start_condition:
            ptr._create_world_pipe()

            # 스레드 ID 갱신 및 월드 등록
            ptr._event_thread_id = threading.get_ident()
            ptr._tid             = threading.get_ident()
            FrWorld._register_world(ptr, ptr._event_thread_id)

            ptr._run_status = ptr.app_start(FrWorld.argv)

            # 메인 스레드 대기 해제
            ptr._start_condition.notify()

        if ptr._run_status:
            ptr.run_world()