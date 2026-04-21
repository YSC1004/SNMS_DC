"""
MMCGenConnection.py
C++ MMCGenConnection.h/.C → Python 변환

MMCGenerator / MMCScheduler / JobMonitor 소켓 연결 처리.
  - MMCRequestConnection 상속
  - 세션 타입별 패킷 분기 처리
  - MMC 요청 큐 삽입 / Generator 전달 / Log 전송
"""

import asyncio
import logging
from typing import Optional, TYPE_CHECKING

from ProcNaServer.MMCRequestConnection import MMCRequestConnection  # 부모 클래스
from Common.CommTypeList import (
    AS_MMC_REQUEST_T, AS_MMC_GEN_RESULT_T, AS_MMC_LOG_T,
    AS_LOG_STATUS_T, AS_ASCII_ERROR_MSG_T, AS_ASCII_ACK_T,
)
from Common.CommType import (
    ASCII_MMC_GENERATOR, ASCII_MMC_SCHEDULER, ASCII_JOB_MONITOR,
    NOT_ASSIGN, START,
    PROC_INIT_END,
    AS_MMC_REQ, AS_LOG_INFO, ASCII_ERROR_MSG,
    MMC_GEN_REQ, MMC_GEN_RES, MMC_LOG,
    CMD_SCHEDULER_RULE_DOWN_ACK, CMD_COMMAND_RULE_DOWN_ACK,
    LOG_DEL, ORDER_KILL,
)
from Common.AsUtil import AsUtil

if TYPE_CHECKING:
    from ProcNaServer.MMCGeneratorConnMgr import MMCGeneratorConnMgr

logger = logging.getLogger(__name__)


class MMCGenConnection(MMCRequestConnection):
    """
    C++ MMCGenConnection (MMCRequestConnection 상속) 대응.

    AsSocket 가상 메서드 오버라이드:
      receive_packet()              ← C++ ReceivePacket()
      close_socket()                ← C++ CloseSocket()
      session_identify_callback()   ← C++ SessionIdentify()
      alive_check_fail()            ← C++ AliveCheckFail()
      ReceiveTimeOut()              ← C++ ReceiveTimeOut()
    """

    def __init__(self, conn_mgr: "MMCGeneratorConnMgr") -> None:
        super().__init__()
        self._mmc_gen_conn_mgr: "MMCGeneratorConnMgr" = conn_mgr
        self._mmc_proc_status: bool = True          # C++: m_MMCProcStatus

    def __del__(self) -> None:
        # 세션 식별이 완료된 경우 세션 포인터 해제
        if self.GetSessionType() != NOT_ASSIGN:
            self._mmc_gen_conn_mgr.SetMMCGeneratorSession(
                self.GetSessionType(), None)

    # =========================================================================
    # AsSocket 가상 메서드 오버라이드
    # =========================================================================

    def receive_packet(self, packet, session_identify: int = -1) -> None:
        """C++: virtual ReceivePacket(PACKET_T*, const int SessionIdentify)"""
        if session_identify == ASCII_MMC_SCHEDULER:
            self._mmc_sch_proc_req(packet)
        elif session_identify == ASCII_MMC_GENERATOR:
            self._mmc_gen_proc_req(packet)
        elif session_identify == ASCII_JOB_MONITOR:
            self._job_monitor_req(packet)
        else:
            logger.debug("UnKnown Session : %d", session_identify)

    def session_identify_callback(self, session_type: int,
                                   session_name: str = "") -> None:
        """C++: virtual SessionIdentify(int SessionType, string SessionName)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR, AsciiServerWorld

        logger.debug("Session Identify : Type(%s), SessionName(%s)",
                     AsUtil.GetProcessTypeString(session_type), session_name)

        # 중복 세션명 검사 (ConnectionMgr.add_session_name)
        if not self._mmc_gen_conn_mgr.add_session_name(session_name):
            self._close()
            self._mmc_gen_conn_mgr.remove(self)     # ConnectionMgr.remove()
            return

        self._mmc_gen_conn_mgr.SetMMCGeneratorSession(session_type, self)

        # Scheduler / JobMonitor → MMCRequestQueue 등록
        if session_type in (ASCII_JOB_MONITOR, ASCII_MMC_SCHEDULER):
            self._mmc_request_queue = \
                AsciiServerWorld.m_WorldPtr.RegisterMMCReqConn(self, 100000)

        self._mmc_gen_conn_mgr.SendProcessInfo(
            session_name, session_type, START)

        # AliveCheck 시작 (AsSocket.StartAliveCheck)
        self.StartAliveCheck(
            MAINPTR().GetProcAliveCheckTime(),      # AsWorld
            MAINPTR().GetAliveCheckLimitCnt(),      # AsWorld
        )

    def close_socket(self, errno_val: int) -> None:
        """C++: virtual CloseSocket(int Errno)"""
        session_name = self.GetSessionName()
        logger.debug("Socket Broken : %s", session_name)

        # 로그 상태 DEL 처리
        log_status = AS_LOG_STATUS_T()
        log_status.name   = session_name
        log_status.status = LOG_DEL
        log_status.logs   = (
            f"sUn,{AsUtil.GetProcessTypeString(self.GetSessionType())},"
            f"{session_name},"
        )
        self._mmc_gen_conn_mgr.UpdateMMCProcessLogStatus(log_status)

        # ProcConnectionMgr.child_process_dead() 호출
        if self._mmc_proc_status:
            self._mmc_gen_conn_mgr.child_process_dead(self)
        else:
            self._mmc_gen_conn_mgr.child_process_dead(self, ORDER_KILL)

    def alive_check_fail(self, fail_count: int) -> None:
        """C++: virtual AliveCheckFail(int FailCount)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        logger.debug("AliveCheckFail(%s) , Count : %d",
                     self.GetSessionName(), fail_count)
        MAINPTR().SendAsciiError(
            1,
            "The Process is killed on purpose for no reply from %s.",
            self.GetSessionName(),
        )
        # ProcConnectionMgr.various_ack_check_time_out()
        self._mmc_gen_conn_mgr.various_ack_check_time_out(self)

    def ReceiveTimeOut(self, reason: int, extra_reason=None) -> None:
        """C++: ReceiveTimeOut(int Reason, void* ExtraReason)"""
        logger.error("Unknown Time Out Reason : %d", reason)

    # =========================================================================
    # 패킷 처리 내부 메서드
    # =========================================================================

    def _mmc_sch_proc_req(self, packet) -> None:
        """C++: MMCSchProcReq(PACKET_T*) — Scheduler 패킷 처리."""
        from ProcNaServer.AsciiServerWorld import MAINPTR, AsciiServerWorld

        msg_id = packet.MsgId

        if msg_id == PROC_INIT_END:
            pass                                    # C++ 원본 동일하게 처리 없음

        elif msg_id == AS_MMC_REQ:
            self.ReceiveMMCReqFromSch(packet.Msg)

        elif msg_id == AS_LOG_INFO:
            self.ReceiveLogInfo(packet.Msg)

        elif msg_id == ASCII_ERROR_MSG:
            err: AS_ASCII_ERROR_MSG_T = packet.Msg
            err.ProcessId = self.GetSessionName()
            MAINPTR().SendAsciiError(err)

        elif msg_id == CMD_SCHEDULER_RULE_DOWN_ACK:
            AsciiServerWorld.m_WorldPtr.RecvSchedulerRuleDownResult(packet.Msg)

        else:
            logger.error("Unknown Msg Id : %d", msg_id)

    def _mmc_gen_proc_req(self, packet) -> None:
        """C++: MMCGenProcReq(PACKET_T*) — Generator 패킷 처리."""
        from ProcNaServer.AsciiServerWorld import MAINPTR, AsciiServerWorld

        msg_id = packet.MsgId

        if msg_id == PROC_INIT_END:
            MAINPTR().NotifyEvent(ASCII_MMC_GENERATOR, msg_id)

        elif msg_id == MMC_GEN_RES:
            self.MMCResFromMMCGen(packet.Msg)

        elif msg_id == AS_LOG_INFO:
            self.ReceiveLogInfo(packet.Msg)

        elif msg_id == ASCII_ERROR_MSG:
            err: AS_ASCII_ERROR_MSG_T = packet.Msg
            err.ProcessId = self.GetSessionName()
            MAINPTR().SendAsciiError(err)

        elif msg_id == CMD_COMMAND_RULE_DOWN_ACK:
            AsciiServerWorld.m_WorldPtr.RecvCommandRuleDownResult(packet.Msg)

        else:
            logger.error("Unknown Msg Id : %d", msg_id)

    def _job_monitor_req(self, packet) -> None:
        """C++: JobMonitorReq(PACKET_T*) — JobMonitor 패킷 처리."""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        msg_id = packet.MsgId

        if msg_id == PROC_INIT_END:
            pass

        elif msg_id == AS_MMC_REQ:
            self.ReceiveMMCReqFromJob(packet.Msg)

        elif msg_id == AS_LOG_INFO:
            self.ReceiveLogInfo(packet.Msg)

        elif msg_id == ASCII_ERROR_MSG:
            err: AS_ASCII_ERROR_MSG_T = packet.Msg
            err.ProcessId = self.GetSessionName()
            MAINPTR().SendAsciiError(err)

        else:
            logger.error("Unknown Msg Id : %d", msg_id)

    # =========================================================================
    # MMC 요청 처리 (Scheduler / JobMonitor)
    # =========================================================================

    def ReceiveMMCReqFromSch(self, mmc_req: AS_MMC_REQUEST_T) -> None:
        """C++: ReceiveMMCReqFromSch(AS_MMC_REQUEST_T*) — Scheduler MMC 요청."""
        mmc_req.priority = 2
        mmc_req.logMode  = 0
        logger.debug(
            "Receive MMCReq From MMCSch : ne(%s), mmc(%s), type(%s), referenceId(%d)",
            mmc_req.ne, mmc_req.mmc,
            AsUtil.GetEnumTypeString(mmc_req.type),
            mmc_req.referenceId,
        )
        # MMCRequestConnection._mmc_request_queue
        self._mmc_request_queue.InsertMMCRequest(mmc_req)

    def ReceiveMMCReqFromJob(self, mmc_req: AS_MMC_REQUEST_T) -> None:
        """C++: ReceiveMMCReqFromJob(AS_MMC_REQUEST_T*) — JobMonitor MMC 요청."""
        logger.debug("Receive MMCReq From JobMonitor : ne(%s), mmc(%s)",
                     mmc_req.ne, mmc_req.mmc)
        self._mmc_request_queue.InsertMMCRequest(mmc_req)

    # =========================================================================
    # Generator 전달
    # =========================================================================

    async def SendMMCReqToMMCGen(self, mmc_req: AS_MMC_REQUEST_T) -> bool:
        """C++: SendMMCReqToMMCGen(AS_MMC_REQUEST_T*) → MMC_GEN_REQ 전송."""
        logger.debug("Send MMCReq to MMCGen : ne(%s), mmc(%s)",
                     mmc_req.ne, mmc_req.mmc)
        payload = _pack(mmc_req)
        return await self.SendPacket(MMC_GEN_REQ, payload, len(payload))

    def MMCResFromMMCGen(self, result: AS_MMC_GEN_RESULT_T) -> None:
        """C++: MMCResFromMMCGen(AS_MMC_GEN_RESULT_T*)"""
        from ProcNaServer.AsciiServerWorld import MAINPTR

        logger.debug("Recv Command Gen Size : %d", result.commandNo)
        MAINPTR().MMCResFromMMCGen(result)

    # =========================================================================
    # Log / FlowControl
    # =========================================================================

    def ReceiveLogInfo(self, status: AS_LOG_STATUS_T) -> None:
        """C++: ReceiveLogInfo(AS_LOG_STATUS_T*)"""
        self._mmc_gen_conn_mgr.UpdateMMCProcessLogStatus(status)

    async def SendMMCLog(self, mmc_log: AS_MMC_LOG_T) -> bool:
        """C++: SendMMCLog(AS_MMC_LOG_T*) → MMC_LOG 패킷 전송."""
        payload = _pack(mmc_log)
        return await self.SendPacket(MMC_LOG, payload, len(payload))

    async def SendFlowControl(self, msg_id: int = -1) -> bool:
        """C++: virtual SendFlowControl(int MsgId=-1) — 가상함수, 로그만."""
        logger.error("virtual Call MMCGenConnection SendFlowControl")
        return True


# ─────────────────────────────────────────────────────────────────────────────
# 패킷 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pack(obj) -> bytes:
    if hasattr(obj, 'pack'):
        return obj.pack()
    return b''