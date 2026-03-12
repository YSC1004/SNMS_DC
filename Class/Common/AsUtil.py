"""
[변경이력]
2014.07.08  초기 작성
Python 변환: AsUtil.h/.C → AsUtil.py

역할: 시스템 전역 정적 유틸리티 메서드 모음
  - Enum/Type → 문자열 변환
  - 시스템 정보 조회 (IP, 호스트명, 홈 디렉토리 등)
  - MMC 구조체 변환
  - 메모리 버퍼 관리 (Python bytearray 대응)
"""

import os
import socket
import time
import logging
from copy import deepcopy
from typing import Optional

from Common.CommType import (
    AS_CMD_OPEN_PORT_T, AS_MMC_REQUEST_OLD_T, AS_MMC_REQUEST_T,
    SCHEDULE_TYPE, RESPONSE_RESULT_MODE, RESULT_MODE,
    LOG_CTL_TYPE, AS_SEGFLAG, SYNCDB_KIND, ACTION_TYPE,
    # 프로세스 타입 상수
    ASCII_SERVER, ASCII_MANAGER, ASCII_PARSER, ASCII_CONNECTOR,
    ASCII_DATA_ROUTER, ASCII_ROUTER, ASCII_DATA_HANDLER,
    ASCII_MMC_GENERATOR, ASCII_MMC_SCHEDULER, ASCII_JOB_MONITOR,
    GUI_RULE_EDITOR, GUI_ASCII_CONFIG_INFO, GUI_ASCII_STATUS_INFO,
    GUI_COMMAND_INFO, ASCII_RULE_DOWNLOADER, ASCII_LOG_ROUTER,
    NETFINDER, SNMP_CMD_SERVER, SNMP_EVENT_SERVER, SNMP_IP_POLLER,
    CORBA_CMD_SERVER, CORBA_EVENT_SERVER, CORBA_IP_POLLER,
    ORB_SCHEDULER, ORB_DC_MANAGER, ORB_GW_CMD_SERVER, ORB_GW_EVENT_SERVER,
    ASCII_SUB_PROCESS,
    # 포트 타입 상수
    UNDEFINED, FM, TSPRT, LUCENT_ECP_FM, PM1, TM, TMA, LUCENT_DCS_FM,
    PM2, CM, CMD, GATPRT, GATCRT, REVISE,
    VMS_SMS_HOURLY, VMS_SMS_DAILY, VMS_USER_DAILY, VMS_TG_HOURLY,
    SNMP_IF, SNMP_PING, CORBA_IF, LUCENT_ECP_CMD, LUCENT_DCS_CMD,
    VMS_SMS_5MIN, VMS_GW_HOURLY, VMS_SUBCOUNT_HOURLY,
    BC2G_PM1, BC1X_PM1, BCEV_PM1, LG3GBSS_CM_CMD, F3000, LGXHOUR, SG_FM,
    REMS_R5GATE, REMS_SMS, MOGABI_RFST, MOGABI_RFSI, MOGABI_RFMT, MOGABI_RFSM,
    REMS_R5GATE_MMC, REMS_WAVE, REMS_SKTI, NF3000, SSF3000, PREFIX,
    WIBRO_F3000, WAVE1_CALL_TRACE, WAVE2_CALL_TRACE, WIBRO_FTP_LOG,
    WIBRO_RF, PCC, WIBRO_NETIS,
    LTAS_LOG_KCC_VoLTE, LTAS_LOG_KCC_NEW_VoLTE, LTAS_LOG_KCC_R_APP,
    LTAS_LOG_KCC_APP, LTAS_LOG_CALL_FTP, LTAS_LOG_CTQ_UL,
    SFTP_TEST_AGENT,
    # 포트 상태 상수
    PORT_CONNECTED, PORT_NORMAL, PORT_DISCONNECTED, PORT_ELIMINATION,
    # 요청 상태 상수
    WAIT_NO, WAIT_START, WAIT_STOP, CREATE_DATA, UPDATE_DATA, DELETE_DATA,
    START, STOP,
    # Junction 타입
    ASCII_J, Q3_J, SNMP_J, CORBA_J,
    # DataHandler 모드
    DB_LOAD_SQLLOADER, DB_LOAD_OCI, SAVE_FILE, BYPASS_SERVER, BYPASS_CLIENT,
    SAVE_FILE2, SAVE_FILE3, SAVE_FILE_BC,
    # Log cycle
    ARG_LOG_DAY, ARG_LOG_HOUR,
    # 기타
    STR_UNKNOWN_TYPE,
    # 프로토콜 타입 상수 (일부 대표값)
    ASCII_AGENT, ASCII_NAIM, GAT, PARSER_LISTEN, PARSER_CONNECT,
    ROUTER_LISTEN, ROUTER_CONNECT, DATAHANDLER_LISTEN, DATAHANDLER_CONNECT,
    DATAROUTER_LISTEN, DATAROUTER_CONNECT, MANAGER_CONNECT,
    SS1XBSS, SS2GBSS, TER_SER, JOBMONITOR_CONNECT, OMCR, LUCENT, FREENET,
    VMS, SSHLR, TEMIP, NEC, TEMIP_DATA_AGENT, NET_SNMP, NET_CORBA,
    ECI, COP_LUCENT, COP_NORTEL, COP_WDCS, COP_SMUX, EMS_AGENT,
    SPARE_PROTO1, SPARE_PROTO2, SPARE_PROTO3, IPGS_AGENT, WDCS_AGENT,
    FE1_AGENT, DOTS_AGENT, STP_AGENT, LGEVDOBSS, ACTL_AGENT, LGWDCS_AGENT,
    SS3GMGW_AGENT, SS3GMSV_AGENT, SS3GBSS_AGENT, LG3GBSS_AGENT, SS3GSGSN_AGENT,
    MCODE_SS1X_AGENT, MCODE_SS2G_AGENT, MCODE_SS3G_AGENT, MCODE_LG3G_AGENT,
    MNMUX_AGENT, SG_AGENT, ALCATEL_AGENT, LG_MSV_TMA_AGENT, REMS_R5GATE_AGENT,
    REMS_SMS_AGENT, AROMA_AGENT, MOGABI_RFST_AGENT, MOGABI_RFSI_AGENT,
    MOGABI_RFMT_AGENT, REMS_R5GATE_MMC_AGENT, KTFRIEND_AGENT, SMCI_IF_AGENT,
    REMS_WAVE_AGENT, REMS_SKTI_AGENT, SIM_TT_AGENT, NF3000_AGENT, SSF3000_AGENT,
    PREFIX_SG_NGRD_AGENT, PREFIX_SG_INNET_AGENT, PREFIX_MSV_SS_3G_AGENT,
    WIBRO_W1_AGENT, WIBRO_W2_AGENT, WIBRO_RF_AGENT, SS3GGGSN_AGENT,
    WIBRO_W1_SOAP_AGENT, WIBRO_W2_SOAP_AGENT, SSIMSSPR_AGENT, SS3GGGSNPCC_AGENT,
    SSIMSMRF_AGENT, WIBRO_W2_POS_AGENT, SSIMSPCRF_AGENT, LG3GBSS15MIN_AGENT,
    WIBRO_NETIS_AGENT, WREMS_SNMP_AGENT, WIBRO_L2_AGENT,
    WIFI_SNMP_AGENT, WIFI_PING_AGENT, WIFI_WIMS_AGENT, AROMA_PLUS_AGENT,
    SMARTI_CM_AGENT, STP_SECU_AGENT, LG3GBSSMULTI_AGENT, LG3GBSSMULTI_FM_AGENT,
    WIFI_WIMS_FTP_AGENT, WIFI_BAS_FTP_AGENT, LG3GBSS15MMULTI_AGENT,
    LGE3GBSSCCC15M_AGENT, SSWGS_AGENT, LGE3GBSSFM_AGENT, LGE3GBSSCCCCM_AGENT,
    PREFIX_SG_NGRD2_AGENT, SS3GSGSN2_AGENT, SS3GMSVMGW2_AGENT, SS3GMGW2_AGENT,
    LGE3GBSSCCCMULTIPEG_AGENT, NEW_SG_AGENT,
    SS3GMSVMGW2_ASCII_AGENT, SS3GSGSN2_ASCII_AGENT, SSWGS_ASCII_AGENT,
    MMS_CMD_AGENT, LGE3GBSSCCCRBS_AGENT, LGE3GBSSCCCCM2_AGENT, LG3GBSSCMNBR_AGENT,
    LTE_MME_SS_AGENT, LTE_ENB_SS_AGENT, LTE_PGW_YW_AGENT, LTE_SGW_YW_AGENT,
    SS3GBSS_ASCII_AGENT, LTE_ENB_LGE_15M_AGENT, LTE_ENB_LGE_5M_AGENT,
    LTE_ENB_NSN_AGENT, LTE_ENB_NSN_CM_AGENT, LTE_ENB_LGE_MPEG_AGENT,
    MERQ_FEMTO_AGENT, LTE_ENB_NSN2_AGENT, WIFI_NEW_WIMS_FTP_AGENT,
    LTE_MME_SS_RE_AGENT, LTE_ENB_SS_RE_AGENT, LTE_ENB_LGE_15M_RE_AGENT,
    SS3GMSVMGW2_RE_AGENT, SS3GSGSN2_RE_AGENT, SS3GBSS_RE_AGENT,
    LGE3GBSSCCC15M_RE_AGENT, LTE_ENB_NSN_5M_AGENT, MERQ_FEMTO_NMS_AGENT,
    LTE_ENB_LGE_5M_KC_AGENT, LTE_FEMTO_YW_AGENT, LTE_FEMTO_INO_AGENT,
    LTE_NSN_SP_CM_AGENT, LTE_FEMTO_CM_AGENT, LTE_MRF_TIQ_AGENT, SM_SERVER_AGENT,
    LTE_MME_MULTI_SS_AGENT, LTE_IMG_LOCS_AGENT, LTE_FEMTO_DWTI_AGENT,
    LTE_FEMTO_JUKO_AGENT, LTE_PCRF_TEK_AGENT, LTE_DRA_IRUE_AGENT,
    IMS_CSCF_SS_AGENT, LTE_ENB_LGE_15M_ENIQ_AGENT, LTE_TASDB_DINN_AGENT,
    LTE_ESMLC_IRUE_AGENT, MIDAS_KSMS_AGENT, KSMS_AGENT, LTE_SGW_SS_AGENT,
    IMS_CSCF_ACRO_AGENT, IMS_IBCF_ACRO_AGENT, IMS_IBCF_IRUE_AGENT,
    IMS_IBCF_NABLE_AGENT, LTE_PGW_SS_AGENT, LTE_SGWPGW_SS_AGENT,
    LTE_NBMSC_YOOE_AGENT, LTE_MBMS_SS_AGENT, LTE_HOME_FEMTO_INO_AGENT,
    LTE_ENB_LGE_CM_AGENT, LTE_ENB_LGE_CM1_AGENT, FEP_YOO_AGENT,
    LTE_TAS_DINN_AGENT, LTE_TSUP_DINN_AGENT, LTE_TAS_BRGT_AGENT,
    LTE_PCRFMGW_TEK_AGENT, LTE_PGW_TEST_AGENT, RCCS_AGENT,
    MME_MBMS_MULTI_AGENT, PUBS_AR_AGENT, LTE_PCRF_MULTI_AGENT,
    MAGW_IRU_AGENT, TEST_AGENT, PLAS_ARIE_AGENT, LTAS_AGENT,
    LTE_HSS_IRUE_AGENT, LTE_HSS_SDS_AGENT, LTE_CSC_SDS_AGENT,
    LTE_MRF_IRUE_AGENT, LTE_DEA_IRUE_AGENT, LTE_UMC_IRUE_AGENT,
    LTE_SMSC_LOCS_AGENT, LTE_MMSC_LOCS_AGENT, LTE_IPLS_LOCS_AGENT,
    LTE_MGCF_IPGO_AGENT, LTE_MGW_IPGO_AGENT, REC_XCURE_AGENT,
    SNMP_AGENT, SG_ASCII_CMD_NMS, SG_ASCII_CMD_OPER, HTTP_AGENT_CMD,
    SG_SAME_AMF_AGENT, SG_IRUE_UDM_AGENT, SG_IRUE_UDR_AGENT,
    SG_SAME_CSCF_AGENT, SG_CICS_AMF_AGENT, SG_CICS_SMF_AGENT,
    SG_CICS_UPF_AGENT, SG_CICS_UPF2_AGENT, SG_SAME_CSL_AGENT,
    SG_SAME_VSM_AGENT, SG_LGES_ENM_15M_AGENT, SG_NSNN_NETACT_AGENT,
    SG_NSNN_NETACT_CM_AGENT, SG_ARIE_ePCF_AGENT, SG_SNET_PCF_AGENT,
    SG_SNET_PCRF_AGENT, SG_LGE_ENM_CM_CELL_AGENT, SG_LGE_ENM_CM_SITE_AGENT,
    SG_ARIE_SMLC_AGENT, SG_IRUE_SMLC_AGENT, SG_IRUE_VTAS_AGENT,
    SG_SAME_VSM_5M_AGENT, SG_SAME_VSM_5M_DIV_AGENT, SG_SAME_VSM_15M_AGENT,
    SG_NSNN_NETACT_5M_AGENT, SG_VSM_SAME_CM_DU_AGENT, SG_VSM_SAME_CM_CU_AGENT,
    SG_USM_SAME_CM_DU30_AGENT, SG_VSM_SAME_CM_AU_AGENT, SG_NSNN_NETACT_CM2_AGENT,
    SG_SAME_VSM_CU_5M_AGENT, SG_ARIE_DQE_AGENT, SG_IRUE_iPgw_AGENT,
    SG_LGES_ENM_15M_GZ_AGENT, SG_LGES_ENM_60M_GZ_AGENT,
    SG_LGES_ENM_60M_GZ_DIV_AGENT, SG_LGES_ENM_15M_GZ_PF_AGENT,
    SG_LGES_ENM_15M_GZ_DIV_AGENT, SG_SAME_AMF_CSL_AGENT, SG_IRUE_UDAF_AGENT,
    SG_SAME_USM_AGENT, SG_IRUE_AUSF_AGENT, SG_IRUE_AUSF_CSL_AGENT,
    SG_ARIE_PCC_AGENT, SG_IRUE_NRF_AGENT, SG_ARIE_LMF_AGENT,
    SG_SNET_PCF_SA_AGENT, SG_ARIE_IOTGW_AGENT, SG_ARIE_ePCF_HH_AGENT,
    SG_ARIE_EMG_AGENT, SG_SAME_VSM_CU_DIV_AGENT, SG_ARIE_FNPS_AGENT,
    SG_SAME_USM_CU_5M_AGENT, SG_SAME_USM_5M_AGENT, SG_SAME_USM_60M_AGENT,
    SG_LOCS_KPNS_AGENT, SG_LOCS_IPSMGW_AGENT,
    SG_LGE_ENM_COM_CELL_AGENT, SG_LGE_ENM_COM_DU_AGENT,
    SG_ARIE_FNPSMP_AGENT, SG_LGE_ES_GET_AGENT, SG_LGE_ES_GET_NEW_AGENT,
    SG_ARIE_ESAN_AGENT, SG_ARIE_GMG_AGENT, SG_ARIE_ERS_AGENT,
    SG_ARIE_SSPF_AGENT, SG_IRUE_DRA_AGENT, SG_IRUE_vIBCF_AGENT,
    SG_BRGT_MRF_AGENT, SG_ARIE_CCS_AGENT, SG_ARIE_LTE_PCC_AGENT,
    ALARM_CHG_ASCII_AGENT,
)
from Common.AsciiMmcType import (
    AS_MMC_TYPE, AS_MMC_INTERFACE, AS_MMC_RESPONSE_MODE,
    AS_MMC_COLLECT_MODE, AS_MMC_RESULT_MODE, AS_MMC_PUBLISH_MODE,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 조회 테이블 (switch-case → dict)
# 초기화 비용을 줄이기 위해 모듈 레벨에서 한 번만 생성
# ─────────────────────────────────────────────

_PROCESS_TYPE_STR: dict = {
    ASCII_SERVER:           "SERVER",
    ASCII_MANAGER:          "MANAGER",
    ASCII_PARSER:           "PARSER",
    ASCII_CONNECTOR:        "CONNECTOR",
    ASCII_DATA_ROUTER:      "DATA_ROUTER",
    ASCII_ROUTER:           "ROUTER",
    ASCII_DATA_HANDLER:     "DATA_HANDLER",
    ASCII_MMC_GENERATOR:    "MMC_GENERATOR",
    ASCII_MMC_SCHEDULER:    "MMC_SCHEDULER",
    ASCII_JOB_MONITOR:      "JOB_MONITOR",
    GUI_RULE_EDITOR:        "RULE_EDITOR",
    GUI_ASCII_CONFIG_INFO:  "ASCII_CONFIG_INFO",
    GUI_ASCII_STATUS_INFO:  "ASCII_STATUS_INFO",
    GUI_COMMAND_INFO:       "COMMAND_INFO",
    ASCII_RULE_DOWNLOADER:  "RULE_DOWNLOADER",
    ASCII_LOG_ROUTER:       "LOG_ROUTER",
    NETFINDER:              "NETFINDER",
    SNMP_CMD_SERVER:        "SNMP_CMD_SERVER",
    SNMP_EVENT_SERVER:      "SNMP_EVENT_SERVER",
    SNMP_IP_POLLER:         "SNMP_IP_POLLER",
    CORBA_CMD_SERVER:       "CORBA_CMD_SERVER",
    CORBA_EVENT_SERVER:     "CORBA_EVENT_SERVER",
    CORBA_IP_POLLER:        "CORBA_IP_POLLER",
    ORB_SCHEDULER:          "ORB_SCHEDULER",
    ORB_DC_MANAGER:         "ORB_DC_MANAGER",
    ORB_GW_CMD_SERVER:      "ORB_GW_CMD_SERVER",
    ORB_GW_EVENT_SERVER:    "ORB_GW_EVENT_SERVER",
    ASCII_SUB_PROCESS:      "ASCII_SUB_PROCESS",
}

_PORT_TYPE_STR: dict = {
    UNDEFINED:              "UNDEFINED",
    FM:                     "FM",
    TSPRT:                  "TSPRT",
    LUCENT_ECP_FM:          "LUCENT_ECP_FM",
    PM1:                    "PM1",
    TM:                     "TM",
    TMA:                    "TMA",
    LUCENT_DCS_FM:          "LUCENT_DCS_FM",
    PM2:                    "PM2",
    CM:                     "CM",
    CMD:                    "CMD",
    GATPRT:                 "GATPRT",
    GATCRT:                 "GATCRT",
    REVISE:                 "REVISE",
    VMS_SMS_HOURLY:         "VMS_SMS_HOURLY",
    VMS_SMS_DAILY:          "VMS_SMS_DAILY",
    VMS_USER_DAILY:         "VMS_USER_DAILY",
    VMS_TG_HOURLY:          "VMS_TG_HOURLY",
    SNMP_IF:                "SNMP_IF",
    SNMP_PING:              "SNMP_PING",
    CORBA_IF:               "CORBA_IF",
    LUCENT_ECP_CMD:         "LUCENT_ECP_CMD",
    LUCENT_DCS_CMD:         "LUCENT_DCS_CMD",
    VMS_SMS_5MIN:           "VMS_SMS_5MIN",
    VMS_GW_HOURLY:          "VMS_GW_HOURLY",
    VMS_SUBCOUNT_HOURLY:    "VMS_SUBCOUNT_HOURLY",
    BC2G_PM1:               "BC2G_PM1",
    BC1X_PM1:               "BC1X_PM1",
    BCEV_PM1:               "BCEV_PM1",
    LG3GBSS_CM_CMD:         "LG3GBSS_CM_CMD",
    F3000:                  "F3000",
    LGXHOUR:                "LGXHOUR",
    SG_FM:                  "SG_FM",
    REMS_R5GATE:            "REMS_R5GATE",
    REMS_SMS:               "REMS_SMS",
    MOGABI_RFST:            "MOGABI_RFST",
    MOGABI_RFSI:            "MOGABI_RFSI",
    MOGABI_RFMT:            "MOGABI_RFMT",
    MOGABI_RFSM:            "MOGABI_RFSM",
    REMS_R5GATE_MMC:        "REMS_R5GATE_MMC",
    REMS_WAVE:              "REMS_WAVE",
    REMS_SKTI:              "REMS_SKTI",
    NF3000:                 "NF3000",
    SSF3000:                "SSF3000",
    PREFIX:                 "PREFIX",
    WIBRO_F3000:            "WIBRO_F3000",
    WAVE1_CALL_TRACE:       "WAVE1_CALL_TRACE",
    WAVE2_CALL_TRACE:       "WAVE2_CALL_TRACE",
    WIBRO_FTP_LOG:          "WIBRO_FTP_LOG",
    WIBRO_RF:               "WIBRO_RF",
    PCC:                    "PCC",
    WIBRO_NETIS:            "WIBRO_NETIS",
    LTAS_LOG_KCC_VoLTE:     "LTAS_LOG_KCC_VoLTE",
    LTAS_LOG_KCC_NEW_VoLTE: "LTAS_LOG_KCC_NEW_VoLTE",
    LTAS_LOG_KCC_R_APP:     "LTAS_LOG_KCC_R_APP",
    LTAS_LOG_KCC_APP:       "LTAS_LOG_KCC_APP",
    LTAS_LOG_CALL_FTP:      "LTAS_LOG_CALL_FTP",
    SFTP_TEST_AGENT:        "SFTP_TEST_AGENT",
    LTAS_LOG_CTQ_UL:        "LTAS_LOG_CTQ_UL",
}

_PROTOCOL_TYPE_STR: dict = {
    ASCII_AGENT:                "ASCII_AGENT",
    ASCII_NAIM:                 "ASCII_NAIM",
    GAT:                        "GAT",
    PARSER_LISTEN:              "PARSER_LISTEN",
    PARSER_CONNECT:             "PARSER_CONNECT",
    ROUTER_LISTEN:              "ROUTER_LISTEN",
    ROUTER_CONNECT:             "ROUTER_CONNECT",
    DATAHANDLER_LISTEN:         "DATAHANDLER_LISTEN",
    DATAHANDLER_CONNECT:        "DATAHANDLER_CONNECT",
    DATAROUTER_LISTEN:          "DATAROUTER_LISTEN",
    DATAROUTER_CONNECT:         "DATAROUTER_CONNECT",
    MANAGER_CONNECT:            "MANAGER_CONNECT",
    SS1XBSS:                    "SS1XBSS",
    SS2GBSS:                    "SS2GBSS",
    TER_SER:                    "TER_SER",
    JOBMONITOR_CONNECT:         "JOBMONITOR_CONNECT",
    OMCR:                       "OMCR",
    LUCENT:                     "LUCENT",
    FREENET:                    "FREENET",
    VMS:                        "VMS",
    SSHLR:                      "SSHLR",
    TEMIP:                      "TEMIP",
    NEC:                        "NEC",
    # TEMIP_DATA_AGENT == Q3_AGENT == 1327: 동일 값, TEMIP_DATA_AGENT 우선
    TEMIP_DATA_AGENT:           "TEMIP_DATA_AGENT",
    NET_SNMP:                   "SNMP_AGENT",
    NET_CORBA:                  "CORBA_AGENT",
    ECI:                        "ECI",
    COP_LUCENT:                 "COP_LUCENT",
    COP_NORTEL:                 "COP_NORTEL",
    COP_WDCS:                   "COP_WDCS",
    COP_SMUX:                   "COP_SMUX",
    EMS_AGENT:                  "EMS_AGENT",
    SPARE_PROTO1:               "SPARE_PROTO1",
    SPARE_PROTO2:               "SPARE_PROTO2",
    SPARE_PROTO3:               "SPARE_PROTO3",
    IPGS_AGENT:                 "IPGS_AGENT",
    WDCS_AGENT:                 "WDCS_AGENT",
    FE1_AGENT:                  "FE1_AGENT",
    DOTS_AGENT:                 "DOTS_AGENT",
    STP_AGENT:                  "STP_AGENT",
    LGEVDOBSS:                  "BC_LGEVDO",
    ACTL_AGENT:                 "ACTL_AGENT",
    LGWDCS_AGENT:               "LGWDCS_AGENT",
    SS3GMGW_AGENT:              "SS3GMGW_AGENT",
    SS3GMSV_AGENT:              "SS3GMSV_AGENT",
    SS3GBSS_AGENT:              "SS3GBSS_AGENT",
    LG3GBSS_AGENT:              "LG3GBSS_AGENT",
    SS3GSGSN_AGENT:             "SS3GSGSN_AGENT",
    MCODE_SS1X_AGENT:           "MCODE_SS1X_AGENT",
    MCODE_SS2G_AGENT:           "MCODE_SS2G_AGENT",
    MCODE_SS3G_AGENT:           "MCODE_SS3G_AGENT",
    MCODE_LG3G_AGENT:           "MCODE_LG3G_AGENT",
    MNMUX_AGENT:                "MNMUX_AGENT",
    SG_AGENT:                   "SG_AGENT",
    ALCATEL_AGENT:              "ALCATEL_AGENT",
    LG_MSV_TMA_AGENT:           "LG_MSV_TMA_AGENT",
    REMS_R5GATE_AGENT:          "REMS_R5GATE_AGENT",
    REMS_SMS_AGENT:             "REMS_SMS_AGENT",
    AROMA_AGENT:                "AROMA_AGENT",
    MOGABI_RFST_AGENT:          "MOGABI_RFST_AGENT",
    MOGABI_RFSI_AGENT:          "MOGABI_RFSI_AGENT",
    MOGABI_RFMT_AGENT:          "MOGABI_RFMT_AGENT",
    REMS_R5GATE_MMC_AGENT:      "REMS_R5GATE_MMC_AGENT",
    KTFRIEND_AGENT:             "KTFRIEND_AGENT",
    SMCI_IF_AGENT:              "SMCI_IF_AGENT",
    REMS_WAVE_AGENT:            "REMS_WAVE_AGENT",
    REMS_SKTI_AGENT:            "REMS_SKTI_AGENT",
    SIM_TT_AGENT:               "SIM_TT_AGENT",
    NF3000_AGENT:               "NF3000_AGENT",
    SSF3000_AGENT:              "SSF3000_AGENT",
    PREFIX_SG_NGRD_AGENT:       "PREFIX_SG_NGRD_AGENT",
    PREFIX_SG_INNET_AGENT:      "PREFIX_SG_INNET_AGENT",
    PREFIX_MSV_SS_3G_AGENT:     "PREFIX_MSV_SS_3G_AGENT",
    WIBRO_W1_AGENT:             "WIBRO_W1_AGENT",
    WIBRO_W2_AGENT:             "WIBRO_W2_AGENT",
    WIBRO_RF_AGENT:             "WIBRO_RF_AGENT",
    SS3GGGSN_AGENT:             "SS3GGGSN_AGENT",
    WIBRO_W1_SOAP_AGENT:        "WIBRO_W1_SOAP_AGENT",
    WIBRO_W2_SOAP_AGENT:        "WIBRO_W2_SOAP_AGENT",
    SSIMSSPR_AGENT:             "SSIMSSPR_AGENT",
    SS3GGGSNPCC_AGENT:          "SS3GGGSNPCC_AGENT",
    SSIMSMRF_AGENT:             "SSIMSMRF_AGENT",
    WIBRO_W2_POS_AGENT:         "WIBRO_W2_POS_AGENT",
    SSIMSPCRF_AGENT:            "SSIMSPCRF_AGENT",
    LG3GBSS15MIN_AGENT:         "LG3GBSS15MIN_AGENT",
    WIBRO_NETIS_AGENT:          "WIBRO_NETIS_AGENT",
    WREMS_SNMP_AGENT:           "WREMS_SNMP_AGENT",
    WIBRO_L2_AGENT:             "WIBRO_L2_AGENT",
    WIFI_SNMP_AGENT:            "WIFI_SNMP_AGENT",
    WIFI_PING_AGENT:            "WIFI_PING_AGENT",
    WIFI_WIMS_AGENT:            "WIFI_WIMS_AGENT",
    AROMA_PLUS_AGENT:           "AROMA_PLUS_AGENT",
    SMARTI_CM_AGENT:            "SMARTI_CM_AGENT",
    STP_SECU_AGENT:             "STP_SECU_AGENT",
    LG3GBSSMULTI_AGENT:         "LG3GBSSMULTI_AGENT",
    LG3GBSSMULTI_FM_AGENT:      "LG3GBSSMULTI_FM_AGENT",
    WIFI_WIMS_FTP_AGENT:        "WIFI_WIMS_FTP_AGENT",
    WIFI_BAS_FTP_AGENT:         "WIFI_BAS_FTP_AGENT",
    LG3GBSS15MMULTI_AGENT:      "LG3GBSS15MMULTI_AGENT",
    LGE3GBSSCCC15M_AGENT:       "LGE3GBSSCCC15M_AGENT",
    SSWGS_AGENT:                "SSWGS_AGENT",
    LGE3GBSSFM_AGENT:           "LGE3GBSSFM_AGENT",
    LGE3GBSSCCCCM_AGENT:        "LGE3GBSSCCCCM_AGENT",
    PREFIX_SG_NGRD2_AGENT:      "PREFIX_SG_NGRD2_AGENT",
    SS3GSGSN2_AGENT:            "SS3GSGSN2_AGENT",
    SS3GMSVMGW2_AGENT:          "SS3GMSVMGW2_AGENT",
    SS3GMGW2_AGENT:             "SS3GMGW2_AGENT",
    LGE3GBSSCCCMULTIPEG_AGENT:  "LGE3GBSSCCCMULTIPEG_AGENT",
    NEW_SG_AGENT:               "NEW_SG_AGENT",
    SS3GMSVMGW2_ASCII_AGENT:    "SS3GMSVMGW2_ASCII_AGENT",
    SS3GSGSN2_ASCII_AGENT:      "SS3GSGSN2_ASCII_AGENT",
    SSWGS_ASCII_AGENT:          "SSWGS_ASCII_AGENT",
    MMS_CMD_AGENT:              "MMS_CMD_AGENT",
    LGE3GBSSCCCRBS_AGENT:       "LGE3GBSSCCCRBS_AGENT",
    LGE3GBSSCCCCM2_AGENT:       "LGE3GBSSCCCCM2_AGENT",
    LG3GBSSCMNBR_AGENT:         "LLG3GBSSCMNBR_AGENT",
    LTE_MME_SS_AGENT:           "LTE_MME_SS_AGENT",
    LTE_ENB_SS_AGENT:           "LTE_ENB_SS_AGENT",
    LTE_PGW_YW_AGENT:           "LTE_PGW_YW_AGENT",
    LTE_SGW_YW_AGENT:           "LTE_SGW_YW_AGENT",
    SS3GBSS_ASCII_AGENT:        "SS3GBSS_ASCII_AGENT",
    LTE_ENB_LGE_15M_AGENT:      "LTE_ENB_LGE_15M_AGENT",
    LTE_ENB_LGE_5M_AGENT:       "LTE_ENB_LGE_5M_AGENT",
    LTE_ENB_NSN_AGENT:          "LTE_ENB_NSN_AGENT",
    LTE_ENB_NSN_CM_AGENT:       "LTE_ENB_NSN_CM_AGENT",
    LTE_ENB_LGE_MPEG_AGENT:     "LTE_ENB_LGE_MPEG_AGENT",
    MERQ_FEMTO_AGENT:           "MERQ_FEMTO_AGENT",
    LTE_ENB_NSN2_AGENT:         "LTE_ENB_NSN2_AGENT",
    WIFI_NEW_WIMS_FTP_AGENT:    "WIFI_NEW_WIMS_FTP_AGENT",
    LTE_MME_SS_RE_AGENT:        "LTE_MME_SS_RE_AGENT",
    LTE_ENB_SS_RE_AGENT:        "LTE_ENB_SS_RE_AGENT",
    LTE_ENB_LGE_15M_RE_AGENT:   "LTE_ENB_LGE_15M_RE_AGENT",
    SS3GMSVMGW2_RE_AGENT:       "SS3GMSVMGW2_RE_AGENT",
    SS3GSGSN2_RE_AGENT:         "SS3GSGSN2_RE_AGENT",
    SS3GBSS_RE_AGENT:           "SS3GBSS_RE_AGENT",
    LGE3GBSSCCC15M_RE_AGENT:    "LGE3GBSSCCC15M_RE_AGENT",
    LTE_ENB_NSN_5M_AGENT:       "LTE_ENB_NSN_5M_AGENT",
    MERQ_FEMTO_NMS_AGENT:       "MERQ_FEMTO_NMS_AGENT",
    LTE_ENB_LGE_5M_KC_AGENT:    "LTE_ENB_LGE_5M_KC_AGENT",
    LTE_FEMTO_YW_AGENT:         "LTE_FEMTO_YW_AGENT",
    LTE_FEMTO_INO_AGENT:        "LTE_FEMTO_INO_AGENT",
    LTE_NSN_SP_CM_AGENT:        "LTE_NSN_SP_CM_AGENT",
    LTE_FEMTO_CM_AGENT:         "LTE_FEMTO_CM_AGENT",
    LTE_MRF_TIQ_AGENT:          "LTE_MRF_TIQ_AGENT",
    SM_SERVER_AGENT:            "SM_SERVER_AGENT",
    LTE_MME_MULTI_SS_AGENT:     "LTE_MME_MULTI_SS_AGENT",
    LTE_IMG_LOCS_AGENT:         "LTE_IMG_LOCS_AGENT",
    LTE_FEMTO_DWTI_AGENT:       "LTE_FEMTO_DWTI_AGENT",
    LTE_FEMTO_JUKO_AGENT:       "LTE_FEMTO_JUKO_AGENT",
    LTE_PCRF_TEK_AGENT:         "LTE_PCRF_TEK_AGENT",
    LTE_DRA_IRUE_AGENT:         "LTE_DRA_IRUE_AGENT",
    IMS_CSCF_SS_AGENT:          "IMS_CSCF_SS_AGENT",
    LTE_ENB_LGE_15M_ENIQ_AGENT: "LTE_ENB_LGE_15M_ENIQ_AGENT",
    LTE_TASDB_DINN_AGENT:       "LTE_TASDB_DINN_AGENT",
    LTE_ESMLC_IRUE_AGENT:       "LTE_ESMLC_IRUE_AGENT",
    MIDAS_KSMS_AGENT:           "MIDAS_KSMS_AGENT",
    KSMS_AGENT:                 "KSMS_AGENT",
    LTE_SGW_SS_AGENT:           "LTE_SGW_SS_AGENT",
    IMS_CSCF_ACRO_AGENT:        "IMS_CSCF_ACRO_AGENT",
    IMS_IBCF_ACRO_AGENT:        "IMS_IBCF_ACRO_AGENT",
    IMS_IBCF_IRUE_AGENT:        "IMS_IBCF_IRUE_AGENT",
    IMS_IBCF_NABLE_AGENT:       "IMS_IBCF_NABLE_AGENT",
    LTE_PGW_SS_AGENT:           "LTE_PGW_SS_AGENT",
    LTE_SGWPGW_SS_AGENT:        "LTE_SGWPGW_SS_AGENT",
    LTE_NBMSC_YOOE_AGENT:       "LTE_NBMSC_YOOE_AGENT",
    LTE_MBMS_SS_AGENT:          "LTE_MBMS_SS_AGENT",
    LTE_HOME_FEMTO_INO_AGENT:   "LTE_HOME_FEMTO_INO_AGENT",
    LTE_ENB_LGE_CM_AGENT:       "LTE_ENB_LGE_CM_AGENT",
    LTE_ENB_LGE_CM1_AGENT:      "LTE_ENB_LGE_CM1_AGENT",
    FEP_YOO_AGENT:              "FEP_YOO_AGENT",
    LTE_TAS_DINN_AGENT:         "LTE_TAS_DINN_AGENT",
    LTE_TSUP_DINN_AGENT:        "LTE_TSUP_DINN_AGENT",
    LTE_TAS_BRGT_AGENT:         "LTE_TAS_BRGT_AGENT",
    LTE_PCRFMGW_TEK_AGENT:      "LTE_PCRFMGW_TEK_AGENT",
    LTE_PGW_TEST_AGENT:         "LTE_PGW_TEST_AGENT",
    RCCS_AGENT:                 "RCCS_AGENT",
    MME_MBMS_MULTI_AGENT:       "MME_MBMS_MULTI_AGENT",
    PUBS_AR_AGENT:              "PUBS_AR_AGENT",
    LTE_PCRF_MULTI_AGENT:       "LTE_PCRF_MULTI_AGENT",
    MAGW_IRU_AGENT:             "MAGW_IRU_AGENT",
    TEST_AGENT:                 "TEST_AGENT",
    PLAS_ARIE_AGENT:            "PLAS_ARIE_AGENT",
    LTAS_AGENT:                 "LTAS_AGENT",
    LTE_HSS_IRUE_AGENT:         "LTE_HSS_IRUE_AGENT",
    LTE_HSS_SDS_AGENT:          "LTE_HSS_SDS_AGENT",
    LTE_CSC_SDS_AGENT:          "LTE_CSC_SDS_AGENT",
    LTE_MRF_IRUE_AGENT:         "LTE_MRF_IRUE_AGENT",
    LTE_DEA_IRUE_AGENT:         "LTE_DEA_IRUE_AGENT",
    LTE_UMC_IRUE_AGENT:         "LTE_UMC_IRUE_AGENT",
    LTE_SMSC_LOCS_AGENT:        "LTE_SMSC_LOCS_AGENT",
    LTE_MMSC_LOCS_AGENT:        "LTE_MMSC_LOCS_AGENT",
    LTE_IPLS_LOCS_AGENT:        "LTE_IPLS_LOCS_AGENT",
    LTE_MGCF_IPGO_AGENT:        "LTE_MGCF_IPGO_AGENT",
    LTE_MGW_IPGO_AGENT:         "LTE_MGW_IPGO_AGENT",
    REC_XCURE_AGENT:            "REC_XCURE_AGENT",
    SNMP_AGENT:                 "SNMP_AGENT",
    SG_ASCII_CMD_NMS:           "SG_ASCII_CMD_NMS",
    SG_ASCII_CMD_OPER:          "SG_ASCII_CMD_OPER",
    HTTP_AGENT_CMD:             "HTTP_AGENT_CMD",
    SG_SAME_AMF_AGENT:          "SG_SAME_AMF_AGENT",
    SG_IRUE_UDM_AGENT:          "SG_IRUE_UDM_AGENT",
    SG_IRUE_UDR_AGENT:          "SG_IRUE_UDR_AGENT",
    SG_SAME_CSCF_AGENT:         "SG_SAME_CSCF_AGENT",
    SG_CICS_AMF_AGENT:          "SG_CICS_AMF_AGENT",
    SG_CICS_SMF_AGENT:          "SG_CICS_SMF_AGENT",
    SG_CICS_UPF_AGENT:          "SG_CICS_UPF_AGENT",
    SG_CICS_UPF2_AGENT:         "SG_CICS_UPF2_AGENT",
    SG_SAME_CSL_AGENT:          "SG_SAME_CSL_AGENT",
    SG_SAME_VSM_AGENT:          "SG_SAME_VSM_AGENT",
    SG_LGES_ENM_15M_AGENT:      "SG_LGES_ENM_15M_AGENT",
    SG_NSNN_NETACT_AGENT:       "SG_NSNN_NETACT_AGENT",
    SG_NSNN_NETACT_CM_AGENT:    "SG_NSNN_NETACT_CM_AGENT",
    SG_ARIE_ePCF_AGENT:         "SG_ARIE_ePCF_AGENT",
    SG_SNET_PCF_AGENT:          "SG_SNET_PCF_AGENT",
    SG_SNET_PCRF_AGENT:         "SG_SNET_PCRF_AGENT",
    SG_LGE_ENM_CM_CELL_AGENT:   "SG_LGE_ENM_CM_CELL_AGENT",
    SG_LGE_ENM_CM_SITE_AGENT:   "SG_LGE_ENM_CM_SITE_AGENT",
    SG_ARIE_SMLC_AGENT:         "SG_ARIE_SMLC_AGENT",
    SG_IRUE_SMLC_AGENT:         "SG_IRUE_SMLC_AGENT",
    SG_IRUE_VTAS_AGENT:         "SG_IRUE_VTAS_AGENT",
    SG_SAME_VSM_5M_AGENT:       "SG_SAME_VSM_5M_AGENT",
    SG_SAME_VSM_5M_DIV_AGENT:   "SG_SAME_VSM_5M_DIV_AGENT",
    SG_SAME_VSM_15M_AGENT:      "SG_SAME_VSM_15M_AGENT",
    SG_NSNN_NETACT_5M_AGENT:    "SG_NSNN_NETACT_5M_AGENT",
    SG_VSM_SAME_CM_DU_AGENT:    "SG_VSM_SAME_CM_DU_AGENT",
    SG_VSM_SAME_CM_CU_AGENT:    "SG_VSM_SAME_CM_CU_AGENT",
    SG_USM_SAME_CM_DU30_AGENT:  "SG_USM_SAME_CM_DU30_AGENT",
    SG_VSM_SAME_CM_AU_AGENT:    "SG_VSM_SAME_CM_AU_AGENT",
    SG_NSNN_NETACT_CM2_AGENT:   "SG_NSNN_NETACT_CM2_AGENT",
    SG_SAME_VSM_CU_5M_AGENT:    "SG_SAME_VSM_CU_5M_AGENT",
    SG_ARIE_DQE_AGENT:          "SG_ARIE_DQE_AGENT",
    SG_IRUE_iPgw_AGENT:         "SG_IRUE_iPgw_AGENT",
    SG_LGES_ENM_15M_GZ_AGENT:       "SG_LGES_ENM_15M_GZ_AGENT",
    SG_LGES_ENM_60M_GZ_AGENT:       "SG_LGES_ENM_60M_GZ_AGENT",
    SG_LGES_ENM_60M_GZ_DIV_AGENT:   "SG_LGES_ENM_60M_GZ_DIV_AGENT",
    SG_LGES_ENM_15M_GZ_PF_AGENT:    "SG_LGES_ENM_15M_GZ_PF_AGENT",
    SG_LGES_ENM_15M_GZ_DIV_AGENT:   "SG_LGES_ENM_15M_GZ_DIV_AGENT",
    SG_SAME_AMF_CSL_AGENT:      "SG_SAME_AMF_CSL_AGENT",
    SG_IRUE_UDAF_AGENT:         "SG_IRUE_UDAF_AGENT",
    SG_SAME_USM_AGENT:          "SG_SAME_USM_AGENT",
    SG_IRUE_AUSF_AGENT:         "SG_IRUE_AUSF_AGENT",
    SG_IRUE_AUSF_CSL_AGENT:     "SG_IRUE_AUSF_CSL_AGENT",
    SG_ARIE_PCC_AGENT:          "SG_ARIE_PCC_AGENT",
    SG_IRUE_NRF_AGENT:          "SG_IRUE_NRF_AGENT",
    SG_ARIE_LMF_AGENT:          "SG_ARIE_LMF_AGENT",
    SG_SNET_PCF_SA_AGENT:       "SG_SNET_PCF_SA_AGENT",
    SG_ARIE_IOTGW_AGENT:        "SG_ARIE_IOTGW_AGENT",
    SG_ARIE_ePCF_HH_AGENT:      "SG_ARIE_ePCF_HH_AGENT",
    SG_ARIE_EMG_AGENT:          "SG_ARIE_EMG_AGENT",
    SG_SAME_VSM_CU_DIV_AGENT:   "SG_SAME_VSM_CU_DIV_AGENT",
    SG_ARIE_FNPS_AGENT:         "SG_ARIE_FNPS_AGENT",
    SG_SAME_USM_CU_5M_AGENT:    "SG_SAME_USM_CU_5M_AGENT",
    SG_SAME_USM_5M_AGENT:       "SG_SAME_USM_5M_AGENT",
    SG_SAME_USM_60M_AGENT:      "SG_SAME_USM_60M_AGENT",
    SG_LOCS_KPNS_AGENT:         "SG_LOCS_KPNS_AGENT",
    SG_LOCS_IPSMGW_AGENT:       "SG_LOCS_IPSMGW_AGENT",
    SG_LGE_ENM_COM_CELL_AGENT:  "SG_LGES_ENM_COM_CELL_AGENT",
    SG_LGE_ENM_COM_DU_AGENT:    "SG_LGES_ENM_COM_DU_AGENT",
    SG_ARIE_FNPSMP_AGENT:       "SG_ARIE_FNPSMP_AGENT",
    SG_LGE_ES_GET_AGENT:        "SG_LGE_ES_GET_AGENT",
    SG_LGE_ES_GET_NEW_AGENT:    "SG_LGE_ES_GET_NEW_AGENT",
    SG_ARIE_ESAN_AGENT:         "SG_ARIE_ESAN_AGENT",
    SG_ARIE_GMG_AGENT:          "SG_ARIE_GMG_AGENT",
    SG_ARIE_ERS_AGENT:          "SG_ARIE_ERS_AGENT",
    SG_ARIE_SSPF_AGENT:         "SG_ARIE_SSPF_AGENT",
    SG_IRUE_DRA_AGENT:          "SG_IRUE_DRA_AGENT",
    SG_IRUE_vIBCF_AGENT:        "SG_IRUE_vIBCF_AGENT",
    SG_BRGT_MRF_AGENT:          "SG_BRGT_MRF_AGENT",
    SG_ARIE_CCS_AGENT:          "SG_ARIE_CCS_AGENT",
    SG_ARIE_LTE_PCC_AGENT:      "SG_ARIE_LTE_PCC_AGENT",
    ALARM_CHG_ASCII_AGENT:      "ALARM_CHG_ASCII_AGENT",
}


# ─────────────────────────────────────────────
# AsUtil 클래스 (C++ static 메서드 → @staticmethod)
# ─────────────────────────────────────────────

class AsUtil:
    """
    C++: class AsUtil
    모든 메서드가 static → Python @staticmethod
    인스턴스화 불필요 (직접 AsUtil.메서드() 호출)
    """

    # ── Type → String 변환 ──────────────────

    @staticmethod
    def GetProcessTypeString(Type: int) -> str:
        return _PROCESS_TYPE_STR.get(Type, STR_UNKNOWN_TYPE)

    @staticmethod
    def GetProtocolTypeString(Type: int) -> str:
        return _PROTOCOL_TYPE_STR.get(Type, "UnKnown ProtoColType")

    @staticmethod
    def GetPortTypeString(Type: int) -> str:
        return _PORT_TYPE_STR.get(Type, "UnKnown PortType")

    @staticmethod
    def GetPortStatusTypeString(Type: int) -> str:
        _map = {
            PORT_CONNECTED:    "PORT_CONNECTED",
            PORT_NORMAL:       "PORT_NORMAL",
            PORT_DISCONNECTED: "PORT_DISCONNECTED",
            PORT_ELIMINATION:  "PORT_ELIMINATION",
        }
        return _map.get(Type, "Unknown PORT_STS_MODE Type")

    @staticmethod
    def GetStatusString(Status: int) -> str:
        return {START: "START", STOP: "STOP"}.get(Status, "Unknown Status")

    @staticmethod
    def GetRequestStatusString(Status: int) -> str:
        _map = {
            WAIT_NO:     "WAIT_NO",
            WAIT_START:  "WAIT_START",
            WAIT_STOP:   "WAIT_STOP",
            CREATE_DATA: "CREATE_DATA",
            UPDATE_DATA: "UPDATE_DATA",
            DELETE_DATA: "DELETE_DATA",
        }
        return _map.get(Status, "Unknown Status")

    @staticmethod
    def GetJunctionTypeString(Type: int) -> str:
        _map = {
            ASCII_J: "ASCII",
            Q3_J:    "Q3",
            SNMP_J:  "SNMP",
            CORBA_J: "CORBA",
        }
        return _map.get(Type, "Unknown junction type")

    @staticmethod
    def GetDataHandlerModeString(Mode: int) -> str:
        _map = {
            DB_LOAD_SQLLOADER: "DB_LOAD_SQLLOADER",
            DB_LOAD_OCI:       "DB_LOAD_OCI",
            SAVE_FILE:         "SAVE_FILE",
            BYPASS_SERVER:     "BYPASS_SERVER",
            BYPASS_CLIENT:     "BYPASS_CLIENT",
            SAVE_FILE2:        "SAVE_FILE2",
            SAVE_FILE3:        "SAVE_FILE3",
            SAVE_FILE_BC:      "SAVE_FILE_BC",
        }
        return _map.get(Mode, "Unknown Data Handler mode")

    @staticmethod
    def GetDataHandlerRunModeString(Type: int) -> str:
        return {0: "Normal", 1: "Alone"}.get(Type, "Normal")

    @staticmethod
    def GetLogCycleString(Type: int) -> str:
        return {0: ARG_LOG_DAY, 1: ARG_LOG_HOUR}.get(Type, ARG_LOG_DAY)

    # ── Enum → String (오버로드 대응: 타입별 메서드) ──

    @staticmethod
    def GetEnumTypeString_SCHEDULE(Type: SCHEDULE_TYPE) -> str:
        _map = {
            SCHEDULE_TYPE.SCH_RESERVE: "SCH_RESERVE",
            SCHEDULE_TYPE.SCH_LOOP:    "SCH_LOOP",
            SCHEDULE_TYPE.SCH_MONITOR: "SCH_MONITOR",
        }
        return _map.get(Type, "Unknown Enum Type")

    @staticmethod
    def GetEnumTypeString_RESPONSE_RESULT(Type: RESPONSE_RESULT_MODE) -> str:
        _map = {
            RESPONSE_RESULT_MODE.RESPONSE_NOT_YET:  "RESPONSE_NOT_YET",
            RESPONSE_RESULT_MODE.RESPONSE_CAPTURED: "RESPONSE_CAPTURED",
            RESPONSE_RESULT_MODE.RESPONSE_LOST:     "RESPONSE_LOST",
        }
        return _map.get(Type, "Unknown Enum Type")

    @staticmethod
    def GetEnumTypeString_RESULT(Type: RESULT_MODE) -> str:
        return {RESULT_MODE.FAIL: "FAIL", RESULT_MODE.SUCCEED: "SUCCEED"}.get(
            Type, "Unknown Enum Type")

    @staticmethod
    def GetEnumTypeString_LOG_CTL(Type: LOG_CTL_TYPE) -> str:
        return {LOG_CTL_TYPE.GET_LOG_INFO: "GET_LOG_INFO",
                LOG_CTL_TYPE.SET_LOG:      "SET_LOG"}.get(Type, "Unknown Enum Type")

    @staticmethod
    def GetEnumTypeString_MMC_TYPE(Type: AS_MMC_TYPE) -> str:
        _map = {
            AS_MMC_TYPE.FULL_CMD:   "FULL_CMD",
            AS_MMC_TYPE.CMD_ID:     "CMD_ID",
            AS_MMC_TYPE.CMD_SET_ID: "CMD_SET_ID",
            AS_MMC_TYPE.RE_ISSUE:   "RE_ISSUE",
        }
        return _map.get(Type, "Unknown Enum Type")

    @staticmethod
    def GetEnumTypeString_MMC_INTERFACE(Type: AS_MMC_INTERFACE) -> str:
        return {AS_MMC_INTERFACE.ASCII: "ASCII",
                AS_MMC_INTERFACE.Q3:    "Q3"}.get(Type, "Unknown Enum Type")

    @staticmethod
    def GetEnumTypeString_RESPONSE_MODE(Type: AS_MMC_RESPONSE_MODE) -> str:
        _map = {
            AS_MMC_RESPONSE_MODE.NO_RESPONSE:        "NO_RESPONSE",
            AS_MMC_RESPONSE_MODE.RESPONSE:           "RESPONSE",
            AS_MMC_RESPONSE_MODE.SAVE_AND_RESPONSE:  "SAVE_AND_RESPONSE",
            AS_MMC_RESPONSE_MODE.ONLY_SAVE_RESPONSE: "ONLY_SAVE_RESPONSE",
        }
        return _map.get(Type, "Unknown Enum Type")

    @staticmethod
    def GetEnumTypeString_COLLECT_MODE(Type: AS_MMC_COLLECT_MODE) -> str:
        return {AS_MMC_COLLECT_MODE.NO_RECOLLECT: "NO_RECOLLECT",
                AS_MMC_COLLECT_MODE.RECOLLECT:    "RECOLLECT"}.get(Type, "Unknown Enum Type")

    @staticmethod
    def GetEnumTypeString_RESULT_MODE(Type: AS_MMC_RESULT_MODE) -> str:
        _map = {
            AS_MMC_RESULT_MODE.R_ERROR:    "ERROR",
            AS_MMC_RESULT_MODE.R_CONTINUE: "CONTINUE",
            AS_MMC_RESULT_MODE.R_COMPLETE: "COMPLETE",
        }
        return _map.get(Type, "Unknown Enum Type")

    @staticmethod
    def GetEnumTypeString_PUBLISH_MODE(Type: AS_MMC_PUBLISH_MODE) -> str:
        _map = {
            AS_MMC_PUBLISH_MODE.NO_IMMEDIATE: "NO_IMMEDIATE",
            AS_MMC_PUBLISH_MODE.IMMEDIATE:    "IMMEDIATE",
            AS_MMC_PUBLISH_MODE.NOT_PUBLISH:  "NOT_PUBLISH",
        }
        return _map.get(Type, "Unknown Enum Type")

    @staticmethod
    def GetEnumTypeString_SEGFLAG(Type: AS_SEGFLAG) -> str:
        _map = {
            AS_SEGFLAG.NO_SEG:       "NO_SEG",
            AS_SEGFLAG.SEG_ING:      "SEG_ING",
            AS_SEGFLAG.SEG_END:      "SEG_END",
            AS_SEGFLAG.SEG_COMPLETE: "SEG_COMPLETE",
        }
        return _map.get(Type, "Unknown Enum Type")

    @staticmethod
    def GetEnumTypeString_SYNCDB(Type: SYNCDB_KIND) -> str:
        _map = {
            SYNCDB_KIND.UNDEFINDED_SYNC:    "UNDEFINDED_SYNC",
            SYNCDB_KIND.ALL_SYNC:           "ALL_SYNC",
            SYNCDB_KIND.ORB_SYNC:           "ORB_SYNC",
            SYNCDB_KIND.CMD_SYNC:           "CMD_SYNC",
            SYNCDB_KIND.RULE_SYNC:          "RULE_SYNC",
            SYNCDB_KIND.ETC_SYNC:           "ETC_SYNC",
            SYNCDB_KIND.SESSIONIDENT_SYNC:  "SESSIONIDENT_SYNC",
            SYNCDB_KIND.EVENTCONSUMER_SYNC: "EVENTCONSUMER_SYNC",
            SYNCDB_KIND.JUNCTION_SYNC:      "JUNCTION_SYNC",
        }
        return _map.get(Type, "Unknown SYNCDB_KIND type")

    @staticmethod
    def GetEnumTypeString_ACTION(Type: ACTION_TYPE) -> str:
        _map = {
            ACTION_TYPE.ACT_CREATE: "CREATE",
            ACTION_TYPE.ACT_MODIFY: "MODIFY",
            ACTION_TYPE.ACT_START:  "START",
            ACTION_TYPE.ACT_STOP:   "STOP",
            ACTION_TYPE.ACT_DELETE: "DELETE",
        }
        return _map.get(Type, "Unknown Enum Type")

    # ── 포트 정보 출력 ──────────────────────

    @staticmethod
    def CmdOpenPortDisplay(PortInfo: AS_CMD_OPEN_PORT_T) -> None:
        """C++: frSTD_OUT → print"""
        lines = [
            "== CmdOpenPort ==============================",
            f"             Id : {PortInfo.Id}",
            f"       Sequence : {PortInfo.Sequence}",
            f"        EquipId : {PortInfo.EquipId}",
            f"   AgentEquipId : {PortInfo.AgentEquipId}",
            f"       Consumer : {PortInfo.Consumer}",
            f"           Name : {PortInfo.Name}",
            f"    ConnectorId : {PortInfo.ConnectorId}",
            f"      IpAddress : {PortInfo.IpAddress}",
            f"         PortNo : {PortInfo.PortNo}",
            f"       PortPath : {PortInfo.PortPath}",
            f"         UserId : {PortInfo.UserId}",
            f"       Password : {PortInfo.Password}",
            f"   ProtocolType : {AsUtil.GetProtocolTypeString(PortInfo.ProtocolType)}",
            f"       PortType : {AsUtil.GetPortTypeString(PortInfo.PortType)} ({PortInfo.PortType})",
            f"        GatFlag : {PortInfo.GatFlag}",
            f"           DnId : {PortInfo.DnId}",
            f"CommandPortFlag : {PortInfo.CommandPortFlag}",
            "==============================================",
        ]
        print("\n".join(lines))

    @staticmethod
    def OpenPortInfoCmp(Info1: AS_CMD_OPEN_PORT_T,
                        Info2: AS_CMD_OPEN_PORT_T) -> bool:
        """두 AS_CMD_OPEN_PORT_T 구조체의 내용이 동일한지 비교"""
        return (
            Info1.EquipId        == Info2.EquipId        and
            Info1.Consumer       == Info2.Consumer        and
            Info1.ConnectorId    == Info2.ConnectorId     and
            Info1.IpAddress      == Info2.IpAddress       and
            Info1.PortNo         == Info2.PortNo          and
            Info1.PortPath       == Info2.PortPath        and
            Info1.UserId         == Info2.UserId          and
            Info1.Password       == Info2.Password        and
            Info1.AsciiHeader    == Info2.AsciiHeader     and
            Info1.ProtocolType   == Info2.ProtocolType    and
            Info1.PortType       == Info2.PortType        and
            Info1.GatFlag        == Info2.GatFlag         and
            Info1.CommandPortFlag== Info2.CommandPortFlag and
            Info1.DnId           == Info2.DnId
        )

    # ── 시스템 정보 ──────────────────────────

    @staticmethod
    def GetLocalIp() -> str:
        """로컬 IP 주소 반환 (C++: frUtilMisc::GetLocalIp)"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    @staticmethod
    def GetHostName() -> str:
        """호스트명 반환 (C++: gethostname)"""
        try:
            return socket.gethostname()
        except Exception:
            return ""

    @staticmethod
    def GetHomeDir() -> str:
        """HOME 환경변수 반환"""
        return os.environ.get("HOME", "")

    @staticmethod
    def GetUserName() -> str:
        """USER 환경변수 반환"""
        return os.environ.get("USER", "")

    # ── MMC 구조체 변환 ─────────────────────

    @staticmethod
    def ConvertMMC_OldToNew(OldMMCReq: AS_MMC_REQUEST_OLD_T,
                            NewMMCReq: AS_MMC_REQUEST_T) -> None:
        """
        AS_MMC_REQUEST_OLD_T → AS_MMC_REQUEST_T 필드 복사.
        C++: memcpy(parameters, ...) → deepcopy 로 대응.
        NewMMCReq 를 in-place 수정.
        """
        NewMMCReq.id           = OldMMCReq.id
        NewMMCReq.ne           = OldMMCReq.ne
        NewMMCReq.type         = OldMMCReq.type
        NewMMCReq.referenceId  = OldMMCReq.referenceId
        NewMMCReq.interfaces   = OldMMCReq.interfaces
        NewMMCReq.responseMode = OldMMCReq.responseMode
        NewMMCReq.publishMode  = OldMMCReq.publishMode
        NewMMCReq.collectMode  = OldMMCReq.collectMode
        NewMMCReq.mmc          = OldMMCReq.mmc
        NewMMCReq.userid       = OldMMCReq.userid
        NewMMCReq.display      = OldMMCReq.display
        NewMMCReq.cmdDelayTime = OldMMCReq.cmdDelayTime
        NewMMCReq.retryNo      = OldMMCReq.retryNo
        NewMMCReq.curRetryNo   = OldMMCReq.curRetryNo
        NewMMCReq.parameterNo  = OldMMCReq.parameterNo
        NewMMCReq.priority     = OldMMCReq.priority
        NewMMCReq.logMode      = OldMMCReq.logMode
        NewMMCReq.parameters   = deepcopy(OldMMCReq.parameters)

    # ── Sleep ────────────────────────────────

    @staticmethod
    def AsSleep(Useconds: int) -> None:
        """
        C++: frUtilMisc::Sleep2(Useconds) — 마이크로초 단위 슬립
        Python: time.sleep 은 초 단위이므로 변환
        """
        time.sleep(Useconds / 1_000_000)

    # ── 메모리 버퍼 관리 ────────────────────

    @staticmethod
    def ResizeMemory(cur_buf: bytearray, new_size: int) -> bytearray:
        """
        C++: ResizeMemory(char*& CurBuf, int& CurSize, int NewSize)
        Python: bytearray 새로 할당하여 반환
        (C++ 포인터 참조 갱신 → 반환값으로 처리)

        Usage:
            buf = AsUtil.ResizeMemory(buf, new_size)
        """
        if len(cur_buf) < new_size:
            logger.debug("Memory resizing: old(%d byte), new(%d byte)",
                         len(cur_buf), new_size)
            return bytearray(new_size)
        return cur_buf