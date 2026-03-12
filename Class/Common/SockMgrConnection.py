# -*- coding: utf-8 -*-
"""
SockMgrConnection.h / SockMgrConnection.C  →  SockMgrConnection.py
Python 3.11.10 변환

변환 설계:
  SockMgrConnection → SockMgrConnection  (AsSocket 상속)

C++ → Python 주요 변환 포인트:
  PACKET_T* / Msg 캐스팅               → PacketT dataclass + 타입별 분기
  pthread_mutex_lock/unlock             → AsWorld.m_connection_mgr_vector_lock
  memset / memcpy                       → dataclass 초기화 / 직접 대입
  frSockFdManager::ShutDownSock()       → FrSockFdManager.shut_down_sock()
  frSockFdManager::SocketCheck()        → FrSockFdManager.socket_check()
  frSockFdManager::GetSockInfos()       → FrSockFdManager.get_sock_infos()
  FR_SOCKET_INFO_T                      → SocketInfo  (fr_sock_fd_manager)
  FR_SOCKET_CHECK_REQ_T                 → FrSocketCheckReqT (로컬 dataclass)
  AS_SOCKET_INFO_LIST_T                 → AsSocketInfoListT  (로컬 dataclass)
  분절 전송 (INFO_NO_SEG/START/ING/END) → 그대로 유지

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
from dataclasses import dataclass, field as dc_field
from typing import TYPE_CHECKING

# ── Event 레이어 ──────────────────────────────────────────────────────────────
from Event.fr_sock_fd_manager import FrSockFdManager, SocketInfo
from Event.fr_object import get_g_err_msg

# ── Common 레이어 ─────────────────────────────────────────────────────────────
from Common.AsSocket import AsSocket
from Common.AsWorld import AsWorld
from Common.CommType import (
    PacketT,
    AS_SOCKET_STATUS_REQ_T as AsSocketStatusReqT,
    AS_GUI_INIT_INFO_T,
    AS_SOCKET_STATUS_REQ, FR_SOCKET_STATUS_REQ,
    FR_SOCKET_SHUTDOWN_REQ, FR_SOCKET_CHECK_REQ,
    AS_SOCKET_STATUS_RES,  FR_SOCKET_STATUS_RES,
    FR_SOCKET_SHUTDOWN_RES, FR_SOCKET_CHECK_RES,
    INIT_INFO_START, INIT_INFO_END,
    INFO_NO_SEG, INFO_START, INFO_ING, INFO_END,
    MAX_SOCKET_INFO_CNT,
)

if TYPE_CHECKING:
    from Common.SockMgrConnMgr import SockMgrConnMgr

logger = logging.getLogger(__name__)


# ── 로컬 dataclass (CommType 에 미정의) ──────────────────────────────────────

@dataclass
class FrSocketCheckReqT:
    """C++ FR_SOCKET_CHECK_REQ_T 대응."""
    info:            SocketInfo = dc_field(default_factory=SocketInfo)
    check_sec:       int        = 0
    check_micro_sec: int        = 0

    @classmethod
    def from_bytes(cls, data: bytes) -> 'FrSocketCheckReqT':
        """TODO: struct.unpack 으로 실제 바이너리 파싱 구현."""
        return cls()


@dataclass
class AsSocketInfoListT:
    """C++ AS_SOCKET_INFO_LIST_T 대응."""
    group_name: str  = ""
    status:     int  = 0
    size:       int  = 0
    info_list:  list = dc_field(default_factory=list)

    def to_bytes(self) -> bytes:
        """TODO: struct.pack 으로 실제 바이너리 직렬화 구현."""
        return b""


# ── SockMgrConnection ─────────────────────────────────────────────────────────

class SockMgrConnection(AsSocket):
    """
    C++ SockMgrConnection 대응.
    SockMgrConnMgr 에 소속된 GUI 소켓 연결.
    소켓 상태 조회 / 셧다운 / 체크 요청을 처리한다.
    """

    def __init__(self, conn_mgr: 'SockMgrConnMgr') -> None:
        super().__init__()
        self._sock_mgr_conn_mgr = conn_mgr

    # ── AsSocket 콜백 ─────────────────────────

    def receive_packet(self, packet: PacketT, session_identify: int) -> None:
        """C++ ReceivePacket() 대응."""
        self.gui_req_process(packet)

    def close_socket(self, errno_val: int) -> None:
        """C++ CloseSocket() 대응. 연결 해제 시 ConnMgr 에서 제거."""
        logger.debug(
            "SockMgr Connection Broken(%s,%s)",
            self.get_peer_ip(), self.get_session_name(),
        )
        self._sock_mgr_conn_mgr.remove(self)

    # ── GUI 요청 처리 ─────────────────────────

    def gui_req_process(self, packet: PacketT) -> None:
        """C++ GuiReqProcess() 대응. MsgId 기준 분기 처리."""
        logger.debug("Recv Request SockMgr GUI : %d", packet.msg_id)

        if packet.msg_id in (AS_SOCKET_STATUS_REQ, FR_SOCKET_STATUS_REQ):
            req = AsSocketStatusReqT()   # TODO: from_bytes(packet.msg) 구현 후 교체
            self._recv_socket_status_req(packet.msg_id, req)

        elif packet.msg_id == FR_SOCKET_SHUTDOWN_REQ:
            info = SocketInfo()          # TODO: from_bytes(packet.msg) 구현 후 교체
            if FrSockFdManager.shut_down_sock(info):
                self.send_ack(FR_SOCKET_SHUTDOWN_RES, 1)
            else:
                self.send_ack(FR_SOCKET_SHUTDOWN_RES, 1, 0, get_g_err_msg())

        elif packet.msg_id == FR_SOCKET_CHECK_REQ:
            req = FrSocketCheckReqT.from_bytes(packet.msg)
            if FrSockFdManager.socket_check(req.info, req.check_sec, req.check_micro_sec):
                self.send_ack(FR_SOCKET_CHECK_RES, 1)
            else:
                self.send_ack(FR_SOCKET_CHECK_RES, 1, 0, get_g_err_msg())

        else:
            logger.debug("Unknown SockMgr Gui Request : %d", packet.msg_id)

    # ── 소켓 상태 조회 ────────────────────────

    def _recv_socket_status_req(
        self, req_type: int, status_req: AsSocketStatusReqT
    ) -> None:
        """C++ RecvSocketStatusReq() 대응."""
        if req_type == AS_SOCKET_STATUS_REQ:
            info_vector: list[SocketInfo] = []
            with AsWorld.m_connection_mgr_vector_lock:
                mgr_vector = AsWorld.get_connection_mgr_vector()
                if mgr_vector:
                    for mgr in mgr_vector:
                        mgr.get_con_sock_infos(
                            info_vector,
                            bool(status_req.IsWriterableCheck),
                            status_req.CheckSec,
                            status_req.CheckMiscroSec,
                        )
                self._send_socket_status_info(AS_SOCKET_STATUS_RES, info_vector)

        elif req_type == FR_SOCKET_STATUS_REQ:
            info_vector = FrSockFdManager.get_sock_infos(
                bool(status_req.IsWriterableCheck),
                status_req.CheckSec,
                status_req.CheckMiscroSec,
            )
            self._send_socket_status_info(FR_SOCKET_STATUS_RES, info_vector)

        else:
            logger.error("Unknown Socket Status ReqType : %d", req_type)

    # ── 소켓 정보 분절 전송 ───────────────────

    def _send_socket_status_info(
        self,
        res_type:   int,
        info_vector: list[SocketInfo],
        group_name: str = "",
    ) -> bool:
        """
        C++ SendSocketStatusInfo() 대응.
        MAX_SOCKET_INFO_CNT 기준으로 분절(segmentation) 전송.
        """
        init_info = AS_GUI_INIT_INFO_T(Count=len(info_vector))
        self.send_packet(INIT_INFO_START, init_info)

        info_list = AsSocketInfoListT()
        if group_name:
            info_list.group_name = group_name

        total = len(info_vector)

        if total <= MAX_SOCKET_INFO_CNT:
            info_list.status    = INFO_NO_SEG
            info_list.info_list = list(info_vector)
            info_list.size      = total
            self.send_packet(res_type, info_list.to_bytes())

        else:
            info_list.status = INFO_START
            buf: list[SocketInfo] = []

            for info in info_vector:
                buf.append(info)
                if len(buf) == MAX_SOCKET_INFO_CNT:
                    info_list.info_list = buf
                    info_list.size      = len(buf)
                    if not self.send_packet(res_type, info_list.to_bytes()):
                        return False
                    buf              = []
                    info_list.status = INFO_ING

            # 마지막 잔여분
            info_list.info_list = buf
            info_list.size      = len(buf)
            info_list.status    = INFO_END
            self.send_packet(res_type, info_list.to_bytes())

        return self.send_packet(INIT_INFO_END, init_info)