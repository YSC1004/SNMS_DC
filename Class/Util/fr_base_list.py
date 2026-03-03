"""
frBaseList.h / frBaseList.C  →  fr_base_list.py

변환 매핑:
  frCharPtrList   (list<char*>)    → CharPtrList  : deque[str]  래퍼 클래스
  frStringList    (list<string>)   → StringList   : deque[str]  래퍼 클래스
  frStringVector  (vector<string>) → StringVector : list[str]   래퍼 클래스
  frIntVector     (vector<int>)    → IntVector    : list[int]   래퍼 클래스
  IntList         (list<int>)      → IntList      = deque[int]  (타입 별칭)
  frStrStrMap     (map<str,str>)   → StrStrMap    = dict[str,str] (타입 별칭)

설계 원칙:
  - list<T>  (순서 유지, 앞/뒤 삽입 빈번) → collections.deque
  - vector<T>(인덱스 접근, 뒤 삽입 중심) → list
  - C++ delete[] / 메모리 해제            → Python GC 가 자동 처리
  - frSTD_OUT(...)                        → print() / logging
  - Copy()                                → Python 의 slice copy 또는 copy()
                                            (하위 호환용으로 메서드도 제공)
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# CharPtrList  ←  frCharPtrList : public list<char*>
# ══════════════════════════════════════════════════════════════════════════════
class CharPtrList(deque):
    """
    C++ char* 포인터 리스트 대응.
    Python 에서는 str 로 저장하며, GC 가 메모리를 자동 해제하므로
    Clear() 는 단순 deque.clear() 로 구현.
    """

    def clear_all(self) -> None:
        """
        C++ Clear() 대응: 각 원소를 delete 후 clear().
        Python 에서는 참조만 제거하면 GC 가 처리.
        """
        self.clear()

    # deque 기본 메서드로 push_back / push_front / pop_front 등 사용 가능:
    #   append()      ← push_back()
    #   appendleft()  ← push_front()
    #   popleft()     ← pop_front()
    #   pop()         ← pop_back()


# ══════════════════════════════════════════════════════════════════════════════
# StringList  ←  frStringList : public list<string>
# ══════════════════════════════════════════════════════════════════════════════
class StringList(deque):
    """
    C++ string 리스트 대응.
    deque 를 상속하므로 append/appendleft/popleft 등 모두 사용 가능.
    """

    def copy_from(self, src: "StringList") -> None:
        """
        C++ Copy(frStringList& Src) 대응.
        src 의 내용을 self 에 복사한다 (기존 내용은 지워짐).
        """
        self.clear()
        self.extend(src)

    def __copy__(self) -> "StringList":
        new = StringList()
        new.extend(self)
        return new


# ══════════════════════════════════════════════════════════════════════════════
# StringVector  ←  frStringVector : public vector<string>
# ══════════════════════════════════════════════════════════════════════════════
class StringVector(list):
    """
    C++ string 벡터 대응.
    list 를 상속하므로 인덱스 접근, append 등 모두 사용 가능.
    """

    def copy_from(self, src: "StringVector") -> None:
        """C++ Copy(frStringVector& Src) 대응."""
        self.clear()
        self.extend(src)

    def print_all(
        self,
        start_tag: Optional[str] = None,
        end_tag:   Optional[str] = None,
    ) -> None:
        """
        C++ Print(StartTag, EndTag) 대응.
        frSTD_OUT → print() 로 변환.
        """
        if start_tag:
            print(f"[{start_tag}]")
        for i, val in enumerate(self):
            print(f"{i}:[{val}]")
        if end_tag:
            print(f"[{end_tag}]")

    def __copy__(self) -> "StringVector":
        new = StringVector()
        new.extend(self)
        return new


# ══════════════════════════════════════════════════════════════════════════════
# IntVector  ←  frIntVector : public vector<int>
# ══════════════════════════════════════════════════════════════════════════════
class IntVector(list):
    """
    C++ int 벡터 대응.
    list 를 상속하므로 인덱스 접근, append 등 모두 사용 가능.
    """

    def copy_from(self, src: "IntVector") -> None:
        """C++ Copy(frIntVector& Src) 대응."""
        self.clear()
        self.extend(src)

    def print_all(
        self,
        start_tag: Optional[str] = None,
        end_tag:   Optional[str] = None,
    ) -> None:
        """C++ Print(StartTag, EndTag) 대응."""
        if start_tag:
            print(f"[{start_tag}]")
        for i, val in enumerate(self):
            print(f"{i}:[{val}]")
        if end_tag:
            print(f"[{end_tag}]")

    def __copy__(self) -> "IntVector":
        new = IntVector()
        new.extend(self)
        return new


# ══════════════════════════════════════════════════════════════════════════════
# 타입 별칭  ←  typedef
# ══════════════════════════════════════════════════════════════════════════════

# typedef list<int>            IntList
IntList = deque   # 제네릭 힌트: deque[int]

# typedef map<string, string>  frStrStrMap
StrStrMap = dict  # 제네릭 힌트: dict[str, str]