import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrRdFdSensor import FrRdFdSensor

# -------------------------------------------------------
# FrFdPipeSensor Class
# 파이프(FD)의 읽기 이벤트를 감지하여 FrPipeSensor에게 전달하는 어댑터
# -------------------------------------------------------
class FrFdPipeSensor(FrRdFdSensor):
    def __init__(self, sensor, file_des):
        """
        C++: frFdPipeSensor(frPipeSensor* Sensor, int FileDes)
        :param sensor: 이벤트를 전달받을 FrPipeSensor 객체
        :param file_des: 감시할 파일 디스크립터 (Pipe의 Read End)
        """
        # 부모 클래스(FrRdFdSensor) 초기화 -> FD 등록 및 Select 감시 시작
        super().__init__(file_des)
        
        self.m_frPipeSensor = sensor

    def __del__(self):
        """
        C++: ~frFdPipeSensor()
        """
        super().__del__()

    def subject_changed(self):
        """
        C++: int SubjectChanged()
        Select 루프에서 FD에 읽기 이벤트가 발생하면 호출됨.
        여기서 실제 데이터 처리를 담당하는 PipeSensor의 메서드를 호출.
        """
        if self.m_frPipeSensor:
            # Duck Typing: receive_message 메서드가 있는지 확인
            if hasattr(self.m_frPipeSensor, 'receive_message'):
                self.m_frPipeSensor.receive_message()
            else:
                print("[FrFdPipeSensor] Error: Target sensor has no receive_message method")
        
        return 1