import sys
import os
import paramiko

# -------------------------------------------------------
# 프로젝트 경로 설정
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# FrSshUtil Class
# Python paramiko를 사용하여 SSH 명령 실행 구현
# -------------------------------------------------------
class FrSshUtil:
    def __init__(self):
        self.ssh = None
        self.m_User = ""
        self.m_Password = ""
        self.m_Host = ""
        self.m_Port = 22

    def __del__(self):
        self.close()

    def close(self):
        """
        C++: free_channel, free_session
        """
        if self.ssh:
            try:
                self.ssh.close()
            except: pass
            self.ssh = None

    def ssh_connect(self, ip_address, port, user, passwd, cmd=None):
        """
        C++: bool SshConnect(...)
        단순 연결 및 명령 실행 (결과를 stdout으로 출력)
        """
        self.m_Host = ip_address
        self.m_Port = port
        self.m_User = user
        self.m_Password = passwd

        try:
            # 1. SSH 클라이언트 생성 및 연결
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            print(f"[FrSshUtil] Connecting to {ip_address}...")
            self.ssh.connect(
                hostname=self.m_Host,
                port=self.m_Port,
                username=self.m_User,
                password=self.m_Password,
                timeout=10
            )
            
            # 2. 명령 실행
            if cmd:
                print(f"[FrSshUtil] Executing remote command: {cmd}")
                stdin, stdout, stderr = self.ssh.exec_command(cmd)
                
                # 3. 결과 출력 (C++의 fwrite(buffer... stdout) 대응)
                # 실시간 출력을 위해 iter_lines 사용 가능하나, 간단히 read() 후 출력
                output = stdout.read().decode('utf-8', errors='ignore')
                if output:
                    print("[Received]:")
                    print(output)
                
                err = stderr.read().decode('utf-8', errors='ignore')
                if err:
                    print(f"[Remote Error]: {err}")

            self.close()
            return True

        except Exception as e:
            print(f"[FrSshUtil] Error: {e}")
            self.close()
            return False

    def ssh_send_cmd(self, ip_address, port, user, passwd, cmd):
        """
        C++: char* SshSendCmd(...)
        명령 실행 후 결과를 문자열로 반환
        """
        self.m_Host = ip_address
        self.m_Port = port
        self.m_User = user
        self.m_Password = passwd
        
        result_str = ""

        try:
            # 1. 연결
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.ssh.connect(
                hostname=self.m_Host,
                port=self.m_Port,
                username=self.m_User,
                password=self.m_Password,
                timeout=10
            )
            
            # 2. 실행
            stdin, stdout, stderr = self.ssh.exec_command(cmd)
            
            # 3. 결과 수집 (버퍼링 없이 전체 읽기)
            # C++ 코드에서는 500,000 바이트 버퍼 사용 -> Python은 메모리 허용 범위 내 자동 처리
            result_str = stdout.read().decode('utf-8', errors='ignore')
            
            # 에러도 필요하면 수집 가능
            # err_str = stderr.read().decode('utf-8')
            
            self.close()
            return result_str

        except Exception as e:
            print(f"[FrSshUtil] Error in SshSendCmd: {e}")
            self.close()
            return None # 또는 빈 문자열 ""