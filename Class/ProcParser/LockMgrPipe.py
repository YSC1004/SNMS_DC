import sys
import os

# -------------------------------------------------------
# Project Path Setup
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Common.AsPipe import AsPipe
from Class.Event.FrLogger import FrLogger

class LockMgrPipe(AsPipe):
    """
    Pipe for receiving lock completion events.
    Triggers ParserWorld to finish data sender locking process.
    """
    def __init__(self):
        """
        C++: LockMgrPipe()
        """
        super().__init__()

    def __del__(self):
        """
        C++: ~LockMgrPipe()
        """
        super().__del__()

    def receive_message(self):
        """
        C++: int ReceiveMessage()
        Callback triggered when data is available on the pipe.
        """
        print("[LockMgrPipe] recv finish lock event")
        
        # Read from pipe (max 10 bytes as per C++ tmp[10])
        data = self.read(10)
        
        if data:
            # Lazy Import to avoid circular dependency
            from ParserWorld import ParserWorld
            world = ParserWorld.get_instance()
            
            if world:
                # C++: MAINPTR->DataSenderLockFinish2();
                world.data_sender_lock_finish2()
        else:
            print("[LockMgrPipe] [CORE_ERROR] LockMgrPipe read error")
            
        return 1