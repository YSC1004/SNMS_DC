import sys
import os
import logging
from datetime import datetime

# -------------------------------------------------------
# FrLogger Class
# Python built-in logging 모듈을 래핑하여 기존 C++ 인터페이스와 호환
# -------------------------------------------------------
class FrLogger:
    _instance = None # Singleton Instance

    def __init__(self):
        # Root Logger 설정
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO) # 기본 레벨
        
        # 기본 포맷터 (C++ GetTimeStamp 스타일 반영)
        # YYYY/MM/DD HH:MM:SS.mmm
        self.formatter = logging.Formatter(
            fmt='%(asctime)s.%(msecs)03d %(message)s',
            datefmt='%Y/%m/%d %H:%M:%S'
        )
        
        # 기본적으로 콘솔 핸들러 추가
        self._add_console_handler()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = FrLogger()
        return cls._instance

    def _add_console_handler(self):
        # 중복 추가 방지
        if not any(isinstance(h, logging.StreamHandler) for h in self.logger.handlers):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(self.formatter)
            self.logger.addHandler(console_handler)

    def open(self, log_file_name, dup_stdout_err=False):
        """
        C++: void Open(string logFileName, bool dupStdOutErr)
        파일 로깅을 활성화합니다.
        """
        try:
            file_handler = logging.FileHandler(log_file_name, mode='a', encoding='utf-8')
            file_handler.setFormatter(self.formatter)
            self.logger.addHandler(file_handler)
            
            if dup_stdout_err:
                # 표준 출력/에러를 로그 파일로 리다이렉션하는 것은 Python logging에서
                # 직접 지원하지 않으므로, 필요한 경우 sys.stdout/stderr을 교체해야 함.
                # 여기서는 logging 모듈을 통한 로깅만 처리함.
                pass
                
        except Exception as e:
            print(f"[FrLogger] Can't open log file {log_file_name}: {e}")

    # -------------------------------------------------------
    # Log Level Management
    # -------------------------------------------------------
    def enable(self, package, feature=None, level=logging.INFO):
        """
        특정 패키지/기능의 로그 레벨 설정
        """
        name = package
        if feature:
            name = f"{package}.{feature}"
            
        target_logger = logging.getLogger(name)
        target_logger.setLevel(level)

    def disable(self, package=None, feature=None):
        """
        로그 비활성화 (레벨을 CRITICAL보다 높게 설정하거나 핸들러 제거)
        여기서는 레벨을 CRITICAL + 1로 설정하여 사실상 끔
        """
        if package:
            self.enable(package, feature, logging.CRITICAL + 10)
        else:
            # 전체 비활성화
            self.logger.setLevel(logging.CRITICAL + 10)

    # -------------------------------------------------------
    # Logging Methods
    # -------------------------------------------------------
    def write(self, msg, level=logging.INFO):
        """
        기본 로거를 통한 쓰기
        """
        self.logger.log(level, msg)

    @staticmethod
    def get_timestamp():
        """
        C++: char* GetTimeStamp()
        """
        now = datetime.now()
        return now.strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]

# -------------------------------------------------------
# FrLogDef Class
# 각 모듈에서 개별적으로 생성하여 사용하는 로거 객체
# -------------------------------------------------------
class FrLogDef:
    def __init__(self, package, feature):
        """
        C++: frLogDef(string package, string feature)
        package.feature 이름의 로거를 생성/가져옴
        """
        self.logger_name = f"{package}.{feature}"
        self.logger = logging.getLogger(self.logger_name)
        
        # 부모(Root) 로거 설정을 따르도록 전파 설정
        self.logger.propagate = True

    def is_enable(self, level):
        return self.logger.isEnabledFor(level)

    def write(self, msg, level=logging.INFO):
        """
        C++: Write(const char *format, ...)
        Python은 포맷 문자열 대신 f-string 사용 권장
        """
        self.logger.log(level, msg)

# -------------------------------------------------------
# Helper Global Function (싱글톤 접근용)
# -------------------------------------------------------
def get_logger():
    return FrLogger.get_instance()