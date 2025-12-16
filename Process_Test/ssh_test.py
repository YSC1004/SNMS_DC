import sys
import os

# -------------------------------------------------------------
# 1. 라이브러리 경로 설정
# -------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 파일: Server/ssh_test.py
from Class.Util.FrSshUtil import FrSshUtil

ssh = FrSshUtil()

# 1. 단순 실행 및 출력
ssh.ssh_connect("ktoss.iptime.org", 20022, "ncadmin", "ncadmin000!@", "ls -al /home/ncadmin/SNMS")

# 2. 결과 받아오기
result = ssh.ssh_send_cmd("ktoss.iptime.org", 20022, "ncadmin", "ncadmin000!@", "df -h")
if result:
    print(f"Disk Usage:\n{result}")