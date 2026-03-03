"""
frSshUtil.h / frSshUtil.C  →  fr_ssh_util.py

변환 설계:
  C++ 원본: libssh (ssh_session / ssh_channel) 로 SSH 직접 구현
  Python  : paramiko (SSHClient) 로 대체
            → pip install paramiko

매핑:
  SshConnect(ip, port, user, passwd, cmd) → ssh_connect(ip, port, user, passwd, cmd)
  SshSendCmd(ip, port, user, passwd, cmd) → ssh_send_cmd(ip, port, user, passwd, cmd)
  free_channel(channel)                   → 내부 자동 처리 (with 블록)
  free_session(session)                   → 내부 자동 처리 (with 블록)
  error(session)                          → _error(msg)

C++ 원본 주요 특징:
  - SshConnect : 명령 실행 결과를 stdout 에 출력, 반환값은 bool
  - SshSendCmd : 명령 실행 결과를 문자열(char*)로 반환 (최대 500000 bytes)
  - 두 함수 모두 매 호출마다 새 세션 생성 → 연결 후 명령 실행 → 세션 해제
  - 패스워드 인증만 사용 (공개키 미사용)

Python 변환:
  - SshSendCmd 반환값: char* (로컬 버퍼) → str (Python 문자열)
  - 세션 생성/해제는 with 블록으로 자동 관리
  - stdout 출력 (fwrite) → sys.stdout.write() 또는 print()
"""

import sys
import time
import logging
from typing import Optional

try:
    import paramiko
except ImportError:
    raise ImportError("paramiko 가 필요합니다. 'pip install paramiko' 로 설치하세요.")

logger = logging.getLogger(__name__)

# C++ 원본 buffer 크기 (500000 bytes)
_READ_BUF_SIZE = 500_000
_CHANNEL_TIMEOUT = 30.0
_SLEEP_USEC = 20_000   # usleep(20000) → 0.02 초


class SshUtil:
    """
    SSH 원격 명령 실행 유틸리티 (SshUtil / frSshUtil 대응).
    paramiko.SSHClient 를 래핑하여 C++ 원본과 동일한 인터페이스 제공.

    C++ 원본 설계:
      - 인스턴스 멤버(m_User 등)는 선언되어 있으나 실제로는
        메서드 인자로 모두 받아서 사용 (매 호출마다 새 세션 생성).
      - Python 에서도 동일한 패턴을 유지.
    """

    def __init__(self):
        self._user:     str = ""
        self._password: str = ""
        self._host:     str = ""
        self._port:     int = 22

    # ------------------------------------------------------------------ #
    # SshConnect : 명령 실행 결과를 stdout 으로 출력
    # ------------------------------------------------------------------ #

    def ssh_connect(
        self,
        ip_address: Optional[str] = None,
        port:       int           = 22,
        user:       Optional[str] = None,
        passwd:     Optional[str] = None,
        cmd:        Optional[str] = None,
    ) -> bool:
        """
        SSH 접속 후 명령 실행, 결과를 stdout 에 출력 (SshConnect).
        성공 시 True, 실패 시 False.

        C++ 원본 동작:
          ssh_new → ssh_options_set → ssh_connect
          → ssh_userauth_password → ssh_channel_new
          → ssh_channel_open_session → ssh_channel_request_exec
          → ssh_channel_read 루프 → fwrite(stdout) → free
        """
        logger.debug("ssh_connect: Session to %s:%d", ip_address, port)

        client = self._make_client()
        try:
            client.connect(
                hostname = ip_address,
                port     = port,
                username = user,
                password = passwd,
                look_for_keys = False,
                allow_agent   = False,
                timeout       = _CHANNEL_TIMEOUT,
            )
        except paramiko.AuthenticationException as e:
            self._error(f"password authentication failed: {e}")
            return False
        except Exception as e:
            self._error(f"connect failed [{ip_address}:{port}]: {e}")
            return False

        try:
            logger.debug("ssh_connect: executing [%s]", cmd)
            stdin, stdout, stderr = client.exec_command(
                cmd or "", timeout=_CHANNEL_TIMEOUT
            )

            # C++ 원본: ssh_channel_read → fwrite(stdout) 루프
            while True:
                chunk = stdout.read(4096)
                if not chunk:
                    break
                sys.stdout.write(chunk.decode("utf-8", errors="replace"))
                sys.stdout.flush()

            return True

        except Exception as e:
            self._error(f"exec_command failed: {e}")
            return False
        finally:
            client.close()

    # ------------------------------------------------------------------ #
    # SshSendCmd : 명령 실행 결과를 문자열로 반환
    # ------------------------------------------------------------------ #

    def ssh_send_cmd(
        self,
        ip_address: Optional[str] = None,
        port:       int           = 22,
        user:       Optional[str] = None,
        passwd:     Optional[str] = None,
        cmd:        Optional[str] = None,
    ) -> Optional[str]:
        """
        SSH 접속 후 명령 실행, 결과를 문자열로 반환 (SshSendCmd).
        실패 시 None 반환 (C++ 원본: NULL / 0 반환).

        C++ 원본 동작:
          세션 생성 → 인증 → 채널 열기 → exec →
          read 루프(usleep(20000) 포함) → tmp 버퍼에 누적 → return tmp
        """
        logger.debug("ssh_send_cmd: Session to %s:%d", ip_address, port)

        client = self._make_client()
        try:
            client.connect(
                hostname = ip_address,
                port     = port,
                username = user,
                password = passwd,
                look_for_keys = False,
                allow_agent   = False,
                timeout       = _CHANNEL_TIMEOUT,
            )
        except paramiko.AuthenticationException as e:
            self._error(f"password authentication failed: {e}")
            return None
        except Exception as e:
            self._error(f"connect failed [{ip_address}:{port}]: {e}")
            return None

        try:
            logger.debug("ssh_send_cmd: executing [%s]", cmd)
            stdin, stdout, stderr = client.exec_command(
                cmd or "", timeout=_CHANNEL_TIMEOUT
            )

            # C++ 원본: strncat(tmp, buffer) + usleep(20000) 루프
            result_parts: list[str] = []
            total = 0

            while True:
                chunk = stdout.read(4096)
                if not chunk:
                    break

                # C++ 원본: write(1, buffer, nbytes) → stdout 출력도 병행
                sys.stdout.buffer.write(chunk)
                sys.stdout.flush()

                decoded = chunk.decode("utf-8", errors="replace")
                result_parts.append(decoded)
                total += len(chunk)

                # C++ 원본: usleep(20000) 대응
                time.sleep(_SLEEP_USEC / 1_000_000)

                # C++ 원본 버퍼 상한 (500000 bytes) 초과 방지
                if total >= _READ_BUF_SIZE:
                    logger.warning(
                        "ssh_send_cmd: output truncated at %d bytes", _READ_BUF_SIZE
                    )
                    break

            return "".join(result_parts)

        except Exception as e:
            self._error(f"exec_command failed: {e}")
            return None
        finally:
            client.close()

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #

    @staticmethod
    def _make_client() -> paramiko.SSHClient:
        """paramiko SSHClient 생성 및 기본 설정."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        return client

    @staticmethod
    def _error(msg: str) -> None:
        """
        error(session) 대응.
        C++ 원본: fprintf(stderr, ...) + free_session().
        Python  : logging.error() (세션은 finally 블록에서 자동 해제).
        """
        logger.error("SshUtil error: %s", msg)