import os
import sys

# -------------------------------------------------------
# FrDirHandler Class
# 디렉토리 생성, 삭제, 확인 유틸리티
# -------------------------------------------------------
class FrDirHandler:
    
    @staticmethod
    def exist(name):
        """
        C++: bool Exist(string& pName)
        디렉토리 존재 여부 확인 (opendir 대응)
        """
        return os.path.isdir(name)

    @staticmethod
    def exist2(name):
        """
        C++: bool Exist2(string& pName)
        경로(파일 또는 디렉토리) 존재 여부 확인 (stat 대응)
        """
        return os.path.exists(name)

    @staticmethod
    def create(name):
        """
        C++: bool Create(string& pName)
        디렉토리 재귀 생성 (mkdir -p 와 유사)
        """
        # 1. 이미 존재하면 True 반환 (C++ 로직 동일)
        if os.path.exists(name):
            return True

        try:
            # 2. os.makedirs: 중간 경로가 없으면 자동으로 생성해줌
            # mode=0o755: rwx for owner, rx for group/others (C++의 S_IRUSR... 대응)
            # exist_ok=True: 생성 도중 다른 프로세스가 폴더를 만들어도 에러 안 냄
            os.makedirs(name, mode=0o755, exist_ok=True)
            return True
        except OSError as e:
            # 권한 문제 등으로 실패 시
            print(f"[Error] Failed to create directory '{name}': {e}")
            return False

    @staticmethod
    def create2(name):
        """
        C++: bool Create2(string& pName)
        C++ 코드상 Create와 로직이 완전히 동일함
        """
        return FrDirHandler.create(name)

    @staticmethod
    def remove(name):
        """
        C++: bool Remove(string& pName)
        빈 디렉토리 삭제
        """
        try:
            os.rmdir(name)
            return True
        except OSError:
            # 디렉토리가 비어있지 않거나, 존재하지 않을 때
            return False
