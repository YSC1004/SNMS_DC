import sys
import os
import threading
import copy
from collections import deque

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.ProcNaServer.MMCRequestQueueTimer import MMCRequestQueueTimer

class MMCRequestQueue:
    """
    MMC 요청 메시지를 관리하는 큐 클래스.
    최대 크기 제한 및 흐름 제어(Flow Control) 기능을 포함함.
    """
    def __init__(self, max_cmd_cnt, req_conn):
        """
        C++: MMCRequestQueue(int MaxCmdCnt, MMCRequestConnection* ReqConn)
        """
        self.m_MaxCmdCnt = max_cmd_cnt
        self.m_Status = True
        self.m_QueueEmpty = True # True implies "Ready to accept", False implies "Full/Flow Control Active"
        self.m_MMCRequestConnection = req_conn
        
        # C++ std::list -> Python deque (Thread-safe, O(1) pops)
        self.m_ReqList = deque()
        
        self.m_QueueTimer = None
        self.m_QueueLock = threading.Lock()
        self.m_StatusLock = threading.Lock()
        self.m_QueueName = ""

    def __del__(self):
        """
        C++: ~MMCRequestQueue()
        """
        # Python handles memory deallocation automatically
        self.m_ReqList.clear()
        if self.m_QueueTimer:
            # Assuming timer has a cancel or stop method if inherited from AsTimer
            pass

    def insert_mmc_request(self, mmc_req):
        """
        C++: bool InsertMMCRequest(AS_MMC_REQUEST_T* MMCReq)
        큐에 요청 삽입. 큐가 가득 찼으면 Flow Control 시작.
        """
        if self.m_QueueEmpty:
            with self.m_QueueLock:
                # 큐 크기 체크
                if self.m_MaxCmdCnt < len(self.m_ReqList):
                    # Lock 해제는 with 문이 처리
                    
                    # 1. Flow Control 시작 (Stop)
                    # print(f"[MMCRequestQueue] Send Flow Control Stop... MaxSize({self.m_MaxCmdCnt}), QueueSize({len(self.m_ReqList)})")
                    
                    if self.m_MMCRequestConnection:
                        # C++: SendFlowControl(MMCReq->id)
                        self.m_MMCRequestConnection.send_flow_control(mmc_req.id)
                    
                    self.m_QueueEmpty = False
                    self.set_timer()
                    return False

                # 2. 큐에 삽입
                # C++: memcpy -> push_back
                # Python: Deep copy to act like separate memory instance
                new_req = copy.deepcopy(mmc_req)
                self.m_ReqList.append(new_req)
                
                return True
        else:
            # print("[MMCRequestQueue] Command Not Receive Because of Queue is Full...")
            return False

    def get_mmc_request(self):
        """
        C++: AS_MMC_REQUEST_T* GetMMCRequest()
        큐에서 요청 하나를 꺼냄 (FIFO)
        """
        mmc_req = None
        
        with self.m_QueueLock:
            # --- Debug Logging (Before) ---
            # self.status_lock()
            # conn_name = self.m_MMCRequestConnection.get_session_name() if self.m_MMCRequestConnection else "Disconnect Session"
            # print(f"GetMMCRequest Before cnt({conn_name}) : {len(self.m_ReqList)}")
            # self.status_unlock()
            # ------------------------------

            if len(self.m_ReqList) > 0:
                mmc_req = self.m_ReqList.popleft() # pop_front

            # --- Debug Logging (After) ---
            # self.status_lock()
            # conn_name = self.m_MMCRequestConnection.get_session_name() if self.m_MMCRequestConnection else "Disconnect Session"
            # print(f"GetMMCRequest After cnt({conn_name}) : {len(self.m_ReqList)}")
            # self.status_unlock()
            # -----------------------------

        return mmc_req

    def set_status(self, status):
        """
        C++: void SetStatus(bool Status)
        """
        with self.m_StatusLock:
            self.m_Status = status
            # Status가 변경(주로 False)되면 연결 객체 참조를 해제
            self.m_MMCRequestConnection = None

    def get_status(self):
        """
        C++: bool GetStatus()
        """
        return self.m_Status

    def receive_time_out(self, reason, extra_reason=None):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        타이머 콜백: Flow Control 해제 조건 확인
        """
        if reason == 1019:
            # --- Debug Log ---
            # self.status_lock()
            # conn_name = self.m_MMCRequestConnection.get_session_name() if self.m_MMCRequestConnection else "Disconnect Session"
            # print(f"Check MMCReqQueue size({conn_name})...")
            # self.status_unlock()
            # -----------------

            # 큐 상태 재확인 (Lock 필요 여부는 상황에 따르나, 여기선 size 체크만 수행)
            current_size = len(self.m_ReqList)

            if self.m_MaxCmdCnt < current_size:
                # 여전히 큐가 가득 참 -> 타이머 재설정
                # print(f"[MMCRequestQueue] MaxSize({self.m_MaxCmdCnt}), QueueSize({current_size})")
                self.set_timer()
            else:
                # 큐가 비워짐 -> Flow Control 해제 (Restart)
                # print("[MMCRequestQueue] Send Flow Control Restart...")
                
                with self.m_StatusLock:
                    if self.m_Status and self.m_MMCRequestConnection:
                        # C++: SendFlowControl() (Overloaded or Default Arg)
                        # Python: Pass None or specific flag to indicate Resume
                        # Assuming connection handles None as Resume or generic signal
                        # If connection only accepts one arg, you might need to check implementation.
                        # Here assuming send_flow_control(-1) or similar means resume.
                        # For now, calling without args equivalent if implemented with default.
                        if hasattr(self.m_MMCRequestConnection, 'send_flow_control'):
                             # Assuming implementation supports resume logic
                             try:
                                 self.m_MMCRequestConnection.send_flow_control(None)
                             except TypeError:
                                 # Fallback if signature requires argument
                                 self.m_MMCRequestConnection.send_flow_control(-1)

                self.m_QueueEmpty = True # Ready to accept again

        else:
            print(f"[MMCRequestQueue] [CORE_ERROR] Unknown Time Out : {reason}")

    def set_timer(self):
        """
        C++: void SetTimer()
        """
        if self.m_QueueTimer is None:
            self.m_QueueTimer = MMCRequestQueueTimer(self)
        
        # Assuming MMCRequestQueueTimer / AsTimer has set_timer(seconds, id)
        # 2초 후 1019번 이벤트 발생
        if hasattr(self.m_QueueTimer, 'set_timer'):
            self.m_QueueTimer.set_timer(2, 1019)
        elif hasattr(self.m_QueueTimer, 'SetTimer'): # C++ style naming check
             self.m_QueueTimer.SetTimer(2, 1019)

    def set_queue_name(self, name):
        """
        C++: void SetQueueName(string Name)
        """
        self.m_QueueName = name

    def get_queue_name(self):
        """
        C++: string GetQueueName()
        """
        return self.m_QueueName

    def status_lock(self):
        """
        C++: void StatusLock()
        """
        self.m_StatusLock.acquire()

    def status_unlock(self):
        """
        C++: void StatusUnLock()
        """
        self.m_StatusLock.release()