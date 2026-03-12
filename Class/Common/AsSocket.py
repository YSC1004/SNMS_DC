"""
[변경이력]
2014.07.08  초기 작성
Python 변환: AsSocket.h/.C → AsSocket.py

역할: 소켓 기반 패킷 송수신 추상 클래스
  - C++: frSocketSensor 상속 → Python asyncio 스트림 기반
  - htonl/ntohl 바이트오더 변환 → struct.pack/unpack
  - 패킷 헤더: PACKET_T { MsgId(4B) + Length(4B) + Msg(MAX_MSG) }
  - 가상함수(virtual) → Python 추상메서드(@abstractmethod) 또는 오버라이드
"""

import asyncio
import struct
import logging
from typing import Optional, Tuple, Any

from Common.AsciiMmcType import (
    PACKET_T, MAX_MSG,
    AS_MMC_IDENT_RES_T, AS_MMC_FLOW_CONTROL_T,
    AS_MMC_REQUEST_OLD_T, AS_MMC_REQUEST_T, AS_MMC_ACK_T, AS_MMC_RESULT_T,
    AS_ROUTER_INFO_REQ_T, AS_ROUTER_INFO_RES_T, AS_ROUTER_CONFIG_T,
    AS_MMC_TYPE, AS_MMC_INTERFACE, AS_MMC_RESPONSE_MODE,
    AS_MMC_PUBLISH_MODE, AS_MMC_COLLECT_MODE, AS_MMC_RESULT_MODE,
    AS_MMC_IDENT_REQ, AS_MMC_IDENT_RES, AS_MMC_FLOW_CONTROL,
    AS_MMC_REQ_OLD, AS_MMC_REQ, AS_MMC_REQ_ACK, AS_MMC_RES,
    AS_ROUTER_INFO_REQ, AS_ROUTER_INFO_RES, AS_ROUTER_CONFIG,
)
from Common.CommType import (
    NOT_ASSIGN, SESSION_REPORTING, CMD_ALIVE_ACK, CMD_ALIVE_SEND, CMD_ALIVE_RECEIVE,
    CMD_LOG_STATUS_CHANGE, CMD_OPEN_PORT, CMD_OPEN_PORT_ACK,
    CONNECTOR_PORT_INFO_REQ, PORT_STATUS_INFO, PROCESS_INFO, PROCESS_INFO_LIST,
    ROUTER_PORT_INFO, AS_PARSED_DATA, MMC_LOG, CONNECTOR_DATA,
    ASCII_ERROR_MSG, CMD_PARSING_RULE_CHANGE, PROC_CONTROL, SESSION_CONTROL,
    AS_LOG_INFO, INIT_INFO_START, INIT_INFO_END,
    MANAGER_MODIFY, AS_MANAGER_INFO, CONNECTOR_MODIFY, AS_CONNECTOR_INFO,
    CONNECTION_MODIFY, AS_CONNECTION_INFO, CONNECTION_LIST_MODIFY, AS_CONNECTION_INFO_LIST,
    COMMAND_AUTHORITY_MODIFY, AS_COMMAND_AUTHORITY_INFO,
    AS_PROCESS_INFO, DATAHANDLER_MODIFY, AS_DATA_HANDLER_INFO,
    TAIL_LOG_DATA_REQ, TAIL_LOG_DATA_RES, TAIL_LOG_DATA,
    AS_SOCKET_STATUS_REQ, AS_SOCKET_STATUS_RES,
    FR_SOCKET_STATUS_REQ, FR_SOCKET_STATUS_RES,
    FR_SOCKET_SHUTDOWN_REQ, FR_SOCKET_SHUTDOWN_RES,
    FR_SOCKET_CHECK_REQ, FR_SOCKET_CHECK_RES,
    AS_DB_SYNC_KIND, AS_DB_SYNC_INFO_LIST,
    AS_DATA_HANDLER_INIT, AS_DATA_ROUTING_INIT,
    AS_SYSTEM_INFO, AS_SESSION_CFG,
    SUB_PROC_MODIFY, AS_SUB_PROC_INFO,
    MMC_GEN_REQ, MMC_GEN_RES, CMD_MMC_PUBLISH_REQ, CMD_MMC_PUBLISH_RES,
    MMC_RESPONSE_DATA, MMC_RESPONSE_DATA_REQ,
    CMD_PROC_INIT, PROC_INIT_END, CMD_PROC_TERMINATE,
    CMD_PARSING_RULE_DOWN, CMD_PARSING_RULE_DOWN_ACK,
    CMD_MAPPING_RULE_DOWN, CMD_MAPPING_RULE_DOWN_ACK,
    CMD_COMMAND_RULE_DOWN, CMD_COMMAND_RULE_DOWN_ACK,
    CMD_SCHEDULER_RULE_DOWN, CMD_SCHEDULER_RULE_DOWN_ACK,
    CONNECTOR_MODIFY_ACK, MANAGER_MODIFY_ACK, CONNECTION_MODIFY_ACK,
    DATAHANDLER_MODIFY_ACK, CONNECTION_LIST_MODIFY_ACK,
    COMMAND_AUTHORITY_MODIFY_ACK, SUB_PROC_MODIFY_ACK,
    NETFINDER_REQ, NETFINDER_REV,
    AS_SESSION_INFO_T, AS_ASCII_ACK_T,
    AS_CMD_OPEN_PORT_T, AS_CMD_LOG_CONTROL_T, AS_LOG_STATUS_T,
    AS_PORT_STATUS_INFO_T, AS_PROCESS_STATUS_T, AS_PROCESS_STATUS_LIST_T,
    AS_ROUTER_PORT_INFO_T, AS_PARSED_DATA_T, AS_MMC_LOG_T,
    AS_CONNECTOR_DATA_T, AS_ASCII_ERROR_MSG_T, AS_RULE_CHANGE_INFO_T,
    AS_PROC_CONTROL_T, AS_SESSION_CONTROL_T,
    AS_DATA_HANDLER_INFO_T, AS_TARGET_IP_INFO_T,
    AS_LOG_TAIL_DATA_REQ_T, AS_LOG_TAIL_DATA_RES_T,
    AS_GUI_INIT_INFO_T, AS_MANAGER_INFO_T, AS_CONNECTOR_INFO_T,
    AS_CONNECTION_INFO_T, AS_CONNECTION_INFO_LIST_T,
    AS_COMMAND_AUTHORITY_INFO_T, AS_PROCESS_STATUS_T,
    AS_SOCKET_STATUS_REQ_T, AS_SYSTEM_INFO_T, AS_SESSION_CFG_T,
    AS_SUB_PROC_INFO_T, AS_DB_SYNC_KIND_T, AS_DB_SYNC_INFO_LIST_T,
    AS_DATA_HANDLER_INIT_T, AS_DATA_ROUTING_INIT_T,
    AS_MMC_GEN_RESULT_T, AS_MMC_PUBLISH_T,
    PK_ResultMsg, LOG_CTL_TYPE, AS_STATUS, AS_SEGFLAG,
    MAX_SOCKET_INFO_CNT,
)
from Common.AsUtil import AsUtil

logger = logging.getLogger(__name__)

# PACKET_T 헤더: MsgId(4B, int) + Length(4B, int)
_PACKET_HEADER_FMT  = "!II"          # network byte order (big-endian) unsigned int x2
_PACKET_HEADER_SIZE = struct.calcsize(_PACKET_HEADER_FMT)  # 8 bytes

# PACKET_T 전체 크기 = 헤더(8) + 본문(MAX_MSG)
_PACKET_FULL_SIZE   = _PACKET_HEADER_SIZE + MAX_MSG


class AsSocket:
    """
    C++: class AsSocket : public frSocketSensor

    소켓 패킷 송수신 추상 기반 클래스.
    asyncio StreamReader/StreamWriter 를 사용하여 비동기 I/O 처리.

    하위 클래스에서 반드시 오버라이드해야 하는 가상 메서드:
        - receive_packet(packet, session_identify)
        - close_socket(errno_val)
        - session_identify_callback(session_type, session_name)
        - alive_check_fail(fail_count)          [선택]
        - cmd_open_port_info(port_info)         [선택]
    """

    def __init__(self):
        self._session_identify: int = NOT_ASSIGN
        self._alive_check_task: Optional[asyncio.Task] = None
        self._alive_send_task:  Optional[asyncio.Task] = None
        self._fail_count:       int  = 0
        self._fail_count_max:   int  = 0
        self._re_read_check:    bool = False
        self._session_name:     str  = ""

        # asyncio 스트림 (Connect 후 set_streams()로 주입)
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

        self._object_name: str = ""

    # ──────────────────────────────────────────
    # 스트림 주입 (frSocketSensor 역할 대체)
    # ──────────────────────────────────────────

    def set_streams(self, reader: asyncio.StreamReader,
                    writer: asyncio.StreamWriter) -> None:
        """TCP 연결 후 asyncio 스트림을 주입한다."""
        self._reader = reader
        self._writer = writer

    def get_peer_ip(self) -> str:
        if self._writer:
            try:
                return self._writer.get_extra_info("peername", ("", 0))[0]
            except Exception:
                pass
        return ""

    # ──────────────────────────────────────────
    # 이름 / 세션 타입
    # ──────────────────────────────────────────

    def set_object_name(self, name: str) -> None:
        self._object_name = name

    def get_object_name(self) -> str:
        return self._object_name

    def SetSessionName(self, name: str) -> None:
        self.set_object_name(name)

    def GetSessionName(self) -> str:
        return self.get_object_name()

    def GetSessionType(self) -> int:
        return self._session_identify

    # ──────────────────────────────────────────
    # 패킷 헤더 바이트오더 변환
    # htonl/ntohl → struct.pack/unpack (network = big-endian)
    # ──────────────────────────────────────────

    @staticmethod
    def _hton_packet(pkt: PACKET_T) -> PACKET_T:
        """호스트→네트워크 바이트오더 (패킷 헤더만)"""
        # Python int는 플랫폼 무관 → 직렬화 시 struct.pack으로 처리하므로
        # 이 메서드는 논리적 변환 표시용 (실제 변환은 _serialize에서 수행)
        return pkt

    @staticmethod
    def _ntoh_packet(pkt: PACKET_T) -> PACKET_T:
        return pkt

    # ──────────────────────────────────────────
    # 직렬화 / 역직렬화 (htonl/ntohl 실질 처리)
    # ──────────────────────────────────────────

    @staticmethod
    def _serialize(pkt: PACKET_T) -> bytes:
        """PACKET_T → bytes (network byte order)"""
        msg_bytes = pkt.Msg.encode("utf-8", errors="replace") if isinstance(pkt.Msg, str) \
                    else bytes(pkt.Msg)
        msg_bytes = msg_bytes[:MAX_MSG].ljust(pkt.Length, b'\x00')[:pkt.Length]
        header = struct.pack(_PACKET_HEADER_FMT, pkt.MsgId, pkt.Length)
        return header + msg_bytes

    @staticmethod
    def _deserialize_header(data: bytes) -> Tuple[int, int]:
        """bytes(8) → (MsgId, Length)"""
        return struct.unpack(_PACKET_HEADER_FMT, data)

    # ──────────────────────────────────────────
    # 저수준 패킷 송수신
    # ──────────────────────────────────────────

    async def _packet_send(self, pkt: PACKET_T) -> bool:
        """
        C++: PacketSend()
        패킷 직렬화 후 전송. 실패 시 False 반환.
        """
        if not self._writer:
            return False
        try:
            payload = _serialize_packet(pkt)
            self._writer.write(payload)
            await self._writer.drain()
            return True
        except (ConnectionError, OSError) as e:
            logger.debug("packet_send error: %s", e)
            return False

    async def _packet_recv(self) -> Tuple[int, Optional[PACKET_T]]:
        """
        C++: PacketRecv()
        Returns:
            (bytes_read, PACKET_T) 또는 (-1, None) on error
        """
        if not self._reader:
            return -1, None

        re_read_cnt = 0
        try:
            # 헤더 수신
            header_buf = await _read_exact(self._reader, _PACKET_HEADER_SIZE,
                                           self._re_read_check)
            if header_buf is None:
                return -1, None

            msg_id, length = self._deserialize_header(header_buf)

            if length == 0:
                pkt = PACKET_T(MsgId=msg_id, Length=0, Msg="")
                return _PACKET_HEADER_SIZE, pkt

            if length > MAX_MSG:
                logger.error("length(%d) is over than MAX_MSG(%d)", length, MAX_MSG)
                return -1, None

            # 본문 수신
            msg_buf = await _read_exact(self._reader, length, self._re_read_check)
            if msg_buf is None:
                return -1, None

            pkt = PACKET_T(MsgId=msg_id, Length=length,
                           Msg=msg_buf.decode("utf-8", errors="replace"))
            return _PACKET_HEADER_SIZE + length, pkt

        except (ConnectionError, asyncio.IncompleteReadError, OSError) as e:
            logger.debug("packet_recv error: %s", e)
            return -1, None

    # ──────────────────────────────────────────
    # 공개 패킷 API
    # ──────────────────────────────────────────

    async def SendPacket(self, msg_id: int,
                         result: Optional[bytes] = None,
                         length: int = 0) -> bool:
        """C++: SendPacket(int MsgId, char* Result, int Len)"""
        pkt = PACKET_T(MsgId=msg_id, Length=length,
                       Msg=result.decode("utf-8", errors="replace") if result else "")
        return await self._packet_send(pkt)

    async def SendPacketRaw(self, pkt: PACKET_T) -> bool:
        """C++: SendPacket(PACKET_T*)"""
        return await self._packet_send(pkt)

    async def SendAck(self, msg_id: int, id_: int,
                      result_mode: int = 1,
                      result_msg: str = "") -> bool:
        """C++: SendAck()"""
        ack = AS_ASCII_ACK_T(Id=id_, ResultMode=result_mode, Result=result_msg)
        payload = _pack_ascii_ack(ack)
        return await self.SendPacket(msg_id, payload, len(payload))

    def RecvAck(self, pkt: PACKET_T) -> AS_ASCII_ACK_T:
        """C++: RecvAck() — 동기 파싱 (패킷 수신 후 호출)"""
        return _unpack_ascii_ack(pkt.Msg)

    async def SendAndWaitPacket(self, msg_id: int, result: bytes,
                                length: int, wait_msg_id: int) -> Tuple[int, Optional[bytes]]:
        """
        C++: SendAndWaitPacket()
        Returns: (1, msg_bytes) on success, (-1, None) on fail
        """
        if not await self.SendPacket(msg_id, result, length):
            return -1, None
        return await self.WaitPacket(wait_msg_id)

    async def WaitPacket(self, wait_msg_id: int) -> Tuple[int, Optional[bytes]]:
        """C++: WaitPacket()"""
        ret, pkt = await self._packet_recv()
        if ret > 0 and pkt and pkt.MsgId == wait_msg_id:
            return 1, pkt.Msg.encode("utf-8", errors="replace")
        logger.error("WaitPacket: no wait msgid (got %s, want %d)",
                     pkt.MsgId if pkt else None, wait_msg_id)
        return -1, None

    async def SendCmdLogStatusChange(self, log_ctl: AS_CMD_LOG_CONTROL_T) -> bool:
        payload = _pack_log_control(log_ctl)
        return await self.SendPacket(CMD_LOG_STATUS_CHANGE, payload, len(payload))

    # ──────────────────────────────────────────
    # 세션 식별
    # ──────────────────────────────────────────

    def _do_session_identify(self, pkt: PACKET_T) -> None:
        """C++: SessionIdentify(PACKET_T*)"""
        session_info = _unpack_session_info(pkt.Msg)
        self._session_identify = session_info.SessionType
        self.set_object_name(session_info.Name)

    async def SetSessionIdentify(self, session_type: int,
                                  name: str = "",
                                  check_interval: int = 100,
                                  auto_ack: bool = True) -> None:
        """C++: SetSessionIdentify()"""
        self._session_identify = session_type
        self.set_object_name(name)

        session_info = AS_SESSION_INFO_T(SessionType=session_type, Name=name)
        payload = _pack_session_info(session_info)
        await self.SendPacket(SESSION_REPORTING, payload, len(payload))

        if auto_ack:
            self._start_alive_send(check_interval)

    # ──────────────────────────────────────────
    # Alive Check
    # ──────────────────────────────────────────

    def StartAliveCheck(self, interval_ms: int, max_fail: int) -> bool:
        """C++: StartAliveCheck() — 수신 측 타이머"""
        if self._session_identify == NOT_ASSIGN:
            logger.debug("Not yet Session Identify")
            return False
        self._fail_count_max = max_fail
        self._stop_alive_check()
        self._alive_check_task = asyncio.create_task(
            self._alive_check_loop(interval_ms))
        return True

    def StopAliveCheck(self) -> None:
        self._stop_alive_check()

    def _stop_alive_check(self) -> None:
        if self._alive_check_task:
            self._alive_check_task.cancel()
            self._alive_check_task = None

    def _start_alive_send(self, interval_ms: int) -> None:
        """C++: CMD_ALIVE_SEND 타이머 — 주기적으로 ACK 패킷 전송"""
        if self._alive_send_task:
            self._alive_send_task.cancel()
        self._alive_send_task = asyncio.create_task(
            self._alive_send_loop(interval_ms))

    async def _alive_check_loop(self, interval_ms: int) -> None:
        """C++: AliveCheckTimer → CMD_ALIVE_RECEIVE 이벤트 대응"""
        try:
            while True:
                await asyncio.sleep(interval_ms / 1000)
                self._fail_count += 1
                if self._fail_count_max < self._fail_count:
                    logger.debug("AliveCheckTimeOut: %s(%d)",
                                 self.GetSessionName(), self._fail_count)
                    self.alive_check_fail(self._fail_count)
        except asyncio.CancelledError:
            pass

    async def _alive_send_loop(self, interval_ms: int) -> None:
        """주기적으로 CMD_ALIVE_ACK 패킷 전송"""
        try:
            while True:
                await asyncio.sleep(interval_ms / 1000)
                await self._send_alive_ack()
        except asyncio.CancelledError:
            pass

    async def _send_alive_ack(self) -> None:
        """C++: AliveCheckSendTime()"""
        if not await self.SendPacket(CMD_ALIVE_ACK):
            self._socket_broken(0)
        logger.debug("AliveCheckPacketSend(%s)", self.GetSessionName())

    # ──────────────────────────────────────────
    # 메시지 수신 루프
    # ──────────────────────────────────────────

    async def ReceiveMessage(self) -> None:
        """
        C++: ReceiveMessage() — 소켓에서 패킷을 읽어 처리.
        호출자(ConnectionMgr 등)가 루프에서 반복 호출.
        """
        ret, pkt = await self._packet_recv()
        if ret == -1 or pkt is None:
            self._socket_broken(0)
            return

        if pkt.MsgId == SESSION_REPORTING:
            if self._session_identify != NOT_ASSIGN:
                logger.error("Already Session Identify")
            else:
                self._do_session_identify(pkt)
                self.session_identify_callback(
                    self._session_identify, self.get_object_name())

        elif pkt.MsgId == CMD_ALIVE_ACK:
            logger.debug("Alive Ack Receive: %s", self.GetSessionName())
            self._fail_count = 0

        else:
            self.receive_packet(pkt, self._session_identify)

    # ──────────────────────────────────────────
    # 내부 유틸
    # ──────────────────────────────────────────

    def _socket_broken(self, errno_val: int) -> None:
        """C++: SocketBroken()"""
        self._close()
        self.close_socket(errno_val)

    def _close(self) -> None:
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
        self._writer = None
        self._reader = None

    def SetReReadCheck(self, flag: bool) -> None:
        self._re_read_check = flag

    # ──────────────────────────────────────────
    # 바이트오더 변환 (HtonStruct / NtohStruct)
    # Python에서는 직렬화/역직렬화 시 struct.pack/unpack으로 처리하므로
    # 메시지 타입별 변환 로직을 별도 함수로 분리
    # ──────────────────────────────────────────

    def HtonStruct(self, pkt: PACKET_T) -> None:
        """
        C++: HtonStruct() — 전송 전 int 필드를 network byte order로 변환.
        Python에서는 송신 직렬화(_serialize_msg_payload)에서 처리.
        하위 클래스에서 오버라이드 가능.
        """
        _apply_byteorder(pkt, to_network=True)

    def NtohStruct(self, pkt: PACKET_T) -> None:
        """
        C++: NtohStruct() — 수신 후 host byte order로 복원.
        """
        _apply_byteorder(pkt, to_network=False)

    # ──────────────────────────────────────────
    # 가상 메서드 (하위 클래스 오버라이드 대상)
    # ──────────────────────────────────────────

    def receive_packet(self, pkt: PACKET_T, session_identify: int = -1) -> None:
        """C++: virtual ReceivePacket() — 수신 패킷 처리 (서브클래스 구현)"""
        logger.debug("receive_packet is virtual function")

    def close_socket(self, errno_val: int) -> None:
        """C++: virtual CloseSocket()"""
        logger.debug("close_socket is virtual function")

    def session_identify_callback(self, session_type: int,
                                   session_name: str = "") -> None:
        """C++: virtual SessionIdentify(int, string)"""
        logger.debug("session_identify_callback is virtual function")

    def alive_check_fail(self, fail_count: int) -> None:
        """C++: virtual AliveCheckFail()"""
        logger.debug("alive_check_fail is virtual function (%s)",
                     self.GetSessionName())

    def CmdOpenPortInfo(self, port_info: AS_CMD_OPEN_PORT_T) -> bool:
        """C++: virtual CmdOpenPortInfo()"""
        logger.debug("CmdOpenPortInfo is virtual function")
        AsUtil.CmdOpenPortDisplay(port_info)
        return False


# ──────────────────────────────────────────────
# 모듈 레벨 헬퍼 함수
# (C++ 내부 캐스트/memcpy 로직을 순수 함수로 분리)
# ──────────────────────────────────────────────

async def _read_exact(reader: asyncio.StreamReader,
                      n: int,
                      re_read_check: bool = False,
                      max_retry: int = 4) -> Optional[bytes]:
    """
    정확히 n 바이트를 읽을 때까지 반복.
    C++: while((len = Read(msg, length)) != length) { ... }
    """
    buf = bytearray()
    retry = 0
    while len(buf) < n:
        try:
            chunk = await reader.read(n - len(buf))
        except (ConnectionError, asyncio.IncompleteReadError) as e:
            logger.debug("_read_exact error: %s", e)
            return None

        if not chunk:
            if re_read_check and retry < max_retry:
                await asyncio.sleep(0.07)   # 70ms (C++: AsUtil::AsSleep(70000))
                retry += 1
                continue
            return None
        buf.extend(chunk)
    return bytes(buf)


def _serialize_packet(pkt: PACKET_T) -> bytes:
    """PACKET_T → bytes (network byte order 헤더 + raw 본문)"""
    if isinstance(pkt.Msg, str):
        msg_bytes = pkt.Msg.encode("utf-8", errors="replace")
    else:
        msg_bytes = bytes(pkt.Msg)
    length = pkt.Length if pkt.Length else len(msg_bytes)
    msg_bytes = msg_bytes[:length]
    return struct.pack("!II", pkt.MsgId, length) + msg_bytes


# ── 개별 구조체 pack/unpack 헬퍼 ────────────────

def _pack_session_info(s: AS_SESSION_INFO_T) -> bytes:
    name_b = s.Name.encode("utf-8")[:99].ljust(100, b'\x00')
    return struct.pack("!i", s.SessionType) + name_b

def _unpack_session_info(msg: str) -> AS_SESSION_INFO_T:
    raw = msg.encode("utf-8", errors="replace") if isinstance(msg, str) else bytes(msg)
    session_type = struct.unpack_from("!i", raw, 0)[0]
    name = raw[4:104].rstrip(b'\x00').decode("utf-8", errors="replace")
    return AS_SESSION_INFO_T(SessionType=session_type, Name=name)

def _pack_ascii_ack(ack: AS_ASCII_ACK_T) -> bytes:
    result_b = ack.Result.encode("utf-8")[:1999].ljust(2000, b'\x00')
    return struct.pack("!ii", ack.Id, ack.ResultMode) + result_b

def _unpack_ascii_ack(msg: str) -> AS_ASCII_ACK_T:
    raw = msg.encode("utf-8", errors="replace") if isinstance(msg, str) else bytes(msg)
    id_, mode = struct.unpack_from("!ii", raw, 0)
    result = raw[8:2008].rstrip(b'\x00').decode("utf-8", errors="replace")
    return AS_ASCII_ACK_T(Id=id_, ResultMode=mode, Result=result)

def _pack_log_control(lc: AS_CMD_LOG_CONTROL_T) -> bytes:
    mgr_b  = lc.ManagerId.encode("utf-8")[:39].ljust(40, b'\x00')
    proc_b = lc.ProcessId.encode("utf-8")[:79].ljust(80, b'\x00')
    pkg_b  = lc.Package.encode("utf-8")[:127].ljust(128, b'\x00')
    feat_b = lc.Feature.encode("utf-8")[:127].ljust(128, b'\x00')
    return (struct.pack("!iii", lc.Id, lc.ProcessType, int(lc.Type))
            + mgr_b + proc_b + pkg_b + feat_b
            + struct.pack("!i", lc.Level))


def _apply_byteorder(pkt: PACKET_T, to_network: bool) -> None:
    """
    C++: HtonStruct / NtohStruct 의 Python 대응.
    Python int는 플랫폼 무관하므로 실제 변환은 struct.pack/unpack 시 수행.
    이 함수는 MsgId 기반으로 Msg 내부 int 필드를 수동 변환이 필요한 경우를 위한
    확장 포인트. 현재는 no-op (직렬화 단계에서 처리됨).

    고성능이 필요하거나 C 바이너리 호환이 필요한 경우
    struct.pack_into 를 사용하여 Msg 버퍼를 직접 조작하는
    방식으로 확장 가능.
    """
    pass  # 직렬화(_serialize_packet)에서 big-endian 처리