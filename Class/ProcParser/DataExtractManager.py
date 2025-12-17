import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.CommType import AsParsedDataT

class DataExtractManager:
    """
    Manages the extraction of data from raw messages based on rules.
    Delegates the result back to the connection.
    """
    def __init__(self, conn):
        """
        C++: DataExtractManager(DataRouterConnection* Conn)
        """
        self.m_Conn = conn
        
        # Variables for GUID generation (from InitGUIDMaker)
        self.m_Pid = 0
        self.m_Tid = 0
        self.m_Ip = ""

    def __del__(self):
        """
        C++: ~DataExtractManager()
        """
        pass

    def parsing_result(self, consumers, p_data):
        """
        C++: void ParsingResult(const char* Consumers, const AS_PARSED_DATA_T* Pdata)
        Callback method that sends the parsed result to the connection.
        """
        if self.m_Conn:
            self.m_Conn.parsing_result(consumers, p_data)

    # -------------------------------------------------------
    # Methods required by DataRouterConnection usage
    # (Not in provided C++ snippet, but necessary for runtime)
    # -------------------------------------------------------
    def init_guid_maker(self, pid, tid, ip):
        self.m_Pid = pid
        self.m_Tid = tid
        self.m_Ip = ip

    def data_extract(self, ident_rule, ident_id_string, raw_msg, session_name):
        """
        Performs the actual regex matching and data extraction.
        """
        # [NOTE] Actual extraction logic was missing in the provided C++ snippet.
        # This is a placeholder implementation to prevent crashes.
        
        # 1. Create Result Object
        p_data = AsParsedDataT()
        p_data.neId = "" # Will be filled by Connection
        p_data.eventId = ident_id_string
        
        # 2. TODO: Implement Regex Matching here using ident_rule
        # ...
        
        # 3. Send Result (Simulating a successful parse)
        # In a real implementation, this would loop through matches
        p_data.listSequence = 0 # Example
        self.parsing_result(session_name, p_data)
        
        # Send EOR (End of Record)
        eor_data = AsParsedDataT()
        eor_data.listSequence = -1
        self.parsing_result(session_name, eor_data)