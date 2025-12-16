import sys
import os

# -------------------------------------------------------------
# 1. 라이브러리 경로 설정
# -------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 파일: Server/ftp_test.py
from Class.Util.FrFtpUtil import FrFtpUtil

ftp = FrFtpUtil()

# 1. 연결
if ftp.ftp_connect("user", "pass", "127.0.0.1"):
    print("Connected!")
    
    # 2. 파일 목록 조회
    files = []
    ftp.ftp_nlst(files)
    print(f"Files: {files}")
    
    # 3. 다운로드
    ftp.ftp_get("downloaded.txt", "remote_file.txt")
    
    # 4. 업로드
    ftp.ftp_put("local_file.txt", "remote_uploaded.txt")
    
    ftp.ftp_quit()