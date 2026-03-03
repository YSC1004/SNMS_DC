"""
frDirHandler.h / frDirHandler.C  →  fr_dir_handler.py

변환 매핑:
  frDirHandler::Exist        → DirHandler.exist()
  frDirHandler::Exist2       → DirHandler.exist2()
  frDirHandler::Create       → DirHandler.create()
  frDirHandler::Create2      → DirHandler.create2()
  frDirHandler::Remove       → DirHandler.remove()

  opendir/readdir/closedir   → os.scandir / os.path.isdir
  stat()                     → os.stat / os.path.exists
  mkdir()                    → os.mkdir  (권한 0o755 = S_IRUSR|S_IWUSR|S_IXUSR|S_IRGRP|S_IXGRP|S_IROTH)
  rmdir()                    → os.rmdir
  frTokenizer (경로 분리)    → pathlib.PurePosixPath.parts

Windows(_WIN_MSC_) 분기:
  Python 에서는 os / pathlib 이 플랫폼을 자동으로 처리하므로
  별도 분기 없이 단일 코드로 통합.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# mkdir 권한 : S_IRUSR|S_IWUSR|S_IXUSR | S_IRGRP|S_IXGRP | S_IROTH
# = 0755 (8진수)
_DIR_MODE = 0o755


class DirHandler:
    """디렉토리 존재 확인 / 생성 / 삭제 유틸리티 (정적 메서드만 보유)."""

    # ------------------------------------------------------------------ #
    # exist  : opendir 방식 (디렉토리가 열리고 엔트리가 있어야 True)
    # ------------------------------------------------------------------ #
    @staticmethod
    def exist(name: str) -> bool:
        """
        opendir → readdir 방식으로 디렉토리 존재 여부를 확인한다.
        디렉토리가 존재하고 최소 1개의 엔트리(. 포함)가 있어야 True.

        C++ Exist() 와 동일한 동작:
          - opendir 실패 → False
          - readdir 결과 없음 → False
          - readdir 결과 있음 → True
        """
        try:
            with os.scandir(name) as it:
                # readdir 에서 첫 항목이 존재하면 True
                next(it)
                return True
        except StopIteration:
            # 디렉토리는 열렸지만 항목이 없음 (빈 디렉토리)
            return False
        except OSError:
            return False

    # ------------------------------------------------------------------ #
    # exist2 : stat 방식 (경로가 존재하기만 하면 True)
    # ------------------------------------------------------------------ #
    @staticmethod
    def exist2(name: str) -> bool:
        """
        stat() 방식으로 경로 존재 여부를 확인한다.
        파일/디렉토리/심볼릭링크 모두 True 반환.

        C++ Exist2() 와 동일한 동작.
        """
        return os.path.exists(name)

    # ------------------------------------------------------------------ #
    # create : exist 기반으로 중간 경로를 직접 생성
    # ------------------------------------------------------------------ #
    @staticmethod
    def create(name: str) -> bool:
        """
        exist() 기반으로 경로의 각 구성 요소를 순서대로 생성한다.
        이미 존재하면 True 즉시 반환.

        C++ Create() + frTokenizer("/") 조합과 동일한 동작.
        권한: 0o755 (S_IRUSR|S_IWUSR|S_IXUSR|S_IRGRP|S_IXGRP|S_IROTH)
        """
        if DirHandler.exist(name):
            return True
        return DirHandler._mkdir_recursive(name, use_exist2=False)

    # ------------------------------------------------------------------ #
    # create2 : exist2 기반으로 중간 경로를 직접 생성
    # ------------------------------------------------------------------ #
    @staticmethod
    def create2(name: str) -> bool:
        """
        exist2() 기반으로 경로의 각 구성 요소를 순서대로 생성한다.
        이미 존재하면 True 즉시 반환.

        C++ Create2() + frTokenizer("/") 조합과 동일한 동작.
        """
        if DirHandler.exist2(name):
            return True
        return DirHandler._mkdir_recursive(name, use_exist2=True)

    # ------------------------------------------------------------------ #
    # remove : rmdir (비어 있는 디렉토리만 삭제)
    # ------------------------------------------------------------------ #
    @staticmethod
    def remove(name: str) -> bool:
        """
        빈 디렉토리를 삭제한다.
        C++ Remove() / rmdir() 와 동일한 동작.
        비어 있지 않으면 False 반환.
        (재귀 삭제가 필요하면 DirReader.delete_dir() 을 사용할 것)
        """
        try:
            os.rmdir(name)
            return True
        except OSError as e:
            logger.error("remove failed [%s]: %s", name, e)
            return False

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #
    @staticmethod
    def _mkdir_recursive(name: str, use_exist2: bool) -> bool:
        """
        frTokenizer 로 '/' 구분자 분리 후 mkdir 를 반복하는
        C++ 로직을 그대로 재현한다.

        use_exist2=True  → exist2() (stat 방식) 로 존재 여부 확인
        use_exist2=False → exist()  (scandir 방식) 로 존재 여부 확인
        """
        exist_fn = DirHandler.exist2 if use_exist2 else DirHandler.exist

        # pathlib 으로 경로를 토큰으로 분리 (frTokenizer 역할)
        # Path("/a/b/c").parts → ('/', 'a', 'b', 'c')
        parts = Path(name).parts  # e.g. ('/', 'a', 'b', 'c') or ('a', 'b', 'c')

        current = ""
        for part in parts:
            if current == "":
                current = part          # 첫 토큰 (절대경로면 '/')
            else:
                current = os.path.join(current, part)

            if not exist_fn(current):
                try:
                    os.mkdir(current, _DIR_MODE)
                except OSError as e:
                    logger.error("_mkdir_recursive: mkdir failed [%s]: %s", current, e)
                    return False

        return True