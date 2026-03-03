"""
frDirReader.h / frDirReader.C  →  fr_dir_reader.py

변환 매핑:
  frDirReader                → DirReader
  frStringList               → collections.deque (pop_front → popleft)
  READ_TYPE enum             → DirReader.ReadType (IntEnum)
  opendir/readdir/closedir   → os.scandir
  stat()                     → os.stat / Path.stat()
  open/read/write/close      → Python 내장 open()
  frUtilMisc::System(buf)    → subprocess.run()
  frCORE_ERROR / SetGErrMsg  → logging.error
"""

import os
import stat
import logging
import subprocess
from enum import IntEnum, auto
from collections import deque
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DirReader:
    """디렉토리 내 파일 목록을 읽고 순회하는 유틸리티 클래스."""

    class ReadType(IntEnum):
        FILE_TYPE = 0
        DIR_TYPE  = 1
        ALL_TYPE  = 2

    # ------------------------------------------------------------------ #
    # 생성자 / 소멸자
    # ------------------------------------------------------------------ #

    def __init__(self, target_dir: str = ""):
        self._target_dir: str         = ""
        self._file_list:  deque[str]  = deque()

        if target_dir:
            self.set(target_dir)

    # ------------------------------------------------------------------ #
    # 인스턴스 메서드
    # ------------------------------------------------------------------ #

    def set(self, target_dir: str) -> None:
        """대상 디렉토리를 설정하고 파일 목록을 갱신한다."""
        self._target_dir = target_dir
        self._file_list.clear()
        DirReader.read_dir(target_dir, self._file_list)

    def is_exist_file(self, file_name: str) -> bool:
        """목록에 file_name 이 존재하면 True."""
        return file_name in self._file_list

    def has_more_file(self) -> bool:
        """아직 순회할 파일이 남아 있으면 True."""
        return len(self._file_list) > 0

    def next(self) -> str:
        """목록의 맨 앞 파일명을 꺼내 반환한다. 없으면 빈 문자열."""
        if self._file_list:
            return self._file_list.popleft()
        return ""

    def get_file_list(self) -> deque[str]:
        """내부 파일 목록(deque)의 참조를 반환한다."""
        return self._file_list

    # ------------------------------------------------------------------ #
    # 정적(static) 메서드
    # ------------------------------------------------------------------ #

    @staticmethod
    def read_dir(
        target_dir: str,
        file_list:  deque[str],
        read_type:  "DirReader.ReadType" = None,
    ) -> bool:
        """
        target_dir 내 항목을 read_type 에 따라 file_list 에 추가한다.

        ReadType.FILE_TYPE : 일반 파일만
        ReadType.DIR_TYPE  : 디렉토리만
        ReadType.ALL_TYPE  : 모두
        기본값(None)        : FILE_TYPE 과 동일
        """
        if read_type is None:
            read_type = DirReader.ReadType.FILE_TYPE

        try:
            with os.scandir(target_dir) as it:
                for entry in it:
                    if entry.name in (".", ".."):
                        continue
                    if read_type == DirReader.ReadType.ALL_TYPE:
                        file_list.append(entry.name)
                    elif read_type == DirReader.ReadType.DIR_TYPE:
                        if entry.is_dir(follow_symlinks=False):
                            file_list.append(entry.name)
                    else:  # FILE_TYPE
                        if entry.is_file(follow_symlinks=False):
                            file_list.append(entry.name)
            return True
        except OSError as e:
            logger.error("read_dir failed [%s]: %s", target_dir, e)
            return False

    @staticmethod
    def is_exist_dir(dir_path: str) -> bool:
        """디렉토리가 존재하면 True."""
        return os.path.isdir(dir_path)

    @staticmethod
    def is_access_file(file_name: str, mode: int = os.R_OK | os.W_OK) -> bool:
        """
        file_name 에 mode 권한으로 접근 가능하면 True.
        mode : os.R_OK, os.W_OK, os.X_OK 조합 (기본 R_OK|W_OK)
        """
        return os.access(file_name, mode)

    @staticmethod
    def file_create_and_only_read(file_name: str) -> Optional[int]:
        """
        파일을 생성(또는 초기화)한 뒤 파일 디스크립터(int)를 반환한다.
        실패 시 None 반환.

        C++ 원본: open(O_RDWR|O_CREAT|O_TRUNC, 0644) → fd
        주의: 반환된 fd 는 사용 후 os.close(fd) 로 닫아야 한다.
        """
        try:
            fd = os.open(
                file_name,
                os.O_RDWR | os.O_CREAT | os.O_TRUNC,
                0o644,
            )
            return fd
        except OSError as e:
            logger.error("file_create_and_only_read failed [%s]: %s", file_name, e)
            return None

    @staticmethod
    def file_create_and_write(file_name: str, data: bytes) -> bool:
        """
        파일을 생성(또는 초기화)하고 data 를 기록한다.
        성공 시 True, 실패 시 False.
        """
        try:
            with open(file_name, "wb") as f:
                f.write(data)
            return True
        except OSError as e:
            logger.error("file_create_and_write failed [%s]: %s", file_name, e)
            return False

    @staticmethod
    def delete_dir(dir_path: str) -> bool:
        """
        디렉토리를 비동기(백그라운드)로 삭제한다.
        C++ 원본: system("\\rm -rf <path> &")
        """
        try:
            subprocess.Popen(
                ["rm", "-rf", dir_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except OSError as e:
            logger.error("delete_dir failed [%s]: %s", dir_path, e)
            return False

    @staticmethod
    def get_file_size(path: str) -> int:
        """
        파일 크기(bytes)를 반환한다.
        실패 시 -1 반환.
        """
        try:
            return os.stat(path).st_size
        except OSError as e:
            logger.error("get_file_size failed [%s]: %s", path, e)
            return -1

    def get_large_file_size(self, path: str) -> int:
        """
        대용량 파일 크기(bytes)를 반환한다.
        C++ 원본에서는 unsigned int 반환이었으나 Python int 는 크기 제한 없음.
        실패 시 -1 반환.
        """
        return DirReader.get_file_size(path)

    @staticmethod
    def read_file_to_buf(file_name: str) -> Optional[bytes]:
        """
        파일 전체를 읽어 bytes 로 반환한다.
        C++ 원본: char* Buf 를 직접 채웠으나, Python 에서는 bytes 반환.
        실패 시 None 반환.
        """
        try:
            with open(file_name, "rb") as f:
                return f.read()
        except OSError as e:
            logger.error("read_file_to_buf failed [%s]: %s", file_name, e)
            return None