import sys
import os
import time
from datetime import datetime

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

class TimeMaker:
    """
    Utility class to parse various date/time string formats into Unix Timestamp.
    Supports adding/subtracting time intervals.
    """
    def __init__(self):
        """
        C++: TimeMaker()
        """
        self.clear()

    def clear(self):
        """
        C++: void Clear()
        """
        self.m_DateStr = ""
        self.m_TimeStr = ""
        self.m_DateTimeStr = ""
        self.m_Time = 0 # Unix Timestamp (int/float)
        self.m_IsAnySet = False
        self.m_TM = None # time.struct_time

    def set_date(self, date_str):
        """
        C++: void SetDate(const char* DateStr)
        """
        if not self.m_DateStr and date_str:
            self.m_DateStr = date_str
            self.m_IsAnySet = True

    def set_time(self, time_str):
        """
        C++: void SetTime(const char* TimeStr)
        """
        if not self.m_TimeStr and time_str:
            self.m_TimeStr = time_str
            self.m_IsAnySet = True

    def set_date_time(self, date_time_str):
        """
        C++: void SetDateTime(const char* DateTimeStr)
        """
        if not self.m_DateTimeStr and date_time_str:
            self.m_DateTimeStr = date_time_str
            self.m_IsAnySet = True

    def get_time(self):
        """
        C++: time_t GetTime()
        Parses the stored strings and returns Unix Timestamp.
        """
        if not self.m_IsAnySet:
            return -1

        if self.m_Time > 0:
            return self.m_Time

        source = ""
        if self.m_DateTimeStr:
            source = self.m_DateTimeStr
        elif self.m_DateStr and self.m_TimeStr:
            source = f"{self.m_DateStr} {self.m_TimeStr}"
            self.m_DateTimeStr = source
        else:
            return 0

        # Parse the string
        if self._set_time_string(source) == 1:
            return self.m_Time
        
        return 0

    def _set_tm(self):
        """
        C++: void _SetTM()
        Updates internal struct_time from timestamp.
        """
        if self.m_Time > 0:
            self.m_TM = time.localtime(self.m_Time)

    def _set_time_string(self, source):
        """
        C++: int _SetTimeString(char *source)
        Core parsing logic using string length and delimiters.
        """
        if not source: return 0
        
        slen = len(source)
        dt_obj = None

        try:
            # Logic mapped from C++ switch case
            if slen == 19:
                # - YYYY/MM/DD HH:MI:SS
                if source[4] == '/' and source[7] == '/' and source[10] == ' ':
                    dt_obj = datetime.strptime(source, "%Y/%m/%d %H:%M:%S")
                # - YYYY/MM/DD-HH:MI:SS
                elif source[4] == '/' and source[7] == '/' and source[10] == '-':
                    dt_obj = datetime.strptime(source, "%Y/%m/%d-%H:%M:%S")
                # - YYYY-MM-DD HH:MI:SS
                elif source[4] == '-' and source[7] == '-' and source[10] == ' ':
                    dt_obj = datetime.strptime(source, "%Y-%m-%d %H:%M:%S")
                # - YYYY:MM:DD HH:MI:SS
                elif source[4] == ':' and source[7] == ':':
                    dt_obj = datetime.strptime(source, "%Y:%m:%d %H:%M:%S")

            elif slen == 16:
                # - YYYY/MM/DD HH:MI
                if source[4] == '/' and source[7] == '/':
                    dt_obj = datetime.strptime(source, "%Y/%m/%d %H:%M")
                # - YYYY-MM-DD HH:MI
                elif source[4] == '-':
                    dt_obj = datetime.strptime(source, "%Y-%m-%d %H:%M")
                # - YYYY:MM:DD HH:MI
                elif source[4] == ':':
                    dt_obj = datetime.strptime(source, "%Y:%m:%d %H:%M")

            elif slen == 17:
                # - YY-MM-DD HH:MI:SS
                if source[2] == '-' and source[5] == '-':
                    dt_obj = datetime.strptime(source, "%y-%m-%d %H:%M:%S")
                # - DD/MM/YY HH/MI/SS (Caution: C++ logic swaps Day/Month position in sscanf?)
                # C++: sscanf(source, "%02d/%02d/%02d %02d/%02d/%02d", &mday, &mon, &year...)
                elif source[2] == '/' and source[5] == '/':
                    # Python %d/%m/%y matches DD/MM/YY
                    dt_obj = datetime.strptime(source, "%d/%m/%y %H/%M/%S")

            elif slen == 14:
                # - MM/DD/YY HH:MI
                if source[2] == '/' and source[5] == '/':
                    dt_obj = datetime.strptime(source, "%m/%d/%y %H:%M")
                # - YY-MM-DD HH:MI
                elif source[2] == '-' and source[5] == '-':
                    dt_obj = datetime.strptime(source, "%y-%m-%d %H:%M")
                # - YYYYMMDD HH:MI
                elif source[8] == ' ':
                    dt_obj = datetime.strptime(source, "%Y%m%d %H:%M")
                # - YYYYMMDDHHMMSS
                else:
                    dt_obj = datetime.strptime(source, "%Y%m%d%H%M%S")

            elif slen == 13:
                # - YYYY-MM-DD HH
                if source[4] == '-':
                    dt_obj = datetime.strptime(source, "%Y-%m-%d %H")
                # - YY-MM-DD HHMI
                elif source[2] == '-':
                    dt_obj = datetime.strptime(source, "%y-%m-%d %H%M")

            elif slen == 11:
                # - YY-MM-DD HH
                if source[2] == '-':
                    dt_obj = datetime.strptime(source, "%y-%m-%d %H")
                # - YYMMDD HHMM
                elif source[6] == ' ':
                    dt_obj = datetime.strptime(source, "%y%m%d %H%M")
                else:
                    # C++: %04d%02d%02d %02d (YYYYMMDD HH)
                    dt_obj = datetime.strptime(source, "%Y%m%d %H")

            elif slen == 10:
                # - YYYYMMDDHH
                if source[0] == '2' or source[0] == '1': # Starts with century
                    dt_obj = datetime.strptime(source, "%Y%m%d%H")
                # - YYMMDDHHMM
                else:
                    dt_obj = datetime.strptime(source, "%y%m%d%H%M")

            elif slen == 8:
                # - YYMMDDHH
                dt_obj = datetime.strptime(source, "%y%m%d%H")

            elif slen == 9:
                # - YYMMDD HH
                if source[6] == ' ':
                    dt_obj = datetime.strptime(source, "%y%m%d %H")

            elif slen == 5:
                # - DD HH (Current Year/Month)
                if source[2] == ' ':
                    now = datetime.now()
                    day = int(source[:2])
                    hour = int(source[3:])
                    dt_obj = datetime(now.year, now.month, day, hour, 0, 0)

        except ValueError:
            return 0

        if dt_obj:
            # Convert to Unix Timestamp
            self.m_Time = int(time.mktime(dt_obj.timetuple()))
            self._set_tm()
            return 1
        
        return 0

    def setting_time(self, time_val_str):
        """
        C++: time_t SettingTime(const char* Time)
        Format: (+/-)YYYYMMDDHHMISS (15 chars)
        1: +, 2: -
        """
        if not self.m_IsAnySet or self.m_Time <= 0:
            return -1

        if len(time_val_str) != 15:
            return -1

        try:
            flag = time_val_str[0]
            year = int(time_val_str[1:5])
            mon  = int(time_val_str[5:7])
            day  = int(time_val_str[7:9])
            hour = int(time_val_str[9:11])
            min_ = int(time_val_str[11:13])
            sec  = int(time_val_str[13:15])
        except ValueError:
            return -1

        # Use struct_time tuple manipulation to handle overflow/underflow (e.g. month > 12)
        # Python's mktime automatically normalizes out-of-range values
        
        # Current TM
        tm = self.m_TM
        
        curr_year = tm.tm_year
        curr_mon  = tm.tm_mon
        curr_day  = tm.tm_mday
        curr_hour = tm.tm_hour
        curr_min  = tm.tm_min
        curr_sec  = tm.tm_sec

        if flag == '1': # Add
            new_tm = (
                curr_year + year,
                curr_mon + mon,
                curr_day + day,
                curr_hour + hour,
                curr_min + min_,
                curr_sec + sec,
                0, 0, -1 # wday, yday, isdst
            )
        elif flag == '2': # Subtract
            new_tm = (
                curr_year - year,
                curr_mon - mon,
                curr_day - day,
                curr_hour - hour,
                curr_min - min_,
                curr_sec - sec,
                0, 0, -1
            )
        else:
            return -1

        # time.mktime normalizes the tuple (e.g. month 13 becomes next year month 1)
        try:
            self.m_Time = int(time.mktime(new_tm))
            self._set_tm()
            return self.m_Time
        except OverflowError:
            return -1