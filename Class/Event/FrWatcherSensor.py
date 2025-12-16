import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrRdFdSensor import FrRdFdSensor

# -------------------------------------------------------
# FrWatcherSensor Class
# 표준 입력(키보드)을 감시하여 사용자 입력을 처리하는 센서
# -------------------------------------------------------
class FrWatcherSensor(FrRdFdSensor):
    def __init__(self, header="> "):
        """
        C++: frWatcherSensor(string Header) : frRdFdSensor(0)
        FD 0번(STDIN)을 감시하는 센서로 초기화
        """
        # STDIN_FILENO = 0
        super().__init__(0)
        
        self.m_Header = header
        
        self.print_header()
        
        # C++ 로직과 동일하게 생성 시에는 비활성화 상태로 시작
        # (필요한 시점에 enable()을 호출해야 입력 감지 시작)
        self.disable()

    def __del__(self):
        """
        C++: ~frWatcherSensor()
        """
        super().__del__()

    def subject_changed(self):
        """
        C++: int SubjectChanged()
        키보드 입력 이벤트가 발생했을 때 호출됨
        """
        # 1. 데이터 읽기 (최대 1024바이트, 혹은 적절한 버퍼 크기)
        # FrRdFdSensor.read()는 os.read()를 호출하여 bytes를 반환함
        raw_data = self.read(1024)
        
        if raw_data:
            # 2. 문자열 변환 (Decoding)
            try:
                input_str = raw_data.decode('utf-8').strip()
            except UnicodeDecodeError:
                input_str = ""

            # 3. 가상 함수 호출 (사용자가 구현할 로직)
            if input_str:
                self.watch(input_str)

            # 4. 프롬프트 재출력
            self.print_header()

        return 1

    def set_header(self, header):
        """
        C++: void SetHeader(string Header)
        """
        self.m_Header = header

    def print_header(self):
        """
        C++: void PrintHeader()
        프롬프트(Header) 출력. 줄바꿈 없이 출력하고 버퍼를 비움.
        """
        print(self.m_Header, end='', flush=True)

    # ---------------------------------------------------
    # Virtual Method (Override Target)
    # ---------------------------------------------------
    def watch(self, input_buffer):
        """
        C++: virtual void Watch(char* m_InputBuffer)
        자식 클래스에서 이 메서드를 오버라이딩하여 입력 명령어 처리
        """
        # print(f"[Input Received] {input_buffer}")
        pass