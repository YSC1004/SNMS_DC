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

class DataMapper(ObjectBase):
    """
    Base class for Data Mapping Logic.
    Parses configuration strings to determine failure behavior and default values.
    Concrete mapping logic is implemented in subclasses (StringDataMapper, NumberDataMapper).
    """
    def __init__(self):
        """
        C++: DataMapper::DataMapper(void)
        """
        super().__init__()
        self.m_MappingFailBehavior = MAPPING_FAIL_BEHAVIOR_USE_PARSED_ITEM
        self.m_DefaultValue = ""

    def __del__(self):
        """
        C++: DataMapper::~DataMapper(void)
        """
        pass

    def init_mapping_value(self, value):
        """
        C++: bool InitMappingValue(string Value)
        Parses the mapping configuration string.
        Format: BehaviorChar,0,0,0,DefaultValue_PBS4_MappingData...
        """
        if not value:
            return False

        # 1. Check Failure Behavior (First Character)
        first_char = value[0]
        
        # Note: _CHAR constants are defined in RuleType.h/py ('1', '2', '3')
        if first_char == MAPPING_FAIL_BEHAVIOR_USE_PARSED_ITEM_CHAR: # '1'
            self.m_MappingFailBehavior = MAPPING_FAIL_BEHAVIOR_USE_PARSED_ITEM
            
        elif first_char == MAPPING_FAIL_BEHAVIOR_USE_DEFAULE_VALUE_CHAR: # '2'
            self.m_MappingFailBehavior = MAPPING_FAIL_BEHAVIOR_USE_DEFAULE_VALUE
            
        elif first_char == MAPPING_FAIL_BEHAVIOR_USE_PARSED_FAIL_CHAR: # '3'
            self.m_MappingFailBehavior = MAPPING_FAIL_BEHAVIOR_USE_PARSED_FAIL
            
        else:
            self.m_MappingFailBehavior = MAPPING_FAIL_BEHAVIOR_USE_PARSED_ITEM
            return False

        # 2. Strip Header
        # C++: Value.erase(0, 2+6); -> Removes "1,0,0,0," (8 chars)
        if len(value) < 8:
            return False
            
        remaining_value = value[8:]

        # 3. Extract Default Value
        # Delimiter: MAPPING_DEFAULT_VALUE_DELIMITER ("_PBS4_")
        delimiter = MAPPING_DEFAULT_VALUE_DELIMITER
        
        parts = remaining_value.split(delimiter, 1)
        
        if len(parts) < 2:
            # Delimiter not found
            return False
            
        default_val = parts[0]
        mapping_data = parts[1]

        self.m_DefaultValue = default_val

        # Clear default value if behavior is not USE_DEFAULT_VALUE
        if self.m_MappingFailBehavior != MAPPING_FAIL_BEHAVIOR_USE_DEFAULE_VALUE:
            self.m_DefaultValue = ""

        # 4. Delegate to Subclass
        return self.set_value(mapping_data)

    def get_default_value(self):
        """
        C++: const char* GetDefaultValue()
        """
        return None # C++ implementation returns NULL

    # -------------------------------------------------------
    # Virtual Methods (To be overridden)
    # -------------------------------------------------------
    def set_value(self, value):
        """
        C++: virtual bool SetValue(string Value)
        """
        return True

    def find_mapping_value(self, value):
        """
        C++: virtual const char* FinaMappingValue(const char* Value)
        """
        return None