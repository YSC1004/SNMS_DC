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

# Constants
PRE_DEF_NULL_MAPPING = "PRE_DEF_NULL_MAPPING"

class NumberDataMapper(DataMapper):
    """
    Maps input integer (or range) to output string based on rules.
    Format: _PBS2_Range(1~5,7)_PBS3_NewItem_PBS3_Flag ...
    """
    def __init__(self):
        """
        C++: NumberDataMapper()
        """
        super().__init__()
        self.m_IntStringMap = {} # Key: int, Value: str

    def __del__(self):
        """
        C++: ~NumberDataMapper()
        """
        self.m_IntStringMap.clear()

    def set_value(self, value):
        """
        C++: bool SetValue(string Value)
        Parses the mapping string (ranges/lists) and populates the map.
        """
        # 1. Split by Item Delimiter (_PBS2_)
        tokens = value.split(MAPPING_EACH_DELIMITER)
        
        for token in tokens:
            if not token:
                continue

            # 2. Split by Value Delimiter (_PBS3_)
            # Format: RangeStr _PBS3_ NewItem _PBS3_ Flag
            # C++: itemList.size() < 4 (0:dummy, 1:Range, 2:New, 3:Flag)
            # Python: size < 3 (0:Range, 1:New, 2:Flag)
            
            item_list = token.split(MAPPING_VALUE_DELIMITER)
            
            if len(item_list) < 3:
                continue
                
            range_str = item_list[0]
            new_item = item_list[1]
            flag_str = item_list[2]
            
            try:
                # Check Flag
                if int(flag_str) != 0:
                    # Logic for Null Mapping
                    final_val = "" if new_item == PRE_DEF_NULL_MAPPING else new_item
                    
                    # 3. Parse Range String (e.g., "1~5,7,9")
                    value_range = self.get_value_range(range_str)
                    
                    # 4. Insert into Map
                    for num in value_range:
                        # C++ check duplicates, here just overwrite or log
                        if num in self.m_IntStringMap:
                            print(f"[NumberDataMapper] [CORE_ERROR] value insert error : {num}({range_str})")
                        else:
                            self.m_IntStringMap[num] = final_val
                            
            except ValueError:
                continue

        return True

    def find_mapping_value(self, value):
        """
        C++: const char* FinaMappingValue(const char* Value)
        """
        try:
            key = int(value)
            
            # Lookup
            if key in self.m_IntStringMap:
                return self.m_IntStringMap[key]
                
        except (ValueError, TypeError):
            # Input value is not a number
            pass

        # Fallback Logic (Same as StringDataMapper/DataMapper)
        if self.m_MappingFailBehavior == MAPPING_FAIL_BEHAVIOR_USE_DEFAULE_VALUE:
            return self.m_DefaultValue
            
        elif self.m_MappingFailBehavior == MAPPING_FAIL_BEHAVIOR_USE_PARSED_FAIL:
            return None
            
        elif self.m_MappingFailBehavior == MAPPING_FAIL_BEHAVIOR_USE_PARSED_ITEM:
             return None # C++ logic usually handled by caller for this case, or return value? 
             # In C++ DataMapper it returns NULL for default case.
             
        return None

    def get_value_range(self, value_str):
        """
        C++: void GetValueRange(string Value, IntVector& ValueRange)
        Parses comma-separated list with ranges (e.g. "1,3~5,10")
        """
        int_vector = []
        
        # Split by comma
        items = value_str.split(',')
        
        for item in items:
            item = item.strip()
            if not item: continue
            
            # Check for range '~'
            if '~' in item:
                # C++ Tokenize logic implies dummy index 0
                # "1~5" -> parts[0]="1", parts[1]="5"
                range_parts = item.split('~')
                
                if len(range_parts) >= 2:
                    try:
                        start = int(range_parts[0])
                        end = int(range_parts[1])
                        
                        # C++ Loop: for(start; start < end + 1; start++)
                        # Handles ascending ranges
                        if start <= end:
                            int_vector.extend(range(start, end + 1))
                        else:
                            # If descending (5~1), C++ loop wouldn't run or needs adjustment.
                            # Python range handles step -1 if needed, but assuming ascending here.
                            pass 
                    except ValueError:
                        print(f"[NumberDataMapper] [CORE_ERROR] Number range value invalid : {item}")
            else:
                # Single Number
                try:
                    int_vector.append(int(item))
                except ValueError:
                    print(f"[NumberDataMapper] Invalid number : {item}")
                    
        return int_vector