# -*- coding: utf-8 -*-
"""
ConnectionMgr.h / ConnectionMgr.C  →  ConnectionMgr.py
Python 3.11.10 변환

변환 설계:
  ConnectionMgr → ConnectionMgr  (AsSocket 상속)

C++ → Python 주요 변환 포인트:
  SocketConnectionList (list<AsSocket*>) → list[AsSocket]
  frStringList (list<string>)            → list[str]
  sighold/sigrelse(SIGCLD/SIGINT)        → threading.Lock() 으로 대체
  SocketRemoveLock/UnLock() virtual      → _socket_remove_lock/unlock() (no-op, override 가능)
  AsWorld::RegisterConnectionMgr(this)   → AsWorld.register_connection_mgr(self)
  frSockFdManager::SocketCheck()         → FrSockFdManager.socket_check()
  delete (*itr)                          → GC 위임 (list 에서 제거)

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
import signal
import threading
from typing import Optional, TYPE_CHECKING

from Common.AsSocket import AsSocket
from Common.CommType import AsCmdLogControlT, AsCmdOpenPortT, FrSocketInfo
from Common.CommTypeList import SocketConnectionList

if TYPE_CHECKING:
    from Event.fr_sock_fd_manager import FrSockFdManager

logger = logging.getLogger(__name__)

# SOCK_INFO_WRITERABLE_STATUS 상수 (CommType.py 에 정의되어 있지 않을 경우 여기서 정의)
SOCK_INFO_WRITERABLE_STATUS_OK  = 1
SOCK_INFO_WRITERABLE_STATUS_NOK = 0


class ConnectionMgr(AsSocket):
    """
    C++ ConnectionMgr 대응.
    AsSocket 연결 목록을 관리하며 세션 조회, 명령 전송, 소켓 정보 수집을 담당.
    """

    def __init__(self) -> None:
        super().__init__()
        self._socket_connection_list: SocketConnectionList = []
        self._current_session_id: list[str] = []
        self._lock = threading.Lock()  # sighold/sigrelse 대체

        from Common.AsWorld import AsWorld
        AsWorld.register_connection_mgr(self)

    def __del__(self) -> None:
        from Common.AsWorld import AsWorld
        AsWorld.deregister_connection_mgr(self)
        self._socket_connection_list.clear()

    # ── 소켓 추가 / 제거 ──────────────────────

    def add(self, socket: AsSocket) -> None:
        """C++ Add(AsSocket*) 대응."""
        self._socket_connection_list.append(socket)

    def remove(self, socket: AsSocket) -> None:
        """
        C++ Remove(AsSocket*) 대응.
        시그널 블록(Lock) → 세션명 제거 → 소켓 제거 → 언락.
        """
        with self._lock:
            self._socket_remove_lock()
            session = socket.get_session_name()
            self._current_session_id = [s for s in self._current_session_id if s != session]
            if socket in self._socket_connection_list:
                self._socket_connection_list.remove(socket)
            self._socket_remove_unlock()

    def _socket_remove_lock(self) -> None:
        """C++ SocketRemoveLock() virtual no-op 대응. 하위 클래스에서 override 가능."""

    def _socket_remove_unlock(self) -> None:
        """C++ SocketRemoveUnLock() virtual no-op 대응. 하위 클래스에서 override 가능."""

    # ── 세션 이름 관리 ────────────────────────

    def add_session_name(self, session_name: str) -> bool:
        """
        C++ AddSessionName() 대응.
        중복 등록 시 에러 로그 후 False 반환.
        """
        if session_name in self._current_session_id:
            logger.error("Already Register SessionName : %s", session_name)
            return False
        self._current_session_id.append(session_name)
        return True

    def remove_session_name(self, session_name: str) -> bool:
        """C++ RemoveSessionName() 대응. 없으면 False 반환."""
        try:
            self._current_session_id.remove(session_name)
            return True
        except ValueError:
            return False

    def find_session(self, session_name: str) -> Optional[AsSocket]:
        """C++ FindSession() 대응. 없으면 None 반환."""
        for sock in self._socket_connection_list:
            if session_name == sock.get_session_name():
                return sock
        return None

    # ── 명령 전송 ─────────────────────────────

    def send_cmd_log_status_change(
        self,
        log_ctl: AsCmdLogControlT,
        session_name: str = "",
    ) -> bool:
        """
        C++ SendCmdLogStatusChange() 대응.
        session_name 이 빈 문자열이면 전체 전송, 아니면 해당 세션만 전송.
        """
        if not session_name:
            for sock in self._socket_connection_list:
                sock.send_cmd_log_status_change(log_ctl)
            return True

        sock = self.find_session(session_name)
        if sock is None:
            return False
        sock.send_cmd_log_status_change(log_ctl)
        return True

    def cmd_open_port_info(
        self, session_name: str, port_info: AsCmdOpenPortT
    ) -> bool:
        """C++ CmdOpenPortInfo() 대응."""
        sock = self.find_session(session_name)
        if sock is None:
            return False
        sock.cmd_open_port_info(port_info)
        return True

    def send_all_cmd_open_port_info(self, port_info: AsCmdOpenPortT) -> None:
        """C++ SendAllCmdOpenPortInfo() 대응. 전체 소켓에 전송."""
        for sock in self._socket_connection_list:
            sock.cmd_open_port_info(port_info)

    # ── 유효성 검사 ───────────────────────────

    def is_valid_connection(self, socket: AsSocket) -> bool:
        """C++ IsValidConnection() 대응."""
        return socket in self._socket_connection_list

    # ── 소켓 정보 수집 ────────────────────────

    def get_con_sock_infos(
        self,
        info_vector: list[FrSocketInfo],
        is_writerable_check: bool = False,
        sec: int = 0,
        micro_sec: int = 100000,
    ) -> None:
        """
        C++ GetConSockInfos() 대응.
        자신 + 연결 소켓 목록의 FrSocketInfo 를 info_vector 에 추가.
        is_writerable_check=True 이면 쓰기 가능 여부도 함께 설정.
        """
        from Event.fr_sock_fd_manager import FrSockFdManager

        self._socket_remove_lock()
        try:
            info = FrSocketInfo()
            self.get_socket_info(info)
            if is_writerable_check:
                info.writerable_status = (
                    SOCK_INFO_WRITERABLE_STATUS_OK
                    if FrSockFdManager.socket_check(info, sec, micro_sec)
                    else SOCK_INFO_WRITERABLE_STATUS_NOK
                )
            info_vector.append(info)

            for sock in self._socket_connection_list:
                info = FrSocketInfo()
                sock.get_socket_info(info)
                if is_writerable_check:
                    info.writerable_status = (
                        SOCK_INFO_WRITERABLE_STATUS_OK
                        if FrSockFdManager.socket_check(info, sec, micro_sec)
                        else SOCK_INFO_WRITERABLE_STATUS_NOK
                    )
                info_vector.append(info)
        finally:
            self._socket_remove_unlock()

    def get_connection_list(self) -> SocketConnectionList:
        """C++ GetConnectionList() 대응."""
        return self._socket_connection_list