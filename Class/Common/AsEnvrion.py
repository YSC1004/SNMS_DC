"""
2014.07.08  초기 작성
Python 변환: AsEnvrion.h/.C → AsEnvrion.py

역할: INI 스타일 설정 파일 파서
  형식:
    [SectionName]
    SubSection = Value
    SubSection = Value2   ← MultiSubsectionMode=True 일 때 중복 허용
"""

import logging
from typing import List, Optional

from Common.CommTypeList import SectionValueMap, SubSectionValueMap

logger = logging.getLogger(__name__)


class AsEnvrion:
    """
    C++: class AsEnvrion : public frObject

    INI 스타일 설정 파일을 읽어 SectionValueMap 구조로 관리.
      - [Section] 단위로 구분
      - SubSection = Value 형태
      - '#' 으로 시작하는 줄은 주석
      - MultiSubsectionMode=True 이면 동일 SubSection 키에 값 복수 허용
    """

    def __init__(self):
        self.m_SectionValueMap:  SectionValueMap = SectionValueMap()
        self.m_IsMultiSubsecion: bool = False
        self.m_Delim:            str  = "="

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def SetDelim(self, pDelim: str) -> None:
        """구분자 변경 (기본값 '=')"""
        self.m_Delim = pDelim

    def InitConfig(self, FileName: str, MultiSubsectionMode: bool = False) -> bool:
        """
        설정 파일을 읽어 m_SectionValueMap 에 저장.

        Args:
            FileName:           설정 파일 경로
            MultiSubsectionMode: True 이면 동일 SubSection 키에 값 복수 허용

        Returns:
            True: 성공, False: 실패
        """
        self.m_IsMultiSubsecion = MultiSubsectionMode
        self.m_SectionValueMap.clear()

        try:
            fp = open(FileName, "r", encoding="utf-8", errors="replace")
        except OSError as e:
            logger.error("Can't open config file(%s): %s", FileName, e)
            return False

        current_section: str = ""
        line_cnt: int = 0

        with fp:
            for raw in fp:
                line_cnt += 1
                line = raw.rstrip("\n\r").strip()

                if not line:
                    continue
                if line.startswith("#"):
                    continue

                # ── Section 헤더: [SectionName]
                if line.startswith("["):
                    section_name = line.strip("[]").strip()
                    if section_name in self.m_SectionValueMap:
                        logger.error(
                            "(Line:%d) Duplicate Section: [%s]",
                            line_cnt, section_name,
                        )
                        return False
                    self.m_SectionValueMap[section_name] = SubSectionValueMap()
                    current_section = section_name
                    continue

                # ── Key=Value 행
                if not current_section:
                    continue

                if self.m_Delim not in line:
                    logger.error(
                        "(Line:%d) Config Usage Error: Section(%s), %s",
                        line_cnt, current_section, line,
                    )
                    continue

                delim_pos  = line.index(self.m_Delim)
                sub_section = line[:delim_pos].strip()
                value       = line[delim_pos + len(self.m_Delim):].strip()

                if not sub_section:
                    continue

                sub_map = self.m_SectionValueMap.get(current_section)
                if sub_map is None:
                    continue

                if not self.m_IsMultiSubsecion:
                    # 단일 값 모드: 덮어쓰기
                    sub_map[sub_section] = [value]
                else:
                    # 다중 값 모드: 기존 키에 append
                    if sub_section in sub_map:
                        sub_map[sub_section].append(value)
                    else:
                        sub_map[sub_section] = [value]

        return True

    def IsSection(self, Section: str) -> bool:
        """섹션 존재 여부 확인"""
        return Section in self.m_SectionValueMap

    def GetEnvValue(self,
                    Section: str,
                    SubSection: str,
                    ProcessType: Optional[int] = None) -> str:
        """
        단일 값 반환.

        오버로드 대응:
          - GetEnvValue(Section, SubSection)          → str
          - GetEnvValue(ProcessType(int), SubSection) → str
            (ProcessType 을 첫 인자 int로 받을 때 Section 자동 변환)

        Returns:
            값 문자열, 없으면 ""
        """
        # C++ 오버로드: GetEnvValue(int ProcessType, string SubSection)
        if ProcessType is not None:
            from Common.AsUtil import AsUtil
            Section = AsUtil.GetProcessTypeString(ProcessType)

        sub_map = self.m_SectionValueMap.get(Section)
        if sub_map is None:
            return ""

        values = sub_map.get(SubSection)
        if not values:
            return ""

        return values[0]

    def GetEnvValueList(self, Section: str, SubSection: str) -> List[str]:
        """
        복수 값 반환 (MultiSubsectionMode 용).

        C++ 원본: GetEnvValue(Section, SubSection, frStringVector& EnvValues)
        Python 에서는 반환값으로 처리.

        Returns:
            값 리스트, 없으면 []
        """
        sub_map = self.m_SectionValueMap.get(Section)
        if sub_map is None:
            return []

        values = sub_map.get(SubSection)
        return list(values) if values else []

    def GetEnvValueByProcessType(self, ProcessType: int, SubSection: str) -> str:
        """
        C++ GetEnvValue(int ProcessType, string SubSection) 명시적 대응.
        ProcessType → 문자열 섹션명 변환 후 조회.
        """
        from Common.AsUtil import AsUtil
        return self.GetEnvValue(AsUtil.GetProcessTypeString(ProcessType), SubSection)

    def Print(self, Section: str = "") -> None:
        """설정 내용 출력 (디버그용)"""
        for sec_name, sub_map in self.m_SectionValueMap.items():
            if Section and Section != sec_name:
                continue
            print(f"Section : [{sec_name}]")
            for sub_key, values in sub_map.items():
                for v in values:
                    print(f"\tSubSection : [{sub_key}], Value : [{v}]")
            print()

    def GetValueList(self) -> SectionValueMap:
        """내부 SectionValueMap 참조 반환"""
        return self.m_SectionValueMap