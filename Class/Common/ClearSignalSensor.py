import sys
import os
import signal

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrSignalSensor import FrSignalSensor
from Class.Event.FrWorld import FrWorld

# -------------------------------------------------------
# ClearSignalSensor Class
# SIGINT(Ctrl+C) 발생 시 자식 프로세스 정리 및 프로그램 종료
# -------------------------------------------------------
class ClearSignalSensor(FrSignalSensor):
    def __init__(self, child_proc_handler):
        """
        C++: ClearSignalSensor(ChildProcessHandler* ChildProcHandler) : frSignalSensor(SIGINT)
        """
        # 부모 생성자 호출 (SIGINT 감시 등록)
        super().__init__(signal.SIGINT)
        
        self.m_ChildProcHandler = child_proc_handler

    def __del__(self):
        super().__del__()

    def subject_changed(self):
        """
        C++: int SubjectChanged()
        시그널 발생 시 호출되는 콜백
        """
        # C++: frSignalEventSrc::SignalsHold(); (Python에서는 자동 처리되거나 생략 가능)

        print("[ClearSignalSensor] Recv SIGINT.....................")

        # 1. 자식 프로세스 정리
        if self.m_ChildProcHandler:
            if hasattr(self.m_ChildProcHandler, 'process_all_kill'):
                self.m_ChildProcHandler.process_all_kill()
            else:
                print("[ClearSignalSensor] Error: Handler has no 'process_all_kill' method")

        # 2. 메인 월드 종료
        if FrWorld.m_MainWorldPtr:
            FrWorld.m_MainWorldPtr.exit(0)
        else:
            # 월드가 없으면 강제 종료
            sys.exit(0)
            
        return 1