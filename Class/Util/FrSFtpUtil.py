import os
import sys
import paramiko
import stat

# -------------------------------------------------------
# 프로젝트 경로 설정 (모듈 Import용)
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# 필요 시 FrLogger 등 임포트 (여기서는 print로 대체)

# -------------------------------------------------------
# FrSFtpUtil Class
# Python paramiko를 사용하여 SFTP 기능 구현
# -------------------------------------------------------
class FrSFtpUtil:
    def __init__(self):
        self.ssh = None
        self.sftp = None
        self.m_User = ""
        self.m_Password = ""
        self.m_Host = ""
        self.m_Port = 22
        self.m_flag = False  # SSH Key 인증 성공 여부 플래그

    def __del__(self):
        self.close()

    def close(self):
        """
        C++: free_session, free_sftp, destructor
        """
        if self.sftp:
            try:
                self.sftp.close()
            except: pass
            self.sftp = None
            
        if self.ssh:
            try:
                self.ssh.close()
            except: pass
            self.ssh = None

    def sftp_connect(self, ip_address, port, user_id):
        """
        C++: bool SFtpConnect(...)
        기본 설정 및 클라이언트 초기화
        """
        self.m_Host = ip_address
        self.m_Port = port
        self.m_User = user_id

        try:
            self.ssh = paramiko.SSHClient()
            
            # C++: SSH_OPTIONS_STRICTHOSTKEYCHECK -> "no"
            # Python: AutoAddPolicy 사용 (Known hosts에 없어도 접속 허용)
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            return True
        except Exception as e:
            print(f"[FrSFtpUtil] Init Failed: {e}")
            return False

    def sftp_login(self, user_id, passwd):
        """
        C++: bool SFtpLogin(...)
        SSH 접속(인증) 후 SFTP 세션 오픈
        """
        if user_id: self.m_User = user_id
        self.m_Password = passwd

        # 1. 접속 및 인증 시도
        try:
            # paramiko는 keys를 자동으로 탐색함 (look_for_keys=True)
            # C++ 로직: Key 인증 시도 -> 실패 시 Password 인증
            # paramiko connect는 key가 있으면 key로, 없으면 password로 자동 시도함
            
            # C++ 코드에 있는 외부 명령어 실행 로직 (SSHCHECK)
            # if "sshkey" not in passwd: ... system(...) 
            # 필요하다면 아래 주석 해제하여 구현
            # if "sshkey" not in passwd:
            #     new_pass = f"{passwd}_sshkey"
            #     cmd = f"~/NAA/Bin/SSHCHECK {self.m_Host} '{new_pass}'"
            #     os.system(cmd)

            self.ssh.connect(
                hostname=self.m_Host,
                port=self.m_Port,
                username=self.m_User,
                password=self.m_Password,
                look_for_keys=True, # 공개키 자동 탐색
                timeout=10
            )
            
            # 인증 성공 여부 확인 (Key인지 PW인지 구분은 어렵지만 접속 성공이 중요)
            # paramiko transport 정보를 통해 유추 가능
            if self.ssh.get_transport().auth_handler.auth_method == 'publickey':
                print("[----SSH Public key authentication successful.!!!----]")
                self.m_flag = True
            else:
                print("[----SSH Password authentication successful.!!!----]")
                self.m_flag = False

            # 2. SFTP 세션 열기 (Sftp_init)
            self.sftp = self.ssh.open_sftp()
            return True

        except paramiko.AuthenticationException:
            print("[FrSFtpUtil] Authentication Failed")
            return False
        except Exception as e:
            print(f"[FrSFtpUtil] Login Error: {e}")
            return False

    def sftp_get(self, remote_path, local_file, mode=None):
        """
        C++: bool SFtpGet(...)
        """
        if not self.sftp: return False

        try:
            # paramiko get 메서드로 다운로드
            self.sftp.get(remote_path, local_file)
            return True
        except Exception as e:
            print(f"[FrSFtpUtil] SFtpGet Error: {e}")
            # 파일 쓰다가 에러나면 닫아주는 처리는 paramiko가 내부적으로 수행하거나
            # exception 발생 시 호출자가 처리
            return False

    def sftp_mkdir(self, path):
        """
        C++: bool SFtpMkdir(...)
        """
        if not self.sftp: return False
        try:
            self.sftp.mkdir(path)
            return True
        except IOError:
            # 이미 존재하는 경우 등 에러 처리
            print(f"[FrSFtpUtil] Can't create directory: {path}")
            return False

    def sftp_chdir(self, path):
        """
        C++: bool SFtpChdir(...)
        """
        if not self.sftp: return False
        try:
            self.sftp.chdir(path)
            return True
        except IOError:
            print(f"[FrSFtpUtil] Error Open Directory: {path}")
            return False

    def sftp_nlst(self, file_list, output_file, path, file_name_filter=None):
        """
        C++: bool SFtpNlst(...)
        파일명만 리스트에 추가
        """
        if not self.sftp: return False
        
        try:
            # 해당 경로의 파일 목록 가져오기
            # paramiko listdir은 이름만 문자열 리스트로 반환
            files = self.sftp.listdir(path) if path else self.sftp.listdir()
            
            for name in files:
                if name == "." or name == "..":
                    continue
                
                # 필터링 로직 (C++ strstr)
                if file_name_filter:
                    if file_name_filter not in name:
                        continue
                
                if isinstance(file_list, list):
                    file_list.append(name)
            return True

        except Exception as e:
            print(f"[FrSFtpUtil] SFtpNlst Error: {e}")
            return False

    def sftp_dir(self, file_list, output_file, path, file_name_filter=None):
        """
        C++: bool SFtpDir(...)
        상세 정보(권한, 소유자 등) 포함 리스트
        """
        if not self.sftp: return False

        try:
            # listdir_attr은 SFTPAttributes 객체 리스트 반환
            attrs = self.sftp.listdir_attr(path if path else '.')
            
            for attr in attrs:
                name = attr.filename
                if name == "." or name == "..":
                    continue

                # 필터링
                if file_name_filter and (file_name_filter not in name):
                    continue

                # C++ 포맷과 유사하게 문자열 생성 (Long Format)
                # 예: -rw-r--r-- 1 1000 1000 1234 Nov 11 12:00 filename
                long_str = str(attr) # paramiko attr 객체는 str() 호출 시 ls -l 형식 반환
                
                if isinstance(file_list, list):
                    file_list.append(long_str)
            return True

        except Exception as e:
            print(f"[FrSFtpUtil] SFtpDir Error: {e}")
            return False

    def ssh_check(self):
        return self.m_flag

    # (Optional) 파일 업로드 - C++ Sftp_file_write 대응
    def sftp_put(self, local_file, remote_path):
        if not self.sftp: return False
        try:
            self.sftp.put(local_file, remote_path)
            return True
        except Exception as e:
            print(f"[FrSFtpUtil] SFtpPut Error: {e}")
            return False