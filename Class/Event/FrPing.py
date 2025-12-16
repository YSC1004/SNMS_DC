import sys
import os
import time
from ping3 import ping

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# FrPingResult Class
# 핑 결과를 담는 구조체 (C++ FR_PING_RESULT 대응)
# -------------------------------------------------------
class FrPingResult:
    def __init__(self):
        self.m_Result = False   # 성공 여부
        self.m_DataSize = 0
        self.m_SndCnt = 0       # 보낸 횟수
        self.m_RcvCnt = 0       # 받은 횟수
        self.m_Loss = 0         # 손실률 (%)
        self.m_Min = 0          # 최소 시간 (ms)
        self.m_Max = 0          # 최대 시간 (ms)
        self.m_Avg = 0          # 평균 시간 (ms)
        self.m_ResultStr = ""   # 상세 결과 문자열

# -------------------------------------------------------
# FrPing Class
# ICMP Ping 유틸리티 (ping3 라이브러리 활용)
# -------------------------------------------------------
class FrPing:
    def __init__(self):
        pass

    def __del__(self):
        pass

    def init(self):
        # Python ping3 라이브러리는 별도의 초기화(Raw Socket 생성 등)가 필요 없음
        return True

    def ping(self, dest_ip, count=3, timeout=1000, data_size=56):
        """
        C++: bool Ping(FR_PING_RESULT& Result, ...)
        여러 번 핑을 보내고 통계를 내어 Result 객체를 반환
        timeout: 밀리초 단위
        """
        result = FrPingResult()
        result.m_SndCnt = count
        result.m_DataSize = data_size
        
        rtt_list = []
        total_time = 0.0
        result_str_list = [] # 문자열 조합용

        # Timeout (ms -> sec)
        timeout_sec = timeout / 1000.0

        for i in range(count):
            try:
                # unit='ms' : 밀리초 단위 반환
                # size : 데이터 크기 (ping3 기본값은 56)
                rtt = ping(dest_ip, timeout=timeout_sec, size=data_size, unit='ms')
                
                if rtt is None:
                    # Timeout
                    result_str_list.append(f"       icmp_seq = {i} :: PING FAIL (Timeout)\n")
                elif rtt is False:
                    # Error
                    result_str_list.append(f"       icmp_seq = {i} :: PING FAIL (Error)\n")
                else:
                    # Success
                    result.m_RcvCnt += 1
                    rtt_list.append(rtt)
                    total_time += rtt
                    result_str_list.append(f"       icmp_seq = {i}, time = {int(rtt)}\n")
                    
            except Exception as e:
                result_str_list.append(f"       icmp_seq = {i} :: PING FAIL ({e})\n")
            
            # 간격 (Interval) - C++ 코드엔 없지만 보통 1초 쉼
            if i < count - 1:
                time.sleep(1)

        # 통계 계산
        if result.m_RcvCnt > 0:
            result.m_Result = True
            result.m_Min = int(min(rtt_list))
            result.m_Max = int(max(rtt_list))
            result.m_Avg = int(total_time / result.m_RcvCnt)
            
            loss_cnt = result.m_SndCnt - result.m_RcvCnt
            result.m_Loss = int((loss_cnt / result.m_SndCnt) * 100)
        else:
            result.m_Result = False
            result.m_Min = 0
            result.m_Max = 0
            result.m_Avg = 0
            result.m_Loss = 100

        result.m_ResultStr = "".join(result_str_list)
        return result

    def get_res_string(self, result):
        """
        C++: string GetResString(FR_PING_RESULT& Result)
        결과 요약 문자열 반환
        """
        if result.m_Result:
            return f"snd/rcv/loss = {result.m_SndCnt}/{result.m_RcvCnt}/{result.m_Loss}, min/max/avg = {result.m_Min}/{result.m_Max}/{result.m_Avg}"
        else:
            return f"snd/rcv/loss = {result.m_SndCnt}/{result.m_RcvCnt}/{result.m_Loss}"