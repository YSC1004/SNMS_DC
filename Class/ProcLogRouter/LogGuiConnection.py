import sys
import os
import copy
from datetime import datetime

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.AsSocket import AsSocket
from Class.Common.CommType import *
from Class.Common.AsUtil import AsUtil
from Class.ProcLogRouter.LogFileHandler import LogFileHandler

class LogGuiConnection(AsSocket):
    """
    Handles connection with LogGui Client.
    Processes TAIL_LOG_DATA_REQ and streams log file content.
    """
    
    # Constants
    TIMER_LOG_ROTATE_CHECK = 33333

    def __init__(self, conn_mgr):
        """
        C++: LogGuiConnection(LogGuiConnMgr* ConnMgr)
        """
        super().__init__()
        self.m_LogGuiConnMgr = conn_mgr
        self.m_LogFileHandler = None
        self.m_FirstAction = True
        self.m_TailReq = AsLogTailDataReqT()
        self.m_CurLogFileName = ""

    def __del__(self):
        """
        C++: ~LogGuiConnection()
        """
        if self.m_LogFileHandler:
            self.m_LogFileHandler.close()
        super().__del__()

    def receive_packet(self, packet, session_identify=0):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        if packet.msg_id == TAIL_LOG_DATA_REQ:
            req = AsLogTailDataReqT.unpack(packet.msg_body)
            if req:
                self.m_TailReq = copy.deepcopy(req) # Store request for re-use (rotation)
                self.request_log_data(req)
        else:
            print(f"[LogGuiConnection] Unknown MsgId : {packet.msg_id}")

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        """
        print(f"[LogGuiConnection] Log Gui Connection Broken({self.get_peer_ip()})")
        if self.m_LogFileHandler:
            self.m_LogFileHandler.close()
            self.m_LogFileHandler = None
        
        if self.m_LogGuiConnMgr:
            self.m_LogGuiConnMgr.remove(self)

    def request_log_data(self, req_data):
        """
        C++: void RequestLogData(AS_LOG_TAIL_DATA_REQ_T* ReqData)
        Determines the log file name and starts the LogFileHandler.
        """
        if self.m_FirstAction:
            if req_data.ProcessType == TAIL_RAW_DATA_REQ:
                print(f"[LogGuiConnection] LOG TAIL DATA Req ({req_data.ManagerId})(RAW MESSAGE)({req_data.ProcessId})")
            else:
                print(f"[LogGuiConnection] LOG TAIL DATA Req ({req_data.ManagerId})({AsUtil.get_process_type_string(req_data.ProcessType)})({req_data.ProcessId})({req_data.LogCycle})")

        file_name = self.get_log_file_name(req_data)

        if self.m_FirstAction:
            print(f"[LogGuiConnection] Result Filename : {file_name}")
            if file_name:
                self.m_CurLogFileName = file_name
        else:
            # Check for log rotation (file name change)
            if file_name and self.m_CurLogFileName != file_name:
                print(f"[LogGuiConnection] Result Filename : {file_name}")
                self.m_CurLogFileName = file_name
            else:
                return # No change, keep reading current file or wait

        # Restart handler for new file or first run
        if self.m_LogFileHandler:
            self.m_LogFileHandler.close()
            self.m_LogFileHandler = None

        res = AsLogTailDataResT()
        res.ProcessType = req_data.ProcessType
        res.ProcessId = req_data.ProcessId

        if not file_name:
            res.ResMode = 0
            res.Result = "Log File doesn't exist."
        else:
            res.ResMode = 1
            self.m_LogFileHandler = LogFileHandler(self)
            
            if not self.m_LogFileHandler.open_file(file_name):
                res.ResMode = 0
                res.Result = "File Open Error" # Simplify error msg
                self.m_LogFileHandler = None
            else:
                res.Result = file_name

        if self.m_FirstAction:
            body = res.pack()
            self.packet_send(PacketT(TAIL_LOG_DATA_RES, len(body), body))
            self.m_FirstAction = False
            
            # Timer logic for log rotation check
            now = datetime.now()
            interval = 60 * 5
            if req_data.LogCycle == 1 or req_data.ProcessType == TAIL_RAW_DATA_REQ:
                if now.minute > 55: interval = 20
            else:
                if now.hour > 22 and now.minute > 55: interval = 20
                
            self.set_timer(interval, self.TIMER_LOG_ROTATE_CHECK)

        if self.m_LogFileHandler:
            self.m_LogFileHandler.run()

    def send_log_data(self, log_data):
        """
        C++: void SendLogData(char* Log)
        """
        log_packet = AsLogTailDataT()
        # Ensure data is string/bytes depending on struct definition
        # log_data comes from file read (bytes in Python usually)
        log_packet.TailData = log_data 
        
        body = log_packet.pack()
        self.packet_send(PacketT(TAIL_LOG_DATA, len(body), body))

    def get_log_file_name(self, req_data):
        """
        C++: string GetLogFileName(AS_LOG_TAIL_DATA_REQ_T* ReqData)
        Constructs the log file path based on process type, ID, date/time.
        """
        from LogRouterWorld import LogRouterWorld
        world = LogRouterWorld.get_instance()
        
        now = datetime.now()
        name_buf = ""

        # Determine Process Name/ID string
        if req_data.ProcessType == ASCII_SERVER:
            name_buf = world.env_value(ASCII_SERVER, "name")
        elif req_data.ProcessType in [ASCII_MANAGER, ASCII_PARSER, ASCII_CONNECTOR]:
            name_buf = f"{AsUtil.get_process_type_string(req_data.ProcessType)}_{req_data.ProcessId}"
        elif req_data.ProcessType == ASCII_DATA_ROUTER:
            name_buf = req_data.ProcessId
        elif req_data.ProcessType in [ASCII_MMC_GENERATOR, ASCII_MMC_SCHEDULER, ASCII_JOB_MONITOR, 
                                      ASCII_RULE_DOWNLOADER, ASCII_ROUTER, ASCII_LOG_ROUTER]:
            name_buf = AsUtil.get_process_type_string(req_data.ProcessType) # Or World helper
        elif req_data.ProcessType == TAIL_RAW_DATA_REQ:
            name_buf = req_data.ProcessId
        else:
            return "" # ASCII_DATA_HANDLER or unknown

        # Construct Filename
        file_path_suffix = ""
        
        if req_data.ProcessType == TAIL_RAW_DATA_REQ:
            # Format: /YYYYMMDD/Name_YYYYMMDDHH.msg
            file_path_suffix = f"/{now.strftime('%Y%m%d')}/{name_buf}_{now.strftime('%Y%m%d%H')}.msg"
            
            # Base Dir Logic
            base_dir = world.get_raw_dir()
            host_name = AsUtil.get_host_name()
            # C++: GetRawDir() + "/" + HostName + "/" + ProcessId + suffix
            full_path = f"{base_dir}/{host_name}/{req_data.ProcessId}{file_path_suffix}"
            
        else:
            # Format: /Name_YYYYMMDDHH.log (Hourly) or /Name_YYYYMMDD.log (Daily)
            if req_data.LogCycle == 1:
                file_path_suffix = f"/{name_buf}_{now.strftime('%Y%m%d%H')}.log"
            else:
                file_path_suffix = f"/{name_buf}_{now.strftime('%Y%m%d')}.log"
                
            base_dir = world.get_log_dir()
            full_path = f"{base_dir}{file_path_suffix}"

        if self.m_FirstAction:
            print(f"[LogGuiConnection] file Name : {full_path}")

        # Check existence
        if os.path.exists(full_path):
            return full_path
        else:
            return ""

    def receive_time_out(self, reason, extra_reason=None):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        Timer triggered to check for log rotation.
        """
        # Re-evaluate log file name and switch if needed
        self.request_log_data(self.m_TailReq)

        # Reset timer
        now = datetime.now()
        interval = 60 * 5
        if self.m_TailReq.LogCycle == 1 or self.m_TailReq.ProcessType == TAIL_RAW_DATA_REQ:
            if now.minute > 55: interval = 20
        else:
            if now.hour > 22 and now.minute > 55: interval = 20
            
        self.set_timer(interval, self.TIMER_LOG_ROTATE_CHECK)