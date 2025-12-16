import sys
import os

# -------------------------------------------------------
# 1. FrDbRecord Class
#    DB의 한 행(Row) 데이터를 저장
# -------------------------------------------------------
class FrDbRecord:
    def __init__(self, values=None):
        # C++에서는 char** m_Values로 관리됨
        # Python에서는 문자열 리스트로 관리 (None 값은 빈 문자열 처리됨을 가정)
        self.m_Values = values if values else [] 
        self.m_Col = len(self.m_Values)
        self.m_ColSize = [] # C++와의 호환성을 위해 속성만 유지 (실제론 len(str) 사용)

    def get_value(self, index):
        """특정 컬럼의 값 가져오기 (Safe Access)"""
        if 0 <= index < self.m_Col:
            return self.m_Values[index]
        return ""

# -------------------------------------------------------
# 2. FrDbParam Class
#    쿼리 문자열과 결과 레코드셋(List of FrDbRecord)을 관리
# -------------------------------------------------------
class FrDbParam:
    def __init__(self, query=""):
        self.m_Query = query
        self.m_Records = []      # List[FrDbRecord]
        self.m_ColCnt = 0
        self.m_CurrentPos = 0    # Iterator용 커서 위치

    # --- Getters / Setters ---
    def GetQuery(self):
        return self.m_Query
    
    def SetQuery(self, query):
        self.m_Query = query
    
    def SetCol(self, cnt):
        self.m_ColCnt = cnt
        
    def GetCol(self):
        return self.m_ColCnt

    def GetRow(self):
        return len(self.m_Records)

    def SetRow(self, row):
        # Python 리스트는 동적으로 할당되므로 C++처럼 미리 메모리를 잡을 필요가 없음
        pass

    # --- Data Manipulation ---
    def AddRecord(self, record):
        """레코드 추가"""
        self.m_Records.append(record)
    
    def GetValue(self):
        """
        전체 데이터를 2차원 리스트(List of Lists)로 반환
        C++의 m_Buf (char**) 대응
        """
        return [rec.m_Values for rec in self.m_Records]

    def GetField(self, row, col):
        """특정 행/열의 값 가져오기"""
        if 0 <= row < len(self.m_Records):
            return self.m_Records[row].get_value(col)
        return ""

    # --- Iterator Methods (Rewind / Next) ---
    def Rewind(self):
        """커서 위치 초기화"""
        self.m_CurrentPos = 0
        
    def Next(self):
        """
        다음 레코드를 반환하고 커서를 이동 (C++ 스타일 순회용)
        """
        if self.m_CurrentPos < len(self.m_Records):
            record = self.m_Records[self.m_CurrentPos]
            self.m_CurrentPos += 1
            return record
        return None

    def get_all_records(self):
        """전체 레코드 객체 리스트 반환"""
        return self.m_Records

    # --- Debugging ---
    def Print(self):
        """데이터 확인용 출력"""
        print(f"--- FrDbParam Dump (Rows: {self.GetRow()}, Cols: {self.GetCol()}) ---")
        for i, rec in enumerate(self.m_Records):
            print(f"[{i}] {rec.m_Values}")
        print("---------------------------------------------------------------")