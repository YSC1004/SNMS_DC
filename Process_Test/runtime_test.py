import sys
import os
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Util.FrRunTimeLogger import FrRunTimeLogger, FrRunTimeMarker

def perform_task_A():
    # [방법 1] Python 권장 방식: with 구문 (Context Manager)
    # 블록을 벗어나면 자동으로 mark_end가 호출됨
    with FrRunTimeMarker("Process", "Task_A"):
        time.sleep(0.5) # 500ms 작업 시뮬레이션

def perform_task_B():
    # [방법 2] 수동 호출 (C++ 방식과 유사)
    logger = FrRunTimeLogger.get_instance()
    logger.mark_start("Process", "Task_B")
    try:
        time.sleep(0.2) # 200ms 작업 시뮬레이션
    finally:
        # 예외가 발생해도 시간 측정 종료를 보장
        logger.mark_end("Process", "Task_B")

def main():
    print(">> RunTime Logger Test Start")
    
    logger = FrRunTimeLogger.get_instance()
    
    # 여러 번 실행하여 누적 테스트
    for i in range(3):
        print(f"Iteration {i+1}...")
        perform_task_A()
        perform_task_B()

    # 결과 출력
    print("\n>> Final Stats:")
    logger.print_log()

if __name__ == "__main__":
    main()