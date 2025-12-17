import sys
import os
import copy

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.ProcParser.RuleType import *
from Class.ProcParser.DataExtractor import DataExtractor
from Class.ProcParser.ObjectBase import ObjectBase

class ParsingIdentMgr(ObjectBase):
    """
    Manages loading of Identification Rules and identifying messages.
    Builds a tree structure of IdentRule objects.
    """
    def __init__(self):
        """
        C++: ParsingIdentMgr()
        """
        super().__init__()
        self.m_EndLineNumber = -1
        self.m_IdentRule = IdentRule() # Root Dummy Rule
        self.m_TotalIdentRuleMap = {} # Key: IdentName, Value: IdentRule
        
        self.m_MsgBuf = ""
        self.m_SplitMsgMap = {} # Line cache for identification (simple list/dict)

    def __del__(self):
        """
        C++: ~ParsingIdentMgr()
        """
        self.clear_rule()

    def init(self, rule_file_name, delimiter):
        """
        C++: bool Init(string RuleFileName, string Delimiter)
        Loads Ident Rules from file.
        """
        self.clear_rule()
        self.m_IdentRule.m_DefaultIdentRule = None

        if not os.path.exists(rule_file_name):
            self.set_error_msg(f"Ident Rule File Open Error : {rule_file_name}")
            return False

        try:
            with open(rule_file_name, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            if not lines:
                self.set_error_msg(f"Identification Rule Format Error (Empty)")
                return False

            # First line: Count
            try:
                count = int(lines[0].strip())
                if count == 0:
                    return True
            except ValueError:
                self.set_error_msg(f"Identification Rule Format Error : {lines[0]}")
                return False

            # Process Lines
            for line in lines[1:]:
                line = line.strip()
                if not line: continue

                # Tokenize (Using DataExtractor helper logic or simple split)
                # C++ uses MsgTokenizeString which adds a dummy empty string at index 0
                raw_tokens = line.split(delimiter)
                str_list = [""] + [t.strip() for t in raw_tokens]

                if len(str_list) != 11:
                    self.set_error_msg(f"Ident Rule File Item Miss : Need Item Size(11), Current({len(str_list)})")
                    return False

                ident_rule = IdentRule()
                ident_rule.m_IdentName = str_list[1]
                ident_rule.m_ParentName = str_list[2]
                ident_rule.m_IdString = str_list[3]
                
                try:
                    ident_rule.m_ParsingRuleId = int(str_list[4])
                    ident_rule.m_OutPutFlag = bool(int(str_list[5]))
                    ident_rule.m_ParsingFlag = bool(int(str_list[6]))
                    ident_rule.m_XMLFlag = bool(int(str_list[7]))
                    ident_rule.m_EditorUseFlag = bool(int(str_list[8]))
                    ident_rule.m_DefaultIdentRuleFlag = bool(int(str_list[9]))
                except ValueError:
                    self.set_error_msg(f"Invalid numeric value in rule: {line}")
                    return False

                # Validation
                if not ident_rule.m_IdentName or not ident_rule.m_IdString or ident_rule.m_ParsingRuleId < 1:
                    self.set_error_msg(f"Invalid ParsingIdentMgr Value : {ident_rule.m_IdentName}/{ident_rule.m_IdString}/{ident_rule.m_ParsingRuleId}")
                    return False

                if ident_rule.m_IdentName in self.m_TotalIdentRuleMap:
                    self.set_error_msg(f"Duplication ParsingIdentMgr Name : {ident_rule.m_IdentName}")
                    return False

                self.m_TotalIdentRuleMap[ident_rule.m_IdentName] = ident_rule

            # Validate Count
            if len(self.m_TotalIdentRuleMap) != count:
                self.set_error_msg(f"Identification Rule Count MisMatch!!! Spec: {count}, Real: {len(self.m_TotalIdentRuleMap)}")
                return False

            # Build Tree Structure
            for ident_rule in self.m_TotalIdentRuleMap.values():
                # Link Parent
                if ident_rule.m_ParentName:
                    if ident_rule.m_ParentName not in self.m_TotalIdentRuleMap:
                        self.set_error_msg(f"Can't Search Parent Ident Name : {ident_rule.m_ParentName}")
                        return False
                    
                    parent = self.m_TotalIdentRuleMap[ident_rule.m_ParentName]
                    if ident_rule.m_DefaultIdentRuleFlag:
                        parent.m_DefaultIdentRule = ident_rule
                    
                    parent.m_ChildRuleMap[ident_rule.m_IdentName] = ident_rule
                else:
                    if ident_rule.m_DefaultIdentRuleFlag:
                        self.m_IdentRule.m_DefaultIdentRule = ident_rule

            # Add Roots to m_IdentRule
            for ident_rule in self.m_TotalIdentRuleMap.values():
                if not ident_rule.m_ParentName:
                    self.m_IdentRule.m_ChildRuleMap[ident_rule.m_IdentName] = ident_rule

            return True

        except Exception as e:
            self.set_error_msg(f"Exception loading rules: {e}")
            return False

    def clear_rule(self):
        """
        C++: void ClearRule()
        """
        self.m_TotalIdentRuleMap.clear()
        self.m_IdentRule.m_ChildRuleMap.clear()

    def identify(self, msg_buf):
        """
        C++: IdentInfo* Identify(const char* MsgBuf)
        Identifies the message by traversing the rule tree.
        """
        self.m_MsgBuf = msg_buf
        self.line_scanning() # Fill m_SplitMsgMap
        
        current_rule = self.m_IdentRule # Root
        child_ident_result = True
        
        # Traversing Logic
        # 1. Start from Root
        # 2. Check Children
        # 3. If match found, move to child and repeat
        # 4. If no child match, check Default Rule
        
        if not current_rule.m_ChildRuleMap:
            return IdentInfo()

        final_rule = current_rule # Keep track of last matched

        while True:
            child_matched = False
            
            # Check Children
            for child_rule in current_rule.m_ChildRuleMap.values():
                if self.check_identify(child_rule):
                    child_matched = True
                    current_rule = child_rule
                    final_rule = child_rule
                    # print(f"[Identify] Match: {current_rule.m_IdentName}")
                    break
            
            if not child_matched:
                # Check Default Rule
                if current_rule.m_DefaultIdentRule:
                    current_rule = current_rule.m_DefaultIdentRule
                    # Default Rule matched implicitly, continue traversal
                    # If default rule has children, loop continues
                    if current_rule.m_ChildRuleMap:
                        continue
                    else:
                        # Default leaf
                        return IdentInfo(None, current_rule.m_IdentName, self.m_IdString, current_rule, None)
                else:
                    # No children matched, no default -> End of search
                    break
        
        # If traversal ended, check if current rule is valid leaf or intermediate
        # C++ logic: if childIdentResult == false && identRulePtr != &m_IdentRule -> Valid intermediate?
        # Actually C++ returns IdentInfo with the rule found so far.
        
        if final_rule != self.m_IdentRule:
             return IdentInfo(None, final_rule.m_IdentName, self.m_IdString, final_rule, None)
             
        # Fail
        return IdentInfo()

    def check_identify(self, ident_rule):
        """
        C++: bool Identify(IdentRule* IdentRulePtr) (Overloaded internal check)
        Checks if the message matches the specific IdentRule condition.
        Uses ExtractDataFromParsingRule.
        """
        parsing_rule = ident_rule.m_ParsingRulePtr
        if not parsing_rule:
            return False

        s_line = parsing_rule.m_StartLine
        e_line = parsing_rule.m_EndLine
        
        for i in range(s_line, e_line + 1):
            line_buf = self.get_line(i)
            if not line_buf: return False
            
            temp_buf = ""
            
            if parsing_rule.m_ParsingType == LINE_STR:
                if ident_rule.m_IdString in line_buf:
                    if ident_rule.m_OutPutFlag:
                        self.m_IdString = ident_rule.m_IdString
                    return True
                continue
            else:
                # Use DataExtractor static helper logic
                # We need to access DataExtractor logic here. 
                # Since DataExtractor.extract_data_from_parsing_rule is instance method in prev code,
                # we can make a temporary instance or make methods static.
                # Here assuming we duplicate simple logic or create temp instance.
                extractor = DataExtractor(None) # Dummy mgr
                success, val = extractor.extract_data_from_parsing_rule(parsing_rule, line_buf, i)
                if not success: continue
                temp_buf = val

            if temp_buf == ident_rule.m_IdString:
                if ident_rule.m_OutPutFlag:
                    self.m_IdString = temp_buf
                return True
                
        return False

    def insert_tmpl_grp(self, tmpl_grp):
        """
        C++: bool InsertTmplGrp(ParsingTmplGrp* TmplGrp)
        """
        rule = self.search_ident_rule(tmpl_grp.m_IdentName)
        if not rule:
            self.set_error_msg(f"Can't Search Ident Rule : {tmpl_grp.m_IdentName}")
            return False
        
        rule.m_TmplGrpList.append(tmpl_grp)
        return True

    def insert_ident_parsing_rule(self, parsing_rule_map):
        """
        C++: bool InsertIdentParsingRule(RuleMap& ParsingRuleMap)
        Links ParsingRules to IdentRules based on ID.
        """
        for ident_rule in self.m_TotalIdentRuleMap.values():
            if ident_rule.m_ParsingRuleId not in parsing_rule_map:
                self.set_error_msg(f"Can't Search ParsingRuleId : {ident_rule.m_ParsingRuleId}")
                return False
            
            p_rule = parsing_rule_map[ident_rule.m_ParsingRuleId]
            if p_rule.m_TmplName: # Should be empty for ident rules
                self.set_error_msg(f"Parsing Rule for Identification have not Template Name. Id : {ident_rule.m_ParsingRuleId}")
                return False
                
            ident_rule.m_ParsingRulePtr = p_rule
        return True

    def search_ident_rule(self, ident_name):
        return self.m_TotalIdentRuleMap.get(ident_name)

    # -------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------
    def line_scanning(self):
        """
        Splits message into lines for line-based access.
        """
        self.m_SplitMsgMap = {}
        lines = self.m_MsgBuf.splitlines()
        for i, line in enumerate(lines):
            self.m_SplitMsgMap[i] = line
        self.m_EndLineNumber = len(lines)

    def get_line(self, line_number):
        """
        1-based index access.
        """
        idx = line_number - 1
        return self.m_SplitMsgMap.get(idx)

    # String trim helpers are built-in Python string methods (.strip, .lstrip, .rstrip)
    # used directly in code.