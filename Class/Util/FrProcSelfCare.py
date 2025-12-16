import sys
import os
import time
import subprocess

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Util.FrArgParser import FrArgParser

# -------------------------------------------------------
# FrProcSelfCare Class
# 프로세스 감시 및 자동 재시작(Self-Care) 관리자
# -------------------------------------------------------
class FrProcSelfCare:
    ARG_SELF_CARE = "-selfcare"

    def __init__(self):
        self.m_ChildProc = None # subprocess.Popen 객체

    def __del__(self):
        pass

    def is_self_care(self, argv):
        """
        C++: bool IsSelfCare(int Argc, char** Argv)
        '-selfcare' 옵션이 포함되어 있는지 확인
        """
        parser = FrArgParser(argv)
        return parser.does_it_exist(self.ARG_SELF_CARE)

    def run(self, argv):
        """
        C++: void Run(int Argc, char** Argv)
        무한 루프를 돌며 자식 프로세스를 실행하고 감시함
        """
        # 1. 실행 인자 재구성 ( -selfcare 옵션 제거)
        # 예: ['python3', 'main.py', '-selfcare', '-p', '8080'] 
        # -> ['python3', 'main.py', '-p', '8080']
        new_args = []
        
        # Python 스크립트 실행을 위해 인터프리터 경로 추가
        # (C++은 컴파일된 바이너리라 argv[0]만 있으면 되지만, Python은 python 실행파일 필요)
        new_args.append(sys.executable)

        for arg in argv:
            if arg != self.ARG_SELF_CARE:
                new_args.append(arg)

        print(f"[FrProcSelfCare] Watchdog Mode Started. Target: {new_args}")

        # 2. 감시 루프
        while True:
            # 자식 프로세스 실행
            self.m_ChildProc = self.start_proc("SelfCare", new_args)

            if self.m_ChildProc:
                print(f"[FrProcSelfCare] Child Process Started (PID: {self.m_ChildProc.pid})")
                
                # 자식 프로세스가 종료될 때까지 대기 (Blocking)
                # C++: wait(&status)
                try:
                    self.m_ChildProc.wait()
                except KeyboardInterrupt:
                    # 사용자가 Ctrl+C를 누른 경우, 감시 프로세스도 종료해야 함
                    print("[FrProcSelfCare] Keyboard Interrupt. Stopping Watchdog.")
                    self.m_ChildProc.terminate()
                    break

                # 자식이 종료됨 -> 재시작 준비
                print(f"[FrProcSelfCare] Child Process Died. Restarting in 5 seconds...")
                time.sleep(5)
            else:
                print("[FrProcSelfCare] Failed to start child process. Exiting.")
                break

    def start_proc(self, name, args):
        """
        C++: int StartProc(string Name, frStringVector* Args)
        subprocess.Popen을 사용하여 자식 프로세스 실행
        """
        try:
            # args는 리스트 형태 (예: ['/usr/bin/python3', 'main.py', '-p', '8080'])
            proc = subprocess.Popen(args)
            return proc
        except OSError as e:
            print(f"[FrProcSelfCare] Process Start Error({name}) : {e}")
            return None