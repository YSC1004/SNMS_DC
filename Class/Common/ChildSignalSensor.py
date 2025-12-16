import sys
import os
import signal

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrSignalSensor import FrSignalSensor

# -------------------------------------------------------
# ChildSignalSensor Class
# SIGCHLD 시그널을 감지하여 자식 프로세스 종료 처리 위임
# -------------------------------------------------------
class ChildSignalSensor(FrSignalSensor):
    def __init__(self, child_proc_handler):
        """
        C++: ChildSignalSensor(ChildProcessHandler* ChildProcHandler) : frSignalSensor(SIGCHLD)
        """
        # 부모 생성자 호출 (SIGCHLD 감시 등록)
        super().__init__(signal.SIGCHLD)
        
        self.m_ChildProcHandler = child_proc_handler

    def __del__(self):
        """
        C++: ~ChildSignalSensor()
        """
        super().__del__()

    def subject_changed(self):
        """
        C++: int SubjectChanged()
        SIGCHLD 발생 시 호출됨 -> 핸들러에게 Wait 처리를 위임
        """
        # print("[ChildSignalSensor] Recv SIGCHLD")
        
        if self.m_ChildProcHandler:
            # Duck Typing: wait_proc 메서드 호출
            if hasattr(self.m_ChildProcHandler, 'wait_proc'):
                self.m_ChildProcHandler.wait_proc()
            else:
                print("[ChildSignalSensor] Error: Handler has no 'wait_proc' method")
        
        return 1