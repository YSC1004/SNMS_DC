"""
ProcNaDBGw 패키지
C++ DBGw 디렉토리 → Python ProcNaDBGw 패키지 변환

패키지 구성:
  DBGwMgr.py    : DBGwServerMgr 상속, fork/exec 기반 세션 생성
  DBGwWorld.py  : AsProcWorldBase 상속, 프로세스 진입 및 모드 분기
  main.py       : IMPL_PROC 매크로 대응 진입점

의존 라이브러리 매핑 (Makefile USER_LIBS):
  -lDBGwBase  → Class/libDBGw/libDBGwBase/
  -lDBGwSvr   → Class/libDBGw/libDBGwSvr/
  -lfrSql     → Class/Sql/
  -lfrSqlType → Class/SqlType/
  -lCommon    → Class/Common/
  -lfrEvent   → Class/Event/
  -lfrUtil    → Class/Util/
  -lProcMgr   → Class/Common/ (AsProcWorldBase)
  
# 일반 서버 모드
python -m ProcNaDBGw.main -dbgwport 4100

# Alone 모드 (DBGwMgr.AcceptSession이 fork 후 자동 호출)
python -m ProcNaDBGw.main -alone -name DBGW_CHILD_1234_5 -sessionid 5 -log off
  
"""

from ProcNaDBGw.DBGwMgr   import DBGwMgr
from ProcNaDBGw.DBGwWorld  import DBGwWorld, MAINPTR

__all__ = ["DBGwMgr", "DBGwWorld", "MAINPTR"]