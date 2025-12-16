import ftplib
import os
import sys

# -------------------------------------------------------
# FrFtpUtil Class
# Python ftplib를 래핑하여 기존 C++ 인터페이스와 호환성 제공
# -------------------------------------------------------
class FrFtpUtil:
    def __init__(self):
        self.ftp = ftplib.FTP()
        self.m_FtpLibDebug = 0
        self.m_User = ""
        self.m_Password = ""
        self.m_Host = ""
        self.m_Port = 21
        self.is_connected = False

    def __del__(self):
        self.ftp_quit()

    def set_debug_level(self, level):
        """
        C++: void SetDebugLevel(int Level)
        """
        self.m_FtpLibDebug = level
        self.ftp.set_debuglevel(level)

    def ftp_connect(self, user_id, passwd, ip_address, port=21):
        """
        C++: bool FtpConnect(...)
        연결과 로그인을 순차적으로 수행
        """
        self.m_User = user_id
        self.m_Password = passwd
        self.m_Host = ip_address
        self.m_Port = port

        try:
            # 1. 연결
            self.ftp.connect(self.m_Host, self.m_Port, timeout=30)
            
            # 2. 로그인 (C++ FtpLogin 기능 포함)
            self.ftp.login(self.m_User, self.m_Password)
            
            self.is_connected = True
            return True
        except ftplib.all_errors as e:
            print(f"[FrFtpUtil] Connect Failed: {e}")
            return False

    def ftp_quit(self):
        """
        C++: void FtpQuit()
        """
        if self.is_connected:
            try:
                self.ftp.quit()
            except:
                try: self.ftp.close()
                except: pass
            self.is_connected = False

    # -------------------------------------------------------
    # Directory & File Operations
    # -------------------------------------------------------
    def ftp_chdir(self, path):
        try:
            self.ftp.cwd(path)
            return True
        except ftplib.all_errors: return False

    def ftp_cdup(self):
        try:
            self.ftp.cwd("..")
            return True
        except ftplib.all_errors: return False

    def ftp_mkdir(self, path):
        try:
            self.ftp.mkd(path)
            return True
        except ftplib.all_errors: return False

    def ftp_rmdir(self, path):
        try:
            self.ftp.rmd(path)
            return True
        except ftplib.all_errors: return False

    def ftp_pwd(self):
        try:
            return self.ftp.pwd()
        except ftplib.all_errors: return ""

    def ftp_delete(self, filename):
        try:
            self.ftp.delete(filename)
            return True
        except ftplib.all_errors: return False

    def ftp_rename(self, src, dst):
        try:
            self.ftp.rename(src, dst)
            return True
        except ftplib.all_errors: return False

    def ftp_size(self, filename):
        try:
            return self.ftp.size(filename)
        except ftplib.all_errors: return -1

    # -------------------------------------------------------
    # File Transfer (Get/Put)
    # -------------------------------------------------------
    def ftp_get(self, local_file, remote_file, mode='I'):
        """
        C++: bool FtpGet(...)
        mode: 'I' (Binary), 'A' (Ascii)
        """
        try:
            if mode == 'A':
                # 텍스트 모드 다운로드
                with open(local_file, 'w', encoding='utf-8') as f:
                    def callback(data):
                        f.write(data + '\n')
                    self.ftp.retrlines(f'RETR {remote_file}', callback)
            else:
                # 바이너리 모드 다운로드 (기본)
                with open(local_file, 'wb') as f:
                    self.ftp.retrbinary(f'RETR {remote_file}', f.write)
            return True
        except Exception as e:
            print(f"[FrFtpUtil] FtpGet Error: {e}")
            return False

    def ftp_put(self, local_file, remote_file, mode='I'):
        """
        C++: bool FtpPut(...)
        """
        if not os.path.exists(local_file):
            print(f"[FrFtpUtil] Local file not found: {local_file}")
            return False

        try:
            if mode == 'A':
                # 텍스트 모드 업로드
                with open(local_file, 'r', encoding='utf-8') as f:
                    self.ftp.storlines(f'STOR {remote_file}', f)
            else:
                # 바이너리 모드 업로드 (기본)
                with open(local_file, 'rb') as f:
                    self.ftp.storbinary(f'STOR {remote_file}', f)
            return True
        except Exception as e:
            print(f"[FrFtpUtil] FtpPut Error: {e}")
            return False

    # -------------------------------------------------------
    # List Operations (NLST, LIST)
    # -------------------------------------------------------
    def ftp_nlst(self, output_list, path=None):
        """
        C++: bool FtpNlst(frStringVector* OutputLine...)
        파일 이름만 리스트로 반환 (NLST)
        """
        try:
            # 경로가 지정되면 이동 후 수행하고 복귀
            current_dir = self.ftp.pwd()
            if path:
                self.ftp.cwd(path)

            files = []
            self.ftp.retrlines('NLST', files.append)
            
            # 결과 리스트에 추가 (extend)
            if isinstance(output_list, list):
                output_list.extend(files)

            if path:
                self.ftp.cwd(current_dir) # 원복
            return True
        except ftplib.all_errors as e:
            print(f"[FrFtpUtil] FtpNlst Error: {e}")
            return False

    def ftp_dir(self, output_list, path=None):
        """
        C++: bool FtpDir(...)
        상세 정보 리스트 반환 (LIST)
        """
        try:
            current_dir = self.ftp.pwd()
            if path:
                self.ftp.cwd(path)

            lines = []
            self.ftp.retrlines('LIST', lines.append)
            
            if isinstance(output_list, list):
                output_list.extend(lines)

            if path:
                self.ftp.cwd(current_dir)
            return True
        except ftplib.all_errors as e:
            print(f"[FrFtpUtil] FtpDir Error: {e}")
            return False