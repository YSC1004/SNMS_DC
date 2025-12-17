import sys
import os
import threading
import time

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.ProcParser.LockMgrPipe import LockMgrPipe
from Class.Common.AsUtil import AsUtil

class LockManager:
    """
    Manages the locking process of DataSender threads.
    Runs in a separate thread to avoid blocking the main Event Loop.
    Uses a Pipe to signal completion back to the main thread.
    """
    def __init__(self):
        """
        C++: LockManager()
        """
        self.m_LockMgrPipe = None
        self.m_ThreadStatus = False
        self.m_Thread = None

    def __del__(self):
        """
        C++: ~LockManager()
        """
        if self.m_LockMgrPipe:
            # Clean up pipe resources
            self.m_LockMgrPipe.close()

    def lock_check(self):
        """
        C++: bool LockCheck()
        Starts the background thread process to perform locking.
        """
        # 1. Create Pipe
        self.m_LockMgrPipe = LockMgrPipe()
        # In Python AsPipe __init__ calls os.pipe().
        # We need to register this pipe to the World to receive events.
        
        from ParserWorld import ParserWorld
        world = ParserWorld.get_instance()
        if world:
            world.register_event_src(self.m_LockMgrPipe)

        # 2. Start Run Thread
        try:
            self.m_Thread = threading.Thread(target=self.run, args=())
            self.m_Thread.daemon = True # Detach behavior
            self.m_Thread.start()
        except RuntimeError as e:
            print(f"[LockManager] thread create error : {e}")
            self.m_LockMgrPipe = None
            return False
            
        return True

    def run(self):
        """
        C++: void* Run(void* Arg)
        The orchestration thread. Spawns Locker thread and waits for it.
        """
        # 1. Create Locker Thread
        locker_thread = threading.Thread(target=self.locker, args=())
        locker_thread.start()

        cnt = 0
        
        # Initial sleep (simulating C++ logic)
        time.sleep(3) 

        print("[LockManager] after LockManager::Locker")

        # Wait for Locker to signal it has started/reached check point
        while not self.m_ThreadStatus:
            print(f"[LockManager] Waiting starting thread(LockManager::Locker) : {cnt} sec")
            time.sleep(1)
            cnt += 1

        time.sleep(1)

        print("[LockManager] wait LockManager::Locker...")

        # Wait for Locker to finish (DataSenderLock is blocking)
        locker_thread.join()

        print("[LockManager] join success(LockManager::Locker)...")

        self.finish_lock()

    def locker(self):
        """
        C++: void* Locker(void* Arg)
        The thread that actually performs the blocking lock call.
        """
        print("[LockManager] Function LockManager::Locker")
        
        from ParserWorld import ParserWorld
        world = ParserWorld.get_instance()

        self.m_ThreadStatus = True
        
        print("[LockManager] Waiting release DataSenderLock")
        
        # Blocks until all DataSenders are locked
        if world:
            world.data_sender_lock()
            
        print("[LockManager] finish release DataSenderLock")

    def finish_lock(self):
        """
        C++: void FinishLock()
        Writes to pipe to notify Main Thread.
        """
        if self.m_LockMgrPipe:
            # Write dummy data to trigger pipe read event in Main Loop
            self.m_LockMgrPipe.write(b"gggg")