"""
frValueRangeHandler.h / frValueRangeHandler.C  →  fr_value_range_handler.py

변환 매핑:
  frValueRangeHandler           → ValueRangeHandler
  frCharPtrList* m_List         → list[str]  (Python GC 가 메모리 자동 해제)
  bool m_MemOwner               → 불필요 (GC 처리) → 제거
  frTokenizer(","  구분)        → str.split(",")
  frTokenizer("~"  구분)        → str.split("~")
  new char[] / strcpy / delete  → Python str (불필요)
  frCORE_ERROR                  → logging.error
  frSTD_OUT                     → print / logging.debug

지원 포맷 (DoIt 입력):
  1) "1~4"       → ['1','2','3','4']
  2) "1,3,5"     → ['1','3','5']
  3) "1,3,5~9,11"→ ['1','3','5','6','7','8','9','11']
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ValueRangeHandler:
    """
    콤마(,) 와 범위(~) 표기를 파싱하여 값 목록을 생성하는 유틸리티.

    사용 예:
        h = ValueRangeHandler()
        h.do_it("1,3,5~9,11")
        print(h.get_result())   # ['1', '3', '5', '6', '7', '8', '9', '11']
    """

    def __init__(self):
        self._source: str       = ""
        self._list:   list[str] = []   # frCharPtrList* m_List 대응

    # ------------------------------------------------------------------ #

    def do_it(self, source: str) -> None:
        """
        source 문자열을 파싱하여 내부 결과 목록을 생성한다.

        지원 포맷:
          단일값  : "5"       → ['5']
          범위    : "1~4"     → ['1','2','3','4']
          복합    : "1,3~5,7" → ['1','3','4','5','7']
        """
        self.clear()
        self._source = source

        for token in source.split(","):
            token = token.strip()
            if not token:
                continue

            parts = token.split("~")

            if len(parts) == 1:
                # 단일 값
                self._list.append(parts[0].strip())

            elif len(parts) == 2:
                # 범위 값
                try:
                    from_val = int(parts[0].strip())
                    to_val   = int(parts[1].strip())
                    for i in range(from_val, to_val + 1):
                        self._list.append(str(i))
                except ValueError:
                    logger.error(
                        "ValueRangeHandler: invalid range token '%s' in '%s'",
                        token, source,
                    )
            else:
                logger.error(
                    "ValueRangeHandler: unexpected token format '%s' in '%s'",
                    token, source,
                )

    def get_result(self) -> list[str]:
        """파싱 결과 목록을 반환한다 (GetResult 대응)."""
        return self._list

    def clear(self) -> None:
        """내부 목록을 초기화한다 (Clear 대응)."""
        self._list.clear()
        self._source = ""

    def print_all(self) -> None:
        """파싱 결과를 출력한다 (Print 대응)."""
        print(f"ValueRangeHandler ({self._source})")
        if self._list:
            for val in self._list:
                print(f"\t{val}")
        else:
            print("\tResult is empty")