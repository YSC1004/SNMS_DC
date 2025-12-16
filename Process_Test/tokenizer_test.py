import sys
import os

# 라이브러리 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Util.FrTokenizer import FrTokenizer

def main():
    print(">> Tokenizer Test Start\n")

    # 1. DoIt 테스트 (문자 집합 기준 분리)
    # 콤마(,)와 세미콜론(;)을 모두 구분자로 사용
    src1 = "User=Admin,IP=127.0.0.1;Port=8080"
    delim1 = ",;"
    
    tok = FrTokenizer()
    tok.set_source(src1)
    tok.set_delimiter(delim1)
    
    print(f"[1] DoIt Test (Source: '{src1}', Delim: '{delim1}')")
    tok.do_it()
    tok.print_tokens()
    
    print("Iterating:")
    while tok.has_more_token():
        print(f" - {tok.next()}")

    print("-" * 30)

    # 2. DoIt2 테스트 (문자열 기준 분리)
    # 구분자가 "--" (두 글자)
    src2 = "Apple--Banana--Orange"
    delim2 = "--"
    
    print(f"\n[2] DoIt2 Test (Source: '{src2}', Delim: '{delim2}')")
    tok.set_source(src2)
    tok.set_delimiter(delim2)
    tok.do_it2() # 문자열 전체 매칭
    tok.print_tokens()

    print("-" * 30)

    # 3. Before / After 테스트
    src3 = "Key:Value"
    delim3 = ":"
    tok.set_source(src3)
    
    print(f"\n[3] Before/After Test (Source: '{src3}', Delim: '{delim3}')")
    print(f"   Before: {tok.before(delim3)}") # Key
    print(f"   After : {tok.after(delim3)}")  # Value

if __name__ == "__main__":
    main()