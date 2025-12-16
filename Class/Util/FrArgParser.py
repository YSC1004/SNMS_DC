import sys

class FrArgParser:
    def __init__(self, argv=None):
        """
        C++: frArgParser(int argc, char *argv[])
        argv를 입력받지 않으면 시스템 기본 sys.argv를 사용합니다.
        """
        if argv is None:
            self.m_Argv = sys.argv
        else:
            self.m_Argv = argv
            
        self.m_Argc = len(self.m_Argv)

    def get_value(self, name):
        """
        C++: char * GetValue(const char *name)
        특정 플래그(name)를 찾아서 그 '다음' 인자를 반환합니다.
        없으면 None 반환
        """
        # C++ loop: for (int i = 1; i+1 < m_Argc; i ++)
        # 1번째 인덱스(실행파일명 다음)부터 (전체길이 - 2)까지 검색
        for i in range(1, self.m_Argc - 1):
            if self.m_Argv[i] == name:
                return self.m_Argv[i+1]
        
        return None

    def get_value_list(self, name):
        """
        C++: frStringList GetValueList(const char *name)
        해당 플래그가 여러 번 나올 경우 모든 값을 리스트로 반환
        """
        value_list = []
        
        for i in range(1, self.m_Argc - 1):
            if self.m_Argv[i] == name:
                value_list.append(self.m_Argv[i+1])
                
        return value_list

    def does_it_exist(self, name):
        """
        C++: int DoesItExist(const char *name)
        플래그 존재 여부 확인 (True/False)
        """
        # 1번째 인덱스부터 끝까지 검색
        for i in range(1, self.m_Argc):
            if self.m_Argv[i] == name:
                return True
        
        return False