import sys
import os
import threading

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# FrMutex 필요 (Wait 메서드 인자용)
from Class.Event.FrMutex import FrMutex

# -------------------------------------------------------
# FrCondition Class
# pthread_cond_wait/signal 기능을 Python threading.Condition으로 구현
# -------------------------------------------------------
class FrCondition:
    def __init__(self):
        """
        C++: frCondition() -> pthread_cond_init
        Python은 Condition 객체를 내부적으로 생성하여 관리
        """
        # 내부적으로 사용할 Condition 객체 (자체 RLock을 가짐)
        self.m_cond = threading.Condition()

    def __del__(self):
        """
        C++: ~frCondition() -> pthread_cond_destroy
        """
        pass

    def wait(self, mutex):
        """
        C++: bool Wait(frMutex* Mutex)
        
        [동작 원리]
        1. pthread_cond_wait는 호출 시 넘겨받은 Mutex를 Unlock 하고 대기 상태로 진입함.
        2. 신호(Signal)를 받으면 깨어나면서 다시 Mutex를 Lock 함.
        
        Python에서는 Condition 객체가 Lock을 내장하고 있거나 생성 시점에 받아야 하므로,
        실행 시점에 Mutex가 들어오는 C++ 구조를 맞추기 위해 아래와 같이 구현함.
        """
        if not mutex:
            return False

        try:
            # 1. 내부 Condition 락 획득 (Signal을 놓치지 않기 위해)
            self.m_cond.acquire()
            
            # 2. 외부 Mutex 해제 (C++ pthread_cond_wait의 동작 모사)
            # 호출자는 이미 이 mutex를 lock 한 상태여야 함
            mutex.unlock()
            
            # 3. 대기 (내부 Condition 락이 풀리고 대기 상태 진입)
            self.m_cond.wait()
            
            # 4. 깨어남 (내부 Condition 락 다시 획득됨)
            self.m_cond.release()
            
            # 5. 외부 Mutex 다시 획득 (C++ 동작 모사)
            mutex.lock()
            
            return True
        except Exception as e:
            print(f"[FrCondition] Wait Error: {e}")
            return False

    def signal(self):
        """
        C++: bool Signal() -> pthread_cond_signal
        대기 중인 스레드 하나를 깨움
        """
        try:
            with self.m_cond:
                self.m_cond.notify()
            return True
        except Exception as e:
            print(f"[FrCondition] Signal Error: {e}")
            return False

    def broadcast(self):
        """
        (참고) C++: pthread_cond_broadcast
        대기 중인 모든 스레드를 깨움
        """
        try:
            with self.m_cond:
                self.m_cond.notify_all()
            return True
        except Exception as e:
            return False