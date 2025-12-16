import sys
import os
import signal
import errno

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrRdFdSensor import FrRdFdSensor
from Class.Event.FrFilePollingTimer import FrFilePollingTimer

# -------------------------------------------------------
# FrFileFdSensor Class
# 파일을 주기적으로 감시(Polling)하는 센서
# -------------------------------------------------------
class FrFileFdSensor(FrRdFdSensor):
    def __init__(self):
        """
        C++: frFileFdSensor()
        """
        super().__init__()
        
        # 기본적으로 비활성화 (파일 열기 전까지)
        self.disable()
        
        # SIGPIPE 시그널 무시 (네트워크/파이프 끊김 시 종료 방지)
        # C++: frSignalEventSrc::SignalsBlock(SIGPIPE)
        try:
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        except:
            pass # 윈도우 등 일부 환경 예외 처리

        self.m_PollingTime = 1 # 초 단위
        self.m_Timer = None    # FrFilePollingTimer

    def __del__(self):
        """
        C++: ~frFileFdSensor()
        """
        self.close()
        if self.m_Timer:
            # 타이머 센서 해제 (FrTimerSensor 상속 객체이므로 unregister 필요)
            self.m_Timer.unregister_sensor()
            self.m_Timer = None
        super().__del__()

    def open_file(self, file_name):
        """
        C++: bool OpenFile(string FileName)
        파일을 열고, 끝(End)으로 커서를 이동시킨 뒤 폴링 타이머 시작
        """
        if self.m_FD != -1:
            self.close()

        try:
            # O_RDWR | O_CREAT 모드로 열기 (0644)
            self.m_FD = os.open(file_name, os.O_RDWR | os.O_CREAT, 0o644)
            
            # FD 설정 (Close on Exec 등)
            self.set_close_on_exec(True)
            
            # 파일 끝으로 이동 (기존 내용은 무시하고 새로 추가된 내용만 보겠다는 의도)
            os.lseek(self.m_FD, 0, os.SEEK_END)
            
            # 폴링 타이머 생성 및 시작
            if self.m_Timer is None:
                self.m_Timer = FrFilePollingTimer(self)
                
            # 타이머 설정 (m_PollingTime 후에 Enable 되도록 예약)
            # Reason ID: 100 (C++ 코드 참조)
            self.m_Timer.set_timer(self.m_PollingTime, 100)
            
            return True

        except OSError as e:
            print(f"[FrFileFdSensor] Open File Error ({file_name}): {e}")
            return False

    def subject_changed(self):
        """
        C++: int SubjectChanged()
        Select 루프에서 읽기 가능 신호가 오면 호출됨
        """
        # 1. 데이터가 있는지 살짝 읽어봄 (1바이트)
        data = self.read(1)
        
        if data and len(data) == 1:
            # 데이터가 있다면 읽은 1바이트를 다시 되돌려놓음 (Peek 효과)
            try:
                os.lseek(self.m_FD, -1, os.SEEK_CUR)
            except OSError:
                pass
                
            # 실제 처리를 위한 가상 함수 호출
            self.file_event_read()

        # 2. 중요: 처리가 끝났으므로 자신을 비활성화 (Disable)
        # 계속 켜두면 파일은 항상 Readable 하므로 Select가 무한 루프 돔
        self.disable()
        
        # 3. 타이머 재설정 (일정 시간 뒤에 다시 Enable 되어 감시하도록)
        if self.m_Timer:
            self.m_Timer.set_timer(self.m_PollingTime, 100)
            
        return 1

    def set_polling_time(self, sec):
        self.m_PollingTime = sec

    def get_polling_time(self):
        return self.m_PollingTime

    def close(self):
        """
        C++: bool Close()
        """
        if self.m_Timer:
            self.m_Timer.cancel_all_timer()
            # 타이머 객체 자체는 재사용을 위해 삭제하지 않거나, 
            # C++ 처럼 delete 하려면 참조 해제
            
        return super().close()

    # ---------------------------------------------------
    # Virtual Function (Override Target)
    # ---------------------------------------------------
    def file_event_read(self):
        """
        C++: virtual void FileEventRead()
        실제 파일 데이터를 읽어서 처리하는 로직을 여기에 구현
        """
        # print("[FrFileFdSensor] File Event Detected! (Override this method)")
        pass