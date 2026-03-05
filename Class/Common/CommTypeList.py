"""
CommTypeList.py - C++ CommTypeList.h 변환
공통 컨테이너(list/map/set/vector) 타입 정의
"""

from __future__ import annotations
from typing import Any

from Common.CommType import (
    AsMmcGenCommand, AsPortStatusInfo, AsProcessStatus,
    AsLogStatus, AsCmdOpenPort, AsProcControl,
    AsSubProcInfo, AsDataHandlerInfo,
)

# ──────────────────────────────────────────────
# 단순 타입 별칭 (C++ typedef 대응)
# ──────────────────────────────────────────────
StringList          = list[str]
MmcParameterList    = list[Any]       # list[AS_MMC_PARAMETER_T*]
PortStatusInfoList  = list[AsPortStatusInfo]
ProcessInfoList     = list[AsProcessStatus]
ConnectionMgrVector = list[Any]       # list[ConnectionMgr*]
DataHandlerInfoMap  = dict[str, AsDataHandlerInfo]
IntStringMap        = dict[int, str]
SubProcInfoMap      = dict[str, AsSubProcInfo]

# ──────────────────────────────────────────────
# 소멸자에서 요소 delete 가 필요했던 C++ 클래스
# → Python GC가 처리하므로 list/dict 그대로 사용
# ──────────────────────────────────────────────

class MmcGenCommandList(list):
    """list[AsMmcGenCommand] — C++ MmcGenCommandList 대응"""
    pass

class SocketConnectionList(list):
    """list[AsSocket] — C++ SocketConnectionList 대응"""
    pass

class ProcPidInfoMap(dict):
    """dict[str, int] — C++ ProcPidInfoMap 대응 (ProcessId → Pid)"""
    pass

class ProcControlMap(dict):
    """dict[str, AsProcControl] — C++ ProcControlMap 대응"""
    pass

class PidSet(set):
    """set[int] — C++ PidSet 대응"""
    pass

class CmdOpenPortList(list):
    """list[AsCmdOpenPort] — C++ CmdOpenPortList 대응"""
    pass

class ConnectorIdPortInfoMap(dict):
    """dict[str, CmdOpenPortList] — ConnectorId → Port 목록"""
    pass

class StringSet(set):
    """set[str] — C++ StringSet 대응"""
    pass

class LogStatusMap(dict):
    """dict[str, AsLogStatus] — C++ LogStatusMap 대응"""
    pass

class LogStatusVector(list):
    """list[AsLogStatus] — C++ LogStatusVector 대응"""
    pass

class SubSectionValueMap(dict):
    """dict[str, list[str]] — C++ SubSectionValueMap 대응"""
    pass

class SectionValueMap(dict):
    """dict[str, SubSectionValueMap] — C++ SectionValueMap 대응"""
    pass

# ──────────────────────────────────────────────
# StringIntKey (C++ 클래스)
# ──────────────────────────────────────────────
class StringIntKey:
    """C++ StringIntKey 클래스 대응"""
    def __init__(self, id_: str = "", key: int = 0):
        self.m_id  = id_
        self.m_key = key

TimerKeyMap = dict[str, StringIntKey]   # dict[str, StringIntKey*]