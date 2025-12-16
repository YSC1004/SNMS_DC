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
from Class.Common.AsciiMmcType import *
from Class.Common.AsUtil import AsUtil

class ExternalConnection(AsSocket):
    """
    Handles connections from External Systems (sending MMC commands).
    Inherits from AsSocket.
    """
    def __init__(self, conn_mgr):
        """
        C++: ExternalConnection(ExternalConnMgr* ConnMgr)
        """
        super().__init__()
        self.m_ExtConnMgr = conn_mgr
        self.m_IdentFlag = False
        self.m_FaultCnt = 0
        self.m_CommandAuthorityInfo = AsCommandAuthorityInfoT()
        self.m_SessionStatus = False
        self.m_MMCRequestQueue = None

    def __del__(self):
        """
        C++: ~ExternalConnection()
        """
        super().__del__()

    def receive_packet(self, packet, session_identify=0):
        """
        C++: void ReceivePacket(PACKET_T* Packet, const int SessionIdentify)
        """
        msg_id = packet.msg_id

        if msg_id == AS_MMC_REQ_OLD:
            req_old = AsMmcRequestOldT.unpack(packet.msg_body)
            if req_old:
                self.receive_mmc_req_old(req_old)

        elif msg_id == AS_MMC_REQ:
            req = AsMmcRequestT.unpack(packet.msg_body)
            if req:
                self.receive_mmc_req(req)

        elif msg_id == AS_MMC_IDENT_REQ:
            ident_req = AsMmcIdentReqT.unpack(packet.msg_body)
            if ident_req:
                self.receive_mmc_ident_req(ident_req)

        else:
            print(f"[ExternalConnection] Unknown MsgId : {msg_id}")
            print(f"[ExternalConnection] so now disconnecting.........")
            self.close_socket(1)

    def receive_mmc_req_old(self, mmc_req_old):
        """
        C++: void ReceiveMMCReq(AS_MMC_REQUEST_OLD_T* MMCReq)
        """
        req_new = AsMmcRequestT()
        AsUtil.convert_mmc_old_to_new(mmc_req_old, req_new)
        self.receive_mmc_req(req_new)

    def check_req(self, mmc_req):
        """
        C++: bool CheckReq(AS_MMC_REQUEST_T* MmcReq)
        Truncates string fields to ensure they fit within buffer limits.
        """
        # Ensure imports include length constants like EQUIP_ID_LEN
        if len(mmc_req.ne) > EQUIP_ID_LEN - 1:
            mmc_req.ne = mmc_req.ne[:EQUIP_ID_LEN - 1]

        if len(mmc_req.mmc) > MMC_CMD_LEN_EX - 1:
            mmc_req.mmc = mmc_req.mmc[:MMC_CMD_LEN_EX - 1]

        if len(mmc_req.userid) > USER_ID_LEN - 1:
            mmc_req.userid = mmc_req.userid[:USER_ID_LEN - 1]

        if len(mmc_req.display) > IP_ADDRESS_LEN - 1:
            mmc_req.display = mmc_req.display[:IP_ADDRESS_LEN - 1]

        return True

    def receive_mmc_req(self, mmc_req):
        """
        C++: void ReceiveMMCReq(AS_MMC_REQUEST_T* MMCReq)
        """
        if self.m_SessionStatus:
            # Set attributes from Authority Info
            mmc_req.priority = self.m_CommandAuthorityInfo.Priority
            mmc_req.logMode = self.m_CommandAuthorityInfo.LogMode
            
            # Set Display IP
            mmc_req.display = self.get_peer_ip()

            # Check and truncate lengths
            self.check_req(mmc_req)

            # Insert into Queue
            # In C++: m_MMCRequestQueue->InsertMMCRequest(MMCReq)
            # Python queue implies successful insertion usually, unless full.
            # Assuming insert_mmc_request returns True on success.
            if self.m_MMCRequestQueue and self.m_MMCRequestQueue.insert_mmc_request(mmc_req):
                # Debug Log
                # print(f"Recevie MMC External Command From {self.get_session_name()}({self.get_peer_ip()}) : ...")
                
                self.m_FaultCnt = 0

                if self.m_CommandAuthorityInfo.AckMode:
                    req_res = AsMmcAckT()
                    req_res.id = mmc_req.id
                    req_res.resultMode = 1 # Success
                    
                    body = req_res.pack()
                    self.packet_send(PacketT(AS_MMC_REQ_ACK, len(body), body))
                    # print(f"Send Cmd Req Ack(extid:{req_res.id})")

            else:
                # Queue Insert Failed
                self.m_FaultCnt += 1
                
                if self.m_CommandAuthorityInfo.AckMode:
                    req_res = AsMmcAckT()
                    req_res.id = mmc_req.id
                    req_res.resultMode = 0 # Fail
                    
                    body = req_res.pack()
                    self.packet_send(PacketT(AS_MMC_REQ_ACK, len(body), body))
                    # print(f"Send Cmd Req Ack(extid:{req_res.id})")

                if self.m_FaultCnt > 200:
                    print(f"[ExternalConnection] Insert Queue Fail Count Over({self.get_session_name()})")
                    self.close()
                    if self.m_ExtConnMgr:
                        self.m_ExtConnMgr.remove(self)

        else:
            print("[ExternalConnection] Illegal Command of Not Ident Connection")

    def close_socket(self, errno_val=0):
        """
        C++: void CloseSocket(int Errno)
        """
        print(f"[ExternalConnection] External connection close ({self.get_session_name()},{self.get_peer_ip()})")
        if self.m_ExtConnMgr:
            self.m_ExtConnMgr.remove(self)

    def receive_mmc_ident_req(self, ident_req):
        """
        C++: void ReceiveMMCIdentReq(AS_MMC_IDENT_REQ_T* IdentReq)
        """
        if self.m_IdentFlag:
            return

        ident_res = AsMmcIdentResT()
        # Initialize resultMode to 0 (Fail) by default if necessary, or handled in logic

        from Server.AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        # 1. Authenticate / Identify
        result = world.ident_mmc_request_session(ident_req, self.m_CommandAuthorityInfo)

        if result:
            self.m_SessionStatus = True
            ident_res.resultMode = 1 # Success

            print(f"[ExternalConnection] External Session Ident Ok : {ident_req.name}({self.get_peer_ip()}), "
                  f"priority({self.m_CommandAuthorityInfo.Priority}), logmode({self.m_CommandAuthorityInfo.LogMode}), "
                  f"maxqueuesize({self.m_CommandAuthorityInfo.MaxCmdQueue}), ackmode({self.m_CommandAuthorityInfo.AckMode})")

            # 2. Register Queue
            self.m_MMCRequestQueue = world.register_mmc_req_conn(self, self.m_CommandAuthorityInfo.MaxCmdQueue)
            
            if self.m_MMCRequestQueue is None:
                print("[ExternalConnection] [CORE_ERROR] Error Get MMCRequest Queue")
                # Need to handle failure scenario here? C++ code just logs and continues potentially in a broken state,
                # but let's assume valid queue for now.

            self.set_session_name(ident_req.name)

            # 3. Check Session Count Limit
            cur_session_cnt = self.m_ExtConnMgr.get_cur_session_cnt(ident_req.name)

            if self.m_CommandAuthorityInfo.MaxSessionCnt > 0 and cur_session_cnt > self.m_CommandAuthorityInfo.MaxSessionCnt:
                self.m_SessionStatus = False
                ident_res.resultMode = 0
                ident_res.result = f"Exceed max session : max({self.m_CommandAuthorityInfo.MaxSessionCnt} ea)"
                
                print(f"[ExternalConnection] ### Exceed max session : ID[{ident_req.name}], max({self.m_CommandAuthorityInfo.MaxSessionCnt} ea)")
                print("[ExternalConnection] External Session Close")

            if self.m_SessionStatus:
                world.session_cfg(self, SESSION_TYPE_MMC)

        else:
            # Identification Failed
            self.m_SessionStatus = False
            ident_res.resultMode = 0
            ident_res.result = "Unregistered ID"
            print(f"[ExternalConnection] External Session Ident not ok : {ident_req.name}")
            print("[ExternalConnection] External Session Close")

        self.m_IdentFlag = True
        
        # 4. Send Response
        body = ident_res.pack()
        if not self.packet_send(PacketT(AS_MMC_IDENT_RES, len(body), body)):
            print(f"[ExternalConnection] Socket Broken : {self.get_peer_ip()}")
            self.close()
            self.m_ExtConnMgr.remove(self)
            return

        # 5. Close if Failed
        if not self.m_SessionStatus:
            self.close()
            self.m_ExtConnMgr.remove(self)

    def send_mmc_result(self, result):
        """
        C++: bool SendMMCResult(AS_MMC_RESULT_T* Result)
        """
        body = result.pack()
        return self.packet_send(PacketT(AS_MMC_RES, len(body), body))