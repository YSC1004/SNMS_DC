import sys
import os
import threading
import time
import subprocess
from collections import deque

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.AsSocket import AsSocket
from Class.Common.CommType import *
from Class.Common.AsUtil import AsUtil
from Class.Util.FrTime import FrTime

# -------------------------------------------------------
# ServerConnection Class
# Active-Standby 서버 간 연결 및 DB 동기화 처리
# -------------------------------------------------------
class ServerConnection(AsSocket):
    # Sync Types
    ALL_DB_SYNC     = 120001
    ORB_DB_SYNC     = 120002
    ETC_DB_SYNC     = 120003
    UPDATE_DB_SYNC  = 120010
    TIMER_SYNC_ID   = 11000

    def __init__(self, conn_mgr=None):
        """
        C++: ServerConnection(ServerConnMgr* ConnMgr)
        """
        super().__init__()
        
        self.m_ServerConnMgr = conn_mgr
        self.m_ServerInfo = AsServerInfoT() # 구조체 초기화
        
        # DB Sync Thread 관련
        self.m_DbSyncThread = None
        self.m_TStatus = True
        self.m_DbSyncReqQueue = deque()
        self.m_DbSyncReqLock = threading.Lock()

        # 메시지 센서 초기화 (MainPtr 연동용)
        self.init_msg_sensor(None) # 자기 자신 혹은 World

    def __del__(self):
        """
        C++: ~ServerConnection()
        """
        self.m_TStatus = False
        if self.m_DbSyncThread and self.m_DbSyncThread.is_alive():
            self.m_DbSyncThread.join()
        super().__del__()

    # ---------------------------------------------------
    # Packet Handling (Virtual Override)
    # ---------------------------------------------------
    def receive_packet(self, packet, session_identify):
        """
        C++: void ReceivePacket(...)
        """
        msg_id = packet.msg_id
        
        if msg_id == AS_SERVER_INFO:
            info = AsServerInfoT.unpack(packet.msg_body)
            if info: self.recv_server_info(info)

        elif msg_id == AS_DB_SYNC_KIND:
            req = AsDbSyncKindT.unpack(packet.msg_body)
            if req: self.recv_db_sync_kind(req)

        elif msg_id == AS_DB_SYNC_INFO_LIST:
            info_list = AsDbSyncInfoListT.unpack(packet.msg_body)
            if info_list:
                from AsciiServerWorld import AsciiServerWorld
                AsciiServerWorld._instance.update_db_sync_time(info_list)

        else:
            print(f"[ServerConnection] Unknown MsgId : {msg_id}")

    # ---------------------------------------------------
    # Internal Logic
    # ---------------------------------------------------
    def recv_server_info(self, info):
        """
        Active 서버 정보를 수신하면 DB Sync 스레드 시작
        """
        self.m_ServerInfo = info # 값 복사
        
        print("[ServerConnection] Recv Active Server Info")
        print(f"   Server Name : {info.ServerName}")
        print(f"   Active DB USER : {info.ActDbUser}")
        
        if self.m_DbSyncThread is None:
            self.m_DbSyncThread = threading.Thread(target=self.db_sync_thread, daemon=True)
            self.m_DbSyncThread.start()
            print("[ServerConnection] Thread Create Success For Db Sync")
            
            self.add_db_sync_kind(self.ALL_DB_SYNC)
            
            # 타이머 설정 (매 정시 동기화 등)
            cur_time = FrTime()
            remain = cur_time.get_remain_hour_sec()
            self.set_timer(remain if remain else 3600, self.TIMER_SYNC_ID)

    def recv_db_sync_kind(self, kind_obj):
        self.add_db_sync_kind(kind_obj.SyncKind)

    def add_db_sync_kind(self, kind):
        with self.m_DbSyncReqLock:
            if kind not in self.m_DbSyncReqQueue:
                self.m_DbSyncReqQueue.append(kind)

    def get_db_sync_kind(self):
        with self.m_DbSyncReqLock:
            if self.m_DbSyncReqQueue:
                return self.m_DbSyncReqQueue.popleft()
        return -1

    def db_sync_thread(self):
        """
        DB 동기화 처리 스레드
        """
        while self.m_TStatus:
            kind = self.get_db_sync_kind()
            if kind != -1:
                self.run_db_sync(kind)
            else:
                time.sleep(3)

    def run_db_sync(self, kind):
        """
        외부 유틸리티(DbSyncUtil)를 실행하여 DB 동기화 수행
        """
        sync_kind = UNDEFINDED_SYNC
        
        # Kind 매핑
        if kind == CMD_PARSING_RULE_DOWN: sync_kind = RULE_SYNC
        elif kind == CMD_MAPPING_RULE_DOWN: 
            self.send_message(CMD_MAPPING_RULE_DOWN)
            return
        elif kind in [CMD_COMMAND_RULE_DOWN, CMD_SCHEDULER_RULE_DOWN]: sync_kind = CMD_SYNC
        elif kind == DATAHANDLER_MODIFY: sync_kind = EVENTCONSUMER_SYNC
        elif kind == COMMAND_AUTHORITY_MODIFY: sync_kind = SESSIONIDENT_SYNC
        elif kind in [MANAGER_MODIFY, CONNECTOR_MODIFY, CONNECTION_MODIFY, CONNECTION_LIST_MODIFY]: sync_kind = JUNCTION_SYNC
        elif kind == self.ORB_DB_SYNC: sync_kind = ORB_SYNC
        elif kind == self.ETC_DB_SYNC: sync_kind = ETC_SYNC
        elif kind == self.ALL_DB_SYNC: sync_kind = ALL_SYNC
        
        if sync_kind == UNDEFINDED_SYNC: return

        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance

        # 명령어 구성 (DbSyncUtil 호출)
        # 예: ./DbSyncUtil -type 1 -actdbuser user ...
        cmd = (
            f"{world.get_proc_position()}DbSyncUtil {ARG_TYPES} {sync_kind} "
            f"{ARG_ACT_DB_USER} {self.m_ServerInfo.ActDbUser} "
            f"{ARG_ACT_DB_PASSWD} {self.m_ServerInfo.ActPasswd} "
            f"{ARG_ACT_DB_TNS} {self.m_ServerInfo.ActDbTns}"
        )
        
        print(f"\n[ServerConnection] CMD:[{cmd}]")
        
        # 실행
        ret = subprocess.call(cmd, shell=True)
        
        if ret == 0:
            print(f"[ServerConnection] DbSync({AsUtil.get_enum_type_string(sync_kind)}) success")
            # 성공 시 자기 자신에게 메시지 전송 (메인 스레드 처리용)
            # C++ SendMessage -> recv_message 호출
            if kind in [CMD_PARSING_RULE_DOWN, CMD_MAPPING_RULE_DOWN, self.ALL_DB_SYNC]:
                self.send_message(kind)
            
            self.send_message(self.UPDATE_DB_SYNC)
        else:
            print(f"[ServerConnection] DbSync({AsUtil.get_enum_type_string(sync_kind)}) fail")

    # ---------------------------------------------------
    # Message Sensor Logic (FrMsgSensor Wrapper)
    # ---------------------------------------------------
    def recv_message(self, message, info=None):
        """
        C++: void RecvMessage(int Message, void* AdditionInfo)
        """
        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        
        if message == CMD_PARSING_RULE_DOWN:
            world.cmd_parsing_rule_down()
        elif message == CMD_MAPPING_RULE_DOWN:
            world.cmd_mapping_rule_down()
        elif message == self.ALL_DB_SYNC:
            world.cmd_parsing_rule_down()
            world.cmd_mapping_rule_down()
        elif message == self.UPDATE_DB_SYNC:
            world.update_db_sync_time()

    # ---------------------------------------------------
    # Etc
    # ---------------------------------------------------
    def receive_time_out(self, reason, extra_reason):
        if reason == self.TIMER_SYNC_ID:
            self.add_db_sync_kind(self.ORB_DB_SYNC)
            self.add_db_sync_kind(self.ETC_DB_SYNC)
            
            cur_time = FrTime()
            remain = cur_time.get_remain_hour_sec()
            self.set_timer(remain if remain else 3600, self.TIMER_SYNC_ID)

    def close_socket(self, err):
        if self.m_ServerConnMgr:
            # Active Server로서 Standby 연결이 끊김
            self.m_ServerConnMgr.set_standby_server(None)
            self.m_ServerConnMgr.remove(self)
        else:
            # Standby Server로서 Active 연결이 끊김 -> Active로 승격
            from AsciiServerWorld import AsciiServerWorld
            AsciiServerWorld._instance.stand_by_server_run()

    def session_identify(self, session_type, session_name):
        from AsciiServerWorld import AsciiServerWorld
        world = AsciiServerWorld._instance
        
        print(f"[ServerConnection] Standby Server is running({session_name}, {self.get_peer_ip()})")
        
        if self.m_ServerConnMgr:
            self.m_ServerConnMgr.set_standby_server(self)
            
        # Active 서버 정보 전송
        info = AsServerInfoT()
        info.ServerName = world.get_proc_name()
        info.ActDbUser = world.m_DbUserId
        info.ActPasswd = world.m_DbPassword
        info.ActDbTns = world.m_DbTns
        
        self.packet_send(PacketT(AS_SERVER_INFO, len(info.pack()), info.pack()))