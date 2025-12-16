import time

# -------------------------------------------------------
# ElaspedTime Class
# 실행 시간 측정 유틸리티
# -------------------------------------------------------
class ElaspedTime:
    def __init__(self):
        """
        C++: ElaspedTime()
        생성 시점의 시간을 측정
        """
        self.m_STime = 0.0
        self.m_ETime = 0.0
        self.Start() # C++ 생성자 로직과 동일하게 Start 호출

    def Start(self):
        """
        C++: void Start()
        시작 시간과 종료 시간을 현재 시간으로 초기화
        """
        # time.perf_counter(): 시간 측정용 고해상도 타이머 (초 단위 float 반환)
        now = time.perf_counter()
        self.m_STime = now
        self.m_ETime = now

    def End(self):
        """
        C++: void End()
        종료 시간 갱신
        """
        self.m_ETime = time.perf_counter()

    def GetElaspedSec(self):
        """
        C++: int GetElaspedSec()
        경과 시간 (초 단위 정수)
        """
        return int(self.GetElaspedMiliSec() / 1000)

    def GetElaspedMiliSec(self):
        """
        C++: int GetElaspedMiliSec()
        경과 시간 (밀리초 단위 정수)
        """
        # (종료시간 - 시작시간) = 경과 초(float)
        diff_sec = self.m_ETime - self.m_STime
        
        # 밀리초로 변환 (* 1000) 후 정수 변환
        return int(diff_sec * 1000)