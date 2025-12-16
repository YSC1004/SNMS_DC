import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrTimerSensor import FrTimerSensor

# -------------------------------------------------------
# ProcConnectionMgrTimer Class
# ProcConnectionMgr를 위한 타이머 (현재는 Stub 상태)
# -------------------------------------------------------
class ProcConnectionMgrTimer(FrTimerSensor):
    def __init__(self, mgr):
        """
        C++: ProcConnectionMgrTimer(ProcConnectionMgr* Mgr)
        """
        super().__init__()
        
        # 매니저 객체 참조 저장
        self.m_ProcConnectionMgr = mgr

    def __del__(self):
        """
        C++: ~ProcConnectionMgrTimer()
        """
        super().__del__()

    def receive_time_out(self, reason, extra_reason):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        
        [참고] 제공된 C++ 원본 소스에 구현 내용이 없으므로 
        Python에서도 pass 처리합니다. 
        추후 프로세스 정리(Kill) 후 대기 로직 등이 필요할 때 이곳에 구현합니다.
        """
        pass