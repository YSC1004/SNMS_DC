# -*- coding: utf-8 -*-
"""
DBGwBaseSocket.h / DBGwBaseSocket.C  →  DBGwBaseSocket.py
Python 3.11.10 변환

변환 설계:
  DBGwBaseSocket      → DBGwBaseSocket      (AsSocket 상속)
  AsSocketDisableGuard → AsSocketDisableGuard (컨텍스트 매니저)

C++ → Python 주요 변환 포인트:
  htonl/htons/ntohl/ntohs  → socket.htonl/htons/ntohl/ntohs
  PACKET_T*& Packet 캐스팅  → PacketT + msg_id 분기, dataclass 직접 조작
  HtonStruct/NtohStruct     → hton_struct/ntoh_struct (override)
  AsSocketDisableGuard      → __enter__/__exit__ 컨텍스트 매니저
  DBGwBaseSocket_cxxFun()   → 빌드 전용 함수이므로 변환 제외

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
import socket as _socket
from typing import TYPE_CHECKING

from Common.AsSocket import AsSocket
from Common.CommType import PacketT
from libDBGw.libDBGwBase.DBGwType import (
    DB_CONN_REQ, DB_CONN_RES,
    DB_CLOSE_REQ,
    DB_QUERY_REQ, DB_QUERY_RES,
    DB_BULK_QUERY_DATA, DB_RS_QUERY_DATA,
    DB_RS_MOVE_NEXT_REQ, DB_RS_CLOSE_REQ,
    DB_COMMIT_RES, DB_ROLLBACK_RES,
    DB_QUERY_LONG_UPDATE_REQ, DB_QUERY_LONG_UPDATE_RES,
    DbConnReqT, DbConnResT, DbCloseReqT,
    DbQueryReqT, DbQueryResT,
    DbBulkQueryDataT, DbRsQueryDataT,
    DbRsMoveNextReqT, DbRsCloseReqT,
    DbCommitResT, DbRollbackResT,
    DbQueryLongUpdateReqT, DbQueryLongUpdateResT,
)
from Common.CommType import AS_SEGFLAG

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# AsSocketDisableGuard
# ─────────────────────────────────────────────────────────────────────────────
class AsSocketDisableGuard:
    """
    C++ AsSocketDisableGuard 대응 컨텍스트 매니저.
    진입 시 소켓 Disable, 종료 시에도 Disable 유지 (C++ 원본과 동일).

    사용 예:
        with AsSocketDisableGuard(sock):
            ...  # 소켓이 Disable 상태로 유지됨
    """

    def __init__(self, sock: AsSocket) -> None:
        self._socket = sock

    def __enter__(self) -> 'AsSocketDisableGuard':
        self._socket.disable()
        return self

    def __exit__(self, *_) -> None:
        # C++ 소멸자: Enable() 은 주석 처리, Disable() 만 호출
        self._socket.disable()


# ─────────────────────────────────────────────────────────────────────────────
# DBGwBaseSocket
# ─────────────────────────────────────────────────────────────────────────────
class DBGwBaseSocket(AsSocket):
    """
    C++ DBGwBaseSocket 대응.
    DB Gateway 전용 바이트 오더 변환(hton/ntoh)을 제공하는 AsSocket 서브클래스.
    """

    def __init__(self) -> None:
        super().__init__()

    # ── 바이트 오더 변환 헬퍼 ────────────────
    @staticmethod
    def _htonl(v: int) -> int: return _socket.htonl(v & 0xFFFFFFFF)
    @staticmethod
    def _htons(v: int) -> int: return _socket.htons(v & 0xFFFF)
    @staticmethod
    def _ntohl(v: int) -> int: return _socket.ntohl(v & 0xFFFFFFFF)
    @staticmethod
    def _ntohs(v: int) -> int: return _socket.ntohs(v & 0xFFFF)

    # ── HtonStruct ───────────────────────────
    def hton_struct(self, packet: PacketT) -> None:
        """
        C++ HtonStruct(PACKET_T*&) 대응.
        송신 전 host → network 바이트 오더 변환.
        """
        h4, h2 = self._htonl, self._htons
        mid = packet.msg_id

        if mid == DB_CONN_REQ:
            packet.msg.proc_pid = h4(packet.msg.proc_pid)

        elif mid == DB_CONN_RES:
            packet.msg.result = h2(packet.msg.result)

        elif mid == DB_CLOSE_REQ:
            packet.msg.req = h4(packet.msg.req)

        elif mid == DB_QUERY_REQ:
            m = packet.msg
            m.query_id       = h4(m.query_id)
            m.query_type     = h4(m.query_type)
            m.query_req_type = h4(m.query_req_type)
            m.commit         = h4(m.commit)
            m.seg_flag       = AS_SEGFLAG(h4(int(m.seg_flag)))

        elif mid == DB_QUERY_RES:
            m = packet.msg
            m.query_id  = h4(m.query_id)
            m.col_cnt   = h4(m.col_cnt)
            m.row_cnt   = h4(m.row_cnt)
            m.data_size = h4(m.data_size)
            m.result    = h2(m.result)

        elif mid == DB_BULK_QUERY_DATA:
            m = packet.msg
            m.query_id = h4(m.query_id)
            m.seg_flag = AS_SEGFLAG(h4(int(m.seg_flag)))

        elif mid == DB_RS_QUERY_DATA:
            m = packet.msg
            m.query_id = h4(m.query_id)
            m.cur_row  = h4(m.cur_row)
            m.seg_flag = AS_SEGFLAG(h4(int(m.seg_flag)))
            m.size     = h4(m.size)

        elif mid == DB_RS_MOVE_NEXT_REQ:
            m = packet.msg
            m.query_id = h4(m.query_id)
            m.reserved = h4(m.reserved)

        elif mid == DB_RS_CLOSE_REQ:
            m = packet.msg
            m.query_id = h4(m.query_id)
            m.reserved = h4(m.reserved)

        elif mid == DB_COMMIT_RES:
            packet.msg.result = h2(packet.msg.result)

        elif mid == DB_ROLLBACK_RES:
            packet.msg.result = h2(packet.msg.result)

        elif mid == DB_QUERY_LONG_UPDATE_REQ:
            m = packet.msg
            m.seg_flag  = AS_SEGFLAG(h4(int(m.seg_flag)))
            m.data_size = h4(m.data_size)

        elif mid == DB_QUERY_LONG_UPDATE_RES:
            packet.msg.result = h2(packet.msg.result)

        else:
            super().hton_struct(packet)

    # ── NtohStruct ───────────────────────────
    def ntoh_struct(self, packet: PacketT) -> None:
        """
        C++ NtohStruct(PACKET_T*&) 대응.
        수신 후 network → host 바이트 오더 변환.
        """
        n4, n2 = self._ntohl, self._ntohs
        mid = packet.msg_id

        if mid == DB_CONN_REQ:
            packet.msg.proc_pid = n4(packet.msg.proc_pid)

        elif mid == DB_CONN_RES:
            packet.msg.result = n2(packet.msg.result)

        elif mid == DB_CLOSE_REQ:
            packet.msg.req = n4(packet.msg.req)

        elif mid == DB_QUERY_REQ:
            m = packet.msg
            m.query_id       = n4(m.query_id)
            m.query_type     = n4(m.query_type)
            m.query_req_type = n4(m.query_req_type)
            m.commit         = n4(m.commit)
            m.seg_flag       = AS_SEGFLAG(n4(int(m.seg_flag)))

        elif mid == DB_QUERY_RES:
            m = packet.msg
            m.query_id  = n4(m.query_id)
            m.col_cnt   = n4(m.col_cnt)
            m.row_cnt   = n4(m.row_cnt)
            m.data_size = n4(m.data_size)
            m.result    = n2(m.result)

        elif mid == DB_BULK_QUERY_DATA:
            m = packet.msg
            m.query_id = n4(m.query_id)
            m.seg_flag = AS_SEGFLAG(n4(int(m.seg_flag)))

        elif mid == DB_RS_QUERY_DATA:
            m = packet.msg
            m.query_id = n4(m.query_id)
            m.cur_row  = n4(m.cur_row)
            m.seg_flag = AS_SEGFLAG(n4(int(m.seg_flag)))
            m.size     = n4(m.size)

        elif mid == DB_RS_MOVE_NEXT_REQ:
            m = packet.msg
            m.query_id = n4(m.query_id)
            m.reserved = n4(m.reserved)

        elif mid == DB_RS_CLOSE_REQ:
            m = packet.msg
            m.query_id = n4(m.query_id)
            m.reserved = n4(m.reserved)

        elif mid == DB_COMMIT_RES:
            packet.msg.result = n2(packet.msg.result)

        elif mid == DB_ROLLBACK_RES:
            packet.msg.result = n2(packet.msg.result)

        elif mid == DB_QUERY_LONG_UPDATE_REQ:
            m = packet.msg
            m.seg_flag  = AS_SEGFLAG(n4(int(m.seg_flag)))
            m.data_size = n4(m.data_size)

        elif mid == DB_QUERY_LONG_UPDATE_RES:
            packet.msg.result = n2(packet.msg.result)

        else:
            super().ntoh_struct(packet)