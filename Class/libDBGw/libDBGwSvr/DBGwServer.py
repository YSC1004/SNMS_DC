"""
DBGwServer.py
C++ DBGwServer.h/.C → Python 변환

클라이언트(DBGwUser)로부터 수신된 패킷을 해석하여
실제 DB 작업(frDbSession)을 수행하고 결과를 응답 패킷으로 돌려보낸다.
"""

import os
import struct
import logging
from typing import Optional, Dict, TYPE_CHECKING

from libDBGw.libDBGwBase.DBGwType import (
    PACKET_T,
    DB_CONN_REQ_T, DB_CONN_RES_T,
    DB_CLOSE_REQ_T,
    DB_QUERY_REQ_T, DB_QUERY_RES_T,
    DB_BULK_QUERY_DATA_T,
    DB_RS_MOVE_NEXT_REQ_T,
    DB_RS_CLOSE_REQ_T,
    DB_RS_QUERY_DATA_T,
    DB_COMMIT_RES_T,
    DB_ROLLBACK_RES_T,
    DB_QUERY_LONG_UPDATE_REQ_T, DB_QUERY_LONG_UPDATE_RES_T,
    QueryResult,
    DB_CONN_REQ, DB_CONN_RES,
    DB_CLOSE_REQ,
    DB_QUERY_REQ, DB_QUERY_RES,
    DB_BULK_QUERY_DATA,
    DB_RS_MOVE_NEXT_REQ,
    DB_RS_CLOSE_REQ,
    DB_RS_QUERY_DATA,
    DB_COMMIT_REQ, DB_COMMIT_RES,
    DB_ROLLBACK_REQ, DB_ROLLBACK_RES,
    DB_QUERY_LONG_UPDATE_REQ, DB_QUERY_LONG_UPDATE_RES,
    QUERY_TYPE_SELECT, QUERY_TYPE_UPDATE, QUERY_TYPE_INSERT,
    QUERY_REQ_TYPE_BULK, QUERY_REQ_TYPE_RS,
    NO_SEG, SEG_ING, SEG_END,
    MAX_DATA_SIZE, MAX_ERROR_SIZE, DEF_BUF_SIZE,
    frDbParam, frDbRecord, frDbRecordSet,
)

# frDbSession: 실제 DB 연결/쿼리 담당 (기존 변환된 Sql 모듈)
from Sql.fr_db_session import frDbSession

if TYPE_CHECKING:
    from libDBGw.libDBGwSvr.DBGwServerSession import DBGwServerSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# frDbRecordSetMap : C++ map<int, frDbRecordSet*> 래퍼
# ---------------------------------------------------------------------------

class frDbRecordSetMap:
    """
    QueryId → frDbRecordSet 매핑 딕셔너리.
    C++ map<int, frDbRecordSet*> + Clear/Remove 인터페이스를 유지한다.
    """

    def __init__(self) -> None:
        self._map: Dict[int, frDbRecordSet] = {}

    def __del__(self) -> None:
        self.Clear()

    def Clear(self) -> None:
        """보유한 모든 RecordSet을 해제한다."""
        self._map.clear()

    def Remove(self, Id: int) -> bool:
        """Id에 해당하는 RecordSet을 제거한다. 없으면 False 반환."""
        if Id in self._map:
            del self._map[Id]
            return True
        return False

    def insert(self, key: int, value: frDbRecordSet) -> None:
        self._map[key] = value

    def find(self, key: int) -> Optional[frDbRecordSet]:
        return self._map.get(key, None)


# ---------------------------------------------------------------------------
# DBGwServer
# ---------------------------------------------------------------------------

class DBGwServer:
    """
    DB Gateway 서버 핵심 로직.

    - ReceivePacket()으로 클라이언트 패킷을 수신
    - frDbSession을 통해 실제 DB 작업 수행
    - DBGwServerSession.SendPacket()으로 응답 반환
    """

    # DB 연결 기본 IP/Port (C++ 원본 하드코딩 값 유지, 환경 변수로 오버라이드 가능)
    _DEFAULT_DB_IP   = os.environ.get("DBGW_DB_IP",   "192.168.1.4")
    _DEFAULT_DB_PORT = int(os.environ.get("DBGW_DB_PORT", "3306"))

    def __init__(self,
                 Session: "DBGwServerSession",
                 DbKind: int,
                 DefaultDbUser: str = "",
                 DefaultDbPasswd: str = "",
                 DefaultDbName: str = "") -> None:

        self.m_DbType: int                      = DbKind
        self.m_DBServerSession: "DBGwServerSession" = Session
        self.m_DbSession: Optional[frDbSession] = None

        self.m_DbUser:   str = DefaultDbUser
        self.m_DbPasswd: str = DefaultDbPasswd
        self.m_DbName:   str = DefaultDbName
        self.m_DbIp:     str = ""
        self.m_DbPort:   str = ""
        self.m_LogFile:  str = ""

        self.m_DbRecordSetMap = frDbRecordSetMap()

    def __del__(self) -> None:
        self.m_DbSession = None

    # -------------------------------------------------------------------------
    # Public
    # -------------------------------------------------------------------------

    def ReceivePacket(self, Packet: PACKET_T) -> None:
        """수신 패킷 MsgId에 따라 적절한 핸들러로 분기한다."""
        msg_id = Packet.MsgId
        msg    = Packet.Msg

        dispatch = {
            DB_CONN_REQ:              lambda: self._DbConnReq(DB_CONN_REQ_T.unpack(msg)),
            DB_QUERY_REQ:             lambda: self._DbQueryReq(DB_QUERY_REQ_T.unpack(msg)),
            DB_CLOSE_REQ:             lambda: self._DbCloseReq(DB_CLOSE_REQ_T.unpack(msg)),
            DB_RS_MOVE_NEXT_REQ:      lambda: self._DbRsMoveNextReq(DB_RS_MOVE_NEXT_REQ_T.unpack(msg)),
            DB_RS_CLOSE_REQ:          lambda: self._DbRsCloseReq(DB_RS_CLOSE_REQ_T.unpack(msg)),
            DB_COMMIT_REQ:            lambda: self._DbCommitReq(),
            DB_ROLLBACK_REQ:          lambda: self._DbRollBackReq(),
            DB_QUERY_LONG_UPDATE_REQ: lambda: self._DbQueryLongUpdateReq(DB_QUERY_LONG_UPDATE_REQ_T.unpack(msg)),
        }

        handler = dispatch.get(msg_id)
        if handler:
            handler()
        else:
            logger.warning("Unknown MsgId: %d", msg_id)

    def CloseSession(self, nErrorCode: int) -> None:
        """세션 종료 처리 (현재 구현 없음 - C++ 원본과 동일)."""
        pass

    def GetLogFile(self) -> str:
        return self.m_LogFile

    # -------------------------------------------------------------------------
    # Protected handlers
    # -------------------------------------------------------------------------

    def _DbConnReq(self, Req: DB_CONN_REQ_T) -> None:
        """DB 접속 요청 처리."""
        # 로깅 모드: 클라이언트 접속 정보로 로그 파일 생성
        if self.m_DBServerSession.m_IsLoggingMode:
            host_ip_safe = Req.HostIp.replace(".", "_")
            log_file = (
                f"{self.m_DBServerSession.m_LogDir}/"
                f"DBGW_{os.getpid()}_{Req.HostName}_{host_ip_safe}_{Req.ProcPid}.log"
            )
            # 로그 파일 핸들러 추가 (frLogger::Open 대응)
            fh = logging.FileHandler(log_file)
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logging.getLogger().addHandler(fh)
            self.m_LogFile = log_file
            logger.info("PID : %d[%s]", os.getpid(), self.m_LogFile)
            self.m_DBServerSession.m_IsLoggingMode = False

        logger.debug("Request connect db(%s/%s@%s)",
                     Req.DbUser, Req.DbPasswd, Req.DbName)

        self.m_DbSession = frDbSession.GetInstance()

        res = DB_CONN_RES_T()
        result: bool

        # 접속 정보 판별: 요청에 없으면 기본값 사용
        use_default = (
            not Req.DbPasswd and not Req.DbUser and not Req.DbName
            and self.m_DbUser and self.m_DbPasswd and self.m_DbName
        )
        use_req = Req.DbUser and Req.DbPasswd and Req.DbName

        if use_default:
            result = self.m_DbSession.Connect(
                self.m_DbUser, self.m_DbUser, self.m_DbName,
                self._DEFAULT_DB_IP, self._DEFAULT_DB_PORT
            )
            if not result:
                res.m_Error = self.m_DbSession.GetError()[:MAX_ERROR_SIZE - 1]

        elif use_req:
            result = self.m_DbSession.Connect(
                Req.DbUser, Req.DbPasswd, Req.DbName,
                self._DEFAULT_DB_IP, self._DEFAULT_DB_PORT
            )
            if not result:
                res.m_Error = self.m_DbSession.GetError()[:MAX_ERROR_SIZE - 1]

        else:
            result = False
            res.m_Error = (
                f"invalid connect info."
                f"({Req.DbUser}{Req.DbPasswd}@{Req.DbName})"
            )[:MAX_ERROR_SIZE - 1]
            logger.error(res.m_Error)

        res.m_Result = 1 if result else 0
        self.m_DBServerSession.SendPacket(DB_CONN_RES, res.pack(), res.size())

    def _DbQueryReq(self, Req: DB_QUERY_REQ_T) -> None:
        """쿼리 요청 처리. 세그먼트 분할 쿼리 조립 후 타입별 핸들러에 위임한다."""
        res = DB_QUERY_RES_T()
        res.m_Result = 0
        ret = True
        long_query = ""

        # 분할 전송 쿼리 조립
        if Req.m_SegFlag == SEG_ING:
            long_query = Req.m_Query
            logger.debug("### Start Long query")

            while True:
                tmp_req = DB_QUERY_REQ_T()
                if self.m_DBServerSession.WaitPacket(DB_QUERY_REQ, tmp_req) > 0:
                    long_query += tmp_req.m_Query
                    if tmp_req.m_SegFlag == SEG_END:
                        logger.debug("### Long query assembled")
                        break
                else:
                    logger.error("### Long query receive error")
                    ret = False
                    break

        if not ret:
            res.m_Error = "Segment Query isn't terminated well"
            self.m_DBServerSession.SendPacket(DB_QUERY_RES, res.pack(), res.size())
            return

        effective_query = long_query if long_query else Req.m_Query
        logger.debug("query : [%s]", effective_query)

        if Req.m_QueryType == QUERY_TYPE_SELECT:
            if Req.m_QueryReqType == QUERY_REQ_TYPE_BULK:
                self._DbQueryReqSelectBulk(Req, long_query)
            elif Req.m_QueryReqType == QUERY_REQ_TYPE_RS:
                self._DbQueryReqSelectRs(Req, long_query)
            else:
                res.m_Error = "Unknown DbQueryReq Type"
                self.m_DBServerSession.SendPacket(DB_QUERY_RES, res.pack(), res.size())

        elif Req.m_QueryType in (QUERY_TYPE_UPDATE, QUERY_TYPE_INSERT):
            self._DbQueryReqInsert(Req, long_query)
        else:
            res.m_Error = "Unknown DbQueryReq Type"
            self.m_DBServerSession.SendPacket(DB_QUERY_RES, res.pack(), res.size())

    def _DbQueryReqSelectBulk(self,
                               Req: DB_QUERY_REQ_T,
                               LongQuery: str = "") -> None:
        """SELECT BULK 쿼리: 전체 결과를 한 번에 전송한다."""
        result = QueryResult()
        effective = LongQuery if LongQuery else Req.m_Query
        self.m_DbSession.SqlQuery(effective, result)

        res = DB_QUERY_RES_T()
        res.m_Result  = result.m_Result
        res.m_QueryId = Req.m_QueryId
        res.m_ColCnt  = result.m_ColCnt
        res.m_RowCnt  = result.m_RowCnt

        logger.debug("query result: result=%d, rowcnt=%d",
                     res.m_Result, result.m_RowCnt)

        if res.m_Result == 0:
            res.m_Error = result.m_ErrorString[:MAX_ERROR_SIZE - 1]

        if res.m_Result > 0 and res.m_RowCnt:
            self._EncodeBulkDataSend(Req.m_QueryId, res, result)
        else:
            self.m_DBServerSession.SendPacket(DB_QUERY_RES, res.pack(), res.size())

        self.m_DbSession.Free(result)

    def _DbQueryReqSelectRs(self,
                             Req: DB_QUERY_REQ_T,
                             LongQuery: str = "") -> None:
        """SELECT RS 쿼리: RecordSet을 서버에 보관하고 MoveNext 방식으로 제공한다."""
        effective = LongQuery if LongQuery else Req.m_Query
        r_set: frDbRecordSet = self.m_DbSession.ExecuteRs(effective)

        res = DB_QUERY_RES_T()
        res.m_QueryId = Req.m_QueryId
        res.m_Result  = 1 if r_set.IsValid() else 0

        if r_set.IsValid():
            res.m_ColCnt = r_set.GetCol()
            self.m_DbRecordSetMap.insert(Req.m_QueryId, r_set)
        else:
            res.m_Error = r_set.m_Error[:MAX_ERROR_SIZE - 1]

        self.m_DBServerSession.SendPacket(DB_QUERY_RES, res.pack(), res.size())

    def _DbQueryReqInsert(self,
                          Req: DB_QUERY_REQ_T,
                          LongQuery: str = "") -> None:
        """INSERT/UPDATE/DELETE 쿼리를 실행하고 결과를 응답한다."""
        effective  = LongQuery if LongQuery else Req.m_Query
        auto_commit = (Req.m_Commit == 1)
        ok = self.m_DbSession.Execute(effective, auto_commit)

        res = DB_QUERY_RES_T()
        res.m_Result = 1 if ok else 0
        if not ok:
            err = self.m_DbSession.GetError()
            res.m_Error = err[:MAX_ERROR_SIZE - 1]

        self.m_DBServerSession.SendPacket(DB_QUERY_RES, res.pack(), res.size())
        logger.debug("End sending query result to client")

    def _DbRsMoveNextReq(self, Req: DB_RS_MOVE_NEXT_REQ_T) -> None:
        """RecordSet의 다음 레코드를 클라이언트에 전송한다."""
        r_set = self.m_DbRecordSetMap.find(Req.m_QueryId)

        if r_set is None:
            qdata = DB_RS_QUERY_DATA_T()
            qdata.m_Size    = -1
            qdata.m_Data    = f"Can't find recordset : {Req.m_QueryId}"
            qdata.m_QueryId = Req.m_QueryId
            qdata.m_SegFlag = NO_SEG
            self.m_DBServerSession.SendPacket(
                DB_RS_QUERY_DATA, qdata.pack(), qdata.size()
            )
            return

        record: Optional[frDbRecord] = r_set.MoveNext()
        self._EncodeRsDataSend(Req.m_QueryId, r_set.GetRow(), record)

    def _DbRsCloseReq(self, Req: DB_RS_CLOSE_REQ_T) -> None:
        """클라이언트가 요청한 RecordSet을 서버에서 제거한다."""
        self.m_DbRecordSetMap.Remove(Req.m_QueryId)

    def _DbCommitReq(self) -> None:
        """COMMIT 요청 처리."""
        res = DB_COMMIT_RES_T()
        res.m_Result = 1 if self.m_DbSession.Commit() else 0
        self.m_DBServerSession.SendPacket(DB_COMMIT_RES, res.pack(), res.size())

    def _DbRollBackReq(self) -> None:
        """ROLLBACK 요청 처리."""
        res = DB_ROLLBACK_RES_T()
        res.m_Result = 1 if self.m_DbSession.RollBack() else 0
        self.m_DBServerSession.SendPacket(DB_ROLLBACK_RES, res.pack(), res.size())

    def _DbCloseReq(self, Req: DB_CLOSE_REQ_T) -> None:
        """DB 닫기 요청 처리 (현재 구현 없음 - C++ 원본과 동일)."""
        pass

    def _DbQueryLongUpdateReq(self, Req: DB_QUERY_LONG_UPDATE_REQ_T) -> None:
        """LONG UPDATE 요청 처리. 세그먼트 분할 수신 후 실제 UPDATE 수행."""
        if Req.m_SegFlag == SEG_ING:
            # 분할 수신 조립
            data_buf = bytearray(Req.m_Data[:MAX_DATA_SIZE])

            while True:
                q_data = DB_QUERY_LONG_UPDATE_REQ_T()
                if self.m_DBServerSession.WaitPacket(
                    DB_QUERY_LONG_UPDATE_REQ, q_data
                ) > 0:
                    data_buf.extend(q_data.m_Data[:MAX_DATA_SIZE])
                    if q_data.m_SegFlag == SEG_END:
                        break
                else:
                    break

            self._DbQueryLongUpdate(Req.Table, Req.Field, bytes(data_buf))
        else:
            self._DbQueryLongUpdate(Req.Table, Req.Field,
                                    Req.m_Data if isinstance(Req.m_Data, bytes)
                                    else Req.m_Data.encode("utf-8"))

    def _DbQueryLongUpdate(self,
                           Table: str,
                           Field: str,
                           Data: bytes) -> None:
        """
        [where_len(4)][where][value_len(4)][value] 포맷 버퍼를 파싱하여
        frDbSession.UpdateLong()을 호출하고 결과를 응답한다.
        """
        offset = 0

        where_len = struct.unpack_from("!I", Data, offset)[0]
        offset += 4
        where = Data[offset: offset + where_len].decode("utf-8", errors="replace")
        offset += where_len

        value_len = struct.unpack_from("!I", Data, offset)[0]
        offset += 4
        value = Data[offset: offset + value_len].decode("utf-8", errors="replace")

        res = DB_QUERY_LONG_UPDATE_RES_T()
        ok = self.m_DbSession.UpdateLong(Table, Field, value, where)
        res.m_Result = 1 if ok else 0
        if not ok:
            res.m_Error = self.m_DbSession.GetError()[:MAX_ERROR_SIZE - 1]

        self.m_DBServerSession.SendPacket(
            DB_QUERY_LONG_UPDATE_RES, res.pack(), res.size()
        )

    # -------------------------------------------------------------------------
    # 데이터 인코딩 & 분할 전송
    # -------------------------------------------------------------------------

    def _EncodeBulkDataSend(self,
                             QueryId: int,
                             QueryRes: DB_QUERY_RES_T,
                             Result: QueryResult) -> None:
        """
        QueryResult 전체 레코드를 바이너리로 인코딩하여 분할 전송한다.
        각 컬럼 : [col_size(4, network order)][col_data(col_size)]
        """
        # 전체 데이터 버퍼 구성 (동적 확장 대신 bytearray 사용)
        buf = bytearray()
        rec: Optional[frDbRecord] = Result.m_Param.GetRecordHead()

        for row in range(Result.m_RowCnt):
            for col in range(Result.m_ColCnt):
                col_val   = Result.m_Buf[row][col]
                col_bytes = col_val.encode("utf-8") if isinstance(col_val, str) else col_val
                buf += struct.pack("!I", len(col_bytes))
                buf += col_bytes
            rec = rec.m_Next if rec else None

        QueryRes.m_DataSize = len(buf)
        self.m_DBServerSession.SendPacket(DB_QUERY_RES, QueryRes.pack(), QueryRes.size())

        # 분할 전송
        offset     = 0
        total_size = len(buf)

        while total_size > 0:
            q_data = DB_BULK_QUERY_DATA_T()
            q_data.m_QueryId = QueryId

            if total_size > MAX_DATA_SIZE:
                q_data.m_SegFlag = SEG_ING
                q_data.m_Data    = buf[offset: offset + MAX_DATA_SIZE]
                offset     += MAX_DATA_SIZE
                total_size -= MAX_DATA_SIZE
            else:
                q_data.m_SegFlag = SEG_END
                q_data.m_Data    = buf[offset: offset + total_size]
                offset     += total_size
                total_size  = 0

            self.m_DBServerSession.SendPacket(
                DB_BULK_QUERY_DATA, q_data.pack(), q_data.size()
            )

    def _EncodeRsDataSend(self,
                           QueryId: int,
                           RowCnt: int,
                           Record: Optional[frDbRecord]) -> None:
        """
        단일 레코드(frDbRecord)를 바이너리로 인코딩하여 분할 전송한다.
        Record가 None이면 EOF(-2) 응답을 보낸다.
        """
        q_data = DB_RS_QUERY_DATA_T()

        if Record is None:
            q_data.m_QueryId = QueryId
            q_data.m_Size    = -2          # EOF 마커 (C++ 원본과 동일)
            q_data.m_CurRow  = RowCnt
            self.m_DBServerSession.SendPacket(
                DB_RS_QUERY_DATA, q_data.pack(), q_data.size()
            )
            return

        # 레코드 인코딩
        buf = bytearray()
        for col in range(Record.m_Col):
            col_val   = Record.m_Values[col]
            col_bytes = col_val.encode("utf-8") if isinstance(col_val, str) else (col_val or b"")
            buf += struct.pack("!I", len(col_bytes))
            buf += col_bytes

        offset     = 0
        total_size = len(buf)

        while total_size > 0:
            q_data = DB_RS_QUERY_DATA_T()
            q_data.m_QueryId = QueryId
            q_data.m_CurRow  = RowCnt

            chunk_size = min(total_size, MAX_DATA_SIZE)
            q_data.m_Data    = buf[offset: offset + chunk_size]
            q_data.m_Size    = chunk_size
            q_data.m_SegFlag = SEG_ING if total_size > MAX_DATA_SIZE else SEG_END

            offset     += chunk_size
            total_size -= chunk_size

            self.m_DBServerSession.SendPacket(
                DB_RS_QUERY_DATA, q_data.pack(), q_data.size()
            )

    def _ResizeBufSize(self, cur_buf: bytearray, increment: int = DEF_BUF_SIZE) -> bytearray:
        """
        버퍼를 increment 만큼 확장한다.
        C++ 포인터 재할당 패턴 → Python bytearray 확장으로 대체.
        (EncodeBulkDataSend에서 bytearray를 직접 사용하므로 현재 미사용)
        """
        cur_buf.extend(bytearray(increment))
        return cur_buf