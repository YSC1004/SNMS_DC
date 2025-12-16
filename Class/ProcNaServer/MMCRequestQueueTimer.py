import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 만약 AsTimer 같은 베이스 클래스가 있다면 상속받아야 합니다.
# 여기서는 로직 전달자 역할만 수행하도록 구현합니다.
class MMCRequestQueueTimer:
    """
    MMCRequestQueue의 타임아웃 이벤트를 수신하여 전달하는 타이머 클래스
    """
    def __init__(self, queue):
        """
        C++: MMCRequestQueueTimer(MMCRequestQueue* Queue)
        """
        self.m_MMCRequestQueue = queue

    def __del__(self):
        """
        C++: ~MMCRequestQueueTimer()
        """
        pass

    def receive_time_out(self, reason, extra_reason=None):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        타이머 만료 시 호출되어 큐의 타임아웃 처리 로직을 실행
        """
        if self.m_MMCRequestQueue:
            self.m_MMCRequestQueue.receive_time_out(reason, extra_reason)