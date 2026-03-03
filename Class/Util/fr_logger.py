"""
frLogger.h / frLogger.C  →  fr_logger.py

변환 매핑:
  frLogNode                    → LogNode      (패키지/피처 트리 노드)
  frLogDef                     → LogDef       (파일 단위 로거 정의)
  frLogger                     → Logger       (싱글톤 로거)

  pthread_mutex_t m_LogLock    → threading.Lock
  static frLogger* m_Logger    → Logger._instance (싱글톤)
  FILE* m_Out                  → logging.FileHandler
  dup2(stdout/stderr)          → 핸들러를 루트 로거에 추가

매크로 → Python 함수/데코레이터:
  frDEFINE_DBG_FTR(pkg, ftr)   → log_def = LogDef(pkg, ftr)
  frCORE_ERROR(msg)            → Logger.core_error(msg)   or log_def.error(msg)
  frDEBUG((level, msg))        → log_def.debug(level, msg)
  frSTD_OUT(msg)               → Logger.std_out(msg)

설계 원칙:
  - Python 표준 logging 모듈을 백엔드로 사용
  - LogNode 트리로 패키지/피처별 레벨 제어 유지 (C++ 원본 구조 보존)
  - 싱글톤 Logger 는 logging.Logger 래퍼
  - 스레드 안전: threading.Lock (C++ 주석처리 된 mutex 복원)
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import threading
from datetime import datetime
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
# LogNode  ←  frLogNode
# ══════════════════════════════════════════════════════════════════════════════
class LogNode:
    """
    패키지 / 피처 계층의 노드.
    레벨(int)로 활성화 여부를 제어한다.
    C++ frLogNode 와 동일한 구조.
    """

    def __init__(self, name: str = ""):
        self._name:  str                      = name
        self._level: int                      = 0
        self._map:   dict[str, "LogNode"]     = {}

    # ── 레벨 제어 ────────────────────────────────────────────────────────────

    def enable(self, level: int) -> None:
        """자신과 하위 노드 모두 level 로 활성화."""
        self._level = level
        for child in self._map.values():
            child.enable(level)

    def is_enable(self, level: int) -> bool:
        """현재 레벨이 요청 레벨 이상이면 True."""
        return self._level >= level

    # ── 트리 관리 ────────────────────────────────────────────────────────────

    def add(self, name_or_node) -> Optional["LogNode"]:
        """이름 또는 LogNode 를 자식으로 추가. 중복이면 None 반환."""
        if isinstance(name_or_node, str):
            if name_or_node in self._map:
                return None
            node = LogNode(name_or_node)
            self._map[name_or_node] = node
            return node
        else:  # LogNode 인스턴스
            node: LogNode = name_or_node
            if node._name in self._map:
                return None
            self._map[node._name] = node
            return node

    def find(self, name: str) -> Optional["LogNode"]:
        """이름으로 자식 노드를 검색. 없으면 None."""
        return self._map.get(name)

    def show(self) -> str:
        """자식 노드의 이름과 레벨을 문자열로 반환."""
        return "".join(
            f"{node._name}({node._level})"
            for node in self._map.values()
        )


# ══════════════════════════════════════════════════════════════════════════════
# LogDef  ←  frLogDef  (파일/모듈 단위 로거 정의)
# ══════════════════════════════════════════════════════════════════════════════
class LogDef:
    """
    특정 (package, feature) 쌍에 연결된 로거 정의.
    C++ 매크로 frDEFINE_DBG_FTR(("Util","frTokenizer")) 대응:

        log_def = LogDef("Util", "frTokenizer")
    """

    def __init__(self, package: str, feature: str):
        # 싱글톤 Logger 자동 생성
        if Logger._instance is None:
            Logger._instance = Logger()
        self._log_node: Optional[LogNode] = Logger._instance.register(package, feature)
        self._package   = package
        self._feature   = feature

    # ── 활성화 확인 ──────────────────────────────────────────────────────────

    def is_enable(self, level: int = 1) -> bool:
        """
        C++ IsEnable(level, ...) 대응.
        LogNode 레벨이 요청 레벨 이상이면 True.
        """
        return bool(self._log_node and self._log_node.is_enable(level))

    # ── 쓰기 ─────────────────────────────────────────────────────────────────

    def write(self, msg: str, level: int = 1) -> None:
        """C++ Write(format, ...) 대응."""
        if self.is_enable(level):
            Logger._instance.write(msg)

    def debug(self, level: int, msg: str, *args) -> None:
        """
        frDEBUG((level, msg)) 매크로 대응.
        레벨 활성화 시 [timestamp](file:line) prefix 와 함께 기록.
        """
        if self.is_enable(level):
            ts  = Logger.get_timestamp()
            out = f"[{ts}] [DEBUG:{level}] [{self._package}/{self._feature}] {msg}"
            if args:
                out = out % args
            Logger._instance.write(out)

    def error(self, msg: str, *args) -> None:
        """
        frCORE_ERROR(msg) 매크로 대응 (LogDef 레벨).
        """
        Logger.core_error(msg, *args)


# ══════════════════════════════════════════════════════════════════════════════
# Logger  ←  frLogger  (싱글톤)
# ══════════════════════════════════════════════════════════════════════════════
class Logger:
    """
    전역 싱글톤 로거.
    C++ static frLogger* m_Logger 와 동일한 역할.

    사용:
        Logger.open("/var/log/snms/snms.log")
        Logger.enable(3)
        Logger.enable("Util", 2)
        Logger.enable("Util", "frTokenizer", 3)
        Logger.core_error("Something went wrong: %s", reason)
        Logger.std_out("Hello %s\\n", name)
    """

    _instance:  Optional["Logger"]  = None
    _log_lock:  threading.Lock      = threading.Lock()
    _ts_lock:   threading.Lock      = threading.Lock()

    def __init__(self):
        self._root:    LogNode              = LogNode("root")
        self._handler: Optional[logging.Handler] = None
        # 내부 Python logger (실제 파일/콘솔 출력)
        self._py_logger: logging.Logger    = logging.getLogger("frLogger")
        self._py_logger.setLevel(logging.DEBUG)
        # 기본 콘솔 핸들러 (Open() 호출 전 출력용)
        if not self._py_logger.handlers:
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(self._make_formatter())
            self._py_logger.addHandler(ch)

    # ── 파일 열기 ─────────────────────────────────────────────────────────────

    @staticmethod
    def open(log_file_name: str, dup_stdout_stderr: bool = True) -> None:
        """
        로그 파일을 열고 핸들러를 교체한다.
        C++ Open(logFileName, dupStdOutErr) 대응.
        RotatingFileHandler 로 구현 (C++ 의 append 모드 + FD_CLOEXEC 대응).
        """
        if Logger._instance is None:
            Logger._instance = Logger()
        inst = Logger._instance

        # 기존 핸들러 제거
        for h in inst._py_logger.handlers[:]:
            inst._py_logger.removeHandler(h)
            h.close()

        # 파일 핸들러 추가
        fh = logging.handlers.RotatingFileHandler(
            log_file_name,
            mode="a",
            maxBytes=50 * 1024 * 1024,   # 50MB
            backupCount=10,
            encoding="utf-8",
        )
        fh.setFormatter(inst._make_formatter())
        inst._py_logger.addHandler(fh)
        inst._handler = fh

        # dup_stdout_stderr: stdout/stderr 도 같은 파일로 리다이렉트
        if dup_stdout_stderr:
            sh = logging.StreamHandler(sys.stdout)
            sh.setFormatter(inst._make_formatter())
            inst._py_logger.addHandler(sh)

    # ── 노드 등록 ─────────────────────────────────────────────────────────────

    def register(self, package: str, feature: str) -> Optional[LogNode]:
        """
        (package, feature) 노드를 트리에 등록하고 반환.
        C++ Register() 대응.
        """
        node = self._root.find(package)
        if node is None:
            node = LogNode(package)
            self._root.add(node)
        if node.find(feature) is None:
            return node.add(feature)
        return node.find(feature)

    # ── 활성화 제어 ───────────────────────────────────────────────────────────

    @staticmethod
    def enable(level_or_package, level_or_feature=None, level: int = None) -> None:
        """
        오버로드 통합:
          enable(level)                      → 루트 전체 활성화
          enable(package, level)             → 패키지 활성화
          enable(package, feature, level)    → 피처 활성화
        """
        inst = Logger._instance
        if inst is None:
            return
        if level is not None:
            # enable(package, feature, level)
            node = inst._root.find(level_or_package)
            if node:
                node = node.find(level_or_feature)
                if node:
                    node.enable(level)
        elif level_or_feature is not None:
            # enable(package, level)
            node = inst._root.find(level_or_package)
            if node:
                node.enable(level_or_feature)
        else:
            # enable(level)
            inst._root.enable(level_or_package)

    @staticmethod
    def disable(package: str = None, feature: str = None) -> None:
        """
        레벨을 0 으로 설정해 비활성화.
        C++ Disable() / Disable(pkg) / Disable(pkg, ftr) 대응.
        """
        if package is None:
            Logger.enable(0)
        elif feature is None:
            Logger.enable(package, 0)
        else:
            Logger.enable(package, feature, 0)

    @staticmethod
    def is_enable(package: str, feature: str, level: int) -> bool:
        """C++ IsEnable(package, feature, level) 대응."""
        inst = Logger._instance
        if inst is None:
            return False
        if inst._root.is_enable(level):
            return True
        node = inst._root.find(package)
        if node is None:
            return False
        if node.is_enable(level):
            return True
        node = node.find(feature)
        return node.is_enable(level) if node else False

    # ── 출력 ──────────────────────────────────────────────────────────────────

    def write(self, msg: str) -> None:
        """C++ Write(char*) 대응. 내부 직접 출력."""
        with Logger._log_lock:
            self._py_logger.info(msg)

    @staticmethod
    def core_error(msg: str, *args) -> None:
        """
        frCORE_ERROR(msg) 매크로 대응.
        [timestamp](ERROR:errno) prefix 포함.
        """
        inst = Logger._instance
        if inst is None:
            Logger._instance = Logger()
            inst = Logger._instance
        errno_val = 0
        try:
            import ctypes
            errno_val = ctypes.get_errno()
        except Exception:
            pass
        ts  = Logger.get_timestamp()
        out = f"[{ts}](ERROR:{errno_val}) {msg}"
        if args:
            try:
                out = out % args
            except Exception:
                pass
        with Logger._log_lock:
            inst._py_logger.error(out)

    @staticmethod
    def std_out(msg: str, *args) -> None:
        """
        frSTD_OUT(msg) 매크로 대응.
        잠금 후 기록.
        """
        inst = Logger._instance
        if inst is None:
            Logger._instance = Logger()
            inst = Logger._instance
        if args:
            try:
                msg = msg % args
            except Exception:
                pass
        with Logger._log_lock:
            inst._py_logger.info(msg)

    @staticmethod
    def flush() -> None:
        """C++ Flush() 대응."""
        inst = Logger._instance
        if inst and inst._handler:
            inst._handler.flush()

    # ── 타임스탬프 ────────────────────────────────────────────────────────────

    @staticmethod
    def get_timestamp() -> str:
        """
        C++ GetTimeStamp() 대응.
        'YYYY/MM/DD HH:MM:SS.mmm' 포맷.
        """
        now = datetime.now()
        return (
            f"{now.year:04d}/{now.month:02d}/{now.day:02d} "
            f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}."
            f"{now.microsecond // 1000:03d}"
        )

    @staticmethod
    def show(package: str = None) -> str:
        """C++ Show() / Show(package) 대응."""
        inst = Logger._instance
        if inst is None:
            return ""
        if package is None:
            return inst._root.show()
        node = inst._root.find(package)
        return node.show() if node else ""

    @staticmethod
    def get_thread_id() -> int:
        """C++ GetThreadSelfId() 대응."""
        return threading.get_ident()

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _make_formatter() -> logging.Formatter:
        return logging.Formatter("%(message)s")


# ══════════════════════════════════════════════════════════════════════════════
# 매크로 대응 헬퍼 함수  (모듈 레벨 편의 함수)
# ══════════════════════════════════════════════════════════════════════════════

def make_log_def(package: str, feature: str) -> LogDef:
    """
    frDEFINE_DBG_FTR(("Util","frTokenizer")) 매크로 대응.

    사용:
        _log = make_log_def("Util", "frTokenizer")
        _log.debug(3, "DoIt called")
        _log.error("Something failed: %s", reason)
    """
    return LogDef(package, feature)