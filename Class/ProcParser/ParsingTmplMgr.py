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
# XMLParserMgr Import if needed, currently stubbed or assumed available

class ParsingTmplMgr(ObjectBase):
    """
    Manages loading and organization of Parsing Templates.
    Links templates to their groups via ParsingTmplGrpMgr.
    """
    def __init__(self, tmpl_grp_mgr):
        """
        C++: ParsingTmplMgr(ParsingTmplGrpMgr* TmplGrpMgrPtr)
        """
        super().__init__()
        self.m_ParsingTmplGrpMgr = tmpl_grp_mgr
        self.m_TmplMap = {} # Key: TmplName, Value: ParsingTmpl
        self.m_ExceptTmplVec = [] # For inner templates

    def __del__(self):
        """
        C++: ~ParsingTmplMgr()
        """
        self.clear_rule()

    def init(self, rule_file_name, delimiter):
        """
        C++: bool Init(string RuleFileName, string Delimiter)
        Loads template rules from file.
        """
        self.clear_rule()

        if not os.path.exists(rule_file_name):
            self.set_error_msg(f"Template Rule File Open Error : {rule_file_name}")
            return False

        try:
            with open(rule_file_name, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            if not lines:
                self.set_error_msg(f"Template Rule Format Error (Empty)")
                return False

            try:
                count = int(lines[0].strip())
                print(f"[ParsingTmplMgr] Template Rule Count : {count}")
                if count == 0:
                    return True
            except ValueError:
                self.set_error_msg(f"Template Rule Format Error : {lines[0]}")
                return False

            for line in lines[1:]:
                line = line.strip()
                if not line: continue

                # Tokenize logic (dummy at index 0)
                raw_tokens = line.split(delimiter)
                str_list = [""] + [t.strip() for t in raw_tokens]

                if len(str_list) != 20:
                    self.set_error_msg(f"Template Rule File Item Miss : Need(20), Current({len(str_list)})")
                    return False

                tmpl = ParsingTmpl()
                tmpl.m_TmplName = str_list[1]
                tmpl.m_TmplGrpName = str_list[2]
                tmpl.m_EventId = str_list[3]
                
                try:
                    tmpl.m_Sequence = int(str_list[4])
                    tmpl.m_TmplType = TMPL_LIST_TYPE if int(str_list[5]) else TMPL_ATOMIC_TYPE
                    tmpl.m_HeaderSize = int(str_list[6])
                    tmpl.m_DataSize = int(str_list[7])
                    tmpl.m_SkipLine = int(str_list[8])
                    tmpl.m_NextFlag = bool(int(str_list[9]))
                    tmpl.m_EquipFlag = int(str_list[10])
                    # Consumers str_list[11]
                    tmpl.m_Consumers = str_list[11]
                    tmpl.m_AtomResultHideFlag = bool(int(str_list[12]))
                    tmpl.m_EORHideFlag = bool(int(str_list[13]))
                    
                    # XML Fields (14 ~ 18)
                    xmlRootElementTag = str_list[14]
                    # In C++ code: strList[15].c_str() + xmlRootElementTag.size() logic 
                    # seems to imply extracting suffix or just using index 15.
                    # Assuming standard CSV structure here.
                    
                    # [Caution] C++ logic:
                    # xmlRootElementPCDATATag = strList[15].c_str() + xmlRootElementTag.size();
                    # This looks like pointer arithmetic to skip prefix. 
                    # Python equivalent: 
                    # if str_list[15].startswith(xmlRootElementTag): 
                    #    xmlRootElementPCDATATag = str_list[15][len(xmlRootElementTag):]
                    # But if strList[15] is just the tag, we use it directly.
                    # Let's assume direct usage for now or implement prefix skip.
                    
                    tmpl.m_XmlRootElementPCDATA = str_list[16]
                    tmpl.m_XmlKeyElementTag = str_list[17]
                    
                    tmpl.m_XmlRootElementPCDATAKind = XML_PC_DATA if int(str_list[18]) == 0 else XML_ATTRIBUTE

                except ValueError:
                    self.set_error_msg(f"Invalid numeric value in template rule: {line}")
                    return False

                # XML Tag Parsing Logic (Stubbed for now, needs XmlParserMgr equivalent)
                # ...

                if not tmpl.m_TmplName or not tmpl.m_TmplGrpName or not tmpl.m_EventId:
                    self.set_error_msg(f"Invalid Template Value : {tmpl.m_TmplName}")
                    return False

                if tmpl.m_DataSize == 0:
                    self.set_error_msg(f"Not Allow Template Data Size is Zero : {tmpl.m_TmplName}")
                    return False

                if tmpl.m_TmplName in self.m_TmplMap:
                    self.set_error_msg(f"Duplication Template Name : {tmpl.m_TmplName}")
                    return False

                # Insert to Group or Exception List
                if tmpl.m_TmplGrpName == "RULE_INNER_DUMMY_TMPL_GRP":
                    self.m_ExceptTmplVec.append(tmpl)
                else:
                    if not self.m_ParsingTmplGrpMgr.insert_tmpl(tmpl):
                        self.set_error_msg(self.m_ParsingTmplGrpMgr.get_error_msg())
                        return False

                self.m_TmplMap[tmpl.m_TmplName] = tmpl

            if len(self.m_TmplMap) != count:
                self.set_error_msg(f"Template Rule Count MisMatch!!! Spec: {count}, Real: {len(self.m_TmplMap)}")
                return False

            return True

        except Exception as e:
            self.set_error_msg(f"Exception loading templates: {e}")
            return False

    def insert_rule(self, parsing_rule):
        """
        C++: bool InsertRule(ParsingRule* ParsingRulePtr)
        Links a ParsingRule to its Template.
        """
        if parsing_rule.m_TmplName not in self.m_TmplMap:
            self.set_error_msg(f"Can't Search Template Name For RuleId : {parsing_rule.m_ParsingRuleId}")
            return False
        
        tmpl = self.m_TmplMap[parsing_rule.m_TmplName]
        tmpl.m_RuleList.append(parsing_rule)
        return True

    def rule_inner_tmpl_setup(self, parsing_rule_map):
        """
        C++: bool RuleInnerTmplSetup(RuleMap& ParsingRuleMap)
        Links Inner Templates to Rules (Recursive structures).
        """
        if not self.m_ExceptTmplVec:
            return True

        for tmpl in self.m_ExceptTmplVec:
            # Name is rule ID string?
            try:
                rule_id = int(tmpl.m_TmplName)
                if rule_id not in parsing_rule_map:
                    self.set_error_msg(f"Can't find rule for RuleInnerTmpl : {tmpl.m_TmplName}")
                    return False
                
                parsing_rule_map[rule_id].m_RuleInnerTmpl = tmpl
            except ValueError:
                self.set_error_msg(f"Invalid Rule ID in Inner Tmpl Name: {tmpl.m_TmplName}")
                return False
                
        self.m_ExceptTmplVec.clear()
        return True

    def clear_rule(self):
        """
        C++: void ClearRule()
        """
        self.m_TmplMap.clear()
        self.m_ExceptTmplVec.clear()

    def xml_init_rule_tag_in_key_tmpl(self):
        """
        C++: void XmlInitRuleTagInKeyTmpl()
        Optimizes XML tag matching for List Templates.
        """
        # Logic stub: Iterate all templates, check if LIST type and KeyTag exists, 
        # then mark rules inside that match the key tag prefix.
        pass