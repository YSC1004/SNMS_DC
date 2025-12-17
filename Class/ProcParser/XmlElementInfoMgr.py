import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.ProcParser.RuleType import *
from Class.ProcParser.XMLParserMgr import XmlDataInfo
from Class.ProcParser.ObjectBase import ObjectBase

class XmlElementInfoMgr(ObjectBase):
    """
    Helper class to navigate and extract data from XmlDataInfo tree structure.
    Used by DataExtractor for XML parsing.
    """
    
    XML_FIND_PCDATA_ERROR   = -1
    XML_FIND_ATTRNAME_ERROR = -2
    XML_DATA_END            = -3

    def __init__(self, data_info):
        """
        C++: XmlElementInfoMgr(XmlDataInfo* DataInfo)
        """
        super().__init__()
        self.m_RootXmlDataInfo = data_info
        self.m_RootElementKey = None # XmlDataInfo
        self.m_RootElementKeyPos = -1
        self.m_KeyXmlDataInfo = None # XmlDataInfo
        self.m_RootElementListKeyPos = 0

    def __del__(self):
        pass

    def is_valid_key_xml_sequence(self, seq):
        """
        C++: bool IsValidKeyXmlSequence(const int& Seq)
        """
        if self.m_KeyXmlDataInfo and self.m_KeyXmlDataInfo.size() > seq:
            return True
        return False

    def find_pc_data(self, parsing_rule, str_list, seq, key_data_kind, tmpl_root_element_key_pcdata_tag, root_element_list_pos):
        """
        C++: int FindPCData(...)
        Traverses the XML tree to find data defined by ParsingRule.
        """
        cur_node = None
        find_node = None
        tag_pos = 0
        
        # Check Root
        if not parsing_rule.m_XMLElementTagVec:
            return 0

        # Compare Root Name with first tag in rule
        rule_root_tag = parsing_rule.m_XMLElementTagVec[0]
        
        if self.m_RootXmlDataInfo.m_ElementName == rule_root_tag:
            tag_pos += 1
            if len(parsing_rule.m_XMLElementTagVec) > tag_pos:
                cur_node = self.m_RootXmlDataInfo.m_ChildDataInfoVector
            else:
                # Rule points to Root itself? Usually not handled or handled specially
                pass
        else:
            return 0

        flag = True
        find_node_flag = True
        root_tag_pos = -1
        root_tag_vec_size = len(tmpl_root_element_key_pcdata_tag)

        while flag and find_node_flag and cur_node:
            find_node_flag = False # Reset for loop
            
            for i, node in enumerate(cur_node):
                if node.m_ElementName == parsing_rule.m_XMLElementTagVec[tag_pos]:
                    # Attribute Key Logic
                    if key_data_kind == XML_ATTRIBUTE:
                        if root_tag_vec_size > 1:
                            if node.m_ElementName == tmpl_root_element_key_pcdata_tag[0]:
                                root_tag_pos += 1
                                if root_element_list_pos != root_tag_pos:
                                    continue
                    
                    tag_pos += 1
                    find_node_flag = True
                    
                    if len(parsing_rule.m_XMLElementTagVec) == tag_pos:
                        flag = False # Found target
                        find_node = node
                        
                        # List Handling logic
                        if self.m_KeyXmlDataInfo and find_node == self.m_KeyXmlDataInfo:
                            find_node = self.m_KeyXmlDataInfo.get_at(seq)
                        break
                    else:
                        # Navigate Deeper
                        if self.m_KeyXmlDataInfo and self.m_KeyXmlDataInfo == node:
                            if self.m_KeyXmlDataInfo.size() > seq:
                                next_node = self.m_KeyXmlDataInfo.get_at(seq)
                                cur_node = next_node.m_ChildDataInfoVector if next_node else None
                            else:
                                cur_node = None
                                return self.XML_DATA_END
                        else:
                            if node == self.m_RootElementKey:
                                # Access specific sibling in root list
                                next_node = node.get_at(self.m_RootElementKeyPos)
                                cur_node = next_node.m_ChildDataInfoVector if next_node else None
                            else:
                                cur_node = node.m_ChildDataInfoVector
                        break
            
            if not find_node_flag:
                # Loop ended without match in current level
                break

        if find_node:
            ret = self.get_data_from_xml_data_node(find_node, str_list, parsing_rule)
            if ret < 0: return ret
        else:
            # self.set_error_msg(f"ElementTag[{parsing_rule.m_XMLElementTag}] not found.")
            pass

        return len(str_list)

    def get_data_from_xml_data_node(self, data_node, str_list, parsing_rule):
        """
        C++: int GetDataFromXmlDataNode(...)
        Extracts PCDATA or Attribute Value from the found node.
        """
        find_value = True

        # 1. Attribute Extraction
        if parsing_rule.m_XMLCharDataMask & XML_ATTR_VALUE_MASK:
            for attr_name in parsing_rule.m_XMLAttrNameList:
                find_value = False
                if data_node.m_AttributeNames:
                    for i, name in enumerate(data_node.m_AttributeNames):
                        if name == attr_name:
                            find_value = True
                            str_list.append(data_node.m_AttrValues[i])
                            break
                
                if not find_value:
                    # self.set_error_msg(f"Attribute {attr_name} not found in {parsing_rule.m_XMLElementTag}")
                    return self.XML_FIND_ATTRNAME_ERROR

        # 2. PCData Extraction
        if find_value:
            if parsing_rule.m_XMLCharDataMask & XML_PCDATA_MASK:
                str_list.append(data_node.m_PCData if data_node.m_PCData else "")
            
            elif parsing_rule.m_XMLCharDataMask & XML_PCDATA_ALL_LIST_MASK:
                # Iterate siblings/own list
                size = data_node.size()
                for i in range(size):
                    node = data_node.get_at(i)
                    str_list.append(node.m_PCData if node and node.m_PCData else "")
            
            elif parsing_rule.m_XMLCharDataMask & XML_PCDATA_PART_LIST_MASK:
                for idx in parsing_rule.m_XMLPCDataList:
                    if data_node.size() > idx - 1:
                        node = data_node.get_at(idx - 1)
                        str_list.append(node.m_PCData if node and node.m_PCData else "")
                    else:
                        return self.XML_FIND_PCDATA_ERROR

        return 0

    def set_key_element(self, tmpl_root_tag, tmpl_root_key_pcdata_tag, tmpl_key_element_tag, key_data_kind, key_pc_data, root_element_list_pos=0):
        """
        C++: bool SetKeyElement(...)
        Locates the iteration root (Key Element) for list processing.
        """
        self.m_RootElementKey = None
        self.m_KeyXmlDataInfo = None
        self.m_RootElementKeyPos = -1

        root_data_info = self.get_xml_data_info_from_root(tmpl_root_tag)
        if not root_data_info: return False

        self.m_RootElementKeyPos = 0
        
        # Iterate over root list to find key match
        size = root_data_info.size()
        for i in range(size):
            node = root_data_info.get_at(i)
            if not node: break
            
            self.m_RootElementKeyPos = i
            
            data_info = self.get_xml_data_info(node, tmpl_root_key_pcdata_tag, key_data_kind)
            
            if data_info:
                if key_data_kind == XML_PC_DATA:
                    # Match PCDATA
                    if not data_info.m_PCData or data_info.m_PCData == key_pc_data:
                        self.m_RootElementKey = root_data_info
                        break
                
                elif key_data_kind == XML_ATTRIBUTE:
                    # Match Attribute "Name=Value"
                    if "=" in key_pc_data:
                        name, val = key_pc_data.split("=", 1)
                        # val = val.strip() if needed
                        
                        is_find = False
                        
                        # Get count logic omitted for brevity, assuming standard find loop
                        # Simple attribute check
                        if data_info.m_AttributeNames:
                            for k, attr_name in enumerate(data_info.m_AttributeNames):
                                if attr_name == name and data_info.m_AttrValues[k] == val:
                                    is_find = True
                                    self.m_RootElementListKeyPos = 0 # logic might need refinement for list pos
                                    break
                        
                        if is_find:
                            self.m_RootElementKey = root_data_info
                            break
            
        if self.m_RootElementKey:
            root_node = self.m_RootElementKey.get_at(self.m_RootElementKeyPos)
            self.m_KeyXmlDataInfo = self.get_xml_data_info(
                root_node, 
                tmpl_key_element_tag, 
                key_data_kind, 
                root_element_list_pos, 
                self.m_RootElementListKeyPos
            )
            return True if self.m_KeyXmlDataInfo else False
            
        return False

    def get_xml_data_info_from_root(self, element_tag_vec):
        """
        C++: XmlDataInfo* GetXmlDataInfoFromRoot(CharPtrVector& ElementTag)
        """
        cur_node = None
        find_node = None
        tag_pos = 0
        
        if not element_tag_vec: return None

        if self.m_RootXmlDataInfo.m_ElementName == element_tag_vec[tag_pos]:
            tag_pos += 1
            if len(element_tag_vec) > tag_pos:
                cur_node = self.m_RootXmlDataInfo.m_ChildDataInfoVector
            else:
                return self.m_RootXmlDataInfo
        else:
            return None

        flag = True
        find_node_flag = True

        while flag and find_node_flag and cur_node:
            find_node_flag = False
            for node in cur_node:
                if node.m_ElementName == element_tag_vec[tag_pos]:
                    find_node_flag = True
                    tag_pos += 1
                    
                    if len(element_tag_vec) == tag_pos:
                        flag = False
                        find_node = node
                        break
                    else:
                        cur_node = node.m_ChildDataInfoVector
                        break
        
        return find_node

    def get_xml_data_info(self, root_data_info, element_tag_vec, key_data_kind, root_element_list_pos=0, root_element_list_key_pos=0):
        """
        C++: XmlDataInfo* GetXmlDataInfo(...)
        Navigates from a given root node.
        """
        cur_node = root_data_info.m_ChildDataInfoVector
        if not element_tag_vec:
            return cur_node[0] if cur_node else None

        tag_pos = 0
        flag = True
        find_node_flag = True
        find_node = None
        
        root_tag_pos = -1
        root_key_tag_pos = -1

        while flag and find_node_flag and cur_node:
            find_node_flag = False
            for node in cur_node:
                if node.m_ElementName == element_tag_vec[tag_pos]:
                    # Index Logic for list handling
                    if key_data_kind == XML_ATTRIBUTE:
                        if tag_pos == 0:
                            root_tag_pos += 1
                            if root_element_list_pos != root_tag_pos: continue
                        if tag_pos == 1:
                            root_key_tag_pos += 1
                            if root_element_list_key_pos != root_key_tag_pos: continue
                    
                    find_node_flag = True
                    tag_pos += 1
                    
                    if len(element_tag_vec) == tag_pos:
                        flag = False
                        find_node = node
                        break
                    else:
                        cur_node = node.m_ChildDataInfoVector
                        break
        
        return find_node

    def get_key_xml_data_info(self, seq):
        """
        C++: XmlDataInfo* GetKeyXmlDataInfo(int Seq)
        """
        if self.m_KeyXmlDataInfo:
            return self.m_KeyXmlDataInfo.get_at(seq)
        return None