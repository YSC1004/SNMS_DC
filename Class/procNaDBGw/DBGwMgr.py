import sys
import os
import signal
import socket

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import ServerMgr
try:
    from Class.libDBGw.libDBGwSvr.DBGwServerMgr import DBGwServerMgr
except ImportError:
    # Fallback if dependencies are missing
    class DBGwServerMgr:
        def __init__(self, k, u, p, n): pass

class DBGwMgr(DBGwServerMgr):
    """
    C++: DBGwMgr
    Manages the Gateway Process.
    Uses Fork-Exec model to handle sessions in separate processes.
    """
    def __init__(self, db_kind, default_db_user, default_db_passwd, default_db_name):
        """
        C++: DBGwMgr(...) : DBGwServerMgr(...)
        """
        super().__init__(db_kind, default_db_user, default_db_passwd, default_db_name)
        
        # C++: signal(SIGCHLD, SIG_IGN);
        # Prevent Zombie processes by ignoring SIGCHLD
        if sys.platform != 'win32':
            signal.signal(signal.SIGCHLD, signal.SIG_IGN)

    def __del__(self):
        pass

    def accept_session(self, session):
        """
        C++: bool AcceptSession(DBGwServerSession* Session)
        Forks a new process to handle the session.
        The child process re-executes the script with '-alone' and '-sessionid' arguments.
        """
        # Windows does not support fork().
        if sys.platform == 'win32':
            print("Windows does not support fork(). Single process mode suggested.")
            return False

        # Get File Descriptor of the socket
        # Note: In C++, Session->SetCloseOnExec(false) is called.
        # In Python 3.4+, FDs are non-inheritable by default. We must allow inheritance.
        try:
            client_socket = session.client_socket
            fd = client_socket.fileno()
            os.set_inheritable(fd, True) 
        except Exception as e:
            print(f"[DBGwMgr] Failed to get socket FD: {e}")
            return False

        try:
            pid = os.fork()
        except OSError as e:
            print(f"FORK FAIL : {e}")
            return False

        if pid > 0:
            # ---------------------------------------------------
            # Parent Process
            # ---------------------------------------------------
            print("Create child success", flush=True)
            
            # C++ returns true, meaning the session object in Parent is no longer needed
            # (It will be deleted by the caller DBGwServerMgr::AcceptSocket)
            return True

        else:
            # ---------------------------------------------------
            # Child Process
            # ---------------------------------------------------
            # Prepare arguments for execv
            # We need to execute: python [script_name] -alone -name ...
            
            # 1. Base executable (python interpreter)
            python_exe = sys.executable
            
            # 2. Script path (argv[0])
            script_path = sys.argv[0]
            
            # 3. Construct Arguments
            # args.push_back("-alone");
            # args.push_back("-name"); ...
            new_args = [python_exe, script_path, "-alone"]
            
            new_args.append("-name")
            new_args.append(f"DBGW_CHILD_{os.getpid()}_{fd}")
            
            new_args.append("-sessionid")
            new_args.append(str(fd))

            # Parse "-log" from current process args (Mimicking frArgParser logic)
            if "-log" in sys.argv:
                try:
                    idx = sys.argv.index("-log")
                    if idx + 1 < len(sys.argv):
                        log_val = sys.argv[idx + 1]
                        new_args.append("-log")
                        new_args.append(log_val)
                except ValueError:
                    pass

            try:
                # C++: execv(args[0].c_str(), procArgs);
                # In Python, we re-execute the interpreter with the script
                os.execv(python_exe, new_args)
                
            except OSError as e:
                print(f"Execl fail({script_path}) : {e}", flush=True)
                sys.exit(0)
            
            # Should not reach here
            return True