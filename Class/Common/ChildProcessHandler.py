import sys
import os
import signal
import subprocess

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.ClearSignalSensor import ClearSignalSensor

# -------------------------------------------------------
# ChildProcessHandler Class
# 자식 프로세스 목록을 관리하고, 종료 시 일괄 Kill 수행
# -------------------------------------------------------
class ChildProcessHandler:
    def __init__(self):
        """
        C++: ChildProcessHandler()
        """
        # 관리할 자식 프로세스 리스트 (subprocess.Popen 객체들)
        self.m_ProcessList = []
        
        # SIGINT 감지 센서 생성 (자신(self)을 핸들러로 등록)
        # 이 센서가 SIGINT를 받으면 self.process_all_kill()을 호출함
        self.m_ClearSignalSensor = ClearSignalSensor(self)
        
        # ChildSignalSensor는 주석 처리되어 있어 생략
        # self.m_ChildSignalSensor = ChildSignalSensor(self)

    def __del__(self):
        """
        C++: ~ChildProcessHandler()
        """
        # 센서 해제 (ClearSignalSensor __del__ 호출됨)
        self.m_ClearSignalSensor = None

    def process_all_kill(self):
        """
        C++: void ProcessAllKill()
        """
        self.kill_all_proc()

    def wait_proc(self):
        """
        C++: virtual void WaitProc()
        [보완] SIGCHLD 발생 시 종료된 자식 프로세스 정보 회수 (Zombie 방지)
        """
        try:
            while True:
                # -1: 어떤 자식이든, WNOHANG: 종료된 자식이 없으면 즉시 리턴 (Non-blocking)
                pid, status = os.waitpid(-1, os.WNOHANG)
                
                if pid == 0:
                    # 더 이상 종료된 자식이 없음
                    break
                
                print(f"[ChildProcessHandler] Child {pid} terminated with status {status}")
                
                # 관리 리스트에서 제거
                # (self.m_ProcessList는 Popen 객체나 int PID를 담고 있음)
                self._remove_process_from_list(pid)
                
        except ChildProcessError:
            # 자식 프로세스가 없는 경우
            pass
        except OSError:
            pass

    def _remove_process_from_list(self, pid):
        # 리스트에서 해당 PID를 가진 항목 제거
        for proc in self.m_ProcessList[:]: # 복사본 순회
            if isinstance(proc, int) and proc == pid:
                self.m_ProcessList.remove(proc)
            elif hasattr(proc, 'pid') and proc.pid == pid:
                self.m_ProcessList.remove(proc)

    # ---------------------------------------------------
    # Process Management Logic (C++ KillAllProc 구현)
    # ---------------------------------------------------
    def add_process(self, proc):
        """
        프로세스 등록 (subprocess.Popen 객체)
        """
        if proc not in self.m_ProcessList:
            self.m_ProcessList.append(proc)

    def kill_all_proc(self):
        """
        등록된 모든 자식 프로세스 종료
        """
        if not self.m_ProcessList:
            return

        print(f"[ChildProcessHandler] Killing {len(self.m_ProcessList)} child processes...")
        
        for proc in self.m_ProcessList:
            try:
                # Popen 객체인 경우
                if isinstance(proc, subprocess.Popen):
                    if proc.poll() is None: # 아직 실행 중이면
                        print(f"   - Terminating PID: {proc.pid}")
                        proc.terminate() # SIGTERM 전송
                        try:
                            proc.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            proc.kill() # 강제 종료 (SIGKILL)
                            
                # 단순 PID(int)인 경우
                elif isinstance(proc, int):
                    os.kill(proc, signal.SIGTERM)
                    
            except Exception as e:
                print(f"[ChildProcessHandler] Error killing process: {e}")
        
        self.m_ProcessList.clear()