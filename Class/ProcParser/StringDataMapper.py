import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.ProcParser.DataMapper import DataMapper
from Class.ProcParser.RuleType import *

# Constants from RuleType.h / Defined Macros
PRE_DEF_NULL_MAPPING = "PRE_DEF_NULL_MAPPING" # Placeholder, actual value needed from header

class StringDataMapper(DataMapper):
    """
    Maps input string to output string based on rules.
    Format: _PBS2_OldItem_PBS3_NewItem_PBS3_Flag ...
    """
    def __init__(self):
        """
        C++: StringDataMapper()
        """
        super().__init__()
        self.m_StringMap = {} # Key: str, Value: str

    def __del__(self):
        """
        C++: ~StringDataMapper()
        """
        self.m_StringMap.clear()

    def set_value(self, value):
        """
        C++: bool SetValue(string Value)
        Parses the mapping string and populates the map.
        """
        # 1. Split by Item Delimiter (_PBS2_)
        # C++: DataExtractor::MsgTokenizeString(..., MAPPING_EACH_DELIMITER)
        # Note: C++ tokenizer puts a dummy empty string at index 0.
        # Python split will treat "_PBS2_A..." as ["", "A..."].
        
        tokens = value.split(MAPPING_EACH_DELIMITER)
        
        for token in tokens:
            if not token:
                continue

            # 2. Split by Value Delimiter (_PBS3_)
            # Format: OldItem _PBS3_ NewItem _PBS3_ Flag
            # C++: itemList.size() < 4 (0:dummy, 1:Old, 2:New, 3:Flag)
            # Python: size < 3 (0:Old, 1:New, 2:Flag)
            
            item_list = token.split(MAPPING_VALUE_DELIMITER)
            
            if len(item_list) < 3:
                continue
                
            old_item = item_list[0]
            new_item = item_list[1]
            flag_str = item_list[2]
            
            try:
                # Check Flag (atoi)
                if int(flag_str) != 0:
                    # Logic for Null Mapping Constant
                    final_val = "" if new_item == PRE_DEF_NULL_MAPPING else new_item
                    
                    # Insert into Map (Check for duplicates like C++ logic)
                    if old_item in self.m_StringMap:
                        print(f"[StringDataMapper] [CORE_ERROR] value insert error : {old_item} (Duplicate)")
                    else:
                        self.m_StringMap[old_item] = final_val
                        
            except ValueError:
                continue

        return True

    def find_mapping_value(self, value):
        """
        C++: const char* FinaMappingValue(const char* Value)
        """
        # Lookup in Map
        if value in self.m_StringMap:
            return self.m_StringMap[value]
        
        # Not Found - Check Behavior
        if self.m_MappingFailBehavior == MAPPING_FAIL_BEHAVIOR_USE_DEFAULE_VALUE:
            return self.m_DefaultValue
            
        elif self.m_MappingFailBehavior == MAPPING_FAIL_BEHAVIOR_USE_PARSED_FAIL:
            return None # C++ returns NULL
            
        elif self.m_MappingFailBehavior == MAPPING_FAIL_BEHAVIOR_USE_PARSED_ITEM:
             return value # C++ Logic in ParsingRuleMgr usually handles this, but here for completeness
             
        # Default fallback
        return None