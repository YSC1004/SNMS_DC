import sys
import os
import threading
import time
from collections import deque

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrThreadWorld import FrThreadWorld
from Class.ProcParser.RuleType import RAW_MSG_CHANGE_FLAG
from Class.Event.FrLogger import FrLogger

class DataSender(FrThreadWorld):
    """
    Manages a thread-safe queue of ExtractDataInfo objects.
    Used by DataRouterConnection to fetch parsed data.
    """
    def __init__(self, consumer, conn):
        """
        C++: DataSender(string Consumer, DataRouterConnection* Conn)
        """
        super().__init__()
        self.m_Consumer = consumer
        self.m_DataRouterConnection = conn
        
        self.m_ExtractDataInfoList = deque()
        self.m_IdentListLock = threading.Lock()
        self.m_SenderLock = threading.Lock()

    def __del__(self):
        """
        C++: ~DataSender()
        """
        self.clear_extract_data_info_list()

    def clear_extract_data_info_list(self):
        """
        C++: void ClearExtractDataInfoList()
        """
        with self.m_IdentListLock:
            self.m_ExtractDataInfoList.clear()
            # Python GC handles deletion of objects inside

    def push_extract_data_info(self, info):
        """
        C++: bool PushExtractDataInfo(ExtractDataInfo* Info)
        """
        with self.m_IdentListLock:
            self.m_ExtractDataInfoList.append(info)
        return True

    def get_extract_data_info(self):
        """
        C++: ExtractDataInfo* GetExtractDataInfo()
        Pop from front (FIFO).
        """
        ptr = None
        with self.m_IdentListLock:
            if self.m_ExtractDataInfoList:
                ptr = self.m_ExtractDataInfoList.popleft()
        return ptr

    def get_end_extract_data_info(self):
        """
        C++: ExtractDataInfo* GetEndExtractDataInfo()
        Pop from back (LIFO) - Used during ReIdentify to drain queue.
        """
        # Note: C++ source had a bug where it returned GetExtractDataInfo() immediately.
        # Here we implement the logic implied by the function name and usage context.
        ptr = None
        with self.m_IdentListLock:
            if self.m_ExtractDataInfoList:
                ptr = self.m_ExtractDataInfoList.pop()
        return ptr

    def sender_lock(self):
        self.m_SenderLock.acquire()

    def sender_unlock(self):
        self.m_SenderLock.release()

    def re_identify(self, raw_msg_fp, ident_mgr):
        """
        C++: void ReIdentify(FILE* RawMsgFp, IdentManager* IdentMgr)
        Drains the queue and re-processes items with new rules.
        """
        tmp_extract_data_info_list = []
        
        print(f"[DataSender] ReIdentify({self.m_Consumer}) Cnt : {len(self.m_ExtractDataInfoList)}")

        # 1. Drain current queue to temp list
        while True:
            ptr = self.get_end_extract_data_info()
            if ptr:
                tmp_extract_data_info_list.append(ptr)
            else:
                break
        
        re_ident_cnt = 0
        
        # 2. Process temp list
        # Iterate in reverse to maintain original order if popped from back?
        # C++ used pop_back into list, then iterated list. 
        # If we want FIFO preservation during re-queue:
        # [A, B, C] -> pop_back C -> [C], pop_back B -> [C, B], pop_back A -> [C, B, A]
        # Iterating [C, B, A] -> process C, then B, then A.
        # Push back C -> [C], push B -> [C, B]... Order preserved.
        
        for ptr in tmp_extract_data_info_list:
            if ptr.m_MsgId != RAW_MSG_CHANGE_FLAG:
                try:
                    # Seek and Read
                    raw_msg_fp.seek(ptr.m_FilePos)
                    
                    # Read bytes
                    data = raw_msg_fp.read(ptr.m_MsgSize)
                    
                    if len(data) == ptr.m_MsgSize:
                        # Decode bytes to string for identification
                        msg_buf = data.decode('utf-8', errors='ignore')
                        
                        # Identify
                        info = ident_mgr.data_identify(msg_buf)
                        
                        consumer_matched = False
                        
                        if info and info.m_IdentRulePtr:
                            # Check if Consumer exists in new rule
                            # C++: IdentRulePtr->m_ConsumerVector is list of strings
                            if self.m_Consumer in info.m_IdentRulePtr.m_ConsumerVector:
                                ptr.m_IdentRulePtr = info.m_IdentRulePtr
                                ptr.m_IdentIdString = info.m_IdentIdString
                                self.push_extract_data_info(ptr)
                                re_ident_cnt += 1
                                consumer_matched = True
                        
                        # Note: info object is local, but ptr is reused.
                        # If not matched, ptr is discarded (GC)
                        
                    else:
                        print(f"[DataSender] [CORE_ERROR] Msg Read Error -- Read: {len(data)}, Expected: {ptr.m_MsgSize}")
                        
                except Exception as e:
                    print(f"[DataSender] [CORE_ERROR] File/Parsing Error: {e}")
                    
            else:
                # Keep RAW_MSG_CHANGE_FLAG items
                self.push_extract_data_info(ptr)

        print(f"[DataSender] Finish Reidentify({self.m_Consumer}) Cnt : {re_ident_cnt}")

    def run(self):
        """
        C++: virtual void Run()
        Standard FrThreadWorld entry point.
        DataSender is mostly passive (polled), so this might just keep thread alive or be empty.
        """
        while self.m_RunStatus:
            time.sleep(1)