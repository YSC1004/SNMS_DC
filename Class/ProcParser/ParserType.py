import sys
import os
import threading

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# Constants
# -------------------------------------------------------
RAW_MSG_CHANGE_FLAG = -100
TMP_DH_ID = "TEMP"

# Message IDs / Timer Reasons
DELETE_DATA_HANDLER             = 13001

PARSINGDATA_POLLING_TIME        = 0.01 
PARSINGDATA_POLLING_TIME_OUT    = 12001

DATA_ROUTER_CONN_TIME           = 1
DATA_ROUTER_CONN_TIME_OUT       = 12002

SEARCH_RAW_LOG_TIME_OUT         = 12003
PARSING_RAW_TIME_OUT            = 12004

# -------------------------------------------------------
# ResponseCommand Class
# -------------------------------------------------------
class ResponseCommand:
    def __init__(self):
        self.Id = 0
        self.Ne = ""
        self.IdString = ""
        self.Key = ""
        self.Mmc = ""
        self.TimerKey = 0

class ResponseCommandList(list):
    pass

# -------------------------------------------------------
# DeleteDebugSet Class
# -------------------------------------------------------
class DeleteDebugSet(dict):
    """
    Tracks ExtractDataInfo objects to detect memory leaks.
    Key: DataHandlerId (str), Value: Set of IDs (set)
    """
    def __init__(self):
        super().__init__()
        self.m_Lock = threading.Lock()

    def insert(self, data_handler_id, id_val):
        """
        C++: bool Insert(const char* DataHandlerId, unsigned int Id)
        """
        with self.m_Lock:
            if data_handler_id not in self:
                self[data_handler_id] = set()
            
            # set.add returns None, check existence manually if needed to return bool
            if id_val in self[data_handler_id]:
                return False # Already exists
            
            self[data_handler_id].add(id_val)
            return True

    def remove(self, data_handler_id, id_val):
        """
        C++: bool Remove(const char* DataHandlerId, unsigned int Id)
        """
        with self.m_Lock:
            if data_handler_id not in self:
                print(f"[DeleteDebugSet] [CORE_ERROR] Can't Find DataHandlerId({data_handler_id})")
                return False

            if id_val not in self[data_handler_id]:
                print(f"[DeleteDebugSet] [CORE_ERROR] Can't Find ExtractDataInfo({data_handler_id},{id_val})")
                return False
            
            self[data_handler_id].remove(id_val)
            
            # Clean up empty sets
            if not self[data_handler_id]:
                del self[data_handler_id]
                
            return True

# -------------------------------------------------------
# TemporaryMsgInfo Class
# -------------------------------------------------------
class TemporaryMsgInfo:
    def __init__(self, msg_id, ne_id, port_no, file_pos, msg_size):
        self.m_MsgId = msg_id
        self.m_NeId = ne_id
        self.m_PortNo = port_no
        self.m_FilePos = file_pos
        self.m_MsgSize = msg_size

# -------------------------------------------------------
# ExtractDataInfo Class
# -------------------------------------------------------
class ExtractDataInfo:
    """
    Stores parsing results. Tracks its own lifecycle via ParserWorld's DeleteDebugSet.
    """
    m_ExtractDataInfoId = 0
    m_MsgIdLock = threading.Lock()

    def __init__(self, msg_id=RAW_MSG_CHANGE_FLAG, ident_rule_ptr=None, ident_id_string="", 
                 ne_id="", port_no=0, file_pos=0, msg_size=0, 
                 data_handler_id=TMP_DH_ID, ref_cnt=0):
        
        self.m_MsgId = msg_id
        self.m_IdentRulePtr = ident_rule_ptr
        self.m_IdentIdString = ident_id_string
        self.m_NeId = ne_id
        self.m_PortNo = port_no
        self.m_FilePos = file_pos
        self.m_MsgSize = msg_size
        self.m_DataHandlerId = data_handler_id
        self.m_RefCnt = ref_cnt
        
        # Assign Unique ID
        with ExtractDataInfo.m_MsgIdLock:
            ExtractDataInfo.m_ExtractDataInfoId += 1
            self.m_ID = ExtractDataInfo.m_ExtractDataInfoId

        # Track Instance (Insert to DebugSet)
        try:
            from ParserWorld import ParserWorld
            world = ParserWorld.get_instance()
            if world and hasattr(world, 'm_DeleteDebugSet') and world.m_DeleteDebugSet:
                world.m_DeleteDebugSet.insert(self.m_DataHandlerId, self.m_ID)
        except Exception:
            # Can happen during shutdown/init
            pass

    def __del__(self):
        """
        C++: ~ExtractDataInfo()
        Removes itself from the tracker.
        """
        try:
            # Lazy Import to avoid circular dependency
            from ParserWorld import ParserWorld
            world = ParserWorld.get_instance()
            
            # Check validity before accessing (Python interpreter shutdown check)
            if world and hasattr(world, 'm_DeleteDebugSet') and world.m_DeleteDebugSet:
                world.m_DeleteDebugSet.remove(self.m_DataHandlerId, self.m_ID)
        except Exception:
            # Ignore errors during interpreter shutdown (globals might be None)
            pass

    def dup_instance(self, ref_cnt, data_handler_id=None):
        """
        C++: ExtractDataInfo* DupInstance(...)
        Creates a copy for a specific consumer.
        """
        target_dh_id = data_handler_id if data_handler_id else self.m_DataHandlerId
        
        return ExtractDataInfo(
            self.m_MsgId,
            self.m_IdentRulePtr,
            self.m_IdentIdString,
            self.m_NeId,
            self.m_PortNo,
            self.m_FilePos,
            self.m_MsgSize,
            target_dh_id,
            ref_cnt
        )