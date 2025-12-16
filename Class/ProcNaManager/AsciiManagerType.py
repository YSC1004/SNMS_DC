import threading
from collections import deque

# -------------------------------------------------------
# MmcPublishSet Class
# -------------------------------------------------------
class MmcPublishSet:
    """
    MMC 명령과 해당 명령을 처리할 Connector ID를 묶어주는 데이터 클래스
    """
    def __init__(self, mmc_publish, connector_id):
        """
        :param mmc_publish: AsMmcPublishT 객체 (MMC 명령어 정보)
        :param connector_id: str (전송할 Connector 식별자)
        """
        self.m_MmcPublish = mmc_publish
        self.m_ConnectorId = connector_id

# -------------------------------------------------------
# MmcPublishSetQueue Class
# -------------------------------------------------------
class MmcPublishSetQueue:
    """
    MmcPublishSet 객체들을 저장하는 스레드 안전 큐 (Thread-Safe Queue)
    """
    def __init__(self, queue_number=0):
        """
        C++: MmcPublishSetQueue(int QueueNumber)
        """
        self.m_QueueNumber = queue_number
        self.m_MmcPublishSetLock = threading.Lock()
        
        # C++ std::list -> Python deque (Double-ended queue)
        # deque는 양쪽 끝에서의 추가/삭제가 O(1)로 효율적임
        self.m_Queue = deque()

    def __del__(self):
        """
        C++: ~MmcPublishSetQueue()
        """
        self.m_Queue.clear()

    def get_mmc_publish_set(self):
        """
        C++: MmcPublishSet* GetMmcPublishSet()
        큐의 맨 앞에서 데이터를 꺼내 반환 (Pop Front)
        """
        mmc_com_set = None
        
        # C++: pthread_mutex_lock
        with self.m_MmcPublishSetLock:
            if self.m_Queue:
                # C++: begin(), erase() -> pop_front()
                mmc_com_set = self.m_Queue.popleft()
                
        # C++: pthread_mutex_unlock (with 블록 종료 시 자동 처리)
        return mmc_com_set

    def insert_mmc_publish_set(self, mmc_publish_set):
        """
        C++: void InsertMMCPublishSet(MmcPublishSet* MMCPublishSet)
        큐의 맨 뒤에 데이터를 추가 (Push Back)
        """
        # 디버그 로그 (필요 시 주석 해제)
        # print(f"[MmcPublishSetQueue] Queue({self.m_QueueNumber}) Lock")
        
        with self.m_MmcPublishSetLock:
            self.m_Queue.append(mmc_publish_set)
            
        # print(f"[MmcPublishSetQueue] Queue({self.m_QueueNumber}) UnLock")