import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrTimerSensor import FrTimerSensor

# -------------------------------------------------------
# ProcClearTimer Class
# 지정된 PID에 대해 waitpid를 호출하여 좀비 프로세스 정리
# -------------------------------------------------------
class ProcClearTimer(FrTimerSensor):
    def __init__(self):
        """
        C++: ProcClearTimer()
        """
        super().__init__()

    def __del__(self):
        """
        C++: ~ProcClearTimer()
        """
        super().__del__()

    def receive_time_out(self, reason, extra_reason):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        Reason 인자로 넘어온 값을 PID로 간주하고 waitpid 실행
        """
        target_pid = reason
        
        try:
            # os.WNOHANG: 프로세스가 아직 종료되지 않았으면 블로킹되지 않고 0 리턴
            pid, status = os.waitpid(target_pid, os.WNOHANG)
            
            # C++: frDEBUG(("WaitPid(%d) Result : %d", Reason, ret));
            print(f"[ProcClearTimer] WaitPid({target_pid}) Result : {pid}")
            
        except ChildProcessError:
            # 이미 회수되었거나 내 자식 프로세스가 아님
            print(f"[ProcClearTimer] WaitPid({target_pid}) : No child process found")
        except OSError as e:
            print(f"[ProcClearTimer] WaitPid({target_pid}) Error : {e}")