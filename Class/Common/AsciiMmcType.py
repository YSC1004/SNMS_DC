import struct

# ==========================================================================
# [CONSTANTS] Defines
# ==========================================================================

MAX_PACKET      = 4096
MAX_MSG         = 4088
MAX_RESULT_MSG  = 4080

EQUIP_ID_LEN    = 40
MMC_CMD_LEN     = 128
MMC_CMD_LEN_EX  = 1000
MMC_CMD_LEN_EX2 = 500

MMC_VAL_LEN     = 128
USER_ID_LEN     = 16
PASSWORD_LEN    = 16
IP_ADDRESS_LEN  = 16
EVENT_ID_LEN    = 32

# Message IDs
AS_MMC_REQ          = 6
AS_MMC_REQ_ACK      = 2
AS_MMC_REQ_OLD      = 1
AS_MMC_RES          = 11
AS_MMC_RES_ACK      = 12
AS_MMC_IDENT_REQ    = 21
AS_MMC_IDENT_RES    = 22
AS_MMC_FLOW_CONTROL = 31
SESSION_TYPE_MMC    =   2

AS_ROUTER_INFO_REQ  = 101
AS_ROUTER_INFO_RES  = 102
AS_ROUTER_CONFIG    = 111

# ==========================================================================
# [ENUMS]
# ==========================================================================
# AS_MMC_TYPE
FULL_CMD = 0; CMD_ID = 1; CMD_SET_ID = 2; RE_ISSUE = 3

# AS_MMC_INTERFACE
ASCII = 0; Q3 = 1

# AS_MMC_RESPONSE_MODE
NO_RESPONSE = 0; RESPONSE = 1; SAVE_AND_RESPONSE = 2; ONLY_SAVE_RESPONSE = 3

# AS_MMC_PUBLISH_MODE
NO_IMMEDIATE = 0; IMMEDIATE = 1; NOT_PUBLISH = 2

# AS_MMC_COLLECT_MODE
NO_RECOLLECT = 0; RECOLLECT = 1

# AS_MMC_RESULT_MODE
R_ERROR = 0; R_CONTINUE = 1; R_COMPLETE = 2


# ==========================================================================
# [PACKET STRUCTURES]
# ==========================================================================

class BasePacket:
    """Helper class for pack/unpack"""
    @classmethod
    def _decode_str(cls, byte_data):
        return byte_data.decode('utf-8', errors='ignore').strip('\x00')

    @classmethod
    def _encode_str(cls, str_data, size):
        return str_data.encode('utf-8')[:size]

# -------------------------------------------------------
# 1. Basic Packet Header (Deprecated in Python, usually part of PacketT)
# -------------------------------------------------------
# typedef struct { int MsgId; int Length; char Msg[MAX_MSG]; } PACKET_T;
# -> CommType.py의 PacketT 사용 권장

# -------------------------------------------------------
# 2. MMC Related Structures
# -------------------------------------------------------

class AsMmcIdentReqT(BasePacket):
    # char name[80]
    FMT = "!80s"
    SIZE = struct.calcsize(FMT)
    
    def __init__(self, name=""):
        self.name = name
        
    def pack(self):
        return struct.pack(self.FMT, self._encode_str(self.name, 80))
        
    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        return cls(cls._decode_str(data[:cls.SIZE]))

class AsMmcIdentResT(BasePacket):
    # int resultMode; char result[256];
    FMT = "!I256s"
    SIZE = struct.calcsize(FMT)

    def __init__(self, result_mode=0, result=""):
        self.resultMode = result_mode
        self.result = result

    def pack(self):
        return struct.pack(self.FMT, self.resultMode, self._encode_str(self.result, 256))
        
    @classmethod
    def unpack(cls, data):
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        return cls(t[0], cls._decode_str(t[1]))

class AsMmcParameterT:
    # int sequence; char value[MMC_VAL_LEN];
    FMT = f"!I{MMC_VAL_LEN}s"
    SIZE = struct.calcsize(FMT)
    
    def __init__(self, seq=0, val=""):
        self.sequence = seq
        self.value = val
        
    def pack(self):
        return struct.pack(self.FMT, self.sequence, BasePacket._encode_str(self.value, MMC_VAL_LEN))
        
    @classmethod
    def unpack(cls, data):
        t = struct.unpack(cls.FMT, data)
        return cls(t[0], BasePacket._decode_str(t[1]))

class AsMmcRequestT(BasePacket):
    """
    AS_MMC_REQUEST_T
    """
    # Header fields (13 ints) + Strings + Parameters Array
    # int(id), char[40](ne), int(type), int(refId), int(if), int(resMode), int(pubMode), int(colMode)
    # char[1000](mmc), char[16](userid), char[16](display)
    # int(delay), int(retry), int(curRetry), int(paramNo), int(prio), int(logMode)
    # AS_MMC_PARAMETER_T parameters[20]
    # char[100](Reserved)
    
    def __init__(self):
        self.id = 0
        self.ne = ""
        self.type = 0
        self.referenceId = 0
        self.interfaces = 0
        self.responseMode = 0
        self.publishMode = 0
        self.collectMode = 0
        self.mmc = ""
        self.userid = ""
        self.display = ""
        self.cmdDelayTime = 0
        self.retryNo = 0
        self.curRetryNo = 0
        self.parameterNo = 0
        self.priority = 0
        self.logMode = 0
        self.parameters = [] # List of AsMmcParameterT
        self.Reserved = ""

    def pack(self):
        # 1. Header Packing
        # I(id) 40s(ne) I(type) I(ref) I(if) I(res) I(pub) I(col) 
        # 1000s(mmc) 16s(user) 16s(disp) 
        # I(delay) I(retry) I(cur) I(pNo) I(prio) I(log)
        fmt_base = f"!I{EQUIP_ID_LEN}sIIIIII{MMC_CMD_LEN_EX}s{USER_ID_LEN}s{IP_ADDRESS_LEN}sIIIIII"
        
        packed = struct.pack(fmt_base,
            self.id, self._encode_str(self.ne, EQUIP_ID_LEN),
            self.type, self.referenceId, self.interfaces, self.responseMode, self.publishMode, self.collectMode,
            self._encode_str(self.mmc, MMC_CMD_LEN_EX), self._encode_str(self.userid, USER_ID_LEN),
            self._encode_str(self.display, IP_ADDRESS_LEN),
            self.cmdDelayTime, self.retryNo, self.curRetryNo, self.parameterNo, self.priority, self.logMode
        )
        
        # 2. Parameters Array (20 items fixed size)
        for i in range(20):
            if i < len(self.parameters):
                packed += self.parameters[i].pack()
            else:
                # Empty parameter padding
                packed += struct.pack(AsMmcParameterT.FMT, 0, b'')
                
        # 3. Reserved
        packed += self._encode_str(self.Reserved, 100)
        return packed

    @classmethod
    def unpack(cls, data):
        obj = cls()
        fmt_base = f"!I{EQUIP_ID_LEN}sIIIIII{MMC_CMD_LEN_EX}s{USER_ID_LEN}s{IP_ADDRESS_LEN}sIIIIII"
        base_size = struct.calcsize(fmt_base)
        
        if len(data) < base_size: return None
        
        t = struct.unpack(fmt_base, data[:base_size])
        obj.id = t[0]
        obj.ne = cls._decode_str(t[1])
        obj.type, obj.referenceId, obj.interfaces = t[2], t[3], t[4]
        obj.responseMode, obj.publishMode, obj.collectMode = t[5], t[6], t[7]
        obj.mmc = cls._decode_str(t[8])
        obj.userid, obj.display = cls._decode_str(t[9]), cls._decode_str(t[10])
        obj.cmdDelayTime, obj.retryNo, obj.curRetryNo = t[11], t[12], t[13]
        obj.parameterNo, obj.priority, obj.logMode = t[14], t[15], t[16]
        
        # Parameters
        offset = base_size
        p_size = AsMmcParameterT.SIZE
        for _ in range(20):
            if offset + p_size > len(data): break
            p_data = data[offset : offset + p_size]
            obj.parameters.append(AsMmcParameterT.unpack(p_data))
            offset += p_size
            
        return obj

class AsMmcResultT(BasePacket):
    # int id; int resultMode; char result[MAX_RESULT_MSG];
    FMT = f"!II{MAX_RESULT_MSG}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self, id_val=0, mode=0, result=""):
        self.id = id_val
        self.resultMode = mode
        self.result = result

    def pack(self):
        return struct.pack(self.FMT, self.id, self.resultMode, self._encode_str(self.result, MAX_RESULT_MSG))

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        return cls(t[0], t[1], cls._decode_str(t[2]))

# -------------------------------------------------------
# 3. Router Info Structures
# -------------------------------------------------------
class AsRouterInfoReqT(BasePacket):
    # char userid[16], char password[16], int equipNo, char equipIds[50][40]
    BASE_FMT = f"!{USER_ID_LEN}s{PASSWORD_LEN}sI"
    BASE_SIZE = struct.calcsize(BASE_FMT)
    
    def __init__(self):
        self.userid = ""
        self.password = ""
        self.equipNo = 0
        self.equipIds = [] # List of strings

    def pack(self):
        packed = struct.pack(self.BASE_FMT, 
                             self._encode_str(self.userid, USER_ID_LEN),
                             self._encode_str(self.password, PASSWORD_LEN),
                             self.equipNo)
        # Equip IDs array (Fixed 50)
        for i in range(50):
            eid = self.equipIds[i] if i < len(self.equipIds) else ""
            packed += self._encode_str(eid, EQUIP_ID_LEN)
        return packed

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.BASE_SIZE: return None
        obj = cls()
        t = struct.unpack(cls.BASE_FMT, data[:cls.BASE_SIZE])
        obj.userid, obj.password = cls._decode_str(t[0]), cls._decode_str(t[1])
        obj.equipNo = t[2]
        
        offset = cls.BASE_SIZE
        for _ in range(50):
            if offset + EQUIP_ID_LEN > len(data): break
            eid_bytes = data[offset : offset + EQUIP_ID_LEN]
            obj.equipIds.append(cls._decode_str(eid_bytes))
            offset += EQUIP_ID_LEN
        return obj

class AsRouterInfoT(BasePacket):
    # int resultMode, char equipId[40], char ip[16], int port
    FMT = f"!I{EQUIP_ID_LEN}s{IP_ADDRESS_LEN}sI"
    SIZE = struct.calcsize(FMT)
    
    def __init__(self):
        self.resultMode = 0
        self.equipId = ""
        self.ipaddress = ""
        self.portNo = 0
        
    @classmethod
    def unpack(cls, data):
        t = struct.unpack(cls.FMT, data)
        obj = cls()
        obj.resultMode = t[0]
        obj.equipId = cls._decode_str(t[1])
        obj.ipaddress = cls._decode_str(t[2])
        obj.portNo = t[3]
        return obj
    
# -------------------------------------------------------
# AS_MMC_ACK_T Structure
# -------------------------------------------------------
class AsMmcAckT(BasePacket):
    """
    typedef struct {
        int id;
        int resultMode; // 1: Success, 0: Fail
    } AS_MMC_ACK_T;
    """
    FMT = "!II" # int(4) + int(4)
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.id = 0
        self.resultMode = 0

    def pack(self):
        return struct.pack(self.FMT, self.id, self.resultMode)

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.id = t[0]
        obj.resultMode = t[1]
        return obj