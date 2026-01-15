import sys
import os
import argparse
import socket
import time

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import Dependencies
from Class.procNaDBGw.DBGwMgr import DBGwMgr
from Class.libDBGw.libDBGwSvr.DBGwServerSession import DBGwServerSession
from Class.Sql.FrDbBaseType import eDB_TYPE
from Class.Util.FrUtilMisc import FrUtilMisc

class DBGwWorld:
    """
    C++: DBGwWorld
    Application Entry Point & Manager.
    Handles process startup, argument parsing, and mode selection (Manager vs Session).
    """
    instance = None

    def __init__(self):
        DBGwWorld.instance = self
        self.log_dir = "./log" # Default log dir (Mocking BASE_MAINPTR->GetLogDir())

    def app_start(self):
        """
        C++: bool AppStart(int Argc, char** Argv)
        """
        # Argument Parsing
        parser = argparse.ArgumentParser(description="DBGw Process")
        parser.add_argument("-name", help="Process Name")
        parser.add_argument("-sessionid", type=int, help="Socket FD for Child Process")
        parser.add_argument("-dbgwport", type=int, help="Listen Port for Parent Process")
        parser.add_argument("-alone", action="store_true", help="Run in detached/child mode")
        parser.add_argument("-log", help="Logging option (off to disable)")

        # Parse known args to avoid erroring on unknown flags passed by framework
        args, unknown = parser.parse_known_args()

        # -------------------------------------------------------
        # Case 1: Child Process Mode (Session)
        # -------------------------------------------------------
        if args.sessionid:
            ppid = os.getppid()
            print(f"parentPID : {ppid}, sessionid : {args.sessionid}")

            # Create Session Instance
            # Using default credentials/DB type as per C++ (eDB_ORACLE_OCI2)
            session = DBGwServerSession(
                eDB_TYPE.eDB_ORACLE_OCI2.value, "scott", "tiger", "orcl"
            )

            session.m_IsAloneMode = True
            session.m_IsLoggingMode = True

            # Handle Log Option
            if args.log:
                if args.log.lower() == "off":
                    session.m_IsLoggingMode = False

            session.m_LogDir = self.log_dir

            # Reconstruct Socket from File Descriptor (FD)
            # This is critical for the child process to take over the connection
            try:
                # Assuming TCP Socket
                client_sock = socket.fromfd(args.sessionid, socket.AF_INET, socket.SOCK_STREAM)
                session.set_socket(client_sock, None) # Address not strictly needed here
                
                # session.Enable() equivalent
                print(f"[Child] Session Started on FD {args.sessionid}")
                
                # Start Session Loop
                # In C++, Enable() likely registers to a reactor. 
                # In Python, we run a loop to read/process packets.
                self.run_session_loop(session)
                
            except OSError as e:
                print(f"[Error] Invalid Session FD: {e}")
                return False

            return True

        # -------------------------------------------------------
        # Case 2: Parent Process Mode (Manager)
        # -------------------------------------------------------
        if args.dbgwport:
            db_gw_port = args.dbgwport
        else:
            print("\n")
            print(f"## [Usage] {sys.argv[0]} -dbgwport 410x")
            print("\n")
            return False

        # Create Manager
        gw = DBGwMgr(eDB_TYPE.eDB_ORACLE_OCI2.value, "scott", "tiger", "orcl")

        if gw.run(db_gw_port):
            gw.set_log_dir(self.log_dir)
            pid = FrUtilMisc.get_pid()
            print(f"DBGwMgr Run Success (pid:{pid})(port:{db_gw_port})")
            
            # Run Main Loop
            # This keeps the parent process alive to accept new connections
            self.run_manager_loop(gw)
            
        else:
            print(f"DBGwMgr Run Error(port:{db_gw_port})")
            return False

        return True

    def run_session_loop(self, session):
        """
        Simulates the event loop for a child session process.
        """
        try:
            while True:
                # Blocking read or use select/poll
                # For simplicity, we assume packet reading logic exists in session
                # In a real framework, this would be handled by AsSocket/Reactor
                data = session.client_socket.recv(4096)
                if not data:
                    break
                # Process raw data -> Packet -> receive_packet()
                # Here we just print mock info
                # session.receive_packet(...)
        except Exception as e:
            print(f"Session Loop Error: {e}")
        finally:
            session.close_socket(0)

    def run_manager_loop(self, gw):
        """
        Simulates the main loop for the parent process.
        """
        try:
            while True:
                gw.accept_socket()
                # Prevent CPU spin
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("Server Stopping...")

# -------------------------------------------------------
# Execution Entry Point (Equivalent to main.C usually linking this)
# -------------------------------------------------------
if __name__ == "__main__":
    world = DBGwWorld()
    world.app_start()