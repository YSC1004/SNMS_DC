"""
AsciiManagerType.py
C++ AsciiManagerType.h/.C → Python 변환

ProcNaManager 전역 데이터 구조 정의.
  - MmcPublishSet        : MMC 명령 + ConnectorId 묶음
  - MmcPublishSetQueue   : thread-safe MMC 발행 큐
  - MmcPublishSetQueueList : 우선순위별 큐 목록 (list[MmcPublishSetQueue])
"""

import threading
import logging
from collections import deque
from typing import Optional

from Common.CommTypeList import AS_MMC_PUBLISH_T

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# MmcPublishSet
# ─────────────────────────────────────────────────────────────────────────────

class MmcPublishSet:
    """
    C++: MmcPublishSet(AS_MMC_PUBLISH_T* MMCCom, string ConnectorId)
    MMC 명령과 전송 대상 ConnectorId를 묶는 데이터 클래스.
    """

    def __init__(self, mmc_publish: AS_MMC_PUBLISH_T,
                 connector_id: str) -> None:
        self.m_MmcPublish:  AS_MMC_PUBLISH_T = mmc_publish
        self.m_ConnectorId: str              = connector_id

    def __del__(self) -> None:
        # C++: delete m_MmcPublish → Python GC 처리
        self.m_MmcPublish = None


# ─────────────────────────────────────────────────────────────────────────────
# MmcPublishSetQueue
# ─────────────────────────────────────────────────────────────────────────────

class MmcPublishSetQueue:
    """
    C++: MmcPublishSetQueue : public list<MmcPublishSet*>
    thread-safe MmcPublishSet 큐.
    C++ pthread_mutex → threading.Lock
    C++ list<MmcPublishSet*> → collections.deque
    """

    def __init__(self, queue_number: int = 0) -> None:
        self.m_QueueNumber:        int            = queue_number
        self._lock:                threading.Lock = threading.Lock()
        self._queue: deque[MmcPublishSet]         = deque()

    def __del__(self) -> None:
        self._queue.clear()

    def GetMmcPublishSet(self) -> Optional[MmcPublishSet]:
        """
        C++: MmcPublishSet* GetMmcPublishSet()
        큐 앞에서 MmcPublishSet을 꺼내 반환. 비어있으면 None.
        C++: pthread_mutex_lock/unlock → threading.Lock (with 문)
        """
        with self._lock:
            if self._queue:
                return self._queue.popleft()    # C++: begin() → erase()
        return None

    def InsertMMCPublishSet(self, mmc_publish_set: MmcPublishSet) -> None:
        """
        C++: void InsertMMCPublishSet(MmcPublishSet* MMCPublishSet)
        큐 뒤에 MmcPublishSet 추가.
        """
        logger.debug("Queue(%d) Lock", self.m_QueueNumber)
        with self._lock:
            self._queue.append(mmc_publish_set)  # C++: push_back()
        logger.debug("Queue(%d) UnLock", self.m_QueueNumber)

    def __len__(self) -> int:
        return len(self._queue)


# ─────────────────────────────────────────────────────────────────────────────
# MmcPublishSetQueueList
# ─────────────────────────────────────────────────────────────────────────────

class MmcPublishSetQueueList(list):
    """
    C++: MmcPublishSetQueueList : public vector<MmcPublishSetQueue*>
    우선순위별 MmcPublishSetQueue 목록.
    AsciiManagerWorld.__init__ 에서 큐 2개를 생성하여 채운다.
    """
    pass