import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrWorld import FrWorld, FR_MODE
from Class.Event.FrThread import FrThread
from Class.Event.FrMutex import FrMutex
from Class.Event.FrCondition import FrCondition

# -------------------------------------------------------
# FrThreadWorld Class
# 별도의 스레드에서 이벤트 루프를 돌리는 World
# -------------------------------------------------------
class FrThreadWorld(FrWorld):
    def __init__(self):
        """
        C++: frThreadWorld():frWorld(frWorld::FR_THREAD)
        """
        # Python에서는 FR_THREAD 상수가 없으므로 FR_SUB(1) 모드로 초기화
        super().__init__(FR_MODE.FR_SUB)
        
        self.m_frThread = FrThread()
        self.m_ThreadStartLock = FrMutex()
        self.m_ThreadCond = FrCondition()
        self.m_TId = 0

    def __del__(self):
        """
        C++: ~frThreadWorld()
        """
        # 객체들은 GC에 의해 자동 정리됨
        pass

    # ---------------------------------------------------
    # Execution Control
    # ---------------------------------------------------
    def run(self):
        """
        C++: bool Run()
        스레드를 생성하고, 스레드가 초기화를 마칠 때까지 대기(Wait)함
        """
        # 동기화를 위해 Lock 획득
        self.m_ThreadStartLock.lock()

        # 스레드 시작 (Target: self._thread_entry)
        # C++의 static Start 함수 대신 인스턴스 메서드 사용
        if not self.m_frThread.start(self._thread_entry):
            self.m_ThreadStartLock.unlock()
            return False

        # 스레드 ID 저장 및 월드 등록
        self.m_EventThreadId = self.m_frThread.get_thread_id()
        self.register_world(self, self.m_EventThreadId)

        # 자식 스레드가 초기화 완료 신호(Signal)를 보낼 때까지 대기
        # Wait 내부에서 Unlock -> 대기 -> Signal 수신 -> Lock 과정을 거침
        self.m_ThreadCond.wait(self.m_ThreadStartLock)
        
        # 신호를 받고 깨어남, Lock 해제
        self.m_ThreadStartLock.unlock()

        # 초기화 실패 시 정리
        if not self.m_RunStatus:
            self.wait_finish()

        return self.m_RunStatus

    def _thread_entry(self):
        """
        C++: static void* Start(void* Arg)
        실제 스레드가 수행하는 진입점 함수
        """
        # 메인 스레드가 Wait()에 들어가서 Lock을 풀 때까지 대기하거나 즉시 획득
        self.m_ThreadStartLock.lock()

        # 1. 초기화 작업
        self.create_world_pipe()
        
        # 2. 메인 스레드 깨우기 (초기화 완료 알림)
        self.m_ThreadCond.signal()

        # 3. Thread ID 갱신
        self.m_TId = FrThread.get_thread_self_id()

        # 4. 사용자 정의 초기화 실행 (AppStart)
        # Argc, Argv는 FrWorld의 static 변수 사용
        self.m_RunStatus = self.app_start(FrWorld.m_Argc, FrWorld.m_Argv)

        # 5. Lock 해제 (이제 메인 스레드와 독립적으로 동작)
        self.m_ThreadStartLock.unlock()

        # 6. 이벤트 루프 진입
        if self.m_RunStatus:
            self.run_world()

    def app_start(self, argc, argv):
        """
        C++: virtual bool AppStart(...)
        자식 클래스에서 오버라이딩하여 로직 구현
        """
        return True

    def wait_finish(self):
        """
        C++: bool WaitFinish()
        스레드 종료 대기 (Join)
        """
        if not self.m_frThread.join():
            print(f"[FrThreadWorld] Wait thread Fail, WorldId({self.m_WorldId})")
            return False
        else:
            # print(f"[FrThreadWorld] Wait thread success, WorldId : {self.m_WorldId}")
            return True