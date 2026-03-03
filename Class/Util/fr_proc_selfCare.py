"""
FrProcSelfCare : 프로세스 감시 및 자동 재시작(Watchdog) 관리자

C++ 원본 매핑:
  IsSelfCare(Argc, Argv)           → is_self_care(argv)
  Run(Argc, Argv)                  → run(argv)
  StartProc(Name, frStringVector*) → start_proc(name, args)

개선 사항:
  - 재시작 횟수 및 이력 기록
  - 최대 재시작 횟수 초과 시 중단 옵션
  - SIGTERM / SIGINT 시그널 처리 (graceful shutdown)
  - 자식 프로세스 종료 코드 로깅
  - logging 모듈로 통합 (print → logger)
"""

import os
import sys
import time
import signal
import logging
import subprocess
from datetime import datetime

# 프로젝트 경로 설정
current_dir  = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Util.fr_arg_parser import ArgParser

logger = logging.getLogger(__name__)


class FrProcSelfCare:
    """
    프로세스 감시 및 자동 재시작(Self-Care / Watchdog) 관리자.

    사용 예:
        sc = FrProcSelfCare()
        if sc.is_self_care(sys.argv):
            sc.run(sys.argv)          # Watchdog 모드
        else:
            main()                    # 실제 프로세스 모드
    """

    ARG_SELF_CARE   = "-selfcare"
    RESTART_DELAY   = 5      # 재시작 전 대기 초 (C++ 원본 없음, 추가)
    MAX_RESTART     = 0      # 최대 재시작 횟수 (0 = 무제한, C++ 원본 동일)

    def __init__(
        self,
        restart_delay: int = 5,
        max_restart:   int = 0,
    ):
        """
        restart_delay : 자식 프로세스 종료 후 재시작까지 대기 초
        max_restart   : 최대 재시작 횟수 (0 = 무제한)
        """
        self._child_proc:    subprocess.Popen | None = None
        self._restart_delay: int                     = restart_delay
        self._max_restart:   int                     = max_restart
        self._restart_cnt:   int                     = 0
        self._running:       bool                    = False

        # SIGTERM / SIGINT 핸들러 등록
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT,  self._signal_handler)

    # ------------------------------------------------------------------ #
    # 공개 인터페이스
    # ------------------------------------------------------------------ #

    def is_self_care(self, argv: list[str]) -> bool:
        """
        argv 에 '-selfcare' 옵션이 있으면 True (IsSelfCare).
        Watchdog 모드 여부를 판단.
        """
        parser = ArgParser(argv)
        return parser.does_it_exist(self.ARG_SELF_CARE)

    def run(self, argv: list[str]) -> None:
        """
        Watchdog 루프 실행 (Run).
        '-selfcare' 를 제거한 인자로 자식 프로세스를 실행하고,
        종료 시 자동으로 재시작한다.
        """
        child_args = self._build_child_args(argv)
        logger.info("[SelfCare] Watchdog started. Target: %s", child_args)

        self._running = True
        while self._running:
            self._child_proc = self.start_proc("SelfCare", child_args)

            if self._child_proc is None:
                logger.error("[SelfCare] Failed to start child process. Exiting.")
                break

            logger.info(
                "[SelfCare] Child started (PID=%d, restart#%d)",
                self._child_proc.pid, self._restart_cnt,
            )

            # 자식 종료 대기 (C++ wait(&status) 대응)
            exit_code = self._wait_child()

            if not self._running:
                # 시그널로 인한 정상 종료
                break

            logger.warning(
                "[SelfCare] Child exited (code=%s). Restart in %ds...",
                exit_code, self._restart_delay,
            )

            # 최대 재시작 횟수 체크
            self._restart_cnt += 1
            if self._max_restart > 0 and self._restart_cnt >= self._max_restart:
                logger.error(
                    "[SelfCare] Max restart count (%d) reached. Stopping.",
                    self._max_restart,
                )
                break

            time.sleep(self._restart_delay)

        logger.info("[SelfCare] Watchdog stopped.")

    def start_proc(self, name: str, args: list[str]) -> subprocess.Popen | None:
        """
        자식 프로세스 실행 (StartProc).
        성공 시 Popen 객체, 실패 시 None 반환.
        """
        try:
            proc = subprocess.Popen(args)
            return proc
        except OSError as e:
            logger.error("[SelfCare] Process start error (%s): %s", name, e)
            return None

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #

    def _build_child_args(self, argv: list[str]) -> list[str]:
        """
        argv 에서 '-selfcare' 옵션을 제거하고
        Python 인터프리터 경로를 앞에 붙인다.
        """
        args = [sys.executable]
        args += [a for a in argv if a != self.ARG_SELF_CARE]
        return args

    def _wait_child(self) -> int | None:
        """
        자식 프로세스가 종료될 때까지 대기.
        종료 코드를 반환한다.
        """
        try:
            self._child_proc.wait()
            return self._child_proc.returncode
        except ChildProcessError as e:
            logger.error("[SelfCare] wait() error: %s", e)
            return None

    def _signal_handler(self, signum, frame) -> None:
        """
        SIGTERM / SIGINT 수신 시 자식 프로세스를 종료하고
        Watchdog 루프를 중단한다.
        """
        sig_name = signal.Signals(signum).name
        logger.info("[SelfCare] Signal %s received. Shutting down...", sig_name)
        self._running = False
        if self._child_proc and self._child_proc.poll() is None:
            logger.info(
                "[SelfCare] Terminating child (PID=%d)...", self._child_proc.pid
            )
            self._child_proc.terminate()
            try:
                self._child_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("[SelfCare] Child did not exit. Killing...")
                self._child_proc.kill()