import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrFileFdSensor import FrFileFdSensor

# -------------------------------------------------------
# AsFileSensor Class
# FrFileFdSensor를 상속받아 구체적인 파일 처리 로직을 담는 클래스
# -------------------------------------------------------
class AsFileSensor(FrFileFdSensor):
    def __init__(self):
        """
        C++: AsFileSensor()
        """
        super().__init__()

    def __del__(self):
        """
        C++: ~AsFileSensor()
        """
        super().__del__()

    def file_event_read(self):
        """
        C++: (Inherited virtual function)
        FrFileFdSensor에서 파일 변경(이벤트) 감지 시 호출되는 함수.
        이곳에 실제 파일 읽기 및 처리 로직을 구현해야 합니다.
        """
        if self.m_FD != -1:
            try:
                # 변경된 내용 읽기 (최대 4KB)
                # 여기서 읽지 않으면 계속 읽기 가능 상태로 남아 루프가 돌 수 있음
                data = os.read(self.m_FD, 4096)
                
                if data:
                    # 예: 로그 출력 또는 파싱
                    # print(f"[AsFileSensor] New Data: {data.decode('utf-8', errors='ignore').strip()}")
                    pass
                    
            except OSError as e:
                print(f"[AsFileSensor] Read Error: {e}")