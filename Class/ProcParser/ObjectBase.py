import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

class ObjectBase:
    """
    Base class for objects, providing common error message handling.
    """
    def __init__(self):
        """
        C++: ObjectBase::ObjectBase()
        """
        self.m_ErrMsg = ""

    def __del__(self):
        """
        C++: ObjectBase::~ObjectBase()
        """
        pass

    def get_error_msg(self):
        """
        C++: string ObjectBase::GetErrorMsg()
        """
        return self.m_ErrMsg

    def set_error_msg(self, msg_or_fmt, *args):
        """
        C++: 
        1. void ObjectBase::SetErrorMsg(string Msg)
        2. void ObjectBase::SetErrorMsg(const char *format, ...)
        
        Handles both simple string assignment and printf-style formatting.
        """
        if not args:
            # Case 1: Simple string assignment
            self.m_ErrMsg = str(msg_or_fmt)
        else:
            # Case 2: Formatted string (vsprintf style)
            try:
                # Python's % operator handles C-style formatting codes (%d, %s, etc.)
                self.m_ErrMsg = msg_or_fmt % args
            except Exception as e:
                # Fallback in case of formatting error
                self.m_ErrMsg = f"{msg_or_fmt} {args} (Format Error: {e})"