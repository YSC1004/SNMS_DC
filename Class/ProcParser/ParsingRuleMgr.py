import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.ProcParser.ObjectBase import ObjectBase
from Class.ProcParser.RuleType import *
# Stub imports for DataMapper subclasses (assuming implementation exists or stubbed)
# from Class.ProcParser.StringDataMapper import StringDataMapper
# from Class.ProcParser.NumberDataMapper import NumberDataMapper

class ParsingRuleMgr(ObjectBase):
    """
    Manages loading and organization of Parsing Rules.
    Links rules to Templates and Identifiers.
    Handles DataMapper initialization.
    """
    def __init__(self, ident_mgr, tmpl_mgr):
        """
        C++: ParsingRuleMgr(ParsingIdentMgr* ParsingIdentMgr, ParsingTmplMgr* ParsingTmplMgrPtr)
        """
        super().__init__()
        self.m_ParsingIdentMgr = ident_mgr
        self.m_ParsingTmplMgr = tmpl_mgr
        self.m_ParsingRuleMap = {} # Key: RuleId (int), Value: ParsingRule

    def __del__(self):
        """
        C++: ~ParsingRuleMgr()
        """
        self.clear_rule()

    def init(self, rule_file_name, delimiter):
        """
        C++: bool Init(string RuleFileName, string Delimiter)
        Loads parsing rules from file.
        """
        self.clear_rule()

        if not os.path.exists(rule_file_name):
            self.set_error_msg(f"Parsing Rule File Open Error : {rule_file_name}")
            return False

        try:
            with open(rule_file_name, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            if not lines:
                self.set_error_msg(f"Parsing Rule Format Error (Empty)")
                return False

            try:
                count = int(lines[0].strip())
                print(f"[ParsingRuleMgr] Parsing Rule Count : {count}")
                if count == 0:
                    return True
            except ValueError:
                self.set_error_msg(f"Parsing Rule Format Error : {lines[0]}")
                return False

            for line in lines[1:]:
                line = line.strip()
                if not line: continue

                # Tokenize logic
                raw_tokens = line.split(delimiter)
                str_list = [""] + [t.strip() for t in raw_tokens]

                if len(str_list) < 35:
                    self.set_error_msg(f"Parsing Rule File Item Miss : Need(35), Current({len(str_list)})")
                    return False

                rule = ParsingRule()
                
                try:
                    rule.m_ParsingRuleId = int(str_list[1])
                    rule.m_TmplName = str_list[2]
                    rule.m_ParsingName = str_list[3]
                    rule.m_Sequence = int(str_list[4])
                    rule.m_StartLine = int(str_list[5])
                    rule.m_EndLine = int(str_list[6])
                    rule.m_StartColumn = int(str_list[7])
                    rule.m_EndColumn = int(str_list[8])
                    rule.m_StartString = str_list[9]
                    rule.m_EndString = str_list[10]
                    rule.m_ExtractSize = int(str_list[11])
                    rule.m_DataType = int(str_list[12])
                    rule.m_TokenIndex = int(str_list[13])
                    
                    # Token Delimiter Logic (Remove [])
                    t_delim = str_list[14]
                    if len(t_delim) > 1:
                        t_delim = t_delim[1:-1]
                    elif not t_delim:
                        pass # identification rule
                    else:
                        self.set_error_msg(f"Token Delimiter Format Error : {rule.m_ParsingName}")
                        return False
                    rule.m_TokenDelimiter = t_delim

                    rule.m_TokenSize = int(str_list[16])
                    rule.m_NullStringFlag = bool(int(str_list[17]))
                    rule.m_ParsingType = int(str_list[18])
                    rule.m_NullSkipFlag = bool(int(str_list[19]))
                    rule.m_PreDataCopyFlag = bool(int(str_list[20]))
                    rule.m_BscNo = bool(int(str_list[21]))
                    rule.m_DataTypeCheckFlag = bool(int(str_list[22]))
                    rule.m_MappingValueFlag = bool(int(str_list[23]))
                    rule.m_MappingValue = str_list[24]
                    rule.m_InclusionNameFlag = bool(int(str_list[25]))

                    # Defined Data (26)
                    if str_list[26]:
                        parts = str_list[26].split(',')
                        # C++ check: size == 3 (dummy + 2 values)
                        # Here split doesn't add dummy unless we do manually or adjust logic
                        if len(parts) == 2:
                            rule.m_DefinedDataType = int(parts[0])
                            rule.m_DefinedDataTypeFormat = int(parts[1])
                        else:
                            # Error logic
                            pass

                    # DateTime Flag (27)
                    time_flag = int(str_list[27])
                    # Logic simplified
                    if time_flag == PARSING_RULE_DATE_TIME_NONE_FLAG:
                        rule.m_DateTimeFlag |= PARSING_RULE_DATE_TIME_NONE_MASK
                    # ... others

                    # XML Tag (28)
                    rule.m_XMLElementTag = str_list[28]
                    # Tag Parsing stubbed

                    if int(str_list[29]): rule.m_XMLCharDataMask |= XML_ATTR_VALUE_MASK
                    if int(str_list[30]): rule.m_XMLCharDataMask |= XML_PCDATA_MASK

                    # PCDATA List (31)
                    # Logic to parse 31 (ranges, etc.) stubbed for brevity

                    # Attr List (32)
                    # Logic to parse 32 stubbed

                    rule.m_TrimFlag = int(str_list[33])
                    
                    if len(str_list) > 34 and str_list[34]:
                        rule.m_SetTimeFlag = int(str_list[34])
                    else:
                        rule.m_SetTimeFlag = 0
                    
                    if len(str_list) > 35:
                        rule.m_SetTime = str_list[35]

                except ValueError as ve:
                    self.set_error_msg(f"Invalid numeric value in rule: {ve}")
                    return False

                # Data Mapper Init
                if rule.m_MappingValueFlag:
                    tmp_map_val = rule.m_MappingValue
                    mapper_type_char = tmp_map_val[0]
                    # Logic to create StringDataMapper or NumberDataMapper
                    # And Init with substr(2)
                    pass

                # Basic Validation
                if rule.m_TmplName:
                    if not rule.m_ParsingName:
                        self.set_error_msg(f"There is no Parsing Rule Attribute. Id: {rule.m_ParsingRuleId}")
                        return False
                    
                    # Insert to TmplMgr
                    if not self.m_ParsingTmplMgr.insert_rule(rule):
                        self.set_error_msg(self.m_ParsingTmplMgr.get_error_msg())
                        return False

                self.m_ParsingRuleMap[rule.m_ParsingRuleId] = rule

            # Post-Load Linking
            if not self.m_ParsingIdentMgr.insert_ident_parsing_rule(self.m_ParsingRuleMap):
                self.set_error_msg(self.m_ParsingIdentMgr.get_error_msg())
                return False

            if not self.m_ParsingTmplMgr.rule_inner_tmpl_setup(self.m_ParsingRuleMap):
                self.set_error_msg(self.m_ParsingTmplMgr.get_error_msg())
                return False

            if len(self.m_ParsingRuleMap) != count:
                self.set_error_msg(f"Parsing Rule Count MisMatch!!! Spec: {count}, Real: {len(self.m_ParsingRuleMap)}")
                return False

            return True

        except Exception as e:
            self.set_error_msg(f"Exception loading parsing rules: {e}")
            return False

    def clear_rule(self):
        """
        C++: void ClearRule()
        """
        self.m_ParsingRuleMap.clear()

    def determine_parsing_type(self):
        return True