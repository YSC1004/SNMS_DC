"""
AsciiMmcType.py - C++ AsciiMmcType.h 변환
MMC/패킷 공통 상수, Enum, 데이터클래스 정의
CommType.py 가 이 모듈에 의존하므로 의존성 최하위 파일입니다.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum

# ── 패킷 크기 상수 ─────────────────────────────────────────────────────
MAX_PACKET      = 4096
MAX_MSG         = 4088
MAX_RESULT_MSG  = 4080

# ── 필드 길이 상수 ─────────────────────────────────────────────────────
EQUIP_ID_LEN    = 40
MMC_CMD_LEN     = 128
MMC_CMD_LEN_EX  = 1000
MMC_CMD_LEN_EX2 = 500
MMC_VAL_LEN     = 128
USER_ID_LEN     = 16
PASSWORD_LEN    = 16
IP_ADDRESS_LEN  = 16    # "xxx.xxx.xxx.xxx"
EVENT_ID_LEN    = 32

# ── MMC 메시지 ID 상수 ─────────────────────────────────────────────────
AS_MMC_REQ          = 6
AS_MMC_REQ_ACK      = 2
AS_MMC_REQ_OLD      = 1
AS_MMC_RES          = 11
AS_MMC_RES_ACK      = 12
AS_MMC_IDENT_REQ    = 21
AS_MMC_IDENT_RES    = 22
AS_MMC_FLOW_CONTROL = 31

# ── Router 메시지 ID 상수 ──────────────────────────────────────────────
AS_ROUTER_INFO_REQ  = 101
AS_ROUTER_INFO_RES  = 102
AS_ROUTER_CONFIG    = 111

# ── Enum ───────────────────────────────────────────────────────────────
class AsMmcType(IntEnum):
    FULL_CMD    = 0
    CMD_ID      = 1
    CMD_SET_ID  = 2
    RE_ISSUE    = 3

class AsMmcInterface(IntEnum):
    ASCII   = 0
    Q3      = 1

class AsMmcResponseMode(IntEnum):
    NO_RESPONSE         = 0
    RESPONSE            = 1
    SAVE_AND_RESPONSE   = 2
    ONLY_SAVE_RESPONSE  = 3

class AsMmcPublishMode(IntEnum):
    NO_IMMEDIATE    = 0
    IMMEDIATE       = 1
    NOT_PUBLISH     = 2

class AsMmcCollectMode(IntEnum):
    NO_RECOLLECT    = 0
    RECOLLECT       = 1

class AsMmcResultMode(IntEnum):
    R_ERROR     = 0
    R_CONTINUE  = 1
    R_COMPLETE  = 2

# ── 데이터클래스 ───────────────────────────────────────────────────────

@dataclass
class PacketT:
    """PACKET_T"""
    msg_id: int = 0
    length: int = 0
    msg:    str = ""        # MAX_MSG(4088) 바이트

@dataclass
class AsMmcIdentReq:
    """AS_MMC_IDENT_REQ_T"""
    name: str = ""          # max 80자

@dataclass
class AsMmcIdentRes:
    """AS_MMC_IDENT_RES_T"""
    result_mode: int = 0    # 0: NOK, 1: OK
    result:      str = ""   # max 256자

@dataclass
class AsMmcFlowControl:
    """AS_MMC_FLOW_CONTROL_T"""
    control_mode: int = 0   # 0: stop, 1: restart
    msg_id:       int = 0
    control_info: str = ""  # max 256자

@dataclass
class AsMmcParameter:
    """AS_MMC_PARAMETER_T"""
    sequence: int = 0
    value:    str = ""      # max MMC_VAL_LEN(128)자

@dataclass
class AsMmcRequestOld:
    """AS_MMC_REQUEST_OLD_T (AS_MMC_REQ_OLD 구버전)"""
    id:            int = 0
    ne:            str = ""
    type:          AsMmcType         = AsMmcType.FULL_CMD
    reference_id:  int = 0
    interfaces:    AsMmcInterface    = AsMmcInterface.ASCII
    response_mode: AsMmcResponseMode = AsMmcResponseMode.NO_RESPONSE
    publish_mode:  AsMmcPublishMode  = AsMmcPublishMode.NO_IMMEDIATE
    collect_mode:  AsMmcCollectMode  = AsMmcCollectMode.NO_RECOLLECT
    mmc:           str = ""          # max MMC_CMD_LEN(128)
    userid:        str = ""          # max USER_ID_LEN(16)
    display:       str = ""          # max IP_ADDRESS_LEN(16)
    cmd_delay_time:int = 0
    retry_no:      int = 0
    cur_retry_no:  int = 0
    parameter_no:  int = 0
    priority:      int = 0
    log_mode:      int = 0
    parameters:    list[AsMmcParameter] = field(default_factory=list)  # max 20

@dataclass
class AsMmcRequest:
    """AS_MMC_REQUEST_T (AS_MMC_REQ 현행)"""
    id:            int = 0
    ne:            str = ""
    type:          AsMmcType         = AsMmcType.FULL_CMD
    reference_id:  int = 0
    interfaces:    AsMmcInterface    = AsMmcInterface.ASCII
    response_mode: AsMmcResponseMode = AsMmcResponseMode.NO_RESPONSE
    publish_mode:  AsMmcPublishMode  = AsMmcPublishMode.NO_IMMEDIATE
    collect_mode:  AsMmcCollectMode  = AsMmcCollectMode.NO_RECOLLECT
    mmc:           str = ""          # max MMC_CMD_LEN_EX(1000)
    userid:        str = ""
    display:       str = ""
    cmd_delay_time:int = 0
    retry_no:      int = 0
    cur_retry_no:  int = 0
    parameter_no:  int = 0
    priority:      int = 0
    log_mode:      int = 0
    parameters:    list[AsMmcParameter] = field(default_factory=list)  # max 20
    reserved:      str = ""          # max 100자

@dataclass
class AsMmcRequestNetwin:
    """AS_MMC_REQUEST_T_NETWIN — NetWindow 전용 확장 구조체"""
    id:            int = 0
    ne:            str = ""
    type:          int = 0
    reference_id:  int = 0
    interfaces:    int = 0
    response_mode: int = 0
    publish_mode:  int = 0
    collect_mode:  int = 0
    mmc:           str = ""          # max 128
    userid:        str = ""          # max 16
    display:       str = ""          # max 16
    cmd_delay_time:int = 0
    retry_no:      int = 0
    cur_retry_no:  int = 0
    parameter_no:  int = 0
    priority:      int = 0
    log_mode:      int = 0
    parameters:    str = ""          # raw 2664바이트 (직렬화된 파라미터)
    mscid:         str = ""          # max 40
    mscip:         str = ""          # max 15
    bsmid:         str = ""          # max 40
    bsmip:         str = ""          # max 15
    minno:         str = ""          # max 16
    trequesttime:  str = ""          # max 16+282

@dataclass
class AsMmcAck:
    """AS_MMC_ACK_T"""
    id:          int = 0
    result_mode: int = 0    # 0: NOK, 1: OK
    result:      list[int] = field(default_factory=list)  # int[40]

@dataclass
class AsMmcResult:
    """AS_MMC_RESULT_T"""
    id:          int = 0
    result_mode: AsMmcResultMode = AsMmcResultMode.R_ERROR
    result:      str = ""        # max MAX_RESULT_MSG(4080)

@dataclass
class AsRouterInfoReq:
    """AS_ROUTER_INFO_REQ_T"""
    userid:    str = ""
    password:  str = ""
    equip_no:  int = 0           # max 50
    equip_ids: list[str] = field(default_factory=list)  # max 50 × EQUIP_ID_LEN

@dataclass
class AsRouterInfo:
    """AS_ROUTER_INFO_T"""
    result_mode: int = 0         # 0: NOK, 1: OK
    equip_id:    str = ""
    ipaddress:   str = ""
    port_no:     int = 0

@dataclass
class AsRouterInfoRes:
    """AS_ROUTER_INFO_RES_T"""
    router_no:    int = 0
    router_infos: list[AsRouterInfo] = field(default_factory=list)  # max 50

@dataclass
class AsRouterConfig:
    """AS_ROUTER_CONFIG_T"""
    mode:      int = 0           # 0: raw, 1: parsed, 2: both
    equip_id:  str = ""
    msg_id_no: int = 0
    msg_ids:   list[str] = field(default_factory=list)  # max 100 × EVENT_ID_LEN