import sys
import os
import time
import threading

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

class LogFileHandler:
    """
    Handles reading from a specific log file in a separate thread
    and sending the data to the LogGuiConnection.
    Simulates 'tail -f' behavior.
    """
    def __init__(self, conn):
        """
        C++: LogFileHandler(LogGuiConnection* Conn)
        """
        self.m_LogConn = conn
        self.m_File = None  # Replaces m_FileFd
        self.m_ThreadStatus = False
        self.m_Thread = None
        self.MAX_MSG = 8190

    def __del__(self):
        """
        C++: ~LogFileHandler()
        """
        self.close()

    def close(self):
        """
        Stops the thread and closes the file.
        """
        self.m_ThreadStatus = False
        if self.m_Thread and self.m_Thread.is_alive():
            self.m_Thread.join()
        
        if self.m_File:
            self.m_File.close()
            self.m_File = None

    def open_file(self, file_name):
        """
        C++: bool OpenFile(string FileName)
        Opens the file and seeks to the appropriate starting position (last 1000 bytes).
        """
        try:
            # Open in binary read/write (though we mostly read)
            # C++ used O_RDWR | O_CREAT
            if not os.path.exists(file_name):
                # Create if not exists to match O_CREAT
                open(file_name, 'a').close()

            self.m_File = open(file_name, 'rb')
            
            # Get File Size
            self.m_File.seek(0, 2) # Seek to End
            size = self.m_File.tell()

            # Seek Logic matching C++
            # If size > 1000, read last 1000 bytes. Else read from start.
            if size > 1000:
                self.m_File.seek(-1000, 2) # Relative to end
            else:
                self.m_File.seek(0, 0) # Start of file
            
            return True

        except Exception as e:
            print(f"[LogFileHandler] [CORE_ERROR] File({file_name}) Open Error : {e}")
            return False

    def run(self):
        """
        C++: void Run()
        Starts the file reading thread.
        """
        self.m_ThreadStatus = True
        self.m_Thread = threading.Thread(target=self.file_read, daemon=True)
        self.m_Thread.start()

    def file_read(self):
        """
        C++: void* FileRead(void* Arg)
        Reads new data from file and sends it via connection.
        """
        while self.m_ThreadStatus:
            if not self.m_File:
                time.sleep(1)
                continue

            try:
                # Read chunks
                # C++ loops `while((ret = read(...)) != 0)` inside the main loop
                # Python `read()` returns empty bytes b'' at EOF
                data = self.m_File.read(self.MAX_MSG)
                
                if data:
                    # Send data
                    # C++: fileHandler->m_LogConn->SendLogData(msgBuf);
                    # Assuming LogGuiConnection has send_log_data method
                    if self.m_LogConn:
                        self.m_LogConn.send_log_data(data)
                else:
                    # EOF reached, wait for new data (tail -f)
                    # C++: select with 70000 usec
                    time.sleep(0.07)

            except Exception as e:
                print(f"[LogFileHandler] Error reading file: {e}")
                time.sleep(1)