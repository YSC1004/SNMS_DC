import sys
import os
import socket
import time

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
from Class.Util.FrUtilMisc import FrUtilMisc

# CommType의 모든 상수와 구조체를 가져옴
try:
    from Class.Common.CommType import *
except ImportError:
    print("[AsUtil] Warning: CommType module not found.")

# -------------------------------------------------------
# AsUtil Class
# 애플리케이션 전용 유틸리티 (Enum 변환, 시스템 정보 등)
# -------------------------------------------------------
class AsUtil:
    def __init__(self):
        pass

    # ---------------------------------------------------
    # Enum -> String Converters
    # ---------------------------------------------------
    @staticmethod
    def get_process_type_string(proc_type):
        type_map = {
            ASCII_SERVER: "SERVER",
            ASCII_MANAGER: "MANAGER",
            ASCII_PARSER: "PARSER",
            ASCII_CONNECTOR: "CONNECTOR",
            ASCII_DATA_ROUTER: "DATA_ROUTER",
            ASCII_ROUTER: "ROUTER",
            ASCII_DATA_HANDLER: "DATA_HANDLER",
            ASCII_MMC_GENERATOR: "MMC_GENERATOR",
            ASCII_MMC_SCHEDULER: "MMC_SCHEDULER",
            ASCII_JOB_MONITOR: "JOB_MONITOR",
            GUI_RULE_EDITOR: "RULE_EDITOR",
            GUI_ASCII_CONFIG_INFO: "ASCII_CONFIG_INFO",
            GUI_ASCII_STATUS_INFO: "ASCII_STATUS_INFO",
            GUI_COMMAND_INFO: "COMMAND_INFO",
            ASCII_RULE_DOWNLOADER: "RULE_DOWNLOADER",
            ASCII_LOG_ROUTER: "LOG_ROUTER",
            NETFINDER: "NETFINDER",
            ASCII_SUB_PROCESS: "ASCII_SUB_PROCESS",
            # ... (필요 시 나머지 추가)
        }
        return type_map.get(proc_type, "UNKNOWN_TYPE")

    @staticmethod
    def get_schedule_type_string(sch_type):
        type_map = {
            SCH_RESERVE: "SCH_RESERVE",
            SCH_LOOP: "SCH_LOOP",
            SCH_MONITOR: "SCH_MONITOR"
        }
        return type_map.get(sch_type, "Unknown Enum Type")

    @staticmethod
    def get_response_result_mode_string(res_mode):
        mode_map = {
            RESPONSE_NOT_YET: "RESPONSE_NOT_YET",
            RESPONSE_CAPTURED: "RESPONSE_CAPTURED",
            RESPONSE_LOST: "RESPONSE_LOST"
        }
        return mode_map.get(res_mode, "Unknown Enum Type")

    @staticmethod
    def get_result_mode_string(res_mode):
        mode_map = {
            FAIL: "FAIL",
            SUCCEED: "SUCCEED"
        }
        return mode_map.get(res_mode, "Unknown Enum Type")

    @staticmethod
    def get_port_type_string(port_type):
        port_map = {
            UNDEFINED: "UNDEFINED",
            FM: "FM",
            TSPRT: "TSPRT",
            LUCENT_ECP_FM: "LUCENT_ECP_FM",
            PM1: "PM1",
            TM: "TM",
            TMA: "TMA",
            LUCENT_DCS_FM: "LUCENT_DCS_FM",
            PM2: "PM2",
            CM: "CM",
            CMD: "CMD",
            GATPRT: "GATPRT",
            GATCRT: "GATCRT",
            REVISE: "REVISE",
            SNMP_IF: "SNMP_IF",
            SNMP_PING: "SNMP_PING",
            CORBA_IF: "CORBA_IF",
            # ... (C++ 소스에 있는 나머지 포트 타입들) ...
        }
        return port_map.get(port_type, "UnKnown PortType")

    @staticmethod
    def get_protocol_type_string(proto_type):
        proto_map = {
            ASCII_AGENT: "ASCII_AGENT",
            ASCII_NAIM: "ASCII_NAIM",
            GAT: "GAT",
            PARSER_LISTEN: "PARSER_LISTEN",
            PARSER_CONNECT: "PARSER_CONNECT",
            ROUTER_LISTEN: "ROUTER_LISTEN",
            ROUTER_CONNECT: "ROUTER_CONNECT",
            DATAHANDLER_LISTEN: "DATAHANDLER_LISTEN",
            DATAHANDLER_CONNECT: "DATAHANDLER_CONNECT",
            DATAROUTER_LISTEN: "DATAROUTER_LISTEN",
            DATAROUTER_CONNECT: "DATAROUTER_CONNECT",
            MANAGER_CONNECT: "MANAGER_CONNECT",
            SNMP_AGENT: "SNMP_AGENT",
            # ... (C++ 소스에 있는 나머지 프로토콜 타입들) ...
        }
        return proto_map.get(proto_type, "UnKnown ProtoColType")

    @staticmethod
    def get_log_ctl_type_string(log_type):
        if log_type == GET_LOG_INFO: return "GET_LOG_INFO"
        if log_type == SET_LOG: return "SET_LOG"
        return "Unknown Enum Type"

    @staticmethod
    def get_action_type_string(act_type):
        act_map = {
            ACT_CREATE: "CREATE",
            ACT_MODIFY: "MODIFY",
            ACT_START: "START",
            ACT_STOP: "STOP",
            ACT_DELETE: "DELETE"
        }
        return act_map.get(act_type, "Unknown Enum Type")

    @staticmethod
    def get_port_status_type_string(status_type):
        status_map = {
            PORT_CONNECTED: "PORT_CONNECTED",
            PORT_NORMAL: "PORT_NORMAL",
            PORT_DISCONNECTED: "PORT_DISCONNECTED",
            PORT_ELIMINATION: "PORT_ELIMINATION"
        }
        return status_map.get(status_type, "Unknown PORT_STS_MODE Type")

    @staticmethod
    def get_request_status_string(status):
        status_map = {
            WAIT_NO: "WAIT_NO",
            WAIT_START: "WAIT_START",
            WAIT_STOP: "WAIT_STOP",
            CREATE_DATA: "CREATE_DATA",
            UPDATE_DATA: "UPDATE_DATA",
            DELETE_DATA: "DELETE_DATA"
        }
        return status_map.get(status, "Unknown Status")

    @staticmethod
    def get_status_string(status):
        status_map = {
            START: "START",
            STOP: "STOP"
        }
        return status_map.get(status, "Unknown Status")

    @staticmethod
    def get_junction_type_string(j_type):
        # CommType에 ASCII_J 등의 상수가 정의되어 있다고 가정
        try:
            j_map = {
                ASCII_J: "ASCII",
                Q3_J: "Q3",
                SNMP_J: "SNMP",
                CORBA_J: "CORBA"
            }
            return j_map.get(j_type, "Unknown junction type")
        except NameError:
            return "Unknown"

    @staticmethod
    def get_data_handler_mode_string(mode):
        # CommType에 DB_LOAD_SQLLOADER 등 정의 가정
        try:
            mode_map = {
                DB_LOAD_SQLLOADER: "DB_LOAD_SQLLOADER",
                DB_LOAD_OCI: "DB_LOAD_OCI",
                SAVE_FILE: "SAVE_FILE",
                BYPASS_SERVER: "BYPASS_SERVER",
                BYPASS_CLIENT: "BYPASS_CLIENT"
            }
            return mode_map.get(mode, "Unknown Data Handler mode")
        except NameError:
            return "Unknown"

    # ---------------------------------------------------
    # Display & Compare
    # ---------------------------------------------------
    @staticmethod
    def cmd_open_port_display(port_info):
        print("== CmdOpenPort ==============================")
        print(f"              Id : {port_info.Id}")
        print(f"        Sequence : {port_info.Sequence}")
        print(f"         EquipId : {port_info.EquipId}")
        print(f"    AgentEquipId : {port_info.AgentEquipId}")
        print(f"        Consumer : {port_info.Consumer}")
        print(f"            Name : {port_info.Name}")
        print(f"     ConnectorId : {port_info.ConnectorId}")
        print(f"       IpAddress : {port_info.IpAddress}")
        print(f"          PortNo : {port_info.PortNo}")
        print(f"        PortPath : {port_info.PortPath}")
        print(f"          UserId : {port_info.UserId}")
        print(f"        Password : {port_info.Password}")
        print(f"    ProtocolType : {AsUtil.get_protocol_type_string(port_info.ProtocolType)}")
        print(f"        PortType : {AsUtil.get_port_type_string(port_info.PortType)} ({port_info.PortType})")
        print(f"         GatFlag : {port_info.GatFlag}")
        print(f"            DnId : {port_info.DnId}")
        print(f" CommandPortFlag : {port_info.CommandPortFlag}")
        print("==============================================")

    @staticmethod
    def open_port_info_cmp(info1, info2):
        # Python 객체 속성 비교
        return (
            info1.EquipId == info2.EquipId and
            info1.Consumer == info2.Consumer and
            info1.ConnectorId == info2.ConnectorId and
            info1.IpAddress == info2.IpAddress and
            info1.PortNo == info2.PortNo and
            info1.PortPath == info2.PortPath and
            info1.UserId == info2.UserId and
            info1.Password == info2.Password and
            info1.AsciiHeader == info2.AsciiHeader and
            info1.ProtocolType == info2.ProtocolType and
            info1.PortType == info2.PortType and
            info1.GatFlag == info2.GatFlag and
            info1.CommandPortFlag == info2.CommandPortFlag and
            info1.DnId == info2.DnId
        )

    # ---------------------------------------------------
    # System Utils
    # ---------------------------------------------------
    @staticmethod
    def get_local_ip():
        return FrUtilMisc.get_local_ip()

    @staticmethod
    def as_sleep(useconds):
        FrUtilMisc.sleep2(useconds)

    @staticmethod
    def get_host_name():
        return socket.gethostname()

    @staticmethod
    def get_home_dir():
        return os.environ.get("HOME", "")

    @staticmethod
    def get_user_name():
        return os.environ.get("USER", "")

    @staticmethod
    def convert_mmc_old_to_new(old_req, new_req):
        """
        C++: void ConvertMMC_OldToNew(AS_MMC_REQUEST_OLD_T*, AS_MMC_REQUEST_T*)
        """
        new_req.id = old_req.id
        new_req.ne = old_req.ne
        new_req.type = old_req.type
        new_req.referenceId = old_req.referenceId
        new_req.interfaces = old_req.interfaces
        new_req.responseMode = old_req.responseMode
        new_req.publishMode = old_req.publishMode
        new_req.collectMode = old_req.collectMode
        new_req.mmc = old_req.mmc
        new_req.userid = old_req.userid
        new_req.display = old_req.display
        new_req.cmdDelayTime = old_req.cmdDelayTime
        new_req.retryNo = old_req.retryNo
        new_req.curRetryNo = old_req.curRetryNo
        new_req.parameterNo = old_req.parameterNo
        new_req.priority = old_req.priority
        new_req.logMode = old_req.logMode
        # 파라미터 리스트 복사 (Deep Copy 권장)
        import copy
        new_req.parameters = copy.deepcopy(old_req.parameters)

    @staticmethod
    def resize_memory(cur_buf, cur_size, new_size):
        # Python에서는 자동 관리되므로 로직 불필요 (호환성용 Stub)
        if cur_size < new_size:
            # print(f"Memory resizing : old({cur_size}), new({new_size})")
            return bytearray(new_size)
        return cur_buf