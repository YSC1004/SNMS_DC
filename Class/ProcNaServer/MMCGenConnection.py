import sys
import os

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

class MMCGenConnection(AsSocket):
    """
    Handles connections for MMC related processes:
    - ASCII_MMC_GENERATOR
    - ASCII_MMC_SCHEDULER
    - ASCII_JOB_MONITOR
    """
    def __init__(self, conn_mgr):
        """
        C++: MMCGenConnection(MMCGeneratorConnMgr* ConMgr)
        """
        super().__init__()
        self.m_MMCGeneratorConnMgr = conn_mgr
        self.m_MMCProcStatus = True
        self.m_MMCRequestQueue = None # Populated in SessionIdentify

    def __del__(self):
        """
        C++: ~MMCGenConnection()
        """
        if self.get_session_type() != NOT_ASSIGN:
            # Note: set_mmc_generator_session checks if conn_mgr exists
            if self.m_MMCGeneratorConnMgr:
                self.m_MMCGeneratorConnMgr.set_mmc_generator_session(self.get_session_type(), None)
        super().__del__()

    def receive_packet(self, packet, session_identify):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        if session_identify == ASCII_MMC_SCHEDULER:
            self.mmc_sch_proc_req(packet)
            
        elif session_identify == ASCII_MMC_GENERATOR:
            self.mmc_gen_proc_req(packet)
            
        elif session_identify == ASCII_JOB_MONITOR:
            self.job_monitor_req(packet)
            
        else:
            print(f"[MMCGenConnection] UnKnown Session : {session_identify}")

    def session_identify(self, session_type, session_name):
        """
        C++: void SessionIdentify(int SessionType, string SessionName)
        """
        print(f"[MMCGenConnection] Session Identify : Type({AsUtil.get_process_type_string(session_type)}), SessionName({session_name})")

        if not self.m_MMCGeneratorConnMgr.add_session_name(session_name):
            self.close()
            self.m_MMCGeneratorConnMgr.remove(self)
            return

        self.m_MMCGeneratorConnMgr.set_mmc_generator_session(session_type, self)

        if session_type == ASCII_JOB_MONITOR or session_type == ASCII_MMC_SCHEDULER:
            from Server.AsciiServerWorld import AsciiServerWorld
            # Register to World and get the Queue reference
            self.m_MMCRequestQueue = AsciiServerWorld._instance.register_mmc_req_conn(self, 100000)

        self.m_MMCGeneratorConnMgr.send_process_info(session_name, session_type, START)
        
        # Start Alive Check
        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        self.start_alive_check(world.get_proc_alive_check_time(), world.get_alive_check_limit_cnt())

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        """
        print(f"[MMCGenConnection] Socket Broken : {self.get_session_name()}")

        # Create Log Status for disconnection
        log_status = AsLogStatusT()
        log_status.name = self.get_session_name()
        log_status.status = LOG_DEL
        log_status.logs = f"sUn,{AsUtil.get_process_type_string(self.get_session_type())},{self.get_session_name()},"

        self.m_MMCGeneratorConnMgr.update_mmc_process_log_status(log_status)

        if self.m_MMCProcStatus:
            self.m_MMCGeneratorConnMgr.child_process_dead(self)
        else:
            self.m_MMCGeneratorConnMgr.child_process_dead(self, ORDER_KILL)

    def receive_time_out(self, reason, extra_reason=None):
        """
        C++: void ReceiveTimeOut(int Reason, void* ExtraReason)
        """
        print(f"[MMCGenConnection] Unknown Time Out Reason : {reason}")

    def alive_check_fail(self, fail_count):
        """
        C++: void AliveCheckFail(int FailCount)
        """
        print(f"[MMCGenConnection] AliveCheckFail({self.get_session_name()}) , Count : {fail_count}")
        
        from Server.AsciiServerWorld import AsciiServerWorld
        msg = f"The Process is killed on purpose for no reply from {self.get_session_name()}."
        AsciiServerWorld._instance.send_ascii_error(1, msg)
        
        self.m_MMCGeneratorConnMgr.various_ack_check_time_out(self)

    # -----------------------------------------------------------
    # Request Handlers by Session Type
    # -----------------------------------------------------------

    def mmc_sch_proc_req(self, packet):
        """
        C++: void MMCSchProcReq(PACKET_T* Packet)
        """
        msg_id = packet.msg_id
        
        if msg_id == PROC_INIT_END:
            pass # No action in C++

        elif msg_id == AS_MMC_REQ:
            req = AsMmcRequestT.unpack(packet.msg_body)
            if req: self.receive_mmc_req_from_sch(req)

        elif msg_id == AS_LOG_INFO:
            status = AsLogStatusT.unpack(packet.msg_body)
            if status: self.receive_log_info(status)

        elif msg_id == ASCII_ERROR_MSG:
            error = AsAsciiErrorMsgT.unpack(packet.msg_body)
            if error:
                error.ProcessId = self.get_session_name()
                from Server.AsciiServerWorld import AsciiServerWorld
                # Assuming send_ascii_error handles the object logging
                AsciiServerWorld._instance.write_error_log(error) 

        elif msg_id == CMD_SCHEDULER_RULE_DOWN_ACK:
            ack = AsAsciiAckT.unpack(packet.msg_body)
            if ack:
                from Server.AsciiServerWorld import AsciiServerWorld
                # World needs to have this method or delegate to GuiConnMgr
                if hasattr(AsciiServerWorld._instance.m_GuiConnMgr, 'recv_scheduler_rule_down_result'):
                    AsciiServerWorld._instance.m_GuiConnMgr.recv_scheduler_rule_down_result(ack)

        else:
            print(f"[MMCGenConnection] Unknown Msg Id : {msg_id}")

    def mmc_gen_proc_req(self, packet):
        """
        C++: void MMCGenProcReq(PACKET_T* Packet)
        """
        msg_id = packet.msg_id
        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        if msg_id == PROC_INIT_END:
            world.notify_event(ASCII_MMC_GENERATOR, msg_id)

        elif msg_id == MMC_GEN_RES:
            res = AsMmcGenResultT.unpack(packet.msg_body)
            if res: self.mmc_res_from_mmc_gen(res)

        elif msg_id == AS_LOG_INFO:
            status = AsLogStatusT.unpack(packet.msg_body)
            if status: self.receive_log_info(status)

        elif msg_id == ASCII_ERROR_MSG:
            error = AsAsciiErrorMsgT.unpack(packet.msg_body)
            if error:
                error.ProcessId = self.get_session_name()
                world.write_error_log(error)

        elif msg_id == CMD_COMMAND_RULE_DOWN_ACK:
            ack = AsAsciiAckT.unpack(packet.msg_body)
            if ack:
                if hasattr(world.m_GuiConnMgr, 'recv_command_rule_down_result'):
                    world.m_GuiConnMgr.recv_command_rule_down_result(ack)

        else:
            print(f"[MMCGenConnection] Unknown Msg Id : {msg_id}")

    def job_monitor_req(self, packet):
        """
        C++: void JobMonitorReq(PACKET_T* Packet)
        """
        msg_id = packet.msg_id

        if msg_id == PROC_INIT_END:
            pass

        elif msg_id == AS_MMC_REQ:
            req = AsMmcRequestT.unpack(packet.msg_body)
            if req: self.receive_mmc_req_from_job(req)

        elif msg_id == AS_LOG_INFO:
            status = AsLogStatusT.unpack(packet.msg_body)
            if status: self.receive_log_info(status)

        elif msg_id == ASCII_ERROR_MSG:
            error = AsAsciiErrorMsgT.unpack(packet.msg_body)
            if error:
                error.ProcessId = self.get_session_name()
                from Server.AsciiServerWorld import AsciiServerWorld
                AsciiServerWorld._instance.write_error_log(error)

        else:
            print(f"[MMCGenConnection] Unknown Msg Id : {msg_id}")

    # -----------------------------------------------------------
    # Logic Methods
    # -----------------------------------------------------------

    def receive_mmc_req_from_sch(self, mmc_req):
        """
        C++: void ReceiveMMCReqFromSch(AS_MMC_REQUEST_T* MMCReq)
        """
        mmc_req.priority = 2
        mmc_req.logMode = 0
        # Debug Log
        # print(f"Receive MMCReq From MMCSch : ne({mmc_req.ne}), mmc({mmc_req.mmc}), type({mmc_req.type}), referenceId({mmc_req.referenceId})")
        
        if self.m_MMCRequestQueue:
            self.m_MMCRequestQueue.insert_mmc_request(mmc_req)

    def receive_mmc_req_from_job(self, mmc_req):
        """
        C++: void ReceiveMMCReqFromJob(AS_MMC_REQUEST_T* MMCReq)
        """
        # Debug Log
        # print(f"Receive MMCReq From JobMonitor : ne({mmc_req.ne}), mmc({mmc_req.mmc})")
        
        if self.m_MMCRequestQueue:
            self.m_MMCRequestQueue.insert_mmc_request(mmc_req)

    def send_mmc_req_to_mmc_gen(self, mmc_req):
        """
        C++: bool SendMMCReqToMMCGen(AS_MMC_REQUEST_T* MMCReq)
        """
        # Debug Log
        # print(f"Send MMCReq to MMCGen : ne({mmc_req.ne}), mmc({mmc_req.mmc})")
        body = mmc_req.pack()
        return self.packet_send(PacketT(MMC_GEN_REQ, len(body), body))

    def mmc_res_from_mmc_gen(self, result):
        """
        C++: void MMCResFromMMCGen(AS_MMC_GEN_RESULT_T* Result)
        """
        # Debug Log
        # print(f"Recv Command Gen Size : {result.commandNo}")
        from Server.AsciiServerWorld import AsciiServerWorld
        # Note: In C++, MAINPTR->MMCResFromMMCGen(Result) is called.
        # Ensure AsciiServerWorld has this method.
        AsciiServerWorld._instance.mmc_res_from_mmc_gen(result)

    def receive_log_info(self, status):
        """
        C++: void ReceiveLogInfo(AS_LOG_STATUS_T* Status)
        """
        self.m_MMCGeneratorConnMgr.update_mmc_process_log_status(status)

    def send_flow_control(self, msg_id):
        """
        C++: bool SendFlowControl(int MsgId)
        """
        print("[MMCGenConnection] virtual Call MMCGenConnection SendFlowControl")
        return True

    def send_mmc_log(self, mmc_log):
        """
        C++: bool SendMMCLog(AS_MMC_LOG_T* MMCLog)
        """
        body = mmc_log.pack()
        return self.packet_send(PacketT(MMC_LOG, len(body), body))