"""
AsSocket.py - C++ AsSocket.h/.C 변환

"""

from __future__ import annotations

import errno
import logging
import socket
import struct
import time
from typing import TYPE_CHECKING, Any

from Event.fr_socket_sensor import FrSocketSensor   # ← 실제 구현체 사용

from Common.CommType import (
    NOT_ASSIGN, SESSION_REPORTING, CMD_ALIVE_ACK,
    CMD_ALIVE_RECEIVE, CMD_ALIVE_SEND,
    CMD_LOG_STATUS_CHANGE, AS_PARSED_DATA,
    AS_LOG_INFO, PORT_STATUS_INFO, PROCESS_INFO, PROCESS_INFO_LIST,
    ROUTER_PORT_INFO, CONNECTOR_DATA, ASCII_ERROR_MSG,
    CMD_PARSING_RULE_CHANGE, PROC_CONTROL, SESSION_CONTROL,
    DATAHANDLER_MODIFY, AS_DATA_HANDLER_INFO, TAIL_LOG_DATA_REQ,
    TAIL_LOG_DATA_RES, TAIL_LOG_DATA, INIT_INFO_START,
    MANAGER_MODIFY, AS_MANAGER_INFO, CONNECTOR_MODIFY, AS_CONNECTOR_INFO,
    CONNECTION_MODIFY, AS_CONNECTION_INFO, CONNECTION_LIST_MODIFY,
    AS_CONNECTION_INFO_LIST, COMMAND_AUTHORITY_MODIFY,
    AS_COMMAND_AUTHORITY_INFO, AS_PROCESS_INFO,
    CMD_PARSING_RULE_DOWN_ACK, CMD_MAPPING_RULE_DOWN_ACK,
    CMD_COMMAND_RULE_DOWN_ACK, CMD_SCHEDULER_RULE_DOWN_ACK,
    CONNECTOR_MODIFY_ACK, MANAGER_MODIFY_ACK, CONNECTION_MODIFY_ACK,
    DATAHANDLER_MODIFY_ACK, CONNECTION_LIST_MODIFY_ACK,
    COMMAND_AUTHORITY_MODIFY_ACK, SUB_PROC_MODIFY_ACK,
    CMD_PROC_INIT, CMD_PARSING_RULE_DOWN, CMD_MAPPING_RULE_DOWN,
    CMD_COMMAND_RULE_DOWN, CMD_SCHEDULER_RULE_DOWN,
    PROC_INIT_END, CMD_PROC_TERMINATE, INIT_INFO_END,
    AS_SOCKET_STATUS_REQ, FR_SOCKET_STATUS_REQ,
    AS_SOCKET_STATUS_RES, FR_SOCKET_STATUS_RES,
    FR_SOCKET_SHUTDOWN_REQ, FR_SOCKET_SHUTDOWN_RES,
    FR_SOCKET_CHECK_REQ, FR_SOCKET_CHECK_RES,
    AS_DB_SYNC_KIND, AS_DB_SYNC_INFO_LIST,
    AS_DATA_HANDLER_INIT, AS_DATA_ROUTING_INIT,
    AS_SYSTEM_INFO, AS_SESSION_CFG,
    SUB_PROC_MODIFY, AS_SUB_PROC_INFO,
    MMC_LOG, CONNECTOR_PORT_INFO_REQ, CMD_OPEN_PORT, CMD_OPEN_PORT_ACK,
    NETFINDER_REV,
    AsAsciiAck, AsCmdOpenPort, AsCmdLogControl, AsSessionInfo,
    AsLogStatus, AsPortStatusInfo, AsProcessStatus, AsProcessStatusList,
    AsRouterPortInfo, AsParsedData, AsConnectorData, AsAsciiErrorMsg,
    AsRuleChangeInfo, AsProcControl, AsSessionControl,
    AsDataHandlerInfo, AsLogTailDataReq, AsLogTailDataRes,
    AsGuiInitInfo, AsManagerInfo, AsConnectorInfo, AsConnectionInfo,
    AsConnectionInfoList, AsCommandAuthorityInfo, AsDataHandlerInit,
    AsDataRoutingInit, AsSystemInfoData, AsSessionCfg, AsSubProcInfo,
)
from Common.AsciiMmcType import (
    MAX_MSG, MAX_PACKET,
    AS_MMC_IDENT_RES, AS_MMC_FLOW_CONTROL,
    AS_MMC_REQ_OLD, AS_MMC_REQ, AS_MMC_REQ_ACK, AS_MMC_RES,
    AS_MMC_IDENT_REQ, AS_ROUTER_INFO_REQ, AS_ROUTER_INFO_RES,
    AS_ROUTER_CONFIG,
    MMC_GEN_REQ, MMC_GEN_RES, MMC_RESPONSE_DATA_REQ, MMC_RESPONSE_DATA,
    CMD_MMC_PUBLISH_REQ, CMD_MMC_PUBLISH_RES,
    PacketT, AsMmcIdentRes, AsMmcFlowControl,
    AsMmcRequestOld, AsMmcRequest, AsMmcAck, AsMmcResult,
    AsMmcGenResult, AsMmcPublish,
    AsRouterInfoReq, AsRouterInfoRes, AsRouterConfig,
)

if TYPE_CHECKING:
    from Common.AliveCheckTimer import AliveCheckTimer

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 패킷 직렬화/역직렬화 헬퍼
# PACKET_T 헤더: MsgId(4) + Length(4) = 8 bytes
# ──────────────────────────────────────────────
_HDR_FMT  = "!II"          # network byte order: uint32 MsgId, uint32 Length
_HDR_SIZE = struct.calcsize(_HDR_FMT)   # == 8


def _pack_packet(packet: PacketT) -> bytes:
    """PacketT → 전송용 bytes (헤더 + 페이로드)."""
    payload = packet.msg.encode() if isinstance(packet.msg, str) else packet.msg
    hdr = struct.pack(_HDR_FMT, packet.msg_id, len(payload))
    return hdr + payload


def _unpack_header(data: bytes) -> tuple[int, int]:
    """8바이트 헤더 → (msg_id, length)."""
    return struct.unpack(_HDR_FMT, data)


# ──────────────────────────────────────────────
# hton / ntoh 헬퍼 (int 필드 바이트 변환)
# ──────────────────────────────────────────────
def _htonl(v: int) -> int: return socket.htonl(v & 0xFFFFFFFF)
def _ntohl(v: int) -> int: return socket.ntohl(v & 0xFFFFFFFF)
def _htons(v: int) -> int: return socket.htons(v & 0xFFFF)
def _ntohs(v: int) -> int: return socket.ntohs(v & 0xFFFF)


# ──────────────────────────────────────────────
# AsSocket
# ──────────────────────────────────────────────
class AsSocket(FrSocketSensor):
    """
    C++ AsSocket 대응.
    PACKET_T 기반 송수신, Alive Check, Session Identify, hton/ntoh 처리를 담당합니다.
    """

    def __init__(self) -> None:
        super().__init__()   # FrSocketSensor.__init__() 호출
        self._session_identify: int = NOT_ASSIGN
        self._alive_check_timer: AliveCheckTimer | None = None
        self._fail_count:     int = 0
        self._fail_count_max: int = 0
        self._re_read_check_flag: bool = False

    def __del__(self) -> None:
        if self._alive_check_timer:
            self._alive_check_timer.cancel_timer()

    # ── 패킷 송신 ─────────────────────────────
    def packet_send(self, packet: PacketT) -> bool:
        """C++ PacketSend 대응 — hton 변환 후 전송."""
        payload = packet.msg.encode() if isinstance(packet.msg, str) else packet.msg
        length  = _HDR_SIZE + len(payload)
        hdr     = struct.pack(_HDR_FMT, socket.htonl(packet.msg_id),
                              socket.htonl(len(payload)))
        ret = self.write(hdr + payload[:len(payload)])
        if ret < 1:
            if self.is_block_mode():
                return False
            else:
                if self._get_errno() == errno.EAGAIN:
                    logger.debug("Session is block(%s)(%d)",
                                 self.get_peer_ip(), packet.msg_id)
                    return True
                return False
        return True

    # ── 패킷 수신 ─────────────────────────────
    def packet_recv(self) -> PacketT | None:
        """
        C++ PacketRecv 대응.
        성공 시 PacketT 반환, 오류 시 None 반환.
        """
        # 헤더 수신
        hdr_data = self._recv_exact(_HDR_SIZE)
        if hdr_data is None:
            return None

        msg_id, length = struct.unpack(_HDR_FMT, hdr_data)
        msg_id  = socket.ntohl(msg_id)
        length  = socket.ntohl(length)

        if length == 0:
            return PacketT(msg_id=msg_id, length=0, msg="")

        if length > MAX_MSG:
            logger.error("length(%d) is over than MAX_MSG(4K)", length)
            return None

        # 페이로드 수신
        payload = self._recv_exact(length)
        if payload is None:
            return None

        return PacketT(msg_id=msg_id, length=length, msg=payload)

    def _recv_exact(self, size: int) -> bytes | None:
        """정확히 size 바이트를 수신. 실패 시 None 반환."""
        buf = b""
        re_read_cnt = 0
        while len(buf) < size:
            try:
                chunk = self.read(size - len(buf))
            except OSError as e:
                if e.errno == errno.EINTR:
                    continue
                logger.debug("recv error: %s", e)
                return None

            if not chunk:
                if self._re_read_check_flag and re_read_cnt < 4:
                    time.sleep(0.07)
                    re_read_cnt += 1
                    continue
                return None
            buf += chunk
        return buf

    # ── 세션 식별 ─────────────────────────────
    def _session_identify_packet(self, packet: PacketT) -> None:
        """C++ SessionIdentify(PACKET_T*) 대응."""
        raw = packet.msg if isinstance(packet.msg, bytes) else packet.msg.encode()
        # AS_SESSION_INFO_T: SessionType(4) + Name(100)
        if len(raw) >= 4:
            session_type = socket.ntohl(struct.unpack("!I", raw[:4])[0])
            name = raw[4:104].rstrip(b"\x00").decode(errors="replace")
            self._session_identify = session_type
            self.set_object_name(name)

    def set_session_identify(self, session_type: int, name: str = "",
                              check_interval: int = 100,
                              auto_ack_flag: bool = True) -> None:
        """C++ SetSessionIdentify 대응."""
        from Common.AliveCheckTimer import AliveCheckTimer
        self._session_identify = session_type
        self.set_object_name(name)

        # SESSION_REPORTING 패킷 전송
        session_info = AsSessionInfo(session_type=session_type, name=name)
        payload = struct.pack("!I", session_type) + name.encode().ljust(100, b"\x00")
        self.send_packet(SESSION_REPORTING, payload, len(payload))

        if auto_ack_flag:
            if self._alive_check_timer:
                self._alive_check_timer.cancel_timer()
            self._alive_check_timer = AliveCheckTimer(
                check_interval, CMD_ALIVE_SEND, self)

    # ── Alive Check ───────────────────────────
    def start_alive_check(self, interval: int, max_fail_count: int) -> bool:
        from Common.AliveCheckTimer import AliveCheckTimer
        if self._session_identify == NOT_ASSIGN:
            logger.debug("Not yet Session Identify")
            return False
        self._fail_count_max = max_fail_count
        if self._alive_check_timer:
            self._alive_check_timer.cancel_timer()
        self._alive_check_timer = AliveCheckTimer(interval, CMD_ALIVE_RECEIVE, self)
        return True

    def stop_alive_check(self) -> None:
        if self._alive_check_timer is None:
            return
        self._alive_check_timer.cancel_timer()
        self._alive_check_timer = None

    def alive_check_time(self) -> None:
        """C++ AliveCheckTime 대응 — CMD_ALIVE_RECEIVE 모드."""
        self._fail_count += 1
        if self._fail_count > self._fail_count_max:
            logger.debug("AliveCheckTimeOut: %s(%d)",
                         self.get_session_name(), self._fail_count)
            self.alive_check_fail(self._fail_count)

    def alive_check_send_time(self) -> None:
        """C++ AliveCheckSendTime 대응 — CMD_ALIVE_SEND 모드."""
        pkt = PacketT(msg_id=CMD_ALIVE_ACK, length=0, msg="")
        if not self.packet_send(pkt):
            self.socket_broken(self._get_errno())
        logger.debug("AliveCheckPacketSend(%s)", self.get_session_name())

    # ── 수신 메시지 처리 ─────────────────────
    def receive_message(self) -> None:
        """C++ ReceiveMessage 대응 — 이벤트 루프에서 호출."""
        packet = self.packet_recv()
        if packet is None:
            self.socket_broken(self._get_errno())
            return

        mid = packet.msg_id
        if mid == SESSION_REPORTING:
            if self._session_identify != NOT_ASSIGN:
                logger.error("Already Session Identify")
            else:
                self._session_identify_packet(packet)
                self.on_session_identify(self._session_identify,
                                         self.get_object_name())

        elif mid == CMD_ALIVE_ACK:
            logger.debug("Alive Ack Receive: %s", self.get_session_name())
            self._fail_count = 0

        else:
            self.receive_packet(packet, self._session_identify)

    # ── 패킷 전송 퍼블릭 API ──────────────────
    def send_packet(self, msg_id: int,
                    result: bytes | None = None, length: int = 0) -> bool:
        payload = result[:length] if result else b""
        pkt = PacketT(msg_id=msg_id, length=len(payload),
                      msg=payload.decode(errors="replace"))
        return self.packet_send(pkt)

    def send_nonblock_packet(self, msg_id: int,
                             result: bytes | None = None, length: int = 0) -> bool:
        if not self.set_block_mode(False):
            logger.error("SetBlockMode(False) Error")
            return False
        ok = self.send_packet(msg_id, result, length)
        if not self.set_block_mode(True):
            logger.error("SetBlockMode(True) Error")
            return False
        return ok

    def send_packet_obj(self, packet: PacketT) -> bool:
        return self.packet_send(packet)

    def send_nonblock_packet_obj(self, packet: PacketT) -> bool:
        if not self.set_block_mode(False):
            return False
        ok = self.packet_send(packet)
        if not self.set_block_mode(True):
            return False
        return ok

    def send_and_wait_packet(self, msg_id: int, result: bytes,
                              length: int, wait_msg_id: int,
                              out_buf: bytearray) -> int:
        if self.send_packet(msg_id, result, length):
            return self.wait_packet(wait_msg_id, out_buf)
        return -1

    def wait_packet(self, wait_msg_id: int, out_buf: bytearray) -> int:
        packet = self.packet_recv()
        if packet and packet.msg_id == wait_msg_id:
            payload = packet.msg if isinstance(packet.msg, bytes) \
                      else packet.msg.encode()
            out_buf[:len(payload)] = payload
            return 1
        logger.error("no wait msgid")
        return -1

    # ── ACK 송수신 ────────────────────────────
    def send_ack(self, msg_id: int, id_: int,
                 result_mode: int = 1, result_msg: str | None = None) -> bool:
        ack = AsAsciiAck(id=id_, result_mode=result_mode,
                         result=result_msg or "")
        payload = struct.pack("!II", id_, result_mode)
        res_bytes = (result_msg or "").encode().ljust(MAX_MSG - 8, b"\x00")
        return self.send_packet(msg_id, payload + res_bytes,
                                len(payload) + len(res_bytes))

    def recv_ack(self, packet: PacketT) -> AsAsciiAck:
        raw = packet.msg if isinstance(packet.msg, bytes) \
              else packet.msg.encode()
        if len(raw) >= 8:
            id_, result_mode = struct.unpack("!II", raw[:8])
            result = raw[8:].rstrip(b"\x00").decode(errors="replace")
            return AsAsciiAck(id=id_, result_mode=result_mode, result=result)
        return AsAsciiAck()

    # ── 로그 상태 변경 전송 ───────────────────
    def send_cmd_log_status_change(self, log_ctl: AsCmdLogControl) -> bool:
        payload = struct.pack("!III",
                              log_ctl.id, log_ctl.process_type, int(log_ctl.type))
        payload += log_ctl.manager_id.encode().ljust(40, b"\x00")
        payload += log_ctl.process_id.encode().ljust(80, b"\x00")
        payload += log_ctl.package.encode().ljust(128, b"\x00")
        payload += log_ctl.feature.encode().ljust(128, b"\x00")
        payload += struct.pack("!I", log_ctl.level)
        return self.send_packet(CMD_LOG_STATUS_CHANGE, payload, len(payload))

    # ── 세션명 ────────────────────────────────
    def set_session_name(self, name: str) -> None:
        self.set_object_name(name)

    def get_session_name(self) -> str:
        return self.get_object_name()

    def get_session_type(self) -> int:
        return self._session_identify

    def set_re_read_check(self, flag: bool) -> None:
        self._re_read_check_flag = flag

    # ── 소켓 오류 처리 ────────────────────────
    def socket_broken(self, err: int) -> None:
        self.close()
        self.close_socket(err)

    # ── virtual 메서드 (서브클래스 오버라이드) ─
    def alive_check_fail(self, fail_count: int) -> None:
        logger.debug("AliveCheckFail (virtual): %s", self.get_session_name())

    def close_socket(self, err: int) -> None:
        logger.debug("CloseSocket (virtual)")

    def receive_packet(self, packet: PacketT, session_identify: int = -1) -> None:
        logger.debug("ReceivePacket (virtual)")

    def on_session_identify(self, session_type: int, name: str) -> None:
        logger.debug("SessionIdentify (virtual)")

    def cmd_open_port_info(self, port_info: AsCmdOpenPort) -> bool:
        logger.debug("CmdOpenPortInfo (virtual)")
        return False

    # ── hton / ntoh (네트워크 바이트 변환) ────
    def hton_struct(self, packet: PacketT) -> None:
        """C++ HtonStruct 대응 — msg_id 별 페이로드 int 필드 htonl 변환."""
        self._convert_struct(packet, to_network=True)

    def ntoh_struct(self, packet: PacketT) -> None:
        """C++ NtohStruct 대응 — msg_id 별 페이로드 int 필드 ntohl 변환."""
        self._convert_struct(packet, to_network=False)

    def _convert_struct(self, packet: PacketT, to_network: bool) -> None:
        """
        hton/ntoh 변환 공통 처리.
        Python은 네트워크 전송 시 struct.pack('!...') 으로 처리하므로
        이미 직렬화/역직렬화 단계에서 변환이 완료됩니다.
        이 메서드는 C++ 코드와의 인터페이스 호환성을 위해 존재하며,
        PacketT.msg 가 raw bytes 인 경우에만 실제 변환이 필요합니다.
        필드별 변환이 필요한 경우 서브클래스에서 오버라이드하세요.
        """
        conv32 = socket.htonl if to_network else socket.ntohl
        conv16 = socket.htons if to_network else socket.ntohs
        mid = packet.msg_id
        raw = packet.msg if isinstance(packet.msg, bytes) \
              else packet.msg.encode()

        # ── 4바이트 단일 int 필드 변환 헬퍼 ──
        def c32(buf: bytes, offset: int) -> bytes:
            v = struct.unpack_from("!I", buf, offset)[0]
            return buf[:offset] + struct.pack("!I", conv32(v)) + buf[offset+4:]

        def c16(buf: bytes, offset: int) -> bytes:
            v = struct.unpack_from("!H", buf, offset)[0]
            return buf[:offset] + struct.pack("!H", conv16(v)) + buf[offset+2:]

        # msg_id 별 변환 규칙 적용
        # (C++ switch-case 와 동일한 로직, 대표 케이스만 구현)
        if mid in (AS_MMC_REQ, MMC_GEN_REQ, AS_MMC_REQ_OLD):
            # id(0~3), type(4~7), referenceId(8~11), interfaces(12~15)
            # responseMode(16~19), publishMode(20~23), collectMode(24~27)
            # cmdDelayTime(28~31), retryNo(32~35), curRetryNo(36~39)
            # parameterNo(40~43), priority(44~47), logMode(48~51)
            for off in (0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48):
                if off + 4 <= len(raw):
                    raw = c32(raw, off)

        elif mid in (AS_MMC_RES, CMD_MMC_PUBLISH_RES, MMC_RESPONSE_DATA):
            # id(0~3), resultMode(4~7)
            for off in (0, 4):
                if off + 4 <= len(raw):
                    raw = c32(raw, off)

        elif mid == AS_MMC_REQ_ACK:
            for off in (0, 4):
                if off + 4 <= len(raw):
                    raw = c32(raw, off)

        elif mid == SESSION_REPORTING:
            if 4 <= len(raw):
                raw = c32(raw, 0)

        elif mid == AS_PARSED_DATA:
            # eventTime(0~3), bscNo(4~5), equipFlag(6~7)
            # segBlkCnt(8~9), listSequence(10~11), attributeNo(12~13)
            if 4 <= len(raw): raw = c32(raw, 0)
            for off in (4, 6, 8, 10, 12):
                if off + 2 <= len(raw): raw = c16(raw, off)

        elif mid == CONNECTOR_DATA:
            # MsgId(0~3), SegFlag(4~7), Length(8~9), PortNo(10~11), LoggingFlag(12~13)
            if 4 <= len(raw): raw = c32(raw, 0)
            if 8 <= len(raw): raw = c32(raw, 4)
            for off in (8, 10, 12):
                if off + 2 <= len(raw): raw = c16(raw, off)

        elif mid == PROC_CONTROL:
            # ProcessType(0), MmcIdentType(4), JunctionType(8)
            # ConnectorStatus(12), ParserStatus(16), Status(20)
            # DelayTime(24), CmdResponseType(28), LogCycle(32)
            for off in (0, 4, 8, 12, 16, 20, 24, 28, 32):
                if off + 4 <= len(raw): raw = c32(raw, off)

        elif mid in (AS_SOCKET_STATUS_RES, FR_SOCKET_STATUS_RES):
            # Status(0~3), Size(4~7), 이후 FR_SOCKET_INFO_T 배열
            if 8 <= len(raw):
                raw = c32(raw, 0)
                raw = c32(raw, 4)

        elif mid in (CMD_PROC_INIT, CMD_ALIVE_ACK, CMD_PARSING_RULE_DOWN,
                     CMD_MAPPING_RULE_DOWN, CMD_COMMAND_RULE_DOWN,
                     CMD_SCHEDULER_RULE_DOWN, PROC_INIT_END,
                     CMD_PROC_TERMINATE, INIT_INFO_END):
            pass  # 변환 없음

        # 변환된 raw 를 다시 packet.msg 에 저장
        packet.msg = raw

    # ── 내부 유틸 ────────────────────────────
    @staticmethod
    def _get_errno() -> int:
        import ctypes
        return ctypes.get_errno()