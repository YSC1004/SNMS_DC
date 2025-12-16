import sys
import os
import threading

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# FrMutex Class
# Python threading.Lock을 래핑한 클래스
# -------------------------------------------------------
class FrMutex:
    def __init__(self):
        """
        C++: frMutex() -> pthread_mutex_init
        """
        self.m_mutex = threading.Lock()

    def __del__(self):
        """
        C++: ~frMutex() -> pthread_mutex_destroy
        Python은 GC가 처리하므로 명시적 파괴 불필요
        """
        pass

    def init(self):
        """
        C++: bool Init()
        Python에서는 __init__에서 생성되므로 항상 True 반환
        """
        return True

    def lock(self):
        """
        C++: void Lock()
        """
        self.m_mutex.acquire()

    def unlock(self):
        """
        C++: void UnLock()
        """
        self.m_mutex.release()

    # ---------------------------------------------------
    # Python Context Manager Support (with 구문 지원)
    # ---------------------------------------------------
    def __enter__(self):
        self.lock()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unlock()

# -------------------------------------------------------
# FrMutexGuard Class
# RAII 패턴 구현 (객체 생성 시 Lock, 소멸 시 Unlock)
# -------------------------------------------------------
class FrMutexGuard:
    def __init__(self, mutex):
        """
        C++: frMutexGuard(frMutex* mutex)
        생성자에서 락을 걺
        """
        self.m_mutex = mutex
        if self.m_mutex:
            self.m_mutex.lock()

    def __del__(self):
        """
        C++: ~frMutexGuard()
        소멸자에서 락을 해제
        주의: Python GC 시점은 불확실하므로, 가급적 'with' 구문 사용 권장
        """
        if self.m_mutex:
            # 이미 해제되었는지 확인은 어렵지만, 
            # threading.Lock은 해제된 상태에서 release 호출 시 RuntimeError 발생 가능성 있음.
            # 여기서는 안전장치 없이 호출 (로직상 맞춤)
            try:
                self.m_mutex.unlock()
            except RuntimeError:
                pass # 이미 해제된 경우 무시
            self.m_mutex = None

    # Context Manager 지원
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # with 블록을 빠져나갈 때 명시적으로 unlock 수행
        if self.m_mutex:
            self.m_mutex.unlock()
            self.m_mutex = None