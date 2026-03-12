"""
DBGwUser.py
C++ DBGwUser.h/.C → Python 변환
"""

import os
import socket
import struct
import threading
import logging
from typing import Optional

# 내부 모듈 import (변환 완료된 파일들)
from libDBGw.libDBGwBase.DBGwType import (
    DB_CONN_REQ_T, DB_CONN_RES_T,
    DB_CLOSE_REQ_T,
    DB_QUERY_REQ_T, DB_QUERY_RES_T,
    DB_BULK_QUERY_DATA_T,
    DB_COMMIT_RES_T, DB_ROLLBACK_RES_T,
    DB_QUERY_LONG_UPDATE_REQ_T, DB_QUERY_LONG_UPDATE_RES_T,
    PACKET_T,
    eDB_TYPE, eQUERY_DATA_TYPE,
    QueryResult,
    DB_CONN_REQ, DB_CONN_RES,
    DB_CLOSE_REQ,
    DB_QUERY_REQ, DB_QUERY_RES,
    DB_BULK_QUERY_DATA,
    DB_COMMIT_REQ, DB_COMMIT_RES,
    DB_ROLLBACK_REQ, DB_ROLLBACK_RES,
    DB_QUERY_LONG_UPDATE_REQ, DB_QUERY_LONG_UPDATE_RES,
    QUERY_TYPE_SELECT, QUERY_TYPE_UPDATE,
    QUERY_REQ_TYPE_RS, QUERY_REQ_TYPE_BULK,
    NO_SEG, SEG_ING, SEG_END,
    MAX_DATA_SIZE,
    frDbParam, frDbRecord,
)
from libDBGw.libDBGwClient.DBGwRecordSet import DBGwRecordSet
from libDBGw.libDBGwClient.DBClientSocket import DBClientSocket

logger = logging.getLogger(__name__)


class DBGwUser:
    """
    DB Gateway 클라이언트 사용자 클래스.
    DBGateway 서버와 소켓 통신으로 DB 쿼리를 수행한다.
    """

    def __init__(self) -> None:
        self.m_DBClientSocket: Optional[DBClientSocket] = None
        self.m_IsOpen: bool = False
        self.m_QueryId: int = 0

        self.m_DbGwIp: str = ""
        self.m_DbGwPort: int = 0
        self.m_DbUser: str = ""
        self.m_DbPasswd: str = ""
        self.m_DbName: str = ""
        self.m_DBType: eDB_TYPE = eDB_TYPE.eDB_NONE   # DBGwType에 정의된 기본값 사용

        self.m_Error: str = ""
        self.m_SqlLock: threading.Lock = threading.Lock()

    def __del__(self) -> None:
        self.CloseDB()

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def Connect(self,
                DbGwIp: str = "",
                DbGwPort: int = 0,
                DbUser: str = "",
                DbPasswd: str = "",
                DbName: str = "") -> bool:
        """
        DB Gateway 서버에 연결한다.
        인자 없이 호출 시 저장된 접속 정보로 재접속(reconnect)을 시도한다.
        """
        # 인자가 없으면 저장된 접속 정보로 재접속
        if not DbGwIp:
            if (self.m_DbGwIp and self.m_DbGwPort
                    and self.m_DbUser and self.m_DbPasswd and self.m_DbName):
                return self._ConnectWithInfo(
                    self.m_DbGwIp, self.m_DbGwPort,
                    self.m_DbUser, self.m_DbPasswd, self.m_DbName
                )
            return False

        return self._ConnectWithInfo(DbGwIp, DbGwPort, DbUser, DbPasswd, DbName)

    def CloseDB(self) -> bool:
        """DB 연결을 종료한다."""
        if self.m_DBClientSocket:
            with self.m_SqlLock:
                req = DB_CLOSE_REQ_T()
                req.m_Req = 1
                self.m_DBClientSocket.SendPacket(
                    DB_CLOSE_REQ,
                    req.pack(),
                    req.size()
                )
                self.m_DBClientSocket = None
        self.m_DBClientSocket = None
        self.m_IsOpen = False
        return True

    def ReceivePacket(self, Packet: PACKET_T) -> None:
        """패킷 수신 콜백 (필요 시 서브클래스에서 오버라이드)."""
        pass

    def CloseSession(self, nErrorCode: int) -> None:
        """소켓 세션 종료 시 호출된다. 1회 재접속을 시도한다."""
        with self.m_SqlLock:
            logger.warning(
                "Disconnected db session :(%s:%d:%s/%s@%s)",
                self.m_DbGwIp, self.m_DbGwPort,
                self.m_DbUser, self.m_DbPasswd, self.m_DbName
            )
            if self.m_DBClientSocket:
                self.m_DBClientSocket = None
            self.m_IsOpen = False

        logger.info("Try reconnect db (only 1 time)")
        ret = self.Connect()
        logger.info("Try reconnect %s", "success" if ret else "fail")

    def Execute(self, Query: str, AutoCommit: bool = True) -> bool:
        """INSERT/UPDATE/DELETE 쿼리를 실행한다."""
        with self.m_SqlLock:
            return self._ExecuteNoLock(Query, AutoCommit)

    def ExecuteRs(self, Query: str) -> Optional["DBGwRecordSet"]:
        """SELECT 쿼리를 실행하고 DBGwRecordSet을 반환한다."""
        with self.m_SqlLock:
            if self.m_DBClientSocket is None:
                if not self.Connect():
                    return None

            req = DB_QUERY_REQ_T()
            req.m_QueryId    = self.m_QueryId
            self.m_QueryId  += 1
            req.m_QueryType  = QUERY_TYPE_SELECT
            req.m_SegFlag    = NO_SEG
            req.m_QueryReqType = QUERY_REQ_TYPE_RS
            req.m_Query      = Query

            res = DB_QUERY_RES_T()

            if self.m_DBClientSocket.SendAndWaitPacket(
                DB_QUERY_REQ, req.pack(), req.size(),
                DB_QUERY_RES, res
            ) > 0:
                rs = DBGwRecordSet(self)
                rs.m_IsValid  = bool(res.m_Result)
                rs.m_Query    = Query
                rs.m_QueryId  = res.m_QueryId

                if rs.m_IsValid:
                    rs.SetCol(res.m_ColCnt)
                else:
                    rs.m_Error = res.m_Error
                return rs

            return None

    def SqlQuery(self,
                 Query: str,
                 Result: QueryResult,
                 AdditionText: str = "") -> bool:
        """
        SELECT 쿼리를 실행하고 결과를 QueryResult에 저장한다.
        INSERT/UPDATE/DELETE는 Execute로 위임한다.
        긴 쿼리(> MAX_DATA_SIZE)는 세그먼트 분할 전송을 수행한다.
        """
        with self.m_SqlLock:
            if self.m_DBClientSocket is None:
                if not self.Connect():
                    Result.m_ErrorString = self.m_Error
                    return False

            # DML 판별 (앞 6글자)
            head = Query[:6].upper()
            if head in ("INSERT", "UPDATE", "DELETE"):
                ok = self._ExecuteNoLock(Query, False)
                if ok:
                    Result.m_Result = 1
                else:
                    Result.m_Result = 0
                    Result.m_ErrorString = self.GetError()
                return ok

            # SELECT
            req = DB_QUERY_REQ_T()
            req.m_QueryId      = self.m_QueryId
            self.m_QueryId    += 1
            req.m_QueryType    = QUERY_TYPE_SELECT
            req.m_SegFlag      = NO_SEG
            req.m_QueryReqType = QUERY_REQ_TYPE_BULK

            query_bytes = Query.encode("utf-8")
            cnt = 0

            # 긴 쿼리 분할 전송
            if len(query_bytes) > MAX_DATA_SIZE - 1:
                logger.debug("### long query start")
                offset = 0
                q_len  = len(query_bytes)

                while q_len > 0:
                    chunk = query_bytes[offset: offset + MAX_DATA_SIZE - 1]
                    req.m_Query = chunk.decode("utf-8", errors="replace")
                    offset += len(chunk)
                    q_len  -= len(chunk)

                    if q_len > 0:
                        req.m_SegFlag = SEG_ING
                        logger.debug("### long query send : %d", cnt)
                        self.m_DBClientSocket.SendPacket(
                            DB_QUERY_REQ, req.pack(), req.size()
                        )
                        cnt += 1
                    else:
                        req.m_SegFlag = SEG_END
                        # 마지막 패킷은 아래 SendAndWaitPacket으로 전송
            else:
                req.m_Query = Query

            res = DB_QUERY_RES_T()

            if cnt > 0:
                logger.debug("### long query send last : %d", cnt)

            if self.m_DBClientSocket.SendAndWaitPacket(
                DB_QUERY_REQ, req.pack(), req.size(),
                DB_QUERY_RES, res
            ) > 0:
                Result.m_Result      = res.m_Result
                Result.m_ErrorString = res.m_Error
                self.m_Error         = Result.m_ErrorString

                if res.m_Result == 1:
                    Result.m_ColCnt = res.m_ColCnt
                    Result.m_RowCnt = res.m_RowCnt

                    if Result.m_RowCnt:
                        # 분할 수신
                        data_buf = bytearray()
                        while True:
                            qdata = DB_BULK_QUERY_DATA_T()
                            if self.m_DBClientSocket.WaitPacket(
                                DB_BULK_QUERY_DATA, qdata
                            ) < 0:
                                return False

                            data_buf.extend(
                                qdata.m_Data[:MAX_DATA_SIZE]
                            )
                            if qdata.m_SegFlag != SEG_ING:
                                break

                        return self._DecodeBulkData(Result, bytes(data_buf))

                    return True
                return False

        return False

    def Commit(self) -> bool:
        """트랜잭션을 커밋한다."""
        with self.m_SqlLock:
            if not self._EnsureConnected():
                return False

            res = DB_COMMIT_RES_T()
            if self.m_DBClientSocket.SendAndWaitPacket(
                DB_COMMIT_REQ, b"", 0,
                DB_COMMIT_RES, res
            ) > 0:
                self.m_Error = res.m_Error
                return bool(res.m_Result)
        return False

    def RollBack(self) -> bool:
        """트랜잭션을 롤백한다."""
        with self.m_SqlLock:
            if not self._EnsureConnected():
                return False

            res = DB_ROLLBACK_RES_T()
            if self.m_DBClientSocket.SendAndWaitPacket(
                DB_ROLLBACK_REQ, b"", 0,
                DB_ROLLBACK_RES, res
            ) > 0:
                self.m_Error = res.m_Error
                return bool(res.m_Result)
        return False

    def Free(self, Result: QueryResult) -> None:
        """QueryResult 메모리를 해제한다."""
        Result.Free()

    def UpdateLong(self,
                   Table: str,
                   Field: str,
                   Value: str,
                   Where: str) -> bool:
        """
        LONG 타입 컬럼 UPDATE를 수행한다.
        대용량 데이터를 세그먼트 분할 전송한다.
        """
        with self.m_SqlLock:
            if not self._EnsureConnected():
                return False

            # 데이터 버퍼 구성 : [where_len(4)][where][value_len(4)][value]
            where_b = Where.encode("utf-8")
            value_b = Value.encode("utf-8")
            data_buf = (
                struct.pack("!I", len(where_b)) + where_b +
                struct.pack("!I", len(value_b)) + value_b
            )
            total_size = len(data_buf)

            qdata = DB_QUERY_LONG_UPDATE_REQ_T()
            qdata.Table      = Table
            qdata.Field      = Field
            qdata.m_DataSize = total_size

            qres  = DB_QUERY_LONG_UPDATE_RES_T()
            offset = 0

            while total_size > 0:
                chunk = data_buf[offset: offset + MAX_DATA_SIZE]
                qdata.m_Data = chunk

                if total_size > MAX_DATA_SIZE:
                    qdata.m_SegFlag = SEG_ING
                    self.m_DBClientSocket.SendPacket(
                        DB_QUERY_LONG_UPDATE_REQ,
                        qdata.pack(),
                        qdata.size()
                    )
                else:
                    qdata.m_SegFlag = SEG_END
                    self.m_DBClientSocket.SendAndWaitPacket(
                        DB_QUERY_LONG_UPDATE_REQ,
                        qdata.pack(),
                        qdata.size(),
                        DB_QUERY_LONG_UPDATE_RES,
                        qres
                    )

                offset     += len(chunk)
                total_size -= len(chunk)

            self.m_Error = qres.m_Error
            return bool(qres.m_Result)

    def IsExistTable(self, TableName: str) -> bool:
        """테이블 존재 여부를 확인한다."""
        if self.m_DBClientSocket is None:
            if not self.Connect():
                return False

        db_type = self.GetDbType()
        if db_type in (eDB_TYPE.eDB_ORACLE_OCI_OLD,
                       eDB_TYPE.eDB_ORACLE_OCI2,
                       eDB_TYPE.eDB_ORACLE_ODBC):
            query = (f"SELECT COUNT(*) FROM TAB "
                     f"WHERE TNAME = '{TableName}'")
        elif db_type in (eDB_TYPE.eDB_MSSQL_ODBC,
                         eDB_TYPE.eDB_MYSQL):
            query = (f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                     f"WHERE TABLE_NAME = '{TableName}'")
        else:
            return False

        result = QueryResult()
        if not self.SqlQuery(query, result):
            return False

        is_table = int(result.m_Buf[0][0])
        self.Free(result)
        return bool(is_table)

    def GetError(self) -> str:
        return self.m_Error

    def IsConnect(self) -> bool:
        if self.m_DBClientSocket:
            return self.m_DBClientSocket.IsConnect()
        return False

    def GetDbType(self) -> eDB_TYPE:
        return self.m_DBType

    # -------------------------------------------------------------------------
    # Query helper : INSERT/SELECT 용 DB별 SQL 표현식 생성
    # -------------------------------------------------------------------------

    def MakeQueryInsert(self,
                        DataType: eQUERY_DATA_TYPE,
                        Data: str) -> str:
        """INSERT 쿼리에 사용할 DB 종류별 날짜/SYSDATE 표현식을 반환한다."""
        out = ""
        if DataType == eQUERY_DATA_TYPE.eDATE_TYPE:
            if self.m_DBType in (eDB_TYPE.eDB_ORACLE_OCI2,
                                  eDB_TYPE.eDB_ORACLE_OCI_OLD):
                out = f"TO_DATE('{Data}', 'YYYY/MM/DD HH24:MI:SS')"
            elif self.m_DBType == eDB_TYPE.eDB_MYSQL:
                out = f"STR_TO_DATE('{Data}', '%Y/%m/%d %H:%i:%s')"
            elif self.m_DBType == eDB_TYPE.eDB_MSSQL_ODBC:
                out = f"'{Data}'"

        elif DataType == eQUERY_DATA_TYPE.eSYSDATE:
            if self.m_DBType in (eDB_TYPE.eDB_ORACLE_OCI2,
                                  eDB_TYPE.eDB_ORACLE_OCI_OLD):
                out = "SYSDATE"
            elif self.m_DBType == eDB_TYPE.eDB_MYSQL:
                out = "sysdate()"
            elif self.m_DBType == eDB_TYPE.eDB_MSSQL_ODBC:
                out = "not impl"

        return out if out else "undefined dbtype or datatype"

    def MakeQuerySelect(self,
                        DataType: eQUERY_DATA_TYPE,
                        Field: str) -> str:
        """SELECT 쿼리에 사용할 DB 종류별 날짜/SYSDATE 표현식을 반환한다."""
        out = ""
        if DataType == eQUERY_DATA_TYPE.eDATE_TYPE:
            if self.m_DBType in (eDB_TYPE.eDB_ORACLE_OCI2,
                                  eDB_TYPE.eDB_ORACLE_OCI_OLD):
                out = f"TO_CHAR({Field}, 'YYYY/MM/DD HH24:MI:SS')"
            elif self.m_DBType == eDB_TYPE.eDB_MYSQL:
                out = f"DATE_FORMAT({Field}, '%Y/%m/%d %H:%i:%s')"
            elif self.m_DBType == eDB_TYPE.eDB_MSSQL_ODBC:
                out = Field

        elif DataType == eQUERY_DATA_TYPE.eSYSDATE:
            if self.m_DBType in (eDB_TYPE.eDB_ORACLE_OCI2,
                                  eDB_TYPE.eDB_ORACLE_OCI_OLD):
                out = "SYSDATE"
            elif self.m_DBType == eDB_TYPE.eDB_MYSQL:
                out = "sysdate()"
            elif self.m_DBType == eDB_TYPE.eDB_MSSQL_ODBC:
                out = "not impl"

        return out if out else "undefined dbtype or datatype"

    # -------------------------------------------------------------------------
    # RecordSet 데이터 디코딩 (DBGwRecordSet에서 호출)
    # -------------------------------------------------------------------------

    def DecodeRsData(self,
                     ColCnt: int,
                     Param: frDbParam,
                     DataBuf: bytes) -> frDbRecord:
        """
        바이너리 버퍼에서 단일 레코드를 디코딩하여 Param에 추가하고 반환한다.
        각 컬럼 : [col_data_size(4, network order)][col_data(col_data_size)]
        """
        offset = 0
        record = frDbRecord()
        record.m_Col    = ColCnt
        record.m_Values = []

        for _ in range(ColCnt):
            col_size = struct.unpack_from("!I", DataBuf, offset)[0]
            offset  += 4
            value    = DataBuf[offset: offset + col_size].decode("utf-8", errors="replace")
            offset  += col_size
            record.m_Values.append(value)

        Param.AddRecord(record)
        return record

    # -------------------------------------------------------------------------
    # Protected helpers
    # -------------------------------------------------------------------------

    def _ConnectWithInfo(self,
                         DbGwIp: str,
                         DbGwPort: int,
                         DbUser: str,
                         DbPasswd: str,
                         DbName: str) -> bool:
        """실제 접속 처리 (인자 포함)."""
        with self.m_SqlLock:
            if self.m_IsOpen:
                self.m_Error = "Already Open"
                return False

            if self.m_DBClientSocket:
                self.m_Error = "Already Open Socket"
                return False

            self.m_IsOpen = False
            self.m_DBClientSocket = DBClientSocket(self)

            if not self.m_DBClientSocket.Create():
                self.m_Error = "DB GW Socket Create Error"
                return False

            if not self.m_DBClientSocket.Connect(DbGwIp, DbGwPort):
                self.m_Error = (
                    f"DB GW Connect Error({self.m_DBClientSocket.GetObjErrMsg()})"
                )
                self.m_DBClientSocket = None
                return False

            # 접속 요청 패킷 구성
            con_req = DB_CONN_REQ_T()
            con_req.DbUser   = DbUser
            con_req.DbPasswd = DbPasswd
            con_req.DbName   = DbName
            self._GetLocalInfo(con_req)

            con_res = DB_CONN_RES_T()

            if self.m_DBClientSocket.SendAndWaitPacket(
                DB_CONN_REQ, con_req.pack(), con_req.size(),
                DB_CONN_RES, con_res
            ) > 0:
                self.m_Error   = con_res.m_Error
                self.m_IsOpen  = bool(con_res.m_Result)

                self.m_DbGwIp  = DbGwIp
                self.m_DbGwPort = DbGwPort
                self.m_DbUser   = DbUser
                self.m_DbPasswd = DbPasswd
                self.m_DbName   = DbName
                return bool(con_res.m_Result)

            self.m_DBClientSocket = None
        return False

    def _GetLocalInfo(self, ConReq: DB_CONN_REQ_T) -> bool:
        """로컬 호스트/IP/유저/PID 정보를 접속 요청 구조체에 채운다."""
        ConReq.HostName = socket.gethostname()
        try:
            ConReq.HostIp = socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            ConReq.HostIp = "127.0.0.1"
        ConReq.UserId  = os.environ.get("USER", os.environ.get("USERNAME", ""))
        ConReq.ProcPid = os.getpid()
        return True

    def _EnsureConnected(self) -> bool:
        """소켓이 없으면 재접속을 시도한다. Lock 내부에서 호출할 것."""
        if self.m_DBClientSocket is None:
            return self.Connect()
        return True

    def _ExecuteNoLock(self, Query: str, AutoCommit: bool) -> bool:
        """Lock 없이 DML 쿼리를 실행한다. (SqlQuery/Execute 내부 전용)"""
        if self.m_DBClientSocket is None:
            if not self.Connect():
                return False

        req = DB_QUERY_REQ_T()
        req.m_QueryId   = self.m_QueryId
        self.m_QueryId += 1
        req.m_QueryType = QUERY_TYPE_UPDATE
        req.m_SegFlag   = NO_SEG
        req.m_Commit    = 1 if AutoCommit else 2
        req.m_Query     = Query

        res = DB_QUERY_RES_T()

        if self.m_DBClientSocket.SendAndWaitPacket(
            DB_QUERY_REQ, req.pack(), req.size(),
            DB_QUERY_RES, res
        ) > 0:
            self.m_Error = res.m_Error
            return bool(res.m_Result)
        return False

    def _DecodeBulkData(self,
                        Result: QueryResult,
                        DataBuf: bytes) -> bool:
        """
        바이너리 버퍼에서 전체 레코드셋을 디코딩하여 QueryResult에 저장한다.
        각 컬럼 : [col_data_size(4, network order)][col_data(col_data_size)]
        """
        Result.m_Param = frDbParam()
        Result.m_Param.SetCol(Result.m_ColCnt)

        offset = 0
        for _ in range(Result.m_RowCnt):
            record = frDbRecord()
            record.m_Col    = Result.m_ColCnt
            record.m_Values = []

            for _ in range(Result.m_ColCnt):
                col_size = struct.unpack_from("!I", DataBuf, offset)[0]
                offset  += 4
                value    = DataBuf[offset: offset + col_size].decode(
                    "utf-8", errors="replace"
                )
                offset  += col_size
                record.m_Values.append(value)

            Result.m_Param.AddRecord(record)

        Result.m_Param.SetRow(Result.m_RowCnt)
        Result.m_Buf = Result.m_Param.GetValue()
        return True