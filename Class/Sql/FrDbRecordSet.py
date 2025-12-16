import sys
import os

# -------------------------------------------------------
# 1. 프로젝트 경로 설정
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))

if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# 2. 모듈 Import
# -------------------------------------------------------
# FrDbParam 위치: Class/SqlType/FrDbParam.py
from Class.SqlType.FrDbParam import FrDbParam, FrDbRecord
# FrBaseType 위치: Class/Sql/FrBaseType.py
from Class.Sql.FrBaseType import EDB_TYPE

# -------------------------------------------------------
# 3. FrDbRecordSet Class
#    DB 커서(Cursor)를 감싸서 Iterator 패턴(MoveNext)으로
#    데이터를 한 줄씩 공급하는 클래스
# -------------------------------------------------------
class FrDbRecordSet:
    def __init__(self, db_session, db_kind, cursor=None):
        """
        C++: frDbRecordSet(frDbSession* DbSession, int DbKind)
        """
        self.m_IsValid = False
        self.m_IsEndRow = False
        self.m_DbSession = db_session
        self.m_DbKind = db_kind
        
        # Python DB-API Cursor 객체를 직접 보관
        self.m_Cursor = cursor
        
        # 데이터를 담을 컨테이너 생성
        self.m_DbParam = FrDbParam()
        
        # C++의 DescList, DefList, FetchInfo는 Python cursor 내부에서 처리되므로 제거됨
        
        # 커서가 유효하다면 컬럼 메타데이터 세팅
        if self.m_Cursor and self.m_Cursor.description:
            self.m_IsValid = True
            col_cnt = len(self.m_Cursor.description)
            self.SetCol(col_cnt)

    def __del__(self):
        """
        C++: ~frDbRecordSet()
        소멸 시 커서를 닫아줌
        """
        if self.m_Cursor:
            try:
                self.m_Cursor.close()
            except:
                pass
        self.m_Cursor = None
        # m_DbParam 등은 Python GC가 알아서 해제함

    # ---------------------------------------------------
    # Proxy Methods (FrDbParam 연결)
    # ---------------------------------------------------
    def GetCol(self):
        return self.m_DbParam.GetCol()

    def GetRow(self):
        return self.m_DbParam.GetRow()

    def SetCol(self, col):
        self.m_DbParam.SetCol(col)

    def SetRow(self, row):
        self.m_DbParam.SetRow(row)

    # ---------------------------------------------------
    # Core Logic (Fetch)
    # ---------------------------------------------------
    def MoveNext(self):
        """
        C++: frDbRecord* MoveNext()
        DB 커서에서 한 줄(Row)을 읽어와 FrDbRecord로 반환하고 내부 목록에 저장
        """
        record = None

        if self.GetCol() > 0:
            if not self.m_IsEndRow and self.m_Cursor:
                # C++: m_DbSession->_FetchData(m_FetchInfo)
                # Python: cursor.fetchone() -> 한 줄씩 Fetch
                row_data = self.m_Cursor.fetchone()
                
                if row_data:
                    # C++ 호환성을 위해 모든 데이터를 문자열로 변환
                    # (None 값은 빈 문자열("")로 변환)
                    str_values = [str(val) if val is not None else "" for val in row_data]
                    
                    record = FrDbRecord(str_values)
                    self.m_DbParam.AddRecord(record)
                else:
                    # 더 이상 데이터가 없음 (End of Fetch)
                    self.m_IsEndRow = True
        
        return record

    def IsValid(self):
        return self.m_IsValid