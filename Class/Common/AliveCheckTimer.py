import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrTimerSensor import FrTimerSensor
from Class.Common.CommType import CMD_ALIVE_CHECK, CMD_ALIVE_RECEIVE, CMD_ALIVE_SEND

# -------------------------------------------------------
# AliveCheckTimer Class
# 주기적으로 Alive Check(Heartbeat)를 수행하는 타이머
# -------------------------------------------------------
class AliveCheckTimer(FrTimerSensor):
    def __init__(self, interval, check_mode, socket_obj):
        """
        C++: AliveCheckTimer(int Interval, int CheckMode, AsSocket* Socket)
        """
        super().__init__()
        
        self.m_CheckInterval = interval
        self.m_CheckMode = check_mode
        self.m_AsSocket = socket_obj # AsSocket 객체 참조
        
        # 타이머 시작 (Reason: CMD_ALIVE_CHECK)
        self.set_timer(self.m_CheckInterval, CMD_ALIVE_CHECK)

    def __del__(self):
        """
        C++: ~AliveCheckTimer()
        """
        super().__del__()

    def receive_time_out(self, reason, extra_reason):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        타이머 만료 시 호출됨
        """
        if reason == CMD_ALIVE_CHECK:
            if self.m_AsSocket:
                if self.m_CheckMode == CMD_ALIVE_RECEIVE:
                    # 수신 확인 (상대방이 살아있는지 체크)
                    # C++: m_AsSocket->AliveCheckTime()
                    # Python AsSocket 메서드명: alive_check_time (구현 필요)
                    if hasattr(self.m_AsSocket, 'alive_check_time'):
                        self.m_AsSocket.alive_check_time()
                    else:
                        print("[AliveCheckTimer] Error: AsSocket has no alive_check_time")

                elif self.m_CheckMode == CMD_ALIVE_SEND:
                    # 송신 (내가 살아있음을 알림)
                    # C++: m_AsSocket->AliveCheckSendTime()
                    # Python AsSocket 메서드명: alive_check_send_time (구현 필요)
                    if hasattr(self.m_AsSocket, 'alive_check_send_time'):
                        self.m_AsSocket.alive_check_send_time()
                    else:
                        print("[AliveCheckTimer] Error: AsSocket has no alive_check_send_time")

                else:
                    print(f"[AliveCheckTimer] Abnormal Check Mode : {self.m_CheckMode}")
            
            # 주기적 실행을 위해 타이머 재설정
            self.set_timer(self.m_CheckInterval, reason)
            
        else:
            print(f"[AliveCheckTimer] Abnormal Time Out Reason : {reason}")