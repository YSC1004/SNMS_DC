import time
from datetime import datetime, timedelta

# -------------------------------------------------------
# FrTime Class
# 날짜/시간 관리 및 연산 유틸리티
# -------------------------------------------------------
class FrTime:
    # GetTimeStringEach용 마스크 상수 (C++ 헤더 내용을 추정하여 정의)
    TIME_ELEMENT_YEAR_MASK   = 0x01
    TIME_ELEMENT_MONTH_MASK  = 0x02
    TIME_ELEMENT_DAY_MASK    = 0x04
    TIME_ELEMENT_HOUR_MASK   = 0x08
    TIME_ELEMENT_MINUTE_MASK = 0x10
    TIME_ELEMENT_SECOND_MASK = 0x20

    def __init__(self, source=None):
        """
        생성자 오버로딩 대응
        source: None(현재시간), int/float(timestamp), datetime, str, FrTime
        """
        self.m_dt = None # datetime 객체
        self.set(source)

    # -------------------------------------------------------
    # Setters
    # -------------------------------------------------------
    def set(self, source=None):
        if source is None:
            # void Set()
            self.m_dt = datetime.now()
        
        elif isinstance(source, (int, float)):
            # Set(time_t t)
            self.m_dt = datetime.fromtimestamp(source)
            
        elif isinstance(source, datetime):
            # Set(struct tm) 대응 -> Python은 datetime 사용
            self.m_dt = source
            
        elif isinstance(source, FrTime):
            # Copy Constructor 대응
            self.m_dt = source.m_dt
            
        elif isinstance(source, str):
            # Set(char* source)
            if not self._set_time_string(source):
                # 파싱 실패 시 Epoch 0 (1970-01-01)
                self.m_dt = datetime.fromtimestamp(0)
        else:
            # Fallback
            self.m_dt = datetime.now()

    def _set_time_string(self, source):
        """
        C++ _SetTimeString(char *source) 대응
        문자열 길이에 따라 포맷을 추정하여 파싱
        """
        if not source:
            return False

        s = source.strip()
        length = len(s)
        
        # 파싱 시도할 포맷 목록 (길이별)
        candidate_formats = []

        if length == 19:
            # YYYY-MM-DD HH:MI:SS 등
            candidate_formats = [
                "%Y/%m/%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y:%m:%d %H:%M:%S",
                "%y/%m/%d %H:%M:%S.%f" # .X (microseconds 일부)
            ]
        elif length == 17:
            # YY-MM-DD HH:MI:SS (YY가 앞에 옴 -> C++ 로직상 2000년 더함)
            # Python %y는 시스템 기준(보통 1969~2068) 따름
            candidate_formats = [
                "%y-%m-%d %H:%M:%S",
                "%d/%m/%y %H/%M/%S",
                "%y/%m/%d %H:%M:%S"
            ]
        elif length == 16:
            candidate_formats = [
                "%Y/%m/%d %H:%M",
                "%Y-%m-%d %H:%M",
                "%Y:%m:%d %H:%M",
                "%Y %m %d %H:%M"
            ]
        elif length == 15:
            # YYYYMMDD HHMMSS
            candidate_formats = ["%Y%m%d %H%M%S"]
        elif length == 14:
            # MM/DD/YY HH:MI 등
            candidate_formats = [
                "%m/%d/%y %H:%M",
                "%y-%m-%d %H:%M",
                "%Y%m%d%H%M%S",
                "%Y%m%d %H:%M"
            ]
        elif length == 13:
             candidate_formats = [
                "%Y-%m-%d %H",
                "%y-%m-%d %H%M",
                "%Y%m%d %H%M",
                "%y%m%d %H%M%S"
             ]
        elif length == 12:
             candidate_formats = [
                 "%y%m%d%H%M%S",
                 "%Y%m%d%H%M"
             ]
        elif length == 11:
             candidate_formats = [
                 "%y-%m-%d %H",
                 "%y%m%d %H%M",
                 "%Y%m%d %H"
             ]
        elif length == 10:
             candidate_formats = [
                 "%Y%m%d%H",
                 "%y%m%d%H%M"
             ]
        elif length == 23 or length == 24:
             # Milliseconds 포함
             candidate_formats = [
                 "%Y-%m-%d %H:%M:%S.%f",
                 "%Y/%m/%d %H:%M:%S.%f"
             ]
        
        # 1. 길이 기반 매칭 시도
        for fmt in candidate_formats:
            try:
                # C++ 로직 중 year += 2000 하는 부분은 
                # Python %y가 2000년대(00~68)를 자동 처리하므로 대체 가능하다고 판단
                self.m_dt = datetime.strptime(s, fmt)
                return True
            except ValueError:
                continue

        return False

    # -------------------------------------------------------
    # Getters
    # -------------------------------------------------------
    def get_time(self):
        """time_t GetTime() -> timestamp (float/int)"""
        return int(self.m_dt.timestamp())

    def get_time_string(self):
        """char* GetTimeString() -> Standard Format"""
        return self.m_dt.strftime("%Y/%m/%d %H:%M:%S")

    @staticmethod
    def get_current_time_string():
        """string GetCurrentTimeString() -> YYYYMMDDHHMISS.mmm"""
        now = datetime.now()
        return now.strftime("%Y%m%d%H%M%S.%f")[:-3] # microseconds -> milliseconds

    @staticmethod
    def get_current_mille_time_string():
        """string GetCurrentMilleTimeString() -> YYYY-MM-DD WDAY HH:MM:SS.mmm"""
        now = datetime.now()
        day_str = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        wday = day_str[now.weekday()]
        
        base_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S.%f")[:-3]
        
        return f"{base_str} {wday} {time_str}"

    def get_time_string_each(self, mask):
        """char* GetTimeStringEach(int TimeElementMask)"""
        res = ""
        
        if mask & self.TIME_ELEMENT_YEAR_MASK:
            res += f"{self.m_dt.year:04d}"
            
        if mask & self.TIME_ELEMENT_MONTH_MASK:
            if mask & self.TIME_ELEMENT_YEAR_MASK: res += "/"
            res += f"{self.m_dt.month:02d}"
            
        if mask & self.TIME_ELEMENT_DAY_MASK:
            if (mask & self.TIME_ELEMENT_MONTH_MASK) or (mask & self.TIME_ELEMENT_YEAR_MASK): res += "/"
            res += f"{self.m_dt.day:02d}"
            
        if mask & self.TIME_ELEMENT_HOUR_MASK:
            if (mask & self.TIME_ELEMENT_MONTH_MASK) or \
               (mask & self.TIME_ELEMENT_YEAR_MASK) or \
               (mask & self.TIME_ELEMENT_DAY_MASK): res += " "
            res += f"{self.m_dt.hour:02d}"
            
        if mask & self.TIME_ELEMENT_MINUTE_MASK:
            if mask & self.TIME_ELEMENT_HOUR_MASK: res += ":"
            res += f"{self.m_dt.minute:02d}"
            
        if mask & self.TIME_ELEMENT_SECOND_MASK:
            if (mask & self.TIME_ELEMENT_HOUR_MASK) or (mask & self.TIME_ELEMENT_MINUTE_MASK): res += ":"
            res += f"{self.m_dt.second:02d}"
            
        return res

    # -------------------------------------------------------
    # Unit Getters
    # -------------------------------------------------------
    def get_year(self): return self.m_dt.year
    def get_month(self): return self.m_dt.month
    def get_day(self): return self.m_dt.day
    def get_hour(self): return self.m_dt.hour
    def get_minute(self): return self.m_dt.minute
    def get_second(self): return self.m_dt.second
    def get_wday(self): return self.m_dt.weekday() # 0:Mon ~ 6:Sun (Python 기준)

    def get_remain_day_sec(self):
        """자정까지 남은 초"""
        return (24 * 3600) - (self.m_dt.hour * 3600 + self.m_dt.minute * 60 + self.m_dt.second)

    def get_remain_hour_sec(self):
        """다음 정각까지 남은 초"""
        return 3600 - (self.m_dt.minute * 60 + self.m_dt.second)

    # -------------------------------------------------------
    # Operators Overloading
    # -------------------------------------------------------
    def __sub__(self, other):
        """
        operator -
        Case 1: FrTime - FrTime -> int (seconds difference)
        Case 2: FrTime - int -> FrTime (new object)
        """
        if isinstance(other, FrTime):
            diff = self.m_dt - other.m_dt
            return int(diff.total_seconds())
        elif isinstance(other, int):
            new_dt = self.m_dt - timedelta(seconds=other)
            return FrTime(new_dt)
        return 0

    def __add__(self, other):
        """
        operator + (int seconds)
        """
        if isinstance(other, int):
            new_dt = self.m_dt + timedelta(seconds=other)
            return FrTime(new_dt)
        return self

    def __eq__(self, other):
        if isinstance(other, FrTime): return self.m_dt == other.m_dt
        return False

    def __lt__(self, other):
        if isinstance(other, FrTime): return self.m_dt < other.m_dt
        return False
        
    def __gt__(self, other):
        if isinstance(other, FrTime): return self.m_dt > other.m_dt
        return False
        
    def __le__(self, other):
        if isinstance(other, FrTime): return self.m_dt <= other.m_dt
        return False
        
    def __ge__(self, other):
        if isinstance(other, FrTime): return self.m_dt >= other.m_dt
        return False
    
    # Python str() 표현
    def __str__(self):
        return self.get_time_string()