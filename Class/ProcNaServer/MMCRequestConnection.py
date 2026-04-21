"""
MMCRequestConnection.py
C++ MMCRequestConnection.h/.C → Python 변환

MMC 요청 처리 소켓 기반 클래스.
  - AsSocket 상속
  - MMCRequestQueue 보유 (세션 종료 시 SetStatus(false))
  - SendFlowControl: 큐 초과 시 흐름 제어 패킷 전송
  - SendMMCResult: 가상 메서드 (하위 클래스 오버라이드)
"""

import asyncio
import logging
from typing import Optional, TYPE_CHECKING

from Common.AsSocket import AsSocket                    # 치트시트: AsSocket 가상함수
from Common.CommTypeList import (
    AS_MMC_FLOW_CONTROL_T, AS_MMC_RESULT_T,
)
from Common.CommType import AS_MMC_FLOW_CONTROL

if TYPE_CHECKING:
    from ProcNaServer.MMCRequestQueue import MMCRequestQueue

logger = logging.getLogger(__name__)

# 흐름 제어 타임아웃 이유
FLOW_CONTROL_TIMEOUT_REASON = 1019


class MMCRequestConnection(AsSocket):
    """
    C++ MMCRequestConnection (AsSocket 상속) 대응.

    하위 클래스:
      MMCGenConnection  (MMCGenerator/Scheduler/JobMonitor)
      ExternalConnection (외부 시스템 MMC 요청)
    """

    def __init__(self) -> None:
        super().__init__()
        self._mmc_request_queue: Optional["MMCRequestQueue"] = None
        self._session_status:    bool = False               # C++: m_SessionStatus

    def __del__(self) -> None:
        # C++: ~MMCRequestConnection() → m_MMCRequestQueue->SetStatus(false)
        if self._mmc_request_queue is not None:
            self._mmc_request_queue.SetStatus(False)

    # =========================================================================
    # SendFlowControl (virtual)
    # =========================================================================

    async def SendFlowControl(self, msg_id: int = -1) -> bool:
        """
        C++: virtual SendFlowControl(int MsgId = -1)

        MsgId > 0 : 큐 초과로 Stop   (controlMode=0, msgId=MsgId)
        MsgId <= 0: 큐 여유로 Restart (controlMode=1, msgId=MsgId)

        C++ 원본: SendNonBlockPacket → Python: SendPacket (async)
        """
        flow_ctl = AS_MMC_FLOW_CONTROL_T()

        if msg_id > 0:
            # Stop: 커맨드 양 초과
            flow_ctl.controlMode = 0
            flow_ctl.msgId       = msg_id
            flow_ctl.controlInfo = "Command 양을 초과하였습니다"
        else:
            # Restart
            flow_ctl.msgId       = msg_id
            flow_ctl.controlMode = 1

        payload = _pack(flow_ctl)
        return await self.SendPacket(AS_MMC_FLOW_CONTROL, payload, len(payload))

    # =========================================================================
    # SendMMCResult (virtual)
    # =========================================================================

    async def SendMMCResult(self, result: AS_MMC_RESULT_T) -> bool:
        """
        C++: virtual SendMMCResult(AS_MMC_RESULT_T*) — 가상 메서드.
        하위 클래스(ExternalConnection 등)에서 오버라이드.
        """
        logger.debug("MMCRequestConnection::SendMMCResult is virtual Function")
        return True


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''