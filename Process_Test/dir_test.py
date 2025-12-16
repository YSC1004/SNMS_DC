import sys
import os

# -------------------------------------------------------------
# [필수] 부모 폴더(SNMS_DC)를 라이브러리 경로에 추가
# -------------------------------------------------------------
# 현재 파일(time_test.py)의 위치
current_dir = os.path.dirname(os.path.abspath(__file__))
# 부모 폴더(SNMS_DC) 위치 계산
project_root = os.path.abspath(os.path.join(current_dir, '..'))

# 경로에 추가
if project_root not in sys.path:
    sys.path.append(project_root)
# -------------------------------------------------------------

from Class.Util.FrDirReader import FrDirReader, READ_TYPE

# 1. 객체 생성 및 디렉토리 읽기
reader = FrDirReader("/home/ncadmin/log")

# 2. 파일 목록 순회
print(f"Has files: {reader.has_more_file()}")
while reader.has_more_file():
    filename = reader.next()
    print(f"Found: {filename}")

# 3. 유틸리티 사용
file_size = FrDirReader.get_file_size("/home/ncadmin/test.txt")
print(f"File Size: {file_size}")

# 4. 파일 생성
FrDirReader.file_create_and_write("test_python.txt", "Hello Python")