# -*- coding: utf-8 -*-
"""
MmcKeyHandler.h / MmcKeyHandler.C  →  MmcKeyHandler.py
Python 3.11.10 변환

변환 설계:
  MmcKeyNode     → MmcKeyNode     (dataclass)
  MmcKeyNodeList → list[MmcKeyNode] (Python list 로 대체, 별도 클래스 불필요)
  MmcKeyHandler  → MmcKeyHandler

C++ → Python 주요 변환 포인트:
  list<MmcKeyNode*> + 수동 delete  → list[MmcKeyNode] (GC 위임)
  정렬 삽입 (name 사전순)          → bisect.insort / sorted key 활용
  SEP_MARK ":"                     → 모듈 상수 SEP_MARK
  Make() 오버로드 2종              → make() + make_append() 로 분리
  _Arrange() 파싱 로직             → str.split(',') + str.split(':') 활용

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
import bisect
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SEP_MARK = ":"


# ──────────────────────────────────────────────
# MmcKeyNode
# ──────────────────────────────────────────────
@dataclass
class MmcKeyNode:
    """C++ MmcKeyNode 대응."""
    name:  str
    value: str

    # bisect.insort 가 name 기준 정렬에 사용할 비교 연산자
    def __lt__(self, other: 'MmcKeyNode') -> bool:
        return self.name < other.name

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MmcKeyNode):
            return NotImplemented
        return self.name == other.name


# ──────────────────────────────────────────────
# MmcKeyHandler
# ──────────────────────────────────────────────
class MmcKeyHandler:
    """
    C++ MmcKeyHandler 대응.

    name/value 쌍을 name 사전순으로 정렬 관리하며,
    "(name:value),(name:value),..." 형태의 키 문자열을 생성한다.

    사용 예:
        h = MmcKeyHandler()
        h.add("z_key", "1")
        h.add("a_key", "2")
        print(h.get_key())          # (a_key:2),(z_key:1)

        key = MmcKeyHandler.make("host", "127.0.0.1")
        key = MmcKeyHandler.make_append(key, "port", "8080")
    """

    def __init__(self) -> None:
        self._list: list[MmcKeyNode] = []

    def __del__(self) -> None:
        self.clear()

    # ── public ────────────────────────────────

    def clear(self) -> None:
        """C++ Clear() 대응. 리스트 초기화."""
        self._list.clear()

    def add(self, name: str, value: str) -> None:
        """
        C++ Add(char*, char*) 대응.
        name 사전순을 유지하면서 삽입 (bisect 활용).
        """
        logger.debug("(name:%s),(value:%s)", name, value)
        bisect.insort(self._list, MmcKeyNode(name, value))

    def get_key(self, source: str | None = None) -> str:
        """
        C++ GetKey(char* source) 대응.
        source 가 주어지면 파싱 후 재구성, 없으면 현재 리스트로 키 생성.
        반환 형식: (name:value),(name:value),...
        """
        if source:
            self.clear()
            self._arrange(source)

        parts = [f"({n.name}{SEP_MARK}{n.value})" for n in self._list]
        return ",".join(parts)

    @staticmethod
    def make(name: str, value: str) -> str:
        """
        C++ Make(char* name, char* value) 대응.
        단일 키 문자열 생성: "(name:value)"
        """
        return f"({name}{SEP_MARK}{value})"

    @staticmethod
    def make_append(source: str | None, name: str, value: str) -> str:
        """
        C++ Make(char* source, char* name, char* value) 대응.
        source 가 있으면 뒤에 추가: "source,(name:value)"
        없으면 make(name, value) 와 동일.
        """
        if source:
            return f"{source},({name}{SEP_MARK}{value})"
        return MmcKeyHandler.make(name, value)

    # ── protected ─────────────────────────────

    def _arrange(self, source: str) -> None:
        """
        C++ _Arrange(char*) 대응.
        "(name:value),(name:value),..." 형식 문자열을 파싱하여 add().

        파싱 규칙:
          - 최상위 콤마(,)로 토큰 분리
          - 각 토큰은 "(name:value)" 형식
          - 괄호와 SEP_MARK(':') 기준으로 name/value 추출
        """
        logger.debug("(src:%s)", source)
        for token in source.split(","):
            token = token.strip()
            if not token:
                continue
            # "(name:value)" → "name:value"
            inner = token.strip("()")
            sep_pos = inner.find(SEP_MARK)
            if sep_pos == -1:
                logger.warning("_arrange: SEP_MARK not found in token '%s'", token)
                continue
            name  = inner[:sep_pos]
            value = inner[sep_pos + 1:]
            self.add(name, value)