import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Util.FrTokenizer import FrTokenizer
from Class.Util.FrBaseList import FrStringList

class FrValueRangeHandler:
    def __init__(self):
        """
        C++: frValueRangeHandler(bool memOwner)
        Python은 메모리 관리가 자동이므로 memOwner 플래그 불필요
        """
        self.m_List = FrStringList() # 결과 저장용 리스트
        self.m_Source = ""

    def clear(self):
        """
        C++: void Clear()
        """
        self.m_List.clear()

    def do_it(self, source):
        """
        C++: void DoIt(const char *source)
        범위 문자열 파싱 로직
        Format 예시: "1~4", "1,3,5", "1,3,5~9,11"
        """
        self.clear()
        self.m_Source = source
        
        if not source:
            return

        # 1차 분리: 콤마(,) 기준
        token_handler = FrTokenizer(self.m_Source)
        token_handler.set_delimiter(",")
        token_handler.do_it()

        while token_handler.has_more_token():
            token = token_handler.next()
            
            # 2차 분리: 물결(~) 기준 (범위 확인)
            token_handler2 = FrTokenizer(token)
            token_handler2.set_delimiter("~")
            token_handler2.do_it()
            
            cnt = token_handler2.count_token()

            if cnt == 1:
                # 단일 값 (예: "3")
                val = token_handler2.get_token(1)
                self.m_List.append(val)
                
            elif cnt == 2:
                # 범위 값 (예: "1~4")
                try:
                    # C++ atoi 대응 -> int()
                    start_val = int(token_handler2.get_token(1))
                    end_val = int(token_handler2.get_token(2))
                    
                    # for (int i = from; i <= to; i ++)
                    for i in range(start_val, end_val + 1):
                        self.m_List.append(str(i))
                except ValueError:
                    print(f"[Error] Invalid number format in range: {token}")
            else:
                print(f"[Error] Value is strange ({self.m_Source})")

    def get_result(self):
        """
        C++: frCharPtrList * GetResult()
        """
        return self.m_List

    def print_handler(self):
        """
        C++: void Print()
        """
        print(f"frValueRangeHandler ({self.m_Source})")
        if self.m_List:
            for val in self.m_List:
                print(f"\t{val}")
        else:
            print("\tResult is Empty")