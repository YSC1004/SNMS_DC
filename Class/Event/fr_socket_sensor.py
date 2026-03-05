# -*- coding: utf-8 -*-
"""
frSocketSensor.h / frSocketSensor.C  →  fr_socket_sensor.py
Python 3.11.10 버전

변환 설계:
  frSocketSensor   → FrSocketSensor  (FrRdFdSensor 상속)

C++ → Python 주요 변환 포인트:
  socket() / bind() / listen() / accept() / connect()
                               → socket.socket (Python 표준 라이브러리)
  AF_INET / AF_UNIX / SOCK_STREAM / SOCK_DGRAM
                               → socket.AF_INET 등
  setsockopt SO_SNDBUF/RCVBUF/REUSEADDR/LINGER
                               → sock.setsockopt()
  select() FD_SET/FD_ISSET     → select.select()  (IsWriterable/IsReaderable)
  ioctl FIONREAD                → socket.ioctl(FIONREAD) 또는 fcntl.ioctl()
  WriteDataList (list<WriteData*>) → deque[_WriteData]
  frMutex m_WriteDataLock / m_WriteLock → threading.Lock
  frSocketSensorTimer*         → FrSocketSensorTimer (지연 임포트)
  memset(m_SessionTime)        → str
  timeb / ftime()              → datetime.datetime.now()
  strcpy / strncpy             → str 대입
  SIGPIPE 블록                 → signal.signal(SIGPIPE, SIG_IGN)  (POSIX)
  shutdown(fd, SHUT_RDWR)      → sock.shutdown()
  AcceptSocket / ReceiveMessage → 가상함수, 서브클래스 오버라이드
  RecvShutDownInfo / RecvOverFlowDataBufInfo → 가상함수

변경 이력:
  v1 - 초기 변환
"""

import datetime
import os
import select as _select
import signal
import socket
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import ClassVar, Optional, TYPE_CHECKING

from fr_rd_fd_sensor import FrRdFdSensor
from fr_sensor        import SensorMode

if TYPE_CHECKING:
    from fr_socket_sensor_timer import FrSocketSensorTimer

# ─────────────────────────────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────────────────────────────
_CONNECT_SOCKET = 0
_LISTEN_SOCKET  = 1

_DEFAULT_SOCK_BUF_SIZE        = 32768
_DEFAULT_SOCK_CHECK_TIME_OUT  = 100          # microsec
_MAX_SOCK_BUF_SIZE            = 1024*1024*200
_MAX_DATADUMP_SIZE            = 51

# SOCK_INFO 상수 (frSockFdManager.h 대응)
SOCK_INFO_USE_TYPE_UNKNOWN   = 0
SOCK_INFO_USE_TYPE_LISTEN    = 1
SOCK_INFO_USE_TYPE_CONNECT   = 2
SOCK_INFO_USE_TYPE_CONNECTED = 3
SOCK_INFO_MODE_UNKNOWN       = 0
SOCK_INFO_MODE_AF_INET_TCP   = 1
SOCK_INFO_MODE_AF_UNIX       = 2


# ─────────────────────────────────────────────────────────────────────────────
# _WriteData  (C++ WriteData 구조체 대응)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class _WriteData:
    data:   bytes
    length: int = field(init=False)

    def __post_init__(self) -> None:
        self.length = len(self.data)


# ─────────────────────────────────────────────────────────────────────────────
# FrSocketSensor
# ─────────────────────────────────────────────────────────────────────────────
class FrSocketSensor(FrRdFdSensor):
    """
    C++ frSocketSensor 대응 클래스.
    TCP/UDP/Unix Domain 소켓을 FrRdFdSensor 위에 래핑.

    클래스(static) 변수:
      m_SystemMaxSendSockBuf → system_max_send_sock_buf : int
      m_SystemMaxRecvSockBuf → system_max_recv_sock_buf : int

    인스턴스 변수:
      m_FD          → _fd  (부모 FrRdFdSensor 에서 관리, socket.fileno())
      _sock         : socket.socket | None  — Python socket 객체
    """

    system_max_send_sock_buf: ClassVar[int] = -1
    system_max_recv_sock_buf: ClassVar[int] = -1

    def __init__(self, sensor_mode: SensorMode = SensorMode.FR_NORMAL_SENSOR) -> None:
        """
        C++ frSocketSensor() / frSocketSensor(FR_SENSOR_MODE) 통합.
        sensor_mode=FR_NO_SENSOR 이면 create_no_sensor() 팩토리를 사용.
        """
        super().__init__()          # fd=-1, FR_NORMAL_SENSOR
        self._sock:              Optional[socket.socket] = None
        self._socket_mode:       int  = -1   # AF_INET / AF_UNIX
        self._socket_type:       int  = -1   # SOCK_STREAM / SOCK_DGRAM
        self._socket_path:       str  = ''
        self._listener_name:     str  = ''
        self._peer_ip:           str  = ''
        self._port_no:           int  = 0
        self._use_flag:          int  = _CONNECT_SOCKET
        self._use_type:          int  = SOCK_INFO_USE_TYPE_UNKNOWN
        self._session_time:      str  = ''
        self._session_time_detail: int = 0
        self._writerable_check:  bool = False
        self._writerable_check_timeout: int = _DEFAULT_SOCK_CHECK_TIME_OUT
        self._max_data_buf_size: int  = -1
        self._cur_data_buf_size: int  = 0
        self._write_data_list:   deque[_WriteData] = deque()
        self._write_data_lock:   threading.Lock    = threading.Lock()
        self._write_lock:        threading.Lock    = threading.Lock()
        self._write_timer_sensor: Optional['FrSocketSensorTimer'] = None

        self._object_type = 5
        self.disable()

        # SIGPIPE 무시 (C++ SignalsBlock(SIGPIPE) 대응, POSIX 전용)
        try:
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        except (AttributeError, OSError):
            pass

    def __del__(self) -> None:
        with self._write_data_lock:
            self._write_data_list.clear()
        self._write_timer_sensor = None
        self.close()

    # ------------------------------------------------------------------ #
    # 소켓 생성
    # ------------------------------------------------------------------ #
    def create(self, socket_mode: int = socket.AF_INET,
               socket_type: int = socket.SOCK_STREAM) -> bool:
        """C++ Create(int SocketMode, int SocketType) 대응."""
        self._socket_type = socket_type
        self._socket_mode = socket_mode

        if self._socket_mode == socket.AF_UNIX:
            self._socket_type = socket.SOCK_STREAM

        allowed_modes  = (socket.AF_INET, socket.AF_UNIX)
        allowed_types  = (socket.SOCK_STREAM, socket.SOCK_DGRAM)

        if self._socket_mode not in allowed_modes or self._socket_type not in allowed_types:
            self.set_obj_err_msg('Unsupported socket mode %d type %d',
                                 socket_mode, self._socket_type)
            return False

        if self._fd != -1:
            self.close()

        try:
            self._sock = socket.socket(self._socket_mode, self._socket_type, 0)
            self._fd   = self._sock.fileno()
            return True
        except OSError as e:
            self.set_obj_err_msg('socket create error: %s', e)
            return False

    # ------------------------------------------------------------------ #
    # Listen (TCP/UDP + Unix Domain)
    # ------------------------------------------------------------------ #
    def listen(self, port_or_path, backlog: int = 5) -> bool:
        """
        C++ Listen(int Port, int BackLog) / Listen(string SocketPath, int BackLog) 통합.
        port_or_path: int → AF_INET,  str → AF_UNIX
        """
        if isinstance(port_or_path, str):
            return self._listen_unix(port_or_path, backlog)
        return self._listen_inet(port_or_path, backlog)

    def _listen_inet(self, port: int, backlog: int) -> bool:
        if self._socket_mode != socket.AF_INET:
            self.set_obj_err_msg('Listen: SocketMode is not AF_INET')
            return False
        if self._fd == -1:
            self.set_obj_err_msg('must call create() first')
            return False

        self._use_type = SOCK_INFO_USE_TYPE_LISTEN
        try:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if not self._set_sock_opt():
                return False
            self._sock.bind(('', port))
            if self._socket_type == socket.SOCK_STREAM:
                self._sock.listen(backlog)
            self.set_close_on_exec(True)
            self._port_no  = port
            self._use_flag = _LISTEN_SOCKET
            self._set_session_time()
            self.enable()
            return True
        except OSError as e:
            self.set_obj_err_msg('listen error: %s', e)
            return False

    def _listen_unix(self, path: str, backlog: int) -> bool:
        if self._socket_mode != socket.AF_UNIX:
            self.set_obj_err_msg('Listen: SocketMode is not AF_UNIX')
            return False
        if self._fd == -1:
            self.set_obj_err_msg('must call create() first')
            return False

        self._use_type = SOCK_INFO_USE_TYPE_LISTEN
        try:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if not self._set_sock_opt():
                return False
            try:
                self._sock.bind(path)
            except OSError as e:
                import errno
                if e.errno == errno.EADDRINUSE:
                    os.unlink(path)
                    return self._listen_unix(path, backlog)
                self.set_obj_err_msg('%s', e)
                return False
            self._sock.listen(backlog)
            self.set_close_on_exec(True)
            self._socket_path = path
            self._use_flag    = _LISTEN_SOCKET
            self._set_session_time()
            self.enable()
            return True
        except OSError as e:
            self.set_obj_err_msg('unix listen error: %s', e)
            return False

    # ------------------------------------------------------------------ #
    # Accept
    # ------------------------------------------------------------------ #
    def accept(self, new_sensor: 'FrSocketSensor') -> bool:
        """C++ Accept(frSocketSensor*) 대응."""
        try:
            conn, addr = self._sock.accept()
            new_sensor._sock      = conn
            new_sensor._fd        = conn.fileno()
            new_sensor._socket_mode = self._socket_mode

            if self._socket_mode == socket.AF_INET:
                new_sensor._peer_ip = addr[0]
                new_sensor._port_no = addr[1]
            else:
                new_sensor._peer_ip = 'localhost'

            new_sensor._use_type      = SOCK_INFO_USE_TYPE_CONNECTED
            new_sensor._listener_name = self.get_object_name()
            if not new_sensor._set_sock_opt():
                return False
            new_sensor.set_close_on_exec(True)
            new_sensor._set_session_time()
            new_sensor.enable()
            return True
        except OSError as e:
            self.set_obj_err_msg('accept error: %s', e)
            return False

    # ------------------------------------------------------------------ #
    # Connect (TCP + Unix Domain)
    # ------------------------------------------------------------------ #
    def connect(self, address_or_path: str, port: int = 0) -> bool:
        """
        C++ Connect(string Address, int Port) / Connect(string SocketPath) 통합.
        port=0 이면 Unix Domain 소켓으로 간주.
        """
        if port == 0:
            return self._connect_unix(address_or_path)
        return self._connect_inet(address_or_path, port)

    def _connect_inet(self, address: str, port: int) -> bool:
        self._use_type = SOCK_INFO_USE_TYPE_CONNECT
        self._peer_ip  = address
        self._port_no  = port
        if self._fd != -1:
            self.close()
        if not self.create():
            return False
        try:
            if not self._set_sock_opt():
                return False
            self._sock.connect((address, port))
            self.set_close_on_exec(True)
            self._set_session_time()
            self._use_flag = _CONNECT_SOCKET
            self.enable()
            return True
        except OSError as e:
            self.set_obj_err_msg('%s (%s:%d)', e, address, port)
            self.close()
            return False

    def _connect_unix(self, path: str) -> bool:
        self._use_type = SOCK_INFO_USE_TYPE_CONNECT
        if self._fd != -1:
            self.close()
        if not self.create(socket.AF_UNIX):
            return False
        try:
            if not self._set_sock_opt():
                return False
            self._sock.connect(path)
            self.set_close_on_exec(True)
            self._socket_path = path
            self._use_flag    = _CONNECT_SOCKET
            self.enable()
            return True
        except OSError as e:
            self.set_obj_err_msg('%s (PATH:%s)', e, path)
            self.close()
            return False

    # ------------------------------------------------------------------ #
    # Close
    # ------------------------------------------------------------------ #
    def close(self) -> bool:
        """C++ Close() 대응."""
        prev_use_type   = self._use_type
        prev_sock_mode  = self._socket_mode
        prev_sock_path  = self._socket_path
        self._use_type  = SOCK_INFO_USE_TYPE_UNKNOWN

        # 부모 close() — selector 해제 + os.close()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

        # fd 는 sock.close() 로 이미 닫혔으므로 부모 _fd 만 초기화
        self._fd = -1
        self.disable()

        # AF_UNIX Listen 소켓 파일 삭제
        if (prev_sock_mode == socket.AF_UNIX
                and prev_use_type == SOCK_INFO_USE_TYPE_LISTEN
                and prev_sock_path):
            try:
                os.unlink(prev_sock_path)
            except OSError:
                pass
        return True

    # ------------------------------------------------------------------ #
    # SubjectChanged / 가상 함수
    # ------------------------------------------------------------------ #
    def subject_changed(self) -> int:
        """C++ SubjectChanged() 대응."""
        if self._use_flag == _CONNECT_SOCKET:
            self.receive_message()
        elif self._use_flag == _LISTEN_SOCKET:
            if self._socket_type == socket.SOCK_STREAM:
                self.accept_socket()
            else:
                self.receive_message()
        return 1

    def accept_socket(self) -> None:
        """C++ AcceptSocket() 가상함수 대응. 서브클래스에서 오버라이드."""
        import logging
        logging.getLogger(__name__).error(
            'FrSocketSensor.accept_socket: virtual (override me)')

    def receive_message(self) -> None:
        """C++ ReceiveMessage() 가상함수 대응. 서브클래스에서 오버라이드."""
        import logging
        logging.getLogger(__name__).error(
            'FrSocketSensor.receive_message: virtual (override me)')

    def recv_shut_down_info(self, info: str) -> None:
        """C++ RecvShutDownInfo() 가상함수 대응."""
        import logging
        logging.getLogger(__name__).error(
            'FrSocketSensor.recv_shut_down_info: virtual (override me)')

    def recv_overflow_data_buf_info(self, max_size: int, cur_size: int) -> None:
        """C++ RecvOverFlowDataBufInfo() 가상함수 대응."""
        import logging
        logging.getLogger(__name__).error(
            'FrSocketSensor.recv_overflow_data_buf_info: virtual (override me)')

    # ------------------------------------------------------------------ #
    # Write
    # ------------------------------------------------------------------ #
    def write(self, packet: bytes) -> int:
        """C++ Write(char* Packet, int Length) 대응."""
        if not self._writerable_check:
            return self._write_socket(packet)

        with self._write_lock:
            while True:
                if self.is_writerable():
                    data = self._get_write_data()
                    if data:
                        ret = self._write_socket(data.data)
                        if ret < 1:
                            return ret
                    else:
                        return self._write_socket(packet)
                else:
                    return self._put_write_data(packet)

    def _write_socket(self, packet: bytes) -> int:
        """C++ WriteSocket() 대응 — 부모 os.write() 직접 호출."""
        return super().write(packet)

    def write_to(self, packet: bytes, dest_ip: str,
                 dest_port: int) -> int:
        """C++ WriteTo(char*, int, const char*, unsigned short) 대응."""
        try:
            return self._sock.sendto(packet, (dest_ip, dest_port))
        except OSError as e:
            self.set_obj_err_msg('write_to error: %s', e)
            return -1

    def read_from(self, length: int) -> tuple[bytes, str, int]:
        """
        C++ ReadFrom(char*, int, string&, int&) 대응.
        반환: (data, src_ip, src_port)
        """
        try:
            data, addr = self._sock.recvfrom(length)
            return data, addr[0], addr[1]
        except OSError as e:
            self.set_obj_err_msg('read_from error: %s', e)
            return b'', '', 0

    # ------------------------------------------------------------------ #
    # 쓰기 버퍼 관리
    # ------------------------------------------------------------------ #
    def _put_write_data(self, data: bytes) -> int:
        """C++ PutWriteData() 대응."""
        entry = _WriteData(data)
        with self._write_data_lock:
            self._write_data_list.append(entry)
            if self._max_data_buf_size > 0:
                self._cur_data_buf_size += entry.length

        if self._max_data_buf_size > 0 and self._cur_data_buf_size > self._max_data_buf_size:
            self.recv_overflow_data_buf_info(self._max_data_buf_size,
                                             self._cur_data_buf_size)
            return -1
        return entry.length

    def _get_write_data(self) -> Optional[_WriteData]:
        """C++ GetWriteData() (포인터 반환형) 대응."""
        with self._write_data_lock:
            if self._write_data_list:
                entry = self._write_data_list.popleft()
                if self._max_data_buf_size > 0:
                    self._cur_data_buf_size -= entry.length
                return entry
        return None

    def _is_write_data(self) -> bool:
        """C++ IsWriteData() 대응."""
        with self._write_data_lock:
            return bool(self._write_data_list)

    def data_send_time(self) -> None:
        """C++ DataSendTime() 대응."""
        if self._is_write_data():
            with self._write_lock:
                while True:
                    if self.is_writerable():
                        data = self._get_write_data()
                        if data:
                            ret = self._write_socket(data.data)
                            if ret < 1:
                                break
                        else:
                            break
                    else:
                        break
        if self._write_timer_sensor:
            self._write_timer_sensor.set_timer2(350, 1)

    # ------------------------------------------------------------------ #
    # 소켓 상태 확인
    # ------------------------------------------------------------------ #
    def is_connect(self) -> bool:
        """C++ IsConnect() 대응."""
        return self._fd != -1

    def is_writerable(self, sec: int = 0, micro_sec: int = -1) -> bool:
        """C++ IsWriterable() / select() FD_SET 대응."""
        if micro_sec == -1:
            micro_sec = self._writerable_check_timeout
        timeout = sec + micro_sec / 1_000_000
        try:
            _, w, _ = _select.select([], [self._sock], [], timeout)
            return bool(w)
        except OSError as e:
            self.set_obj_err_msg('is_writerable error: %s', e)
            return False

    def is_readerable(self, sec: int = 0, micro_sec: int = 100_000) -> bool:
        """C++ IsReaderable() 대응."""
        self.disable()
        timeout = sec + micro_sec / 1_000_000
        try:
            r, _, _ = _select.select([self._sock], [], [], timeout)
            self.enable()
            return bool(r)
        except OSError:
            self.enable()
            return False

    # ------------------------------------------------------------------ #
    # 소켓 옵션
    # ------------------------------------------------------------------ #
    def get_peer_ip(self) -> str:
        return self._peer_ip

    def get_peer_port(self) -> int:
        return self._port_no

    def get_port_no(self) -> int:
        return self._port_no

    def set_writerable_check(self, flag: bool) -> None:
        """C++ SetWriterableCheck() 대응."""
        self._writerable_check = flag
        if flag and self._write_timer_sensor is None:
            from fr_socket_sensor_timer import FrSocketSensorTimer
            self._write_timer_sensor = FrSocketSensorTimer(self)
            self._write_timer_sensor.set_parent_sensor(self)
            self._write_timer_sensor.set_timer(1, 1)
        elif not flag and self._write_timer_sensor:
            self._write_timer_sensor = None

    def set_write_check_time_out(self, micro_sec: int) -> None:
        self._writerable_check_timeout = micro_sec

    def get_write_check_time_out(self) -> int:
        return self._writerable_check_timeout

    def set_max_data_buf_size(self, size: int) -> None:
        self._max_data_buf_size = size

    def get_cur_send_sock_buf(self) -> int:
        """C++ GetCurSendSockBuf() / getsockopt(SO_SNDBUF) 대응."""
        try:
            return self._sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
        except OSError as e:
            self.set_obj_err_msg('getsockopt SO_SNDBUF error: %s', e)
            return -1

    def get_cur_recv_sock_buf(self) -> int:
        """C++ GetCurRecvSockBuf() / getsockopt(SO_RCVBUF) 대응."""
        try:
            return self._sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
        except OSError as e:
            self.set_obj_err_msg('getsockopt SO_RCVBUF error: %s', e)
            return -1

    def set_send_sock_buf(self, size: int) -> bool:
        try:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, size)
            return True
        except OSError as e:
            self.set_obj_err_msg('setsockopt SO_SNDBUF error: %s', e)
            return False

    def set_recv_sock_buf(self, size: int) -> bool:
        try:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, size)
            return True
        except OSError as e:
            self.set_obj_err_msg('setsockopt SO_RCVBUF error: %s', e)
            return False

    def get_max_can_send_sock_buf(self) -> int:
        """C++ GetMaxCanSendSockBuf() 대응. 최대 송신 버퍼 탐색."""
        if FrSocketSensor.system_max_send_sock_buf > 0:
            return FrSocketSensor.system_max_send_sock_buf
        return self._probe_max_buf(send=True)

    def get_max_can_recv_sock_buf(self) -> int:
        """C++ GetMaxCanRecvSockBuf() 대응. 최대 수신 버퍼 탐색."""
        if FrSocketSensor.system_max_recv_sock_buf > 0:
            return FrSocketSensor.system_max_recv_sock_buf
        return self._probe_max_buf(send=False)

    def get_to_read_size(self) -> int:
        """C++ GetToReadSize() / ioctl(FIONREAD) 대응."""
        import fcntl, array, termios
        try:
            buf = array.array('I', [0])
            fcntl.ioctl(self._fd, termios.FIONREAD, buf)
            return buf[0]
        except OSError as e:
            self.set_obj_err_msg('get_to_read_size error: %s', e)
            return -1

    def get_timer_count(self) -> int:
        return 0

    @staticmethod
    def shut_down(sock: socket.socket,
                  how: int = socket.SHUT_RDWR) -> int:
        """C++ static ShutDown(int Fd, int How) 대응."""
        try:
            sock.shutdown(how)
            return 0
        except OSError:
            return -1

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #
    def _set_sock_opt(self) -> bool:
        """C++ _SetSockOpt() 대응."""
        if not self.set_recv_sock_buf(_DEFAULT_SOCK_BUF_SIZE):
            return False
        if not self.set_send_sock_buf(_DEFAULT_SOCK_BUF_SIZE):
            return False
        if self._socket_type != socket.SOCK_DGRAM:
            try:
                self._sock.setsockopt(
                    socket.SOL_SOCKET, socket.SO_LINGER,
                    __import__('struct').pack('ii', 0, 0))
            except OSError as e:
                self.set_obj_err_msg('setsockopt SO_LINGER error: %s', e)
                return False
        return True

    def _set_session_time(self) -> None:
        """C++ _SetSessionTime() 대응."""
        now = datetime.datetime.now()
        self._session_time        = now.strftime('%Y/%m/%d %H:%M:%S')
        self._session_time_detail = now.microsecond // 1000

    def _probe_max_buf(self, send: bool) -> int:
        """C++ GetMaxCanSend/RecvSockBuf() 탐색 루프 공통화."""
        getter = self.get_cur_send_sock_buf if send else self.get_cur_recv_sock_buf
        setter = self.set_send_sock_buf     if send else self.set_recv_sock_buf

        cur = getter()
        if cur < 0:
            return -1

        test = 4096
        while test <= _MAX_SOCK_BUF_SIZE:
            if not setter(test):
                test -= 512
                break
            test += 512

        result = max(0, test - 100)
        setter(cur)

        if send:
            if result > FrSocketSensor.system_max_send_sock_buf:
                FrSocketSensor.system_max_send_sock_buf = result
        else:
            if result > FrSocketSensor.system_max_recv_sock_buf:
                FrSocketSensor.system_max_recv_sock_buf = result
        return result

    def _data_dump(self, data: bytes) -> None:
        """C++ DataDump() 대응. 디버그용 데이터 덤프."""
        chunk = data[:_MAX_DATADUMP_SIZE]
        readable = ''.join(
            '<N>' if b == 0 else chr(b) for b in chunk)
        import logging
        logging.getLogger(__name__).debug(
            '--- DataDump (len=%d) ---\n[%s]', len(data), readable)