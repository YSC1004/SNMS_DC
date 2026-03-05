# -*- coding: utf-8 -*-
"""
frFtpSession.h / frFtpSession.C  →  fr_ftp_session.py
Python 3.11.10 버전

변환 설계:
  frFtpSession     → FrFtpSession

C++ → Python 주요 변환 포인트:
  frSocket*                    → socket.socket (직접 사용, FrSocket 래핑)
  char m_LastResponse[BUFSIZ]  → _last_response : str
  sprintf / strcpy / strncpy   → str 포맷 / 대입 / 슬라이싱
  sscanf(pasv, ...)            → re.findall()
  fopen / fread / fwrite       → open() / file.read() / file.write()
  DELETE_INSTANCE(x)           → x = None
  RET_ERROR(inst, msg)         → _require_ctl() 헬퍼
  IsReaderable / IsWriterable  → select.select()
  strstr / strcmp / strncmp    → in / == / startswith()
  frStringVector               → list[str]
  MsgTokenizeString            → _tokenize()
  FR_FTP_DATA_MODE enum        → DataMode(IntEnum)
  FR_FTP_CON_MODE  enum        → ConMode(IntEnum)
  FR_FTP_SYS_TYPE  enum        → SysType(IntEnum)
  Active 모드 PORT/accept      → socket listen/accept
  Passive 모드 PASV            → PASV 응답 파싱 후 connect

변경 이력:
  v1 - 초기 변환
"""

import logging
import os
import re
import select as _select
import socket
import struct
from enum import IntEnum
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────────────────────────────
_FTPLIB_BUFSIZ         = 30000
_TMP_BUFSIZ            = 1024
_ACTIVE_ACCEPT_TIMEOUT = 20   # sec

_FTP_DATA_ASCII  = 'A'
_FTP_DATA_BINARY = 'I'


# ─────────────────────────────────────────────────────────────────────────────
# 열거형
# ─────────────────────────────────────────────────────────────────────────────
class DataMode(IntEnum):
    ASCII  = 0
    BINARY = 1

class ConMode(IntEnum):
    PASSIVE = 0
    ACTIVE  = 1

class SysType(IntEnum):
    UNKNOWN = 0
    UNIX    = 1
    NT      = 2


# ─────────────────────────────────────────────────────────────────────────────
# FrFtpSession
# ─────────────────────────────────────────────────────────────────────────────
class FrFtpSession:
    """
    C++ frFtpSession 대응 클래스.
    FTP 제어/전송 세션을 socket.socket 으로 직접 구현.
    frSocket → socket.socket 으로 대체하여 이벤트 루프 의존성 제거.
    """

    def __init__(self) -> None:
        self._user:        str  = ''
        self._password:    str  = ''
        self._host:        str  = ''
        self._port:        int  = 21
        self._debug:       bool = False
        self._con_mode:    ConMode  = ConMode.PASSIVE
        self._sys_type:    SysType  = SysType.UNKNOWN
        self._last_response: str   = ''
        self._accept_timeout: int  = _ACTIVE_ACCEPT_TIMEOUT

        self._ctl_sock:  Optional[socket.socket] = None   # 제어 세션
        self._trf_sock:  Optional[socket.socket] = None   # 전송 세션
        self._acc_sock:  Optional[socket.socket] = None   # Active 모드 acceptor

    def __del__(self) -> None:
        if self._ctl_sock:
            self.cmd_quit()

    # ------------------------------------------------------------------ #
    # 공개 API
    # ------------------------------------------------------------------ #
    def connect(self, user: str, passwd: str, ip: str,
                port: int = 21,
                con_mode: ConMode = ConMode.PASSIVE) -> bool:
        """C++ Connect() 대응."""
        self._user     = user
        self._password = passwd
        self._host     = ip
        self._port     = port
        self._con_mode = con_mode

        self._ctl_sock = self._trf_sock = self._acc_sock = None

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, port))
            self._ctl_sock = sock
        except OSError as e:
            self._last_response = f"Can't connect({ip}:{port})"
            return False

        return self._wait_response('2')

    def login(self, user: str = '', passwd: str = '') -> bool:
        """C++ Login() 대응."""
        if user:   self._user     = user
        if passwd: self._password = passwd

        if not self._send_ftp_cmd(f'USER {self._user}', '3'):
            if self._last_response.startswith('2'):
                return True
            return False

        ret = self._send_ftp_cmd(f'PASS {self._password}', '2')

        if ret and self._sys_type == SysType.UNKNOWN:
            sys_buf = self.cmd_sys_type()
            if sys_buf:
                if 'UNIX' in sys_buf:
                    self._sys_type = SysType.UNIX
                elif 'Windows' in sys_buf:
                    self._sys_type = SysType.NT
        return ret

    def get_last_response(self) -> str:
        return self._last_response

    def set_debug_on_off(self, on_off: bool) -> None:
        self._debug = on_off

    # ── FTP 명령 ─────────────────────────────────────────────────────── #
    def cmd_nlist(self, path: str = '', filename: str = '') \
            -> tuple[list[str], list[str]] | tuple[None, None]:
        """C++ Cmd_NList(FileList, DirList) 대응. 반환: (files, dirs)"""
        if not self._require_ctl(): return None, None
        if self._sys_type == SysType.UNIX:
            return self._cmd_nlist_unix(path, filename)
        elif self._sys_type == SysType.NT:
            return self._cmd_nlist_nt(path, filename)
        else:
            return self._cmd_nlist_unknown(path, filename)

    def cmd_nlist_files(self, path: str = '',
                        filename: str = '') -> Optional[list[str]]:
        """C++ Cmd_NList(FileList) 파일만 반환 버전 대응."""
        if not self._require_ctl(): return None
        result = self._send_list_cmd('NLST', path, filename)
        return result

    def cmd_dir(self, path: str = '',
                filename: str = '') -> Optional[list[str]]:
        """C++ Cmd_Dir() 대응."""
        if not self._require_ctl(): return None
        return self._send_list_cmd('LIST', path, filename)

    def cmd_cdup(self) -> bool:
        return self._require_ctl() and self._send_ftp_cmd('CDUP', '2')

    def cmd_rmdir(self, path: str) -> bool:
        return self._require_ctl() and self._send_ftp_cmd(f'RMD {path}', '2')

    def cmd_chdir(self, path: str) -> bool:
        return self._require_ctl() and self._send_ftp_cmd(f'CWD {path}', '2')

    def cmd_mkdir(self, path: str) -> bool:
        return self._require_ctl() and self._send_ftp_cmd(f'MKD {path}', '2')

    def cmd_file_delete(self, filename: str) -> bool:
        return self._require_ctl() and self._send_ftp_cmd(f'DELE {filename}', '2')

    def cmd_file_rename(self, src: str, dest: str) -> bool:
        if not self._require_ctl(): return False
        if src == dest: return True
        return (self._send_ftp_cmd(f'RNFR {src}', '3') and
                self._send_ftp_cmd(f'RNTO {dest}', '2'))

    def cmd_site(self, cmd: str) -> bool:
        return self._require_ctl() and self._send_ftp_cmd(f'SITE {cmd}', '2')

    def cmd_sys_type(self) -> Optional[str]:
        """C++ Cmd_SysType() 대응. 시스템 타입 문자열 반환."""
        if not self._require_ctl(): return None
        if not self._send_ftp_cmd('SYST', '2'): return None
        parts = self._last_response[4:].split()
        return parts[0] if parts else ''

    def cmd_pwd(self) -> Optional[str]:
        """C++ Cmd_Pwd() 대응."""
        if not self._require_ctl(): return None
        if not self._send_ftp_cmd('PWD', '2'): return None
        m = re.search(r'"([^"]*)"', self._last_response)
        return m.group(1) if m else None

    def cmd_file_size(self, path: str,
                      data_mode: DataMode = DataMode.ASCII) -> Optional[int]:
        """C++ Cmd_FileSize() 대응. 파일 크기(int) 반환."""
        if not self._require_ctl(): return None
        if not self._send_ftp_cmd(f'SIZE {path}', '2'): return None
        parts = self._last_response.split()
        if len(parts) < 2: return None
        try:
            return int(parts[-1])
        except ValueError:
            return None

    def cmd_mod_date(self, path: str) -> Optional[str]:
        """C++ Cmd_ModDate() 대응."""
        if not self._require_ctl(): return None
        if not self._send_ftp_cmd(f'MDTM {path}', '2'): return None
        return self._last_response[4:].strip()

    def cmd_quit(self) -> bool:
        """C++ Cmd_Quit() 대응."""
        if not self._ctl_sock: return False
        self._send_ftp_cmd('QUIT', '2')
        self._ctl_sock = self._trf_sock = self._acc_sock = None
        return True

    def cmd_file_get(self, remote_file: str, local_file: str,
                     data_mode: DataMode = DataMode.BINARY) -> bool:
        """C++ Cmd_FileGet() 대응."""
        if not self._require_ctl(): return False

        mode_char = _FTP_DATA_BINARY if data_mode == DataMode.BINARY else _FTP_DATA_ASCII
        open_mode = 'wb' if data_mode == DataMode.BINARY else 'w'

        if not self._send_ftp_cmd(f'TYPE {mode_char}', '2'): return False
        if not self._open_ftp_port(): return False
        if not self._send_ftp_cmd(f'RETR {remote_file}', '1'):
            self._handle_trf_fail()
            return False
        if self._con_mode == ConMode.ACTIVE and not self._get_accept_session():
            return False

        try:
            encoding = None if data_mode == DataMode.BINARY else 'utf-8'
            with open(local_file, open_mode, encoding=encoding) as fp:
                while True:
                    if not self._is_readerable(self._trf_sock, 5): break
                    chunk = self._trf_sock.recv(_FTPLIB_BUFSIZ)
                    if not chunk: break
                    if data_mode == DataMode.ASCII:
                        fp.write(chunk.decode('utf-8', errors='replace').replace('\r', ''))
                    else:
                        fp.write(chunk)
        except OSError as e:
            self._last_response = f'[{e}][{local_file}]'
            self._session_close(close_trf=True, wait_msg=True)
            return False

        self._session_close(close_trf=True, wait_msg=True)
        return True

    def cmd_file_put(self, local_file: str, remote_file: str,
                     data_mode: DataMode = DataMode.BINARY) -> bool:
        """C++ Cmd_FilePut() 대응."""
        if not self._require_ctl(): return False

        mode_char = _FTP_DATA_BINARY if data_mode == DataMode.BINARY else _FTP_DATA_ASCII
        open_mode = 'rb' if data_mode == DataMode.BINARY else 'r'

        if not self._send_ftp_cmd(f'TYPE {mode_char}', '2'): return False
        if not self._open_ftp_port(): return False
        if not self._send_ftp_cmd(f'STOR {remote_file}', '1'):
            self._handle_trf_fail()
            return False
        if self._con_mode == ConMode.ACTIVE and not self._get_accept_session():
            return False

        ret = True
        encoding = None if data_mode == DataMode.BINARY else 'utf-8'
        try:
            with open(local_file, open_mode, encoding=encoding) as fp:
                while True:
                    if not self._is_writerable(self._trf_sock, 5):
                        logger.error("Can't put data, write buf full, 5 sec")
                        ret = False
                        break
                    chunk = fp.read(_FTPLIB_BUFSIZ)
                    if not chunk: break
                    data = chunk if isinstance(chunk, bytes) else chunk.encode('utf-8')
                    if self._trf_sock.sendall(data) is not None:
                        ret = False
                        break
        except OSError as e:
            self._last_response = f'[{e}][{local_file}]'
            ret = False

        self._session_close(close_trf=True, wait_msg=True)
        return ret

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #
    def _require_ctl(self) -> bool:
        """C++ RET_ERROR(m_FtpCtlSession, ...) 대응."""
        if self._ctl_sock is None:
            self._last_response = 'session is invalid(NULL)'
            return False
        return True

    def _send_ftp_cmd(self, cmd: str, expected: str) -> bool:
        """C++ SendFtpCmd() 대응."""
        if self._debug:
            logger.debug('CMD [%s]', cmd)
        try:
            self._ctl_sock.sendall(f'{cmd}\r\n'.encode())
        except OSError as e:
            logger.error('send ftp command error: %s', e)
            self._ctl_sock = None
            return False

        ret = self._wait_response(expected)
        if not ret and cmd != 'QUIT':
            logger.error('WaitResponse fail: expect(%s), got[%s]', expected, self._last_response)
        return ret

    def _wait_response(self, expected: str) -> bool:
        """C++ WaitResponse(char C) 대응."""
        msg = self._read_msg(self._ctl_sock, timeout=2)
        if msg is None: return False

        lines = self._msg_to_lines(msg)
        if not lines: return False

        self._last_response = lines[0]

        # 멀티라인 응답 처리 (코드 + '-' 시작)
        if len(self._last_response) > 3 and self._last_response[3] == '-':
            match_prefix = self._last_response[:3] + ' '
            for line in lines[1:]:
                self._last_response = line
                if line.startswith(match_prefix):
                    break

        return self._last_response.startswith(expected)

    def _read_msg(self, sock: socket.socket, timeout: int = 3) -> Optional[str]:
        """C++ ReadMsg() 대응."""
        if sock is None:
            self._last_response = 'session is invalid(NULL)'
            return None
        buf = b''
        cur_timeout = timeout
        while True:
            if not self._is_readerable(sock, cur_timeout, 50_000):
                break
            try:
                chunk = sock.recv(_TMP_BUFSIZ)
            except OSError:
                return None
            if not chunk:
                return None
            buf += chunk
            cur_timeout = 1
        return buf.decode('utf-8', errors='replace')

    def _session_close(self, close_trf: bool, wait_msg: bool) -> None:
        """C++ SessionClose() 대응."""
        if wait_msg and self._ctl_sock:
            msg = self._read_msg(self._ctl_sock, timeout=1)
            if msg:
                self._last_response = msg
        if close_trf and self._trf_sock:
            try: self._trf_sock.close()
            except OSError: pass
            self._trf_sock = None

    def _open_ftp_port(self) -> bool:
        """C++ OpenFtpPort() 대응."""
        if self._con_mode == ConMode.PASSIVE:
            return self._open_passive()
        return self._open_active()

    def _open_passive(self) -> bool:
        """PASV 명령으로 전송 포트 연결."""
        if not self._send_ftp_cmd('PASV', '2'): return False
        m = re.search(r'\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)', self._last_response)
        if not m:
            logger.error('PASV parse error: %s', self._last_response)
            return False
        nums = [int(x) for x in m.groups()]
        ip   = '.'.join(str(n) for n in nums[:4])
        port = nums[4] * 256 + nums[5]
        try:
            self._trf_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._trf_sock.connect((ip, port))
            return True
        except OSError as e:
            logger.error('PASV connect error [%s:%d]: %s', ip, port, e)
            self._trf_sock = None
            return False

    def _open_active(self) -> bool:
        """PORT 명령으로 수신 소켓 준비."""
        try:
            local_ip = self._ctl_sock.getsockname()[0]
            acc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            acc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            acc.bind((local_ip, 0))
            acc.listen(1)
            _, port = acc.getsockname()
            ip_parts = local_ip.split('.')
            p1, p2 = port >> 8, port & 0xFF
            port_str = ','.join(ip_parts) + f',{p1},{p2}'
            if not self._send_ftp_cmd(f'PORT {port_str}', '2'):
                acc.close()
                return False
            self._acc_sock = acc
            return True
        except OSError as e:
            logger.error('PORT error: %s', e)
            return False

    def _get_accept_session(self) -> bool:
        """C++ GetAcceptSession() 대응."""
        self._trf_sock = None
        if not self._is_readerable(self._acc_sock, self._accept_timeout):
            self._last_response = f'wait timeout {self._accept_timeout}s (ACTIVE)'
            self._acc_sock = None
            return False
        try:
            conn, _ = self._acc_sock.accept()
            self._trf_sock = conn
        except OSError as e:
            self._last_response = f'accept error: {e}'
            self._trf_sock = None
            self._acc_sock = None
            return False
        self._acc_sock = None
        return True

    def _handle_trf_fail(self) -> None:
        """전송 명령 실패 시 공통 처리."""
        if self._trf_sock:
            wait = self._last_response.startswith('5')
            self._session_close(close_trf=True, wait_msg=wait)
        self._acc_sock = None

    def _send_list_cmd(self, ftp_cmd: str, path: str,
                       filename: str) -> Optional[list[str]]:
        """LIST / NLST 공통 처리."""
        if not self._send_ftp_cmd('TYPE A', '2'): return None
        hint = ''
        if path:     hint = path.rstrip('/') + '/'
        if filename: hint += filename
        cmd = f'{ftp_cmd} {hint}' if hint else ftp_cmd
        if not self._open_ftp_port(): return None
        if not self._send_ftp_cmd(cmd, '1'):
            self._handle_trf_fail()
            return None
        if self._con_mode == ConMode.ACTIVE and not self._get_accept_session():
            return None
        msg = self._read_msg(self._trf_sock) or ''
        self._session_close(close_trf=True, wait_msg=True)
        return self._msg_to_lines(msg)

    # ── NList 파싱 ───────────────────────────────────────────────────── #
    def _cmd_nlist_nt(self, path: str, filename: str) \
            -> tuple[list[str], list[str]]:
        files, dirs = [], []
        total = self.cmd_dir(path, filename) or []
        for line in total:
            parts = self._tokenize(line)
            if len(parts) != 4:
                continue
            if '<DIR>' in line:
                dirs.append(parts[3])
            else:
                files.append(parts[3])
        return files, dirs

    def _cmd_nlist_unix(self, path: str, filename: str) \
            -> tuple[list[str], list[str]]:
        files, dirs = [], []
        total = self.cmd_dir(path, filename) or []
        for line in total:
            is_link = '->' in line
            if is_link:
                line = line.replace('->', ' ')
            parts = self._tokenize(line)
            if len(parts) < 9:
                continue
            if line.startswith('-'):
                files.append(parts[8])
            else:
                if is_link and len(parts) == 10:
                    dirs.append(parts[9])
                else:
                    dirs.append(parts[8])
        return files, dirs

    def _cmd_nlist_unknown(self, path: str, filename: str) \
            -> tuple[list[str], list[str]]:
        files = self.cmd_nlist_files(path, filename)
        if files is None: return None, None
        dirs = []
        total = self.cmd_dir(path, filename) or []
        for line in total:
            if line.startswith('-'): continue
            if line.startswith('d') or '<DIR>' in line:
                for i, f in enumerate(files):
                    if line.endswith(f):
                        dirs.append(files.pop(i))
                        break
        return files, dirs

    # ── 유틸 ─────────────────────────────────────────────────────────── #
    @staticmethod
    def _msg_to_lines(msg: str) -> list[str]:
        """C++ MsgToLine() 대응."""
        return [l for l in msg.replace('\r', '').split('\n') if l]

    @staticmethod
    def _tokenize(line: str, delimiter: str = ' ') -> list[str]:
        """C++ MsgTokenizeString() 대응."""
        if delimiter == ' ':
            return line.split()
        return [p.strip() for p in line.split(delimiter)]

    @staticmethod
    def _is_readerable(sock: Optional[socket.socket],
                       sec: int = 0, micro_sec: int = 100_000) -> bool:
        if sock is None: return False
        timeout = sec + micro_sec / 1_000_000
        r, _, _ = _select.select([sock], [], [], timeout)
        return bool(r)

    @staticmethod
    def _is_writerable(sock: Optional[socket.socket],
                       sec: int = 0, micro_sec: int = 100_000) -> bool:
        if sock is None: return False
        timeout = sec + micro_sec / 1_000_000
        _, w, _ = _select.select([], [sock], [], timeout)
        return bool(w)