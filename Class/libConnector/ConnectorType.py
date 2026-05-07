"""
ConnectorType.py
C++ ConnectorType.h → Python 변환

ProcNaConnector 전역 데이터 구조 / 상수 정의.
  - AgentPacket / EmsAgentPacket / Fe1Packet 등 패킷 구조체
  - 프로토콜 상수 (#define)
  - DCMediationList / DCMediationVector
  - MsgIdMap / RshPidMap
  - NEC 관련 데이터 클래스
  - 기타 타입 별칭
"""

from __future__ import annotations
import ctypes
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ProcConnector.DCMediation import DCMediation

# ─────────────────────────────────────────────────────────────────────────────
# 크기 상수
# ─────────────────────────────────────────────────────────────────────────────
MAX_PARAMETER_DATA     = 4080
MAX_EMS_PARAMETER_DATA = 4040
MAX_FE1_PARAMETER_DATA = 4078

# ─────────────────────────────────────────────────────────────────────────────
# 패킷 구조체
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SEGMENTIND_T:
    SegFlag: int = 0
    SeqNum:  int = 0

@dataclass
class AgentPacket:
    Ptype:             int            = 0
    MsgId:             int            = 0
    SegmentIndicator:  SEGMENTIND_T   = field(default_factory=SEGMENTIND_T)
    Length:            int            = 0
    Msg:               bytearray      = field(
        default_factory=lambda: bytearray(MAX_PARAMETER_DATA))

@dataclass
class EmsAgentPacket:
    Ptype:             int            = 0
    MsgId:             int            = 0
    neId:              str            = ""
    SegmentIndicator:  SEGMENTIND_T   = field(default_factory=SEGMENTIND_T)
    Length:            int            = 0
    Msg:               bytearray      = field(
        default_factory=lambda: bytearray(MAX_EMS_PARAMETER_DATA))

@dataclass
class Fe1Packet:
    m_sHead: bytes    = b'\x00' * 18
    Msg:     bytearray = field(
        default_factory=lambda: bytearray(4078))

@dataclass
class MNMuxPacket:
    m_sHead: bytes    = b'\x00' * 18
    Msg:     bytearray = field(
        default_factory=lambda: bytearray(4608))

# ─────────────────────────────────────────────────────────────────────────────
# ASCII AGENT 패킷 타입 상수
# ─────────────────────────────────────────────────────────────────────────────
APPSTS_P          = 0x00000001
APPSTS_ACK_P      = 0x00000002
CLOSEPORT_P       = 0x00000003
CLOSEPORT_ACK_P   = 0x00000004
INPUTCOMM_P       = 0x00000005
INPUTCOMM_ACK_P   = 0x00000006
OUTPUTMSG_P       = 0x00000007
PORTCONF_P        = 0x00000008
PORTCONF_ACK_P    = 0x00000009
STARTMSG_P        = 0x0000000A
STARTMSG_ACK_P    = 0x0000000B
STOPMSG_P         = 0x0000000C
MDREINIT_P        = 0x0000000D

# ASCII NAIM 패킷 타입 상수
CLOSEPORT_P_NAIM      = 0x00000001
CLOSEPORT_ACK_P_NAIM  = 0x00000002
MMLCOMM_P_NAIM        = 0x00000003
MMLCOMM_ACK_P_NAIM    = 0x00000004
OUTPUTMSG_P_NAIM      = 0x00000005
PROCREADY_P_NAIM      = 0x00000006
PROCREADY_ACK_P_NAIM  = 0x00000007
PROCSTS_P_NAIM        = 0x00000008
PROCSTS_ACK_P_NAIM    = 0x00000009

# ─────────────────────────────────────────────────────────────────────────────
# 타이머 상수 (초 단위)
# ─────────────────────────────────────────────────────────────────────────────
PORTCONF_TIME  = 15
PROCREADY_TIME = 15
t1             = 15
STARTMSG_TIME  = 15
t2             = 15
STOPMSG_TIME   = 15
t3             = 15
INPUTCOMM_TIME = 10
t4             = 10
APPSTS_TIME    = 60
PROCSTS_TIME   = 60
t6             = 60
CLOSEPORT_TIME = 15
t7             = 15

# 타임아웃 이유값
APPSTS_ACK_TIMEOUT   = 11000
STARTMSG_ACK_TIMEOUT = 11001
PORTCONF_ACK_TIMEOUT = 11002
INPUTCOMM_ACK_TIMEOUT= 11003
PROCREADY_ACK_TIMEOUT= 11002
PROCSTS_ACK_TIMEOUT  = 11000

# ─────────────────────────────────────────────────────────────────────────────
# 메시지 구조체
# ─────────────────────────────────────────────────────────────────────────────
TEMIP_DATA_LENGTH = 4095  # MAX_RAW_MSG - 1

@dataclass
class TEMIP_DATA_T:
    MsgId:             int          = 0
    NeId:              str          = ""
    Length:            int          = 0
    SegmentIndicator:  SEGMENTIND_T = field(default_factory=SEGMENTIND_T)
    Msg:               bytearray    = field(
        default_factory=lambda: bytearray(TEMIP_DATA_LENGTH))

@dataclass
class PROCREADY_T:
    NeIndex: int = 0

@dataclass
class PORTCONF_T:
    PortType: int = 0
    NeIndex:  int = 0

@dataclass
class INOUT_STRING_T:
    InOutString: bytearray = field(
        default_factory=lambda: bytearray(MAX_PARAMETER_DATA))

INPUTCOMM_T = INOUT_STRING_T
OUTPUTMSG_T = INOUT_STRING_T

@dataclass
class INCOMM_ACK_T:
    SyntaxCheckFlag: int       = 0
    InOutString:     bytearray = field(
        default_factory=lambda: bytearray(MAX_PARAMETER_DATA))

@dataclass
class STARTMSG_T:
    MsgType: int = 0

@dataclass
class STOPMSG_T:
    MsgType: int = 0

AGENT_CHECK_COUNT = 5

# ─────────────────────────────────────────────────────────────────────────────
# 상태 열거형
# ─────────────────────────────────────────────────────────────────────────────
class AGENT_STATUS(IntEnum):
    WAIT_PORTCONF_ACK  = 0
    WAIT_STARTMSG_ACK  = 1
    WAIT_APP_STS_ACK   = 2
    WAIT_INPUTCOMM_ACK = 3
    WAIT_ANY           = 4

class NAIM_STATUS(IntEnum):
    WAIT_PROCREADY_ACK = 0
    WAIT_PROC_STS_ACK  = 1
    WAIT_MMCCOMM_ACK   = 2
    WAIT_ANY_INPUT     = 3

# ─────────────────────────────────────────────────────────────────────────────
# DCMediation 컨테이너
# ─────────────────────────────────────────────────────────────────────────────

class DCMediationList(list):
    """C++: list<DCMediation*>"""
    pass

class DCMediationVector(list):
    """C++: vector<DCMediation*>"""
    pass

# ─────────────────────────────────────────────────────────────────────────────
# 맵 타입
# ─────────────────────────────────────────────────────────────────────────────

class MsgIdMap(dict):
    """C++: map<int, int> — NE MsgId → Connector Domain MsgId"""
    pass

class RshPidMap(dict):
    """C++: map<int, string>"""
    pass

# ─────────────────────────────────────────────────────────────────────────────
# 이벤트/타임아웃 상수
# ─────────────────────────────────────────────────────────────────────────────
FILE_EXIST_CHECK_TIMEOUT   = 60
NEXT_RAW_DATA_GET_TIMEOUT  = 30
NEXT_COMMAND_EVENT_TIMEOUT = 3
CHECK_COMMAND_EVENT_TIMEOUT= 3
TSPRT_CHECK_EVENT_TIMEOUT  = 60 * 10   # 10 min
TSPRT_RESPONSE_EVENT_TIMEOUT = 60 * 7  # 7 min
RSH_CONNECT_RETRY_TIMEOUT  = 60 * 10   # 10 min
FTP_CONNECT_RETRY_TIMEOUT  = 60 * 3    # 3 min

PORT_REPORT_TIMEOUT        = 60 * 1    # 1 min
PORT_REPORT_EVENT          = 10051

FILE_EXIST_CHECK_TIME      = 10001
FILE_EXIST_CHECK_FAIL      = 10002

HALF_HOUR_CHANGED_EVENT    = 10011
HOUR_CHANGED_EVENT         = 10012
DAY_CHANGED_EVENT          = 10013

MIN5_CHANGED_EVENT         = 10014
MIN15_CHANGED_EVENT        = 10015
MIN5_CHANGED_EVENT_LG      = 10016
MIN_CHANGED_EVENT          = 10017

NEXT_RAW_DATA_GET_EVENT    = 10021
NEXT_COMMAND_EVENT         = 10031
CHECK_COMMAND_EVENT        = 10032
TSPRT_CHECK_EVENT          = 10041
TSPRT_RESPONSE_EVENT       = 10042

NEC_CONN_HOLD_TIME         = 3201
NEC_CONN_HOLD_TIMEOUT      = 960       # 16분
NEC_CFG_INIT_TIME          = 3202

# ─────────────────────────────────────────────────────────────────────────────
# NEC 관련 데이터 클래스
# ─────────────────────────────────────────────────────────────────────────────

class TOKEN_MODE(IntEnum):
    STRCOL_ENDCOL = 0
    STRCOL_TOKEN  = 1

@dataclass
class MsgTokenInfo:
    m_Mode:           TOKEN_MODE = TOKEN_MODE.STRCOL_ENDCOL
    m_StartColumn:    int        = 0
    m_EndColumn:      int        = 0
    m_TokenIndex:     int        = 0
    m_TokenDelimiter: str        = ""

@dataclass
class NecSDHData:
    m_MsgNumber:          str = ""
    m_Date:               str = ""
    m_Time:               str = ""
    m_SiteCategory:       str = ""
    m_SiteId:             str = ""
    m_SiteName:           str = ""
    m_EquipType:          str = ""
    m_NeName:             str = ""
    m_NE_SECTION_PATH_NAME: str = ""
    m_DetailName:         str = ""
    m_ObjectType:         str = ""
    m_Severity:           str = ""
    m_ProbableCause:      int = -1
    m_EventDetail:        str = ""

@dataclass
class NecCfgData:
    m_SiteCategory: str = ""
    m_SiteId:       str = ""
    m_SiteName:     str = ""
    m_NeName:       str = ""
    m_EquipType:    str = ""

@dataclass
class ProbableCause:
    m_MsgNumber:       str = ""
    m_ProbableCauseCode: int = 0

class ProbableCauseMap(dict):
    """C++: map<string, ProbableCause*>"""
    def Clear(self) -> None:
        self.clear()

class NecCfgDataMap(dict):
    """C++: map<string, NecCfgData*>"""
    def Clear(self) -> None:
        self.clear()

# ─────────────────────────────────────────────────────────────────────────────
# 응답 명령 / 기타 타입
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ResponseCommand:
    Id:       int = 0
    Ne:       str = ""
    Mmc:      str = ""
    TimerKey: int = 0

ResponseCommandMap  = Dict[int, ResponseCommand]
DataCollectItemList = List[str]

# ─────────────────────────────────────────────────────────────────────────────
# 장비 매핑
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EquipMapping:
    m_Id:        str = ""
    m_MappingId: str = ""

EquipMappingVec = List[EquipMapping]

@dataclass
class HostList:
    m_Hostname: str = ""
    m_Hostip:   str = ""
    m_Sshid:    str = ""
    m_Sshpass:  str = ""

HostListVec = List[HostList]

@dataclass
class MscMapping:
    m_MscId:        str = ""
    m_MscMappingId: str = ""

MscMappingVec = List[MscMapping]

@dataclass
class BtsMapping:
    m_BtsId:        str = ""
    m_BtsMappingId: str = ""

BtsMappingMap = Dict[str, BtsMapping]

# ─────────────────────────────────────────────────────────────────────────────
# NE 카운트 정보
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NeCntInfo:
    m_ItemCnt:      int = 0
    m_ItemTotalCnt: int = 0

class NeCntInfoMap(dict):
    """C++: map<string, NeCntInfo*>"""
    def Clear(self) -> None:
        self.clear()