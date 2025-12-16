import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Util.FrBaseList import FrStringVector

# ==========================================================================
# [Note]
# C++의 DELETE_ITERATOR 매크로는 Python의 Garbage Collection에 의해
# 자동으로 메모리가 해제되므로 구현할 필요가 없습니다.
# ==========================================================================

# -------------------------------------------------------
# List Containers (std::list, std::vector 대응)
# -------------------------------------------------------

class StringList(list):
    """typedef list<string> stringList"""
    pass

class MmcParameterList(list):
    """typedef list<AS_MMC_PARAMETER_T *>"""
    pass

class MmcGenCommandList(list):
    """
    class MmcGenCommandList : public list<AS_MMC_GEN_COMMAND_T*>
    C++에서는 소멸자에서 delete를 수행하지만 Python은 불필요
    """
    pass

class PortStatusInfoList(list):
    """typedef list<AS_PORT_STATUS_INFO_T*>"""
    pass

class SocketConnectionList(list):
    """class SocketConnectionList : public list<AsSocket*>"""
    pass

class CmdOpenPortList(list):
    """class CmdOpenPortList : public list<AS_CMD_OPEN_PORT_T>"""
    pass

class LogStatusVector(list):
    """class LogStatusVector : public vector<AS_LOG_STATUS_T*>"""
    pass

class ProcessInfoList(list):
    """class ProcessInfoList : public list<AS_PROCESS_STATUS_T>"""
    pass

class ConnectionMgrVector(list):
    """typedef vector<ConnectionMgr*>"""
    pass

# -------------------------------------------------------
# Map Containers (std::map 대응)
# -------------------------------------------------------

class ProcPidInfoMap(dict):
    """class ProcPidInfoMap : public map<string, int>"""
    pass

class ProcControlMap(dict):
    """class ProcControlMap : public map<string, AS_PROC_CONTROL_T>"""
    pass

class ConnectorIdPortInfoMap(dict):
    """
    class ConnectorIdPortInfoMap : public map<string, CmdOpenPortList*>
    Key: ConnectorId, Value: CmdOpenPortList
    """
    pass

class LogStatusMap(dict):
    """class LogStatusMap : public map<string, AS_LOG_STATUS_T*>"""
    pass

class SubSectionValueMap(dict):
    """
    class SubSectionValueMap : public map<string, frStringVector>
    AsEnvrion에서 사용됨
    """
    pass

class SectionValueMap(dict):
    """
    class SectionValueMap : public map<string, SubSectionValueMap>
    AsEnvrion에서 사용됨
    """
    pass

class DataHandlerInfoMap(dict):
    """typedef map<string, AS_DATA_HANDLER_INFO_T*>"""
    pass

class TimerKeyMap(dict):
    """typedef map<string, StringIntKey*>"""
    pass

class IntStringMap(dict):
    """typedef map<int, string>"""
    pass

class SubProcInfoMap(dict):
    """typedef map<string, AS_SUB_PROC_INFO_T*>"""
    pass

# -------------------------------------------------------
# Set Containers (std::set 대응)
# -------------------------------------------------------

class PidSet(set):
    """class PidSet : public set<int>"""
    pass

class StringSet(set):
    """class StringSet : public set<string>"""
    pass

# -------------------------------------------------------
# Simple Wrapper Classes
# -------------------------------------------------------

class StringIntKey:
    """
    class StringIntKey { string m_Id; int m_Key; }
    """
    def __init__(self):
        self.m_Id = ""
        self.m_Key = 0