import sys
import os
import socket

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Assuming DBGwServer exists based on Makefile
# If not available, we can inherit from object or a base Socket class
try:
    from Class.libDBGw.libDBGwSvr.DBGwServer import DBGwServer
except ImportError:
    class DBGwServer:
        """Mock base class if DBGwServer is not yet defined"""
        def __init__(self):
            self.m_Socket = None
        def create(self, family):
            self.m_Socket = socket.socket(family, socket.SOCK_STREAM)
            self.m_Socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return True
        def listen(self, port, backlog):
            try:
                self.m_Socket.bind(('', port))
                self.m_Socket.listen(backlog)
                return True
            except Exception as e:
                print(f"[DBGwServer] Listen Error: {e}")
                return False
        def accept(self, session):
            """
            Simulates C++ Accept(AsSocket* pSocket).
            Accepts connection and assigns it to the session object.
            """
            try:
                client_sock, addr = self.m_Socket.accept()
                # Assuming session has a method to set the socket
                # In C++, AsSocket::Accept usually copies the handle.
                session.set_socket(client_sock, addr)
                return True
            except Exception as e:
                print(f"[DBGwServer] Accept Error: {e}")
                return False

from Class.libDBGw.libDBGwSvr.DBGwServerSession import DBGwServerSession

class DBGwServerMgr(DBGwServer):
    """
    C++: DBGwServerMgr
    Manages the Gateway Server: Listen port, accept connections, create sessions.
    """
    def __init__(self, db_kind, default_db_user, default_db_passwd, default_db_name):
        """
        C++: DBGwServerMgr(int DbKind, string DefaultDbUser, ...)
        """
        super().__init__()
        
        self.m_DbKind = db_kind
        self.m_DbUser = default_db_user
        self.m_DbPasswd = default_db_passwd
        self.m_DbName = default_db_name
        self.m_LogDir = "."

    def __del__(self):
        """
        C++: ~DBGwServerMgr()
        """
        pass

    def run(self, listen_port):
        """
        C++: bool Run(int ListenPort)
        Starts the server: Creates socket and listens.
        """
        if self.create(socket.AF_INET):
            return self.listen(listen_port, 100)
        else:
            return False

    def accept_socket(self):
        """
        C++: void AcceptSocket()
        Called (usually by a Reactor/Loop) when the listening socket is readable.
        Creates a new session and accepts the connection.
        """
        # Create a new session instance
        session = DBGwServerSession(self.m_DbKind, self.m_DbUser, self.m_DbPasswd, self.m_DbName)

        # Try to accept connection into the session
        if self.accept(session):
            # Hook for additional session acceptance logic
            ret = self.accept_session(session)
            
            if ret is True:
                # C++ logic: if(ret == true) { delete session; }
                # Usually implies session was rejected or handled immediately and should be cleaned up.
                session.close() 
                session = None
            else:
                # Session is accepted and kept alive.
                # In C++, the pointer is managed elsewhere (e.g. Reactor).
                # In Python, we might need to store it or start its loop.
                # For now, we assume the session manages its own lifecycle or is registered to a loop.
                pass
        else:
            # Accept failed
            session.close()
            session = None

    def accept_session(self, session):
        """
        C++: bool AcceptSession(DBGwServerSession* Session)
        Virtual method hook. Returns False by default.
        """
        return False

    def set_log_dir(self, log_dir):
        """
        C++: void SetLogDir(string LogDir)
        """
        self.m_LogDir = log_dir