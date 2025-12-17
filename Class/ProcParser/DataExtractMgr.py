import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Lazy Import to avoid circular dependency issues if DataExtractor imports Mgr
try:
    from Class.ProcParser.DataExtractor import DataExtractor
except ImportError:
    pass

class DataExtractMgr:
    """
    Manager class for Data Extraction.
    Delegates actual parsing tasks to the DataExtractor instance.
    """
    def __init__(self):
        """
        C++: DataExtractMgr::DataExtractMgr()
        """
        # Create DataExtractor instance, passing self as parent/manager
        self.m_DataExtractor = DataExtractor(self)

    def __del__(self):
        """
        C++: DataExtractMgr::~DataExtractMgr()
        """
        pass

    def init_guid_maker(self, pid, thread_id, host_ip):
        """
        C++: void InitGUIDMaker(int Pid, int ThreadId, string HostIP)
        """
        if self.m_DataExtractor:
            self.m_DataExtractor.init_guid_maker(pid, thread_id, host_ip)

    def data_extract_by_info(self, info, consumer):
        """
        C++: void DataExtract(IdentInfo* Info, const char* Consumer)
        Overloaded method wrapper for IdentInfo object.
        """
        if self.m_DataExtractor:
            # Extract fields from IdentInfo and delegate
            self.m_DataExtractor.parsing(
                info.m_IdentRulePtr, 
                info.m_IdentIdString, 
                info.m_ConvertMsg, 
                consumer
            )

    def data_extract(self, ident_rule, id_string, convert_msg, consumer):
        """
        C++: void DataExtract(IdentRule* IdentRule, const char* IdString, char* ConvertMsg, const char* Consumer)
        Direct parsing method.
        """
        if self.m_DataExtractor:
            self.m_DataExtractor.parsing(ident_rule, id_string, convert_msg, consumer)

    def remake_msg(self):
        """
        C++: void ReMakeMsg()
        """
        if self.m_DataExtractor:
            self.m_DataExtractor.remake_msg()