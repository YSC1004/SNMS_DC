"""
frArgParser.h / frArgParser.C  →  fr_arg_parser.py

변환 매핑:
  frArgParser(int argc, char *argv[]) → ArgParser(argv: list[str])
  GetValue(name)                      → get_value(name)       : str | None
  GetValueList(name)                  → get_value_list(name)  : list[str]
  DoesItExist(name)                   → does_it_exist(name)   : bool

C++ 원본 동작 유지:
  - argv[0] 은 프로그램명이므로 탐색에서 제외 (i = 1 부터 시작)
  - GetValue    : 첫 번째로 매칭된 name 바로 뒤의 값(i+1) 반환
  - GetValueList: 매칭된 name 바로 뒤의 값을 모두 수집 (중복 key 지원)
  - DoesItExist : name 이 argv 에 존재하면 True (값 없이 플래그로 쓰인 경우 포함)

Python 통합:
  - sys.argv 와 자연스럽게 연동 가능
  - 생성자에서 argc 는 불필요 (len(argv) 로 대체)
"""

import sys
from typing import Optional


class ArgParser:
    """커맨드라인 인수 파서 (frArgParser 대응)."""

    def __init__(self, argv: list[str] = None):
        """
        argv : sys.argv 형식의 리스트 (argv[0] = 프로그램명).
               None 이면 sys.argv 를 자동으로 사용.
        """
        self._argv: list[str] = argv if argv is not None else sys.argv

    # ------------------------------------------------------------------ #

    def get_value(self, name: str) -> Optional[str]:
        """
        argv 에서 name 과 일치하는 인수를 찾아 바로 다음 값을 반환한다.
        없으면 None 반환.

        C++ GetValue() : return m_Argv[i+1] or NULL
        """
        argv = self._argv
        for i in range(1, len(argv) - 1):   # i+1 < argc → range(1, len-1)
            if argv[i] == name:
                return argv[i + 1]
        return None

    def get_value_list(self, name: str) -> list[str]:
        """
        argv 에서 name 과 일치하는 인수를 모두 찾아,
        각각 바로 다음 값을 리스트로 반환한다.
        (동일 key 가 여러 번 등장할 때 모두 수집)

        C++ GetValueList() : frStringList 반환
        """
        argv = self._argv
        result: list[str] = []
        for i in range(1, len(argv) - 1):
            if argv[i] == name:
                result.append(argv[i + 1])
        return result

    def does_it_exist(self, name: str) -> bool:
        """
        argv 에 name 이 존재하면 True, 없으면 False.
        값 없이 플래그로만 쓰이는 인수도 감지한다.

        C++ DoesItExist() : return 1 or 0  →  Python bool
        """
        return name in self._argv[1:]