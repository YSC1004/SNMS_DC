import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.ProcParser.DataExtractor import DataExtractor

class DataExtractMgr:
    """
    Manages the extraction of data from raw messages.
    Acts as a bridge between DataRouterConnection and DataExtractor.
    """
    def __init__(self, conn):
        """
        C++: DataExtractManager(DataRouterConnection* Conn)
        """
        self.m_Conn = conn
        
        # Create the core parsing engine
        # Pass 'self' so DataExtractor can callback (ParsingResult)
        self.m_DataExtractor = DataExtractor(self) 

    def __del__(self):
        """
        C++: ~DataExtractManager()
        """
        pass

    def init_guid_maker(self, pid, tid, ip):
        """
        Initialize GUID Maker in DataExtractor.
        """
        if self.m_DataExtractor:
            self.m_DataExtractor.init_guid_maker(pid, tid, ip)

    def data_extract(self, ident_rule, ident_id_string, raw_msg, session_name):
        """
        Entry point called by DataRouterConnection.
        Delegates the actual parsing work to DataExtractor.
        """
        if self.m_DataExtractor:
            self.m_DataExtractor.parsing(ident_rule, ident_id_string, raw_msg, session_name)

    def parsing_result(self, consumers, p_data):
        """
        C++: void ParsingResult(const char* Consumers, const AS_PARSED_DATA_T* Pdata)
        Callback method called by DataExtractor when parsing is successful.
        Forwards the result to the Connection.
        """
        if self.m_Conn:
            self.m_Conn.parsing_result(consumers, p_data)

    def parse_error(self, error_info):
        """
        C++: void ParseError(ParseErrorInfo& ErrorInfo)
        Callback method called by DataExtractor (XML parsing) when an error occurs.
        """
        if self.m_Conn:
            # Assuming connection handles logging or error reporting
            # In C++: m_Conn->SendParseError(errorInfo) or similar
            # For now, we just print or delegate if method exists
            print(f"[DataExtractMgr] Parse Error: {error_info.m_ErrorStr}")