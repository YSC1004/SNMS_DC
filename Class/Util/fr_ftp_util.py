"""
frFtpUtil.h / frFtpUtil.C  →  fr_ftp_util.py

변환 설계:
  C++ 원본은 raw 소켓으로 FTP 프로토콜을 직접 구현했으나,
  Python 에서는 표준 라이브러리 ftplib.FTP 를 백엔드로 사용.
  외부 인터페이스(메서드명·시그니처·반환값)는 C++ 원본과 동일하게 유지.

매핑:
  NetBuf (소켓 버퍼 구조체)  → 내부적으로 ftplib.FTP 가 대체, 외부 노출 최소화
  FtpCallback                 → Callable[[int, Any], None]
  FtpConnect()                → ftp_connect()
  FtpLogin()                  → ftp_login()
  FtpQuit()                   → ftp_quit()
  FtpClose()                  → ftp_close()
  FtpGet/Put                  → ftp_get / ftp_put  (binary/ascii 모드 지원)
  FtpDir/Nlst                 → ftp_dir / ftp_nlst (list[str] 반환)
  FtpMkdir/Chdir/CDUp/Rmdir   → ftp_mkdir / ftp_chdir / ftp_cdup / ftp_rmdir
  FtpPwd                      → ftp_pwd
  FtpSize                     → ftp_size
  FtpDelete / FtpRename       → ftp_delete / ftp_rename
  FtpSite / FtpSysType        → ftp_site / ftp_sys_type
  FtpOptions                  → ftp_options  (CONNMODE / IDLETIME 등)
  FtpLastResponse             → ftp_last_response
  SetDebugLevel/GetDebugLevel → set_debug_level / get_debug_level

상수 매핑:
  FTPLIB_ASCII / FTPLIB_IMAGE  → 'A' / 'I'  (C++ 원본 그대로)
  FTPLIB_PASSIVE / FTPLIB_PORT → ConnMode.PASSIVE / ConnMode.PORT
  FTPLIB_DIR / FILE_READ 등    → AccessType enum
"""

import ftplib
import io
import os
import logging
from enum import IntEnum
from typing import Callable, Optional, Any

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# 상수 (C++ #define 대응)
# ══════════════════════════════════════════════════════════════════════════════
FTPLIB_ASCII  = 'A'
FTPLIB_IMAGE  = 'I'
FTPLIB_TEXT   = FTPLIB_ASCII
FTPLIB_BINARY = FTPLIB_IMAGE

BUFSIZE = 1024


class ConnMode(IntEnum):
    PASSIVE = 1
    PORT    = 2


class AccessType(IntEnum):
    DIR          = 1   # NLST
    DIR_VERBOSE  = 2   # LIST
    FILE_READ    = 3   # RETR
    FILE_WRITE   = 4   # STOR


class FtpOption(IntEnum):
    CONNMODE     = 1
    CALLBACK     = 2
    IDLETIME     = 3
    CALLBACKARG  = 4
    CALLBACKBYTES= 5


# ══════════════════════════════════════════════════════════════════════════════
# FtpUtil  ←  FtpUtil
# ══════════════════════════════════════════════════════════════════════════════
class FtpUtil:
    """
    FTP 유틸리티 클래스 (frFtpUtil 대응).
    ftplib.FTP 를 래핑하여 C++ 원본과 동일한 인터페이스를 제공.
    """

    def __init__(self):
        self._user:      str               = ""
        self._password:  str               = ""
        self._host:      str               = ""
        self._port:      int               = 21
        self._debug:     int               = 0
        self._conn_mode: ConnMode          = ConnMode.PASSIVE
        self._ftp:       Optional[ftplib.FTP] = None
        self._last_resp: str               = ""
        # 콜백 관련 (FtpOptions 대응)
        self._idle_cb:   Optional[Callable]= None
        self._idle_arg:  Any               = None
        self._idle_sec:  float             = 0.0
        self._cb_bytes:  int               = 0

    def __del__(self):
        if self._ftp:
            self.ftp_quit()

    # ------------------------------------------------------------------ #
    # 디버그 레벨
    # ------------------------------------------------------------------ #

    def set_debug_level(self, level: int) -> None:
        """SetDebugLevel() 대응."""
        self._debug = level
        if self._ftp:
            self._ftp.set_debuglevel(level)

    def get_debug_level(self) -> int:
        """GetDebugLevel() 대응."""
        return self._debug

    # ------------------------------------------------------------------ #
    # 연결 / 로그인 / 종료
    # ------------------------------------------------------------------ #

    def ftp_connect(
        self,
        user:       str,
        passwd:     str,
        ip_address: str,
        port:       int = 21,
        mode:       int = 0,   # 0=Passive(기본), 1=Port
    ) -> bool:
        """
        FTP 서버에 연결하고 로그인까지 수행 (FtpConnect).
        mode: 0 또는 ConnMode.PASSIVE = Passive, ConnMode.PORT = Port
        """
        self._user     = user
        self._password = passwd
        self._host     = ip_address
        self._port     = port
        self._conn_mode = ConnMode.PORT if mode == int(ConnMode.PORT) else ConnMode.PASSIVE

        try:
            self._ftp = ftplib.FTP()
            self._ftp.set_debuglevel(self._debug)
            self._ftp.connect(host=ip_address, port=port, timeout=30)
            self._last_resp = self._ftp.getwelcome()

            if self._conn_mode == ConnMode.PASSIVE:
                self._ftp.set_pasv(True)
            else:
                self._ftp.set_pasv(False)

            return self.ftp_login(user, passwd)

        except (ftplib.all_errors, OSError) as e:
            logger.error("ftp_connect failed [%s:%d]: %s", ip_address, port, e)
            self._last_resp = str(e)
            self._ftp = None
            return False

    def ftp_login(self, user: str = "", passwd: str = "") -> bool:
        """
        FTP 로그인 (FtpLogin).
        인자가 비어 있으면 connect 시 저장된 값 사용.
        """
        if user:   self._user     = user
        if passwd: self._password = passwd
        try:
            self._ftp.login(user=self._user, passwd=self._password)
            self._last_resp = self._ftp.lastresp
            return True
        except ftplib.all_errors as e:
            logger.error("ftp_login failed: %s", e)
            self._last_resp = str(e)
            return False

    def ftp_quit(self) -> None:
        """연결을 정상 종료한다 (FtpQuit / QUIT 명령)."""
        if self._ftp:
            try:
                self._ftp.quit()
            except Exception:
                pass
            finally:
                self._ftp = None

    def ftp_close(self) -> bool:
        """연결을 강제 종료한다 (FtpClose)."""
        if self._ftp:
            try:
                self._ftp.close()
                return True
            except Exception as e:
                logger.error("ftp_close failed: %s", e)
            finally:
                self._ftp = None
        return False

    def ftp_last_response(self) -> str:
        """마지막 서버 응답 문자열 반환 (FtpLastResponse)."""
        return self._last_resp

    # ------------------------------------------------------------------ #
    # 디렉토리 조작
    # ------------------------------------------------------------------ #

    def ftp_mkdir(self, path: str) -> bool:
        """원격 디렉토리 생성 (FtpMkdir / MKD)."""
        return self._cmd(self._ftp.mkd, path)

    def ftp_chdir(self, path: str) -> bool:
        """원격 디렉토리 이동 (FtpChdir / CWD)."""
        return self._cmd(self._ftp.cwd, path)

    def ftp_cdup(self) -> bool:
        """상위 디렉토리로 이동 (FtpCDUp / CDUP)."""
        return self._cmd(self._ftp.cwd, "..")

    def ftp_rmdir(self, path: str) -> bool:
        """원격 디렉토리 삭제 (FtpRmdir / RMD)."""
        return self._cmd(self._ftp.rmd, path)

    def ftp_pwd(self) -> Optional[str]:
        """현재 원격 디렉토리 경로 반환 (FtpPwd / PWD). 실패 시 None."""
        try:
            path = self._ftp.pwd()
            self._last_resp = self._ftp.lastresp
            return path
        except ftplib.all_errors as e:
            logger.error("ftp_pwd failed: %s", e)
            self._last_resp = str(e)
            return None

    # ------------------------------------------------------------------ #
    # 파일 조작
    # ------------------------------------------------------------------ #

    def ftp_delete(self, filename: str) -> bool:
        """원격 파일 삭제 (FtpDelete / DELE)."""
        return self._cmd(self._ftp.delete, filename)

    def ftp_rename(self, src: str, dst: str) -> bool:
        """원격 파일 이름 변경 (FtpRename / RNFR+RNTO)."""
        return self._cmd(self._ftp.rename, src, dst)

    def ftp_size(self, path: str, mode: str = FTPLIB_BINARY) -> Optional[int]:
        """
        원격 파일 크기 반환 (FtpSize / SIZE).
        실패 시 None.
        C++ 원본 int* Size 출력 인자 → 반환값으로 변경.
        """
        try:
            self._ftp.sendcmd(f"TYPE {mode}")
            size = self._ftp.size(path)
            self._last_resp = self._ftp.lastresp
            return size
        except ftplib.all_errors as e:
            logger.error("ftp_size failed [%s]: %s", path, e)
            self._last_resp = str(e)
            return None

    def ftp_mod_date(self, path: str) -> Optional[str]:
        """
        원격 파일 수정 날짜 반환 (FtpModDate / MDTM).
        'YYYYMMDDHHmmss' 형식 문자열. 실패 시 None.
        C++ 원본 char* Dt 출력 인자 → 반환값으로 변경.
        """
        try:
            resp = self._ftp.sendcmd(f"MDTM {path}")
            self._last_resp = resp
            # 응답 형식: "213 YYYYMMDDHHmmss"
            return resp[4:].strip() if resp.startswith("213") else None
        except ftplib.all_errors as e:
            logger.error("ftp_mod_date failed [%s]: %s", path, e)
            return None

    # ------------------------------------------------------------------ #
    # 파일 전송
    # ------------------------------------------------------------------ #

    def ftp_get(
        self,
        output_file: str,
        remote_path: str,
        mode: str = FTPLIB_BINARY,
    ) -> bool:
        """
        원격 파일을 로컬로 다운로드 (FtpGet / RETR).
        mode: FTPLIB_ASCII('A') 또는 FTPLIB_BINARY('I').
        """
        try:
            open_mode = "w" if mode == FTPLIB_ASCII else "wb"
            with open(output_file, open_mode) as f:
                if mode == FTPLIB_ASCII:
                    def _write_line(line: str):
                        f.write(line + "\n")
                    self._ftp.retrlines(f"RETR {remote_path}", _write_line)
                else:
                    self._ftp.retrbinary(f"RETR {remote_path}", f.write)
            self._last_resp = self._ftp.lastresp
            return True
        except (ftplib.all_errors, OSError) as e:
            logger.error("ftp_get failed [%s → %s]: %s", remote_path, output_file, e)
            self._last_resp = str(e)
            return False

    def ftp_put(
        self,
        input_file: str,
        remote_path: str,
        mode: str = FTPLIB_BINARY,
    ) -> bool:
        """
        로컬 파일을 원격으로 업로드 (FtpPut / STOR).
        mode: FTPLIB_ASCII('A') 또는 FTPLIB_BINARY('I').
        """
        try:
            open_mode = "r" if mode == FTPLIB_ASCII else "rb"
            with open(input_file, open_mode) as f:
                if mode == FTPLIB_ASCII:
                    self._ftp.storlines(f"STOR {remote_path}", f)
                else:
                    self._ftp.storbinary(f"STOR {remote_path}", f)
            self._last_resp = self._ftp.lastresp
            return True
        except (ftplib.all_errors, OSError) as e:
            logger.error("ftp_put failed [%s → %s]: %s", input_file, remote_path, e)
            self._last_resp = str(e)
            return False

    # ------------------------------------------------------------------ #
    # 목록 조회
    # ------------------------------------------------------------------ #

    def ftp_nlst(
        self,
        path:        Optional[str] = None,
        filename:    Optional[str] = None,
        output_file: Optional[str] = None,
    ) -> Optional[list[str]]:
        """
        NLST 명령으로 파일명 목록 반환 (FtpNlst).
        output_file 지정 시 파일에도 저장.
        실패 시 None.
        """
        return self._list_transfer("NLST", path, filename, output_file)

    def ftp_dir(
        self,
        path:        Optional[str] = None,
        filename:    Optional[str] = None,
        output_file: Optional[str] = None,
    ) -> Optional[list[str]]:
        """
        LIST 명령으로 상세 목록 반환 (FtpDir).
        output_file 지정 시 파일에도 저장.
        실패 시 None.
        """
        return self._list_transfer("LIST", path, filename, output_file)

    # ------------------------------------------------------------------ #
    # 기타 명령
    # ------------------------------------------------------------------ #

    def ftp_site(self, cmd: str) -> bool:
        """SITE 명령 전송 (FtpSite)."""
        return self._cmd(self._ftp.sendcmd, f"SITE {cmd}")

    def ftp_sys_type(self) -> Optional[str]:
        """
        SYST 명령으로 서버 시스템 타입 반환 (FtpSysType).
        C++ char* Buf 출력 인자 → 반환값으로 변경.
        """
        try:
            resp = self._ftp.sendcmd("SYST")
            self._last_resp = resp
            # "215 UNIX Type: L8" 형식에서 첫 단어 추출
            parts = resp[4:].split()
            return parts[0] if parts else resp[4:].strip()
        except ftplib.all_errors as e:
            logger.error("ftp_sys_type failed: %s", e)
            return None

    def ftp_options(self, opt: int, val) -> bool:
        """
        FTP 옵션 설정 (FtpOptions).
        opt: FtpOption enum 값
        """
        try:
            o = FtpOption(opt)
        except ValueError:
            return False

        if o == FtpOption.CONNMODE:
            if val in (int(ConnMode.PASSIVE), int(ConnMode.PORT)):
                self._conn_mode = ConnMode(val)
                if self._ftp:
                    self._ftp.set_pasv(self._conn_mode == ConnMode.PASSIVE)
                return True
            return False
        elif o == FtpOption.CALLBACK:
            self._idle_cb = val
            return True
        elif o == FtpOption.IDLETIME:
            self._idle_sec = val / 1000.0   # ms → sec
            return True
        elif o == FtpOption.CALLBACKARG:
            self._idle_arg = val
            return True
        elif o == FtpOption.CALLBACKBYTES:
            self._cb_bytes = int(val)
            return True
        return False

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #

    def _cmd(self, fn, *args) -> bool:
        """ftplib 메서드 호출 래퍼. 예외 시 False."""
        try:
            fn(*args)
            if self._ftp:
                self._last_resp = self._ftp.lastresp
            return True
        except ftplib.all_errors as e:
            logger.error("%s failed %s: %s", fn.__name__, args, e)
            self._last_resp = str(e)
            return False

    def _list_transfer(
        self,
        cmd:         str,
        path:        Optional[str],
        filename:    Optional[str],
        output_file: Optional[str],
    ) -> Optional[list[str]]:
        """NLST / LIST 공통 처리."""
        lines: list[str] = []
        ftp_cmd = cmd
        if filename:
            ftp_cmd += f" {filename}"
        elif path:
            ftp_cmd += f" {path}"

        try:
            self._ftp.retrlines(ftp_cmd, lines.append)
            self._last_resp = self._ftp.lastresp

            if output_file:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")

            return lines
        except (ftplib.all_errors, OSError) as e:
            logger.error("_list_transfer [%s] failed: %s", ftp_cmd, e)
            self._last_resp = str(e)
            return None

    def _check_conn(self) -> bool:
        """연결 상태 확인. 연결 안 됐으면 False."""
        if self._ftp is None:
            logger.error("FtpUtil: not connected")
            return False
        return True