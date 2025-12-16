import time
import threading
import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 필요시 로거 import (없으면 print로 대체)
try:
    from Class.Event.FrLogger import FrLogger
    logger_inst = FrLogger.get_instance()
    def log_error(msg): logger_inst.write(f"[ERROR] {msg}")
except ImportError:
    def log_error(msg): print(f"[ERROR] {msg}")

# -------------------------------------------------------
# FrRunTimeRecord Class
# 단일 측정 항목의 통계 저장
# -------------------------------------------------------
class FrRunTimeRecord:
    def __init__(self):
        self.cnt = 0            # 호출 횟수
        self.total_sec = 0.0    # 누적 시간 (초 단위, 실수형)
        self.start_time = 0.0   # 시작 시간
        self.is_running = False # 측정 중 여부 Flag

# -------------------------------------------------------
# FrRunTimeLogger Class (Singleton)
# 전체 측정 기록 관리
# -------------------------------------------------------
class FrRunTimeLogger:
    _instance = None
    _lock = threading.Lock() # 싱글톤 인스턴스 생성용 락

    def __init__(self):
        self._enable = True
        # 구조: { "ThreadID_LogID": { "Tag": FrRunTimeRecord } }
        self._run_time_map = {} 
        self._mutex = threading.Lock() # 데이터 접근용 락

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = FrRunTimeLogger()
        return cls._instance

    def enable(self):
        self._enable = True

    def disable(self):
        self._enable = False

    def mark_start(self, p_id, p_tag):
        if not self._enable:
            return

        # C++: ThreadID + "_" + ID
        thread_id = threading.get_ident()
        new_id = f"{thread_id}_{p_id}"

        with self._mutex:
            # 1. ID 레벨 맵 확인 및 생성
            if new_id not in self._run_time_map:
                self._run_time_map[new_id] = {}
            
            rec_map = self._run_time_map[new_id]

            # 2. Tag 레벨 레코드 확인 및 생성
            if p_tag not in rec_map:
                rec_map[p_tag] = FrRunTimeRecord()
            
            rec = rec_map[p_tag]

            # 3. 시작 시간 기록
            if not rec.is_running:
                rec.start_time = time.perf_counter()
                rec.is_running = True
            else:
                log_error(f"Try to mark start at not-completed {new_id}, {p_tag}")

    def mark_end(self, p_id, p_tag):
        if not self._enable:
            return

        thread_id = threading.get_ident()
        new_id = f"{thread_id}_{p_id}"

        with self._mutex:
            # 맵 탐색
            rec_map = self._run_time_map.get(new_id)
            if not rec_map:
                log_error(f"Failed to find {new_id}")
                return

            rec = rec_map.get(p_tag)
            if not rec:
                log_error(f"Failed to find {new_id}.{p_tag}")
                return

            # 종료 시간 기록 및 누적
            if rec.is_running:
                end_time = time.perf_counter()
                duration = end_time - rec.start_time
                
                rec.total_sec += duration
                rec.cnt += 1
                rec.is_running = False
            else:
                log_error(f"Try to mark end at not-started {new_id}, {p_tag}")

    def print_log(self):
        if not self._enable:
            return

        print("[FrRunTimeLogger::print]==============================")
        
        with self._mutex:
            for key, rec_map in self._run_time_map.items():
                print(f"[{key}]")
                for tag, rec in rec_map.items():
                    # 초 단위 실수를 sec / millisecond 정수로 변환 (C++ 포맷 호환)
                    sec_part = int(rec.total_sec)
                    ms_part = int((rec.total_sec - sec_part) * 1000)
                    
                    print(f"\t({tag}) (cnt:{rec.cnt}),({sec_part} sec {ms_part} millitm)")
        
        print("======================================================")

# -------------------------------------------------------
# FrRunTimeMarker Class (Context Manager)
# C++ RAII 패턴 -> Python 'with' 구문 대응
# -------------------------------------------------------
class FrRunTimeMarker:
    def __init__(self, p_id, p_tag):
        self.id = p_id
        self.tag = p_tag
        self.logger = FrRunTimeLogger.get_instance()

    def __enter__(self):
        """with 블록 진입 시 자동 실행"""
        self.logger.mark_start(self.id, self.tag)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """with 블록 탈출 시 자동 실행"""
        self.logger.mark_end(self.id, self.tag)