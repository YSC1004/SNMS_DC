"""
frTokenizer.h / frTokenizer.C  →  fr_tokenizer.py

변환 매핑:
  frTokenizer(source)        → Tokenizer(source)
  SetSource / SetDelimiter   → set_source / set_delimiter
  Before(delimiter)          → before(delimiter)
  After(delimiter)           → after(delimiter)
  DoIt()                     → do_it()   : 단일 문자 구분자 기반 파싱
  DoIt2()                    → do_it2()  : 문자열 구분자 기반 파싱 (strncmp)
  CountToken()               → count_token()
  HasMoreToken()             → has_more_token()
  Next()                     → next()
  GetToken(no)               → get_token(no)   ← 1-based (C++ 원본 유지)
  FindToken(token, startPos) → find_token(token, start_pos)  ← 0-based
  operator[](Pos)            → __getitem__(pos) ← 0-based (C++ 원본 유지)
  Print()                    → print_all()
  Clear()                    → clear()

DoIt() 동작 (C++ 원본 재현):
  - 구분자는 "문자 집합"으로 취급 (delimiter 문자열 내 각 문자가 구분자)
  - 연속 구분자는 하나로 취급 (delFlag 로직)

DoIt2() 동작 (C++ 원본 재현):
  - 구분자는 "문자열" 로 취급 (strncmp 방식)
  - 빈 토큰도 포함
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Tokenizer:
    """문자열을 구분자 기준으로 토큰으로 분리하는 유틸리티."""

    def __init__(self, source: str = ""):
        self._source:    str       = source or ""
        self._delimiter: str       = ""
        self._tokens:    list[str] = []
        self._itr_pos:   int       = 0      # m_Itr (iterator) 대응

    # ------------------------------------------------------------------ #
    # 설정
    # ------------------------------------------------------------------ #

    def set_source(self, source: str) -> None:
        """소스 문자열을 설정하고 기존 토큰을 초기화한다."""
        self.clear()
        self._source = source

    def set_delimiter(self, delimiter: str) -> None:
        """구분자 문자열을 설정한다."""
        self._delimiter = delimiter

    def clear(self) -> None:
        """토큰 벡터와 이터레이터를 초기화한다."""
        self._tokens.clear()
        self._itr_pos = 0

    # ------------------------------------------------------------------ #
    # Before / After
    # ------------------------------------------------------------------ #

    def before(self, delimiter: str = None) -> str:
        """
        소스에서 구분자 집합 중 첫 번째로 등장하는 문자 이전 부분을 반환.
        구분자가 맨 앞이면 빈 문자열, 없으면 소스 전체 반환.

        C++ Before() : delimiter 내 각 문자를 개별 구분자로 취급.
        """
        if delimiter is not None:
            self._delimiter = delimiter

        del_set = set(self._delimiter)
        for i, ch in enumerate(self._source):
            if ch in del_set:
                return "" if i == 0 else self._source[:i]
        return self._source

    def after(self, delimiter: str = None) -> str:
        """
        소스에서 구분자 집합 중 첫 번째로 등장하는 문자 이후 부분을 반환.
        구분자가 맨 끝이면 빈 문자열, 없으면 빈 문자열 반환.

        C++ After() : flag(0=미발견, 1=발견, 2=다음문자) 로직 재현.
        """
        if delimiter is not None:
            self._delimiter = delimiter

        del_set  = set(self._delimiter)
        src_len  = len(self._source)
        found    = False

        for i, ch in enumerate(self._source):
            if found:
                # flag == 2: 구분자 다음 문자부터 반환
                return self._source[i:]
            if ch in del_set:
                if i == src_len - 1:
                    return ""
                found = True   # flag = 1 → 다음 루프에서 flag = 2

        return ""

    # ------------------------------------------------------------------ #
    # DoIt : 단일 문자 구분자 집합 기반 파싱 (연속 구분자 무시)
    # ------------------------------------------------------------------ #

    def do_it(self) -> None:
        """
        C++ DoIt() 재현.
        - m_Delimiter 내 각 문자를 구분자 집합으로 취급
        - 연속 구분자(delFlag=True)는 건너뜀 → 빈 토큰 미생성
        """
        self.clear()

        src      = self._source
        del_set  = set(self._delimiter)
        src_len  = len(src)
        start    = 0
        del_flag = True   # True: 이전 문자가 구분자(또는 시작)

        for i, ch in enumerate(src):
            if ch in del_set:
                if del_flag:
                    start = i + 1
                    continue
                size = i - start
                if size > 0:
                    self._tokens.append(src[start:i])
                else:
                    logger.error(
                        "Tokenizer.do_it: parsing error (i=%d, start=%d)", i, start
                    )
                start    = i + 1
                del_flag = True
            else:
                del_flag = False

        # 마지막 토큰 처리
        if start < src_len:
            self._tokens.append(src[start:])

        self._itr_pos = 0

    # ------------------------------------------------------------------ #
    # DoIt2 : 문자열 구분자 기반 파싱 (빈 토큰 포함, strncmp 방식)
    # ------------------------------------------------------------------ #

    def do_it2(self) -> None:
        """
        C++ DoIt2() 재현.
        - m_Delimiter 를 문자열 단위로 매칭 (strncmp)
        - 빈 토큰도 포함됨
        """
        self.clear()

        src   = self._source
        deli  = self._delimiter
        dlen  = len(deli)

        if dlen == 0:
            self._tokens.append(src)
            return

        node  = ""
        i     = 0
        while i < len(src):
            if src[i:i + dlen] == deli:
                self._tokens.append(node)
                node = ""
                i   += dlen
            else:
                node += src[i]
                i    += 1

        self._tokens.append(node)   # 마지막 토큰 (빈 문자열도 포함)
        self._itr_pos = 0

    # ------------------------------------------------------------------ #
    # 토큰 순회
    # ------------------------------------------------------------------ #

    def count_token(self) -> int:
        """토큰 개수 반환 (CountToken)."""
        return len(self._tokens)

    def has_more_token(self) -> bool:
        """순회할 토큰이 남아 있으면 True (HasMoreToken)."""
        return self._itr_pos < len(self._tokens)

    def next(self) -> str:
        """다음 토큰을 반환하고 이터레이터를 전진시킨다 (Next)."""
        if not self.has_more_token():
            return ""
        token         = self._tokens[self._itr_pos]
        self._itr_pos += 1
        return token

    def get_token(self, no: int) -> str:
        """
        1-based 인덱스로 토큰을 반환한다 (GetToken).
        C++ 원본: GetToken(1) → 첫 번째 토큰.
        범위 초과 시 빈 문자열 반환.
        """
        idx = no - 1
        return self._tokens[idx] if 0 <= idx < len(self._tokens) else ""

    def find_token(self, token: str, start_pos: int = 0) -> int:
        """
        start_pos(0-based) 부터 token 과 일치하는 첫 번째 인덱스를 반환.
        없으면 -1 반환 (FindToken).
        """
        for i in range(start_pos, len(self._tokens)):
            if self._tokens[i] == token:
                return i
        return -1

    def __getitem__(self, pos: int) -> str:
        """
        0-based 인덱스로 토큰을 반환한다 (operator[]).
        범위 초과 시 빈 문자열 반환.
        """
        return self._tokens[pos] if 0 <= pos < len(self._tokens) else ""

    def __iter__(self):
        """Python 이터레이터 지원 (for token in tokenizer)."""
        return iter(self._tokens)

    def __len__(self) -> int:
        return len(self._tokens)

    # ------------------------------------------------------------------ #
    # 출력
    # ------------------------------------------------------------------ #

    def print_all(self) -> None:
        """파싱 결과를 출력한다 (Print)."""
        print(f"Tokenizer source=({self._source}), delimiter=({self._delimiter})")
        for token in self._tokens:
            print(f"\t{token}")