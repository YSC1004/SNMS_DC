import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.AsSocket import AsSocket
from Class.Common.CommType import *

class MMCRequestConnection(AsSocket):
    """
    MMC 요청을 처리하는 연결의 기본 클래스.
    MMCRequestQueue와 연동하여 흐름 제어(Flow Control) 메시지를 전송합니다.
    """
    def __init__(self):
        """
        C++: MMCRequestConnection()
        """
        super().__init__()
        self.m_MMCRequestQueue = None
        self.m_SessionStatus = False

    def __del__(self):
        """
        C++: ~MMCRequestConnection()
        """
        # 큐에게 현재 연결이 끊어짐을 알림
        if self.m_MMCRequestQueue:
            self.m_MMCRequestQueue.set_status(False)
        
        super().__del__()

    def send_flow_control(self, msg_id=0):
        """
        C++: bool SendFlowControl(int MsgId)
        MMC 요청 큐가 가득 찼을 때(STOP) 또는 해소되었을 때(RESTART)
        클라이언트에게 흐름 제어 패킷을 전송합니다.
        
        Args:
            msg_id (int): 0보다 크면 STOP(오버플로우), 0 이하이면 RESTART
        """
        flow_ctl = AsMmcFlowControlT()
        
        # C++ Logic:
        # if(MsgId > 0) -> STOP (0)
        # else -> RESTART (1)
        
        if msg_id > 0:
            # STOP: Queue Full
            flow_ctl.controlMode = 0
            flow_ctl.msgId = msg_id
            flow_ctl.controlInfo = "Command 허용량을 초과하였습니다"
        else:
            # RESTART: Queue Available
            flow_ctl.msgId = msg_id # 보통 0
            flow_ctl.controlMode = 1
            
        # 패킷 직렬화 및 전송
        # C++: SendNonBlockPacket 사용. Python AsSocket은 기본적으로 블로킹/논블로킹 설정을 따름.
        # 여기서는 표준 packet_send 사용.
        body = flow_ctl.pack()
        return self.packet_send(PacketT(AS_MMC_FLOW_CONTROL, len(body), body))

    def send_mmc_result(self, result):
        """
        C++: virtual bool SendMMCResult(AS_MMC_RESULT_T* Result)
        가상 함수: 자식 클래스에서 구현해야 함.
        """
        print("[MMCRequestConnection] MMCRequestConnection::SendMMCResult is virtual Function")
        return True