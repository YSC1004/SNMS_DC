import sys
import os
import threading
import copy

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# [중요] 부모 클래스 임포트
# (경로는 사용자의 프로젝트 구조에 맞춰 조정 필요, 보통 Class/Common 혹은 Class/ProcNaServer에 위치)
# 만약 SockMgrConnMgr가 Class/Common에 있다면 아래 경로입니다.
from Class.Common.SockMgrConnMgr import SockMgrConnMgr
from Class.ProcNaServer.MMCGenConnection import MMCGenConnection
from Class.Common.CommType import *

class MMCGeneratorConnMgr(SockMgrConnMgr):
    """
    SockMgrConnMgr를 상속받아 소켓 관리 기능(Accept, List 등)을 재사용하고,
    MMC 관련 비즈니스 로직을 추가한 클래스
    """
    def __init__(self):
        """
        C++: MMCGeneratorConnMgr::MMCGeneratorConnMgr()
        """
        # 1. 부모 생성자 호출 (소켓 초기화, 리스트 초기화)
        super().__init__()
        
        # 2. MMC 전용 멤버 변수 초기화
        self.m_MMCGenerator = None
        self.m_MMCScheduler = None
        self.m_JobMonitor = None
        self.m_MmcGeneratorStatus = False
        
        # Lock 초기화
        self.m_SocketRemoveLock = threading.Lock()
        
        # Log Map 초기화
        self.m_LogStatusMap = {} 

    def __del__(self):
        """
        C++: MMCGeneratorConnMgr::~MMCGeneratorConnMgr()
        """
        self.m_LogStatusMap.clear()
        super().__del__()

    # -------------------------------------------------------
    # Override Methods (부모 메서드 재정의)
    # -------------------------------------------------------
    def accept_socket(self):
        """
        C++: void AcceptSocket()
        [중요] 부모의 accept_socket을 오버라이딩하여 
        SockMgrConnection 대신 'MMCGenConnection'을 생성합니다.
        """
        # 1. MMCGenConnection 객체 생성
        mmc_conn = MMCGenConnection(self)

        # 2. 부모(FrSocketSensor)의 accept 기능 사용
        if not self.accept(mmc_conn):
            print(f"[MMCGeneratorConnMgr] MMCGenerator Socket Accept Error : {self.get_obj_err_msg()}")
            mmc_conn.close()
            return

        # 3. 부모(ConnectionMgr)의 리스트 추가 기능 사용
        self.add(mmc_conn)

    # -------------------------------------------------------
    # Business Logic (MMC 고유 기능)
    # -------------------------------------------------------
    def process_dead(self, name, pid, status):
        """
        C++: void ProcessDead(string Name, int Pid, int Status)
        """
        self.send_process_info(name, -1, STOP)

        if status == ORDER_KILL:
            pass
        else:
            from Server.AsciiServerWorld import AsciiServerWorld
            AsciiServerWorld._instance.process_dead(name, pid)

    def set_mmc_generator_session(self, session_type, mmc_con):
        """
        C++: void SetMMCGeneratorSession(int SessionType, MMCGenConnection* MMCCon)
        """
        if session_type == ASCII_MMC_GENERATOR:
            self.m_MMCGenerator = mmc_con
            if mmc_con is None:
                self.m_MmcGeneratorStatus = False

        elif session_type == ASCII_MMC_SCHEDULER:
            self.m_MMCScheduler = mmc_con
            if mmc_con and self.m_MmcGeneratorStatus:
                self.m_MMCScheduler.packet_send_msg(CMD_PROC_INIT)

        elif session_type == ASCII_JOB_MONITOR:
            self.m_JobMonitor = mmc_con

        else:
            print(f"[MMCGeneratorConnMgr] [CORE_ERROR] UnKnown SessionType : {session_type}")

    def send_mmc_req_to_mmc_gen(self, mmc_req):
        """
        C++: void SendMMCReqToMMCGen(AS_MMC_REQUEST_T* MMCReq)
        """
        with self.m_SocketRemoveLock:
            if self.m_MMCGenerator:
                # is_valid_connection은 부모(ConnectionMgr)에 구현되어 있음
                if self.is_valid_connection(self.m_MMCGenerator):
                    self.m_MMCGenerator.send_mmc_req_to_mmc_gen(mmc_req)
                else:
                    print("[MMCGeneratorConnMgr] MMCGenerator Is Not Connection")
            else:
                print("[MMCGeneratorConnMgr] MMCGenerator Is Not Connection")

    def update_mmc_process_log_status(self, status):
        """
        C++: void UpdateMMCProcessLogStatus(AS_LOG_STATUS_T* Status)
        """
        if status.name in self.m_LogStatusMap:
            del self.m_LogStatusMap[status.name]

        if status.status == LOG_ADD:
            self.m_LogStatusMap[status.name] = copy.deepcopy(status)

        from Server.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld._instance.send_log_status(status)

    def get_log_status_list(self, status_list):
        """
        C++: void GetLogStatusList(LogStatusVector* StatusList)
        """
        for status in self.m_LogStatusMap.values():
            status_list.append(status)

    def send_mmc_log(self, mmc_log):
        """
        C++: void SendMMCLog(AS_MMC_LOG_T* MMCLog)
        """
        with self.m_SocketRemoveLock:
            if self.m_JobMonitor:
                if self.is_valid_connection(self.m_JobMonitor):
                    self.m_JobMonitor.send_mmc_log(mmc_log)
                else:
                    print("[MMCGeneratorConnMgr] Job Monitor is Not Connected")
            else:
                print("[MMCGeneratorConnMgr] Job Monitor is Not Connected")

    def stop_process(self, session_name):
        return True

    def send_process_info(self, session_name, process_type, status):
        """
        C++: void SendProcessInfo(...)
        """
        from Server.AsciiServerWorld import AsciiServerWorld
        
        proc_info = AsProcessStatusT()
        proc_info.ProcessId = session_name
        proc_info.Status = status

        if proc_info.Status == START:
            if not self.get_process_info(session_name, proc_info):
                return

        world = AsciiServerWorld._instance
        proc_info.ManagerId = world.get_proc_name()
        proc_info.ProcessType = process_type
        
        world.update_process_info(proc_info)

    def notify_event(self, session_type, msg_id):
        """
        C++: void NotifyEvent(...)
        """
        if session_type == ASCII_MMC_GENERATOR:
            if msg_id == PROC_INIT_END:
                self.m_MmcGeneratorStatus = True
                if self.m_MMCScheduler:
                    if not self.m_MMCScheduler.packet_send_msg(CMD_PROC_INIT):
                        print("[MMCGeneratorConnMgr] [CORE_ERROR] MMCScheduler Socket Broken")
                        # remove는 부모(ConnectionMgr)에 구현되어 있음
                        self.remove(self.m_MMCScheduler)

    def send_cmd_scheduler_rule_down(self):
        if self.m_MMCScheduler:
            self.m_MMCScheduler.packet_send_msg(CMD_SCHEDULER_RULE_DOWN)

    def send_cmd_command_rule_down(self):
        if self.m_MMCGenerator:
            self.m_MMCGenerator.packet_send_msg(CMD_COMMAND_RULE_DOWN)

    def get_process_info(self, session_name, proc_info):
        """
        C++: bool GetProcessInfo(string SessionName, AS_PROCESS_STATUS_T* ProcInfo)
        프로세스 상세 정보(PID, 시작 시간)를 채웁니다.
        """
        import time
        from datetime import datetime

        # 1. 시작 시간 설정 (현재 시간)
        # C++ 포맷: YYYY-MM-DD HH:MM:SS
        now = datetime.now()
        proc_info.StartTime = now.strftime("%Y-%m-%d %H:%M:%S")

        # 2. PID 설정
        # 실제 운영 환경에서는 해당 프로세스의 실제 PID를 찾아야 합니다.
        # (1) 클라이언트가 패킷에 담아 보냈다면 패킷에서 추출해야 하고,
        # (2) 서버가 fork/exec로 띄운 자식 프로세스라면 관리 맵에서 조회해야 합니다.
        # 정보가 없다면 0 또는 임시 값을 설정합니다.
        proc_info.Pid = 0 
        
        # 만약 연결 객체(mmc_con)를 통해 Peer의 정보를 알 수 있다면 여기서 조회 로직 추가
        # 예: proc_info.Pid = self.find_pid_by_name(session_name)
        
        return True