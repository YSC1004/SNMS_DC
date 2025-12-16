import sys
import os
import time
import subprocess
import signal

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrTimerSensor import FrTimerSensor
from Class.Util.FrTime import FrTime
from Class.Common.CommType import AsProcessStatusT

# -------------------------------------------------------
# ProcConnectionMgr Class
# 자식 프로세스 관리 (생성, 종료, PID 매핑)
# -------------------------------------------------------
class ProcConnectionMgr:
    PROCESS_WAIT_TIME = 5

    def __init__(self):
        # { "ProcName": PID }
        self.m_ProcPidInfo = {}
        
        # 프로세스 정리용 타이머 (FrTimerSensor 상속 클래스 필요)
        # 여기서는 간단히 FrTimerSensor 사용 (콜백 구현 필요 시 상속)
        self.m_ProcClearTimer = FrTimerSensor()

    def __del__(self):
        # 타이머 해제 등
        if self.m_ProcClearTimer:
            self.m_ProcClearTimer.unregister_sensor()

    # ---------------------------------------------------
    # Process Map Management
    # ---------------------------------------------------
    def remove_pid(self, proc_name):
        """
        C++: bool RemovePid(string ProcName)
        """
        if proc_name in self.m_ProcPidInfo:
            del self.m_ProcPidInfo[proc_name]
            return True
        else:
            print(f"[ProcConnectionMgr] Can't Find Process Pid : {proc_name}")
            return False

    def get_proc_name(self, pid):
        """
        C++: string GetProcName(int Pid)
        """
        for name, p_id in self.m_ProcPidInfo.items():
            if p_id == pid:
                return name
        # print(f"[ProcConnectionMgr] Can't Find Process Name Pid({pid})")
        return ""

    def get_proc_pid(self, proc_name):
        """
        C++: int GetProcPid(string ProcName)
        """
        return self.m_ProcPidInfo.get(proc_name, -1)

    # ---------------------------------------------------
    # Process Control
    # ---------------------------------------------------
    def start_proc(self, name, args):
        """
        C++: int StartProc(string Name, frStringVector Args)
        """
        try:
            # args는 리스트 형태여야 함
            # Python 스크립트 실행 시 인터프리터 경로 추가 필요할 수 있음
            proc = subprocess.Popen(args)
            pid = proc.pid
            
            self.m_ProcPidInfo[name] = pid
            print(f"[ProcConnectionMgr] Started Process: {name} (PID: {pid})")
            return pid
            
        except OSError as e:
            print(f"[ProcConnectionMgr] Process Start Error({name}) : {e}")
            return -1

    def stop_process_by_name(self, name):
        """
        C++: bool StopProcess(string Name)
        """
        pid = self.get_proc_pid(name)
        if pid == -1:
            print(f"[ProcConnectionMgr] Can't Find Process Name : {name}")
            return True # 이미 없으므로 성공 간주
            
        return self.kill_proc(pid)

    def stop_process_by_pid(self, pid):
        """
        C++: bool StopProcess(int Pid)
        """
        # 맵에 있는지 확인 (없어도 Kill은 시도할 수 있음)
        for name, p_id in self.m_ProcPidInfo.items():
            if p_id == pid:
                return self.kill_proc(pid)
        return False

    def kill_proc(self, pid):
        """
        ChildProcessManager::KillProc 대체
        """
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except OSError as e:
            print(f"[ProcConnectionMgr] Kill Error (PID:{pid}): {e}")
            return False

    # ---------------------------------------------------
    # Process Info
    # ---------------------------------------------------
    def get_process_info_by_pid(self, pid, process_status):
        """
        C++: bool GetProcessInfo(int Pid, AS_PROCESS_STATUS_T* Process)
        """
        process_status.Pid = pid
        
        # 시작 시간은 현재 시간으로 설정 (C++ 로직 동일)
        # 실제 프로세스 시작 시간을 얻으려면 psutil 등을 써야 함
        cur_time = FrTime()
        process_status.StartTime = cur_time.get_time_string()
        
        return True

    def get_process_info_by_name(self, proc_name, process_status):
        """
        C++: bool GetProcessInfo(string ProcName, AS_PROCESS_STATUS_T* Process)
        """
        pid = self.get_proc_pid(proc_name)
        if pid == -1:
            return False
            
        return self.get_process_info_by_pid(pid, process_status)

    def get_process_info_list(self, proc_info_list):
        """
        C++: void GetProcessInfo(ProcessInfoList& ProcInfoList)
        """
        for name, pid in self.m_ProcPidInfo.items():
            status = AsProcessStatusT() # CommType.py의 클래스
            status.ProcessId = name
            self.get_process_info_by_pid(pid, status)
            proc_info_list.append(status)

    # ---------------------------------------------------
    # Event Handlers
    # ---------------------------------------------------
    def child_process_dead(self, socket, status):
        """
        C++: void ChildProcessDead(AsSocket* Socket, int Status)
        소켓 연결이 끊기거나 프로세스가 죽었을 때 호출됨
        """
        name = socket.get_session_name()
        pid = self.get_proc_pid(name)
        
        self.remove_pid(name)
        # self.remove(socket) # ConnectionMgr 상속 시 구현
        
        print(f"[ProcConnectionMgr] {name}({pid}) Process Dead")

        # 타이머 설정 (재시작 딜레이 등)
        # Reason ID로 pid를 넘기는 것은 Python에서는 별도 처리 필요 (Timer 클래스 확장 등)
        # 여기서는 단순히 타이머만 설정
        self.m_ProcClearTimer.set_timer(self.PROCESS_WAIT_TIME, pid)
        
        self.process_dead(name, pid, status)

    # ---------------------------------------------------
    # Virtual Functions (Override Targets)
    # ---------------------------------------------------
    def process_dead(self, name, pid, status):
        """
        C++: virtual void ProcessDead(...)
        """
        print(f"[ProcConnectionMgr] ProcessDead Virtual Call: {name}")

    def remove(self, socket):
        """
        C++: ConnectionMgr::Remove(Socket)
        부모 클래스(ConnectionMgr)에 있을 것으로 추정
        """
        pass