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

# 이제 Class 모듈을 찾을 수 있습니다
from Class.Util.FrTime import FrTime

# 1. 현재 시간
t1 = FrTime()
print(f"Current: {t1.get_time_string()}")

# 2. 문자열 파싱
t2 = FrTime("2024-11-20 12:30:00")
print(f"Parsed: {t2.get_year()} / {t2.get_month()}")

# 3. 연산
t3 = t1 + 3600  # 1시간 뒤
diff = t3 - t1  # 차이 (초)
print(f"Diff: {diff} sec") # 3600

# 4. 마스크 출력
mask = FrTime.TIME_ELEMENT_YEAR_MASK | FrTime.TIME_ELEMENT_MONTH_MASK
print(f"Year/Month: {t1.get_time_string_each(mask)}")