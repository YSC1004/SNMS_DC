"""
frPing.py - C++ frPing 클래스를 Python 3.11로 변환
ICMP Ping 구현 (Raw Socket 사용)
"""

import socket
import struct
import select
import time
import os
from dataclasses import dataclass, field


# ──────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────
ICMP_ECHO      = 8
ICMP_ECHOREPLY = 0
ICMP_MINLEN    = 8


# ──────────────────────────────────────────────
# 결과 데이터 클래스
# ──────────────────────────────────────────────
@dataclass
class FrPingResult:
    result:     bool = False
    min_ms:     int  = -1   # ms
    max_ms:     int  = 0    # ms
    avg_ms:     int  = 0    # ms
    snd_cnt:    int  = 0
    rcv_cnt:    int  = 0
    loss:       int  = 100  # percent
    data_size:  int  = 32
    result_str: str  = ""


# ──────────────────────────────────────────────
# frPing 클래스
# ──────────────────────────────────────────────
class FrPing:
    """ICMP Raw Socket 기반 Ping 구현."""

    def __init__(self):
        self._ping_fd: socket.socket | None = None
        self._icmp_id:  int = 0
        self._icmp_seq: int = 0
        self._send_cnt: int = 0
        self._recv_cnt: int = 0

    def __del__(self):
        self._close()

    # ── public ────────────────────────────────

    def ping(
        self,
        dest_ip:   str,
        icmp_id:   int,
        count:     int = 3,
        timeout:   int = 200,   # ms
        data_size: int = 32,
    ) -> FrPingResult:
        """
        Ping 실행 후 FrPingResult 반환.

        Parameters
        ----------
        dest_ip   : 대상 IP 주소 (예: "8.8.8.8")
        icmp_id   : ICMP 식별자 (프로세스 ID 등 고유값 권장)
        count     : 전송 횟수 (기본 3)
        timeout   : 패킷당 타임아웃 ms (기본 200)
        data_size : ICMP 데이터 크기 바이트 (기본 32)
        """
        res = FrPingResult(snd_cnt=count, data_size=data_size)

        if not self._init():
            raise OSError("frPing 초기화 실패 - Raw Socket 생성 오류 (root 권한 필요)")

        self._icmp_id  = icmp_id & 0xFFFF
        self._icmp_seq = icmp_id & 0xFFFF

        total_time = 0

        for i in range(count):
            ok, elapsed = self._ping_once(dest_ip, timeout, data_size)
            if ok:
                res.rcv_cnt += 1
                res.result   = True

                if res.max_ms == 0:
                    res.max_ms = elapsed
                if res.min_ms == -1:
                    res.min_ms = elapsed

                res.max_ms = max(res.max_ms, elapsed)
                res.min_ms = min(res.min_ms, elapsed)
                total_time += elapsed

                res.result_str += f"       icmp_seq = {i}, time = {elapsed}\n"
            else:
                res.result_str += f"       icmp_seq = {i} :: PING FAIL !!!\n"

            self._icmp_seq = (self._icmp_seq + 1) & 0xFFFF

        if res.min_ms == -1:
            res.min_ms = 0

        res.avg_ms = total_time // count if total_time else 0

        if res.rcv_cnt:
            lost = res.snd_cnt - res.rcv_cnt
            res.loss = 0 if lost == 0 else (lost * 100) // res.snd_cnt
        else:
            res.loss = 100

        self._close()
        return res

    @staticmethod
    def get_res_string(res: FrPingResult) -> str:
        """결과 요약 문자열 반환."""
        if res.result:
            return (
                f"snd/rcv/loss = {res.snd_cnt}/{res.rcv_cnt}/{res.loss}, "
                f"min/max/avg = {res.min_ms}/{res.max_ms}/{res.avg_ms}"
            )
        return f"snd/rcv/loss = {res.snd_cnt}/{res.rcv_cnt}/{res.loss}"

    # ── protected / private ───────────────────

    def _init(self) -> bool:
        self._icmp_id  = 0
        self._icmp_seq = 15
        self._send_cnt = 0
        self._recv_cnt = 0
        self._close()
        return self._create_raw_sock()

    def _ping_once(self, dest_ip: str, timeout: int, data_size: int) -> tuple[bool, int]:
        """단일 ICMP Echo 전송 후 응답 대기. (성공여부, 경과시간ms) 반환."""
        if not self._send_icmp(dest_ip, data_size):
            return False, 0

        tot_timeout = timeout
        result      = False
        elapsed_ms  = 0

        while tot_timeout > 0:
            t_start = time.monotonic()
            ready   = self._select(tot_timeout)
            t_end   = time.monotonic()
            spent   = int((t_end - t_start) * 1000)

            if ready == 0:          # timeout
                tot_timeout -= spent
                continue
            if ready < 0:           # error
                break

            try:
                rcv_buf, addr = self._ping_fd.recvfrom(1024)
            except OSError:
                break

            t_end   = time.monotonic()
            spent   = int((t_end - t_start) * 1000)

            # IP 헤더 파싱 (첫 바이트로 헤더 길이 계산)
            if len(rcv_buf) < 1:
                tot_timeout -= spent
                continue

            ip_hl  = (rcv_buf[0] & 0x0F) * 4
            if len(rcv_buf) < ip_hl + ICMP_MINLEN:
                tot_timeout -= spent
                continue

            # ICMP 헤더 파싱: type(1) code(1) cksum(2) id(2) seq(2)
            icmp_data = rcv_buf[ip_hl:ip_hl + ICMP_MINLEN]
            icmp_type, icmp_code, _, icmp_id, icmp_seq = struct.unpack("!BBHHH", icmp_data)

            recv_ip = addr[0]

            if icmp_type != ICMP_ECHOREPLY:
                tot_timeout -= spent
                continue
            if icmp_id != self._icmp_id:
                tot_timeout -= spent
                continue
            if icmp_seq != self._icmp_seq:
                tot_timeout -= spent
                continue
            if recv_ip != dest_ip:
                tot_timeout -= spent
                continue

            elapsed_ms = max(spent, 1)
            result     = True
            break

        return result, elapsed_ms

    def _send_icmp(self, dest_ip: str, data_size: int) -> bool:
        """ICMP Echo Request 전송."""
        # type(1) code(1) cksum(2) id(2) seq(2) + data
        header = struct.pack("!BBHHH", ICMP_ECHO, 0, 0, self._icmp_id, self._icmp_seq)
        data   = b'\x00' * data_size
        packet = header + data

        cksum  = self._checksum(packet)
        packet = struct.pack("!BBHHH", ICMP_ECHO, 0, cksum, self._icmp_id, self._icmp_seq) + data

        try:
            self._ping_fd.sendto(packet, (dest_ip, 0))
            return True
        except OSError as e:
            print(f"[frPing] send icmp error : [{dest_ip}] {e}")
            return False

    def _close(self):
        if self._ping_fd:
            try:
                self._ping_fd.close()
            except OSError:
                pass
            self._ping_fd = None

    def _create_raw_sock(self) -> bool:
        self._close()
        try:
            self._ping_fd = socket.socket(
                socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP
            )
            self._ping_fd.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, 255)
            return True
        except OSError as e:
            print(f"[frPing] error to create raw socket : {e}")
            self._ping_fd = None
            return False

    def _checksum(self, data: bytes) -> int:
        """인터넷 체크섬 (RFC 1071)."""
        s = 0
        n = len(data)
        for i in range(0, n - 1, 2):
            s += (data[i] << 8) + data[i + 1]
        if n % 2:
            s += data[-1] << 8
        s  = (s >> 16) + (s & 0xFFFF)
        s += (s >> 16)
        return ~s & 0xFFFF

    def _select(self, timeout_ms: int) -> int:
        """소켓 읽기 준비 대기. 0=타임아웃, 1=준비, -1=오류."""
        try:
            r, _, _ = select.select([self._ping_fd], [], [], timeout_ms / 1000.0)
            return 1 if r else 0
        except OSError:
            return -1


# ──────────────────────────────────────────────
# 사용 예시
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import os, sys

    target = sys.argv[1] if len(sys.argv) > 1 else "8.8.8.8"
    icmp_id = os.getpid() & 0xFFFF

    pinger = FrPing()
    try:
        result = pinger.ping(
            dest_ip=target,
            icmp_id=icmp_id,
            count=4,
            timeout=1000,
            data_size=32,
        )
    except OSError as e:
        print(f"오류: {e}")
        sys.exit(1)

    print(f"\n--- {target} ping 결과 ---")
    print(result.result_str)
    print(FrPing.get_res_string(result))