"""
frRunTimeLogger.h / frRunTimeLogger.C  →  fr_runtime_logger.py

변환 매핑:
  frRunTimeRecord               → RunTimeRecord  (dataclass)
  frRunTimeRecordMap            → dict[str, RunTimeRecord]
  frRunTimeMap                  → dict[str, dict[str, RunTimeRecord]]
  frRunTimeLogger (싱글톤)      → RunTimeLogger  (싱글톤, threading.Lock)
  frRunTimeMarker (RAII 마커)   → RunTimeMarker  (context manager / __del__)
  frMutex / frMutexGuard        → threading.Lock + with 블록
  ftime() / timeb               → time.time() (float, 밀리초 포함)
  frLogger::GetThreadSelfId()   → threading.get_ident()

frRunTimeMarker 사용법:
  # 1) with 문 (권장 - Python 관용)
  with RunTimeMarker("proc_id", "tag_name"):
      do_something()

  # 2) 수동 (C++ 원본 스타일)
  m = RunTimeMarker("proc_id", "tag_name")
  do_something()
  del m   # __del__ 에서 mark_end 호출
"""

from __future__ import annotations

import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# RunTimeRecord  ←  frRunTimeRecord
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class RunTimeRecord:
    """
    단일 (id, tag) 쌍의 누적 실행 시간 기록.
    C++ frRunTimeRecord 대응.
    """
    type:       str   = ""
    cnt:        int   = 0       # 완료 횟수
    sec:        int   = 0       # 누적 초
    millitm:    int   = 0       # 누적 밀리초 (항상 0~999)
    start_time: float = 0.0     # mark_start 시각 (time.time())
    flag:       bool  = False   # True = 측정 중


# ══════════════════════════════════════════════════════════════════════════════
# RunTimeLogger  ←  frRunTimeLogger (싱글톤)
# ══════════════════════════════════════════════════════════════════════════════
class RunTimeLogger:
    """
    스레드별 실행 시간 측정 싱글톤 로거.

    사용:
        rtl = RunTimeLogger.get_instance()
        rtl.mark_start("proc_id", "tag")
        ...
        rtl.mark_end("proc_id", "tag")
        rtl.print()
    """

    _instance: Optional["RunTimeLogger"] = None
    _g_lock:   threading.Lock            = threading.Lock()   # 싱글톤 생성 보호

    def __init__(self):
        self._lock:         threading.Lock                              = threading.Lock()
        # { thread_id_procId : { tag : RunTimeRecord } }
        self._run_time_map: dict[str, dict[str, RunTimeRecord]]         = {}
        self._enable:       bool                                        = True

    # ── 싱글톤 ───────────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "RunTimeLogger":
        """C++ getInstance() 대응. Double-checked locking."""
        if cls._instance is None:
            with cls._g_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── 활성화 제어 ───────────────────────────────────────────────────────────

    def enable(self) -> None:
        self._enable = True

    def disable(self) -> None:
        self._enable = False

    # ── 측정 시작 ─────────────────────────────────────────────────────────────

    def mark_start(self, proc_id: str, tag: str) -> None:
        """
        측정 시작 (markStart).
        스레드 ID 를 proc_id 앞에 prefix 로 붙여 스레드별로 분리.
        """
        if not self._enable:
            return

        tid    = threading.get_ident()
        new_id = f"{tid}_{proc_id}"

        with self._lock:
            rec_map = self._run_time_map.setdefault(new_id, {})

            if tag not in rec_map:
                rec           = RunTimeRecord()
                rec.start_time = time.time()
                rec.flag       = True
                rec_map[tag]   = rec
            else:
                rec = rec_map[tag]
                if not rec.flag:
                    rec.start_time = time.time()
                    rec.flag       = True
                else:
                    logger.error(
                        "mark_start: already started [%s, %s]", new_id, tag
                    )

    # ── 측정 종료 ─────────────────────────────────────────────────────────────

    def mark_end(self, proc_id: str, tag: str) -> None:
        """
        측정 종료 (markEnd).
        경과 시간을 누적하고 cnt 를 증가시킨다.
        """
        if not self._enable:
            return

        tid    = threading.get_ident()
        new_id = f"{tid}_{proc_id}"

        with self._lock:
            rec_map = self._run_time_map.get(new_id)
            if rec_map is None:
                logger.error("mark_end: id not found [%s]", new_id)
                return

            rec = rec_map.get(tag)
            if rec is None:
                logger.error("mark_end: tag not found [%s.%s]", new_id, tag)
                return

            if not rec.flag:
                logger.error(
                    "mark_end: not started [%s, %s]", new_id, tag
                )
                return

            end_time = time.time()
            elapsed  = end_time - rec.start_time   # 초 단위 float

            # C++ 원본과 동일하게 sec / millitm 분리하여 누적
            e_sec    = int(elapsed)
            e_milli  = int(round((elapsed - e_sec) * 1000))

            if e_sec >= 0 and e_milli >= 0:
                rec.sec     += e_sec
                rec.millitm += e_milli
                # millitm 올림 처리 (C++ 원본 동일)
                if rec.millitm >= 1000:
                    rec.sec    += rec.millitm // 1000
                    rec.millitm = rec.millitm % 1000
                rec.cnt  += 1
                rec.flag  = False
            else:
                logger.error("mark_end: invalid elapsed values [%s.%s]", new_id, tag)

    # ── 출력 ──────────────────────────────────────────────────────────────────

    def print(self) -> None:
        """누적 측정 결과를 출력한다 (print / printf 대응)."""
        if not self._enable:
            return

        print("[RunTimeLogger::print]==============================")
        with self._lock:
            for id_key, rec_map in self._run_time_map.items():
                print(f"[{id_key}]")
                for tag, rec in rec_map.items():
                    print(
                        f"\t({tag}) "
                        f"(cnt:{rec.cnt}),"
                        f"({rec.sec} sec {rec.millitm} millitm)"
                    )
        print("=====================================================")

    def get_stats(self) -> dict:
        """측정 결과를 dict 로 반환 (Python 추가 기능)."""
        with self._lock:
            return {
                id_key: {
                    tag: {
                        "cnt":     rec.cnt,
                        "sec":     rec.sec,
                        "millitm": rec.millitm,
                        "total_ms": rec.sec * 1000 + rec.millitm,
                        "avg_ms":  (rec.sec * 1000 + rec.millitm) // rec.cnt
                                    if rec.cnt else 0,
                    }
                    for tag, rec in rec_map.items()
                }
                for id_key, rec_map in self._run_time_map.items()
            }


# ══════════════════════════════════════════════════════════════════════════════
# RunTimeMarker  ←  frRunTimeMarker (RAII 마커)
# ══════════════════════════════════════════════════════════════════════════════
class RunTimeMarker:
    """
    생성 시 mark_start, 소멸/종료 시 mark_end 를 자동 호출하는 RAII 마커.
    C++ frRunTimeMarker 대응.

    사용법:
        # 권장: context manager
        with RunTimeMarker("proc_id", "db_query"):
            result = db.execute(sql)

        # C++ 스타일 (수동)
        marker = RunTimeMarker("proc_id", "db_query")
        result = db.execute(sql)
        del marker
    """

    def __init__(
        self,
        proc_id: str,
        tag:     str,
        rtl:     Optional[RunTimeLogger] = None,
    ):
        self._id     = proc_id
        self._tag    = tag
        self._logger = rtl if rtl is not None else RunTimeLogger.get_instance()
        self._logger.mark_start(self._id, self._tag)

    def __del__(self):
        """C++ ~frRunTimeMarker() → markEnd 자동 호출."""
        try:
            self._logger.mark_end(self._id, self._tag)
        except Exception:
            pass

    # ── context manager 지원 ─────────────────────────────────────────────────

    def __enter__(self) -> "RunTimeMarker":
        return self

    def __exit__(self, *_) -> None:
        self._logger.mark_end(self._id, self._tag)
        # __del__ 에서 중복 호출 방지를 위해 flag 비활성화
        self._logger = _NoOpLogger()


class _NoOpLogger:
    """mark_end 중복 호출 방지용 더미 로거."""
    def mark_end(self, *_): pass
    def mark_start(self, *_): pass