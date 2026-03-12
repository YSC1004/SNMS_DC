# -*- coding: utf-8 -*-
"""
ProcConnection.h / ProcConnection.C  →  ProcConnection.py
Python 3.11.10 변환

변환 설계:
  ProcConnection → ProcConnection  (AsSocket 상속)

C++ → Python 주요 변환 포인트:
  memset(&m_ProcStatus, 0, sizeof(ProcessStatus)) → ProcessStatus() 기본 초기화
  ProcConnectionMgr::GetProcessInfo(m_Pid, &m_ProcStatus)
    → ProcConnectionMgr.get_process_info(self._pid, self._proc_status)
  ProcessStatus* 반환                             → ProcessStatus 객체 반환
  m_ProcStatus->SendFlag                          → proc_status.send_flag

비고:
  C++ GetProcessInfo() 에 return 문이 없으나 ProcessStatus* 를 반환하도록
  의도된 것으로 보임 → Python 에서 self._proc_status 반환으로 처리.

변경 이력:
  2014.07.08  초기 작성 (C++ 원본)
  Python 변환
"""

import logging
from typing import Optional, TYPE_CHECKING

from Common.AsSocket import AsSocket
from Common.CommType import ProcessStatus

if TYPE_CHECKING:
    from Common.ProcConnectionMgr import ProcConnectionMgr

logger = logging.getLogger(__name__)


class ProcConnection(AsSocket):
    """
    C++ ProcConnection 대응.
    AsSocket 을 상속하며 프로세스 상태 정보(ProcessStatus)를 관리한다.
    """

    def __init__(self) -> None:
        super().__init__()
        self._proc_status:        ProcessStatus = ProcessStatus()
        self._pid:                int           = 0
        self._proc_info_send_flag: bool         = False

    def get_process_info(self) -> ProcessStatus:
        """
        C++ GetProcessInfo() 대응.
        ProcConnectionMgr 에서 PID 기준 프로세스 정보를 조회한 뒤
        SendFlag 를 설정하고 반환한다.

        최초 호출 시 send_flag=False (미전송 상태), 이후 True 로 전환.
        """
        from Common.ProcConnectionMgr import ProcConnectionMgr
        ProcConnectionMgr.get_process_info(self._pid, self._proc_status)

        self._proc_status.send_flag = self._proc_info_send_flag
        if not self._proc_info_send_flag:
            self._proc_info_send_flag = True

        return self._proc_status