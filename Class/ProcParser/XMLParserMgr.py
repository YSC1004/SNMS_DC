import sys
import os
import xml.parsers.expat

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# XmlDataInfo Class
# -------------------------------------------------------
class XmlDataInfo:
    """
    Node structure for parsed XML data.
    """
    def __init__(self):
        self.m_ElementName = ""
        self.m_PCData = ""
        self.m_AttributeNames = [] # List[str]
        self.m_AttrValues = []     # List[str]

        self.m_OwnDataInfoVector = [] # List[XmlDataInfo] (Siblings/Same Name List)
        self.m_ChildDataInfoVector = [] # List[XmlDataInfo] (Children)
        self.m_Size = -1

    def __del__(self):
        self.m_OwnDataInfoVector.clear()
        self.m_ChildDataInfoVector.clear()

    def size(self):
        if self.m_Size != -1:
            pass
        else:
            if self.m_OwnDataInfoVector:
                self.m_Size = len(self.m_OwnDataInfoVector) + 1
            else:
                self.m_Size = 1
        return self.m_Size

    def get_at(self, pos):
        """
        Equivalent to operator[](int Pos)
        """
        if pos == 0:
            return self
        else:
            if self.m_OwnDataInfoVector and len(self.m_OwnDataInfoVector) > pos - 1:
                return self.m_OwnDataInfoVector[pos - 1]
            else:
                return None

# -------------------------------------------------------
# XmlParserMgr Class
# -------------------------------------------------------
class XmlParserMgr:
    """
    Manages XML Parsing using Expat.
    Builds a tree of XmlDataInfo.
    """
    def __init__(self):
        self.m_RootXmlDataInfo = None
        self.m_CurXmlDataInfo = None
        self.m_Parser = None
        self.m_UseAttributeData = False
        self.m_RootElementListcnt = 1
        
        self.m_Buf = "" # PCData Buffer
        self.m_XMLDepth = 0
        self.m_GabageFlag = False
        
        self.m_UseAttributeNames = [] # List[str] passed from Rule
        self.m_TmplPtr = None # Current Template

    def __del__(self):
        self.m_RootXmlDataInfo = None # GC handles recursive deletion

    def init(self):
        self.m_GabageFlag = False
        self.m_Buf = ""
        self.m_XMLDepth = 0
        
        # Create Parser
        self.m_Parser = xml.parsers.expat.ParserCreate()
        self.m_Parser.StartElementHandler = self.start_element_handler
        self.m_Parser.EndElementHandler = self.end_element_handler
        self.m_Parser.CharacterDataHandler = self.character_data_handler
        
        self.m_RootXmlDataInfo = None
        self.m_CurXmlDataInfo = None
        self.m_RootElementListcnt = 1
        
        return True

    def xml_parse(self, msg, msg_length, ident_rule_ptr):
        """
        C++: bool XMLParse(...)
        Entry point for parsing XML string.
        """
        if not self.init(): return False

        self.m_UseAttributeData = ident_rule_ptr.m_UseXMLAttributeFlag
        self.m_UseAttributeNames = ident_rule_ptr.m_UseXMLAttributeNames

        # Check Template Logic (Stubbed/Simplified)
        if self.m_UseAttributeData and self.m_UseAttributeNames:
            flag = False
            for grp in ident_rule_ptr.m_TmplGrpList:
                if grp.m_TmplVector:
                    self.m_TmplPtr = grp.m_TmplVector[0] # Simplification
                    flag = True
                    break
            
            if flag:
                if not self.m_TmplPtr.m_XmlRootElementPCDATATagVec:
                    return False
            else:
                return False

        try:
            self.m_Parser.Parse(msg, True) # True = is_final
            return True
        except xml.parsers.expat.ExpatError as e:
            err_msg = f"XML Parsing error at line {e.lineno}: {xml.parsers.expat.ErrorString(e.code)}"
            print(f"[XmlParserMgr] {err_msg}")
            # print("--------XML is not wellform---------")
            return False

    def get_root_element_info(self):
        return self.m_RootXmlDataInfo

    # -------------------------------------------------------
    # Expat Handlers
    # -------------------------------------------------------
    def start_element_handler(self, name, attrs):
        """
        Callback for start tag.
        """
        tmp = None

        if self.m_RootXmlDataInfo is None:
            self.m_Buf = ""
            tmp = self.insert_xml_data_info(self.m_XMLDepth, name)
        else:
            if self.m_Buf:
                self.update_xml_data_info(self.m_Buf)
                self.m_Buf = ""
            tmp = self.insert_xml_data_info(self.m_XMLDepth, name)

        # Attribute Processing
        if self.m_UseAttributeData and self.m_UseAttributeNames:
            for attr_name in self.m_UseAttributeNames:
                if attr_name in attrs:
                    if tmp.m_AttributeNames is None:
                        tmp.m_AttributeNames = []
                        tmp.m_AttrValues = []
                    
                    tmp.m_AttributeNames.append(attr_name)
                    tmp.m_AttrValues.append(attrs[attr_name])

        self.m_XMLDepth += 1
        self.m_GabageFlag = False

    def end_element_handler(self, name):
        """
        Callback for end tag.
        """
        self.m_GabageFlag = True
        
        if self.m_Buf:
            self.update_xml_data_info(self.m_Buf)
            self.m_Buf = ""
            
        self.m_XMLDepth -= 1

    def character_data_handler(self, data):
        """
        Callback for PCData.
        """
        if not self.m_GabageFlag:
            self.m_Buf += data

    # -------------------------------------------------------
    # Tree Building Logic
    # -------------------------------------------------------
    def insert_xml_data_info(self, depth, element_name):
        """
        Logic to insert node into the tree based on depth.
        """
        data_info = XmlDataInfo()
        data_info.m_ElementName = element_name

        if self.m_RootXmlDataInfo is None:
            self.m_RootXmlDataInfo = data_info
            self.m_CurXmlDataInfo = data_info
            return data_info

        end_node = None
        
        # Navigate to current parent
        # C++ logic re-traverses from root using depth.
        # Efficient way: keep stack of parents. But following C++ logic:
        
        curr = self.m_RootXmlDataInfo
        # Traverse depth to find parent
        # Depth 0 = Root. Depth 1 = Child of Root.
        
        # Re-implementing C++ loop logic:
        # It traverses down the last child of 'm_ChildDataInfoVector'
        # And last of 'm_OwnDataInfoVector'
        
        target_parent = None
        
        # Simple stack approach to find parent (assuming DFS traversal order of SAX)
        # But stick to C++ logic for fidelity
        
        node_ptr = self.m_RootXmlDataInfo
        
        for i in range(depth):
            if node_ptr is None: # Should not happen if depth matches structure
                node_ptr = self.m_RootXmlDataInfo
                continue
                
            if not node_ptr.m_ChildDataInfoVector:
                node_ptr.m_ChildDataInfoVector = []
                break # Found leaf parent
            else:
                if len(node_ptr.m_ChildDataInfoVector) == 0:
                    break
                else:
                    # Go to last child
                    node_ptr = node_ptr.m_ChildDataInfoVector[-1]
                    # If that child has siblings (OwnVector), go to last sibling
                    if node_ptr.m_OwnDataInfoVector:
                        node_ptr = node_ptr.m_OwnDataInfoVector[-1]
        
        end_node = node_ptr
        
        # Insert Logic
        if end_node.m_ChildDataInfoVector is None:
            end_node.m_ChildDataInfoVector = []
            
        if len(end_node.m_ChildDataInfoVector) == 0:
            end_node.m_ChildDataInfoVector.append(data_info)
        else:
            last_child = end_node.m_ChildDataInfoVector[-1]
            
            # Check for same element name (List handling)
            if last_child.m_ElementName == element_name:
                flag = False
                # Check template for list handling logic
                if self.m_UseAttributeData and self.m_UseAttributeNames and self.m_TmplPtr:
                    vec_cnt = len(self.m_TmplPtr.m_XmlRootElementPCDATATagVec)
                    if vec_cnt > 0:
                        if element_name in self.m_TmplPtr.m_XmlRootElementPCDATATagVec:
                            flag = True
                            if vec_cnt > 1 and element_name == self.m_TmplPtr.m_XmlRootElementPCDATATagVec[0]:
                                self.m_RootElementListcnt += 1
                
                if flag:
                    end_node.m_ChildDataInfoVector.append(data_info)
                else:
                    # Append as sibling
                    if last_child.m_OwnDataInfoVector is None:
                        last_child.m_OwnDataInfoVector = []
                    last_child.m_OwnDataInfoVector.append(data_info)
            else:
                end_node.m_ChildDataInfoVector.append(data_info)

        self.m_CurXmlDataInfo = data_info
        return data_info

    def update_xml_data_info(self, pc_data):
        if self.m_CurXmlDataInfo:
            self.m_CurXmlDataInfo.m_PCData = pc_data.strip()
        return self.m_CurXmlDataInfo

    # -------------------------------------------------------
    # Utilities
    # -------------------------------------------------------
    @staticmethod
    def xml_element_tag_parsing(element_tag, str_vec):
        """
        C++: bool XMLElementTagParsing(const char* ElementTag, StringVector& StrVec)
        Splits tag path "Root/Child/Leaf".
        """
        if not element_tag:
            return False

        # Add trailing slash if missing logic in C++?
        # C++: sprintf(buf, "%s/", ElementTag) if no slash.
        # Python split logic:
        
        parts = element_tag.split('/')
        valid_parts = [p for p in parts if p] # Remove empty strings from leading/trailing slash split
        
        if not valid_parts:
            return False
            
        str_vec.extend(valid_parts)
        return True