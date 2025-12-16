import sys
import re

class FrTokenizer:
    def __init__(self, source=""):
        self.m_Source = source
        self.m_Delimiter = ""
        self.m_TokenVector = [] # Python list
        self.m_CurrentIdx = 0   # Iterator용 인덱스

    def clear(self):
        self.m_TokenVector = []
        self.m_CurrentIdx = 0

    def set_source(self, source):
        self.clear()
        self.m_Source = source

    def set_delimiter(self, delimiter):
        self.m_Delimiter = delimiter

    def before(self, delimiter=None):
        """
        C++: string Before(const char *delimiter)
        구분자에 포함된 '어떤 문자라도' 처음 발견되면, 그 앞부분을 반환
        """
        target_delim = delimiter if delimiter else self.m_Delimiter
        if not target_delim:
            return self.m_Source

        # C++ 로직: 구분자 문자셋 중 가장 먼저 나오는 위치 찾기
        min_idx = len(self.m_Source)
        found = False

        for char in target_delim:
            idx = self.m_Source.find(char)
            if idx != -1 and idx < min_idx:
                min_idx = idx
                found = True
        
        if found:
            return self.m_Source[:min_idx]
        
        return self.m_Source

    def after(self, delimiter=None):
        """
        C++: string After(const char *delimiter)
        구분자에 포함된 '어떤 문자라도' 처음 발견되면, 그 뒷부분을 반환
        """
        target_delim = delimiter if delimiter else self.m_Delimiter
        if not target_delim:
            return ""

        # C++ 로직: 구분자 문자셋 중 가장 먼저 나오는 위치 찾기
        min_idx = len(self.m_Source)
        found = False

        for char in target_delim:
            idx = self.m_Source.find(char)
            if idx != -1 and idx < min_idx:
                min_idx = idx
                found = True
        
        if found:
            # C++ 로직상 해당 구분자 문자 바로 다음부터 끝까지 반환
            return self.m_Source[min_idx+1:]
        
        return ""

    def do_it(self):
        """
        C++: void DoIt()
        구분자를 '문자들의 집합'으로 간주하여 토큰화 (strtok 스타일)
        예: Source="A,B;C", Delim=",;" -> ["A", "B", "C"]
        """
        self.clear()
        if not self.m_Source or not self.m_Delimiter:
            return

        # 정규표현식 문자셋 [] 을 사용하여 구현
        # escape를 통해 특수문자(., | 등)도 문자로 인식하게 함
        pattern = f"[{re.escape(self.m_Delimiter)}]+"
        
        # re.split은 구분자를 기준으로 자름
        tokens = re.split(pattern, self.m_Source)
        
        # C++ 로직은 연속된 구분자나 빈 토큰을 무시하는 경향이 있음 (size > 0 체크)
        # 따라서 빈 문자열 제거 필터링 수행
        self.m_TokenVector = [t for t in tokens if t]
        self.m_CurrentIdx = 0

    def do_it2(self):
        """
        C++: void DoIt2()
        구분자를 '하나의 문자열'로 간주하여 토큰화 (Python split 스타일)
        예: Source="A--B--C", Delim="--" -> ["A", "B", "C"]
        """
        self.clear()
        if not self.m_Source:
            return
            
        if not self.m_Delimiter:
            self.m_TokenVector.append(self.m_Source)
            return

        # Python의 split이 C++ DoIt2(strncmp 방식)와 동일하게 동작
        self.m_TokenVector = self.m_Source.split(self.m_Delimiter)
        
        # C++ 코드는 마지막에 남은 잔여 문자열도 push함. 
        # Python split은 자동으로 처리하므로 추가 작업 불필요.
        # 단, C++ 코드 특성상 마지막 빈 문자열 처리가 다를 수 있으나 
        # 일반적인 사용처에서는 split() 결과가 더 직관적임.
        
        self.m_CurrentIdx = 0

    def count_token(self):
        return len(self.m_TokenVector)

    def has_more_token(self):
        return self.m_CurrentIdx < len(self.m_TokenVector)

    def next(self):
        """
        C++: string Next()
        """
        if self.has_more_token():
            token = self.m_TokenVector[self.m_CurrentIdx]
            self.m_CurrentIdx += 1
            return token
        return ""

    def get_token(self, no):
        """
        C++: string GetToken(int no) (1-based index)
        """
        idx = no - 1
        if 0 <= idx < len(self.m_TokenVector):
            return self.m_TokenVector[idx]
        return ""

    def find_token(self, token, start_pos=0):
        """
        C++: int FindToken(string Token, unsigned int StartPos)
        """
        try:
            # start_pos부터 검색
            return self.m_TokenVector.index(token, start_pos)
        except ValueError:
            return -1

    def print_tokens(self):
        """
        C++: void Print()
        """
        print(f"frTokenizer ({self.m_Source}),({self.m_Delimiter})")
        for t in self.m_TokenVector:
            print(f"\t{t}")