"""
frTime.h / frTime.C  →  fr_time.py

변환 매핑:
  frTime                        → FrTime
  time_t / struct tm            → float (timestamp) / datetime
  pthread_mutex_t m_TimeLock    → threading.Lock (클래스 변수)
  mktime / localtime            → datetime / calendar.timegm
  ftime / timeb (밀리초)        → time.time() / datetime.now()
  sscanf 다중 포맷 파싱         → _parse_string() : re + strptime 조합
  operator -/+/>/</==/>=/<= 등 → Python 매직 메서드 __sub__, __add__, __gt__ 등
  GetTimeStringEach(mask)       → get_time_string_each(mask)
  FORMAT_TYPE enum              → FrTime.FormatType (Enum)
  TIME_ELEMENT_*_MASK 상수      → FrTime.Mask (IntFlag)
"""

import re
import time
import threading
import calendar
from datetime import datetime, timezone
from enum import IntEnum, IntFlag
from typing import Optional, Union


# ── 포맷 상수 (C++ #define 대응) ────────────────────────────────────────────
ORACLE_DATE_FORMAT   = "YYYY/MM/DD HH24:MI:SS"
ORACLE_DATE_FORMAT_C = "%04d/%02d/%02d %02d:%02d:%02d"
UNIX_DATE_FORMAT     = "+%Y/%m/%d-%H:%M:%S"
UNIX_DATE_FORMAT_C   = "%04d/%02d/%02d-%02d:%02d:%02d"

DAY_STR = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]


class FrTime:
    """날짜/시간 처리 유틸리티 클래스 (frTime 대응)."""

    # ── 내부 enum / flag ─────────────────────────────────────────────────────

    class FormatType(IntEnum):
        ORACLE_DATE = 0
        MSSQL_DATE  = 1

    class Mask(IntFlag):
        """TIME_ELEMENT_*_MASK 상수 대응 (GetTimeStringEach 용)."""
        YEAR   = 0x01
        MONTH  = 0x02
        DAY    = 0x04
        HOUR   = 0x08
        MINUTE = 0x10
        SECOND = 0x20

    # ── 클래스 변수 (pthread_mutex_t 대응) ───────────────────────────────────
    _time_lock: threading.Lock = threading.Lock()

    # ── 생성자 ───────────────────────────────────────────────────────────────

    def __init__(
        self,
        source: Union[None, float, datetime, str] = None,
    ):
        """
        source 타입별 동작:
          None      → 현재 시각 (frTime())
          float     → Unix timestamp (frTime(time_t))
          datetime  → datetime 객체 (frTime(struct tm))
          str       → 문자열 파싱 (frTime(char*))
        """
        self._timestamp: float = 0.0   # time_t 대응
        self._dt: datetime     = datetime.now()  # struct tm 대응

        if source is None:
            self.set()
        elif isinstance(source, float) or isinstance(source, int):
            self.set_timestamp(float(source))
        elif isinstance(source, datetime):
            self.set_datetime(source)
        elif isinstance(source, str):
            self.set_string(source)

    def __copy__(self):
        return FrTime(self._timestamp)

    # ── set 계열 ─────────────────────────────────────────────────────────────

    def set(self) -> None:
        """현재 시각으로 설정."""
        self._timestamp = time.time()
        self._set_dt()

    def set_timestamp(self, t: float) -> None:
        """Unix timestamp 로 설정."""
        self._timestamp = t
        self._set_dt()

    def set_datetime(self, dt: datetime) -> None:
        """datetime 객체로 설정 (mktime 대응)."""
        self._timestamp = dt.timestamp()
        self._set_dt()

    def set_string(self, source: str) -> None:
        """문자열 파싱으로 설정. 실패 시 timestamp = 0."""
        ts = self._parse_string(source)
        if ts is None:
            self._timestamp = 0.0
        else:
            self._timestamp = ts
        self._set_dt()

    def add(self, sec: int) -> None:
        """초 단위로 시각을 더한다 (frTime::Add)."""
        self.set_timestamp(self._timestamp + sec)

    # ── get 계열 ─────────────────────────────────────────────────────────────

    def get_time(self) -> float:
        """Unix timestamp 반환 (GetTime)."""
        return self._timestamp

    def get_datetime(self) -> datetime:
        """datetime 반환 (GetTM → struct tm 대응)."""
        return self._dt

    def get_time_string(self) -> str:
        """
        'YYYY/MM/DD HH:MM:SS' 포맷 문자열 반환 (GetTimeString).
        C++ 원본의 ORACLE_DATE_FORMAT_C 포맷과 동일.
        """
        return self._dt.strftime("%Y/%m/%d %H:%M:%S")

    def get_time_string_each(self, mask: "FrTime.Mask") -> str:
        """
        TIME_ELEMENT_*_MASK 조합에 따라 날짜/시간 부분만 선택적으로 반환
        (GetTimeStringEach).

        예) mask = Mask.YEAR | Mask.MONTH | Mask.DAY → "2024/07/15"
        """
        M = FrTime.Mask
        parts = []

        date_parts = []
        if mask & M.YEAR:
            date_parts.append(f"{self.get_year():04d}")
        if mask & M.MONTH:
            date_parts.append(f"{self.get_month():02d}")
        if mask & M.DAY:
            date_parts.append(f"{self.get_day():02d}")
        if date_parts:
            parts.append("/".join(date_parts))

        time_parts = []
        if mask & M.HOUR:
            time_parts.append(f"{self.get_hour():02d}")
        if mask & M.MINUTE:
            time_parts.append(f"{self.get_minute():02d}")
        if mask & M.SECOND:
            time_parts.append(f"{self.get_second():02d}")
        if time_parts:
            parts.append(":".join(time_parts))

        return " ".join(parts)

    @staticmethod
    def get_current_time_string(
        fmt: "FrTime.FormatType" = None,
    ) -> str:
        """
        현재 시각을 'YYYYMMDDHHmmss.mmm' 포맷으로 반환 (GetCurrentTimeString).
        fmt 인자는 C++ 원본과 시그니처 호환을 위해 유지하나 동작은 동일.
        """
        now = datetime.now()
        return now.strftime("%Y%m%d%H%M%S") + f".{now.microsecond // 1000:03d}"

    @staticmethod
    def get_current_mille_time_string() -> str:
        """
        'YYYY-MM-DD DOW HH:MM:SS.mmm' 포맷으로 반환 (GetCurrentMilleTimeString).
        예) "2024-07-15 MON 09:05:03.127"
        """
        now = datetime.now()
        dow = DAY_STR[now.weekday() + 1 if now.weekday() < 6 else 0]
        # Python weekday(): 0=MON … 6=SUN  → C++ tm_wday: 0=SUN … 6=SAT
        wday = (now.weekday() + 1) % 7   # 0=SUN
        return (
            f"{now.year:04d}-{now.month:02d}-{now.day:02d} "
            f"{DAY_STR[wday]} "
            f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}."
            f"{now.microsecond // 1000:03d}"
        )

    @staticmethod
    def get_format() -> str:
        """ORACLE_DATE_FORMAT 상수 반환 (GetFormat)."""
        return ORACLE_DATE_FORMAT

    def get_year(self)   -> int: return self._dt.year
    def get_month(self)  -> int: return self._dt.month
    def get_day(self)    -> int: return self._dt.day
    def get_hour(self)   -> int: return self._dt.hour
    def get_minute(self) -> int: return self._dt.minute
    def get_second(self) -> int: return self._dt.second

    def get_wday(self) -> int:
        """요일 반환. 0=SUN … 6=SAT (C++ tm_wday 와 동일)."""
        return (self._dt.weekday() + 1) % 7

    def get_remain_day_sec(self) -> int:
        """자정까지 남은 초 (GetRemainDaySec)."""
        return (
            60 * 60 * 24
            - (self.get_hour() * 3600 + self.get_minute() * 60 + self.get_second())
        )

    def get_remain_hour_sec(self) -> int:
        """현재 시각 기준 다음 정시까지 남은 초 (GetRemainHourSec)."""
        return 3600 - (self.get_minute() * 60 + self.get_second())

    # ── 연산자 (매직 메서드) ──────────────────────────────────────────────────

    def __sub__(self, other: Union["FrTime", int, float]) -> float:
        if isinstance(other, FrTime):
            return self._timestamp - other._timestamp
        return self._timestamp - other

    def __add__(self, other: Union[int, float]) -> float:
        return self._timestamp + other

    def __eq__(self, other: "FrTime") -> bool:
        return self._timestamp == other._timestamp

    def __gt__(self, other: "FrTime") -> bool:
        return self._timestamp > other._timestamp

    def __ge__(self, other: "FrTime") -> bool:
        return self._timestamp >= other._timestamp

    def __lt__(self, other: "FrTime") -> bool:
        return self._timestamp < other._timestamp

    def __le__(self, other: "FrTime") -> bool:
        return self._timestamp <= other._timestamp

    def __repr__(self) -> str:
        return f"FrTime({self.get_time_string()})"

    # ── 내부 헬퍼 ────────────────────────────────────────────────────────────

    def _set_dt(self) -> None:
        """timestamp → datetime 변환 (localtime 대응). 스레드 안전."""
        with FrTime._time_lock:
            try:
                self._dt = datetime.fromtimestamp(self._timestamp)
            except (OSError, OverflowError, ValueError):
                self._dt = datetime.fromtimestamp(0)

    @staticmethod
    def _parse_string(src: str) -> Optional[float]:
        """
        C++ _SetTimeString() 의 switch(strlen) 다중 포맷 파싱을 Python 으로 재현.
        성공 시 Unix timestamp(float), 실패 시 None 반환.

        지원 포맷 (C++ 원본 주석 기준):
          길이 19 : YYYY/MM/DD HH:MI:SS  YYYY/MM/DD-HH:MI:SS  YYYY-MM-DD HH:MI:SS
                    YYYY:MM:DD HH:MI:SS  YY/MM/DD HH:MI:SS.X
          길이 17 : YY-MM-DD HH:MI:SS   DD/MM/YY HH/MI/SS   YY/MM/DD HH:MI:SS
          길이 16 : YYYY/MM/DD HH:MI    YYYY-MM-DD HH:MI     YYYY:MM:DD HH:MI
                    YYYY MM DD HH:MI
          길이 15 : YYYYMMDD HHMMSS
          길이 14 : MM/DD/YY HH:MI      YY-MM-DD HH:MI      YYYYMMDDHHMMSS
                    YYYYMMDD HH:MI
          길이 13 : YYYY-MM-DD HH       YY-MM-DD HHMI        YYYYMMDD HHMI
                    YYMMDD HHMISS
          길이 12 : YYYYMMDDHHMI        YYMMDDHHMISS
          길이 11 : YY-MM-DD HH         YYMMDD HHMM          YYYYMMDD HH
          길이 10 : YYYYMMDDHH          YYMMDDHHMM
          길이  9 : YYMMDD HH
          길이  8 : YYMMDDHH
          길이  5 : DD HH
          길이 20 : YYYY-MM-DD  HH:MI:SS  (공백 2개)
          길이 23 : YYYY-MM-DD HH:MI:SS:XXX  또는 .XXX
          길이 24 : YYYY-MM-DD  HH:MI:SS:XXX 또는 .XXX (공백 2개)
        """
        if not src:
            return None

        n  = len(src)
        y = mo = d = h = mi = s = 0

        def _make_ts(year, month, day, hour=0, minute=0, sec=0) -> Optional[float]:
            """struct tm → mktime 대응."""
            try:
                dt = datetime(year, month, day, hour, minute, sec)
                return dt.timestamp()
            except ValueError:
                return None

        def _c(i: int) -> str:
            """인덱스 i 의 문자 반환 (C++ *(source+i) 대응)."""
            return src[i] if i < n else ""

        try:
            if n == 19:
                if _c(4)=='/' and _c(7)=='/' and _c(10)==' ' and _c(13)==':' and _c(16)==':':
                    y,mo,d,h,mi,s = int(src[0:4]),int(src[5:7]),int(src[8:10]),int(src[11:13]),int(src[14:16]),int(src[17:19])
                elif _c(4)=='/' and _c(7)=='/' and _c(10)=='-' and _c(13)==':' and _c(16)==':':
                    y,mo,d,h,mi,s = int(src[0:4]),int(src[5:7]),int(src[8:10]),int(src[11:13]),int(src[14:16]),int(src[17:19])
                elif _c(4)=='-' and _c(7)=='-' and _c(10)==' ' and _c(13)==':' and _c(16)==':':
                    y,mo,d,h,mi,s = int(src[0:4]),int(src[5:7]),int(src[8:10]),int(src[11:13]),int(src[14:16]),int(src[17:19])
                elif _c(4)==':' and _c(7)==':' and _c(10)==' ' and _c(13)==':' and _c(16)==':':
                    y,mo,d,h,mi,s = int(src[0:4]),int(src[5:7]),int(src[8:10]),int(src[11:13]),int(src[14:16]),int(src[17:19])
                elif _c(2)=='/' and _c(5)=='/' and _c(8)==' ' and _c(11)==':' and _c(14)==':' and _c(17)=='.':
                    y,mo,d,h,mi,s = int(src[0:2])+2000,int(src[3:5]),int(src[6:8]),int(src[9:11]),int(src[12:14]),int(src[15:17])
                else:
                    return None

            elif n == 17:
                if _c(2)=='-' and _c(5)=='-' and _c(8)==' ' and _c(11)==':' and _c(14)==':':
                    y,mo,d,h,mi,s = int(src[0:2])+2000,int(src[3:5]),int(src[6:8]),int(src[9:11]),int(src[12:14]),int(src[15:17])
                elif _c(2)=='/' and _c(5)=='/' and _c(8)==' ' and _c(11)=='/' and _c(14)=='/':
                    d,mo,y,h,mi,s = int(src[0:2]),int(src[3:5]),int(src[6:8])+2000,int(src[9:11]),int(src[12:14]),int(src[15:17])
                elif _c(2)=='/' and _c(5)=='/' and _c(8)==' ' and _c(11)==':' and _c(14)==':':
                    y,mo,d,h,mi,s = int(src[0:2])+2000,int(src[3:5]),int(src[6:8]),int(src[9:11]),int(src[12:14]),int(src[15:17])
                else:
                    return None

            elif n == 16:
                if _c(4)=='/' and _c(7)=='/' and _c(10)==' ' and _c(13)==':':
                    y,mo,d,h,mi = int(src[0:4]),int(src[5:7]),int(src[8:10]),int(src[11:13]),int(src[14:16])
                elif _c(4)=='-' and _c(7)=='-' and _c(10)==' ' and _c(13)==':':
                    y,mo,d,h,mi = int(src[0:4]),int(src[5:7]),int(src[8:10]),int(src[11:13]),int(src[14:16])
                elif _c(4)==':' and _c(7)==':' and _c(10)==' ' and _c(13)==':':
                    y,mo,d,h,mi = int(src[0:4]),int(src[5:7]),int(src[8:10]),int(src[11:13]),int(src[14:16])
                elif _c(4)==' ' and _c(7)==' ' and _c(10)==' ' and _c(13)==':':
                    y,mo,d,h,mi = int(src[0:4]),int(src[5:7]),int(src[8:10]),int(src[11:13]),int(src[14:16])
                else:
                    return None

            elif n == 15:
                if _c(8)==' ' and _c(6)!=' ':
                    y,mo,d,h,mi,s = int(src[0:4]),int(src[4:6]),int(src[6:8]),int(src[9:11]),int(src[11:13]),int(src[13:15])
                else:
                    return None

            elif n == 14:
                if _c(2)=='/' and _c(5)=='/' and _c(8)==' ' and _c(11)==':':
                    mo,d,y,h,mi = int(src[0:2]),int(src[3:5]),int(src[6:8])+2000,int(src[9:11]),int(src[12:14])
                elif _c(2)=='-' and _c(5)=='-' and _c(8)==' ' and _c(11)==':':
                    y,mo,d,h,mi = int(src[0:2])+2000,int(src[3:5]),int(src[6:8]),int(src[9:11]),int(src[12:14])
                elif src[0]=='2' and _c(8)==' ' and _c(11)==':':
                    y,mo,d,h,mi = int(src[0:4]),int(src[4:6]),int(src[6:8]),int(src[9:11]),int(src[12:14])
                elif _c(4)!=' ' and _c(6)!=' ':
                    y,mo,d,h,mi,s = int(src[0:4]),int(src[4:6]),int(src[6:8]),int(src[8:10]),int(src[10:12]),int(src[12:14])
                else:
                    return None

            elif n == 13:
                if _c(4)=='-' and _c(7)=='-' and _c(10)==' ':
                    y,mo,d,h = int(src[0:4]),int(src[5:7]),int(src[8:10]),int(src[11:13])
                elif _c(2)=='-' and _c(5)=='-' and _c(8)==' ':
                    y,mo,d,h,mi = int(src[0:2])+2000,int(src[3:5]),int(src[6:8]),int(src[9:11]),int(src[11:13])
                elif src[0]=='2' and _c(8)==' ':
                    y,mo,d,h,mi = int(src[0:4]),int(src[4:6]),int(src[6:8]),int(src[9:11]),int(src[11:13])
                elif _c(6)==' ':
                    y,mo,d,h,mi,s = int(src[0:2])+2000,int(src[2:4]),int(src[4:6]),int(src[7:9]),int(src[9:11]),int(src[11:13])
                else:
                    return None

            elif n == 12:
                if src[0]=='2':
                    y,mo,d,h,mi = int(src[0:4]),int(src[4:6]),int(src[6:8]),int(src[8:10]),int(src[10:12])
                else:
                    y,mo,d,h,mi,s = int(src[0:2])+2000,int(src[2:4]),int(src[4:6]),int(src[6:8]),int(src[8:10]),int(src[10:12])

            elif n == 11:
                if _c(2)=='-' and _c(5)=='-' and _c(8)==' ':
                    y,mo,d,h = int(src[0:2])+2000,int(src[3:5]),int(src[6:8]),int(src[9:11])
                elif _c(6)==' ':
                    y,mo,d,h,mi = int(src[0:2])+2000,int(src[2:4]),int(src[4:6]),int(src[7:9]),int(src[9:11])
                elif src[0]=='2' and _c(8)==' ':
                    y,mo,d,h = int(src[0:4]),int(src[4:6]),int(src[6:8]),int(src[9:11])
                else:
                    return None

            elif n == 10:
                if src[0]=='2':
                    y,mo,d,h = int(src[0:4]),int(src[4:6]),int(src[6:8]),int(src[8:10])
                else:
                    y,mo,d,h,mi = int(src[0:2])+2000,int(src[2:4]),int(src[4:6]),int(src[6:8]),int(src[8:10])

            elif n == 9:
                y,mo,d,h = int(src[0:2])+2000,int(src[2:4]),int(src[4:6]),int(src[7:9])

            elif n == 8:
                y,mo,d,h = int(src[0:2])+2000,int(src[2:4]),int(src[4:6]),int(src[6:8])

            elif n == 5:
                if _c(2)==' ':
                    now = datetime.now()
                    y,mo,d,h = now.year,now.month,int(src[0:2]),int(src[3:5])
                else:
                    return None

            elif n == 20:
                if _c(4) in ('-','/') and _c(7) in ('-','/') and _c(10)==' ' and _c(11)==' ' and _c(14)==':' and _c(17)==':':
                    y,mo,d,h,mi,s = int(src[0:4]),int(src[5:7]),int(src[8:10]),int(src[12:14]),int(src[15:17]),int(src[18:20])
                else:
                    return None

            elif n in (23, 24):
                # 밀리초/마이크로초 부분은 무시하고 초까지만 파싱
                sep = src[4]
                if sep in ('-', '/') and src[7]==sep and src[10]==' ' and src[13]==':' and src[16]==':':
                    y,mo,d,h,mi,s = int(src[0:4]),int(src[5:7]),int(src[8:10]),int(src[11:13]),int(src[14:16]),int(src[17:19])
                elif sep in ('-', '/') and src[7]==sep and src[10]==' ' and src[11]==' ' and src[14]==':' and src[17]==':':
                    y,mo,d,h,mi,s = int(src[0:4]),int(src[5:7]),int(src[8:10]),int(src[12:14]),int(src[15:17]),int(src[18:20])
                else:
                    return None

            else:
                return None

        except (ValueError, IndexError):
            return None

        return _make_ts(y, mo, d, h, mi, s)