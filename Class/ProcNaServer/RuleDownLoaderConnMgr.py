"""
RuleDownLoaderConnMgr.py
C++ RuleDownLoaderConnMgr.h/.C → Python 변환

RuleDownLoader 프로세스 연결 관리자.
  - ProcConnectionMgr 상속 (process_dead / start_proc)
  - 파싱/매핑 룰 다운 명령 전달
  - 룰 다운 ACK 수신 → AsciiServerWorld 전달
  - 프로세스/로그 상태 관리
"""

import asyncio
import copy
import logging
from typing import Optional, Dict, TYPE_CHECKING

from Common.ProcConnectionMgr import ProcConnectionMgr  # start_proc/process_dead (치트시트)
from Common.CommTypeList import (
    AS_LOG_STATUS_T, AS_PROCESS_STATUS_T, AS_ASCII_ACK_T,
)
from Common.CommType import (
    ASCII_RULE_DOWNLOADER,
    START, STOP, LOG_ADD, ORDER_KILL,
)

if TYPE_CHECKING:
    from ProcNaServer.RuleDownLoaderConnection import RuleDownLoaderConnection

logger = logging.getLogger(__name__)

LogStatusMap = Dict[str, AS_LOG_STATUS_T]


class RuleDownLoaderConnMgr(ProcConnectionMgr):
    """
    C++ RuleDownLoaderConnMgr (ProcConnectionMgr 상속) 대응.
    """

    def __init__(self) -> None:
        super().__init__()
        self._rule_down_loader_conn: Optional["RuleDownLoaderConnection"] = None
        self._log_status_map: LogStatusMap = {}

    def __del__(self) -> None:
        self._log_status_map.clear()

    # =========================================================================
    # ProcConnectionMgr 추상 메서드 구현
    # =========================================================================

    def process_dead(self, name: str, pid: int, status: int = -1) -> None:
        """
        C++: ProcessDead(string Name, int Pid, int Status)
        ProcConnectionMgr.child_process_dead() 에서 호출.
        """
        self.SendProcessInfo(name, STOP)

        if status != ORDER_KILL:
            self._rule_down_loader_conn = None
            from ProcNaServer.AsciiServerWorld import AsciiServerWorld
            AsciiServerWorld.m_WorldPtr.ProcessDead(name, pid)

    # =========================================================================
    # AcceptSocket
    # =========================================================================

    def AcceptSocket(self) -> None:
        """C++: AcceptSocket()"""
        from ProcNaServer.RuleDownLoaderConnection import RuleDownLoaderConnection

        conn = RuleDownLoaderConnection(self)
        if not self.Accept(conn):
            logger.debug("RuleDownLoaderConnMgr Socket Accept Error : %s",
                         self.GetObjErrMsg())
            return
        self.add(conn)                              # ConnectionMgr.add()

    # =========================================================================
    # StartProc (ProcConnectionMgr.start_proc 위임)
    # =========================================================================

    def StartProc(self, name: str, args: list) -> int:
        """C++: StartProc() → ProcConnectionMgr.start_proc() 위임."""
        return self.start_proc(name, args)          # ProcConnectionMgr.start_proc()

    # =========================================================================
    # Rule Down 명령 전달
    # =========================================================================

    def SendCmdParsingRuleDown(self) -> None:
        """C++: SendCmdParsingRuleDown() — RuleDownLoaderConnection으로 전달."""
        if self._rule_down_loader_conn:
            asyncio.ensure_future(
                self._rule_down_loader_conn.SendCmdParsingRuleDown())

    def SendCmdMappingRuleDown(self) -> None:
        """C++: SendCmdMappingRuleDown() — RuleDownLoaderConnection으로 전달."""
        if self._rule_down_loader_conn:
            asyncio.ensure_future(
                self._rule_down_loader_conn.SendCmdMappingRuleDown())

    # =========================================================================
    # 세션 포인터 설정
    # =========================================================================

    def SetRuleDownConn(self,
                         conn: Optional["RuleDownLoaderConnection"]) -> None:
        """C++: SetRuleDownConn(RuleDownLoaderConnection* Con)"""
        self._rule_down_loader_conn = conn

    # =========================================================================
    # ACK 수신 → AsciiServerWorld 전달
    # =========================================================================

    def RecvRuleDownAck(self, ack: AS_ASCII_ACK_T) -> None:
        """C++: RecvRuleDownAck(AS_ASCII_ACK_T*) → RecvParsingRuleDownResult."""
        from ProcNaServer.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld.m_WorldPtr.RecvParsingRuleDownResult(ack)

    def RecvMappingRuleDownAck(self, ack: AS_ASCII_ACK_T) -> None:
        """C++: RecvMappingRuleDownAck(AS_ASCII_ACK_T*) → RecvMappingRuleDownResult."""
        from ProcNaServer.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld.m_WorldPtr.RecvMappingRuleDownResult(ack)

    # =========================================================================
    # SendProcessInfo
    # =========================================================================

    def SendProcessInfo(self, session_name: str, status: int) -> None:
        """C++: SendProcessInfo(const char* SessionName, int Status)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        proc_info = AS_PROCESS_STATUS_T()
        proc_info.ProcessId   = session_name
        proc_info.Status      = status

        if status == START:
            # ProcConnectionMgr.get_process_info_by_name()
            if not self.get_process_info_by_name(session_name, proc_info):
                return

        proc_info.ManagerId   = MAINPTR().GetProcName()
        proc_info.ProcessType = ASCII_RULE_DOWNLOADER
        MAINPTR().UpdateProcessInfo(proc_info)

    # =========================================================================
    # LogStatus
    # =========================================================================

    def UpdateProcessLogStatus(self, status: AS_LOG_STATUS_T) -> None:
        """C++: UpdateProcessLogStatus(AS_LOG_STATUS_T*)"""
        self._log_status_map.pop(status.name, None)

        if status.status == LOG_ADD:
            self._log_status_map[status.name] = copy.copy(status)

        from ProcNaServer.AsciiServerWorld import AsciiServerWorld
        AsciiServerWorld.m_WorldPtr.SendLogStatus(status)

    def GetLogStatusList(self, status_list: list) -> None:
        """C++: GetLogStatusList(LogStatusVector*)"""
        status_list.extend(self._log_status_map.values())