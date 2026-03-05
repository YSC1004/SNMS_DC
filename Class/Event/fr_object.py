"""
frObject.py
C++ frObject.h / frObject.C → Python 변환
"""

import threading
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from Event.fr_msg_sensor import FrMsgSensor
    from Event.fr_world import FrWorld

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 전역 에러 메시지 (C++ static char GlobalErrMsg[MAX_ERR_MSG_BUF] 대응)
# ---------------------------------------------------------------------------
_global_err_msg: str = ""


def set_g_err_msg(fmt: str, *args) -> None:
    """SetGErrMsg() 대응 — 전역 에러 메시지 설정."""
    global _global_err_msg
    try:
        _global_err_msg = fmt % args if args else fmt
    except Exception as e:
        _global_err_msg = fmt


def get_g_err_msg() -> str:
    """GetGErrMsg() 대응 — 전역 에러 메시지 반환."""
    return _global_err_msg


# ---------------------------------------------------------------------------
# FrObject
# ---------------------------------------------------------------------------
class FrObject:
    """
    C++ frObject 클래스 대응.

    역할
    ----
    - 객체 이름 / 타입 관리
    - 객체 단위 에러 메시지 관리
    - FrMsgSensor를 통한 스레드 간 메시지 송수신
    """

    def __init__(self, name: str = "") -> None:
        """
        frObject::frObject(string ObjectName) 대응.

        Parameters
        ----------
        name : str
            객체 이름 (기본값 "")
        """
        self._object_name: str = name
        self._err_msg: str = ""
        self._msg_sensor: Optional["FrMsgSensor"] = None

        # C++ int m_ObjectType = -1 / string m_ObjectTypeStr = ""
        self._object_type: int = -1
        self._object_type_str: str = ""

        # C++ m_TId = frThread::GetThreadSelfId()
        self._tid: int = threading.get_ident()

    def __del__(self) -> None:
        """frObject::~frObject() 대응 — MsgSensor 정리."""
        self._msg_sensor = None

    # ------------------------------------------------------------------
    # 객체 이름
    # ------------------------------------------------------------------
    def set_object_name(self, name: str) -> None:
        """SetObjectName() 대응."""
        self._object_name = name

    def get_object_name(self) -> str:
        """GetObjectName() 대응."""
        return self._object_name

    # ------------------------------------------------------------------
    # 객체 에러 메시지
    # ------------------------------------------------------------------
    def set_obj_err_msg(self, fmt: str, *args) -> None:
        """
        SetObjErrMsg() 대응.

        Parameters
        ----------
        fmt  : str   printf 스타일 포맷 문자열
        args : tuple 포맷 인자
        """
        try:
            self._err_msg = fmt % args if args else fmt
        except Exception:
            self._err_msg = fmt

    def get_obj_err_msg(self) -> str:
        """GetObjErrMsg() 대응."""
        return self._err_msg

    # ------------------------------------------------------------------
    # 객체 타입
    # ------------------------------------------------------------------
    def get_object_type(self) -> int:
        """GetObjectType() 대응."""
        return self._object_type

    def get_object_type_str(self) -> str:
        """GetObjectTypeStr() 대응."""
        return self._object_type_str

    # ------------------------------------------------------------------
    # MsgSensor 초기화
    # ------------------------------------------------------------------
    def init_msg_sensor(self, tid_or_world=None) -> bool:
        """
        InitMsgSensor() 대응 — 오버로드 2개를 하나로 통합.

        Parameters
        ----------
        tid_or_world : int | FrWorld | None
            - None 또는 0(int)  : 현재 객체의 _tid 로 FrWorld 검색
            - int (THREAD_ID)   : 지정 tid 로 FrWorld 검색
            - FrWorld 인스턴스  : 직접 전달 (두 번째 오버로드)

        Returns
        -------
        bool : 성공 여부
        """
        # 지연 임포트 — 순환 참조 방지
        from Event.fr_msg_sensor import FrMsgSensor
        from Event.fr_world import FrWorld

        # 기존 센서 해제
        self._msg_sensor = None

        # ── 오버로드 분기 ──────────────────────────────────────────────
        if isinstance(tid_or_world, FrWorld):
            # bool InitMsgSensor(frWorld* WorldPtr)
            world_ptr = tid_or_world
        else:
            # bool InitMsgSensor(THREAD_ID TId = 0)
            tid: int = tid_or_world if tid_or_world else 0
            effective_tid = self._tid if tid == 0 else tid

            world_ptr = FrWorld.find_world_info(effective_tid)
            if world_ptr is None:
                logger.error(
                    "FrObject.init_msg_sensor : can't find world (tid=%d)",
                    effective_tid,
                )
                return False

            self._tid = effective_tid

        self._msg_sensor = FrMsgSensor(self, world_ptr)
        return True

    # ------------------------------------------------------------------
    # 메시지 송수신
    # ------------------------------------------------------------------
    def send_message(self, message: int, addition_info=None) -> bool:
        """
        SendMessage() 대응.

        MsgSensor 가 없으면 init_msg_sensor() 를 자동 호출한 뒤 전송.

        Parameters
        ----------
        message       : int   메시지 코드
        addition_info : any   부가 데이터 (C++ void*)

        Returns
        -------
        bool : 전송 성공 여부
        """
        if self._msg_sensor:
            return self._msg_sensor.send_event(message, addition_info)

        # 자동 초기화 재시도
        if self.init_msg_sensor():
            return self._msg_sensor.send_event(message, addition_info)

        return False

    def recv_message(self, message: int, addition_info=None) -> None:
        """
        RecvMessage() 대응 — 서브클래스에서 반드시 오버라이드.

        C++ 원본은 virtual 함수이므로 Python 에서도 override 를 강제하기
        위해 호출 시 에러 로그를 남긴다.
        """
        logger.error(
            "FrObject.recv_message is only a virtual function — "
            "please override in subclass (object=%s)",
            self._object_name,
        )