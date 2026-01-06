import sys
import os
import time
import copy
from datetime import datetime

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.CommType import AsParsedDataT, PARSED_DATA_SEG_BLK_SIZE
from Class.ProcParser.ParsingIdentMgr import ParsingIdentMgr
from Class.ProcParser.RuleType import * # Import Rule Constants

# -------------------------------------------------------
# XML Related Imports
# -------------------------------------------------------
import xml.parsers.expat  # C++ expat 대응 (Error 처리 등)

from Class.ProcParser.XMLParserMgr import XmlParserMgr

class RuleInnerDataRec:
    """
    Helper class for recursive XML data extraction.
    """
    def __init__(self):
        self.m_RecValue = None          # Single String
        self.m_RecValueList = None      # List of Strings
        self.m_RuleInnerDataRecVecVec = None # Nested structure (List of List of RuleInnerDataRec)

class ParsedDataInfo:
    """
    Helper class for handling result set expansion (Cartesian product) during XML parsing.
    """
    def __init__(self, attr_no, base_result, offset):
        self.m_AttributeNo = attr_no
        # Make a copy of the bytearray up to the current offset
        self.m_Result = bytearray(base_result[:offset]) 
        self.m_ResultPtr = offset # Logical pointer (index) in bytearray
        
class GUIDMaker:
    """
    Generates Unique IDs for segmented data blocks.
    """
    def __init__(self):
        self.m_HostKey = hex(id(self))[2:] # Memory Address Hex
        self.m_Pid = 0
        self.m_Tid = 0
        self.m_GuiSeq = 0
        self.m_Guid = ""

    def init(self, pid, thread_id, host_ip):
        self.m_HostKey += f"-{host_ip}"
        self.m_Pid = pid
        self.m_Tid = thread_id

    def get_guid(self):
        self.m_GuiSeq += 1
        now = time.time()
        sec = int(now)
        ms = int((now - sec) * 1000)
        
        # Format: HostKey-MS-Sec-Pid-Tid-Seq
        self.m_Guid = f"{self.m_HostKey}-{hex(ms)[2:]}-{hex(sec)[2:]}-{hex(self.m_Pid)[2:]}-{hex(self.m_Tid)[2:]}-{hex(self.m_GuiSeq)[2:]}"
        return self.m_Guid

class DataExtractor:
    """
    Core Parsing Engine.
    Extracts data from raw messages based on IdentRule definitions.
    Supports ASCII line-based parsing. (XML support stubbed)
    """
    
    TEMP_ITEM_BUF_SIZE = 16000
    MAX_PARSED_DATA_SIZE = 40960 # Example size

    def __init__(self, data_extract_mgr):
        """
        C++: DataExtractor(DataExtractMgr* DataExtractMgr)
        """
        self.m_DataExtractMgr = data_extract_mgr
        self.m_ParsedData = AsParsedDataT()
        
        self.m_CurResultPtr = 0 # Offset index instead of pointer
        self.m_CurAtomicAttrCnt = 0
        self.m_BscNo = -1
        
        self.m_LongResult = bytearray(self.MAX_PARSED_DATA_SIZE)
        self.m_LongResultLen = self.MAX_PARSED_DATA_SIZE
        
        self.m_SplitMsgMap = {} # Line Number -> Line String
        self.m_TokenListMap = {} # Line Number -> Token List
        self.m_PreParsedDataCopy = [] # Cache for previous rule results
        
        self.m_GUIDMaker = GUIDMaker()
        self.m_EndLineNumber = -1
        self.m_MsgBuf = "" # Current Message String

        # [XML 파서 활성화]
        if XmlParserMgr:
            self.m_XmlParserMgr = XmlParserMgr()
        else:
            self.m_XmlParserMgr = None

    def __del__(self):
        """
        C++: ~DataExtractor()
        Performs cleanup. In Python, GC handles memory, but explicit clearing
        can help break circular references or release resources immediately.
        """
        # m_SplitMsgMap.clear()
        if hasattr(self, 'm_SplitMsgMap') and self.m_SplitMsgMap:
            self.m_SplitMsgMap.clear()

        # m_TokenListMap.Clear()
        if hasattr(self, 'm_TokenListMap') and self.m_TokenListMap:
            self.m_TokenListMap.clear()

        # delete m_ParsedData
        self.m_ParsedData = None

        # delete m_LongResult
        self.m_LongResult = None

        # if(m_XmlParserMgr) delete m_XmlParserMgr
        if hasattr(self, 'm_XmlParserMgr'):
            self.m_XmlParserMgr = None
    
    def init_guid_maker(self, pid, thread_id, host_ip):
        self.m_GUIDMaker.init(pid, thread_id, host_ip)

    def parsing(self, ident_rule_ptr, id_string, msg_buf, consumer):
        """
        C++: void Parsing(...)
        Entry point for parsing. Delegates to ASCII or XML parser.
        """
        if not ident_rule_ptr.m_ParsingFlag:
            return

        # XML Flag Check
        if not ident_rule_ptr.m_XMLFlag:
            self.parsing_ascii(ident_rule_ptr, id_string, msg_buf, consumer)
        else:
            # self.parsing_xml(...) # Stub
            pass

    def parsing_ascii(self, ident_rule_ptr, id_string, msg_buf, consumer):
        """
        C++: void ParsingASCII(...)
        Line-based ASCII parsing logic.
        """
        self.m_MsgBuf = msg_buf
        self.line_scanning() # Pre-scan lines
        self.m_TokenListMap.clear()

        start_line_number = 1
        parsing_success_flag = False
        
        # Iterate Template Groups
        for tmpl_grp in ident_rule_ptr.m_TmplGrpList:
            if consumer and not tmpl_grp.check_consumer(consumer):
                continue

            # Iterate Templates inside Group
            tmpl_idx = 0
            while tmpl_idx < len(tmpl_grp.m_TmplVector):
                tmpl_ptr = tmpl_grp.m_TmplVector[tmpl_idx]
                
                # Check End of Message
                if start_line_number == -100 or self.is_end_line(start_line_number):
                    # Handle Group End logic (EOR)
                    self.m_ParsedData.listSequence = -1
                    self.m_ParsedData.attributeNo = 0
                    self.m_ParsedData.bscNo = self.m_BscNo
                    self.m_ParsedData.idString = id_string
                    
                    # Send End Marks for all templates in group
                    for t in tmpl_grp.m_TmplVector:
                        if not t.m_EORHideFlag and not t.m_AtomResultHideFlag:
                            self.m_ParsedData.eventId = t.m_EventId
                            self.m_ParsedData.equipFlag = t.m_EquipFlag
                            self.m_DataExtractMgr.parsing_result(t.m_Consumers, self.m_ParsedData)
                    break 

                parsing_result = False
                line_advance = 0
                tmpl_advance = 0
                
                # Atomic vs List Logic
                if tmpl_ptr.m_TmplType == TMPL_ATOMIC_TYPE:
                    self.m_BscNo = -1
                    self.m_CurResultPtr = 0 # Reset buffer pointer
                    self.m_ParsedData.listSequence = 0
                    
                    parsing_result = self.extract_data_from_tmpl(id_string, tmpl_ptr, start_line_number, True, TMPL_ATOMIC_TYPE)
                    
                    if parsing_result:
                        parsing_success_flag = True
                        line_advance = tmpl_ptr.m_DataSize # LINE_NEXT_DATASIZE
                        tmpl_advance = 1 # TMPL_NEXT
                    else:
                        if tmpl_ptr.m_SkipLine == 0:
                            line_advance = -1 # LINE_END
                        else:
                            line_advance = tmpl_ptr.m_SkipLine # LINE_NEXT_SKIPLINE

                else: # LIST Type
                    # Header Logic omitted for brevity, assume simple list
                    parsing_result = self.extract_data_from_tmpl(id_string, tmpl_ptr, start_line_number, True, TMPL_LIST_TYPE)
                    
                    if parsing_result:
                        self.m_ParsedData.listSequence += 1
                        parsing_success_flag = True
                        if tmpl_ptr.m_NextFlag:
                            tmpl_advance = 1
                        else:
                            line_advance = tmpl_ptr.m_DataSize
                            tmpl_advance = 0 # Loop self (First List Tmpl)
                    else:
                        if tmpl_ptr.m_SkipLine == 0:
                            tmpl_advance = 1
                        else:
                            line_advance = tmpl_ptr.m_SkipLine
                            tmpl_advance = 0 # Retry?

                # Advance Line
                if line_advance == -1:
                    start_line_number = -100
                else:
                    start_line_number += line_advance
                
                # Advance Template
                if tmpl_advance == 1:
                    tmpl_idx += 1
                # Else: tmpl_idx stays same

    def extract_data_from_tmpl(self, id_string, tmpl_ptr, start_line, tmpl_changed, tmpl_type):
        """
        C++: bool ExtractDataFromTmpl(...)
        Extracts all rules within a template.
        """
        if not tmpl_ptr.m_RuleList:
            self.get_line(start_line) # Just check line existence
            return False

        # Init Result Buffer
        if self.m_CurResultPtr == 0:
            # Clear m_LongResult
            # self.m_LongResult = bytearray(self.MAX_PARSED_DATA_SIZE)
            pass
        
        result_offset = self.m_CurResultPtr
        
        # Init ParsedData Struct
        self.m_ParsedData.eventId = tmpl_ptr.m_EventId
        self.m_ParsedData.idString = id_string
        self.m_ParsedData.eventTime = -1
        # listSequence managed outside or accumulated
        self.m_ParsedData.segBlkCnt = 0
        self.m_ParsedData.equipFlag = 0
        
        current_attr_cnt = self.m_ParsedData.attributeNo if self.m_CurResultPtr != 0 else 0
        
        for i, rule in enumerate(tmpl_ptr.m_RuleList):
            item_buf = ""
            
            # Extract
            success, extracted_val = self.extract_data_from_rule(rule, start_line)
            
            if success:
                item_buf = extracted_val
                
                # Null String Flag
                if rule.m_NullStringFlag:
                    if rule.m_InclusionNameFlag:
                        item_buf = f"{rule.m_ParsingName}:"
                    else:
                        item_buf = ""
                else:
                    # Logic for BscNo, PreDataCopy, Mapping, etc.
                    if tmpl_type == TMPL_ATOMIC_TYPE and rule.m_BscNo:
                        try: self.m_BscNo = int(item_buf)
                        except: pass
                    self.m_ParsedData.bscNo = self.m_BscNo
                    
                    # PreDataCopy Logic
                    if rule.m_PreDataCopyFlag and item_buf.strip():
                        if len(self.m_PreParsedDataCopy) <= i:
                            self.m_PreParsedDataCopy.extend([""] * (i - len(self.m_PreParsedDataCopy) + 1))
                        self.m_PreParsedDataCopy[i] = item_buf
                    
                    # Mapping Logic
                    if rule.m_MappingValueFlag and rule.m_DataMapper:
                        mapped = rule.m_DataMapper.find_mapping_value(item_buf)
                        if mapped: item_buf = mapped
                    
                    if rule.m_InclusionNameFlag:
                        item_buf = f"{rule.m_ParsingName}:{item_buf}"

            else: # Fail
                # Null Skip / PreDataCopy fallback
                if rule.m_NullSkipFlag:
                    if rule.m_InclusionNameFlag:
                        item_buf = f"{rule.m_ParsingName}:"
                    else:
                        item_buf = ""
                elif not tmpl_changed and rule.m_PreDataCopyFlag:
                    if len(self.m_PreParsedDataCopy) > i:
                        item_buf = self.m_PreParsedDataCopy[i]
                    else:
                        return False
                else:
                    return False

            # Write to Result Buffer
            # C++ writes string + null terminator
            encoded = item_buf.encode('utf-8') + b'\0'
            end_pos = result_offset + len(encoded)
            
            if end_pos <= self.MAX_PARSED_DATA_SIZE:
                self.m_LongResult[result_offset : end_pos] = encoded
                result_offset = end_pos
                current_attr_cnt += 1
            else:
                print("[DataExtractor] Result Buffer Overflow")
                return False

        self.m_ParsedData.attributeNo = current_attr_cnt
        
        # Send Data
        if tmpl_type == TMPL_ATOMIC_TYPE and tmpl_ptr.m_AtomResultHideFlag:
            pass # Hide
        else:
            # Handle Segmentation if needed (stubbed logic)
            # Copy buffer to ParsedData.result (fixed size 4096)
            limit = 4096
            data_len = result_offset
            
            if data_len <= limit:
                self.m_ParsedData.result = self.m_LongResult[:data_len] # Assign bytes
                self.m_DataExtractMgr.parsing_result(tmpl_ptr.m_Consumers, self.m_ParsedData)
            else:
                # Segment logic
                blk_cnt = (data_len // PARSED_DATA_SEG_BLK_SIZE) + 1
                guid = self.m_GUIDMaker.get_guid()
                self.m_ParsedData.resultExGuid = guid
                
                for k in range(blk_cnt):
                    self.m_ParsedData.segBlkCnt += 1
                    if k == blk_cnt - 1:
                        self.m_ParsedData.segBlkCnt *= -1 # Last block
                    
                    start = k * PARSED_DATA_SEG_BLK_SIZE
                    end = start + PARSED_DATA_SEG_BLK_SIZE
                    chunk = self.m_LongResult[start:end]
                    self.m_ParsedData.resultExResult = chunk
                    
                    self.m_DataExtractMgr.parsing_result(tmpl_ptr.m_Consumers, self.m_ParsedData)

        if tmpl_type == TMPL_ATOMIC_TYPE:
            self.m_CurResultPtr = result_offset
            self.m_CurAtomicAttrCnt = current_attr_cnt
            
        return True

    def extract_data_from_rule(self, rule, start_line):
        """
        C++: bool ExtractDataFromRule(...)
        Extracts data based on rule definition (Line range, parsing type).
        """
        s_line = rule.m_StartLine
        e_line = rule.m_EndLine
        
        for i in range(s_line, e_line + 1):
            target_line = i + start_line - 1
            line_buf = self.get_line(target_line)
            
            if line_buf is None: return False, ""
            
            temp_buf = ""
            
            # Actual Parsing logic
            success, temp_buf = self.extract_data_from_parsing_rule(rule, line_buf, target_line)
            
            if not success: continue
            if not temp_buf: continue # Empty result
            
            # Trim
            if rule.m_TrimFlag == LR_TRIM:
                temp_buf = temp_buf.strip()
            # ... other trim flags
            
            return True, temp_buf
            
        return False, ""

    def extract_data_from_parsing_rule(self, rule, line_buf, line_number):
        """
        C++: bool ExtractDataFromParsingRule(...)
        Implements parsing types: STRSTR_TOKEN, STRCOL_ENDSTR, etc.
        """
        # Example implementation for STRSTR_TOKEN
        if rule.m_ParsingType == STRSTR_TOKEN:
            idx = line_buf.find(rule.m_StartString)
            if idx == -1: return False, ""
            
            start_ptr = idx + len(rule.m_StartString)
            sub_str = line_buf[start_ptr:]
            
            # Tokenize
            tokens = []
            if not rule.m_TokenDelimiter: # Space default
                tokens = sub_str.split()
            else:
                tokens = sub_str.split(rule.m_TokenDelimiter)
                
            # Token Index (1-based in C++, 0-based in Python logic adjustment needed)
            # C++ logic: Index > 0 normal, Index < 0 back token
            t_idx = rule.m_TokenIndex
            val = ""
            
            if t_idx > 0:
                if len(tokens) >= t_idx: val = tokens[t_idx-1]
            elif t_idx < 0:
                if len(tokens) >= abs(t_idx): val = tokens[t_idx] # Python negative index supported
                
            return True, val

        # ... Implement other cases (STRCOL, EXTSIZE, etc.)
        
        return False, ""

    def line_scanning(self):
        """
        C++: void LineScanning()
        Splits m_MsgBuf into lines and stores in m_SplitMsgMap.
        """
        self.m_SplitMsgMap.clear()
        lines = self.m_MsgBuf.splitlines() # Python splitlines handles \n, \r\n
        
        for i, line in enumerate(lines):
            self.m_SplitMsgMap[i] = line
            
        self.m_EndLineNumber = len(lines)

    def get_line(self, line_number):
        """
        C++: char* GetLine(int LineNumber)
        LineNumber is 1-based index.
        """
        idx = line_number - 1
        return self.m_SplitMsgMap.get(idx)

    def is_end_line(self, line_number):
        return line_number > self.m_EndLineNumber
    
    def msg_tokenize_string(self, line, arg2, arg3=None, arg4=None):
        """
        C++: MsgTokenizeString (Overloaded)
        Dispatcher method to handle C++ function overloading.
        
        Case 1: msg_tokenize_string(line, str_list, delimiter)
        Case 2: msg_tokenize_string(line, token_pos, temp_buf, delimiter)
        """
        # Case 1: Second argument is a List (StringVector& StrList)
        if isinstance(arg2, list):
            str_list = arg2
            delimiter = arg3 if arg3 is not None else " "
            return self._msg_tokenize_list(line, str_list, delimiter)
            
        # Case 2: Second argument is an Int (int TokenPos)
        elif isinstance(arg2, int):
            token_pos = arg2
            # arg3 is temp_buf (Ignored in Python, we return the value)
            delimiter = arg4 if arg4 is not None else " "
            return self._msg_tokenize_index(line, token_pos, delimiter)
            
        else:
            print(f"[DataExtractor] [CORE_ERROR] Unknown MsgTokenizeString signature")
            return None

    def _msg_tokenize_list(self, line, str_list, delimiter=" "):
        """
        Internal implementation for populating a list with tokens.
        Corresponds to: 
        void MsgTokenizeString(const char* Line, CharPtrVector& StrList, string Delimiter)
        void MsgTokenizeString(const char* Line, StringVector& StrList, string Delimiter)
        """
        if not delimiter: 
            delimiter = " "

        # C++ check: if(!strstr(Line, Delimiter.c_str()))
        if delimiter != " " and delimiter not in line:
            if delimiter != " ": 
                return

        # Garbage string for 1-based indexing
        str_list.append("")

        # Tokenize Logic
        if delimiter == " ":
            # C++ Logic: Delimiter " " implies skipping empty tokens (standard split)
            tokens = line.split()
            for token in tokens:
                str_list.append(token.strip())
        else:
            # C++ Logic: Explicit delimiter preserves empty tokens if they exist between delimiters?
            # Looking at C++ code: 
            # if(end-start) -> copy
            # else -> if(Delimiter != " ") -> push token (empty)
            # This matches Python's split(delimiter) behavior exactly.
            
            tokens = line.split(delimiter)
            for token in tokens:
                str_list.append(token.strip())

    def _msg_tokenize_index(self, line, token_pos, delimiter=" "):
        """
        Internal implementation for retrieving a specific token.
        Corresponds to:
        char* MsgTokenizeString(char* &Line, int TokenPos, char* TempBuf, string Delimiter)
        
        Returns:
            The found token string, or None if not found.
        """
        if not delimiter: 
            delimiter = " "

        if delimiter != " " and delimiter not in line:
            return None # C++ returns NULL

        tokens = []
        if delimiter == " ":
            tokens = line.split()
        else:
            tokens = line.split(delimiter)

        # 1-based Indexing check
        # C++ Loop counts 1, 2, 3... and checks == TokenPos
        target_idx = token_pos - 1

        if 0 <= target_idx < len(tokens):
            val = tokens[target_idx].strip()
            # C++ copies to TempBuf and returns pointer. 
            # Python returns the value directly. Caller must handle return value.
            return val
            
        return None # Not found
    
    def msg_tokenize_char(self, line, arg2, arg3=None, arg4=None):
        """
        C++: MsgTokenizeChar (Overloaded)
        Splits string by ANY character present in the Delimiter string.
        
        Case 1: msg_tokenize_char(line, str_list, delimiter)
        Case 2: msg_tokenize_char(line, token_pos, temp_buf, delimiter)
        """
        # Case 1: Second argument is a List
        if isinstance(arg2, list):
            str_list = arg2
            delimiter = arg3 if arg3 is not None else " "
            return self._msg_tokenize_char_list(line, str_list, delimiter)
            
        # Case 2: Second argument is an Int (TokenPos)
        elif isinstance(arg2, int):
            token_pos = arg2
            # arg3 is temp_buf (Ignored in Python, return value used instead)
            delimiter = arg4 if arg4 is not None else " "
            return self._msg_tokenize_char_index(line, token_pos, delimiter)
            
        else:
            print(f"[DataExtractor] [CORE_ERROR] Unknown MsgTokenizeChar signature")
            return None

    def _msg_tokenize_char_list(self, line, str_list, delimiter):
        """
        Internal implementation for populating a list.
        Mimics C++ logic:
          - If delimiter is ' ' (space), consecutive spaces are ignored.
          - If delimiter is other char, consecutive delimiters produce empty strings.
        """
        if not delimiter: 
            delimiter = " "

        # Check if any delimiter char exists in line
        has_delimiter = any(d in line for d in delimiter)
        if not has_delimiter:
            return

        # Garbage string for 1-based indexing
        str_list.append("")
        
        tmp = ""
        
        for char in line:
            # Check if current char is one of the delimiters
            if char in delimiter:
                if not tmp:
                    # Buffer is empty (Consecutive delimiters or start with delimiter)
                    if char != ' ':
                        # If delimiter is NOT space, treat as empty token
                        str_list.append("")
                    # If delimiter IS space, ignore (skip)
                else:
                    # Buffer has content, push it
                    str_list.append(tmp.strip())
                    tmp = ""
            else:
                tmp += char
                
        # Flush remaining buffer
        if tmp:
            str_list.append(tmp.strip())

    def _msg_tokenize_char_index(self, line, token_pos, delimiter):
        """
        Internal implementation for retrieving a specific token index.
        """
        if not delimiter: 
            delimiter = " "

        # Check if any delimiter char exists in line
        has_delimiter = any(d in line for d in delimiter)
        if not has_delimiter:
            return None

        # 1-based Indexing logic
        token_cnt = 0
        tmp = ""
        
        for char in line:
            if char in delimiter:
                if not tmp:
                    if char != ' ':
                        token_cnt += 1
                        if token_cnt == token_pos:
                            return "" # Found empty token
                else:
                    token_cnt += 1
                    if token_cnt == token_pos:
                        return tmp.strip()
                    tmp = ""
            else:
                tmp += char
                
        # Flush remaining check
        if tmp:
            token_cnt += 1
            if token_cnt == token_pos:
                return tmp.strip()
                
        return None # Not found
    
    def check_data_type(self, data_type, data):
        """
        C++: bool CheckDataType(int DataType, char* &Data)
        Validates and formats data based on type.
        
        [Python Change]
        Since strings are immutable in Python, we cannot modify 'Data' in place.
        Return tuple: (is_valid: bool, formatted_data: str)
        """
        if not data:
            return False, data

        # 1. String Type
        if data_type == DT_STR:
            # C++: iscntrl check (0x00-0x1F, 0x7F)
            for char in data:
                code = ord(char)
                if (0 <= code <= 31) or (code == 127):
                    return False, data
            return True, data

        # 2. Integer Type
        elif data_type == DT_INT:
            tmp = data.strip()
            if not tmp:
                return False, data

            # Check Digits (handling optional sign)
            check_str = tmp
            if tmp[0] in ('+', '-'):
                check_str = tmp[1:]

            if not check_str.isdigit():
                return False, data

            # Re-formatting (Remove leading zeros)
            # C++: sprintf(Data, "%d", atoi(data));
            try:
                val = int(tmp)
                return True, str(val)
            except ValueError:
                return False, data

        # 3. Float Type
        elif data_type == DT_FLT:
            # C++ Logic: Truncate at '%', skip spaces, check digits/dots
            
            # Handle '%' truncation first
            if '%' in data:
                data = data.split('%')[0]

            tmp = data.strip() # Remove outer spaces
            
            # Iterate to check characters
            # C++ logic allows spaces INSIDE (e.g., "1 2.3") because of 'continue'
            # We mimic strict character validation logic.
            
            idx = 0
            if tmp and tmp[0] in ('+', '-'):
                idx = 1
                
            for i in range(idx, len(tmp)):
                char = tmp[i]
                if char == ' ':
                    continue
                if not char.isdigit() and char != '.':
                    return False, data
                    
            return True, data

        # Default / Unknown
        else:
            print(f"[DataExtractor] [CORE_ERROR] UnKnown Data Type : {data_type}")
            return False, data
        
    def check_data_value_range(self, value_range, data_type, data):
        """
        C++: bool CheckDataValueRange(string ValueRange, int DataType, char* Data)
        Currently returns True (Placeholder).
        Future implementation checks if 'data' falls within 'value_range'.
        """
        return True
    
    def parsing(self, ident_rule_ptr, id_string, msg_buf, consumer):
        """
        C++: void Parsing(...)
        Entry point for parsing. Delegates to ASCII or XML parser.
        """
        if not ident_rule_ptr.m_XMLFlag:
            self.parsing_ascii(ident_rule_ptr, id_string, msg_buf, consumer)
        else:
            self.parsing_xml(ident_rule_ptr, id_string, msg_buf, consumer)
            
    # ------------------------------------------------------------------
    # Constants for State Machine (Local or from RuleType)
    # ------------------------------------------------------------------
    LINE_NEXT_DATASIZE = 1
    LINE_NEXT_SKIPLINE = 2
    LINE_NEXT_HEADER = 3
    LINE_NEXT = 4
    LINE_END = 5
    
    TMPL_NEXT = 1
    FIRST_LIST_TMPL = 2

    def parsing_ascii(self, ident_rule_ptr, id_string, msg_buf, consumer):
        """
        C++: void ParsingASCII(...)
        Core engine for line-based text parsing.
        Iterates through Template Groups and Templates to extract data.
        """
        if not ident_rule_ptr.m_ParsingFlag:
            # debug log...
            return

        self.m_MsgBuf = msg_buf
        self.m_TokenListMap.clear()

        # Pre-scan lines into map
        self.line_scanning()

        # Local variables
        parsing_result = False
        tmpl_changed = False
        first_list_header = False

        start_line_number = 0
        line_which = -1
        tmpl_which = -1
        tmpl_size = 0
        
        tmpl_sequence = 0
        pre_tmpl_sequence = 0
        recent_atomic_seq = 0
        recent_list_seq = 0

        parsing_success_flag = False
        
        # Iterate over Template Groups
        for tmpl_grp_ptr in ident_rule_ptr.m_TmplGrpList:
            
            # Check Consumer
            if consumer:
                if not tmpl_grp_ptr.check_consumer(consumer):
                    continue

            # Reset state for new group
            start_line_number = 1
            tmpl_which = -1
            line_which = -1
            recent_atomic_seq = 0
            recent_list_seq = 0
            self.m_CurResultPtr = 0
            tmpl_changed = True
            pre_tmpl_sequence = 0
            self.m_PreParsedDataCopy.clear()
            
            tmpl_size = len(tmpl_grp_ptr.m_TmplVector)
            parsing_success_flag = False
            first_list_header = True
            parsing_result = False
            self.m_BscNo = -1
            self.m_ListSequence = 0
            self.m_ParsedData.eventTime = -1

            # Debug log for tmpl list size...

            # Inner Loop: Iterate Templates
            # Using while loop because tmpl_sequence is modified manually logic
            tmpl_sequence = 0
            while tmpl_sequence < tmpl_size:
                
                tmpl_ptr = tmpl_grp_ptr.m_TmplVector[tmpl_sequence]
                
                if pre_tmpl_sequence == tmpl_sequence:
                    tmpl_changed = False
                else:
                    tmpl_changed = True
                    
                pre_tmpl_sequence = tmpl_sequence

                # -------------------------------------------------------
                # 1. End of Parsing Check (EOR)
                # -------------------------------------------------------
                if start_line_number == -100 or self.is_end_line(start_line_number):
                    if not parsing_success_flag:
                        # Logic for empty result parsing (omitted or handled by logic)
                        break # Next group

                    # Send EOR (End of Record) Signal
                    self.m_ParsedData.listSequence = -1
                    self.m_ParsedData.attributeNo = 0
                    self.m_ParsedData.bscNo = self.m_BscNo
                    self.m_ParsedData.idString = id_string
                    
                    for t in tmpl_grp_ptr.m_TmplVector:
                        if not t.m_EORHideFlag:
                            if not t.m_AtomResultHideFlag:
                                self.m_ParsedData.eventId = t.m_EventId
                                self.m_ParsedData.equipFlag = t.m_EquipFlag
                                self.m_DataExtractMgr.parsing_result(t.m_Consumers, self.m_ParsedData)
                    
                    break # Break inner loop, move to next group

                # -------------------------------------------------------
                # 2. Extract Data (Atomic vs List)
                # -------------------------------------------------------
                if tmpl_ptr.m_TmplType == TMPL_ATOMIC_TYPE:
                    self.m_BscNo = -1
                    self.m_CurResultPtr = 0
                    self.m_ListSequence = 0

                    parsing_result = self.extract_data_from_tmpl(id_string, tmpl_ptr, start_line_number, tmpl_changed, TMPL_ATOMIC_TYPE)

                    if parsing_result:
                        parsing_success_flag = True
                        line_which = self.LINE_NEXT_DATASIZE
                        tmpl_which = self.TMPL_NEXT
                        recent_atomic_seq = tmpl_sequence
                    else:
                        if tmpl_ptr.m_SkipLine == 0:
                            line_which = self.LINE_END
                        else:
                            line_which = self.LINE_NEXT_SKIPLINE

                else: # TMPL_LIST_TYPE
                    # Handle Headers
                    if first_list_header:
                        start_line_number += tmpl_ptr.m_HeaderSize
                        first_list_header = False
                        recent_list_seq = tmpl_sequence
                    else:
                        if tmpl_ptr.m_HeaderSize:
                            if recent_list_seq != tmpl_sequence:
                                start_line_number += tmpl_ptr.m_HeaderSize

                    parsing_result = self.extract_data_from_tmpl(id_string, tmpl_ptr, start_line_number, tmpl_changed, TMPL_LIST_TYPE)

                    if parsing_result:
                        if tmpl_ptr.m_HeaderSize:
                            recent_list_seq = tmpl_sequence
                    else:
                        if recent_list_seq != tmpl_sequence:
                            start_line_number -= tmpl_ptr.m_HeaderSize

                    if parsing_result:
                        self.m_ListSequence += 1
                        parsing_success_flag = True
                        if tmpl_ptr.m_NextFlag:
                            tmpl_which = self.TMPL_NEXT
                        else:
                            line_which = self.LINE_NEXT_DATASIZE
                            tmpl_which = self.FIRST_LIST_TMPL
                    else: # Fail
                        if tmpl_ptr.m_SkipLine == 0:
                            tmpl_which = self.TMPL_NEXT
                            line_which = -1 # No op
                        else:
                            tmpl_which = -1 # No op
                            line_which = self.LINE_NEXT_SKIPLINE

                # -------------------------------------------------------
                # 3. State Machine: Update Template Sequence
                # -------------------------------------------------------
                if tmpl_which == self.TMPL_NEXT:
                    tmpl_sequence += 1
                    if tmpl_sequence == len(tmpl_grp_ptr.m_TmplVector):
                        # End of vector
                        if len(tmpl_grp_ptr.m_TmplVector) == 1:
                            tmpl_sequence = 0
                        else:
                            # Wrap around to start of list block
                            tmpl_sequence = recent_list_seq
                        
                        if not parsing_result:
                            line_which = self.LINE_NEXT
                            
                    self.m_PreParsedDataCopy.clear()

                elif tmpl_which == self.FIRST_LIST_TMPL:
                    tmpl_sequence = recent_list_seq
                
                # else: tmpl_sequence stays same

                # -------------------------------------------------------
                # 4. State Machine: Update Line Number
                # -------------------------------------------------------
                if line_which == self.LINE_NEXT_DATASIZE:
                    start_line_number += tmpl_ptr.m_DataSize
                elif line_which == self.LINE_NEXT_SKIPLINE:
                    start_line_number += tmpl_ptr.m_SkipLine
                elif line_which == self.LINE_NEXT_HEADER:
                    start_line_number += tmpl_ptr.m_HeaderSize
                elif line_which == self.LINE_NEXT:
                    start_line_number += 1
                elif line_which == self.LINE_END:
                    start_line_number = -100
                
                # Reset state flags for next iteration
                tmpl_which = -1
                line_which = -1
                
    def extract_data_from_tmpl(self, id_string, tmpl_ptr, start_line, tmpl_changed, tmpl_type):
        """
        C++: bool ExtractDataFromTmpl(...)
        Extracts data based on all rules in the template and constructs the result buffer.
        """
        if not tmpl_ptr.m_RuleList:
            self.get_line(start_line) # Just check line existence
            return False

        # 1. Initialize Buffer Pointer & ParsedData
        # C++: if(m_CurResultPtr == NULL) ...
        if self.m_CurResultPtr == 0:
            # Reset ParsedData (Python object reuse/reset logic)
            self.m_ParsedData.reset_data() # Assuming reset method exists or manually reset
            # In C++ memset clears the result buffer. In Python, we just overwrite.
            self.m_ParsedData.result = bytearray() 
            result_offset = 0
            current_attr_cnt = 0
        else:
            # Optimize: Continue from previous position (Atomic Tmpl accumulation)
            result_offset = self.m_CurResultPtr
            current_attr_cnt = self.m_CurAtomicAttrCnt
            # Clear previous result fields in ParsedData except the buffer

        # Metadata Setup
        self.m_ParsedData.eventId = tmpl_ptr.m_EventId
        self.m_ParsedData.idString = id_string
        self.m_ParsedData.eventTime = -1
        self.m_ParsedData.listSequence = self.m_ListSequence
        self.m_ParsedData.segBlkCnt = 0
        self.m_ParsedData.equipFlag = 0

        # 2. Iterate Rules
        for i, rule in enumerate(tmpl_ptr.m_RuleList):
            item_buf = ""
            
            # Extract Raw Data
            success, extracted_val = self.extract_data_from_rule(rule, start_line)
            
            if success:
                item_buf = extracted_val
                
                # Rule Logic: Null String Flag
                if rule.m_NullStringFlag:
                    if rule.m_InclusionNameFlag:
                        item_buf = f"{rule.m_ParsingName}:"
                    else:
                        item_buf = "" # Empty string, but will be \0 in buffer
                else:
                    # Rule Logic: BSC No (Atomic Only)
                    if tmpl_type == TMPL_ATOMIC_TYPE and rule.m_BscNo:
                        try:
                            self.m_BscNo = int(item_buf)
                        except ValueError:
                            pass
                    self.m_ParsedData.bscNo = self.m_BscNo
                    
                    # Rule Logic: PreDataCopy (Cache Update)
                    # C++: IsSpace check -> Python: not strip()
                    if rule.m_PreDataCopyFlag and item_buf.strip():
                        # Resize list if needed
                        if len(self.m_PreParsedDataCopy) <= i:
                            self.m_PreParsedDataCopy.extend([""] * (i - len(self.m_PreParsedDataCopy) + 1))
                        self.m_PreParsedDataCopy[i] = item_buf

                    # Rule Logic: PreDataCopy (Use Cache if current is empty & Tmpl not changed)
                    if rule.m_PreDataCopyFlag and not tmpl_changed and not item_buf.strip():
                        if len(self.m_PreParsedDataCopy) > i:
                            item_buf = self.m_PreParsedDataCopy[i]

                    # Rule Logic: Mapping
                    if rule.m_MappingValueFlag and rule.m_DataMapper:
                        mapped_val = rule.m_DataMapper.find_mapping_value(item_buf)
                        if mapped_val:
                            item_buf = mapped_val
                        else:
                            if rule.m_DataMapper.m_MappingFailBehavior != MAPPING_FAIL_BEHAVIOR_USE_PARSED_ITEM:
                                return False

                    # Rule Logic: Inclusion Name
                    if rule.m_InclusionNameFlag:
                        item_buf = f"{rule.m_ParsingName}:{item_buf}"

            else: # Extraction Failed
                # Fallback Logic
                if rule.m_NullSkipFlag:
                    # Check Mapping for empty string
                    if rule.m_MappingValueFlag and rule.m_DataMapper:
                        mapped_val = rule.m_DataMapper.find_mapping_value("")
                        if mapped_val:
                            item_buf = mapped_val
                    
                    if rule.m_InclusionNameFlag:
                        item_buf = f"{rule.m_ParsingName}:{item_buf}"
                        
                elif not tmpl_changed and rule.m_PreDataCopyFlag:
                    # Use Cache
                    if len(self.m_PreParsedDataCopy) > i:
                        item_buf = self.m_PreParsedDataCopy[i]
                        
                        # Apply Mapping/Inclusion to cached value
                        if rule.m_MappingValueFlag and rule.m_DataMapper:
                            mapped_val = rule.m_DataMapper.find_mapping_value(item_buf)
                            if mapped_val: item_buf = mapped_val
                            elif rule.m_DataMapper.m_MappingFailBehavior != MAPPING_FAIL_BEHAVIOR_USE_PARSED_ITEM:
                                return False
                        
                        if rule.m_InclusionNameFlag:
                             item_buf = f"{rule.m_ParsingName}:{item_buf}"
                    else:
                        return False
                else:
                    return False # Fatal Failure

            # 3. Write to Buffer
            # C++ writes string + Null Terminator (\0)
            # Python bytearray manipulation
            encoded_data = item_buf.encode('utf-8') + b'\0'
            data_len = len(encoded_data)
            
            if result_offset + data_len > self.MAX_PARSED_DATA_SIZE:
                print(f"[DataExtractor] [CORE_ERROR] Result Buffer Overflow. Max: {self.MAX_PARSED_DATA_SIZE}")
                return False
                
            self.m_LongResult[result_offset : result_offset + data_len] = encoded_data
            result_offset += data_len
            current_attr_cnt += 1

        # End of Rule Loop
        self.m_ParsedData.attributeNo = current_attr_cnt

        # 4. Dispatch Result (Callback)
        if tmpl_type == TMPL_ATOMIC_TYPE and tmpl_ptr.m_AtomResultHideFlag:
            pass # Hide result
        else:
            total_len = result_offset
            
            # Segmentation Check
            # Assuming PARSED_DATA_SEG_BLK_SIZE is defined (e.g. 3000 bytes)
            # and m_PARSED_DATA_SIZE is defined (e.g. 4096 bytes)
            
            limit_size = getattr(self, 'm_PARSED_DATA_SIZE', 4000) # Fallback default
            
            if total_len > limit_size:
                # Segmentation Required
                block_cnt = (total_len // PARSED_DATA_SEG_BLK_SIZE) + 1
                
                # Generate GUID
                self.m_ParsedData.resultExGuid = self.m_GUIDMaker.get_guid()
                
                for k in range(block_cnt):
                    self.m_ParsedData.segBlkCnt += 1
                    
                    # Mark last block with negative sign
                    if k == block_cnt - 1:
                        self.m_ParsedData.segBlkCnt *= -1
                        
                    start_idx = k * PARSED_DATA_SEG_BLK_SIZE
                    end_idx = start_idx + PARSED_DATA_SEG_BLK_SIZE
                    
                    # Extract Chunk
                    chunk = self.m_LongResult[start_idx : min(end_idx, total_len)]
                    
                    # Set Chunk to Extended Result Field
                    self.m_ParsedData.resultExResult = chunk 
                    
                    # Send
                    self.m_DataExtractMgr.parsing_result(tmpl_ptr.m_Consumers, self.m_ParsedData)
            else:
                # No Segmentation
                # Copy buffer to result field (bytes)
                self.m_ParsedData.result = self.m_LongResult[:total_len]
                self.m_DataExtractMgr.parsing_result(tmpl_ptr.m_Consumers, self.m_ParsedData)

        # 5. Update State for Atomic Accumulation
        if tmpl_type == TMPL_ATOMIC_TYPE:
            self.m_CurResultPtr = result_offset
            self.m_CurAtomicAttrCnt = current_attr_cnt
            
        return True
    
    def extract_data_from_rule(self, parsing_rule_ptr, start_line):
        """
        C++: bool ExtractDataFromRule(ParsingRule* ParsingRulePtr, char* TempBuf, int StartLine)
        Iterates through the line range defined in the rule to find and extract data.
        
        Returns:
            tuple (success: bool, result_data: str)
        """
        rule_start_line = parsing_rule_ptr.m_StartLine
        rule_end_line = parsing_rule_ptr.m_EndLine
        
        # Iterate through the relative line range
        for i in range(rule_start_line, rule_end_line + 1):
            
            # Calculate absolute line number (1-based)
            # C++: GetLine(i + StartLine - 1)
            target_line_num = i + start_line - 1
            
            line_buf = self.get_line(target_line_num)
            
            if line_buf is None:
                # Line over or invalid line number
                return False, ""

            temp_buf = ""

            # 1. Attempt Extraction
            success, temp_buf = self.extract_data_from_parsing_rule(parsing_rule_ptr, line_buf, target_line_num)
            
            if not success:
                continue

            # 2. Check Empty Result
            if not temp_buf:
                # frDEBUG(("No Extract Data"))
                continue

            # 3. Trim Processing
            if parsing_rule_ptr.m_TrimFlag != NO_TRIM:
                if parsing_rule_ptr.m_TrimFlag == LR_TRIM:
                    temp_buf = temp_buf.strip()
                elif parsing_rule_ptr.m_TrimFlag == L_TRIM:
                    temp_buf = temp_buf.lstrip()
                elif parsing_rule_ptr.m_TrimFlag == R_TRIM:
                    temp_buf = temp_buf.rstrip()

            # 4. Data Type Check
            if parsing_rule_ptr.m_DataTypeCheckFlag:
                # check_data_type returns (bool, formatted_string)
                is_valid, formatted_data = self.check_data_type(parsing_rule_ptr.m_DataType, temp_buf)
                
                if is_valid:
                    return True, formatted_data
                else:
                    # frDEBUG(("Data Type is diff..."))
                    continue
            else:
                return True, temp_buf

        return False, ""
    
    def is_end_line(self, line_number):
        """
        C++: bool IsEndLine(int LineNumber)
        Checks if the provided line number exceeds the total lines scanned.
        """
        if self.m_EndLineNumber != -1 and self.m_EndLineNumber < line_number:
            return True
        return False

    def is_space(self, string_val):
        """
        C++: bool IsSpace(const char* String)
        Checks if the string consists ONLY of space characters (' ') or is empty.
        
        [Note]
        C++ implementation strictly checks for ' '.
        Tabs (\t) or newlines (\n) will return False (treated as non-space data).
        """
        if not string_val:
            return True

        for char in string_val:
            if char != ' ':
                return False
        return True
    
    def extract_data_from_parsing_rule(self, rule, line_buf, line_number):
        """
        C++: bool ExtractDataFromParsingRule(...)
        Executes the specific string extraction logic based on ParsingType.
        Returns: tuple(success: bool, result: str)
        """
        if not line_buf:
            return False, ""

        p_type = rule.m_ParsingType
        temp_buf = ""

        # -----------------------------------------------------------
        # 1. STRSTR_TOKEN
        # Find a string, then tokenize the remainder.
        # -----------------------------------------------------------
        if p_type == STRSTR_TOKEN:
            start_idx = line_buf.find(rule.m_StartString)
            if start_idx == -1:
                return False, ""
            
            # Move index past the start string
            start_idx += len(rule.m_StartString)
            sub_line = line_buf[start_idx:]
            
            # Delimiter Type 0: String/Space
            if rule.m_DelimiterType == 0:
                # TokenIndex > 0: Forward, < 0: Backward
                # Using our helper msg_tokenize_string
                val = self.msg_tokenize_string(sub_line, rule.m_TokenIndex, None, rule.m_TokenDelimiter)
                if val is not None:
                    temp_buf = val
                else:
                    temp_buf = ""
            
            # Delimiter Type 1: Char
            elif rule.m_DelimiterType == 1:
                val = self.msg_tokenize_char(sub_line, rule.m_TokenIndex, None, rule.m_TokenDelimiter)
                if val is not None:
                    temp_buf = val
                else:
                    temp_buf = ""
            
            else:
                print(f"[DataExtractor] [CORE_ERROR] Unknown DelimiterType: {rule.m_DelimiterType}")
                return False, ""

            # Token Size Processing
            # > 0: Truncate (Keep first N)
            # < 0: Offset (Skip first N)
            if temp_buf and rule.m_TokenSize != 0:
                size = rule.m_TokenSize
                if abs(size) < len(temp_buf) + 1:
                    if size > 0:
                        temp_buf = temp_buf[:size]
                    else:
                        # Skip first 'size' characters
                        # C++: strcpy(Buf, TempBuf + (len + size)) -> size is negative
                        # e.g. len=5, size=-2 -> skip 3? 
                        # Wait, C++ logic: strcpy(Buf, TempBuf + (len + size)) where size is negative?
                        # No, usually logical offset. Let's assume standard substring logic.
                        # If C++ meant "Skip N chars", it usually does ptr += N.
                        # Let's follow Pythonic slicing: [N:]
                        offset = abs(size)
                        if offset < len(temp_buf):
                            temp_buf = temp_buf[offset:]
                        else:
                            temp_buf = ""
                else:
                    return False, ""

        # -----------------------------------------------------------
        # 2. STRCOL_STRSTR_ENDCOL
        # Column -> Find String -> Column
        # -----------------------------------------------------------
        elif p_type == STRCOL_STRSTR_ENDCOL:
            if len(line_buf) < rule.m_StartColumn or len(line_buf) < rule.m_EndColumn:
                return False, ""
            
            # Adjust 1-based to 0-based
            start_ptr = rule.m_StartColumn - 1
            search_area = line_buf[start_ptr:]
            
            found_idx = search_area.find(rule.m_StartString)
            if found_idx == -1:
                return False, ""
            
            # Absolute index of found string start + len
            abs_start = start_ptr + found_idx + len(rule.m_StartString)
            abs_end = rule.m_EndColumn
            
            if abs_start > abs_end:
                return False, ""
                
            temp_buf = line_buf[abs_start:abs_end]

        # -----------------------------------------------------------
        # 3. STRCOL_ENDSTR
        # Column -> Find End String
        # -----------------------------------------------------------
        elif p_type == STRCOL_ENDSTR:
            if len(line_buf) < rule.m_StartColumn:
                return False, ""
            
            start_ptr = rule.m_StartColumn - 1
            search_area = line_buf[start_ptr:]
            
            found_idx = search_area.find(rule.m_EndString)
            if found_idx == -1:
                return False, ""
            
            # Extract from StartColumn to found position
            temp_buf = search_area[:found_idx]

        # -----------------------------------------------------------
        # 4. STRSTR_EXTSIZE
        # Find String -> Extract N chars
        # -----------------------------------------------------------
        elif p_type == STRSTR_EXTSIZE:
            found_idx = line_buf.find(rule.m_StartString)
            if found_idx == -1:
                return False, ""
            
            start_idx = found_idx + len(rule.m_StartString)
            # Safe slicing handles out of bounds by stopping at end
            temp_buf = line_buf[start_idx : start_idx + rule.m_ExtractSize]

        # -----------------------------------------------------------
        # 5. STRSTR_ENDSTR
        # Find Start String -> Find End String
        # -----------------------------------------------------------
        elif p_type == STRSTR_ENDSTR:
            start_idx = line_buf.find(rule.m_StartString)
            if start_idx == -1:
                return False, ""
            
            start_idx += len(rule.m_StartString)
            
            end_idx = line_buf.find(rule.m_EndString, start_idx)
            if end_idx == -1:
                return False, ""
                
            temp_buf = line_buf[start_idx:end_idx]

        # -----------------------------------------------------------
        # 6. STRSTR_ENDCOL
        # Find Start String -> End at Column
        # -----------------------------------------------------------
        elif p_type == STRSTR_ENDCOL:
            if len(line_buf) < rule.m_EndColumn:
                return False, ""
            
            start_idx = line_buf.find(rule.m_StartString)
            if start_idx == -1:
                return False, ""
                
            start_idx += len(rule.m_StartString)
            end_idx = rule.m_EndColumn
            
            if start_idx > end_idx:
                return False, ""
                
            temp_buf = line_buf[start_idx:end_idx]

        # -----------------------------------------------------------
        # 7. EXTSIZE_ENDSTR
        # Extract N chars BEFORE End String
        # -----------------------------------------------------------
        elif p_type == EXTSIZE_ENDSTR:
            if len(line_buf) < rule.m_ExtractSize:
                return False, ""
                
            end_idx = line_buf.find(rule.m_EndString)
            if end_idx == -1:
                return False, ""
                
            # Check if enough chars exist before match
            if rule.m_ExtractSize > (end_idx + 1): # C++ used ptr comparison
                 return False, ""
            
            start_idx = end_idx - rule.m_ExtractSize
            temp_buf = line_buf[start_idx:end_idx]

        # -----------------------------------------------------------
        # 8. LINE_FULL
        # Concatenate multiple lines
        # -----------------------------------------------------------
        elif p_type == LINE_FULL:
            tmp_lines = []
            max_size = self.TEMP_ITEM_BUF_SIZE - 1
            
            # Loop from next line to configured count
            # C++: i = LineNumber + 1 ; i < EndLine - StartLine + LineNumber + 1
            count = rule.m_EndLine - rule.m_StartLine
            
            for i in range(line_number + 1, line_number + 1 + count):
                l_buf = self.get_line(i)
                if l_buf is not None:
                    l_len = len(l_buf)
                    max_size -= (l_len + 1) # +1 for newline
                    if max_size < 0:
                        break
                    tmp_lines.append(l_buf)
                else:
                    return False, ""
            
            # Prepend current line? C++ implementation seems to start from LineNumber+1
            # But normally LINE_FULL implies including current line?
            # C++ code starts loop at LineNumber+1 and appends to 'tmpLine' which was init with 'LineBuf'.
            # Yes: string tmpLine = LineBuf;
            
            result = line_buf
            if tmp_lines:
                result += "\n" + "\n".join(tmp_lines)
            temp_buf = result

        # -----------------------------------------------------------
        # 9. FULL_MESSAGE_EXTRACT
        # Concatenate ALL remaining lines
        # -----------------------------------------------------------
        elif p_type == FULL_MESSAGE_EXTRACT:
            tmp_lines = []
            max_size = self.TEMP_ITEM_BUF_SIZE - 1
            
            # Start from line 1?
            # C++: for(int i = 1 ; i < m_EndLineNumber + 2 ; i++)
            # It seems to grab EVERYTHING from the start?
            # C++ code does NOT init tmpLine = LineBuf here.
            # It iterates from 1 to EndLine.
            
            for i in range(1, self.m_EndLineNumber + 2):
                l_buf = self.get_line(i)
                if l_buf is not None:
                    l_len = len(l_buf)
                    max_size -= (l_len + 1)
                    if max_size < 0:
                        break
                    tmp_lines.append(l_buf)
                else:
                    break
            
            if tmp_lines:
                temp_buf = "\n".join(tmp_lines)
                # C++ does tmpLine.erase(last char) for extra newline? Python join handles this.

        # -----------------------------------------------------------
        # 10. STRCOL_STRSTR_TOKEN
        # Column -> Find String -> Tokenize
        # -----------------------------------------------------------
        elif p_type == STRCOL_STRSTR_TOKEN:
            if len(line_buf) < rule.m_StartColumn:
                return False, ""
                
            start_ptr = rule.m_StartColumn - 1
            search_area = line_buf[start_ptr:]
            
            found_idx = -1
            if rule.m_StartString:
                found_idx = search_area.find(rule.m_StartString)
                if found_idx == -1:
                    return False, ""
                # Adjust start to after found string
                sub_line = search_area[found_idx + len(rule.m_StartString):]
            else:
                sub_line = search_area # No start string, just column

            # Tokenize Logic
            if rule.m_DelimiterType == 0:
                val = self.msg_tokenize_string(sub_line, rule.m_TokenIndex, None, rule.m_TokenDelimiter)
                temp_buf = val if val else ""
            elif rule.m_DelimiterType == 1:
                val = self.msg_tokenize_char(sub_line, rule.m_TokenIndex, None, rule.m_TokenDelimiter)
                temp_buf = val if val else ""
            else:
                return False, ""

            # Token Size Logic (Copy from STRSTR_TOKEN)
            if temp_buf and rule.m_TokenSize != 0:
                size = rule.m_TokenSize
                if abs(size) < len(temp_buf) + 1:
                    if size > 0:
                        temp_buf = temp_buf[:size]
                    else:
                        offset = abs(size)
                        temp_buf = temp_buf[offset:] if offset < len(temp_buf) else ""
                else:
                    return False, ""

        # -----------------------------------------------------------
        # 11. STRCOL_STRSTR_REMAINSTR
        # Column -> Find String -> Take Rest
        # -----------------------------------------------------------
        elif p_type == STRCOL_STRSTR_REMAINSTR:
            if len(line_buf) < rule.m_StartColumn:
                return False, ""
                
            start_ptr = rule.m_StartColumn - 1
            search_area = line_buf[start_ptr:]
            
            if rule.m_StartString:
                found_idx = search_area.find(rule.m_StartString)
                if found_idx == -1:
                    return False, ""
                
                # Take everything AFTER the found string
                temp_buf = search_area[found_idx + len(rule.m_StartString):]
            else:
                return False, ""

        # -----------------------------------------------------------
        # 12. STRCOL_STRSTR_TOKEN_REMAINSTR
        # Column -> Find String -> Tokenize (Start pos) -> Take Rest
        # -----------------------------------------------------------
        elif p_type == STRCOL_STRSTR_TOKEN_REMAINSTR:
            if len(line_buf) < rule.m_StartColumn:
                return False, ""
            
            start_ptr = rule.m_StartColumn - 1
            search_area = line_buf[start_ptr:]
            
            if rule.m_StartString:
                found_idx = search_area.find(rule.m_StartString)
                if found_idx == -1:
                    return False, ""
                
                sub_line = search_area[found_idx + len(rule.m_StartString):]
            else:
                sub_line = search_area # Should not happen based on C++ logic
                
            # Complex C++ Logic simulation:
            # It tries to find the Nth token, and then takes the string starting from that token to the end.
            # Python 'msg_tokenize_string' returns the token VALUE, not the index.
            # We need to find the split point manually here.
            
            # Simple approach: Split, find Nth part, then find that part in original string? Unsafe.
            # Robust approach: Loop find delimiter N times.
            
            delimiter = rule.m_TokenDelimiter if rule.m_TokenDelimiter else " "
            target_idx = rule.m_TokenIndex + 1 # C++ uses +1
            
            current_pos = 0
            found_cnt = 0
            
            # Warning: This is a simplified simulation of C++ pointer logic
            # "Get remainder starting from Token N"
            
            # If delimiter is space, split logic is complex due to merging.
            # We will try to reconstruct using split (approximation)
            parts = sub_line.split(None if delimiter==" " else delimiter)
            
            # Adjust index for 0-based list
            # C++ target_idx is 1-based index of token to start from.
            list_idx = target_idx - 1 
            
            if 0 <= list_idx < len(parts):
                # We need the substring starting from this token.
                # Find the token in the sub_line.
                token_val = parts[list_idx]
                
                # Find where this token *actually* starts (handle duplicates carefully)
                # This is heuristic: we skip the first N-1 tokens' length + delimiters
                # A safer way: sub_line.split(delim, maxsplit=target_idx-1) -> last element is remainder
                
                if delimiter == " ":
                    split_res = sub_line.split(None, target_idx - 1)
                else:
                    split_res = sub_line.split(delimiter, target_idx - 1)
                
                if len(split_res) >= target_idx:
                     # The last element contains the remainder starting from token N
                     temp_buf = split_res[-1]
                else:
                    return False, ""
            else:
                return False, ""

        # -----------------------------------------------------------
        # 13. CREATE_DATA_IN_PREDEFINED
        # -----------------------------------------------------------
        elif p_type == CREATE_DATA_IN_PREDEFINED:
            temp_buf = self.create_pre_defined_data(rule.m_DefinedDataType, rule.m_DefinedDataTypeFormat)

        else:
            print(f"[DataExtractor] [CORE_ERROR] UnKnown Parsing Type : {p_type}")
            return False, ""

        return True, temp_buf

    def create_pre_defined_data(self, defined_data_type, defined_data_type_format):
        """
        C++: void CreatePreDefinedData(int DefinedDataType, int DefinedDataTypeFormat, char* TempBuf)
        Generates formatted date/time strings based on the current system time.
        
        Returns:
            str: The formatted date/time string.
        """
        now = datetime.now()
        temp_buf = ""

        # Note: PARSING_DATE and PARSING_TIME should be imported from RuleType
        # or defined as constants matching the C++ enum values.
        
        if defined_data_type == PARSING_DATE:
            if defined_data_type_format == 0:   # YYYY-MM-DD
                temp_buf = now.strftime("%Y-%m-%d")
            elif defined_data_type_format == 1: # YY-MM-DD
                temp_buf = now.strftime("%y-%m-%d")
            else:
                temp_buf = f"UNKNOWN DATA FORMAT : {defined_data_type},{defined_data_type_format}"
                
        elif defined_data_type == PARSING_TIME:
            if defined_data_type_format == 0:   # HH:MI:SS
                temp_buf = now.strftime("%H:%M:%S")
            elif defined_data_type_format == 1: # HH:MI
                temp_buf = now.strftime("%H:%M")
            elif defined_data_type_format == 2: # HH
                temp_buf = now.strftime("%H")
            else:
                temp_buf = f"UNKNOWN DATA FORMAT : {defined_data_type},{defined_data_type_format}"
        
        else:
            temp_buf = f"UNKNOWN DefinedDataType : {defined_data_type},{defined_data_type_format}"

        return temp_buf
    
    def re_make_msg(self):
        """
        C++: void ReMakeMsg()
        Currently empty in C++ source.
        Placeholder for message reconstruction logic.
        """
        pass
    
    # ------------------------------------------------------------------
    # XML Parsing Methods
    # ------------------------------------------------------------------

    def parsing_xml(self, ident_rule_ptr, id_string, msg_buf, consumer):
        """
        C++: void ParsingXML(...)
        Entry point for XML parsing.
        """
        if not ident_rule_ptr.m_ParsingFlag:
            return

        # 1. Message Trimming (< ... >)
        # Find first '<'
        start_idx = msg_buf.find('<')
        if start_idx != -1:
            m_msg_buf = msg_buf[start_idx:]
        else:
            m_msg_buf = msg_buf

        # Find last '>'
        end_idx = m_msg_buf.rfind('>')
        if end_idx != -1:
            m_msg_buf = m_msg_buf[:end_idx+1]
        
        if not m_msg_buf:
            return

        self.m_CurResultPtr = 0
        self.m_ListSequence = 0

        # 2. Parse XML Document
        if self.m_XmlParserMgr is None:
            print("[DataExtractor] [CORE_ERROR] XMLParserMgr is not initialized.")
            return

        if not self.m_XmlParserMgr.xml_parse(m_msg_buf, ident_rule_ptr):
            # Error handling
            print(f"[DataExtractor] XML Parse Error: {self.m_XmlParserMgr.get_error_msg()}")
            return

        # 3. Create Info Manager from Root
        from Class.ProcParser.XmlElementInfoMgr import XmlElementInfoMgr
        xml_info_mgr = XmlElementInfoMgr(self.m_XmlParserMgr.get_root_element_info())

        # 4. Iterate Template Groups
        for tmpl_grp in ident_rule_ptr.m_TmplGrpList:
            if consumer and not tmpl_grp.check_consumer(consumer):
                continue
            
            self.m_ListSequence = 0
            # m_TimeMaker.Clear() # Python TimeMaker usage to be defined if needed

            parsing_success_flag = False

            # Iterate Templates
            for tmpl_ptr in tmpl_grp.m_TmplVector:
                ret = False
                
                # Check Root Element PCData Kind (Attribute vs Normal)
                # If Attribute, we might iterate based on attribute count? 
                # C++ logic: loop nI < m_RootElementListcnt if XML_ATTRIBUTE
                # Assuming standard case first.
                
                if tmpl_ptr.m_XmlRootElementPCDATAKind == XML_ATTRIBUTE:
                    nI = 0
                    while nI < self.m_XmlParserMgr.m_RootElementListcnt:
                        ret2 = self.extract_data_from_tmpl_xml(xml_info_mgr, id_string, tmpl_ptr, nI)
                        if ret2: ret = True
                        nI += 1
                else:
                    ret = self.extract_data_from_tmpl_xml(xml_info_mgr, id_string, tmpl_ptr, 0)

                if not parsing_success_flag:
                    parsing_success_flag = ret

            # 5. EOR Handling (End of Record)
            if parsing_success_flag:
                self.m_ParsedData.listSequence = -1
                self.m_ParsedData.attributeNo = 0
                self.m_ParsedData.bscNo = -1
                self.m_ParsedData.idString = id_string
                
                for tmpl_ptr in tmpl_grp.m_TmplVector:
                    if not tmpl_ptr.m_EORHideFlag:
                        self.m_ParsedData.eventId = tmpl_ptr.m_EventId
                        self.m_ParsedData.equipFlag = tmpl_ptr.m_EquipFlag
                        self.m_DataExtractMgr.parsing_result(tmpl_ptr.m_Consumers, self.m_ParsedData)
        
        # Cleanup
        # delete xmlInfoMgr (Python GC handles it)
        self.m_XmlParserMgr.init()

    def extract_data_from_tmpl_xml(self, xml_info_mgr, id_string, tmpl_ptr, root_element_list_pos):
        """
        C++: bool ExtractDataFromTmplXML(...)
        Extracts data for a single template from the XML structure.
        Handles LIST type iterations and data expansion.
        """
        if not tmpl_ptr.m_RuleList:
            return False

        # Reset ParsedData
        # self.m_ParsedData.reset_data() # Assuming reset helper exists
        self.m_ParsedData.result = bytearray()
        
        self.m_ParsedData.eventId = tmpl_ptr.m_EventId
        self.m_ParsedData.idString = id_string
        self.m_ParsedData.listSequence = self.m_ListSequence
        
        # 1. Set Key Element (Cursor positioning)
        flag = True
        if tmpl_ptr.m_TmplType == TMPL_LIST_TYPE:
            flag = xml_info_mgr.set_key_element(
                tmpl_ptr.m_XmlRootElementTagVec, 
                tmpl_ptr.m_XmlRootElementPCDATATagVec,
                tmpl_ptr.m_XmlKeyElementTagVec, 
                tmpl_ptr.m_XmlRootElementPCDATAKind,
                tmpl_ptr.m_XmlRootElementPCDATA, 
                root_element_list_pos
            )
            if not flag:
                # Error logging
                pass

        sequence = 0
        parsing_success_flag = False
        parsed_data_vec = None # List of ParsedDataInfo
        
        # 2. Iterate Logic (Loop while valid key sequence exists)
        while flag:
            self.m_ParsedData.attributeNo = 0
            self.m_ParsedData.eventTime = -1
            self.m_ParsedData.bscNo = -1
            self.m_ParsedData.result = bytearray()
            # TimeMaker clear
            
            result_ptr = 0 # Logical offset
            parsed_data_vec = None # Reset vector

            if tmpl_ptr.m_TmplType == TMPL_LIST_TYPE:
                if not xml_info_mgr.is_valid_key_xml_sequence(sequence):
                    return parsing_success_flag

            extrace_ret = 0
            
            # 3. Iterate Rules
            for rule in tmpl_ptr.m_RuleList:
                str_list = [] # StringVector
                
                # --- Case A: Normal Rule ---
                if not rule.m_RuleInnerTmpl:
                    extrace_ret = self.extract_data_from_rule_xml(
                        xml_info_mgr, rule, str_list, sequence, 
                        tmpl_ptr.m_XmlRootElementPCDATAKind, 
                        tmpl_ptr.m_XmlRootElementPCDATATagVec, 
                        root_element_list_pos
                    )
                    
                    if extrace_ret > 0: # Success
                        # Parsing Type Process
                        if rule.m_ParsingType != NOT_USE:
                            new_list = []
                            for s in str_list:
                                success, val = self.extract_data_from_parsing_rule_xml(rule, s)
                                new_list.append(val if success else "")
                            str_list = new_list

                        # Single Value Processing (DateTime, etc.)
                        if len(str_list) == 1 and (rule.m_XMLCharDataMask & (XML_PCDATA_MASK | XML_ATTR_VALUE_MASK)):
                             # DateTime Logic (Omitted for brevity, use TimeMaker)
                             pass

                        # General Processing (Mapping, Inclusion)
                        for i in range(len(str_list)):
                            val = str_list[i]
                            
                            # Mapping
                            if rule.m_MappingValueFlag and rule.m_DataMapper:
                                mapped = rule.m_DataMapper.find_mapping_value(val)
                                if mapped: val = mapped
                            
                            # Inclusion Name
                            if rule.m_InclusionNameFlag:
                                val = f"{rule.m_ParsingName}:{val}"
                            
                            str_list[i] = val
                            
                            # Add to Result
                            if parsed_data_vec is None:
                                # Normal Append
                                encoded = val.encode('utf-8') + b'\0'
                                self.m_ParsedData.result.extend(encoded)
                                self.m_ParsedData.attributeNo += 1
                                result_ptr += len(encoded)
                            else:
                                # Expand existing expanded rows
                                for p_info in parsed_data_vec:
                                    encoded = val.encode('utf-8') + b'\0'
                                    p_info.m_Result.extend(encoded)
                                    p_info.m_ResultPtr += len(encoded)
                                    p_info.m_AttributeNo += 1
                    
                    else: # Fail
                        # Error Handling or Break
                        if extrace_ret == XML_DATA_END:
                            return parsing_success_flag
                        elif extrace_ret in (XML_FIND_PCDATA_ERROR, XML_FIND_PCDATA_NOEXIST):
                            break # Skip this sequence

                # --- Case B: Inner Template (Nested) ---
                else:
                    if xml_info_mgr.get_key_xml_data_info(sequence):
                        from Class.ProcParser.XmlElementInfoMgr import XmlElementInfoMgr
                        
                        ret_vec_vec = [] # List of StringVector
                        tmp_mgr = XmlElementInfoMgr(xml_info_mgr.get_key_xml_data_info(sequence))
                        
                        extrace_ret = self.extrace_data_from_rule_inner_tmpl(tmp_mgr, rule.m_RuleInnerTmpl, ret_vec_vec)
                        
                        if extrace_ret > 0:
                            # Expansion Logic (Cartesian Product)
                            if parsed_data_vec is None:
                                parsed_data_vec = []
                                current_data = self.m_ParsedData.result
                                current_attr = self.m_ParsedData.attributeNo
                                
                                for str_vec in ret_vec_vec:
                                    if str_vec:
                                        p_ptr = ParsedDataInfo(current_attr, current_data, len(current_data))
                                        parsed_data_vec.append(p_ptr)
                                        
                                        for val in str_vec:
                                            encoded = val.encode('utf-8') + b'\0'
                                            p_ptr.m_Result.extend(encoded)
                                            p_ptr.m_ResultPtr += len(encoded)
                                            p_ptr.m_AttributeNo += 1
                            else:
                                re_parsed_data = []
                                for p_info in parsed_data_vec:
                                    base_res = p_info.m_Result
                                    base_attr = p_info.m_AttributeNo
                                    base_ptr = len(base_res)
                                    
                                    for str_vec in ret_vec_vec:
                                        if str_vec:
                                            new_ptr = ParsedDataInfo(base_attr, base_res, base_ptr)
                                            re_parsed_data.append(new_ptr)
                                            
                                            for val in str_vec:
                                                encoded = val.encode('utf-8') + b'\0'
                                                new_ptr.m_Result.extend(encoded)
                                                new_ptr.m_ResultPtr += len(encoded)
                                                new_ptr.m_AttributeNo += 1
                                parsed_data_vec = re_parsed_data
                    else:
                        return parsing_success_flag

            # 4. Finalize Sequence Processing
            # (If no errors occurred)
            if extrace_ret not in (XML_FIND_PCDATA_ERROR, XML_FIND_PCDATA_NOEXIST, XML_FIND_ATTRNAME_ERROR):
                
                # Set Time (Omitted)
                
                if parsed_data_vec is None:
                    # Single Row Result
                    self.m_ParsedData.listSequence = self.m_ListSequence
                    self.m_ListSequence += 1
                    self.m_DataExtractMgr.parsing_result(tmpl_ptr.m_Consumers, self.m_ParsedData)
                else:
                    # Expanded Rows Result
                    for p_info in parsed_data_vec:
                        self.m_ParsedData.listSequence = self.m_ListSequence
                        self.m_ListSequence += 1
                        self.m_ParsedData.attributeNo = p_info.m_AttributeNo
                        
                        # Copy result buffer
                        # Caution: Ensure buffer size matches structure
                        # self.m_ParsedData.result = p_info.m_Result[:4096]...
                        # Simplified assignment:
                        self.m_ParsedData.result = p_info.m_Result
                        
                        self.m_DataExtractMgr.parsing_result(tmpl_ptr.m_Consumers, self.m_ParsedData)
                
                parsing_success_flag = True

            if tmpl_ptr.m_TmplType == TMPL_ATOMIC_TYPE:
                break
            sequence += 1
            
        return parsing_success_flag

    def extrace_data_from_rule_inner_tmpl(self, xml_info_mgr, parsing_tmpl_ptr, ret_vec_vec):
        """
        C++: int ExtraceDataFromRuleInnerTmpl(...)
        Recursive helper to extract nested data.
        """
        rec_vec_vec = [] # RuleInnerDataRecVecVec
        
        # 1. Populate Recursive Data Structure
        self._extrace_data_from_rule_inner_tmpl_internal(xml_info_mgr, parsing_tmpl_ptr, rec_vec_vec)
        
        # 2. Flatten/Decode
        cur_vec = []
        self.decode_rule_inner_rec(rec_vec_vec, cur_vec, ret_vec_vec)
        
        return len(ret_vec_vec)

    def _extrace_data_from_rule_inner_tmpl_internal(self, xml_info_mgr, parsing_tmpl_ptr, inner_rec_vec_vec):
        """
        Internal recursive extraction logic.
        Populates RuleInnerDataRecVecVec.
        """
        flag = xml_info_mgr.set_key_element(
            parsing_tmpl_ptr.m_XmlRootElementTagVec, parsing_tmpl_ptr.m_XmlRootElementPCDATATagVec,
            parsing_tmpl_ptr.m_XmlKeyElementTagVec, parsing_tmpl_ptr.m_XmlRootElementPCDATAKind,
            parsing_tmpl_ptr.m_XmlRootElementPCDATA
        )
        
        sequence = 0
        
        while flag:
            data_rec_vec = [] # RuleInnerDataRecVec
            
            if not xml_info_mgr.is_valid_key_xml_sequence(sequence):
                return XML_DATA_END
            
            # Iterate Rules
            for rule in parsing_tmpl_ptr.m_RuleList:
                str_list = []
                
                if not rule.m_RuleInnerTmpl:
                    # Normal Rule Extraction
                    extrace_ret = self.extract_data_from_rule_xml(
                        xml_info_mgr, rule, str_list, sequence, 
                        parsing_tmpl_ptr.m_XmlRootElementPCDATAKind, 
                        parsing_tmpl_ptr.m_XmlRootElementPCDATATagVec
                    )
                    
                    if extrace_ret > 0:
                        # Parsing Type Process
                        if rule.m_ParsingType != NOT_USE:
                            new_list = []
                            for s in str_list:
                                success, val = self.extract_data_from_parsing_rule_xml(rule, s)
                                new_list.append(val if success else "")
                            str_list = new_list

                        rec = RuleInnerDataRec()
                        data_rec_vec.append(rec)
                        
                        # Populate Rec
                        for i in range(len(str_list)):
                            val = str_list[i]
                            # Mapping / Inclusion logic here...
                            
                            if len(str_list) == 1:
                                rec.m_RecValue = val
                            else:
                                if rec.m_RecValueList is None: rec.m_RecValueList = []
                                rec.m_RecValueList.append(val)
                    else:
                         if extrace_ret in (XML_FIND_PCDATA_ERROR, XML_FIND_PCDATA_NOEXIST):
                             break

                else:
                    # Inner Template Recursion
                    if xml_info_mgr.get_key_xml_data_info(sequence):
                        rec = RuleInnerDataRec()
                        rec.m_RuleInnerDataRecVecVec = []
                        data_rec_vec.append(rec)
                        
                        from Class.ProcParser.XmlElementInfoMgr import XmlElementInfoMgr
                        tmp_mgr = XmlElementInfoMgr(xml_info_mgr.get_key_xml_data_info(sequence))
                        
                        self._extrace_data_from_rule_inner_tmpl_internal(tmp_mgr, rule.m_RuleInnerTmpl, rec.m_RuleInnerDataRecVecVec)
                    else:
                        return XML_DATA_END

            if data_rec_vec:
                inner_rec_vec_vec.append(data_rec_vec)
            
            sequence += 1
        
        return 0

    def decode_rule_inner_rec(self, inner_rec_vec_vec, cur_vec, ret_vec_vec):
        """
        C++: void DecodeRuleInnerRec(...)
        Flattens the recursive structure into a list of string vectors.
        """
        for rec_vec in inner_rec_vec_vec: # Loop over sequences
            new_cur_vec = list(cur_vec)
            is_inner = False
            
            for rec in rec_vec: # Loop over rules in sequence
                if rec.m_RecValue is not None:
                    new_cur_vec.append(rec.m_RecValue)
                    continue
                
                if rec.m_RecValueList:
                    new_cur_vec.extend(rec.m_RecValueList)
                    continue
                
                if rec.m_RuleInnerDataRecVecVec:
                    is_inner = True
                    self.decode_rule_inner_rec(rec.m_RuleInnerDataRecVecVec, new_cur_vec, ret_vec_vec)
                    continue
            
            if not is_inner and len(new_cur_vec) > len(cur_vec):
                ret_vec_vec.append(new_cur_vec)

    def extract_data_from_rule_xml(self, xml_info_mgr, rule, str_list, seq, key_data_kind, tmpl_root_pcdata_tag, root_pos=0):
        """
        C++: int ExtractDataFromRuleXML(...)
        Delegates to XmlInfoMgr to find data.
        """
        if rule.m_IsTagInKeyTmpl:
            return xml_info_mgr.find_pcdata_in_key_tmpl(rule, str_list, seq)
        else:
            return xml_info_mgr.find_pcdata(rule, str_list, seq, key_data_kind, tmpl_root_pcdata_tag, root_pos)

    def extract_data_from_parsing_rule_xml(self, rule, line_buf):
        """
        C++: bool ExtractDataFromParsingRuleXML(...)
        Identical logic to ASCII parsing rule extraction but applied to XML content string.
        """
        # Reusing the logic from ASCII extractor since it operates on a string buffer
        return self.extract_data_from_parsing_rule(rule, line_buf, 0)