"""
frList.py - C++ frList.h를 Python 3.11로 변환
각종 리스트/정보 구조체 정의
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


# ──────────────────────────────────────────────
# 메시지 상수
# ──────────────────────────────────────────────
SENSOR_ADD          = -1
SENSOR_DEL          = -2
WORLD_THREAD_CLEAR  = -3
DUMMY_FR_MESSAGE    = -4


# ──────────────────────────────────────────────
# 소켓 모드 상수
# ──────────────────────────────────────────────
SOCK_INFO_MODE_AF_INET_TCP = 1
SOCK_INFO_MODE_AF_INET_UDP = 2
SOCK_INFO_MODE_AF_UNIX     = 3
SOCK_INFO_MODE_UNKNOWN     = 4

SOCK_INFO_MODE_AF_INET_TCP_STR = "AF_INET_TCP"
SOCK_INFO_MODE_AF_INET_UDP_STR = "AF_INET_UDP"
SOCK_INFO_MODE_AF_UNIX_STR     = "AF_UNIX"
SOCK_INFO_MODE_UNKNOWN_STR     = "UNKNOWN"


# ──────────────────────────────────────────────
# 소켓 사용 타입 상수
# ──────────────────────────────────────────────
SOCK_INFO_USE_TYPE_LISTEN    = 1
SOCK_INFO_USE_TYPE_CONNECT   = 2
SOCK_INFO_USE_TYPE_CONNECTED = 3
SOCK_INFO_USE_TYPE_UNKNOWN   = 4

SOCK_INFO_USE_TYPE_LISTEN_STR    = "LISTEN"
SOCK_INFO_USE_TYPE_CONNECT_STR   = "CONNECT"
SOCK_INFO_USE_TYPE_CONNECTED_STR = "CONNECTED"
SOCK_INFO_USE_TYPE_UNKNOWN_STR   = "UNKNOWN"


# ──────────────────────────────────────────────
# 소켓 쓰기 상태 상수
# ──────────────────────────────────────────────
SOCK_INFO_WRITERABLE_STATUS_OK      = 1
SOCK_INFO_WRITERABLE_STATUS_NOK     = 2
SOCK_INFO_WRITERABLE_STATUS_UNKNOWN = 3

SOCK_INFO_WRITERABLE_STATUS_OK_STR      = "OK"
SOCK_INFO_WRITERABLE_STATUS_NOK_STR     = "Not OK"
SOCK_INFO_WRITERABLE_STATUS_UNKNOWN_STR = "UNKNOWN"


# ──────────────────────────────────────────────
# 데이터 클래스
# ──────────────────────────────────────────────

@dataclass
class FrMessageInfo:
    """C++ frMessageInfo struct 대응."""
    message:        int
    sensor:         Any  # frSensor (순환참조 방지를 위해 Any 사용)
    addition_info:  Any = None


@dataclass
class FrWorldInfo:
    """C++ FR_WORLD_INFO_T struct 대응."""
    world_id:   int
    thread_id:  int | None      # C++ THREAD_ID → Python threading.get_ident() 값
    world_ptr:  Any             # frWorld


@dataclass
class TimeOut:
    """C++ TimeOut 클래스 대응."""
    timeout_sec:      int   # time_t
    timeout_mili_sec: int
    reason:           int
    key:              int
    extra_reason:     Any = None


@dataclass
class FileName:
    """C++ FileName 클래스 대응."""
    create_time: int  = 0
    file_name:   str  = ""


@dataclass
class FrSocketInfo:
    """C++ FR_SOCKET_INFO_T struct 대응."""
    fd:               int  = 0
    socket_mode:      int  = SOCK_INFO_MODE_UNKNOWN       # SOCK_INFO_MODE_*
    use_type:         int  = SOCK_INFO_USE_TYPE_UNKNOWN    # SOCK_INFO_USE_TYPE_*
    address:          str  = ""                            # max 30자
    port_no:          int  = 0
    session_name:     str  = ""                            # max 40자
    listener_name:    str  = ""                            # max 40자
    session_time:     str  = ""                            # max 20자
    detail_time:      int  = 0
    writerable_status: int = SOCK_INFO_WRITERABLE_STATUS_UNKNOWN


# ──────────────────────────────────────────────
# 리스트 타입 별칭
# C++ list<T> 상속 클래스 → Python list 타입 별칭으로 대응
# 필요 시 list를 상속하여 확장 가능
# ──────────────────────────────────────────────

# class frWorldInfoList : public list<frWorldInfo>
FrWorldInfoList = list[FrWorldInfo]

# class frEventSrcList : public list<frEventSrc*>
FrEventSrcList  = list[Any]   # frEventSrc 미정의이므로 Any

# class frSensorList : public list<frSensor*>
FrSensorList    = list[Any]   # frSensor 미정의이므로 Any

# class TimerList : public list<TimeOut*>
TimerList       = list[TimeOut]

# class FileNameList : public list<FileName>
FileNameList    = list[FileName]

# typedef vector<FR_SOCKET_INFO_T> frSocketInfoVector
FrSocketInfoVector = list[FrSocketInfo]