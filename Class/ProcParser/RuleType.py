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
# Constants & Enums
# -------------------------------------------------------
# Parsing Types
NOT_USE = -1
LINE_STR = 0
STRCOL_STRSTR_ENDCOL = 1
STRCOL_ENDSTR = 2
STRSTR_EXTSIZE = 3
STRSTR_ENDSTR = 4
STRSTR_ENDCOL = 5
EXTSIZE_ENDSTR = 6
STRSTR_TOKEN = 7
LINE_FULL = 8
FULL_MESSAGE_EXTRACT = 9
STRCOL_STRSTR_TOKEN = 10
STRCOL_STRSTR_REMAINSTR = 11
STRCOL_STRSTR_TOKEN_REMAINSTR = 12
CREATE_DATA_IN_PREDEFINED = 13
PARSING_RULE_DATE_TIME_NONE_FLAG   =    0

# Data Types
DT_STR = 0
DT_INT = 1
DT_FLT = 2

# Template Types
TMPL_ATOMIC_TYPE = 0
TMPL_LIST_TYPE = 1

# Trim Types
NO_TRIM = 0
L_TRIM = 1
R_TRIM = 2
LR_TRIM = 3

# Defined Data Types
PARSING_DATE = 0
PARSING_TIME = 1

# XML Data Kinds
XML_PC_DATA = 0
XML_ATTRIBUTE = 1

# Mapping Constants
MAPPING_FAIL_BEHAVIOR_USE_PARSED_ITEM = 1

# -------------------------------------------------------
# Mapping Types & Behaviors
# -------------------------------------------------------
MAPPING_STRING_TYPE             = 1
MAPPING_STRING_TYPE_CHAR        = '1'

MAPPING_NUMBER_TYPE             = 2
MAPPING_NUMBER_TYPE_CHAR        = '2'

MAPPING_FAIL_BEHAVIOR_USE_PARSED_ITEM           = 1
MAPPING_FAIL_BEHAVIOR_USE_PARSED_ITEM_CHAR      = '1'

MAPPING_FAIL_BEHAVIOR_USE_DEFAULE_VALUE         = 2 # C++ Typo 유지 (DEFAULE -> DEFAULT)
MAPPING_FAIL_BEHAVIOR_USE_DEFAULE_VALUE_CHAR    = '2'

MAPPING_FAIL_BEHAVIOR_USE_PARSED_FAIL           = 3
MAPPING_FAIL_BEHAVIOR_USE_PARSED_FAIL_CHAR      = '3'

# -------------------------------------------------------
# Mapping Delimiters
# -------------------------------------------------------
MAPPING_EACH_DELIMITER          = "_PBS2_"
MAPPING_VALUE_DELIMITER         = "_PBS3_"
MAPPING_DEFAULT_VALUE_DELIMITER = "_PBS4_"

# -------------------------------------------------------
# Dummy Strings for Inner Rules
# -------------------------------------------------------
RULE_INNER_DUMMY_TMPL_GRP_STR       = "RULE_INNER_DUMMY_TMPL_GRP"
RULE_INNER_DUMMY_TMPL_EVT_ID_STR    = "RULE_INNER_DUMMY_TMPL_EVT_ID"
RULE_INNER_DUMMY_IDENT_ID_STR       = "RULE_INNER_DUMMY_IDENT_ID"

DEFAULT_ARRAY_SIZE = 30

# -------------------------------------------------------
# Date/Time Parsing Masks & Flags
# -------------------------------------------------------
XML_PCDATA_MASK                     = 0x00000001
XML_PCDATA_ALL_LIST_MASK            = 0x00000002
XML_PCDATA_PART_LIST_MASK           = 0x00000004
XML_ATTR_VALUE_MASK                 = 0x00000008

PARSING_RULE_DATE_TIME_NONE_FLAG    = 0
PARSING_RULE_DATE_FLAG              = 1
PARSING_RULE_TIME_FLAG              = 2
PARSING_RULE_DATE_TIME_FLAG         = 3

PARSING_RULE_DATE_TIME_NONE_MASK    = 0x00000001
PARSING_RULE_DATE_MASK              = 0x00000002
PARSING_RULE_TIME_MASK              = 0x00000004
PARSING_RULE_DATE_TIME_MASK         = 0x00000008

# -------------------------------------------------------
# Classes
# -------------------------------------------------------

class IdentRule:
    """
    Identification Rule Definition.
    """
    def __init__(self):
        self.m_IdentName = ""
        self.m_ParentName = ""
        self.m_IdString = ""
        self.m_ParsingRuleId = 0
        self.m_OutPutFlag = False
        self.m_ParsingFlag = False
        self.m_XMLFlag = False
        self.m_EditorUseFlag = False
        
        self.m_ParsingRulePtr = None # ParsingRule Object
        self.m_ChildRuleMap = {} # Key: Name, Value: IdentRule
        self.m_TmplGrpList = [] # List of ParsingTmplGrp
        self.m_ConsumerVector = [] # List of strings
        self.m_Consumers = ""
        
        self.m_DefaultIdentRule = None
        self.m_DefaultIdentRuleFlag = False
        self.m_UseXMLAttributeFlag = False
        self.m_UseXMLAttributeNames = []

class ParsingTmplGrp:
    """
    Grouping of Parsing Templates.
    """
    def __init__(self):
        self.m_TmplGrpName = ""
        self.m_IdentName = ""
        self.m_TmplConsumerVector = []
        self.m_TmplVector = [] # List of ParsingTmpl

    def check_consumer(self, consumer):
        if not self.m_TmplConsumerVector:
            return True
        return consumer in self.m_TmplConsumerVector

class ParsingTmpl:
    """
    Parsing Template Definition.
    """
    def __init__(self):
        self.m_TmplName = ""
        self.m_TmplGrpName = ""
        self.m_EventId = ""
        self.m_Sequence = 0
        self.m_TmplType = TMPL_ATOMIC_TYPE
        
        self.m_HeaderSize = 0
        self.m_DataSize = 0
        self.m_SkipLine = 0
        self.m_NextFlag = False
        self.m_EquipFlag = 0
        
        self.m_AtomResultHideFlag = False
        self.m_EORHideFlag = False
        self.m_Consumers = ""
        
        self.m_RuleList = [] # List of ParsingRule
        
        # XML
        self.m_XmlKeyElementTag = ""
        self.m_XmlRootElementTagVec = []
        self.m_XmlRootElementPCDATATagVec = []
        self.m_XmlRootElementPCDATA = ""
        self.m_XmlRootElementPCDATAKind = XML_PC_DATA
        self.m_XmlKeyElementTagVec = []

class ParsingRule:
    """
    Individual Parsing Rule Definition.
    """
    def __init__(self):
        self.m_ParsingRuleId = 0
        self.m_TmplName = ""
        self.m_ParsingName = ""
        self.m_Sequence = 0
        
        self.m_StartLine = 0
        self.m_EndLine = 0
        self.m_StartColumn = 0
        self.m_EndColumn = 0
        
        self.m_StartString = ""
        self.m_EndString = ""
        self.m_ExtractSize = 0
        
        self.m_DataType = DT_STR
        self.m_TokenIndex = 0
        self.m_TokenDelimiter = ""
        self.m_TokenSize = 0
        
        self.m_NullStringFlag = False
        self.m_NullSkipFlag = False
        self.m_PreDataCopyFlag = False
        self.m_ParsingType = NOT_USE
        
        self.m_DefinedDataType = -1
        self.m_DefinedDataTypeFormat = -1
        
        self.m_BscNo = False
        self.m_DelimiterType = 0 # 0:Str, 1:Char
        
        self.m_DataTypeCheckFlag = False
        self.m_MappingValueFlag = False
        self.m_MappingValue = ""
        self.m_InclusionNameFlag = False
        self.m_DataMapper = None # DataMapper Object
        
        self.m_TrimFlag = 0
        self.m_DateTimeFlag = 0
        
        self.m_RuleInnerTmpl = None # ParsingTmpl Object
        self.m_IsTagInKeyTmpl = False
        self.m_SetTimeFlag = 0
        self.m_SetTime = ""
        
        # XML
        self.m_XMLElementTag = ""
        self.m_XMLElementTagVec = []
        self.m_XMLCharDataMask = 0
        self.m_XMLPCDataList = []
        self.m_XMLAttrNameList = []

class IdentInfo:
    """
    Result of Identification.
    """
    def __init__(self, last_ident_name="", final_ident_name="", ident_id_string="", 
                 ident_rule=None, convert_msg=""):
        self.m_LastIdentName = last_ident_name
        self.m_FinalIdentName = final_ident_name
        self.m_IdentIdString = ident_id_string
        self.m_IdentRulePtr = ident_rule
        self.m_ConvertMsg = convert_msg