import sys
import os
import time

# 라이브러리 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Util.ElaspedTime import ElaspedTime

def main():
    print(">> ElapsedTime Test Start")

    # 1. 객체 생성 및 시작
    timer = ElaspedTime()
    print("Timer Started...")

    # 2. 지연 시뮬레이션 (1.5초 대기)
    sleep_time = 1.5
    print(f"Sleeping for {sleep_time} seconds...")
    time.sleep(sleep_time)

    # 3. 종료 시간 기록
    timer.End()

    # 4. 결과 출력
    # 예상: 밀리초는 약 1500, 초는 1
    ms = timer.GetElaspedMiliSec()
    sec = timer.GetElaspedSec()

    print(f"Elapsed MS : {ms} ms")
    print(f"Elapsed Sec: {sec} sec")

    # 오차 범위 확인 (시스템 부하에 따라 약간의 오차는 정상)
    if 1500 <= ms <= 1600:
        print(">> Test Result: PASS (Time matches)")
    else:
        print(">> Test Result: Warning (Time gap is large)")

if __name__ == "__main__":
    main()