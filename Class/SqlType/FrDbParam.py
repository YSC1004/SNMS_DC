class FrDbRecord:
    def __init__(self, values=None):
        self.m_Values = values if values else [] # List of strings
        self.m_Col = len(self.m_Values)

class FrDbParam:
    def __init__(self, query=""):
        self.m_Query = query
        self.m_Records = [] 
        self.m_ColCnt = 0
        self.m_CurrentPos = 0

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
        # Python 리스트는 동적이므로 실제로는 사용되지 않을 수 있음
        pass

    def AddRecord(self, record):
        self.m_Records.append(record)
    
    def GetValue(self):
        # C++ 코드의 m_Buf (이중 배열) 반환 대응
        return [rec.m_Values for rec in self.m_Records]

    def Rewind(self):
        self.m_CurrentPos = 0
        
    def get_all_records(self):
        return self.m_Records