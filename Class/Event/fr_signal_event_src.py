# -*- coding: utf-8 -*-
"""
frSignalEventSrc.h / frSignalEventSrc.C  →  fr_signal_event_src.py
Python 3.11.10 버전

변환 설계:
  frSignalEventSrc → FrSignalEventSrc  (FrEventSrc 상속)

C++ → Python 주요 변환 포인트:
  sigaction / SA_RESTART        → signal.signal()  (Python 메인 스레드 전용)
  sigprocmask SIG_SETMASK/BLOCK → signal.pthread_sigmask()  (POSIX)
  sigfillset / sigemptyset      → signal.valid_signals() / set()
  sigaddset / sigdelset         → set.add() / set.discard()
  static frSignalEventSrc*      → 클래스 변수 _instance
  static sigset_t m_SigSet      → 클래스 변수 _sig_set : set[int]
  NSIG                          → signal.NSIG  (또는 valid_signals() 최대값)
  switch(SigNo) UseDefaultSignalHandler → signal.signal(sig, SIG_DFL)
  switch(SigNo) SignalToString  → signal.Signals(sig).name
  SignalsHold / SignalsRelease   → signals_hold() / signals_release()
  SignalsBlock / SignalsUnBlock  → signals_block() / signals_unblock()
  fd_set 파라미터               → 제거 (fr_event_src 설계 동일)

주의:
  Python signal.signal() 은 메인 스레드에서만 호출 가능.
  signal.pthread_sigmask() 는 POSIX(Linux/macOS) 전용.

변경 이력:
  v1 - 초기 변환
"""

import logging
import signal
import threading
from typing import ClassVar, Optional

from fr_event_src import FrEventSrc
from fr_sensor    import FrSensor

logger = logging.getLogger(__name__)

# Python 에서 처리 가능한 전체 유효 시그널 집합
_VALID_SIGNALS: frozenset[int] = signal.valid_signals()

# SIGKILL / SIGSTOP 은 핸들러 등록 불가 시그널 (sigaction 에서도 무시됨)
_UNCATCHABLE: frozenset[int] = frozenset(
    s for s in (
        getattr(signal, 'SIGKILL', None),
        getattr(signal, 'SIGSTOP', None),
    ) if s is not None
)


class FrSignalEventSrc(FrEventSrc):
    """
    C++ frSignalEventSrc 대응 클래스.
    프로세스 시그널을 FrSensor 이벤트로 변환한다.

    클래스(static) 변수:
      m_SignalEventSrc → _instance : FrSignalEventSrc | None
      m_SigSet         → _sig_set  : set[int]  (블록 중인 시그널 집합)
    """

    _instance: ClassVar[Optional['FrSignalEventSrc']] = None
    _sig_set:  ClassVar[set[int]]                     = set()

    # ------------------------------------------------------------------ #
    # 생성 / 소멸
    # ------------------------------------------------------------------ #
    def __init__(self) -> None:
        super().__init__()
        self._holding_signals: bool = False

        # 모든 유효 시그널을 기본 핸들러로 초기화
        for sig in _VALID_SIGNALS:
            self._use_default_signal_handler(sig)

        if FrSignalEventSrc._instance is None:
            FrSignalEventSrc._instance = self

        FrSignalEventSrc._sig_set.clear()   # sigemptyset(&m_SigSet)

    # ------------------------------------------------------------------ #
    # FrEventSrc 추상 메서드 구현
    # ------------------------------------------------------------------ #
    def make_select_request(self) -> dict:
        """C++ MakeSelectRequest() 대응. 시그널은 fd 불필요 → 빈 dict."""
        return {}

    def get_events(self) -> None:
        """C++ GetEvents() 대응. 시그널은 핸들러에서 직접 처리 → pass."""
        pass

    # ------------------------------------------------------------------ #
    # 센서 등록 / 해제
    # ------------------------------------------------------------------ #
    def register_sensor(self, sensor: FrSensor) -> int:
        """
        C++ RegisterSensor() 대응.
        시그널 번호 중복 확인 후 signal.signal() 로 핸들러 등록.
        """
        self.signals_hold()

        sig = sensor.get_signal_number()
        if sig < 1 or sig not in _VALID_SIGNALS:
            logger.debug('register_sensor: invalid signal number %d', sig)
            self.signals_release()
            return -1

        # 중복 등록 확인
        for s in self._sensor_list:
            if s.get_signal_number() == sig:
                logger.debug('register_sensor: already registered %s',
                             self.signal_to_string(sig))
                self.signals_release()
                return -1

        super().register_sensor(sensor)

        # sigaction(signal, SA_RESTART, handler) 대응
        if sig not in _UNCATCHABLE:
            try:
                signal.signal(sig, FrSignalEventSrc._signal_handler)
            except (OSError, ValueError) as e:
                logger.error('register_sensor signal.signal error: %s', e)

        logger.debug('register_sensor: %s', self.signal_to_string(sig))
        self.signals_release()
        return 1

    def unregister_sensor(self, sensor: FrSensor) -> int:
        """C++ UnRegisterSensor() 대응."""
        self.signals_hold()
        super().unregister_sensor(sensor)
        self._use_default_signal_handler(sensor.get_signal_number())
        self.signals_release()
        return 1

    # ------------------------------------------------------------------ #
    # 시그널 핸들러 (static)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _signal_handler(sig: int, frame) -> None:
        """
        C++ SignalHandler(int Signal) 대응.
        등록된 센서 중 해당 시그널 번호를 가진 활성 센서의
        subject_changed() 를 직접 호출.
        """
        inst = FrSignalEventSrc._instance
        if inst is None:
            return

        for sensor in inst._sensor_list:
            if sensor.get_signal_number() == sig and sensor.is_enabled():
                logger.debug('_signal_handler: %s',
                             FrSignalEventSrc.signal_to_string(sig))
                sensor.subject_changed()
                return

    # ------------------------------------------------------------------ #
    # 시그널 마스크 (static)
    # ------------------------------------------------------------------ #
    @staticmethod
    def signals_hold() -> int:
        """
        C++ SignalsHold() / sigprocmask(SIG_SETMASK, full) 대응.
        모든 블록 가능한 시그널을 마스킹.
        """
        try:
            blockable = _VALID_SIGNALS - _UNCATCHABLE
            signal.pthread_sigmask(signal.SIG_SETMASK, blockable)
        except (AttributeError, OSError) as e:
            logger.warning('signals_hold: %s', e)
        return 1

    @staticmethod
    def signals_release() -> int:
        """
        C++ SignalsRelease() / sigprocmask(SIG_UNBLOCK, full) + SIG_BLOCK(m_SigSet) 대응.
        전체 언블록 후 명시적 블록 집합(_sig_set) 재적용.
        """
        try:
            blockable = _VALID_SIGNALS - _UNCATCHABLE
            signal.pthread_sigmask(signal.SIG_UNBLOCK, blockable)
            if FrSignalEventSrc._sig_set:
                signal.pthread_sigmask(signal.SIG_BLOCK,
                                       FrSignalEventSrc._sig_set)
        except (AttributeError, OSError) as e:
            logger.warning('signals_release: %s', e)
        return 1

    @staticmethod
    def signals_block(sig_no: int) -> int:
        """C++ SignalsBlock(int SigNo) / sigaddset + SIG_BLOCK 대응."""
        FrSignalEventSrc._sig_set.add(sig_no)
        try:
            signal.pthread_sigmask(signal.SIG_BLOCK, {sig_no})
        except (AttributeError, OSError) as e:
            logger.warning('signals_block: %s', e)
        return 1

    @staticmethod
    def signals_unblock(sig_no: int) -> int:
        """C++ SignalsUnBlock(int SigNo) / sigdelset + SIG_UNBLOCK 대응."""
        FrSignalEventSrc._sig_set.discard(sig_no)
        try:
            signal.pthread_sigmask(signal.SIG_UNBLOCK, {sig_no})
        except (AttributeError, OSError) as e:
            logger.warning('signals_unblock: %s', e)
        return 1

    # ------------------------------------------------------------------ #
    # 유틸
    # ------------------------------------------------------------------ #
    @staticmethod
    def signal_to_string(sig_no: int) -> str:
        """
        C++ SignalToString() switch 문 대응.
        signal.Signals(sig).name 으로 모든 시그널 이름을 자동 반환.
        """
        try:
            return signal.Signals(sig_no).name
        except ValueError:
            return f'UNKNOWN_SIGNAL({sig_no})'

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #
    def _use_default_signal_handler(self, sig_no: int) -> int:
        """
        C++ UseDefaultSignalHandler() switch-sigaction(SIG_DFL) 대응.
        SIGKILL / SIGSTOP 등 변경 불가 시그널은 무시.
        """
        if sig_no in _UNCATCHABLE or sig_no not in _VALID_SIGNALS:
            return 1
        try:
            signal.signal(sig_no, signal.SIG_DFL)
        except (OSError, ValueError):
            pass   # 일부 시그널은 핸들러 변경 불가 → 조용히 무시
        return 1