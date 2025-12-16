import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Util.FrBaseList import FrStringVector
from Class.Common.AsUtil import AsUtil

# -------------------------------------------------------
# AsEnvrion Class
# 설정 파일 파서 (INI 스타일: [Section] Key=Value)
# 중복 키 지원 (MultiSubsectionMode)
# -------------------------------------------------------
class AsEnvrion:
    def __init__(self):
        self.m_IsMultiSubsecion = False
        self.m_Delim = "="
        
        # 구조: { "Section": { "SubSection": ["Value1", "Value2", ...] } }
        self.m_SectionValueMap = {}

    def __del__(self):
        self.m_SectionValueMap.clear()

    def set_delim(self, delim):
        self.m_Delim = delim

    def init_config(self, file_name, multi_subsection_mode=False):
        """
        C++: bool InitConfig(string FileName, bool MultiSubsectionMode)
        파일을 읽어 파싱하여 맵에 저장
        """
        self.m_IsMultiSubsecion = multi_subsection_mode
        self.m_SectionValueMap.clear()

        if not os.path.exists(file_name):
            print(f"[AsEnvrion] Can't open config file({file_name})")
            return False

        current_section = ""
        
        try:
            with open(file_name, 'r', encoding='utf-8') as f:
                for line_no, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # 빈 줄이나 주석(#) 무시
                    if not line or line.startswith('#'):
                        continue

                    # 섹션 시작: [SECTION]
                    if line.startswith('[') and line.endswith(']'):
                        current_section = line[1:-1].strip()
                        
                        if current_section not in self.m_SectionValueMap:
                            self.m_SectionValueMap[current_section] = {}
                        else:
                            # 중복 섹션 경고 (C++ 로직)
                            print(f"[AsEnvrion] (Line : {line_no}) Duplicate Section : [{current_section}]")
                            return False
                            
                    # 키-값 쌍: Key=Value
                    else:
                        if not current_section:
                            continue

                        # 구분자 찾기
                        if self.m_Delim not in line:
                            print(f"[AsEnvrion] (Line : {line_no}) Config Usage Error : Section({current_section}), {line}")
                            continue

                        # 파싱 (첫 번째 구분자 기준 분리)
                        key, value = line.split(self.m_Delim, 1)
                        key = key.strip()
                        value = value.strip()

                        if not key: continue

                        section_map = self.m_SectionValueMap[current_section]

                        # 값 저장
                        if not self.m_IsMultiSubsecion:
                            # 덮어쓰기 모드 (단, C++ 코드는 벡터에 넣으므로 리스트로 관리)
                            section_map[key] = [value]
                        else:
                            # 중복 허용 모드 (리스트에 추가)
                            if key not in section_map:
                                section_map[key] = [value]
                            else:
                                section_map[key].append(value)
            return True

        except IOError as e:
            print(f"[AsEnvrion] File Read Error: {e}")
            return False

    def get_env_value(self, section, sub_section):
        """
        C++: string GetEnvValue(string Section, string SubSection)
        단일 값 반환 (첫 번째 값)
        """
        if section in self.m_SectionValueMap:
            if sub_section in self.m_SectionValueMap[section]:
                values = self.m_SectionValueMap[section][sub_section]
                if values:
                    return values[0]
        return ""

    def get_env_value_by_type(self, process_type, sub_section):
        """
        C++: string GetEnvValue(int ProcessType, string SubSection)
        프로세스 타입 Enum을 문자열로 변환하여 조회
        """
        section = AsUtil.get_process_type_string(process_type)
        return self.get_env_value(section, sub_section)

    def get_env_values(self, section, sub_section, out_vector):
        """
        C++: bool GetEnvValue(..., frStringVector& EnvValues)
        다중 값을 벡터(리스트)에 담아 반환
        """
        if section in self.m_SectionValueMap:
            if sub_section in self.m_SectionValueMap[section]:
                values = self.m_SectionValueMap[section][sub_section]
                
                # FrStringVector.Copy 메서드 사용 (리스트 복사)
                # out_vector가 FrStringVector 인스턴스여야 함
                if hasattr(out_vector, 'Copy'):
                    out_vector.Copy(values)
                else:
                    out_vector.extend(values)
                    
                return len(values) > 0
        return False

    def print_config(self, target_section=""):
        """
        C++: void Print(string Section)
        설정 내용 출력
        """
        for section, sub_map in self.m_SectionValueMap.items():
            if not target_section or target_section == section:
                print(f"Section : [{section}]")
                for key, values in sub_map.items():
                    for val in values:
                        print(f"\tSubSection : [{key}], Value : [{val}]")
                print("")

    def get_value_list(self):
        return self.m_SectionValueMap

    def is_section(self, section):
        return section in self.m_SectionValueMap