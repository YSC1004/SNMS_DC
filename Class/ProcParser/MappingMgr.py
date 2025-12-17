import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

class MappingRule:
    """
    Structure to hold a single mapping rule entry.
    """
    def __init__(self):
        self.m_EquipId = ""
        self.m_PortNo = 0
        self.m_BscNo = 0
        self.m_AsciiHeader = ""

class MappingMgr:
    """
    Manages loading and searching of NE Mapping Rules.
    """
    def __init__(self):
        """
        C++: MappingMgr()
        """
        self.m_MappingRuleMap = {} # Key: EquipId (str), Value: List[MappingRule]

    def __del__(self):
        """
        C++: ~MappingMgr()
        """
        self.clear_rule()

    def init(self, rule_file_name, delimiter):
        """
        C++: bool Init(string RuleFileName, string Delimiter)
        Loads mapping rules from a file.
        """
        self.clear_rule()

        if not os.path.exists(rule_file_name):
            print(f"[MappingMgr] Mapping Rule File Open Error : {rule_file_name}")
            return False

        try:
            with open(rule_file_name, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            if not lines:
                print(f"[MappingMgr] Mapping Rule Format Error (Empty)")
                return False

            # First line is count
            try:
                count = int(lines[0].strip())
                print(f"[MappingMgr] Mapping Rule Count : {count}")
                if count == 0:
                    return True
            except ValueError:
                print(f"[MappingMgr] Mapping Rule Format Error : {lines[0]}")
                return False

            # Process lines
            for line in lines[1:]:
                line = line.strip()
                if not line: continue

                # Tokenize
                # C++ logic uses DataExtractor::MsgTokenizeString which adds a dummy empty string at index 0.
                # So C++ indices 1, 2, 3, 4, 5 correspond to Python splits 0, 1, 2, 3, 4.
                # C++ check: size != 6 (0 + 5 real tokens).
                
                raw_tokens = line.split(delimiter)
                
                # We simulate C++ vector behavior: Index 0 is dummy
                str_list = [""] + [t.strip() for t in raw_tokens] 

                if len(str_list) != 6:
                    print(f"[MappingMgr] Parsing Rule File Item Miss : {line}")
                    return False

                rule = MappingRule()
                # Index 1: EquipId
                rule.m_EquipId = str_list[1]
                
                # Index 2: PortNo
                try: rule.m_PortNo = int(str_list[2])
                except: rule.m_PortNo = 0
                
                # Index 3: BscNo
                try: rule.m_BscNo = int(str_list[3])
                except: rule.m_BscNo = 0
                
                # Index 4: AsciiHeader
                rule.m_AsciiHeader = str_list[4]

                # Insert into Map
                if rule.m_EquipId not in self.m_MappingRuleMap:
                    self.m_MappingRuleMap[rule.m_EquipId] = []
                
                self.m_MappingRuleMap[rule.m_EquipId].append(rule)

            # self.show_mapping_rule()
            return True

        except Exception as e:
            print(f"[MappingMgr] Exception loading rules: {e}")
            return False

    def clear_rule(self):
        """
        C++: void ClearRule()
        """
        self.m_MappingRuleMap.clear()

    def find_mapping_name(self, ne_id, bsc_no, port_no):
        """
        C++: const char* FindMappingName(const char* NeId, int BscNo, int PortNo)
        Searches for a mapping header based on NE ID and either BSC No or Port No.
        """
        if ne_id not in self.m_MappingRuleMap:
            return None

        rule_list = self.m_MappingRuleMap[ne_id]
        
        for rule in rule_list:
            # Priority 1: BscNo check
            if rule.m_BscNo != -2:
                if rule.m_BscNo == bsc_no:
                    # print(f"[MappingMgr] Find Mapping Rule (BSC Match): {rule.m_AsciiHeader}")
                    return rule.m_AsciiHeader
            
            # Priority 2: PortNo check
            elif rule.m_PortNo != -2:
                if rule.m_PortNo == port_no:
                    # print(f"[MappingMgr] Find Mapping Rule (Port Match): {rule.m_AsciiHeader}")
                    return rule.m_AsciiHeader
                    
        return None

    def show_mapping_rule(self):
        """
        C++: void ShowMappingRule()
        Debug print.
        """
        for equip_id, rules in self.m_MappingRuleMap.items():
            print(f"[MappingMgr] EquipId : {equip_id}")
            for rule in rules:
                print(f" BSCNO       : {rule.m_BscNo}")
                print(f" PORTNO      : {rule.m_PortNo}")
                print(f" ASCIIHEADER : {rule.m_AsciiHeader}")
                print(" ")