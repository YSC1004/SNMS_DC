import sys
import os

# 라이브러리 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 메인 프로세스 초기화 부분
from Class.Event.FrLogger import FrLogger, FrLogDef
import logging

# 1. 로거 초기화 및 파일 오픈
main_logger = FrLogger.get_instance()
main_logger.open("/home/ncadmin/SNMS/SNMS_DC/Log/server.log")

# 2. 각 모듈에서 로거 사용
my_log = FrLogDef("Network", "Socket")

# 로그 남기기
my_log.write("Server started", logging.INFO)
my_log.write("Connection failed", logging.ERROR)

# 3. 레벨 조정 (Network 패키지 전체를 DEBUG 레벨로)
main_logger.enable("Network", level=logging.DEBUG)