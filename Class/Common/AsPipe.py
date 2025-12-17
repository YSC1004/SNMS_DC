import os
import sys
import errno

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Event.FrEventSrc import FrEventSrc

class AsPipe(FrEventSrc):
    """
    Wraps os.pipe() to provide inter-process/thread communication.
    Inherits from FrEventSrc to integrate with the Event Loop (select/poll).
    """
    def __init__(self):
        """
        C++: AsPipe()
        Creates a pipe and stores file descriptors.
        """
        super().__init__()
        try:
            # r_fd: Read end, w_fd: Write end
            self.m_ReadFd, self.m_WriteFd = os.pipe()
            
            # Set generic Fd for FrEventSrc (Listening on Read end)
            self.m_Fd = self.m_ReadFd
            
            # Non-blocking mode is often useful in event loops
            # os.set_blocking(self.m_ReadFd, False) # Python 3.5+
            
        except OSError as e:
            print(f"[AsPipe] Pipe Create Error: {e}")
            self.m_ReadFd = -1
            self.m_WriteFd = -1
            self.m_Fd = -1

    def __del__(self):
        """
        C++: ~AsPipe()
        """
        self.close()

    def close(self):
        """
        Closes both ends of the pipe.
        """
        if self.m_ReadFd != -1:
            try:
                os.close(self.m_ReadFd)
            except OSError: pass
            self.m_ReadFd = -1

        if self.m_WriteFd != -1:
            try:
                os.close(self.m_WriteFd)
            except OSError: pass
            self.m_WriteFd = -1
            
        self.m_Fd = -1

    def read(self, size):
        """
        Reads raw bytes from the pipe.
        """
        if self.m_ReadFd == -1:
            return b''
            
        try:
            return os.read(self.m_ReadFd, size)
        except OSError as e:
            if e.errno == errno.EAGAIN or e.errno == errno.EWOULDBLOCK:
                return b''
            print(f"[AsPipe] Read Error: {e}")
            return b''

    def write(self, data):
        """
        Writes raw bytes to the pipe.
        """
        if self.m_WriteFd == -1:
            return -1
            
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            return os.write(self.m_WriteFd, data)
        except OSError as e:
            print(f"[AsPipe] Write Error: {e}")
            return -1

    # -----------------------------------------------------------
    # FrEventSrc Overrides (For Event Loop Integration)
    # -----------------------------------------------------------
    def get_fd(self):
        return self.m_ReadFd

    def prepare_fd(self, rd_fds, wr_fds, ex_fds):
        """
        Registers the Read FD to the select list.
        """
        if self.m_ReadFd != -1:
            rd_fds.append(self.m_ReadFd)

    def dispatch_event(self, r_fds, w_fds, x_fds):
        """
        Checks if Read FD is triggered and calls callback.
        """
        if self.m_ReadFd != -1 and self.m_ReadFd in r_fds:
            self.receive_message()

    def receive_message(self):
        """
        C++: virtual int ReceiveMessage()
        To be overridden by child classes (e.g., LockMgrPipe).
        """
        print("[AsPipe] ReceiveMessage Base Function Called")
        # Default behavior: drain pipe to prevent busy loop
        self.read(1024)
        return 1