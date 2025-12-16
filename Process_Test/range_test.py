import sys
import os

# 라이브러리 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Util.FrValueRangeHandler import FrValueRangeHandler

def main():
    print(">> Value Range Handler Test Start\n")
    
    handler = FrValueRangeHandler()

    # Case 1: 단순 범위 (1~4)
    src1 = "1~4"
    print(f"[Case 1] Input: '{src1}'")
    handler.do_it(src1)
    handler.print_handler()
    print("-" * 20)

    # Case 2: 콤마 분리 (1,3,5)
    src2 = "1,3,5"
    print(f"\n[Case 2] Input: '{src2}'")
    handler.do_it(src2)
    handler.print_handler()
    print("-" * 20)

    # Case 3: 복합 (1,3,5~9,11)
    src3 = "1,3,5~9,11"
    print(f"\n[Case 3] Input: '{src3}'")
    handler.do_it(src3)
    handler.print_handler()
    print("-" * 20)

    # Case 4: 결과 리스트 활용
    result_list = handler.get_result()
    print(f"\n[Case 4] Access Result List Directly (Size: {len(result_list)})")
    print(f"   List: {result_list}")

if __name__ == "__main__":
    main()