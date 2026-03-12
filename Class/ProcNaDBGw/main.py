"""
ProcNaDBGw/main.py

C++ IMPL_PROC(DBGwWorld, "DBGw") 매크로 → Python main() 진입점 변환.

IMPL_PROC 매크로 원본 동작:
  1. 프로세스 이름("DBGw") 등록
  2. DBGwWorld 인스턴스 생성 (→ m_WorldPtr 설정)
  3. AsProcWorldBase::Run(argc, argv) 호출
       └─ 내부에서 AppStart(argc, argv) 호출
       └─ 이벤트 루프 진입 (signal 처리, 타이머 등)

실행 방법:
  python main.py -dbgwport 4100
  python main.py -alone -name DB_GW -sessionid <fd> -log off
"""

import sys
import logging

from ProcNaDBGw.DBGwWorld import DBGwWorld


def main() -> int:
    """
    procNaDBGw 프로세스 진입점.
    IMPL_PROC 매크로의 main() 자동 생성 동작을 수동으로 구현한다.
    """
    # 로깅 기본 설정 (레벨/포맷은 AsProcWorldBase.Run() 에서 재설정 가능)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y/%m/%d %H:%M:%S",
    )

    logger = logging.getLogger("procNaDBGw")
    logger.info("procNaDBGw starting ... (pid=%d)", __import__("os").getpid())

    # DBGwWorld 인스턴스 생성 → m_WorldPtr 자동 설정
    world = DBGwWorld()

    # AsProcWorldBase.Run() : AppStart() 호출 + 이벤트 루프
    ret = world.Run(len(sys.argv), sys.argv)

    if not ret:
        logger.error("procNaDBGw AppStart failed. exit.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())