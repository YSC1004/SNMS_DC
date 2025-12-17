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