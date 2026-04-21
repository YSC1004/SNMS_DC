"""
ExternalConnection.py
C++ ExternalConnection.h/.C → Python 변환

외부 시스템 MMC 요청 소켓 연결 처리.
  - MMCRequestConnection 상속
  - 세션 식별 (ReceiveMMCIdentReq): 권한 확인 → MMCRequestQueue 등록
  - MMC 요청 수신 → 큐 삽입 + ACK 전송
  - MMC 결과 전송 (SendMMCResult 오버라이드)
"""

import asyncio
import logging
from typing import Optional, TYPE_CHECKING

from ProcNaServer.MMCRequestConnection import MMCRequestConnection
from Common.CommTypeList import (
    AS_MMC_REQUEST_T, AS_MMC_REQUEST_OLD_T, AS_MMC_RESULT_T,
    AS_MMC_IDENT_REQ_T, AS_MMC_IDENT_RES_T, AS_MMC_ACK_T,
    AS_COMMAND_AUTHORITY_INFO_T,
)
from Common.CommType import (
    AS_MMC_REQ, AS_MMC_REQ_OLD, AS_MMC_IDENT_REQ,
    AS_MMC_IDENT_RES, AS_MMC_REQ_ACK, AS_MMC_RES,
)
from Common.AsUtil import AsUtil

# 필드 최대 길이 상수 (CommType 또는 CommTypeList에서 import)
try:
    from Common.CommType import (
        EQUIP_ID_LEN, MMC_CMD_LEN_EX, USER_ID_LEN, IP_ADDRESS_LEN,
    )
except ImportError:
    EQUIP_ID_LEN    = 64
    MMC_CMD_LEN_EX  = 512
    USER_ID_LEN     = 40
    IP_ADDRESS_LEN  = 20

from ProcNaServer.AsciiServerType import SESSION_TYPE_MMC

if TYPE_CHECKING:
    from ProcNaServer.ExternalConnMgr import ExternalConnMgr

logger = logging.getLogger(__name__)

# 큐 삽입 실패 최대 허용 횟수
MAX_FAULT_CNT = 200


class ExternalConnection(MMCRequestConnection):
    """
    C++ ExternalConnection (MMCRequestConnection 상속) 대응.

    AsSocket 가상 메서드 오버라이드:
      receive_packet()    ← C++ ReceivePacket()
      close_socket()      ← C++ CloseSocket()

    MMCRequestConnection 가상 메서드 오버라이드:
      SendMMCResult()     ← C++ SendMMCResult()
    """

    def __init__(self, conn_mgr: "ExternalConnMgr") -> None:
        super().__init__()
        self._ext_conn_mgr:            "ExternalConnMgr"          = conn_mgr
        self._ident_flag:              bool                        = False
        self._fault_cnt:               int                        = 0
        self._command_authority_info:  AS_COMMAND_AUTHORITY_INFO_T = AS_COMMAND_AUTHORITY_INFO_T()

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """
        C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)
        MsgId 기반 분기 (세션 타입 무관).
        """
        msg_id = packet.MsgId

        if msg_id == AS_MMC_REQ_OLD:
            asyncio.ensure_future(self._recv_mmc_req_old(packet.Msg))

        elif msg_id == AS_MMC_REQ:
            asyncio.ensure_future(self._recv_mmc_req(packet.Msg))

        elif msg_id == AS_MMC_IDENT_REQ:
            asyncio.ensure_future(self._recv_mmc_ident_req(packet.Msg))

        else:
            logger.debug("Unknown MsgId : %d", msg_id)
            logger.debug("so now disconnecting.........")
            asyncio.ensure_future(self._force_close())

    def close_socket(self, errno_val: int) -> None:
        """C++: virtual CloseSocket(int Errno)"""
        logger.debug("External connection close (%s,%s)",
                     self.GetSessionName(), self.get_peer_ip())
        self._ext_conn_mgr.remove(self)            # ConnectionMgr.remove()

    # =========================================================================
    # MMCRequestConnection 가상 메서드 오버라이드
    # =========================================================================

    async def SendMMCResult(self, result: AS_MMC_RESULT_T) -> bool:
        """C++: virtual SendMMCResult(AS_MMC_RESULT_T*) → AS_MMC_RES 패킷 전송."""
        payload = _pack(result)
        return await self.SendPacket(AS_MMC_RES, payload, len(payload))

    # =========================================================================
    # 세션 식별 (ReceiveMMCIdentReq)
    # =========================================================================

    async def _recv_mmc_ident_req(self,
                                   ident_req: AS_MMC_IDENT_REQ_T) -> None:
        """C++: ReceiveMMCIdentReq(AS_MMC_IDENT_REQ_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        if self._ident_flag:
            return

        ident_res = AS_MMC_IDENT_RES_T()

        result = MAINPTR().IdentMMCRequestSession(
            ident_req, self._command_authority_info)

        if result:
            self._session_status  = True
            ident_res.resultMode  = 1

            logger.debug(
                "External Session Ident Ok : %s(%s), "
                "priority(%d), logmode(%d), maxqueuesize(%d), ackmode(%d)",
                ident_req.name, self.get_peer_ip(),
                self._command_authority_info.Priority,
                self._command_authority_info.LogMode,
                self._command_authority_info.MaxCmdQueue,
                self._command_authority_info.AckMode,
            )

            # MMCRequestQueue 등록 (AsciiServerWorld)
            self._mmc_request_queue = MAINPTR().RegisterMMCReqConn(
                self, self._command_authority_info.MaxCmdQueue)
            if self._mmc_request_queue is None:
                logger.error("Error Get MMCRequest Queue")

            self.SetSessionName(ident_req.name)     # AsSocket.SetSessionName()

            # 최대 세션 수 초과 검사
            cur_cnt = self._ext_conn_mgr.GetCurSessionCnt(ident_req.name)
            max_cnt = self._command_authority_info.MaxSessionCnt

            if max_cnt > 0 and cur_cnt > max_cnt:
                self._session_status = False
                ident_res.resultMode = 0
                ident_res.result = (f"Exceed max session : max({max_cnt} ea)")
                logger.debug("### Exceed max session : ID[%s], max(%d ea)",
                             ident_req.name, max_cnt)
                logger.debug("External Session Close")

            if self._session_status:
                MAINPTR().SessionCfg(self, SESSION_TYPE_MMC)
        else:
            self._session_status = False
            ident_res.resultMode = 0
            ident_res.result     = "Unregistered ID"
            logger.debug("External Session Ident not ok : %s", ident_req.name)
            logger.debug("External Session Close")

        self._ident_flag = True

        payload = _pack(ident_res)
        if not await self.SendPacket(AS_MMC_IDENT_RES, payload, len(payload)):
            logger.info("Socket Broken : %s", self.get_peer_ip())
            await self._force_close()
            return

        if not self._session_status:
            await self._force_close()

    # =========================================================================
    # MMC 요청 수신
    # =========================================================================

    async def _recv_mmc_req_old(self,
                                 mmc_req_old: AS_MMC_REQUEST_OLD_T) -> None:
        """C++: ReceiveMMCReq(AS_MMC_REQUEST_OLD_T*) → 변환 후 처리."""
        new_req = AS_MMC_REQUEST_T()
        AsUtil.ConvertMMC_OldToNew(mmc_req_old, new_req)
        await self._recv_mmc_req(new_req)

    async def _recv_mmc_req(self, mmc_req: AS_MMC_REQUEST_T) -> None:
        """C++: ReceiveMMCReq(AS_MMC_REQUEST_T*)"""
        if not self._session_status:
            logger.debug("Illegal Command of Not Ident Connection")
            return

        # 권한 정보 적용
        mmc_req.priority = self._command_authority_info.Priority
        mmc_req.logMode  = self._command_authority_info.LogMode
        mmc_req.display  = self.get_peer_ip()       # AsSocket.get_peer_ip()

        self._check_req(mmc_req)

        if self._mmc_request_queue.InsertMMCRequest(mmc_req):
            self._fault_cnt = 0

            # ACK 모드: 성공 ACK 전송
            if self._command_authority_info.AckMode:
                ack = AS_MMC_ACK_T()
                ack.id         = mmc_req.id
                ack.resultMode = 1
                payload = _pack(ack)
                await self.SendPacket(AS_MMC_REQ_ACK, payload, len(payload))
                logger.debug("Send Cmd Req Ack(extid:%d)", ack.id)
        else:
            self._fault_cnt += 1

            # ACK 모드: 실패 ACK 전송
            if self._command_authority_info.AckMode:
                ack = AS_MMC_ACK_T()
                ack.id         = mmc_req.id
                ack.resultMode = 0
                payload = _pack(ack)
                await self.SendPacket(AS_MMC_REQ_ACK, payload, len(payload))
                logger.debug("Send Cmd Req Ack(extid:%d)", ack.id)

            # 실패 횟수 초과 시 강제 종료
            if self._fault_cnt > MAX_FAULT_CNT:
                logger.debug("Insert Queue Fail Count Over(%s)",
                             self.GetSessionName())
                await self._force_close()

    # =========================================================================
    # CheckReq
    # =========================================================================

    def _check_req(self, mmc_req: AS_MMC_REQUEST_T) -> bool:
        """
        C++: CheckReq(AS_MMC_REQUEST_T*)
        각 필드 최대 길이 초과 시 잘라냄.
        """
        if len(mmc_req.ne) > EQUIP_ID_LEN - 1:
            mmc_req.ne = mmc_req.ne[:EQUIP_ID_LEN - 1]
        if len(mmc_req.mmc) > MMC_CMD_LEN_EX - 1:
            mmc_req.mmc = mmc_req.mmc[:MMC_CMD_LEN_EX - 1]
        if len(mmc_req.userid) > USER_ID_LEN - 1:
            mmc_req.userid = mmc_req.userid[:USER_ID_LEN - 1]
        if len(mmc_req.display) > IP_ADDRESS_LEN - 1:
            mmc_req.display = mmc_req.display[:IP_ADDRESS_LEN - 1]
        return True

    # =========================================================================
    # 강제 종료 헬퍼
    # =========================================================================

    async def _force_close(self) -> None:
        """C++: Close(); m_ExtConnMgr->Remove(this)"""
        self._close()                               # AsSocket._close()
        self._ext_conn_mgr.remove(self)             # ConnectionMgr.remove()


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''