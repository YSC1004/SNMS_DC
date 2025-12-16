import sys
import os
import threading
import time

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# FrThread Class
# POSIX pthread 기능을 Python threading 모듈로 래핑
# -------------------------------------------------------
class FrThread:
    # Status Constants
    T_STOP = 0
    T_START = 1

    def __init__(self):
        """
        C++: frThread()
        """
        self.m_Id = 0
        self.m_RunningStatus = self.T_STOP
        self.m_FuncPtr = None # 실행할 함수
        self.m_Arg = None     # 함수 파라미터
        self.m_thread = None  # Python threading.Thread 객체

    def __del__(self):
        """
        C++: ~frThread()
        """
        pass

    def start(self, func_ptr=None, arg=None):
        """
        C++: bool Start(void*(*FuncPtr)(void *), void* Arg)
        C++: bool Start()
        """
        if func_ptr:
            self.m_FuncPtr = func_ptr
            self.m_Arg = arg

        if self.m_FuncPtr is None:
            print("[FrThread] Error: Function pointer is not set")
            return False

        try:
            # 스레드 생성
            # args는 튜플이어야 하므로 (arg,) 형태로 전달
            # arg가 None이면 인자 없이 호출하도록 분기 처리
            if self.m_Arg is not None:
                self.m_thread = threading.Thread(target=self.m_FuncPtr, args=(self.m_Arg,))
            else:
                self.m_thread = threading.Thread(target=self.m_FuncPtr)
            
            self.m_thread.start()
            
            # 스레드 ID 저장 (Native ID)
            self.m_Id = self.m_thread.ident
            self.m_RunningStatus = self.T_START
            
            return True

        except RuntimeError as e:
            print(f"[FrThread] Thread Create Fail: {e}")
            return False

    def stop(self):
        """
        C++: void Stop()
        상태 플래그 변경 (실제 스레드 내부에서 이 플래그를 체크하여 루프를 빠져나와야 함)
        """
        self.m_RunningStatus = self.T_STOP

    def get_status(self):
        """
        C++: T_STATUS& GetStatus()
        """
        return self.m_RunningStatus

    def terminate(self):
        """
        C++: bool Terminite()
        Python은 pthread_cancel 같은 강제 종료를 지원하지 않음.
        대신 stop()을 호출하여 플래그를 변경하고 스레드가 끝나기를 기다리는 방식을 권장.
        """
        if self.m_thread and self.m_thread.is_alive():
            # 강제 종료 불가 -> Stop 플래그 설정으로 대체
            self.m_RunningStatus = self.T_STOP
            # 강제 종료가 꼭 필요하다면 ctypes를 이용해야 하지만 매우 위험함.
            # 여기서는 우아한 종료 유도.
            print("[FrThread] Warning: Python does not support force terminate. Set status to STOP.")
            
        self.m_Id = 0
        self.m_RunningStatus = self.T_STOP
        return True

    def join(self):
        """
        C++: bool Join()
        스레드가 종료될 때까지 대기
        """
        if self.m_thread:
            try:
                self.m_thread.join()
                self.m_RunningStatus = self.T_STOP
                return True
            except RuntimeError as e:
                print(f"[FrThread] Thread join Fail: {e}")
                return False
        return False

    def detach(self):
        """
        C++: void Detach()
        Python에는 detach 개념이 명시적으로 없으나, 
        daemon 속성을 True로 주거나 join을 안 하면 됨.
        이미 start된 후에는 daemon 설정이 불가능하므로 여기서는 pass 처리.
        """
        pass

    def get_thread_id(self):
        """
        C++: THREAD_ID GetThreadId()
        """
        return self.m_Id

    @staticmethod
    def get_thread_self_id():
        """
        C++: THREAD_ID GetThreadSelfId()
        """
        return threading.get_ident()