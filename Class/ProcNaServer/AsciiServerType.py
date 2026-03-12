"""
AsciiServerType.py
C++ AsciiServerType.h/.C → Python 변환
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from Common.CommType import (
    AS_CONNECTION_INFO_T,
    AS_CONNECTOR_INFO_T,
    AS_MANAGER_INFO_T,
    AS_COMMAND_AUTHORITY_INFO_T,
    AS_PROCESS_STATUS_T,
    AS_MMC_LOG_T,
    AS_MMC_GEN_RESULT_T,
    AS_MMC_RESULT_T,
    AS_ROUTER_INFO_T,
    AS_SESSION_CFG_T,
    AS_SYSTEM_INFO_T,
    AS_MMC_RESULT_MODE,
)
from Common.AsciiMmcType import AS_MMC_REQUEST_T
from Util.fr_logger import make_log_def

_log = make_log_def("AsciiServer", "ConnectionInfoList")

# ──────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────
WAIT_MANAGER_START_TIME         = 45
WAIT_MANAGER_START_TIMEOUT      = 10001

WAIT_DATA_HANDLER_START_TIME    = 120   # 60 → 120
WAIT_DATA_HANDLER_START_TIMEOUT = 10002

SESSION_TYPE_GUI = 1
SESSION_TYPE_MMC = 2
SESSION_TYPE_MGR = 3


# ──────────────────────────────────────────────
# ConnectionInfoList
# ──────────────────────────────────────────────
class ConnectionInfoList(list):
    """list<AS_CONNECTION_INFO_T*>"""

    def __init__(self) -> None:
        super().__init__()

    def __del__(self) -> None:
        _log.debug(1, "################### log1")
        self.clear()
        _log.debug(1, "################### log2")


# ──────────────────────────────────────────────
# ConnectorInfo
# ──────────────────────────────────────────────
class ConnectorInfo:
    def __init__(self) -> None:
        self.m_ConnectorInfo: AS_CONNECTOR_INFO_T = AS_CONNECTOR_INFO_T()
        self.m_ConnectionInfoList: ConnectionInfoList = ConnectionInfoList()

    def get_connection_info(self, sequence: int) -> Optional[AS_CONNECTION_INFO_T]:
        """Sequence 번호로 AS_CONNECTION_INFO_T 검색"""
        for info in self.m_ConnectionInfoList:
            if info.Sequence == sequence:
                return info
        return None

    def delete_connection_info(self, sequence: int) -> None:
        """Sequence 번호로 AS_CONNECTION_INFO_T 삭제"""
        _log.debug(1, "################### DeleteConnectionInfo Start!!")
        for i, info in enumerate(self.m_ConnectionInfoList):
            _log.debug(1, f"################### DeleteConnectionInfo : {info.Sequence} {sequence}")
            if info.Sequence == sequence:
                _log.debug(1, f"################### sequence [{sequence}]")
                del self.m_ConnectionInfoList[i]
                return

    # C++ 스타일 호환 alias
    GetConnectionInfo    = get_connection_info
    DeleteConnectionInfo = delete_connection_info


# ──────────────────────────────────────────────
# ConnectorInfoMap
# ──────────────────────────────────────────────
class ConnectorInfoMap(dict):
    """map<string, ConnectorInfo*>"""

    def __init__(self) -> None:
        super().__init__()

    def __del__(self) -> None:
        self.clear()


# ──────────────────────────────────────────────
# ManagerInfo
# ──────────────────────────────────────────────
class ManagerInfo:
    def __init__(self) -> None:
        self.m_ManagerInfo: AS_MANAGER_INFO_T = AS_MANAGER_INFO_T()
        self.m_ConnectorInfoMap: ConnectorInfoMap = ConnectorInfoMap()

    def get_connector_info(self, connector_id: str) -> Optional[ConnectorInfo]:
        return self.m_ConnectorInfoMap.get(connector_id)

    GetConnectorInfo = get_connector_info


# ──────────────────────────────────────────────
# ManagerInfoMap
# ──────────────────────────────────────────────
class ManagerInfoMap(dict):
    """map<string, ManagerInfo*>"""

    def __init__(self) -> None:
        super().__init__()

    def __del__(self) -> None:
        self.clear()


# ──────────────────────────────────────────────
# CommandAuthorityInfoMap
# ──────────────────────────────────────────────
class CommandAuthorityInfoMap(dict):
    """map<string, AS_COMMAND_AUTHORITY_INFO_T*>"""

    def __init__(self) -> None:
        super().__init__()

    def __del__(self) -> None:
        self.clear()


# ──────────────────────────────────────────────
# ProcStatusInfoMap / ProcStatusMap
# ──────────────────────────────────────────────
class ProcStatusInfoMap(dict):
    """map<string, AS_PROCESS_STATUS_T*>"""

    def __init__(self) -> None:
        super().__init__()

    def __del__(self) -> None:
        self.clear()


class ProcStatusMap(dict):
    """map<string, ProcStatusInfoMap*>"""

    def __init__(self) -> None:
        super().__init__()


# ──────────────────────────────────────────────
# ExtReqIndentify  (오타 유지: Indentify)
# ──────────────────────────────────────────────
class ExtReqIndentify:
    """External MMC 요청 식별 정보"""

    def __init__(self) -> None:
        self.GId: int          = -1          # Global MsgId
        self.Id: int           = -1          # External MsgId
        self.ReqConn           = None        # MMCRequestConnection (순환 참조 방지용 Any)
        self.IssuedTimeStr: str = ""
        self.IssuedTime: float  = 0.0        # C++ time_t → float (POSIX timestamp)
        self.MmcInfo: AS_MMC_LOG_T = AS_MMC_LOG_T()


# ──────────────────────────────────────────────
# MMCRequestList
# ──────────────────────────────────────────────
class MMCRequestList(list):
    """list<AS_MMC_REQUEST_T*>"""
    pass


# ──────────────────────────────────────────────
# MmcGenResultQueue  (thread-safe deque)
# ──────────────────────────────────────────────
class MmcGenResultQueue(list):
    """
    list<AS_MMC_GEN_RESULT_T*> + mutex
    push_back / pop_front 을 lock으로 보호
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()

    def push_back(self, result: AS_MMC_GEN_RESULT_T) -> None:
        with self._lock:
            self.append(result)

    # C++ alias
    Push_back = push_back

    def get_mmc_gen_result_node(self) -> Optional[AS_MMC_GEN_RESULT_T]:
        with self._lock:
            if self:
                return self.pop(0)
            return None

    GetMmcGenResultNode = get_mmc_gen_result_node


# ──────────────────────────────────────────────
# MMCRequestQueueList
# ──────────────────────────────────────────────
class MMCRequestQueueList(list):
    """list<MMCRequestQueue*>  (MMCRequestQueue는 별도 파일에서 import)"""
    pass


# ──────────────────────────────────────────────
# MmcPublishSet
# ──────────────────────────────────────────────
class MmcPublishSet:
    def __init__(self,
                 mmc_log: AS_MMC_LOG_T,
                 ext_con: Optional[ExtReqIndentify] = None) -> None:
        self.m_MmcLog: AS_MMC_LOG_T              = mmc_log
        self.m_ExtReq: Optional[ExtReqIndentify] = ext_con

    def __del__(self) -> None:
        self.m_MmcLog = None
        self.m_ExtReq = None


# ──────────────────────────────────────────────
# MmcPublishSetQueue  (thread-safe deque)
# ──────────────────────────────────────────────
class MmcPublishSetQueue(list):
    """list<MmcPublishSet*> + mutex"""

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()

    def get_mmc_publish_set(self) -> Optional[MmcPublishSet]:
        with self._lock:
            if self:
                return self.pop(0)
            return None

    def insert_mmc_publish_set(self, mmc_set: MmcPublishSet) -> None:
        with self._lock:
            self.append(mmc_set)

    # C++ alias
    GetMmcPublishSet     = get_mmc_publish_set
    InsertMMCPublishSet  = insert_mmc_publish_set


# ──────────────────────────────────────────────
# MmcPublishSetQueueList
# ──────────────────────────────────────────────
class MmcPublishSetQueueList(list):
    """vector<MmcPublishSetQueue*>"""
    pass


# ──────────────────────────────────────────────
# RouterInfoList
# ──────────────────────────────────────────────
class RouterInfoList(list):
    """vector<AS_ROUTER_INFO_T>"""
    pass


# ──────────────────────────────────────────────
# MmcRequestMap  (thread-safe)
# ──────────────────────────────────────────────
class MmcRequestMap(dict):
    """
    map<int, AS_MMC_REQUEST_T*>
    key: Ascii Global MsgId
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()

    def find(self, id_: int) -> Optional[AS_MMC_REQUEST_T]:
        with self._lock:
            return self.get(id_)

    def erase(self, id_: int) -> None:
        with self._lock:
            self.pop(id_, None)

    def insert(self, id_: int, mmc_req: AS_MMC_REQUEST_T) -> bool:
        with self._lock:
            if id_ in self:
                return False
            self[id_] = mmc_req
            return True

    # C++ alias
    Find   = find
    Erase  = erase
    Insert = insert


# ──────────────────────────────────────────────
# ExtMMCReqMap  (thread-safe)
# ──────────────────────────────────────────────
class ExtMMCReqMap(dict):
    """
    map<int, ExtReqIndentify*>
    key: Ascii Global MsgId
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()

    def find(self, id_: int) -> Optional[ExtReqIndentify]:
        with self._lock:
            return self.get(id_)

    def erase(self, id_: int) -> None:
        with self._lock:
            self.pop(id_, None)

    def insert(self, id_: int, ext_req: ExtReqIndentify) -> bool:
        with self._lock:
            if id_ in self:
                return False
            self[id_] = ext_req
            return True

    # C++ alias
    Find   = find
    Erase  = erase
    Insert = insert


# ──────────────────────────────────────────────
# MMCResultStored
# ──────────────────────────────────────────────
class MMCResultStored:
    def __init__(self) -> None:
        self.Gid: int                      = -1
        self.ExtId: int                    = -1
        self.ResultMode: AS_MMC_RESULT_MODE = AS_MMC_RESULT_MODE.R_ERROR
        self.ResultMsg: str                 = ""
        self.IssuedTimeStr: str             = ""
        self.IssuedTime: float              = 0.0    # time_t → float
        self.ResultStartTime: str           = ""
        self.ResultEndTime: str             = ""
        self.MmcInfo: AS_MMC_LOG_T          = AS_MMC_LOG_T()

    def print(self) -> None:
        from Common.AsUtil import AsUtil
        _log.debug(1, "MMCResult Info :")
        print(
            f"ne : {self.MmcInfo.ne}\n"
            f"cmd : {self.MmcInfo.mmc}\n"
            f"g-msgid:{self.Gid}\n"
            f"ext-msgid :{self.ExtId}\n"
            f"resultMode {AsUtil.GetEnumTypeString_RESULT_MODE(self.ResultMode)}\n"
            f"ExtSysIP :  {self.MmcInfo.display}\n"
            f"Result : [{self.ResultMsg}]"
        )

    # C++ alias
    Print = print


# ──────────────────────────────────────────────
# typedef 대응 타입 별칭
# ──────────────────────────────────────────────
MMCResultStoredMap  = dict    # map<int, MMCResultStored*>
MMCResultStoredList = list    # list<MMCResultStored*>

AsSystemInfoMap  = dict       # map<string, AS_SYSTEM_INFO_T>
AsSessionCfgMap  = dict       # map<int,    AS_SESSION_CFG_T>