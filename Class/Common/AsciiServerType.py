import sys
import os
import threading
from collections import deque

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 필요 모듈 Import
try:
    from Class.Common.CommType import *
except ImportError:
    pass

try:
    from Class.Common.AsUtil import AsUtil
except ImportError:
    AsUtil = None

try:
    from Class.Event.FrLogger import get_logger
    logger = get_logger()
    def fr_debug(msg): logger.write(f"[DEBUG] {msg}")
except ImportError:
    def fr_debug(msg): print(f"[DEBUG] {msg}")

# -------------------------------------------------------
# 1. Connection Info Classes
# -------------------------------------------------------
class ConnectionInfoList(list):
    """
    List of AS_CONNECTION_INFO_T (C++ struct pointer)
    """
    def __init__(self):
        super().__init__()

    def __del__(self):
        # Python GC가 처리하므로 명시적 delete 불필요
        pass

class ConnectorInfo:
    def __init__(self):
        self.m_ConnectionInfoList = ConnectionInfoList()
        self.m_ConnectorInfo = None # AS_CONNECTOR_INFO_T()

    def get_connection_info(self, sequence):
        for info in self.m_ConnectionInfoList:
            if hasattr(info, 'Sequence') and info.Sequence == sequence:
                return info
        return None

    def delete_connection_info(self, sequence):
        fr_debug("################### DeleteConnectionInfo Start!!")
        for i, info in enumerate(self.m_ConnectionInfoList):
            fr_debug(f"################### DeleteConnectionInfo : {info.Sequence} {sequence}")
            if info.Sequence == sequence:
                fr_debug(f"################### sequence [{sequence}]")
                del self.m_ConnectionInfoList[i]
                return

class ConnectorInfoMap(dict):
    """Key: ConnectorId, Value: ConnectorInfo"""
    pass

class ManagerInfo:
    def __init__(self):
        self.m_ConnectorInfoMap = ConnectorInfoMap()
        self.m_ManagerInfo = None # AS_MANAGER_INFO_T()

    def get_connector_info(self, connector_id):
        return self.m_ConnectorInfoMap.get(connector_id)

class ManagerInfoMap(dict):
    """Key: ManagerId, Value: ManagerInfo"""
    pass

class CommandAuthorityInfoMap(dict):
    pass

class ProcStatusInfoMap(dict):
    pass

# -------------------------------------------------------
# 2. MMC Generation Result Queue
# -------------------------------------------------------
class MmcGenResultQueue(deque):
    def __init__(self):
        super().__init__()
        self.m_MmcGenListLock = threading.Lock()

    def push_back(self, result):
        with self.m_MmcGenListLock:
            self.append(result)

    def get_mmc_gen_result_node(self):
        with self.m_MmcGenListLock:
            if self:
                return self.popleft()
        return None

# -------------------------------------------------------
# 3. MMC Publish Set & Queue
# -------------------------------------------------------
class ExtReqIndentify:
    def __init__(self):
        self.GId = -1
        self.Id = -1
        self.ReqConn = None
        self.IssuedTimeStr = ""
        self.IssuedTime = 0
        self.MmcInfo = None # AS_MMC_LOG_T()

class MmcPublishSet:
    def __init__(self, mmc_log, ext_req):
        self.m_MmcLog = mmc_log
        self.m_ExtReq = ext_req

class MmcPublishSetQueue(deque):
    def __init__(self):
        super().__init__()
        self.m_MmcPublishSetLock = threading.Lock()

    def get_mmc_publish_set(self):
        with self.m_MmcPublishSetLock:
            if self:
                return self.popleft()
        return None

    def insert_mmc_publish_set(self, mmc_set):
        with self.m_MmcPublishSetLock:
            self.append(mmc_set)

# -------------------------------------------------------
# 4. MMC Request Maps
# -------------------------------------------------------
class MmcRequestMap(dict):
    def __init__(self):
        super().__init__()
        self.m_MMCReqMapLock = threading.Lock()

    def find(self, id_val):
        with self.m_MMCReqMapLock:
            return self.get(id_val)

    def erase(self, id_val):
        with self.m_MMCReqMapLock:
            if id_val in self:
                del self[id_val]

    def insert(self, id_val, mmc_req):
        with self.m_MMCReqMapLock:
            if id_val in self:
                return False
            self[id_val] = mmc_req
            return True

class ExtMMCReqMap(dict):
    def __init__(self):
        super().__init__()
        self.m_ExtMMCReqMapLock = threading.Lock()

    def find(self, id_val):
        with self.m_ExtMMCReqMapLock:
            return self.get(id_val)

    def erase(self, id_val):
        with self.m_ExtMMCReqMapLock:
            if id_val in self:
                del self[id_val]

    def insert(self, id_val, ext_req):
        with self.m_ExtMMCReqMapLock:
            if id_val in self:
                return False
            self[id_val] = ext_req
            return True

# -------------------------------------------------------
# 5. MMC Result Stored
# -------------------------------------------------------
class MMCResultStored:
    def __init__(self):
        self.Gid = -1
        self.ExtId = -1
        self.ResultMode = 0 # R_ERROR (FAIL)
        self.ResultMsg = ""
        self.IssuedTimeStr = ""
        self.IssuedTime = 0
        self.ResultStartTime = ""
        self.ResultEndTime = ""
        self.MmcInfo = None # AS_MMC_LOG_T()

    def print_info(self):
        fr_debug("MMCResult Info :")
        
        # AsUtil이 있으면 Enum 변환, 없으면 숫자 출력
        res_mode_str = self.ResultMode
        if AsUtil:
            # AsUtil.get_result_mode_string 호출
            if hasattr(AsUtil, 'get_result_mode_string'):
                res_mode_str = AsUtil.get_result_mode_string(self.ResultMode)
        
        ne = self.MmcInfo.ne if hasattr(self.MmcInfo, 'ne') else ""
        mmc = self.MmcInfo.mmc if hasattr(self.MmcInfo, 'mmc') else ""
        disp = self.MmcInfo.display if hasattr(self.MmcInfo, 'display') else ""

        print(f"ne : {ne}\n"
              f"cmd : {mmc}\n"
              f"g-msgid:{self.Gid}\n"
              f"ext-msgid :{self.ExtId}\n"
              f"resultMode {res_mode_str}\n"
              f"ExtSysIP :  {disp}\n"
              f"Result : [{self.ResultMsg}]")