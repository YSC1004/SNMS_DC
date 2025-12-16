import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrSensor import SENSOR_MODE

# 주의: FrSocketSensor 클래스가 정의된 파일이 필요합니다.
# 아직 변환되지 않았다면, 추후 FrSocketSensor.py를 만들고 import 해야 합니다.
try:
    from Class.Event.FrSocketSensor import FrSocketSensor
except ImportError:
    # FrSocketSensor가 아직 없다면 임시로 FrRdFdSensor를 상속받거나
    # Mock 클래스를 사용하도록 처리 (나중에 수정 필요)
    print("[FrSocket] Warning: FrSocketSensor not found. Inheriting from FrRdFdSensor temporarily.")
    from Class.Event.FrRdFdSensor import FrRdFdSensor as FrSocketSensor

# -------------------------------------------------------
# FrSocket Class
# 일반적인 소켓 기능을 제공하는 클래스
# (보통 Connect, Bind, Listen 등의 기능을 가짐 - 부모 클래스에 구현되어 있을 것으로 추정)
# -------------------------------------------------------
class FrSocket(FrSocketSensor):
    def __init__(self):
        """
        C++: frSocket():frSocketSensor(FR_NO_SENSOR)
        """
        # 부모 생성자 호출 (FR_NO_SENSOR 모드)
        # 이 모드는 센서를 생성하자마자 World에 등록하지 않음 (수동 제어)
        super().__init__(sensor_mode=SENSOR_MODE.FR_NO_SENSOR)

    def __del__(self):
        """
        C++: ~frSocket()
        """
        super().__del__()