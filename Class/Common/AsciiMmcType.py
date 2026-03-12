"""
Python 변환: AsciiMmcType.h → AsciiMmcType.py
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List

# ─────────────────────────────────────────────
# 패킷 크기 상수
# ─────────────────────────────────────────────
MAX_PACKET      = 4096
MAX_MSG         = 4088
MAX_RESULT_MSG  = 4080

# ─────────────────────────────────────────────
# 공통 길이 상수
# ─────────────────────────────────────────────
EQUIP_ID_LEN    = 40
MMC_CMD_LEN     = 128
MMC_CMD_LEN_EX  = 1000
MMC_CMD_LEN_EX2 = 500
MMC_VAL_LEN     = 128
USER_ID_LEN     = 16
PASSWORD_LEN    = 16
IP_ADDRESS_LEN  = 16    # "xxx.xxx.xxx.xxx"
EVENT_ID_LEN    = 32

# SOCK_INFO_LISTENER_NAME_MAX_LEN: CommType.h 에서 참조
# frSocket/frList 변환 완료 전 임시값 (실제 값으로 교체 필요)
SOCK_INFO_LISTENER_NAME_MAX_LEN = 64

# ─────────────────────────────────────────────
# MMC 메시지 ID 상수
# ─────────────────────────────────────────────
AS_MMC_REQ          = 6
AS_MMC_REQ_ACK      = 2
AS_MMC_REQ_OLD      = 1
AS_MMC_RES          = 11
AS_MMC_RES_ACK      = 12
AS_MMC_IDENT_REQ    = 21
AS_MMC_IDENT_RES    = 22
AS_MMC_FLOW_CONTROL = 31

# Router Info 메시지 ID
AS_ROUTER_INFO_REQ  = 101
AS_ROUTER_INFO_RES  = 102
AS_ROUTER_CONFIG    = 111

# ─────────────────────────────────────────────
# Enum 정의
# ─────────────────────────────────────────────
class AS_MMC_TYPE(IntEnum):
    FULL_CMD   = 0
    CMD_ID     = 1
    CMD_SET_ID = 2
    RE_ISSUE   = 3


class AS_MMC_INTERFACE(IntEnum):
    ASCII = 0
    Q3    = 1


class AS_MMC_RESPONSE_MODE(IntEnum):
    NO_RESPONSE         = 0
    RESPONSE            = 1
    SAVE_AND_RESPONSE   = 2
    ONLY_SAVE_RESPONSE  = 3


class AS_MMC_PUBLISH_MODE(IntEnum):
    NO_IMMEDIATE = 0
    IMMEDIATE    = 1
    NOT_PUBLISH  = 2


class AS_MMC_COLLECT_MODE(IntEnum):
    NO_RECOLLECT = 0
    RECOLLECT    = 1


class AS_MMC_RESULT_MODE(IntEnum):
    R_ERROR    = 0
    R_CONTINUE = 1
    R_COMPLETE = 2


# ─────────────────────────────────────────────
# 데이터 클래스 (C struct → Python dataclass)
# ─────────────────────────────────────────────

@dataclass
class PACKET_T:
    MsgId:  int = 0
    Length: int = 0
    Msg:    str = ""


@dataclass
class AS_MMC_IDENT_REQ_T:
    name: str = ""


@dataclass
class AS_MMC_IDENT_RES_T:
    resultMode: int = 0   # 0: nok, 1: ok
    result:     str = ""


@dataclass
class AS_MMC_FLOW_CONTROL_T:
    controlMode: int = 0  # 0: stop, 1: restart
    msgId:       int = 0  # restart 시 재시작 msgId
    controlInfo: str = ""


@dataclass
class AS_MMC_PARAMETER_T:
    sequence: int = 0
    value:    str = ""


@dataclass
class AS_MMC_REQUEST_OLD_T:
    id:           int = 0
    ne:           str = ""
    type:         AS_MMC_TYPE         = AS_MMC_TYPE.FULL_CMD
    referenceId:  int = 0
    interfaces:   AS_MMC_INTERFACE    = AS_MMC_INTERFACE.ASCII
    responseMode: AS_MMC_RESPONSE_MODE = AS_MMC_RESPONSE_MODE.NO_RESPONSE
    publishMode:  AS_MMC_PUBLISH_MODE  = AS_MMC_PUBLISH_MODE.NO_IMMEDIATE
    collectMode:  AS_MMC_COLLECT_MODE  = AS_MMC_COLLECT_MODE.NO_RECOLLECT
    mmc:          str = ""            # max MMC_CMD_LEN (128)
    userid:       str = ""
    display:      str = ""
    cmdDelayTime: int = 0
    retryNo:      int = 0
    curRetryNo:   int = 0
    parameterNo:  int = 0
    priority:     int = 0
    logMode:      int = 0
    parameters:   List[AS_MMC_PARAMETER_T] = field(
                      default_factory=lambda: [AS_MMC_PARAMETER_T() for _ in range(20)])


@dataclass
class AS_MMC_REQUEST_T:
    id:           int = 0
    ne:           str = ""
    type:         AS_MMC_TYPE          = AS_MMC_TYPE.FULL_CMD
    referenceId:  int = 0
    interfaces:   AS_MMC_INTERFACE     = AS_MMC_INTERFACE.ASCII
    responseMode: AS_MMC_RESPONSE_MODE = AS_MMC_RESPONSE_MODE.NO_RESPONSE
    publishMode:  AS_MMC_PUBLISH_MODE  = AS_MMC_PUBLISH_MODE.NO_IMMEDIATE
    collectMode:  AS_MMC_COLLECT_MODE  = AS_MMC_COLLECT_MODE.NO_RECOLLECT
    mmc:          str = ""             # max MMC_CMD_LEN_EX (1000)
    userid:       str = ""
    display:      str = ""
    cmdDelayTime: int = 0
    retryNo:      int = 0
    curRetryNo:   int = 0
    parameterNo:  int = 0
    priority:     int = 0
    logMode:      int = 0
    parameters:   List[AS_MMC_PARAMETER_T] = field(
                      default_factory=lambda: [AS_MMC_PARAMETER_T() for _ in range(20)])
    Reserved:     str = ""


@dataclass
class AS_MMC_REQUEST_T_NETWIN:
    """NetWindow 전용 MMC 요청 구조 (C 원본의 raw 레이아웃 대응)"""
    id:           int = 0
    ne:           str = ""
    type:         int = 0
    referenceId:  int = 0
    interfaces:   int = 0
    responseMode: int = 0
    publishMode:  int = 0
    collectMode:  int = 0
    mmc:          str = ""   # 128 bytes
    userid:       str = ""   # 16 bytes
    display:      str = ""   # 16 bytes
    cmdDelayTime: int = 0
    retryNo:      int = 0
    curRetryNo:   int = 0
    parameterNo:  int = 0
    priority:     int = 0
    logMode:      int = 0
    parameters:   str = ""   # 2664 bytes raw (AS_MMC_PARAMETER_T 배열 raw)
    mscid:        str = ""
    mscip:        str = ""
    bsmid:        str = ""
    bsmip:        str = ""
    minno:        str = ""
    trequesttime: str = ""


@dataclass
class AS_MMC_ACK_T:
    id:         int = 0
    resultMode: int = 0   # 0: NOK, 1: OK
    result:     List[int] = field(default_factory=lambda: [0] * 40)


@dataclass
class AS_MMC_RESULT_T:
    id:         int = 0
    resultMode: AS_MMC_RESULT_MODE = AS_MMC_RESULT_MODE.R_ERROR
    result:     str = ""           # max MAX_RESULT_MSG (4080)


@dataclass
class AS_ROUTER_INFO_REQ_T:
    userid:   str = ""
    password: str = ""
    equipNo:  int = 0   # max 50
    equipIds: List[str] = field(default_factory=lambda: [""] * 50)


@dataclass
class AS_ROUTER_INFO_T:
    resultMode: int = 0   # 0: nok, 1: ok
    equipId:    str = ""
    ipaddress:  str = ""
    portNo:     int = 0


@dataclass
class AS_ROUTER_INFO_RES_T:
    routerNo:    int = 0
    routerInfos: List[AS_ROUTER_INFO_T] = field(
                     default_factory=lambda: [AS_ROUTER_INFO_T() for _ in range(50)])


@dataclass
class AS_ROUTER_CONFIG_T:
    mode:    int = 0   # 0: raw data, 1: parsed data, 2: both
    equipId: str = ""
    msgIdNo: int = 0
    msgIds:  List[str] = field(default_factory=lambda: [""] * 100)