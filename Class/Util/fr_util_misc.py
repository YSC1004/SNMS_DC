import os
import sys
import time
import signal
import socket
import math
import subprocess

# 앞서 만든 모듈 import
from Class.Util.FrDirReader import FrDirReader

class ECType:
    ctypeHangle = 0
    ctypeHanja = 1
    ctypeSpecial = 2
    ctypeSpace = 3
    ctypeEnglish = 4
    ctypeNumber = 5
    ctypeOther1 = 6

class FrUtilMisc:
    
    # -------------------------------------------------------
    # String Utilities
    # -------------------------------------------------------
    @staticmethod
    def is_empty_string(data):
        """
        C++: bool IsEmptyString(char* Data)
        공백 문자만 있는지 확인 (문자열이 비었거나 공백만 있으면 True)
        """
        if not data: return True
        return data.strip() == ""

    @staticmethod
    def get_last_error_str():
        """
        C++: const char* GetLastErrorStr()
        Python에서는 Exception 발생 시 해당 에러 메시지를 사용하므로
        이 함수는 보통 try-except 블록의 e를 문자열로 반환하는 용도로 대체됨
        """
        return "See Python Exception Details"

    @staticmethod
    def string_trim(data):
        """
        C++: StringTrim / StringTrim2 / StringLTrim / StringRTrim 통합
        """
        if not data: return ""
        return data.strip()

    @staticmethod
    def string_ltrim(data):
        if not data: return ""
        return data.lstrip()

    @staticmethod
    def string_rtrim(data):
        if not data: return ""
        return data.rstrip()

    @staticmethod
    def is_digit_string(data):
        """
        C++: bool IsDigitString(char* Data)
        """
        if not data: return False
        return data.isdigit()

    @staticmethod
    def string_upper(data):
        if not data: return ""
        return data.upper()

    @staticmethod
    def string_lower(data):
        if not data: return ""
        return data.lower()

    @staticmethod
    def string_replace(src, old, new, start_pos=-1, end_pos=-1):
        """
        C++: void StringReplace(...)
        Python string은 immutable이므로 교체된 새 문자열을 반환해야 함
        """
        if start_pos == -1 and end_pos == -1:
            return src.replace(old, new)
        
        # 부분 교체 로직 구현
        prefix = src[:start_pos] if start_pos > 0 else ""
        
        if end_pos == -1:
            target = src[start_pos:]
            suffix = ""
        else:
            target = src[start_pos:end_pos]
            suffix = src[end_pos:]
            
        return prefix + target.replace(old, new) + suffix

    @staticmethod
    def string_compare_caps(src1, src2):
        """
        대소문자 무시 비교
        """
        return src1.upper() == src2.upper()

    @staticmethod
    def get_size_to_string(size):
        """
        C++: string GetSizeToString(long Size)
        파일 크기를 사람이 읽기 쉬운 단위(KB, MB, GB)로 변환
        """
        if size > (1024**3):
            return f"{size / (1024**3):.3f} GB"
        elif size > (1024**2):
            return f"{size / (1024**2):.2f} MB"
        elif size > 1024:
            return f"{size / 1024:.2f} KB"
        else:
            return f"{size} byte"

    @staticmethod
    def get_start_char_type(char_str):
        """
        C++: ECType GetStartCharType(const char* Str)
        한글/한자 등 인코딩(EUC-KR/CP949 기준)에 따른 문자 타입 판별
        Python3는 유니코드를 사용하므로 로직이 다름.
        """
        if not char_str: return ECType.ctypeOther1
        
        first_char = char_str[0]
        
        if first_char.isspace():
            return ECType.ctypeSpace
        elif 'a' <= first_char <= 'z' or 'A' <= first_char <= 'Z':
            return ECType.ctypeEnglish
        elif '0' <= first_char <= '9':
            return ECType.ctypeNumber
        elif '가' <= first_char <= '힣': # 유니코드 한글 범위
            return ECType.ctypeHangle
        # 한자나 특수문자는 유니코드 범위 확인 필요 (여기서는 생략)
        
        return ECType.ctypeOther1

    # -------------------------------------------------------
    # Process & System Utilities
    # -------------------------------------------------------
    @staticmethod
    def get_pid():
        return os.getpid()

    @staticmethod
    def sleep(sec):
        time.sleep(sec)

    @staticmethod
    def sleep2(microseconds):
        time.sleep(microseconds / 1000000.0)

    @staticmethod
    def system(cmd):
        return os.system(cmd)

    @staticmethod
    def popen(command, mode='r'):
        """
        C++: FILE* Popen(...)
        Python subprocess 사용 권장
        """
        return os.popen(command, mode)

    @staticmethod
    def pclose(stream):
        return stream.close()

    @staticmethod
    def kill_process(pid):
        try:
            os.kill(pid, signal.SIGKILL) # kill -9
            return True
        except OSError:
            return False

    # -------------------------------------------------------
    # File / Directory Utilities
    # -------------------------------------------------------
    @staticmethod
    def mkdir(dir_name):
        try:
            os.makedirs(dir_name, exist_ok=True)
            return True
        except OSError:
            return False

    @staticmethod
    def delete_dir_file_in(dir_name, in_file_vector):
        """
        C++: 포함된 문자열이 있는 파일 삭제
        in_file_vector: 삭제할 파일명 패턴 리스트
        """
        reader = FrDirReader(dir_name)
        if not reader.has_more_file(): return True
        
        file_list = reader.get_file_list()
        
        for fname in file_list:
            # 패턴 매칭
            should_delete = False
            for pattern in in_file_vector:
                if pattern in fname:
                    should_delete = True
                    break
            
            if should_delete:
                full_path = os.path.join(dir_name, fname)
                try:
                    os.remove(full_path)
                except: pass
        return True

    @staticmethod
    def delete_dir_file_exc(dir_name, exc_file_vector):
        """
        C++: 포함된 문자열이 '없는' 파일 삭제 (제외하고 다 삭제)
        """
        reader = FrDirReader(dir_name)
        if not reader.has_more_file(): return True
        
        file_list = reader.get_file_list()
        
        for fname in file_list:
            should_delete = True
            for pattern in exc_file_vector:
                if pattern in fname:
                    should_delete = False # 패턴이 있으면 삭제 안 함
                    break
            
            if should_delete:
                full_path = os.path.join(dir_name, fname)
                try:
                    os.remove(full_path)
                except: pass
        return True

    @staticmethod
    def string_grep(src, grep_list):
        """
        C++: 문자열 안에 grep_list의 키워드가 하나라도 있는지 확인
        """
        for keyword in grep_list:
            if keyword in src:
                return True
        return False

    # -------------------------------------------------------
    # Network Utilities
    # -------------------------------------------------------
    @staticmethod
    def get_local_ip():
        try:
            # hostname을 통해 IP 조회
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except:
            return "127.0.0.1"

    @staticmethod
    def get_ip_str(ip_int):
        """
        C++: unsigned int IP -> String (Little Endian 고려)
        Python에서는 inet_ntoa 사용
        """
        try:
            # network byte order로 변환 후 문자열로
            return socket.inet_ntoa(ip_int.to_bytes(4, 'little')) 
        except:
            return "0.0.0.0"