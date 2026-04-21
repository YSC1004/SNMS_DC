"""
RouterInfoConnMgr.py / RouterInfoConnection.py
C++ RouterInfoConnMgr.h/.C + RouterInfoConnection.h/.C → Python 변환

RouterInfo 요청 처리 (단순 구조 → 하나의 파일로 통합).

RouterInfoConnMgr:
  - RouterInfoConnection Accept 관리만 담당 (로직 없음)

RouterInfoConnection:
  - AS_ROUTER_INFO_REQ 수신 → AsciiServerWorld.GetRouterInfo() 호출
  - AS_ROUTER_INFO_RES 응답 전송
  - equipNo 50 초과 요청 차단
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from Common.ConnectionMgr import ConnectionMgr          # add/remove (치트시트)
from Common.AsSocket import AsSocket                    # 가상함수 오버라이드 (치트시트)
from Common.CommTypeList import (
    AS_ROUTER_INFO_REQ_T, AS_ROUTER_INFO_RES_T,
)
from Common.CommType import (
    AS_ROUTER_INFO_REQ, AS_ROUTER_INFO_RES,
)
from ProcNaServer.AsciiServerType import RouterInfoList

logger = logging.getLogger(__name__)

# RouterInfo 요청 equipNo 최대값
MAX_EQUIP_NO = 50


# =============================================================================
# RouterInfoConnMgr
# =============================================================================

class RouterInfoConnMgr(ConnectionMgr):
    """
    C++ RouterInfoConnMgr (ConnectionMgr 상속) 대응.
    AcceptSocket 외 별도 로직 없음.
    """

    def __init__(self) -> None:
        super().__init__()

    def AcceptSocket(self) -> None:
        """C++: AcceptSocket()"""
        conn = RouterInfoConnection(self)
        if not self.Accept(conn):
            logger.debug("Router Info Socket Accept Error : %s",
                         self.GetObjErrMsg())
            return

        self.add(conn)                              # ConnectionMgr.add()
        logger.debug("Router Connection Gui(%s)", conn.get_peer_ip())


# =============================================================================
# RouterInfoConnection
# =============================================================================

class RouterInfoConnection(AsSocket):
    """
    C++ RouterInfoConnection (AsSocket 상속) 대응.

    AsSocket 가상 메서드 오버라이드:
      receive_packet()  ← C++ ReceivePacket()  (MsgId 기반 분기)
      close_socket()    ← C++ CloseSocket()
    """

    def __init__(self, conn_mgr: RouterInfoConnMgr) -> None:
        super().__init__()
        self._router_info_conn_mgr: RouterInfoConnMgr = conn_mgr
        self._router_info_list:     RouterInfoList    = RouterInfoList()

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """
        C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)
        RouterInfoConnection은 MsgId 기반 분기 (세션 타입 무관).
        """
        if packet.MsgId == AS_ROUTER_INFO_REQ:
            asyncio.ensure_future(
                self._router_info_req_process(packet.Msg))
        else:
            logger.debug("Unknown Msg Id : %d", packet.MsgId)

    def close_socket(self, errno_val: int) -> None:
        """C++: virtual CloseSocket(int Errno)"""
        logger.debug("Router Connection Broken(%s)", self.get_peer_ip())
        self._router_info_conn_mgr.remove(self)     # ConnectionMgr.remove()

    # =========================================================================
    # RouterInfoReqProcess
    # =========================================================================

    async def _router_info_req_process(self,
                                        req: AS_ROUTER_INFO_REQ_T) -> None:
        """C++: RouterInfoReqProcess(AS_ROUTER_INFO_REQ_T*)"""
        from ProcNaServer.AsciiServerWorld import AsciiServerWorld

        logger.debug("Receive Router Info Request : userid(%s), passwd(%s)",
                     req.userid, req.password)

        # equipNo 범위 검사
        if req.equipNo > MAX_EQUIP_NO:
            logger.error("Invalid Router Info Req(equipNo over 50) %s",
                         self.get_peer_ip())
            return

        # RouterInfo 조회
        self._router_info_list.clear()
        AsciiServerWorld.m_WorldPtr.GetRouterInfo(req, self._router_info_list)

        logger.debug("RouterInfo size %d", len(self._router_info_list))

        # 응답 구성 및 전송
        res = AS_ROUTER_INFO_RES_T()
        res.routerNo = len(self._router_info_list)
        for i, router_info in enumerate(self._router_info_list):
            if i >= len(res.routerInfos):
                break
            res.routerInfos[i] = router_info

        self._router_info_list.clear()

        payload = _pack(res)
        await self.SendPacket(AS_ROUTER_INFO_RES, payload, len(payload))


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''