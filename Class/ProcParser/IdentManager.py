import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.ProcParser.IdentMgr import IdentMgr
from Class.Common.CommType import AsMmcResultT, MAX_RESULT_MSG, R_CONTINUE, R_COMPLETE, MMC_CMD_RESULT
from Class.Util.FrUtilMisc import FrUtilMisc

class IdentManager(IdentMgr):
    """
    Subclass of IdentMgr specific to Parser process.
    Handles MMC Command Response matching and forwarding.
    """
    def __init__(self):
        """
        C++: IdentManager()
        """
        super().__init__()
        
        from ParserWorld import ParserWorld
        # Reference to list in ParserWorld (passed by ref in C++)
        # In Python, list assignment passes reference, so modifications affect original
        self.m_ResCmdList = ParserWorld.get_instance().m_ResponseCmdList
        
        self.m_CmdResultCheckFlag = True
        self.m_RuleType = -1
        self.m_Msg = ""
        # m_LineBuf, m_TmpBuf replaced by Python strings
        # m_MMCRes replaced by local object

    def __del__(self):
        """
        C++: ~IdentManager()
        """
        super().__del__()

    def data_identify(self, msg):
        """
        C++: IdentInfo* DataIdentfy(char* Msg)
        Main entry point for identifying a message.
        """
        self.m_CmdResultCheckFlag = True
        
        # Logging (Stub)
        # if MAINPTR.GetMsgLogging(): print(msg)

        # Delegate to Parent (IdentMgr.identify_msg)
        info = self.identify_msg(msg)
        
        if info:
            self.m_Msg = msg # Keep reference to original message
            self.ident_result(info.m_LastIdentName, info.m_FinalIdentName, info.m_IdentIdString)
            
        return info

    def send_mmc_response_data(self, msg_id, continue_flag=False):
        """
        C++: void SendMMCResponseData(int MsgId, bool ContinueFlag)
        Sends the identified message back as an MMC response.
        Handles fragmentation if message is too long.
        """
        from ParserWorld import ParserWorld
        world = ParserWorld.get_instance()

        msg_len = len(self.m_Msg)
        tmp_buf = self.m_Msg
        
        mmc_res = AsMmcResultT()
        mmc_res.id = msg_id

        # Simple Case: Message fits in one packet
        if msg_len < MAX_RESULT_MSG:
            mmc_res.result = tmp_buf
            mmc_res.resultMode = R_CONTINUE if continue_flag else R_COMPLETE
            world.send_response_command_data(mmc_res)
            return

        # Complex Case: Fragmentation loop
        while True:
            mmc_res.resultMode = R_CONTINUE
            # Take chunk
            chunk_size = MAX_RESULT_MSG - 1
            chunk = tmp_buf[:chunk_size]
            mmc_res.result = chunk
            
            # Check if this is the last chunk
            if len(tmp_buf) < MAX_RESULT_MSG:
                mmc_res.result = tmp_buf
                mmc_res.resultMode = R_CONTINUE if continue_flag else R_COMPLETE
                world.send_response_command_data(mmc_res)
                return
            
            # Send current chunk and advance
            world.send_response_command_data(mmc_res)
            tmp_buf = tmp_buf[chunk_size:] # Slice remaining

    def check_mmc_response_data(self, id_string, key):
        """
        C++: bool CheckMMCResponseData(const char* IdString, char* Key)
        """
        if self.m_RuleType == 1:
            return self.check_mmc_response_data_type_one()
        elif self.m_RuleType == 2:
            return self.check_mmc_response_data_type_two()
        elif self.m_RuleType == 3:
            return self.check_mmc_response_data_type_three(id_string, key)
        else:
            print(f"[IdentManager] [CORE_ERROR] Unknown RuleType : {self.m_RuleType}")
            return False

    def set_rule_type(self, rule_type):
        self.m_RuleType = rule_type

    def check_mmc_response_data_type_one(self):
        """
        Type 1: SAMSUNG_BSM, etc. Checks line 1 (0-indexed in Python)
        """
        line = self.get_line(2) # C++ GetLine(1) -> 2nd line? No, C++ GetLine is 1-based index logic
        # C++ GetLine(1) logic: count == LineNumber(1) -> returns 2nd line if count starts at 0? 
        # Checking C++ DataExtractor::GetLine logic:
        # count starts at 0. if(count == LineNumber). So GetLine(1) returns the line at index 1 (second line).
        
        if not line: return False
        
        tmp_buf = line.strip()
        
        # Check for ']'
        if ']' not in tmp_buf:
            return False
            
        # pos = strchr(buf, ']') + 2
        idx = tmp_buf.find(']')
        if idx == -1 or idx + 2 >= len(tmp_buf):
            return False
            
        cmd_str = tmp_buf[idx+2:]
        
        return self._match_and_send(cmd_str)

    def check_mmc_response_data_type_two(self):
        """
        Type 2: SAMSUNG_1XBSS. Checks line 2 (3rd line in 0-indexed?)
        C++ GetLine(2) -> index 2.
        """
        line = self.get_line(3) 
        if not line: return False
        
        tmp_buf = line.strip()
        return self._match_and_send(tmp_buf)

    def _match_and_send(self, cmd_str):
        """
        Helper for Type 1 & 2 matching loop
        """
        from ParserWorld import ParserWorld
        world = ParserWorld.get_instance()

        # Iterate copy or handle modification safely?
        # C++ erases from list during iteration which invalidates iterator.
        # Python iteration over list allows removal if we break or copy.
        
        for cmd in self.m_ResCmdList[:]: # Iterate copy
            if cmd.Mmc == cmd_str:
                self.send_mmc_response_data(cmd.Id)
                world.cancel_timer(cmd.TimerKey)
                # cmd destructor handled by GC
                self.m_ResCmdList.remove(cmd)
                return True
        return False

    def check_mmc_response_data_type_three(self, id_string, key):
        """
        Type 3: PCX. Checks IdString match.
        """
        from ParserWorld import ParserWorld
        world = ParserWorld.get_instance()

        for cmd in self.m_ResCmdList[:]:
            if cmd.IdString == id_string:
                # Key check commented out in C++
                
                last_line = self.get_last_line()
                if last_line:
                    if "CONTINUE" in last_line:
                        self.send_mmc_response_data(cmd.Id, True)
                        world.cancel_timer(cmd.TimerKey)
                        # Reset Timer
                        cmd.TimerKey = world.set_timer(world.m_CmdResponseTimeOut, MMC_CMD_RESULT, cmd)
                    else:
                        self.send_mmc_response_data(cmd.Id)
                        world.cancel_timer(cmd.TimerKey)
                        self.m_ResCmdList.remove(cmd)
                else:
                    print("[IdentManager] [CORE_ERROR] Last Line Find Fail.........")
                    self.send_mmc_response_data(cmd.Id)
                    world.cancel_timer(cmd.TimerKey)
                    self.m_ResCmdList.remove(cmd)
                return True
        return False

    def ident_result(self, last_ident_name, final_ident_name, id_string):
        """
        C++: void IdentResult(...)
        """
        if not last_ident_name and not final_ident_name:
            print("[IdentManager] Ident Fail")
            # print line 1 for debug
        elif not last_ident_name:
            print(f"[IdentManager] Ident Success(Ident ID : [{final_ident_name}])")
            if self.m_CmdResultCheckFlag and self.m_ResCmdList:
                self.check_mmc_response_data(id_string, "")
                self.m_CmdResultCheckFlag = False
        elif not final_ident_name:
            print(f"[IdentManager] Ident Fail(Last Ident ID : [{last_ident_name}])")
            if self.m_CmdResultCheckFlag and self.m_ResCmdList:
                self.check_mmc_response_data(id_string, "")
                self.m_CmdResultCheckFlag = False