"""
Python 변환: CommTypeList.h → CommTypeList.py

C++ STL 컨테이너 → Python 대응표
  list<T>        → List[T]  (list 서브클래스 또는 타입 별칭)
  map<K,V>       → Dict[K,V]
  set<T>         → Set[T]
  vector<T>      → List[T]
  pair<K,V>      → Tuple[K,V]
"""

from __future__ import annotations
from typing import Dict, List, Set, Tuple, Optional, TYPE_CHECKING

from Common.CommType import (
    AS_MMC_PARAMETER_T,
    AS_MMC_GEN_COMMAND_T,
    AS_PORT_STATUS_INFO_T,
    AS_PROC_CONTROL_T,
    AS_CMD_OPEN_PORT_T,
    AS_LOG_STATUS_T,
    AS_PROCESS_STATUS_T,
    AS_DATA_HANDLER_INFO_T,
    AS_SUB_PROC_INFO_T,
)

# 순환 참조 방지: 실제 사용 시 import
if TYPE_CHECKING:
    from Common.AsSocket import AsSocket
    from Common.ConnectionMgr import ConnectionMgr

# ─────────────────────────────────────────────
# 단순 타입 별칭 (typedef)
# ─────────────────────────────────────────────

# typedef list<string>
StringList = List[str]

# typedef list<AS_MMC_PARAMETER_T *>
MmcParameterList         = List[AS_MMC_PARAMETER_T]
MmcParameterListIterator = int  # Python 은 이터레이터가 내장 — 인덱스 힌트용

# typedef list<AS_PORT_STATUS_INFO_T*>
PortStatusInfoList         = List[AS_PORT_STATUS_INFO_T]
PortStatusInfoListIterator = int

# pair 타입 별칭
ProcPidInfoSet    = Tuple[str, int]
ProcControlSet    = Tuple[str, AS_PROC_CONTROL_T]
CmdOpenPortReqSet = Tuple[int, AS_CMD_OPEN_PORT_T]
LogStatusSet      = Tuple[str, AS_LOG_STATUS_T]

ConnectorIdPortInfoSet = Tuple[str, "CmdOpenPortList"]
DataHandlerInfoMap     = Dict[str, AS_DATA_HANDLER_INFO_T]
DataHandlerInfoMapSet  = Tuple[str, AS_DATA_HANDLER_INFO_T]
IntStringMap           = Dict[int, str]
IntStringMapSet        = Tuple[int, str]
SubProcInfoMap         = Dict[str, AS_SUB_PROC_INFO_T]
TimerKeyMap            = Dict[str, "StringIntKey"]
TimerKeyMapSet         = Tuple[str, "StringIntKey"]
ConnectionMgrVector    = List["ConnectionMgr"]

# ─────────────────────────────────────────────
# C++ class → Python class
# (소멸자의 delete 루프 → Python GC 처리로 불필요,
#  clear() → list/dict/set 자체 메서드 사용)
# ─────────────────────────────────────────────

class MmcGenCommandList(list):
    """
    C++: class MmcGenCommandList : public list<AS_MMC_GEN_COMMAND_T*>
    소멸자에서 포인터 해제 → Python GC 자동 처리
    """
    def __init__(self):
        super().__init__()

    # 편의 메서드: 타입 안전 추가
    def append_cmd(self, cmd: AS_MMC_GEN_COMMAND_T) -> None:
        self.append(cmd)

    def clear_all(self) -> None:
        self.clear()


class SocketConnectionList(list):
    """
    C++: class SocketConnectionList : public list<AsSocket*>
    AsSocket 인스턴스를 담는 리스트
    """
    def __init__(self):
        super().__init__()


class ProcPidInfoMap(dict):
    """
    C++: class ProcPidInfoMap : public map<string, int>
    ProcessId → PID 매핑
    """
    def __init__(self):
        super().__init__()


class ProcControlMap(dict):
    """
    C++: class ProcControlMap : public map<string, AS_PROC_CONTROL_T>
    ProcessId → AS_PROC_CONTROL_T 매핑
    """
    def __init__(self):
        super().__init__()


class PidSet(set):
    """
    C++: class PidSet : public set<int>
    PID 집합
    """
    def __init__(self):
        super().__init__()


class CmdOpenPortList(list):
    """
    C++: class CmdOpenPortList : public list<AS_CMD_OPEN_PORT_T>
    """
    def __init__(self):
        super().__init__()


class ConnectorIdPortInfoMap(dict):
    """
    C++: class ConnectorIdPortInfoMap : public map<string, CmdOpenPortList*>
    ConnectorId → CmdOpenPortList 매핑
    """
    def __init__(self):
        super().__init__()


class StringSet(set):
    """
    C++: class StringSet : public set<string>
    """
    def __init__(self):
        super().__init__()


class LogStatusMap(dict):
    """
    C++: class LogStatusMap : public map<string, AS_LOG_STATUS_T*>
    name → AS_LOG_STATUS_T 매핑
    """
    def __init__(self):
        super().__init__()


class LogStatusVector(list):
    """
    C++: class LogStatusVector : public vector<AS_LOG_STATUS_T*>
    """
    def __init__(self):
        super().__init__()


class SubSectionValueMap(dict):
    """
    C++: class SubSectionValueMap : public map<string, frStringVector>
    SubSection key → 문자열 리스트 매핑
    frStringVector → List[str] 대응
    """
    def __init__(self):
        super().__init__()

    def get_values(self, key: str) -> List[str]:
        return self.get(key, [])


class SectionValueMap(dict):
    """
    C++: class SectionValueMap : public map<string, SubSectionValueMap>
    Section key → SubSectionValueMap 매핑
    설정 파일 파싱 결과 저장에 사용
    """
    def __init__(self):
        super().__init__()

    def get_subsection(self, section: str) -> SubSectionValueMap:
        return self.get(section, SubSectionValueMap())


class ProcessInfoList(list):
    """
    C++: class ProcessInfoList : public list<AS_PROCESS_STATUS_T>
    """
    def __init__(self):
        super().__init__()


class StringIntKey:
    """
    C++: class StringIntKey { string m_Id; int m_Key; }
    TimerKeyMap 의 value 타입
    """
    def __init__(self, id_: str = "", key: int = 0):
        self.m_Id:  str = id_
        self.m_Key: int = key

    def __repr__(self) -> str:
        return f"StringIntKey(m_Id={self.m_Id!r}, m_Key={self.m_Key})"