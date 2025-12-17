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
from Class.ProcParser.RuleType import ParsingTmplGrp, RULE_INNER_DUMMY_TMPL_GRP_STR

class ParsingTmplGrpMgr(ObjectBase):
    """
    Manages loading and organization of Parsing Template Groups.
    Links groups to Identification Rules via ParsingIdentMgr.
    """
    def __init__(self, ident_mgr):
        """
        C++: ParsingTmplGrpMgr(ParsingIdentMgr* ParsingIdentMgr)
        """
        super().__init__()
        self.m_ParsingIdentMgr = ident_mgr
        self.m_TmplGrpList = [] # List of ParsingTmplGrp
        self.m_TmplGrpMap = {} # Key: TmplGrpName, Value: ParsingTmplGrp

    def __del__(self):
        """
        C++: ~ParsingTmplGrpMgr()
        """
        self.clear_rule()

    def init(self, rule_file_name, delimiter):
        """
        C++: bool Init(string RuleFileName, string Delimiter)
        Loads template group rules from file.
        """
        self.clear_rule()

        if not os.path.exists(rule_file_name):
            self.set_error_msg(f"Template Group Rule File Open Error : {rule_file_name}")
            return False

        try:
            with open(rule_file_name, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            if not lines:
                self.set_error_msg(f"Template Group Rule Format Error (Empty)")
                return False

            try:
                count = int(lines[0].strip())
                print(f"[ParsingTmplGrpMgr] Template Group Rule Count : {count}")
                if count == 0:
                    return True
            except ValueError:
                self.set_error_msg(f"Template Group Rule Format Error : {lines[0]}")
                return False

            for line in lines[1:]:
                line = line.strip()
                if not line: continue

                # Tokenize logic (dummy at index 0 to match C++ indexing)
                raw_tokens = line.split(delimiter)
                str_list = [""] + [t.strip() for t in raw_tokens]

                if len(str_list) < 4:
                    self.set_error_msg(f"Template Group Rule File Item Miss : Need(4), Current({len(str_list)})")
                    return False

                tmpl_grp = ParsingTmplGrp()
                tmpl_grp.m_IdentName = str_list[1]
                tmpl_grp.m_TmplGrpName = str_list[2]

                if not tmpl_grp.m_IdentName:
                    self.set_error_msg(f"There is no Template Group Value : {tmpl_grp.m_TmplGrpName}")
                    return False

                # Link to IdentMgr
                # C++: if(tmplGrpPtr->m_TmplGrpName != RULE_INNER_DUMMY_TMPL_GRP_STR)
                if tmpl_grp.m_TmplGrpName != "RULE_INNER_DUMMY_TMPL_GRP": # or use constant from RuleType
                    if not self.m_ParsingIdentMgr.insert_tmpl_grp(tmpl_grp):
                        self.set_error_msg(self.m_ParsingIdentMgr.get_error_msg())
                        return False

                self.m_TmplGrpList.append(tmpl_grp)

                if not tmpl_grp.m_TmplGrpName:
                    continue

                self.m_TmplGrpMap[tmpl_grp.m_TmplGrpName] = tmpl_grp

            if len(self.m_TmplGrpList) != count:
                self.set_error_msg(f"Template Group Rule Count MisMatch!!! Spec: {count}, Real: {len(self.m_TmplGrpList)}")
                return False

            return True

        except Exception as e:
            self.set_error_msg(f"Exception loading template groups: {e}")
            return False

    def insert_tmpl(self, tmpl):
        """
        C++: bool InsertTmpl(ParsingTmpl* Tmpl)
        Called by ParsingTmplMgr to link a template to its group.
        """
        if tmpl.m_TmplGrpName not in self.m_TmplGrpMap:
            self.set_error_msg(f"There is no Template Group Name : {tmpl.m_TmplGrpName}")
            return False
        
        grp = self.m_TmplGrpMap[tmpl.m_TmplGrpName]
        grp.m_TmplVector.append(tmpl)
        return True

    def clear_rule(self):
        """
        C++: void ClearRule()
        """
        self.m_TmplGrpList.clear()
        self.m_TmplGrpMap.clear()