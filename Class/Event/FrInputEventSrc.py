import sys
import os

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrEventSrc import FrEventSrc

# -------------------------------------------------------
# FrInputEventSrc Class
# 등록된 여러 센서들의 I/O 요청을 취합하여 FrWorld에 전달하는 중계 클래스
# -------------------------------------------------------
class FrInputEventSrc(FrEventSrc):
    def __init__(self):
        """
        C++: frInputEventSrc()
        """
        super().__init__()

    def make_select_request(self, rd_list, wr_list, ex_list, world_ptr):
        """
        C++: int MakeSelectRequest(fd_set* Rd, fd_set* Wr, fd_set* Ex, timeval* Time)
        
        등록된 모든 센서를 순회하며, 활성화된 센서의 소켓(FD)을
        감시 대상 리스트(rd_list 등)에 추가하도록 위임합니다.
        """
        # FrEventSrc(부모)의 m_SensorList 사용
        for sensor in self.m_SensorList:
            # Duck Typing: 메서드가 존재하고 활성화 상태인지 확인
            if hasattr(sensor, 'is_enabled') and sensor.is_enabled():
                if hasattr(sensor, 'make_select_request'):
                    # C++의 Time 인자는 FrWorld 레벨에서 관리되거나 
                    # timer_event_src에서 처리되므로 여기서는 생략 가능하지만,
                    # 확장성을 위해 world_ptr을 통해 접근하도록 함.
                    sensor.make_select_request(rd_list, wr_list, ex_list, world_ptr)
        return 1

    def get_events(self, rd_list, wr_list, ex_list, world_ptr):
        """
        C++: int GetEvents(fd_set* Rd, fd_set* Wr, fd_set* Ex, timeval* Time)
        
        Select 결과(이벤트가 발생한 소켓 리스트)를 각 센서에게 전달하여
        자신이 처리해야 할 이벤트인지 확인하게 합니다.
        """
        for sensor in self.m_SensorList:
            if hasattr(sensor, 'is_enabled') and sensor.is_enabled():
                if hasattr(sensor, 'get_events'):
                    sensor.get_events(rd_list, wr_list, ex_list, world_ptr)
        return 1