import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 로거 임포트 (없으면 print 사용)
try:
    from Class.Event.FrLogger import FrLogger
    logger = FrLogger.get_instance()
    def fr_debug(msg): logger.write(f"[DEBUG] {msg}")
except ImportError:
    def fr_debug(msg): print(f"[DEBUG] {msg}")

# -------------------------------------------------------
# MmcKeyNode Class
# 단일 키-값 쌍을 저장하는 노드
# -------------------------------------------------------
class MmcKeyNode:
    def __init__(self, name, value):
        """
        C++: MmcKeyNode(char *name, char *value)
        """
        self.m_Name = name
        self.m_Value = value

# -------------------------------------------------------
# MmcKeyHandler Class
# 키-값 쌍 목록을 관리하고 정렬/포맷팅 수행
# -------------------------------------------------------
class MmcKeyHandler:
    SEP_MARK = ":"

    def __init__(self):
        """
        C++: MmcKeyHandler()
        """
        self.m_List = [] # List of MmcKeyNode

    def __del__(self):
        self.clear()

    def clear(self):
        """
        C++: void Clear()
        """
        self.m_List.clear()

    def add(self, name, value):
        """
        C++: void Add(char *name, char *value)
        키(name)를 기준으로 알파벳 오름차순 정렬하여 삽입
        """
        fr_debug(f"(name:{name}),(value:{value})")
        
        new_node = MmcKeyNode(name, value)
        
        # 리스트가 비어있으면 바로 추가
        if not self.m_List:
            self.m_List.append(new_node)
            return

        # 삽입 정렬 (Insertion Sort logic)
        inserted = False
        for i, node in enumerate(self.m_List):
            if node.m_Name > name:
                self.m_List.insert(i, new_node)
                inserted = True
                break
        
        # 가장 큰 값이면 맨 뒤에 추가
        if not inserted:
            self.m_List.append(new_node)

    def get_key(self, source=None):
        """
        C++: string GetKey(char *source)
        source가 있으면 파싱하여 리스트를 재구성하고,
        리스트의 내용을 (Key:Val),(Key:Val) 형태의 문자열로 반환
        """
        if source:
            self.clear()
            self._arrange(source)
        
        result_parts = []
        for node in self.m_List:
            # 포맷: (Name:Value)
            item = f"({node.m_Name}{self.SEP_MARK}{node.m_Value})"
            result_parts.append(item)
            
        # 쉼표로 연결
        return ",".join(result_parts)

    def _arrange(self, source):
        """
        C++: void _Arrange(char *source)
        입력 문자열을 파싱하여 노드 추가
        예상 포맷: (Key1:Val1),(Key2:Val2)
        """
        if not source:
            return

        fr_debug(f"(src:{source})")
        
        # C++ 로직은 쉼표(,)를 기준으로 먼저 자르고 내부를 파싱함
        # Python split을 사용하면 훨씬 간단함
        parts = source.split(',')
        
        for part in parts:
            part = part.strip()
            if not part: continue
            
            # part 예시: (Name:Value)
            # SEP_MARK(:) 위치 찾기
            sep_pos = part.find(self.SEP_MARK)
            
            if sep_pos != -1:
                # 괄호와 구분자 사이의 문자열 추출
                # C++: substr(1, pos-1) -> 맨 앞 '(' 제외, ':' 전까지
                name = part[1:sep_pos]
                
                # C++: substr(pos+1, length-pos-2) -> ':' 후부터, 맨 뒤 ')' 제외
                # Python 슬라이싱: [start : end]
                value = part[sep_pos+1 : -1]
                
                self.add(name, value)

    @staticmethod
    def make(name, value, source=None):
        """
        C++: string Make(char *name, char *value)
        C++: string Make(char *source, char *name, char *value) (Overloaded)
        
        단일 생성 또는 기존 문자열에 추가
        """
        new_item = f"({name}{MmcKeyHandler.SEP_MARK}{value})"
        
        if source and len(source) > 0:
            return f"{source},{new_item}"
        else:
            return new_item