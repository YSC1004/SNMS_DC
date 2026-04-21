"""
ServerConnMgr.py / ServerConnection.py
C++ ServerConnMgr.h/.C + ServerConnection.h/.C → Python 변환

Active ↔ Standby 서버 간 연결 처리.

ServerConnMgr:
  - Standby 서버 접속 Accept
  - DB 동기화 종류 전송 (SendDbSyncKind)
  - Standby 서버 접속 여부 확인 (IsStandByServer)

ServerConnection:
  - Active/Standby 양방향 사용
    · Active 측: AcceptSocket으로 Standby 접속 수락
    · Standby 측: Connect로 Active에 접속 (AsciiServerWorld.InitStandbyServer)
  - DB 동기화 스레드 (DbSyncThread → threading.Thread)
  - DB 동기화 큐 (IntList → collections.deque + threading.Lock)
  - DbSyncUtil 실행 (subprocess)
  - RecvMessage: SendMessage(C++ frObject) → 직접 메서드 호출로 대체
"""

import asyncio
import logging
import subprocess
import threading
from collections import deque
from typing import Optional, TYPE_CHECKING

from Common.ConnectionMgr import ConnectionMgr          # add/remove (치트시트)
from Common.AsSocket import AsSocket                    # 가상함수 오버라이드 (치트시트)
from Common.AsUtil import AsUtil
from Common.CommTypeList import (
    AS_SERVER_INFO_T, AS_DB_SYNC_KIND_T, AS_DB_SYNC_INFO_LIST_T,
)
from Common.CommType import (
    ASCII_SERVER,
    AS_SERVER_INFO, AS_DB_SYNC_KIND, AS_DB_SYNC_INFO_LIST,
    CMD_PARSING_RULE_DOWN, CMD_MAPPING_RULE_DOWN,
    CMD_COMMAND_RULE_DOWN, CMD_SCHEDULER_RULE_DOWN,
    DATAHANDLER_MODIFY, COMMAND_AUTHORITY_MODIFY,
    MANAGER_MODIFY, CONNECTOR_MODIFY,
    CONNECTION_MODIFY, CONNECTION_LIST_MODIFY,
    ARG_TYPES,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# DB 동기화 내부 상수 (C++: #define)
ALL_DB_SYNC    = 120001
ORB_DB_SYNC    = 120002
ETC_DB_SYNC    = 120003
UPDATE_DB_SYNC = 120010

# DB 동기화 주기 타이머 이유값
DB_SYNC_TIMER_REASON = 11000

# SYNCDB_KIND enum 대응
class SyncDbKind:
    UNDEFINDED_SYNC    = 0
    RULE_SYNC          = 1
    CMD_SYNC           = 2
    EVENTCONSUMER_SYNC = 3
    SESSIONIDENT_SYNC  = 4
    JUNCTION_SYNC      = 5
    ORB_SYNC           = 6
    ETC_SYNC           = 7
    ALL_SYNC           = 8

# ARG 상수 (DbSyncUtil 인자)
ARG_ACT_DB_USER   = "-actdbuser"
ARG_ACT_DB_PASSWD = "-actdbpasswd"
ARG_ACT_DB_TNS    = "-actdbtns"


# =============================================================================
# ServerConnMgr
# =============================================================================

class ServerConnMgr(ConnectionMgr):
    """
    C++ ServerConnMgr (ConnectionMgr 상속) 대응.
    Active 서버에서 Standby 접속을 수락하는 리스너.
    """

    def __init__(self) -> None:
        super().__init__()
        self._standby_svr_conn: Optional["ServerConnection"] = None

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """C++: AcceptSocket()"""
        conn = ServerConnection(self)
        if not self.Accept(conn):
            logger.debug("Another Server Accept Error : %s",
                         self.GetObjErrMsg())
            return

        self.add(conn)                              # ConnectionMgr.add()
        logger.debug("Connection Another Server(%s)", conn.get_peer_ip())

    # =========================================================================
    # Standby 서버 관리
    # =========================================================================

    def SetStandByServer(self,
                          svr_conn: Optional["ServerConnection"]) -> None:
        """C++: SetStandByServer(ServerConnection* SvrConn)"""
        self._standby_svr_conn = svr_conn

    def IsStandByServer(self) -> bool:
        """C++: IsStandByServer() → Standby 접속 여부."""
        return self._standby_svr_conn is not None

    # =========================================================================
    # SendDbSyncKind
    # =========================================================================

    def SendDbSyncKind(self, kind: int) -> None:
        """C++: SendDbSyncKind(int Kind) — Standby 서버에 DB 동기화 종류 전송."""
        if self._standby_svr_conn:
            req = AS_DB_SYNC_KIND_T()
            req.SyncKind = kind
            payload = _pack(req)
            asyncio.ensure_future(
                self._standby_svr_conn.SendPacket(
                    AS_DB_SYNC_KIND, payload, len(payload)))
            logger.debug("Send to DbSyncReq : %d", kind)


# =============================================================================
# ServerConnection
# =============================================================================

class ServerConnection(AsSocket):
    """
    C++ ServerConnection (AsSocket 상속) 대응.

    Active 측: ServerConnMgr != None  → Standby 접속 수락 측
    Standby 측: ServerConnMgr == None → Active 서버에 접속한 측

    DB 동기화 스레드:
      C++: pthread_create → Python: threading.Thread (daemon)
      C++: frMutexGuard   → Python: threading.Lock (with 문)
      C++: SendMessage / RecvMessage (frObject IPC)
           → Python: 직접 메서드 호출로 대체
    """

    def __init__(self, conn_mgr: Optional[ServerConnMgr]) -> None:
        super().__init__()
        self._server_conn_mgr:  Optional[ServerConnMgr] = conn_mgr
        self._server_info:       AS_SERVER_INFO_T         = AS_SERVER_INFO_T()
        self._t_status:          bool                     = True
        self._db_sync_thread:    Optional[threading.Thread] = None

        # DB 동기화 요청 큐 (C++: IntList + frMutex)
        self._db_sync_req_queue: deque[int]   = deque()
        self._db_sync_req_lock:  threading.Lock = threading.Lock()

        # Standby 전용: DB 접속 정보
        self._db_user:   str = ""
        self._db_passwd: str = ""
        self._db_tns:    str = ""

        # C++: InitMsgSensor(MAINPTR) → Python에서 불필요 (직접 호출 방식)

    def __del__(self) -> None:
        if self._db_sync_thread and self._db_sync_thread.is_alive():
            self._t_status = False
            logger.debug("DbSyncThread join wait")
            self._db_sync_thread.join(timeout=5.0)
            logger.debug("DbSyncThread join %s",
                         "success" if not self._db_sync_thread.is_alive()
                         else "fail")

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)"""
        msg_id = packet.MsgId

        if msg_id == AS_SERVER_INFO:
            self._recv_server_info(packet.Msg)

        elif msg_id == AS_DB_SYNC_KIND:
            self._recv_db_sync_kind(packet.Msg)

        elif msg_id == AS_DB_SYNC_INFO_LIST:
            from ProcNaServer.AsciiServerWorld import MAINPTR
            MAINPTR().UpdateDbSyncTime(packet.Msg)

        else:
            logger.error("Unknown MsgId : %d", msg_id)

    def close_socket(self, errno_val: int) -> None:
        """
        C++: virtual CloseSocket(int Errno)

        Active 측 (m_ServerConnMgr != None):
          Standby 서버 접속 해제 처리.
        Standby 측 (m_ServerConnMgr == None):
          Active 서버 접속 끊김 → StandByServerRun().
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR

        if self._server_conn_mgr:
            # Active 측: Standby 접속 해제
            if self.GetSessionType() == ASCII_SERVER:
                session_name = self.GetSessionName()
                peer_ip = self.get_peer_ip()
                logger.debug("Standby Server Connection Broken(%s,%s)",
                             session_name, peer_ip)
                MAINPTR().SendAsciiError(
                    1, "Standby Server Connection Broken(%s,%s)",
                    session_name, peer_ip)
                self._server_conn_mgr.SetStandByServer(None)

            self._server_conn_mgr.remove(self)      # ConnectionMgr.remove()
        else:
            # Standby 측: Active 접속 끊김 → Standby가 Active로 승격
            MAINPTR().StandByServerRun()

    def session_identify_callback(self, session_type: int,
                                   session_name: str = "") -> None:
        """
        C++: virtual SessionIdentify(int SessionType, string SessionName)
        Standby 서버가 Active에 접속 식별 완료 시 호출.
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR

        logger.debug("Session Identify : Type(%s), SessionName(%s)",
                     AsUtil.GetProcessTypeString(session_type), session_name)

        if self._server_conn_mgr:
            self._server_conn_mgr.SetStandByServer(self)

        logger.debug("Now, Standby Server is running(%s,%s)",
                     session_name, self.get_peer_ip())
        MAINPTR().SendAsciiError(
            1, "Now, Standby Server is running(%s,%s)",
            session_name, self.get_peer_ip())

        # Active DB 정보를 Standby로 전송
        self._server_info.ServerName = MAINPTR().GetProcName()
        self._server_info.ActDbUser  = MAINPTR().GetDbUserId()
        self._server_info.ActPasswd  = MAINPTR().GetDbPasswd()
        self._server_info.ActDbTns   = MAINPTR().GetDbTns()

        payload = _pack(self._server_info)
        asyncio.ensure_future(
            self.SendPacket(AS_SERVER_INFO, payload, len(payload)))

    # =========================================================================
    # ReceiveTimeOut (AsWorld 가상함수 오버라이드)
    # =========================================================================

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """
        C++: ReceiveTimeOut(int Reason, void* ExtraReason)
        11000: 매 시간 DB 동기화 예약.
        """
        if reason == DB_SYNC_TIMER_REASON:
            self.AddDbSyncKind(ORB_DB_SYNC)
            self.AddDbSyncKind(ETC_DB_SYNC)
            # 다음 정각까지 남은 초 계산
            remain = self._get_remain_hour_sec()
            self.SetTimer(remain if remain else 3600, DB_SYNC_TIMER_REASON)

    # =========================================================================
    # DB 동기화 큐
    # =========================================================================

    def GetDbSyncKind(self) -> int:
        """C++: GetDbSyncKind() — 큐 앞에서 꺼냄. 없으면 -1."""
        with self._db_sync_req_lock:                # C++: frMutexGuard
            if self._db_sync_req_queue:
                return self._db_sync_req_queue.popleft()
        return -1

    def AddDbSyncKind(self, kind: int) -> None:
        """C++: AddDbSyncKind(int Kind) — 중복 없이 큐에 추가."""
        with self._db_sync_req_lock:                # C++: frMutexGuard
            if kind not in self._db_sync_req_queue:
                self._db_sync_req_queue.append(kind)

    # =========================================================================
    # 패킷 처리 내부
    # =========================================================================

    def _recv_server_info(self, info: AS_SERVER_INFO_T) -> None:
        """C++: RecvServerInfo(AS_SERVER_INFO_T*)"""
        self._server_info = info

        logger.debug("Recv Active Server Info")
        logger.debug("Server Name : %s", info.ServerName)
        logger.debug("Active DB USER : %s", info.ActDbUser)
        logger.debug("Active DB PASSWD : %s", info.ActPasswd)
        logger.debug("Active DB TNS : %s", info.ActDbTns)

        # DB 동기화 스레드 최초 1회만 생성
        if self._db_sync_thread is None:
            self._db_sync_thread = threading.Thread(
                target=self._db_sync_thread_func,
                name="DbSyncThread",
                daemon=True,
            )
            self._db_sync_thread.start()
            logger.info("Thread Create Success For Db Sync")

            self.AddDbSyncKind(ALL_DB_SYNC)
            remain = self._get_remain_hour_sec()
            self.SetTimer(remain if remain else 3600,
                          DB_SYNC_TIMER_REASON)     # AsWorld.SetTimer

    def _recv_db_sync_kind(self, kind: AS_DB_SYNC_KIND_T) -> None:
        """C++: RecvDbSyncKind(AS_DB_SYNC_KIND_T*)"""
        self.AddDbSyncKind(kind.SyncKind)

    # =========================================================================
    # DB 동기화 스레드
    # =========================================================================

    def _db_sync_thread_func(self) -> None:
        """
        C++: DbSyncThread(void* Arg) — pthread 대응.
        DB 동기화 큐를 소비하며 RunDbSync 실행.
        """
        import time
        while self._t_status:
            kind = self.GetDbSyncKind()
            if kind != -1:
                self._run_db_sync(kind)
            else:
                time.sleep(3)                       # C++: frUtilMisc::Sleep(3)

    def _run_db_sync(self, kind: int) -> None:
        """
        C++: RunDbSync(int Kind)
        DbSyncUtil 외부 프로세스 실행 후 결과에 따라 RecvMessage 호출.
        C++: SendMessage/RecvMessage(frObject IPC) → Python: 직접 메서드 호출
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR

        # kind → syncKind 매핑
        sync_map = {
            CMD_PARSING_RULE_DOWN:  SyncDbKind.RULE_SYNC,
            CMD_COMMAND_RULE_DOWN:  SyncDbKind.CMD_SYNC,
            CMD_SCHEDULER_RULE_DOWN: SyncDbKind.CMD_SYNC,
            DATAHANDLER_MODIFY:     SyncDbKind.EVENTCONSUMER_SYNC,
            COMMAND_AUTHORITY_MODIFY: SyncDbKind.SESSIONIDENT_SYNC,
            MANAGER_MODIFY:         SyncDbKind.JUNCTION_SYNC,
            CONNECTOR_MODIFY:       SyncDbKind.JUNCTION_SYNC,
            CONNECTION_MODIFY:      SyncDbKind.JUNCTION_SYNC,
            CONNECTION_LIST_MODIFY: SyncDbKind.JUNCTION_SYNC,
            ORB_DB_SYNC:            SyncDbKind.ORB_SYNC,
            ETC_DB_SYNC:            SyncDbKind.ETC_SYNC,
            ALL_DB_SYNC:            SyncDbKind.ALL_SYNC,
        }

        # CMD_MAPPING_RULE_DOWN: RunDbSync 없이 바로 RecvMessage
        if kind == CMD_MAPPING_RULE_DOWN:
            self._recv_message(CMD_MAPPING_RULE_DOWN)
            return

        sync_kind = sync_map.get(kind, SyncDbKind.UNDEFINDED_SYNC)
        if sync_kind == SyncDbKind.UNDEFINDED_SYNC:
            return

        cmd = (
            f"{MAINPTR().GetProcPosition()}DbSyncUtil "
            f"{ARG_TYPES} {sync_kind} "
            f"{ARG_ACT_DB_USER} {self._server_info.ActDbUser} "
            f"{ARG_ACT_DB_PASSWD} {self._server_info.ActPasswd} "
            f"{ARG_ACT_DB_TNS} {self._server_info.ActDbTns}"
        )
        logger.debug("\nCMD:[%s]", cmd)

        ret = subprocess.call(cmd, shell=True)

        if ret == 0:
            # 성공 시 rule down 관련 kind는 RecvMessage 호출
            if kind in (CMD_PARSING_RULE_DOWN, CMD_MAPPING_RULE_DOWN,
                        CMD_COMMAND_RULE_DOWN, CMD_SCHEDULER_RULE_DOWN,
                        ALL_DB_SYNC):
                self._recv_message(kind)

            self._recv_message(UPDATE_DB_SYNC)
            logger.debug("DbSync(%d) success", sync_kind)
        else:
            logger.error("DbSync(%d) fail", sync_kind)

    def _recv_message(self, message: int) -> None:
        """
        C++: RecvMessage(int Message, void* AdditionInfo)
        frObject::SendMessage / RecvMessage IPC
        → Python: asyncio.ensure_future로 메인 루프에 위임
        """
        from ProcNaServer.AsciiServerWorld import MAINPTR

        # 스레드 컨텍스트에서 asyncio 이벤트루프에 안전하게 예약
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            return

        if message == CMD_PARSING_RULE_DOWN:
            loop.call_soon_threadsafe(MAINPTR().CmdParsingRuleDown)

        elif message == CMD_MAPPING_RULE_DOWN:
            loop.call_soon_threadsafe(MAINPTR().CmdMappingRuleDown)

        elif message == ALL_DB_SYNC:
            loop.call_soon_threadsafe(MAINPTR().CmdParsingRuleDown)
            loop.call_soon_threadsafe(MAINPTR().CmdMappingRuleDown)

        elif message == UPDATE_DB_SYNC:
            loop.call_soon_threadsafe(MAINPTR().UpdateDbSyncTime)

    # =========================================================================
    # 내부 헬퍼
    # =========================================================================

    @staticmethod
    def _get_remain_hour_sec() -> int:
        """C++: frTime::GetRemainHourSec() — 다음 정각까지 남은 초."""
        import datetime
        now = datetime.datetime.now()
        next_hour = now.replace(minute=0, second=0, microsecond=0) + \
                    datetime.timedelta(hours=1)
        return max(int((next_hour - now).total_seconds()), 0)


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''