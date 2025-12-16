import sys
import os

# 1. 라이브러리 경로 등록 (C++의 LD_LIBRARY_PATH와 유사)
# 프로젝트 루트 경로('/home/ncadmin/SNMS/SNMS_DC')를 시스템 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 2. 모듈 Import (C++의 #include "frMySQLSession.h" 와 유사)
# Class 폴더 안의 Sql 폴더 안의 FrMySQLSession 파일에서 FrMySQLSession 클래스를 가져옴
from Class.Sql.FrMySQLSession import FrMySQLSession, FrDbParam

def main():
    print(">> Starting Server Process...")

    # 3. 클래스 사용 (C++의 객체 생성 및 호출)
    db_session = FrMySQLSession()
    
    # 실제 DB 연결 정보 입력
    if db_session.connect("dcuser", "dcuser1234", "DCDB", "192.168.1.4", 3306):
        print(">> DB Connected Successfully")
        
        # 비즈니스 로직 수행
        param = FrDbParam("SELECT VERSION()")
        if db_session.execute(param):
            records = param.get_all_records()
            for rec in records:
                print("DB Version: " + rec.m_Values[0])
                
        db_session.disconnect()
    else:
        print(">> DB Connection Failed: " + db_session.m_Error)

if __name__ == "__main__":
    main()