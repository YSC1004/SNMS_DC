# -*- coding: utf-8 -*-
"""
AsSystemChecker.h / AsSystemChecker.C  →  AsSystemChecker.py
Python 3.11.10 변환

변환 설계:
  AsSystemChecker  → AsSystemChecker  (static 메서드만 보유, 인스턴스 불필요)

C++ → Python 주요 변환 포인트:
  getrlimit(RLIMIT_NOFILE)         → resource.getrlimit(resource.RLIMIT_NOFILE)
  frSocketSensor.GetMaxCanSendBuf  → FrSocketSensor().get_max_can_send_sock_buf()
  frSocketSensor.GetMaxCanRecvBuf  → FrSocketSensor().get_max_can_recv_sock_buf()
  AsUtil::GetHostName()            → AsUtil.get_host_name()
  AsUtil::GetLocalIp()             → AsUtil.get_local_ip()
  AS_SYSTEM_INFO_T*                → AsSystemInfo (dataclass, CommType.py 정의)

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환 - 전 메서드 @staticmethod 처리
"""

import logging
import resource
from Common.CommType import AsSystemInfo
from Common.AsUtil import AsUtil
from Event.fr_socket_sensor import FrSocketSensor

logger = logging.getLogger(__name__)


class AsSystemChecker:
    """
    C++ AsSystemChecker 대응 유틸리티 클래스.
    모든 메서드가 @staticmethod 이므로 인스턴스 생성 없이 사용.

    사용 예:
        info = AsSystemInfo()
        AsSystemChecker.get_system_info(info)
        print(info.host_name, info.max_openable_fd)
    """

    @staticmethod
    def get_system_info(info: AsSystemInfo) -> None:
        """
        C++ GetSystemInfo(AS_SYSTEM_INFO_T*) 대응.
        info 객체에 시스템 정보를 채워 넣는다.
        """
        info.max_openable_fd = AsSystemChecker.get_max_openable_file_count()
        info.max_recv_buf    = AsSystemChecker.get_max_sock_recv_buf_size()
        info.max_send_buf    = AsSystemChecker.get_max_sock_send_buf_size()
        info.host_name       = AsUtil.get_host_name()
        info.host_ip         = AsUtil.get_local_ip()

    @staticmethod
    def get_max_openable_file_count() -> int:
        """
        C++ GetMaxOpenableFileCount() 대응.
        getrlimit(RLIMIT_NOFILE) 의 현재 소프트 리밋 반환.
        """
        soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        logger.debug("max_files = %d", soft)
        return soft

    @staticmethod
    def get_max_sock_send_buf_size() -> int:
        """
        C++ GetMaxSockSendBufSize() 대응.
        임시 소켓을 생성하여 최대 송신 버퍼 크기를 조회한다.
        소켓 생성 실패 시 -1 반환.
        """
        sock = FrSocketSensor()
        if not sock.create():
            return -1
        return sock.get_max_can_send_sock_buf()

    @staticmethod
    def get_max_sock_recv_buf_size() -> int:
        """
        C++ GetMaxSockRecvBufSize() 대응.
        임시 소켓을 생성하여 최대 수신 버퍼 크기를 조회한다.
        소켓 생성 실패 시 -1 반환.
        """
        sock = FrSocketSensor()
        if not sock.create():
            return -1
        return sock.get_max_can_recv_sock_buf()