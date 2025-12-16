import sys
import os

# -------------------------------------------------------------
# 1. 라이브러리 경로 설정
# -------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Util.FrArgParser import FrArgParser

# -------------------------------------------------------------
# 2. 테스트 시나리오
# -------------------------------------------------------------
def main():
    print(">> Argument Parser Test Start")

    # 가상의 커맨드 라인 인자 생성
    # 실제 실행 시: ./my_program -ip 127.0.0.1 -p 8080 -d -log error -log info
    fake_argv = [
        "./my_program", 
        "-ip", "127.0.0.1", 
        "-p", "8080", 
        "-d", 
        "-log", "error", 
        "-log", "info"
    ]
    
    # 파서 초기화
    parser = FrArgParser(fake_argv)
    
    # 1. 단일 값 가져오기 (GetValue)
    ip = parser.get_value("-ip")
    port = parser.get_value("-p")
    
    print(f"1. GetValue:")
    print(f"   - IP: {ip}")     # 127.0.0.1
    print(f"   - Port: {port}") # 8080
    
    # 2. 존재 여부 확인 (DoesItExist)
    is_debug = parser.does_it_exist("-d")
    is_verbose = parser.does_it_exist("-v")
    
    print(f"2. DoesItExist:")
    print(f"   - Debug Mode (-d): {is_debug}")   # True
    print(f"   - Verbose Mode (-v): {is_verbose}") # False
    
    # 3. 리스트 값 가져오기 (GetValueList)
    logs = parser.get_value_list("-log")
    
    print(f"3. GetValueList (-log):")
    print(f"   - Logs: {logs}") # ['error', 'info']

if __name__ == "__main__":
    main()