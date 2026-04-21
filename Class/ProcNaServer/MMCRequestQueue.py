"""
MMCRequestQueue.py
C++ MMCRequestQueue.h/.C + MMCRequestQueueTimer.h/.C → Python 변환

MMC 요청 큐 + 타이머 (두 클래스를 하나의 파일로 통합).
  - MMCRequestQueue: thread-safe deque + 흐름 제어
  - MMCRequestQueueTimer: AsWorld.SetTimer 기반 (별도 클래스 불필요)

C++ pthread_mutex → threading.Lock
C++ MMCRequestQueueTimer(frTimerSensor) → AsWorld.SetTimer 직접 사용
"""

import asyncio
import copy
import logging
import threading
from collections import deque
from typing import Optional, TYPE_CHECKING

from Common.CommTypeList import AS_MMC_REQUEST_T

if TYPE_CHECKING:
    from ProcNaServer.MMCRequestConnection import MMCRequestConnection

logger = logging.getLogger(__name__)

# C++: case 1019 (타이머 이유값)
QUEUE_CHECK_TIMEOUT_REASON = 1019


class MMCRequestQueue:
    """
    C++ MMCRequestQueue (frObject 상속) 대응.

    C++ frObject::SetTimer / ReceiveTimeOut
    → AsWorld.SetTimer 대신 threading.Timer 직접 사용
      (MMCRequestQueue는 AsWorld를 상속하지 않으므로)
    """

    def __init__(self, max_cmd_cnt: int,
                 req_conn: "MMCRequestConnection") -> None:
        self._max_cmd_cnt:           int                      = max_cmd_cnt
        self._status:                bool                     = True
        self._queue_empty:           bool                     = True   # C++: m_QueueEmpty (큐 수용 가능 여부)
        self._mmc_request_connection: Optional["MMCRequestConnection"] = req_conn

        self._req_list:   deque[AS_MMC_REQUEST_T] = deque()
        self._queue_lock: threading.Lock           = threading.Lock()  # C++: m_QueueLock
        self._status_lock: threading.Lock          = threading.Lock()  # C++: m_StatusLock

        self._queue_name:  str                     = ""
        self._timer:       Optional[threading.Timer] = None            # MMCRequestQueueTimer 대체

    def __del__(self) -> None:
        self._cancel_timer()

    # =========================================================================
    # InsertMMCRequest
    # =========================================================================

    def InsertMMCRequest(self, mmc_req: AS_MMC_REQUEST_T) -> bool:
        """
        C++: InsertMMCRequest(AS_MMC_REQUEST_T*)
        큐가 수용 가능 상태(_queue_empty=True)일 때만 삽입.
        최대 크기 초과 시 FlowControl Stop 전송 후 타이머 설정.
        """
        if not self._queue_empty:
            logger.debug("Command Not Receive Because of Queue is Full...")
            return False

        with self._queue_lock:
            if len(self._req_list) >= self._max_cmd_cnt:
                # 큐 초과 → FlowControl Stop
                logger.debug("Send Flow Control Stop... MaxSize(%d), QueueSize(%d)",
                             self._max_cmd_cnt, len(self._req_list))
                if self._mmc_request_connection:
                    asyncio.ensure_future(
                        self._mmc_request_connection.SendFlowControl(mmc_req.id))
                self._queue_empty = False
                self._set_timer()
                return False

            new_req = copy.copy(mmc_req)
            self._req_list.append(new_req)
            return True

    # =========================================================================
    # GetMMCRequest
    # =========================================================================

    def GetMMCRequest(self) -> Optional[AS_MMC_REQUEST_T]:
        """
        C++: GetMMCRequest() → deque 앞에서 꺼내 반환. 비어있으면 None.
        """
        with self._queue_lock:
            self.StatusLock()
            conn_name = (self._mmc_request_connection.GetSessionName()
                         if self._mmc_request_connection else "Disconnect Session")
            logger.debug("GetMMCRequest Before cnt(%s) : %d",
                         conn_name, len(self._req_list))
            self.StatusUnLock()

            if self._req_list:
                req = self._req_list.popleft()
            else:
                req = None

            self.StatusLock()
            logger.debug("GetMMCRequest After cnt(%s) : %d",
                         conn_name, len(self._req_list))
            self.StatusUnLock()

        return req

    # =========================================================================
    # SetStatus / GetStatus
    # =========================================================================

    def SetStatus(self, status: bool) -> None:
        """
        C++: SetStatus(bool Status)
        세션 종료 시 MMCRequestConnection 포인터 해제.
        """
        with self._status_lock:
            self._status = status
            self._mmc_request_connection = None

    def GetStatus(self) -> bool:
        """C++: GetStatus()"""
        return self._status

    # =========================================================================
    # StatusLock / StatusUnLock
    # =========================================================================

    def StatusLock(self) -> None:
        """C++: StatusLock() → pthread_mutex_lock(&m_StatusLock)"""
        self._status_lock.acquire()

    def StatusUnLock(self) -> None:
        """C++: StatusUnLock() → pthread_mutex_unlock(&m_StatusLock)"""
        self._status_lock.release()

    # =========================================================================
    # QueueName
    # =========================================================================

    def SetQueueName(self, name: str) -> None:
        self._queue_name = name

    def GetQueueName(self) -> str:
        return self._queue_name

    # =========================================================================
    # ReceiveTimeOut (타이머 콜백)
    # =========================================================================

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """
        C++: ReceiveTimeOut(int Reason, void* ExtraReason)
        MMCRequestQueueTimer → threading.Timer 콜백으로 직접 호출.
        reason=1019: 큐 크기 재확인 후 FlowControl Restart 또는 재타이머.
        """
        if reason == QUEUE_CHECK_TIMEOUT_REASON:
            self.StatusLock()
            conn_name = (self._mmc_request_connection.GetSessionName()
                         if self._mmc_request_connection else "Disconnect Session")
            self.StatusUnLock()
            logger.debug("Check MMCReqQueue size(%s)...", conn_name)

            with self._queue_lock:
                q_size = len(self._req_list)

            if q_size >= self._max_cmd_cnt:
                logger.debug("MaxSize(%d), QueueSize(%d)",
                             self._max_cmd_cnt, q_size)
                self._set_timer()
            else:
                logger.debug("Send Flow Control Restart...")
                with self._status_lock:
                    if self._status and self._mmc_request_connection:
                        asyncio.ensure_future(
                            self._mmc_request_connection.SendFlowControl())
                self._queue_empty = True
        else:
            logger.error("Unknown Time Out : %d", reason)

    # =========================================================================
    # 내부 타이머 헬퍼
    # =========================================================================

    def _set_timer(self) -> None:
        """
        C++: SetTimer() → MMCRequestQueueTimer::SetTimer(2, 1019)
        threading.Timer로 2초 후 ReceiveTimeOut(1019) 호출.
        """
        self._cancel_timer()
        self._timer = threading.Timer(
            2.0, self.ReceiveTimeOut, args=(QUEUE_CHECK_TIMEOUT_REASON,))
        self._timer.daemon = True
        self._timer.start()

    def _cancel_timer(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None