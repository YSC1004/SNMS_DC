import sys
import os

# 라이브러리 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.MmcKeyHandler import MmcKeyHandler

def test_mmc():
    handler = MmcKeyHandler()
    
    # 1. 데이터 추가 (순서 섞어서)
    handler.add("B_Key", "Value2")
    handler.add("A_Key", "Value1")
    handler.add("C_Key", "Value3")
    
    # 2. 결과 확인 (자동 정렬되어야 함)
    # 예상: (A_Key:Value1),(B_Key:Value2),(C_Key:Value3)
    print(f"Sorted Key: {handler.get_key()}")
    
    # 3. 문자열 파싱 테스트
    raw_str = "(Z_Key:999),(X_Key:888)"
    print(f"Parsed & Sorted: {handler.get_key(raw_str)}")
    
    # 4. Make 정적 메서드
    made_str = MmcKeyHandler.make("NewKey", "NewVal", raw_str)
    print(f"Made String: {made_str}")

if __name__ == "__main__":
    test_mmc()