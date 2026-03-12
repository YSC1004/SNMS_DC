"""
[변경이력]
2014.07.08  초기 작성
Python 변환: AliveCheckTimer.h/.C → AliveCheckTimer.py

역할: AsSocket 의 Alive Check 주기 타이머
  - C++: frTimerSensor 상속 → asyncio.Task 기반 주기 루프
  - CheckMode == CMD_ALIVE_RECEIVE : 수신 측 — AsSocket.AliveCheckTime() 호출
  - CheckMode == CMD_ALIVE_SEND    : 송신 측 — AsSocket.AliveCheckSendTime() 호출
  - 생성 시 즉시 타이머 시작, 소멸/stop() 시 취소

※ AsSocket.py 의 _alive_check_loop / _alive_send_loop 와 동일 역할.
   AsSocket 내부에서 직접 asyncio.Task 로 처리하는 방식을 권장하나,
   C++ 원본처럼 별도 객체로 관리해야 하는 경우 이 클래스를 사용.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from Common.CommType import CMD_ALIVE_CHECK, CMD_ALIVE_RECEIVE, CMD_ALIVE_SEND

if TYPE_CHECKING:
    from Common.AsSocket import AsSocket

logger = logging.getLogger(__name__)


class AliveCheckTimer:
    """
    C++: class AliveCheckTimer : public frTimerSensor

    생성 즉시 주기 타이머를 시작한다.
    stop() 또는 GC 시 태스크가 취소된다.

    Args:
        interval_ms : 타이머 주기 (밀리초). C++ 원본의 Interval 단위와 동일.
        check_mode  : CMD_ALIVE_RECEIVE(수신 체크) 또는 CMD_ALIVE_SEND(송신 ACK)
        socket      : 타이머 만료 시 콜백 대상 AsSocket 인스턴스
    """

    def __init__(self, interval_ms: int, check_mode: int, socket: "AsSocket"):
        self._interval_ms:  int         = interval_ms
        self._check_mode:   int         = check_mode
        self._socket:       "AsSocket"  = socket
        self._task:         asyncio.Task | None = None

        # C++: frTimerSensor::SetTimer(m_CheckInterval, CMD_ALIVE_CHECK)
        self._start()

    def __del__(self):
        self.stop()

    # ──────────────────────────────────────────
    # 타이머 제어
    # ──────────────────────────────────────────

    def _start(self) -> None:
        """주기 루프 태스크 시작"""
        try:
            self._task = asyncio.create_task(self._loop())
        except RuntimeError:
            # 이벤트 루프가 없는 환경(테스트 등)에서는 수동 실행 필요
            logger.debug("AliveCheckTimer: no running event loop, task not started")

    def stop(self) -> None:
        """타이머 중지 (C++: ~AliveCheckTimer())"""
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None

    # ──────────────────────────────────────────
    # 타이머 루프
    # ──────────────────────────────────────────

    async def _loop(self) -> None:
        """
        C++: ReceiveTimeOut() + frTimerSensor::SetTimer() 재등록 패턴
        → asyncio 무한 루프로 대체
        """
        try:
            while True:
                await asyncio.sleep(self._interval_ms / 1000.0)
                self._receive_timeout(CMD_ALIVE_CHECK)
        except asyncio.CancelledError:
            pass

    def _receive_timeout(self, reason: int) -> None:
        """
        C++: ReceiveTimeOut(int Reason, void* ExtraReason)
        """
        if reason != CMD_ALIVE_CHECK:
            logger.error("AliveCheckTimer: Abnormal TimeOut Reason: %d", reason)
            return

        if self._check_mode == CMD_ALIVE_RECEIVE:
            # 수신 측: 응답 미수신 카운트 증가 → 한계 초과 시 AliveCheckFail
            self._socket.AliveCheckTime()

        elif self._check_mode == CMD_ALIVE_SEND:
            # 송신 측: 주기적으로 Alive ACK 패킷 전송
            # AliveCheckSendTime 은 async 이므로 태스크로 감쌈
            try:
                asyncio.create_task(self._socket.AliveCheckSendTime())
            except RuntimeError:
                logger.error("AliveCheckTimer: can't schedule AliveCheckSendTime")

        else:
            logger.error("AliveCheckTimer: Unknown CheckMode: %d", self._check_mode)