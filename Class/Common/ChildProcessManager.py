import sys
import os
import signal
import errno

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# ChildProcessManager Class
# PID 기반 자식 프로세스 관리 (등록, 강제종료, 좀비 회수)
# -------------------------------------------------------
class ChildProcessManager:
    def __init__(self):
        """
        C++: ChildProcessManager()
        """
        # PID를 저장할 Set (중복 방지)
        self.m_PidSet = set()

    def __del__(self):
        """
        C++: ~ChildProcessManager()
        """
        pass

    def add_pid(self, pid):
        """
        C++: bool AddPid(int Pid)
        """
        if pid in self.m_PidSet:
            return False
        
        self.m_PidSet.add(pid)
        return True

    def remove_pid(self, pid):
        """
        C++: bool RemovePid(int Pid)
        """
        if pid not in self.m_PidSet:
            print(f"[ChildProcessManager] Can't Find Pid : {pid}")
            return False
        
        self.m_PidSet.remove(pid)
        return True

    @staticmethod
    def kill_proc(pid):
        """
        C++: bool KillProc(int Pid)
        특정 PID에 SIGKILL 전송 (Static으로 사용 가능)
        """
        try:
            os.kill(pid, signal.SIGKILL)
            return True
        except OSError:
            return False

    def kill_all_proc(self):
        """
        C++: void KillAllProc()
        등록된 모든 프로세스 강제 종료
        """
        print("[ChildProcessManager] Process All Kill...................")
        
        for pid in self.m_PidSet:
            try:
                os.kill(pid, signal.SIGKILL)
                print(f"[ChildProcessManager] Process Kill : {pid}")
            except OSError as e:
                print(f"[ChildProcessManager] Process Kill Error(pid:{pid}) : {e}")
        
        self.m_PidSet.clear()

    def wait_proc(self):
        """
        C++: void WaitProc()
        등록된 PID들을 순회하며 종료되었는지 확인하고 회수(Reaping)함.
        """
        # Set을 순회하면서 삭제해야 하므로 복사본(list)을 사용
        for pid in list(self.m_PidSet):
            try:
                # os.WNOHANG: 종료되지 않았으면 기다리지 않고 즉시 리턴 (0, 0 반환)
                pid_ret, status = os.waitpid(pid, os.WNOHANG)

                if pid_ret == pid:
                    # 프로세스가 종료됨
                    print(f"[ChildProcessManager] Recv Child Signal OK...(PID:{pid})")
                    self.m_PidSet.remove(pid)
                    
                    # C++ 원본 로직: 한 번에 하나만 처리하고 break 하는 구조를 따름
                    # (필요 시 break 제거하여 한 번에 모두 처리 가능)
                    break 
                    
            except ChildProcessError:
                # 이미 종료되었거나 내 자식 프로세스가 아님
                self.m_PidSet.remove(pid)
            except OSError:
                pass