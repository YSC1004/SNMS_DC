import sys
import os
import time
import struct
import errno

# -------------------------------------------------------
# 1. 프로젝트 경로 설정
# -------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------
# 2. 모듈 Import
# -------------------------------------------------------
from Class.Event.FrSocket import FrSocket
from Class.Event.FrSockFdManager import SOCK_INFO_USE_TYPE

# CommType (패킷 구조체 및 상수 정의)
try:
    from Class.Common.CommType import (
        PacketT, AsSessionInfoT, AsAsciiAckT,
        SESSION_REPORTING, CMD_ALIVE_ACK, CMD_ALIVE_RECEIVE, CMD_ALIVE_SEND,
        CMD_LOG_STATUS_CHANGE
    )
except ImportError:
    # CommType이 없을 경우를 대비한 임시 상수 (실제 환경에서는 CommType.py 필수)
    print("[AsSocket] Warning: CommType not found. Using dummy constants.")
    SESSION_REPORTING = 1001
    CMD_ALIVE_ACK = 1002
    CMD_ALIVE_RECEIVE = 11
    CMD_ALIVE_SEND = 12
    CMD_LOG_STATUS_CHANGE = 9999
    PacketT = None
    AsSessionInfoT = None
    AsAsciiAckT = None

# AliveCheckTimer (순환 참조 방지를 위해 try-import)
try:
    from Class.Common.AliveCheckTimer import AliveCheckTimer
except ImportError:
    AliveCheckTimer = None

# -------------------------------------------------------
# AsSocket Class
# -------------------------------------------------------
class AsSocket(FrSocket):
    NOT_ASSIGN = -1

    def __init__(self):
        """
        C++: AsSocket()
        """
        super().__init__()
        
        self.m_SessionIdentify = self.NOT_ASSIGN
        self.m_AliveCheckTimer = None
        self.m_FailCount = 0
        self.m_FailCountMax = 0
        self.m_ReReadCheckFlag = False

    def __del__(self):
        """
        C++: ~AsSocket()
        """
        self.stop_alive_check()
        super().__del__()

    # ---------------------------------------------------
    # Packet Send / Recv Logic
    # ---------------------------------------------------
    def packet_send(self, packet_obj):
        """
        C++: bool PacketSend(PACKET_T* Packet)
        패킷 객체를 바이트로 직렬화하여 전송
        """
        if not packet_obj: return False

        try:
            # 직렬화 (Header + Body)
            # C++의 HtonPacket, HtonStruct 로직이 pack() 내부에 포함됨
            data = packet_obj.pack()
            total_len = len(data)
            
            # 전송 (FrSocket -> FrRdFdSensor.write -> os.write)
            sent_len = self.write(data)
            
            if sent_len < total_len:
                # Blocking 모드이거나 에러 발생 시
                if self.is_block_mode():
                    return False
                else:
                    # Non-blocking 모드에서 EAGAIN 등의 경우 (C++ 로직 참조)
                    # 실제로는 남은 데이터를 버퍼링해야 하지만 여기서는 False 리턴
                    return False
            return True
            
        except Exception as e:
            print(f"[AsSocket] Packet Send Error: {e}")
            return False

    def packet_recv(self):
        """
        C++: int PacketRecv(PACKET_T* Packet)
        헤더를 먼저 읽고, 길이를 파악한 뒤 바디를 읽음
        """
        if PacketT is None: return None

        # 1. 헤더 읽기 (8 Bytes: MsgId, Length)
        header_data = self._read_n_bytes(PacketT.HEADER_SIZE)
        if not header_data:
            return None

        # 2. 헤더 파싱 (Network Byte Order -> Host Byte Order)
        packet = PacketT.unpack_header(header_data)
        
        # 3. 바디 읽기
        if packet.length > 0:
            # C++ MAX_MSG 체크 로직
            if packet.length > PacketT.MAX_MSG_SIZE:
                print(f"[AsSocket] Error: Msg length({packet.length}) > MAX({PacketT.MAX_MSG_SIZE})")
                return None
            
            body_data = self._read_n_bytes(packet.length)
            if not body_data:
                return None
            
            packet.msg_body = body_data

        return packet

    def _read_n_bytes(self, n):
        """
        정해진 n바이트를 모두 읽을 때까지 반복 (TCP Fragmentation 처리)
        """
        data = b''
        retry_cnt = 0
        
        while len(data) < n:
            # 부족한 만큼 읽기 request
            chunk = self.read(n - len(data))
            
            if not chunk: # EOF or Error or Non-blocking empty
                # C++ ReReadCheckFlag 로직 일부 반영
                if self.m_ReReadCheckFlag and retry_cnt < 4:
                    time.sleep(0.07) # 70ms
                    retry_cnt += 1
                    continue
                return None
                
            data += chunk
            
        return data

    # ---------------------------------------------------
    # Event Handling (From FrSocketSensor)
    # ---------------------------------------------------
    def receive_message(self):
        """
        C++: void ReceiveMessage()
        소켓에 데이터가 도착했을 때 호출됨
        """
        # 패킷 수신
        packet = self.packet_recv()
        if not packet:
            # 패킷 읽기 실패는 연결 종료로 간주
            self.socket_broken(errno.ECONNRESET)
            return

        # 메시지 ID 분기 처리
        if packet.msg_id == SESSION_REPORTING:
            if self.m_SessionIdentify != self.NOT_ASSIGN:
                print(f"[AsSocket] Error: Already Session Identify ({self.get_session_name()})")
            else:
                self._handle_session_identify(packet)
                
        elif packet.msg_id == CMD_ALIVE_ACK:
            # 하트비트 응답 수신 -> 실패 카운트 초기화
            # print(f"[AsSocket] Alive Ack Receive : {self.get_session_name()}")
            self.m_FailCount = 0
            
        else:
            # 일반 패킷 -> 자식 클래스(Router, Agent 등)로 전달
            self.receive_packet(packet, self.m_SessionIdentify)

    # ---------------------------------------------------
    # Session Identify Logic
    # ---------------------------------------------------
    def _handle_session_identify(self, packet):
        """
        C++: void SessionIdentify(PACKET_T* Packet)
        """
        if AsSessionInfoT:
            try:
                info = AsSessionInfoT.unpack(packet.msg_body)
                self.m_SessionIdentify = info.session_type
                self.set_object_name(info.name)
                
                # 가상 함수 호출 (사용자 정의 로직)
                self.session_identify(self.m_SessionIdentify, info.name)
            except Exception as e:
                print(f"[AsSocket] Session Identify Parsing Error: {e}")

    def set_session_identify(self, session_type, name, interval=0, auto_ack_flag=False):
        """
        C++: void SetSessionIdentify(...)
        자신의 정보를 상대방에게 전송하고, 필요 시 AliveCheck 시작
        """
        self.m_SessionIdentify = session_type
        self.set_object_name(name)

        if AsSessionInfoT and PacketT:
            info = AsSessionInfoT(session_type, name)
            # struct.pack 결과물
            body = info.pack()
            packet = PacketT(SESSION_REPORTING, len(body), body)
            self.packet_send(packet)

        if auto_ack_flag:
            # SEND 모드로 AliveCheck 시작 (내가 주기적으로 보냄)
            self.start_alive_check(interval, 3, CMD_ALIVE_SEND)

    # ---------------------------------------------------
    # Alive Check Logic
    # ---------------------------------------------------
    def start_alive_check(self, interval, max_fail_count, mode=CMD_ALIVE_RECEIVE):
        """
        C++: bool StartAliveCheck(...)
        """
        if self.m_SessionIdentify == self.NOT_ASSIGN:
            print("[AsSocket] Not yet Session Identify")
            return False

        self.m_FailCountMax = max_fail_count
        self.stop_alive_check()

        if AliveCheckTimer:
            # AliveCheckTimer(interval, mode, socket_obj)
            self.m_AliveCheckTimer = AliveCheckTimer(interval, mode, self)
            return True
        return False

    def stop_alive_check(self):
        """
        C++: void StopAliveCheck()
        """
        if self.m_AliveCheckTimer:
            self.m_AliveCheckTimer.kill_timer() # or unregister
            self.m_AliveCheckTimer = None

    def alive_check_time(self):
        """
        C++: void AliveCheckTime()
        RECEIVE 모드일 때 타이머에 의해 주기적으로 호출됨.
        패킷을 못 받은 횟수를 체크.
        """
        self.m_FailCount += 1
        if self.m_FailCount > self.m_FailCountMax:
            print(f"[AsSocket] AliveCheckTimeOut : {self.get_session_name()} ({self.m_FailCount})")
            self.alive_check_fail(self.m_FailCount)

    def alive_check_send_time(self):
        """
        C++: void AliveCheckSendTime()
        SEND 모드일 때 타이머에 의해 주기적으로 호출됨.
        CMD_ALIVE_ACK 패킷 전송.
        """
        if PacketT:
            packet = PacketT(CMD_ALIVE_ACK, 0, b'')
            if not self.packet_send(packet):
                self.socket_broken(errno.EPIPE)
            # print(f"[AsSocket] AliveCheckPacketSend({self.get_session_name()})")

    # ---------------------------------------------------
    # Utils (Ack, Broken, Virtuals)
    # ---------------------------------------------------
    def send_ack(self, msg_id, id_val, result_mode, result_msg=""):
        """
        C++: bool SendAck(...)
        """
        if AsAsciiAckT and PacketT:
            ack = AsAsciiAckT(id_val, result_mode, result_msg)
            body = ack.pack()
            packet = PacketT(msg_id, len(body), body)
            return self.packet_send(packet)
        return False

    def socket_broken(self, err):
        """
        C++: void SocketBroken(int Errno)
        """
        self.close()
        self.close_socket(err)

    def set_re_read_check(self, flag):
        self.m_ReReadCheckFlag = flag