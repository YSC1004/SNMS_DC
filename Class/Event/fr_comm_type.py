"""
frCommType.py - C++ frCommType.h를 Python 3.11로 변환

C++ 표준 헤더 include 및 공통 타입/매크로 정의.
Python 표준 라이브러리로 대응합니다.
"""

# ── C++ 표준/시스템 헤더 대응 import ──────────────
import os
import sys
import time
import signal
import socket
import struct
import threading
import queue
from collections import deque
from typing import Any

# ──────────────────────────────────────────────
# THREAD_ID
# C++: typedef pthread_t THREAD_ID
# Python: threading.get_ident() 반환값(int)을 THREAD_ID 타입으로 정의
# ──────────────────────────────────────────────
THREAD_ID = int  # 타입 별칭


# ──────────────────────────────────────────────
# TRACE 매크로
# C++: printf("(%s:%d) ", __FILE__, __LINE__); printf x; printf("\n");
# Python: 호출 위치(파일명/라인) 를 inspect 로 가져와 출력
# ──────────────────────────────────────────────
import inspect

def TRACE(*args) -> None:
    """C++ TRACE(x) 매크로 대응. 호출 위치와 메시지를 stdout에 출력."""
    frame = inspect.stack()[1]
    filename = os.path.basename(frame.filename)
    lineno   = frame.lineno
    msg      = " ".join(str(a) for a in args)
    print(f"({filename}:{lineno}) {msg}", flush=True)