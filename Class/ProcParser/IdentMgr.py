import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# Imports
# -------------------------------------------------------
from Class.ProcParser.ObjectBase import ObjectBase
from Class.ProcParser.ParsingIdentMgr import ParsingIdentMgr
from Class.Event.FrLogger import FrLogger

# Lazy Import for Managers to avoid potential circular dependency issues during load
# In a real scenario, these files must exist.
try:
    from Class.ProcParser.ParsingTmplGrpMgr import ParsingTmplGrpMgr
    from Class.ProcParser.ParsingTmplMgr import ParsingTmplMgr
    from Class.ProcParser.ParsingRuleMgr import ParsingRuleMgr
except ImportError:
    # Placeholder classes if not yet implemented
    ParsingTmplGrpMgr = None
    ParsingTmplMgr = None
    ParsingRuleMgr = None

class IdentMgr(ObjectBase):
    """
    Top-level Manager for Identification and Parsing Rules.
    Initializes sub-managers (Ident, TmplGrp, Tmpl, Rule) and delegates tasks.
    """
    def __init__(self):
        """
        C++: IdentMgr()
        """
        super().__init__()
        self.m_ParsingIdentMgr = None
        self.m_ParsingTmplGrpMgr = None
        self.m_ParsingTmplMgr = None
        self.m_ParsingRuleMgr = None
        
        self.m_PreBuf = "" # Cached string for message check
        self.m_CleanMsg = "" # Processed message

    def __del__(self):
        """
        C++: ~IdentMgr()
        """
        self.rules_data_clear()

    def init(self, rule_dir, rule_id, rule_delimiter):
        """
        C++: bool Init(string RuleDir, string RuleId, string RuleDelimiter)
        Initializes all sub-managers and loads their respective rule files.
        """
        self.rules_data_clear()

        rule_file_base = f"{rule_dir}/{rule_id}"

        # 1. Create Sub-Managers
        self.m_ParsingIdentMgr = ParsingIdentMgr()
        
        if ParsingTmplGrpMgr:
            self.m_ParsingTmplGrpMgr = ParsingTmplGrpMgr(self.m_ParsingIdentMgr)
        
        if ParsingTmplMgr:
            self.m_ParsingTmplMgr = ParsingTmplMgr(self.m_ParsingTmplGrpMgr)
            
        if ParsingRuleMgr:
            self.m_ParsingRuleMgr = ParsingRuleMgr(self.m_ParsingIdentMgr, self.m_ParsingTmplMgr)

        # 2. Init Ident Rules
        if not self.m_ParsingIdentMgr.init(f"{rule_file_base}_IDENT.RULE", rule_delimiter):
            self.set_error_msg(f"Ident Rule({rule_file_base}) Init Error - {self.m_ParsingIdentMgr.get_error_msg()}")
            return False

        # 3. Init Template Group Rules
        if self.m_ParsingTmplGrpMgr:
            if not self.m_ParsingTmplGrpMgr.init(f"{rule_file_base}_TMPLGRP.RULE", rule_delimiter):
                self.set_error_msg(f"Template Group Rule({rule_file_base}) Init Error - {self.m_ParsingTmplGrpMgr.get_error_msg()}")
                return False

        # 4. Init Template Rules
        if self.m_ParsingTmplMgr:
            if not self.m_ParsingTmplMgr.init(f"{rule_file_base}_TMPL.RULE", rule_delimiter):
                self.set_error_msg(f"Template Rule({rule_file_base}) Init Error - {self.m_ParsingTmplMgr.get_error_msg()}")
                return False

        # 5. Init Parsing Rules
        if self.m_ParsingRuleMgr:
            if not self.m_ParsingRuleMgr.init(f"{rule_file_base}_PARSINGRULE.RULE", rule_delimiter):
                self.set_error_msg(f"Parsing Rule({rule_file_base}) Init Error - {self.m_ParsingRuleMgr.get_error_msg()}")
                return False

        # 6. Post Init Linking
        self.m_ParsingIdentMgr.misc_info_init()
        
        if self.m_ParsingTmplMgr:
            self.m_ParsingTmplMgr.xml_init_rule_tag_in_key_tmpl()
            
        self.m_ParsingIdentMgr.tagging_use_xml_attribute()

        print(f"[IdentMgr] Parsing Rule({rule_id}) Init Success")
        return True

    def rules_data_clear(self):
        """
        C++: void RulesDataClear()
        """
        self.m_ParsingIdentMgr = None
        self.m_ParsingTmplGrpMgr = None
        self.m_ParsingTmplMgr = None
        self.m_ParsingRuleMgr = None

    def show_hierarchy(self, detail):
        """
        C++: void ShowHierarchy(bool Detail)
        """
        if self.m_ParsingIdentMgr:
            self.m_ParsingIdentMgr.show_hierarchy(detail)

    def show_ident_hierarchy(self, ident_name, detail):
        """
        C++: void ShowIdentHierarchy(string IdentName, bool Detail)
        """
        if self.m_ParsingIdentMgr:
            self.m_ParsingIdentMgr.show_ident_hierarchy(ident_name, detail)

    def enable_log(self, flag, level):
        """
        C++: void EnableLog(bool Flag, int Level)
        """
        if flag:
            FrLogger.get_instance().enable("IdentMgr", level)
        else:
            # FrLogger.get_instance().disable("IdentMgr")
            pass

    def msg_check(self, msg):
        """
        C++: char* MsgCheck(char* Msg)
        Trims whitespace from the message.
        """
        if not msg:
            print("[IdentMgr] [CORE_ERROR] Msg Length is 0...")
            return None

        # C++ logic attempts to strip leading/trailing spaces.
        # It handles newlines specifically in leading/trailing logic.
        # Python's strip() is generally robust for this purpose.
        
        self.m_CleanMsg = msg.strip()
        return self.m_CleanMsg

    def identify_msg(self, msg):
        """
        C++: IdentInfo* IdentifyMsg(char* Msg)
        Process the message string and return identification info.
        """
        clean_msg = self.msg_check(msg)

        if clean_msg:
            # Delegate to ParsingIdentMgr
            info = self.m_ParsingIdentMgr.identify(clean_msg)
            
            # Store the converted/cleaned message in info
            if info:
                info.m_ConvertMsg = clean_msg
            return info
            
        return None

    def identify_check(self, msg_buf, info_list):
        """
        C++: bool IdentifyCheck(const char* MsgBuf, IdentRuleList& InfoList)
        """
        if self.m_ParsingIdentMgr:
            return self.m_ParsingIdentMgr.identify_check(msg_buf, info_list)
        return False

    def get_line(self, line_number):
        """
        C++: const char* GetLine(int LineNumber)
        """
        if self.m_ParsingIdentMgr:
            return self.m_ParsingIdentMgr.get_line(line_number)
        return None

    def get_last_line(self):
        """
        C++: const char* GetLastLine()
        Returns the last line of the current message buffer.
        """
        # C++ implementation searched backwards from rear buffer.
        # In Python, assuming m_CleanMsg holds the current context string.
        if self.m_CleanMsg:
            lines = self.m_CleanMsg.splitlines()
            if lines:
                return lines[-1]
        return None