import os
import sys
import collections

# -------------------------------------------------------
# Enum Definition
# -------------------------------------------------------
class READ_TYPE:
    ALL_TYPE = 0
    DIR_TYPE = 1
    FILE_TYPE = 2

# -------------------------------------------------------
# FrDirReader Class
# -------------------------------------------------------
class FrDirReader:
    def __init__(self, target_dir=""):
        self.m_TargetDir = target_dir
        # pop_front() 기능을 위해 deque 사용 (C++의 list/deque 대응)
        self.m_FileList = collections.deque()
        
        if target_dir:
            self.set_dir(target_dir)

    def __del__(self):
        self.m_FileList.clear()

    # -------------------------------------------------------
    # Directory Navigation
    # -------------------------------------------------------
    def set_dir(self, target_dir):
        """
        C++: void Set(string TargetDir)
        """
        self.m_TargetDir = target_dir
        self.m_FileList.clear()
        self.read_dir(target_dir, self.m_FileList)

    def is_exist_file(self, file_name):
        """
        C++: bool IsExistFile(string FileName)
        리스트 내에 파일명이 존재하는지 확인
        """
        return file_name in self.m_FileList

    def has_more_file(self):
        """
        C++: bool HasMoreFile()
        """
        return len(self.m_FileList) > 0

    def next(self):
        """
        C++: string Next()
        리스트의 앞에서 하나를 꺼내서 반환 (Pop Front)
        """
        if self.m_FileList:
            return self.m_FileList.popleft()
        return ""

    def get_file_list(self):
        """
        C++: frStringList* GetFileList()
        """
        return self.m_FileList

    def read_dir(self, target_dir, file_list, read_type=READ_TYPE.ALL_TYPE):
        """
        C++: bool ReadDir(string TargetDir, frStringList& FileList, READ_TYPE Type)
        """
        if not os.path.isdir(target_dir):
            return False

        try:
            # os.listdir는 .과 ..을 포함하지 않음
            entries = os.listdir(target_dir)
            
            for entry in entries:
                full_path = os.path.join(target_dir, entry)
                
                if read_type == READ_TYPE.ALL_TYPE:
                    file_list.append(entry)
                
                elif read_type == READ_TYPE.DIR_TYPE:
                    if os.path.isdir(full_path):
                        file_list.append(entry)
                        
                elif read_type == READ_TYPE.FILE_TYPE:
                    if os.path.isfile(full_path):
                        file_list.append(entry)
            
            return True
            
        except OSError:
            return False

    # -------------------------------------------------------
    # Static Utility Methods
    # -------------------------------------------------------
    @staticmethod
    def is_exist_dir(dir_path):
        """
        C++: bool IsExistDir(string DirPath)
        """
        return os.path.isdir(dir_path)

    @staticmethod
    def is_access_file(file_name, mode):
        """
        C++: bool IsAccessFile(string FileName, int Mode)
        Mode: os.F_OK(존재), os.R_OK(읽기), os.W_OK(쓰기), os.X_OK(실행)
        """
        return os.access(file_name, mode)

    @staticmethod
    def file_create_and_only_read(file_name):
        """
        C++: int FileCreateAndOnlyRead(string FileName)
        파일 디스크립터(int)를 반환하는 로우 레벨 함수
        """
        try:
            # O_RDWR | O_CREAT | O_TRUNC, 0644 모드 대응
            fd = os.open(file_name, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
            return fd
        except OSError:
            return -1

    @staticmethod
    def file_create_and_write(file_name, data, data_size=0):
        """
        C++: bool FileCreateAndWrite(...)
        """
        try:
            # 텍스트/바이너리 처리를 위해 모드 결정 (여기서는 바이너리 wb 가정)
            with open(file_name, 'wb') as f:
                # data가 문자열이면 인코딩, bytes면 그대로 쓰기
                if isinstance(data, str):
                    f.write(data.encode('utf-8'))
                else:
                    f.write(data) # data_size는 Python에서 보통 불필요 (len(data) 사용)
            return True
        except IOError:
            return False

    @staticmethod
    def delete_dir(dir_path):
        """
        C++: bool DeleteDir(const char* DirPath)
        시스템 명령어로 rm -rf 실행
        """
        # 보안상 shutil.rmtree 사용을 권장하지만, 원본 로직(백그라운드 & 실행) 유지를 위해 os.system 사용
        # cmd = f"\\rm -rf {dir_path} &" 
        # Python에서 & (백그라운드) 실행은 os.system으로 가능은 하나 비권장.
        # 일반적인 삭제 로직으로 구현:
        cmd = f"rm -rf {dir_path}"
        ret = os.system(cmd)
        return ret == 0

    @staticmethod
    def get_file_size(path):
        """
        C++: int GetFileSize(char* Path)
        """
        try:
            return os.path.getsize(path)
        except OSError as e:
            print(f"[Error] Can't get the size of file[{path}][{str(e)}]")
            return -1

    @staticmethod
    def get_large_file_size(path):
        """
        C++: unsigned int GetLargeFileSize(char* Path)
        Python은 정수 크기 제한이 없으므로 get_file_size와 동일
        """
        return FrDirReader.get_file_size(path)

    @staticmethod
    def read_file_to_buf(file_name):
        """
        C++: bool ReadFileToBuf(char* FileName, char* Buf)
        Python 특성상 데이터를 직접 반환 (실패 시 None)
        """
        if not os.path.exists(file_name):
            print(f"[Error] File open fail at ReadFileToBuf: {file_name}")
            return None
            
        try:
            with open(file_name, 'rb') as f:
                return f.read() # 전체 읽기
        except IOError as e:
            print(f"[Error] File read error: {str(e)}")
            return None