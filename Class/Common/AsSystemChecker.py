import sys
import os
import socket
import resource

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.AsUtil import AsUtil
# FrSocketSensor는 버퍼 테스트용으로 사용되나, 
# 여기서는 의존성을 줄이기 위해 native socket을 직접 사용해도 됩니다.
# C++ 로직을 따르기 위해 import 합니다.
try:
    from Class.Event.FrSocketSensor import FrSocketSensor
except ImportError:
    FrSocketSensor = None

# -------------------------------------------------------
# AsSystemChecker Class
# 시스템 리소스 한계 및 정보 수집 유틸리티
# -------------------------------------------------------
class AsSystemChecker:
    
    @staticmethod
    def get_system_info(info):
        """
        C++: void GetSystemInfo(AS_SYSTEM_INFO_T* Info)
        시스템 정보를 수집하여 Info 객체에 채움
        """
        info.m_MaxOpenableFd = AsSystemChecker.get_max_openable_file_count()
        info.m_MaxRecvBuf = AsSystemChecker.get_max_sock_recv_buf_size()
        info.m_MaxSendBuf = AsSystemChecker.get_max_sock_send_buf_size()

        info.HostName = AsUtil.get_host_name()
        info.HostIp = AsUtil.get_local_ip()
        
        # C++: strcpy(Info->HostName, ...)
        # Python 객체이므로 단순 할당

    @staticmethod
    def get_max_openable_file_count():
        """
        C++: int GetMaxOpenableFileCount()
        현재 프로세스가 열 수 있는 최대 파일 수(FD) 조회
        """
        try:
            # RLIMIT_NOFILE: (soft_limit, hard_limit)
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            # print(f"max_files==={soft}")
            return soft
        except Exception as e:
            print(f"[AsSystemChecker] Get limit error: {e}")
            return 1024 # 기본값

    @staticmethod
    def get_max_sock_send_buf_size():
        """
        C++: int GetMaxSockSendBufSize()
        소켓 송신 버퍼 최대 크기 측정
        """
        return AsSystemChecker._measure_socket_buffer(socket.SO_SNDBUF)

    @staticmethod
    def get_max_sock_recv_buf_size():
        """
        C++: int GetMaxSockRecvBufSize()
        소켓 수신 버퍼 최대 크기 측정
        """
        return AsSystemChecker._measure_socket_buffer(socket.SO_RCVBUF)

    # ---------------------------------------------------
    # Helper Method (Native Socket Logic)
    # ---------------------------------------------------
    @staticmethod
    def _measure_socket_buffer(opt_name):
        """
        실제 소켓을 열어 버퍼 크기를 늘려가며 한계를 측정하는 로직
        (C++ FrSocketSensor::GetMaxCan... 로직 대체)
        """
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # 현재 값 조회
            current_size = sock.getsockopt(socket.SOL_SOCKET, opt_name)
            
            # 최대값 탐색 (C++ 로직: 4096부터 512씩 증가)
            # Python에서는 OS 레벨에서 허용하는 최대치를 바로 알기 어렵으므로
            # setsockopt가 실패하거나 값이 적용되지 않을 때까지 시도
            
            test_size = 4096
            max_allowed = current_size
            MAX_LIMIT = 1024 * 1024 * 200 # 200MB (C++ MAX_SOCK_BUF_SIZE)

            while test_size < MAX_LIMIT:
                try:
                    sock.setsockopt(socket.SOL_SOCKET, opt_name, test_size)
                    # 설정된 값 확인 (OS가 2배로 잡거나 제한할 수 있음)
                    actual_size = sock.getsockopt(socket.SOL_SOCKET, opt_name)
                    
                    # 리눅스는 setsockopt로 설정한 값의 2배를 커널이 잡는 경우가 많음.
                    # 설정 시도한 값보다 작게 잡히면 한계 도달로 판단
                    if actual_size < test_size: 
                         break
                    
                    max_allowed = actual_size
                    test_size += 5120 # 증가폭을 키움 (Python 속도 고려)
                    
                except OSError:
                    break
            
            return max_allowed

        except Exception as e:
            # print(f"[AsSystemChecker] Socket Buffer Check Error: {e}")
            return -1
        finally:
            if sock: sock.close()