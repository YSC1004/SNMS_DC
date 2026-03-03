"""
frSFtpUtil.h / frSFtpUtil.C  →  fr_sftp_util.py

변환 설계:
  C++ 원본: libssh (ssh_session / sftp_session) 로 SFTP 직접 구현
  Python  : paramiko (SSHClient + SFTPClient) 로 대체
            → pip install paramiko

매핑:
  SFtpConnect(ip, port, id)     → sftp_connect(ip, port, user)
  SFtpLogin(id, passwd)         → sftp_login(id, passwd)
  SSHPUBLC_KEY(session, passwd) → _try_pubkey_auth(passwd)   (내부)
  verify_knownhost(session)     → _verify_known_host()        (내부, AutoAddPolicy 대응)
  Sftp_init(session)            → _sftp_init()                (내부)
  SFtpMkdir(path)               → sftp_mkdir(path)
  SFtpChdir(path)               → sftp_chdir(path)
  SFtpGet(remote, local, mode)  → sftp_get(remote_path, local_file)
  SFtpDir(list, file, path, fn) → sftp_dir(path, filename, output_file)
  SFtpNlst(list,file,path,fn)   → sftp_nlst(path, filename, output_file)
  SSH_CHECK()                   → ssh_check()
  free_session / free_sftp      → _close()  (소멸자에서 자동 호출)

주의:
  - paramiko 설치 필요: pip install paramiko
  - 공개키 인증 우선 시도 → 실패 시 패스워드 인증 (C++ 원본 동일)
  - known_hosts 검증: AutoAddPolicy (C++ 원본의 STRICTHOSTKEYCHECK=no 대응)
    보안 강화가 필요하면 RejectPolicy + known_hosts 파일 관리로 변경
"""

import os
import stat
import logging
from typing import Optional

try:
    import paramiko
except ImportError:
    raise ImportError("paramiko 가 필요합니다. 'pip install paramiko' 로 설치하세요.")

logger = logging.getLogger(__name__)


class SFtpUtil:
    """
    SFTP 유틸리티 클래스 (SFtpUtil / frSFtpUtil 대응).
    paramiko.SSHClient + SFTPClient 를 래핑하여
    C++ 원본과 동일한 인터페이스를 제공.
    """

    def __init__(self):
        self._user:      str                          = ""
        self._password:  str                          = ""
        self._host:      str                          = ""
        self._port:      int                          = 22
        self._flag:      bool                         = False  # 공개키 인증 성공 여부
        self._ssh:       Optional[paramiko.SSHClient] = None
        self._sftp:      Optional[paramiko.SFTPClient]= None
        self._cwd:       str                          = "/"    # SFtpChdir 현재 경로

    def __del__(self):
        self._close()

    # ------------------------------------------------------------------ #
    # 연결 / 인증
    # ------------------------------------------------------------------ #

    def sftp_connect(self, ip_address: str, port: int, user: str) -> bool:
        """
        SSH 소켓 연결 및 세션 초기화 (SFtpConnect).
        실제 인증은 sftp_login() 에서 수행.
        """
        self._host = ip_address
        self._port = port
        self._user = user

        try:
            self._ssh = paramiko.SSHClient()
            # C++ 원본: SSH_OPTIONS_STRICTHOSTKEYCHECK = "no"
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # 연결만 수행 (인증은 sftp_login 에서)
            self._ssh.connect(
                hostname = ip_address,
                port     = port,
                username = user,
                # look_for_keys=False 로 하면 공개키 자동시도 비활성화
                # → sftp_login 에서 순서 제어
                look_for_keys = False,
                allow_agent   = False,
                timeout       = 30,
            )
            logger.debug("sftp_connect: TCP connected to %s:%d", ip_address, port)
            return True
        except Exception as e:
            logger.error("sftp_connect failed [%s:%d]: %s", ip_address, port, e)
            self._ssh = None
            return False

    def sftp_login(self, user: str = "", passwd: str = "") -> bool:
        """
        SSH 인증 후 SFTP 서브시스템 초기화 (SFtpLogin).
        공개키 인증 우선 시도 → 실패 시 패스워드 인증.
        """
        if user:   self._user     = user
        if passwd: self._password = passwd

        if self._ssh is None:
            logger.error("sftp_login: not connected. call sftp_connect() first.")
            return False

        # ── 공개키 인증 우선 시도 (SSHPUBLC_KEY 대응) ──────────────────────
        if self._try_pubkey_auth(passwd):
            self._flag = True
            logger.debug("sftp_login: public key authentication successful.")
        else:
            # ── 패스워드 인증 (ssh_userauth_password 대응) ─────────────────
            self._flag = False
            try:
                transport = self._ssh.get_transport()
                transport.auth_password(self._user, self._password)
                logger.debug("sftp_login: password authentication successful.")
            except paramiko.AuthenticationException as e:
                logger.error("sftp_login: password auth failed: %s", e)
                return False
            except Exception as e:
                logger.error("sftp_login: auth error: %s", e)
                return False

        # ── SFTP 서브시스템 초기화 (Sftp_init 대응) ────────────────────────
        return self._sftp_init()

    def ssh_check(self) -> bool:
        """공개키 인증 성공 여부 반환 (SSH_CHECK / m_flag)."""
        return self._flag

    # ------------------------------------------------------------------ #
    # 디렉토리 조작
    # ------------------------------------------------------------------ #

    def sftp_mkdir(self, path: str) -> bool:
        """
        원격 디렉토리 생성 (SFtpMkdir / sftp_mkdir).
        이미 존재하면 False 반환 (C++ 원본 동일).
        """
        if not self._check():
            return False
        try:
            self._sftp.mkdir(path, mode=0o755)
            return True
        except IOError as e:
            # SSH_FX_FILE_ALREADY_EXISTS 대응
            if "exists" in str(e).lower() or getattr(e, 'errno', 0) == 17:
                logger.error("sftp_mkdir: directory already exists [%s]", path)
            else:
                logger.error("sftp_mkdir failed [%s]: %s", path, e)
            return False

    def sftp_chdir(self, path: str) -> bool:
        """
        원격 디렉토리 존재 여부 확인 및 현재 경로 설정 (SFtpChdir).
        C++ 원본: sftp_opendir 로 존재 확인.
        """
        if not self._check():
            return False
        try:
            self._sftp.listdir(path)   # opendir 대응 (존재 확인)
            self._cwd = path
            return True
        except IOError as e:
            logger.error("sftp_chdir failed [%s]: %s", path, e)
            return False

    # ------------------------------------------------------------------ #
    # 파일 다운로드
    # ------------------------------------------------------------------ #

    def sftp_get(
        self,
        remote_path: str,
        local_file:  str,
        mode:        str = "b",   # 'b'=binary, 'A'=ascii (C++ char Mode)
    ) -> bool:
        """
        원격 파일을 로컬로 다운로드 (SFtpGet / sftp_read).
        C++ 원본: sftp_open → sftp_read 루프 → fwrite.
        """
        if not self._check():
            return False
        try:
            self._sftp.get(remote_path, local_file)
            return True
        except IOError as e:
            logger.error("sftp_get failed [%s → %s]: %s", remote_path, local_file, e)
            return False

    # ------------------------------------------------------------------ #
    # 디렉토리 목록 조회
    # ------------------------------------------------------------------ #

    def sftp_dir(
        self,
        path:        Optional[str] = None,
        filename:    Optional[str] = None,
        output_file: Optional[str] = None,
    ) -> Optional[list[str]]:
        """
        상세 목록 반환 (SFtpDir / sftp_readdir 상세 포맷).
        C++ 원본 포맷:
          "permissions  size owner(uid)\\tgroup(gid) type name"
        output_file 지정 시 파일에도 저장.
        실패 시 None.
        """
        if not self._check():
            return None
        target = path or self._cwd
        try:
            entries = self._sftp.listdir_attr(target)
        except IOError as e:
            logger.error("sftp_dir failed [%s]: %s", target, e)
            return None

        result: list[str] = []
        for attr in entries:
            name = attr.filename
            if name.startswith("."):
                continue
            if filename and filename not in name:
                continue

            ftype  = 1 if stat.S_ISDIR(attr.st_mode or 0) else 8
            perms  = oct(attr.st_mode or 0)[2:]
            line   = (
                f"{perms}  {attr.st_size or 0:10d} "
                f"{attr.st_uid}({attr.st_uid})\t"
                f"{attr.st_gid}({attr.st_gid}) {ftype} {name}"
            )
            result.append(line)

        if output_file:
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(result) + "\n")
            except OSError as e:
                logger.error("sftp_dir: output_file write failed: %s", e)

        return result

    def sftp_nlst(
        self,
        path:        Optional[str] = None,
        filename:    Optional[str] = None,
        output_file: Optional[str] = None,
    ) -> Optional[list[str]]:
        """
        파일명만 반환 (SFtpNlst / sftp_readdir 이름만).
        C++ 원본: token[0] = 파일명만 추출.
        output_file 지정 시 파일에도 저장.
        실패 시 None.
        """
        if not self._check():
            return None
        target = path or self._cwd
        try:
            entries = self._sftp.listdir_attr(target)
        except IOError as e:
            logger.error("sftp_nlst failed [%s]: %s", target, e)
            return None

        result: list[str] = []
        for attr in entries:
            name = attr.filename
            if name.startswith("."):
                continue
            if filename and filename not in name:
                continue
            result.append(name)

        if output_file:
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(result) + "\n")
            except OSError as e:
                logger.error("sftp_nlst: output_file write failed: %s", e)

        return result

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #

    def _try_pubkey_auth(self, passwd: str) -> bool:
        """
        공개키 자동 인증 시도 (SSHPUBLC_KEY / ssh_userauth_publickey_auto).
        ~/.ssh/id_rsa 등 기본 키 사용.
        """
        try:
            transport = self._ssh.get_transport()
            # paramiko 는 에이전트·기본 키 경로에서 자동 시도
            agent = paramiko.Agent()
            for key in agent.get_keys():
                try:
                    transport.auth_publickey(self._user, key)
                    return True
                except paramiko.AuthenticationException:
                    continue

            # 에이전트 실패 시 기본 키 파일 시도
            for key_path in [
                os.path.expanduser("~/.ssh/id_rsa"),
                os.path.expanduser("~/.ssh/id_ecdsa"),
                os.path.expanduser("~/.ssh/id_ed25519"),
            ]:
                if not os.path.exists(key_path):
                    continue
                try:
                    key = paramiko.RSAKey.from_private_key_file(key_path)
                    transport.auth_publickey(self._user, key)
                    return True
                except Exception:
                    continue
        except Exception as e:
            logger.debug("_try_pubkey_auth: %s", e)
        return False

    def _sftp_init(self) -> bool:
        """
        SFTP 서브시스템 초기화 (Sftp_init / sftp_new + sftp_init).
        """
        try:
            self._sftp = self._ssh.open_sftp()
            logger.debug("_sftp_init: SFTP session initialized.")
            return True
        except Exception as e:
            logger.error("_sftp_init failed: %s", e)
            self._sftp = None
            return False

    def _check(self) -> bool:
        """연결 상태 확인."""
        if self._sftp is None:
            logger.error("SFtpUtil: SFTP session not initialized.")
            return False
        return True

    def _close(self) -> None:
        """세션 자원 해제 (free_session / free_sftp 대응)."""
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
            self._ssh = None