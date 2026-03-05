# -*- coding: utf-8 -*-
"""
frSockFdManager.h / frSockFdManager.C  →  fr_sock_fd_manager.py
Python 3.11.10 버전

변환 설계:
  frSockFdManager  → FrSockFdManager  (유틸리티 클래스, 인스턴스 불필요)

C++ → Python 주요 변환 포인트:
  frMutexGuard(&frSensor::m_SensorMgrLock) → with FrSensor._sensor_mgr_lock:
  dynamic_cast<frSocketSensor*>            → isinstance(sensor, FrSocketSensor)
  GetObjectType() == 5                     → sensor._object_type == 5
  frSocketInfoVector                       → list[SocketInfo]  (dataclass)
  FR_SOCKET_INFO_T 구조체                  → SocketInfo dataclass
  select() FD_SET/FD_ISSET                 → select.select()
  frSTD_OUT / frCORE_ERROR                 → print / logger.error
  SetGErrMsg                               → fr_object.set_g_err_msg()
  strcmp                                   → == 연산자
  SOCK_INFO_* 문자열 상수                  → dict 매핑

변경 이력:
  v1 - 초기 변환
"""

import logging
import select as _select
from dataclasses import dataclass, field

from fr_object      import set_g_err_msg
from fr_sensor      import FrSensor
from fr_socket_sensor import (
    FrSocketSensor,
    SOCK_INFO_USE_TYPE_UNKNOWN,
    SOCK_INFO_USE_TYPE_LISTEN,
    SOCK_INFO_USE_TYPE_CONNECT,
    SOCK_INFO_USE_TYPE_CONNECTED,
    SOCK_INFO_MODE_UNKNOWN,
    SOCK_INFO_MODE_AF_INET_TCP,
    SOCK_INFO_MODE_AF_UNIX,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SOCK_INFO 상수 (fr_socket_sensor.py 에 없는 추가 상수)
# ─────────────────────────────────────────────────────────────────────────────
SOCK_INFO_MODE_AF_INET_UDP       = 3

SOCK_INFO_WRITERABLE_STATUS_UNKNOWN = 0
SOCK_INFO_WRITERABLE_STATUS_OK      = 1
SOCK_INFO_WRITERABLE_STATUS_NOK     = 2

# 문자열 표현 매핑
_SOCK_MODE_STR = {
    SOCK_INFO_MODE_AF_INET_TCP: 'AF_INET_TCP',
    SOCK_INFO_MODE_AF_INET_UDP: 'AF_INET_UDP',
    SOCK_INFO_MODE_AF_UNIX:     'AF_UNIX',
}

_SOCK_USE_TYPE_STR = {
    SOCK_INFO_USE_TYPE_LISTEN:    'LISTEN',
    SOCK_INFO_USE_TYPE_CONNECT:   'CONNECT',
    SOCK_INFO_USE_TYPE_CONNECTED: 'CONNECTED',
}

_SOCK_WRITERABLE_STR = {
    SOCK_INFO_WRITERABLE_STATUS_OK:  'OK',
    SOCK_INFO_WRITERABLE_STATUS_NOK: 'NOK',
}


# ─────────────────────────────────────────────────────────────────────────────
# SocketInfo  (C++ FR_SOCKET_INFO_T 구조체 대응)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class SocketInfo:
    """C++ FR_SOCKET_INFO_T 구조체 대응."""
    fd:               int   = -1
    socket_mode:      int   = SOCK_INFO_MODE_UNKNOWN
    use_type:         int   = SOCK_INFO_USE_TYPE_UNKNOWN
    address:          str   = ''
    port_no:          int   = 0
    session_name:     str   = ''
    listener_name:    str   = ''
    session_time:     str   = ''
    detail_time:      int   = 0
    writerable_status: int  = SOCK_INFO_WRITERABLE_STATUS_UNKNOWN


# ─────────────────────────────────────────────────────────────────────────────
# FrSockFdManager
# ─────────────────────────────────────────────────────────────────────────────
class FrSockFdManager:
    """
    C++ frSockFdManager 대응 유틸리티 클래스.
    모든 메서드가 @staticmethod 이므로 인스턴스화 불필요.
    전역 센서 목록에서 FrSocketSensor(_object_type==5) 를 필터링하여
    소켓 상태 조회 / 종료 / 출력 기능을 제공한다.
    """

    # ------------------------------------------------------------------ #
    # 소켓 목록 조회
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_sock_infos(is_writerable_check: bool = False,
                       sec: int = 0,
                       micro_sec: int = 100_000) -> list[SocketInfo]:
        """
        C++ GetSockInfos(frSocketInfoVector&, ...) 대응.
        전역 센서 목록에서 FrSocketSensor 를 찾아 SocketInfo 리스트로 반환.
        """
        result: list[SocketInfo] = []

        with FrSensor._sensor_mgr_lock:
            for sensor in FrSensor.get_global_sensor_list():
                if sensor._object_type != 5:
                    continue
                if not isinstance(sensor, FrSocketSensor):
                    logger.debug('get_sock_infos: type mismatch (%s)',
                                 sensor.get_object_name())
                    continue

                info = FrSockFdManager._get_socket_info(sensor)
                if is_writerable_check:
                    info.writerable_status = (
                        SOCK_INFO_WRITERABLE_STATUS_OK
                        if FrSockFdManager.socket_check(info, sec, micro_sec)
                        else SOCK_INFO_WRITERABLE_STATUS_NOK
                    )
                result.append(info)

        return result

    # ------------------------------------------------------------------ #
    # 소켓 강제 종료
    # ------------------------------------------------------------------ #
    @staticmethod
    def shut_down_sock(info: SocketInfo) -> bool:
        """
        C++ ShutDownSock(FR_SOCKET_INFO_T&) 대응.
        일치하는 소켓을 전역 목록에서 찾아 shutdown.
        """
        import socket as _socket

        with FrSensor._sensor_mgr_lock:
            for sensor in FrSensor.get_global_sensor_list():
                if sensor._object_type != 5:
                    continue
                if not isinstance(sensor, FrSocketSensor):
                    continue

                cur_info = FrSockFdManager._get_socket_info(sensor)
                if not FrSockFdManager.socket_info_compare(info, cur_info):
                    continue

                try:
                    if sensor._sock:
                        sensor._sock.shutdown(_socket.SHUT_RDWR)
                    logger.debug('shut_down_sock: success')
                    return True
                except OSError as e:
                    msg = f'ShutDownSock fail: {e} ({info.session_name})'
                    set_g_err_msg(msg)
                    logger.error(msg)
                    return False

        return False

    # ------------------------------------------------------------------ #
    # 소켓 정보 비교
    # ------------------------------------------------------------------ #
    @staticmethod
    def socket_info_compare(info1: SocketInfo, info2: SocketInfo) -> bool:
        """
        C++ FrSocketInfoCompare() 대응.
        fd, detail_time, port_no, session_time, session_name 기준 비교.
        """
        return (
            info1.fd          == info2.fd          and
            info1.detail_time == info2.detail_time and
            info1.port_no     == info2.port_no     and
            info1.session_time == info2.session_time and
            info1.session_name == info2.session_name
        )

    # ------------------------------------------------------------------ #
    # 쓰기 가능 여부 확인
    # ------------------------------------------------------------------ #
    @staticmethod
    def socket_check(info: SocketInfo, sec: int = 0,
                     micro_sec: int = 100_000) -> bool:
        """
        C++ SocketCheck() / select() FD_SET 대응.
        LISTEN 소켓은 항상 True.
        fd < 3 (stdin/stdout/stderr) 은 False.
        """
        if info.use_type == SOCK_INFO_USE_TYPE_LISTEN:
            return True
        if info.fd < 3:
            return False

        timeout = sec + micro_sec / 1_000_000
        logger.error('socket_check try..')
        FrSockFdManager.print_socket_info(info)

        try:
            _, w, _ = _select.select([], [info.fd], [], timeout)
        except OSError as e:
            set_g_err_msg('IsWriterable check error: %s', str(e))
            logger.debug('socket_check error: %s', e)
            return False

        if not w:
            tout = (sec * 1_000_000 + micro_sec) / 1_000_000
            msg = (f'Session Writerable check timeout({tout:.3f}s) '
                   f'({info.session_name}, {info.address}:{info.port_no})')
            set_g_err_msg(msg)
            logger.debug(msg)
            return False

        return True

    # ------------------------------------------------------------------ #
    # 소켓 상태 전체 출력
    # ------------------------------------------------------------------ #
    @staticmethod
    def show_sock_fd_status() -> None:
        """C++ ShowSockFdStatus() 대응."""
        with FrSensor._sensor_mgr_lock:
            for sensor in FrSensor.get_global_sensor_list():
                if sensor._object_type != 5:
                    continue
                if not isinstance(sensor, FrSocketSensor):
                    logger.debug('show_sock_fd_status: type mismatch (%s)',
                                 sensor.get_object_name())
                    continue
                info = FrSockFdManager._get_socket_info(sensor)
                FrSockFdManager.print_socket_info(info)

    # ------------------------------------------------------------------ #
    # SocketInfo 출력
    # ------------------------------------------------------------------ #
    @staticmethod
    def print_socket_info(info: SocketInfo) -> None:
        """C++ PrintFrSocketInfo() 대응."""
        mode_str       = _SOCK_MODE_STR.get(info.socket_mode,       'UNKNOWN')
        use_type_str   = _SOCK_USE_TYPE_STR.get(info.use_type,      'UNKNOWN')
        writerable_str = _SOCK_WRITERABLE_STR.get(info.writerable_status, 'UNKNOWN')

        print(
            f'Display Socket Info\n'
            f'SessionName      : {info.session_name}\n'
            f'ListenerName     : {info.listener_name}\n'
            f'FD               : {info.fd}\n'
            f'SocketMode       : {mode_str}\n'
            f'UseType          : {use_type_str}\n'
            f'Address          : {info.address}\n'
            f'PortNo           : {info.port_no}\n'
            f'SessionTime      : {info.session_time}.{info.detail_time}\n'
            f'WriterableStatus : {writerable_str}',
            flush=True,
        )

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #
    @staticmethod
    def _get_socket_info(sensor: FrSocketSensor) -> SocketInfo:
        """FrSocketSensor → SocketInfo 변환 헬퍼."""
        import socket as _socket
        info = SocketInfo()
        info.fd           = sensor._fd
        info.session_name = sensor.get_object_name()
        info.listener_name = sensor._listener_name
        info.peer_ip      = sensor._peer_ip      if hasattr(sensor, '_peer_ip') else ''
        info.port_no      = sensor._port_no
        info.session_time = sensor._session_time
        info.detail_time  = sensor._session_time_detail
        info.use_type     = sensor._use_type
        info.address      = sensor._peer_ip

        if sensor._socket_mode == _socket.AF_INET:
            info.socket_mode = SOCK_INFO_MODE_AF_INET_TCP
            if sensor._socket_type == _socket.SOCK_DGRAM:
                info.socket_mode = SOCK_INFO_MODE_AF_INET_UDP
        elif sensor._socket_mode == _socket.AF_UNIX:
            info.socket_mode = SOCK_INFO_MODE_AF_UNIX
            info.address     = sensor._socket_path

        return info