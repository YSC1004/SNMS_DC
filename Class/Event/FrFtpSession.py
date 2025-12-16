import sys
import os
import ftplib
import time

# 프로젝트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Util.FrUtilMisc import FrUtilMisc

# -------------------------------------------------------
# Enums
# -------------------------------------------------------
class FR_FTP_CON_MODE:
    FR_FTP_PASSIVE = 0
    FR_FTP_ACTIVE = 1

class FR_FTP_SYS_TYPE:
    FR_SYS_TYPE_UNKNOWN = 0
    FR_SYS_TYPE_UNIX = 1
    FR_SYS_TYPE_NT = 2

class FR_FTP_DATA_MODE:
    FR_FTP_ASCII = 0
    FR_FTP_BINARY = 1

# -------------------------------------------------------
# FrFtpSession Class
# 소켓 기반 FTP 구현을 Python ftplib로 대체
# -------------------------------------------------------
class FrFtpSession:
    def __init__(self):
        self.m_DebugCond = False
        self.m_Ftp = ftplib.FTP()
        self.m_User = ""
        self.m_Password = ""
        self.m_Host = ""
        self.m_Port = 21
        self.m_FtpConMode = FR_FTP_CON_MODE.FR_FTP_PASSIVE
        self.m_FtpSysType = FR_FTP_SYS_TYPE.FR_SYS_TYPE_UNKNOWN
        self.m_LastResponse = ""
        self.is_connected = False

    def __del__(self):
        self.cmd_quit()

    def set_debug_on_off(self, on_off):
        self.m_DebugCond = on_off
        if self.m_DebugCond:
            self.m_Ftp.set_debuglevel(1)
        else:
            self.m_Ftp.set_debuglevel(0)

    def set_ftp_sys_type(self, sys_type):
        self.m_FtpSysType = sys_type

    # ---------------------------------------------------
    # Connection & Login
    # ---------------------------------------------------
    def connect(self, user_id, passwd, ip_address, port=21, con_mode=FR_FTP_CON_MODE.FR_FTP_PASSIVE):
        """
        C++: bool Connect(...)
        """
        self.m_User = user_id
        self.m_Password = passwd
        self.m_Host = ip_address
        self.m_Port = port
        self.m_FtpConMode = con_mode

        try:
            # 1. 연결
            self.m_Ftp.connect(self.m_Host, self.m_Port, timeout=30)
            self.m_LastResponse = self.m_Ftp.welcome
            
            # 2. 모드 설정 (Active/Passive)
            if self.m_FtpConMode == FR_FTP_CON_MODE.FR_FTP_PASSIVE:
                self.m_Ftp.set_pasv(True)
            else:
                self.m_Ftp.set_pasv(False)

            self.is_connected = True
            return True
        except ftplib.all_errors as e:
            self.m_LastResponse = str(e)
            print(f"[FrFtpSession] Connect Error: {e}")
            return False

    def login(self, user_id=None, passwd=None):
        """
        C++: bool Login(...)
        """
        if user_id: self.m_User = user_id
        if passwd: self.m_Password = passwd

        try:
            resp = self.m_Ftp.login(self.m_User, self.m_Password)
            self.m_LastResponse = resp
            
            # 시스템 타입 확인 (SYST)
            try:
                sys_resp = self.m_Ftp.voidcmd("SYST")
                if "UNIX" in sys_resp.upper() or "LINUX" in sys_resp.upper():
                    self.m_FtpSysType = FR_FTP_SYS_TYPE.FR_SYS_TYPE_UNIX
                elif "WINDOWS" in sys_resp.upper():
                    self.m_FtpSysType = FR_FTP_SYS_TYPE.FR_SYS_TYPE_NT
                else:
                    self.m_FtpSysType = FR_FTP_SYS_TYPE.FR_SYS_TYPE_UNKNOWN
            except:
                pass
                
            return True
        except ftplib.all_errors as e:
            self.m_LastResponse = str(e)
            print(f"[FrFtpSession] Login Error: {e}")
            return False

    def cmd_quit(self):
        """
        C++: bool Cmd_Quit()
        """
        if self.is_connected:
            try:
                self.m_Ftp.quit()
            except:
                try: self.m_Ftp.close()
                except: pass
            self.is_connected = False
        return True

    def get_last_response(self):
        return self.m_LastResponse

    # ---------------------------------------------------
    # Commands (Dir, Mkdir, Delete, Rename, etc.)
    # ---------------------------------------------------
    def cmd_pwd(self):
        try:
            return self.m_Ftp.pwd()
        except ftplib.all_errors as e:
            self.m_LastResponse = str(e)
            return ""

    def cmd_chdir(self, path):
        try:
            self.m_Ftp.cwd(path)
            return True
        except ftplib.all_errors as e:
            self.m_LastResponse = str(e)
            return False

    def cmd_cdup(self):
        try:
            self.m_Ftp.cwd("..")
            return True
        except ftplib.all_errors as e:
            self.m_LastResponse = str(e)
            return False

    def cmd_mkdir(self, path):
        try:
            self.m_Ftp.mkd(path)
            return True
        except ftplib.all_errors as e:
            self.m_LastResponse = str(e)
            return False

    def cmd_rmdir(self, path):
        try:
            self.m_Ftp.rmd(path)
            return True
        except ftplib.all_errors as e:
            self.m_LastResponse = str(e)
            return False

    def cmd_file_delete(self, filename):
        try:
            self.m_Ftp.delete(filename)
            return True
        except ftplib.all_errors as e:
            self.m_LastResponse = str(e)
            return False

    def cmd_file_rename(self, src, dest):
        try:
            self.m_Ftp.rename(src, dest)
            return True
        except ftplib.all_errors as e:
            self.m_LastResponse = str(e)
            return False

    def cmd_file_size(self, path):
        try:
            return self.m_Ftp.size(path)
        except ftplib.all_errors as e:
            self.m_LastResponse = str(e)
            return -1

    # ---------------------------------------------------
    # List Commands (NLST / LIST)
    # ---------------------------------------------------
    def cmd_nlist(self, file_list, path=None, file_name=None):
        """
        C++: Cmd_NList -> 파일 이름만 리스트로 반환
        """
        try:
            # 이동
            curr_dir = self.m_Ftp.pwd()
            if path:
                self.m_Ftp.cwd(path)

            # 목록 조회
            lines = []
            cmd = "NLST"
            if file_name: cmd += f" {file_name}"
            
            self.m_Ftp.retrlines(cmd, lines.append)
            
            # 결과 저장
            if isinstance(file_list, list):
                file_list.extend(lines)

            # 복귀
            if path:
                self.m_Ftp.cwd(curr_dir)
            return True
        except ftplib.all_errors as e:
            self.m_LastResponse = str(e)
            return False

    def cmd_dir(self, file_list, path=None, file_name=None):
        """
        C++: Cmd_Dir -> 상세 정보(ls -l) 리스트 반환
        """
        try:
            curr_dir = self.m_Ftp.pwd()
            if path:
                self.m_Ftp.cwd(path)

            lines = []
            cmd = "LIST"
            if file_name: cmd += f" {file_name}"
            
            self.m_Ftp.retrlines(cmd, lines.append)
            
            if isinstance(file_list, list):
                file_list.extend(lines)

            if path:
                self.m_Ftp.cwd(curr_dir)
            return True
        except ftplib.all_errors as e:
            self.m_LastResponse = str(e)
            return False

    # ---------------------------------------------------
    # File Transfer (Get / Put)
    # ---------------------------------------------------
    def cmd_file_get(self, remote_file, local_file, mode=FR_FTP_DATA_MODE.FR_FTP_BINARY):
        try:
            if mode == FR_FTP_DATA_MODE.FR_FTP_ASCII:
                with open(local_file, 'w', encoding='utf-8') as f:
                    self.m_Ftp.retrlines(f'RETR {remote_file}', lambda s: f.write(s + '\n'))
            else:
                with open(local_file, 'wb') as f:
                    self.m_Ftp.retrbinary(f'RETR {remote_file}', f.write)
            return True
        except Exception as e:
            self.m_LastResponse = str(e)
            print(f"[FrFtpSession] File Get Error: {e}")
            return False

    def cmd_file_put(self, local_file, remote_file, mode=FR_FTP_DATA_MODE.FR_FTP_BINARY):
        if not os.path.exists(local_file):
            self.m_LastResponse = f"Local file not found: {local_file}"
            return False

        try:
            if mode == FR_FTP_DATA_MODE.FR_FTP_ASCII:
                with open(local_file, 'r', encoding='utf-8') as f:
                    self.m_Ftp.storlines(f'STOR {remote_file}', f)
            else:
                with open(local_file, 'rb') as f:
                    self.m_Ftp.storbinary(f'STOR {remote_file}', f)
            return True
        except Exception as e:
            self.m_LastResponse = str(e)
            print(f"[FrFtpSession] File Put Error: {e}")
            return False

    # ---------------------------------------------------
    # Parsing Helpers (NT/UNIX List Parsing)
    # ---------------------------------------------------
    # Python ftplib는 파싱 기능을 직접 제공하지 않음.
    # C++ 코드의 복잡한 파싱 로직(Cmd_NList_NT, Cmd_NList_UNIX)은
    # 필요하다면 이곳에 추가 구현해야 함.
    # 보통은 LIST 결과 문자열을 split() 하여 처리함.
    
    def parse_list_line(self, line):
        """
        단순 예시: 공백으로 분리하여 반환
        """
        return line.split()