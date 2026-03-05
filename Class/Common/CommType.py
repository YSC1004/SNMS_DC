"""
CommType.py - C++ CommType.h 변환
공통 상수, Enum, 데이터클래스 정의
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

# AsciiMmcType 상수 (AsciiMmcType.py 에서 import)
from Common.AsciiMmcType import (
    MMC_CMD_LEN, MMC_CMD_LEN_EX, MMC_VAL_LEN,
    EQUIP_ID_LEN, EVENT_ID_LEN, USER_ID_LEN, PASSWORD_LEN,
    IP_ADDRESS_LEN, MAX_MSG,
    AS_MMC_RESPONSE_MODE, AS_MMC_PUBLISH_MODE, AS_MMC_RESULT_MODE,
    AS_MMC_INTERFACE, AS_MMC_COLLECT_MODE,
    AS_MMC_PARAMETER_T,
)

# ── 기본 길이 상수 ─────────────────────────────────────────────────────
NAME_LEN            = 40
DATE_STRING_LEN     = 20    # "YYYY/MM/DD HH:MI:SS"
PATH_LEN            = 100
MAX_RESULT_LEN      = 2000
MAX_DESC_LEN        = 500
IP_ADDRESS_LEN_EX   = IP_ADDRESS_LEN

# ── MMC 명령 코드 ──────────────────────────────────────────────────────
MMC_GEN_REQ         = 1001
MMC_GEN_REQ_ACK     = 1002
MMC_GEN_RES         = 1011
MMC_GEN_RES_ACK     = 1012
MMC_PUB_REQ         = 1021
MMC_PUB_REQ_ACK     = 1022

# ── Enum ───────────────────────────────────────────────────────────────
class ScheduleType(IntEnum):
    SCH_RESERVE = 0
    SCH_LOOP    = 1
    SCH_MONITOR = 2

class ResponseResultMode(IntEnum):
    RESPONSE_NOT_YET  = 0
    RESPONSE_CAPTURED = 1
    RESPONSE_LOST     = 2

class IdStringType(IntEnum):
    ID_STRING_MMC      = 0
    ID_STRING_IDSTRING = 1

class ActionType(IntEnum):
    ACT_CREATE = 0
    ACT_MODIFY = 1
    ACT_START  = 2
    ACT_STOP   = 3
    ACT_DELETE = 4

class ResultMode(IntEnum):
    FAIL    = 0
    SUCCEED = 1

class LogCtlType(IntEnum):
    GET_LOG_INFO = 0
    SET_LOG      = 1

class AsStatus(IntEnum):
    LOG_ADD = 0
    LOG_DEL = 1

class SegFlag(IntEnum):
    NO_SEG      = 0
    SEG_ING     = 1
    SEG_END     = 2
    SEG_COMPLETE= 3

class MmcResType(IntEnum):
    MMC_RES_NOTYET   = 0
    MMC_RES_CAPTURED = 1
    MMC_RES_LOST     = 2
    MMC_RES_DONTCARE = 3

class SyncdbKind(IntEnum):
    UNDEFINDED_SYNC    = -1
    ALL_SYNC           = 1
    ORB_SYNC           = 2
    CMD_SYNC           = 3
    RULE_SYNC          = 4
    ETC_SYNC           = 5
    SESSIONIDENT_SYNC  = 6
    EVENTCONSUMER_SYNC = 7
    JUNCTION_SYNC      = 8

# ── MMC 관련 상수 ──────────────────────────────────────────────────────
MMC_GEN_COMMAND_MAX = 3

CMD_MMC_PUBLISH_REQ      = 1500
CMD_MMC_PUBLISH_ACK      = 1501
CMD_MMC_PUBLISH_RES      = 1502
MMC_RESPONSE_DATA_REQ    = 1503
MMC_RESPONSE_DATA        = 1504

# ── NETFINDER ──────────────────────────────────────────────────────────
MAX_RESULT_SIZE     = 4068
NETFINDER_REQ       = 901
NETFINDER_REV       = 902
CONNECTOR_HIST_INFO_SIZE = MAX_MSG - 32 - 32 - 12 - 12 - 64 - 16

# ── CMD 상수 ───────────────────────────────────────────────────────────
CMD_ALIVE                   = 2001
CMD_ALIVE_ACK               = 2002
CMD_ALIVE_RECEIVE           = 2003
CMD_ALIVE_SEND              = 2004
CMD_OPEN_PORT               = 2011
CMD_OPEN_PORT_ACK           = 2012
CONNECTOR_PORT_INFO_REQ     = 2013
DATAHANDLER_PORT_INFO_REQ   = 2014
CMD_CLOSE_PORT              = 2021
CMD_CLOSE_PORT_ACK          = 2022
CMD_REOPEN_PORT             = 2031
CMD_REOPEN_PORT_ACK         = 2032
CMD_LOG_STATUS_CHANGE       = 2041
AS_LOG_INFO                 = 2043
CMD_SET_LOG                 = 2051
CMD_SET_LOG_ACK             = 2052
CMD_INIT_CFG                = 2061
CMD_INIT_CFG_ACK            = 2062
CMD_PS_STS                  = 2081
CMD_PS_STS_ACK              = 2082
ASCII_ERROR_MSG             = 2090
CMD_PROC_INIT               = 2101

# ── PROTOCOL_TYPE (1301~1400, 1601~1808) ──────────────────────────────
ASCII_AGENT             = 1301
ASCII_NAIM              = 1302
GAT                     = 1303
PARSER_LISTEN           = 1305
PARSER_CONNECT          = 1306
ROUTER_LISTEN           = 1307
ROUTER_CONNECT          = 1308
DATAHANDLER_LISTEN      = 1309
DATAHANDLER_CONNECT     = 1310
DATAROUTER_LISTEN       = 1311
DATAROUTER_CONNECT      = 1312
MANAGER_CONNECT         = 1313
SS1XBSS                 = 1314
SS2GBSS                 = 1315
TER_SER                 = 1316
JOBMONITOR_CONNECT      = 1319
OMCR                    = 1320
LUCENT                  = 1321
FREENET                 = 1322
VMS                     = 1323
SSHLR                   = 1324
TEMIP                   = 1325
NEC                     = 1326
Q3_AGENT                = 1327
TEMIP_DATA_AGENT        = 1327
NET_SNMP                = 1328
NET_CORBA               = 1329
ECI                     = 1341
COP_LUCENT              = 1342
COP_NORTEL              = 1343
COP_WDCS                = 1344
COP_SMUX                = 1345
EMS_AGENT               = 1346
SPARE_PROTO1            = 1347
SPARE_PROTO2            = 1348
SPARE_PROTO3            = 1349
IPGS_AGENT              = 1350
WDCS_AGENT              = 1351
FE1_AGENT               = 1352
DOTS_AGENT              = 1353
STP_AGENT               = 1354
LGEVDOBSS               = 1355
ACTL_AGENT              = 1356
LGWDCS_AGENT            = 1357
SS3GMGW_AGENT           = 1358
SS3GMSV_AGENT           = 1359
SS3GBSS_AGENT           = 1360
LG3GBSS_AGENT           = 1361
SS3GSGSN_AGENT          = 1362
ALLGATE                 = 1363
MCODE_SS1X_AGENT        = 1364
MCODE_SS2G_AGENT        = 1365
MCODE_SS3G_AGENT        = 1366
MCODE_LG3G_AGENT        = 1367
MNMUX_AGENT             = 1368
SG_AGENT                = 1369
ALCATEL_AGENT           = 1370
LG_MSV_TMA_AGENT        = 1371
REMS_R5GATE_AGENT       = 1372
AROMA_AGENT             = 1373
REMS_SMS_AGENT          = 1374
MOGABI_RFST_AGENT       = 1375
MOGABI_RFSI_AGENT       = 1376
MOGABI_RFMT_AGENT       = 1377
REMS_R5GATE_MMC_AGENT   = 1379
KTFRIEND_AGENT          = 1381
SMCI_IF_AGENT           = 1382
REMS_WAVE_AGENT         = 1383
REMS_SKTI_AGENT         = 1384
SIM_TT_AGENT            = 1385
NF3000_AGENT            = 1386
PREFIX_SG_NGRD_AGENT    = 1387
PREFIX_SG_INNET_AGENT   = 1388
PREFIX_MSV_SS_3G_AGENT  = 1389
WIBRO_PSG_AGENT         = 1390
WIBRO_CALL_TRACE_AGENT  = 1391
WIBRO_W1_AGENT          = 1392
WIBRO_W2_AGENT          = 1393
SS3GGGSN_AGENT          = 1394
WIBRO_RF_AGENT          = 1395
WREMS_SNMP_AGENT        = 1396
WIBRO_L2_AGENT          = 1397
WIBRO_AAA_AGENT         = 1398
WIBRO_WTAS_AGENT        = 1399
WIBRO_WTAS_V2_AGENT     = 1401
WIBRO_W1_SOAP_AGENT     = 1601
WIBRO_W2_SOAP_AGENT     = 1602
SSIMSSPR_AGENT          = 1603
SS3GGGSNPCC_AGENT       = 1604
SSIMSMRF_AGENT          = 1605
WIBRO_W2_POS_AGENT      = 1606
SSIMSPCRF_AGENT         = 1607
LG3GBSS15MIN_AGENT      = 1608
WIBRO_NETIS_AGENT       = 1609
WIFI_SNMP_AGENT         = 1610
WIFI_PING_AGENT         = 1611
WIFI_WIMS_AGENT         = 1612
WIBRO_PDG_AGENT         = 1613
WIFI_BAS_AGENT          = 1614
AROMA_PLUS_AGENT        = 1615
WIBRO_SMART_I_AGENT     = 1616
WIBRO_WIFI_EGG_AGENT    = 1617
WIBRO_PSG_SOAP          = 1618
SMARTI_CM_AGENT         = 1619
STP_SECU_AGENT          = 1620
GNOC_SMS_AGENT          = 1621
LG3GBSSMULTI_AGENT      = 1622
LG3GBSSMULTI_FM_AGENT   = 1623
WIFI_WIMS_FTP_AGENT     = 1624
WIFI_BAS_FTP_AGENT      = 1625
LG3GBSS15MMULTI_AGENT   = 1626
LGE3GBSSCCC15M_AGENT    = 1627
SSWGS_AGENT             = 1628
LGE3GBSSFM_AGENT        = 1629
CCC_TRAP_AGENT          = 1630
LGE3GBSSCCCCM_AGENT     = 1631
PREFIX_SG_NGRD2_AGENT   = 1632
SS3GSGSN2_AGENT         = 1633
SS3GMSVMGW2_AGENT       = 1634
SS3GMGW2_AGENT          = 1635
LGE3GBSSCCCMULTIPEG_AGENT = 1636
SSF3000_AGENT           = 1637
CCC_SNMP_AGENT          = 1638
NEW_SG_AGENT            = 1639
SS3GMSVMGW2_ASCII_AGENT = 1640
SS3GSGSN2_ASCII_AGENT   = 1641
SSWGS_ASCII_AGENT       = 1642
MMS_CMD_AGENT           = 1643
LGE3GBSSCCCRBS_AGENT    = 1644
LGE3GBSSCCCCM2_AGENT    = 1645
LG3GBSSCMNBR_AGENT      = 1646
LTE_MME_SS_AGENT        = 1647
LTE_ENB_SS_AGENT        = 1648
LTE_PGW_YW_AGENT        = 1649
LTE_SGW_YW_AGENT        = 1650
SS3GBSS_ASCII_AGENT     = 1651
LTE_ENB_LGE_15M_AGENT   = 1652
LTE_ENB_NSN_AGENT       = 1653
LTE_ENB_NSN_CM_AGENT    = 1654
LTE_ENB_LGE_MPEG_AGENT  = 1655
MERQ_FEMTO_AGENT        = 1656
LTE_ENB_NSN2_AGENT      = 1657
WIFI_NEW_WIMS_FTP_AGENT = 1658
LTE_MME_SS_RE_AGENT     = 1659
LTE_ENB_SS_RE_AGENT     = 1660
LTE_ENB_LGE_15M_RE_AGENT= 1661
SS3GMSVMGW2_RE_AGENT    = 1662
SS3GSGSN2_RE_AGENT      = 1663
SS3GBSS_RE_AGENT        = 1664
LGE3GBSSCCC15M_RE_AGENT = 1665
LTE_ENB_NSN_5M_AGENT    = 1666
MERQ_FEMTO_NMS_AGENT    = 1667
LTE_ENB_LGE_5M_KC_AGENT = 1668
LTE_FEMTO_YW_AGENT      = 1669
LTE_NSN_SP_CM_AGENT     = 1670
LTE_FEMTO_CM_AGENT      = 1671
LTE_FEMTO_INO_AGENT     = 1672
P_ROUTER_SNMP_AGENT     = 1673
SM_SERVER_AGENT         = 1674
LTE_MRF_TIQ_AGENT       = 1675
LTE_MME_MULTI_SS_AGENT  = 1676
LTE_IMG_LOCS_AGENT      = 1677
LTE_FEMTO_DWTI_AGENT    = 1678
LTE_FEMTO_JUKO_AGENT    = 1679
LTE_PCRF_TEK_AGENT      = 1680
LTE_DRA_IRUE_AGENT      = 1681
IMS_CSCF_SS_AGENT       = 1682
LTE_ENB_LGE_15M_ENIQ_AGENT = 1683
LTE_TASDB_DINN_AGENT    = 1684
WIBRO_DAY_AAA_AGENT     = 1685
LTE_ESMLC_IRUE_AGENT    = 1686
MIDAS_KSMS_AGENT        = 1687
KSMS_AGENT              = 1688
LTE_SGW_SS_AGENT        = 1689
IMS_CSCF_ACRO_AGENT     = 1690
ASCII_MCODE_AGENT       = 1691
LTE_PGW_SS_AGENT        = 1692
LTE_SGWPGW_SS_AGENT     = 1693
ASCII_LGE3G_MCODE_AGENT = 1694
LTE_NBMSC_YOOE_AGENT    = 1695
LTE_MBMS_SS_AGENT       = 1696
LTE_HOME_FEMTO_INO_AGENT= 1697
LTE_ENB_LGE_CM_AGENT    = 1698
IMS_IBCF_ACRO_AGENT     = 1699
FEP_YOO_AGENT           = 1700
LTE_TAS_DINN_AGENT      = 1701
LTE_TAS_BRGT_AGENT      = 1702
LTE_PCRFMGW_TEK_AGENT   = 1703
LTE_TSUP_DINN_AGENT     = 1704
LTE_PGW_TEST_AGENT      = 1705
RCCS_AGENT              = 1706
MME_MBMS_MULTI_AGENT    = 1707
LTE_PCRF_MULTI_AGENT    = 1708
PUBS_AR_AGENT           = 1709
LTE_ENB_LGE_CM1_AGENT   = 1710
MAGW_IRU_AGENT          = 1711
TEST_AGENT              = 1712
PLAS_ARIE_AGENT         = 1713
LTAS_AGENT              = 1714
LTE_ENB_LGE_5M_AGENT    = 1715
LTE_DEA_IRUE_AGENT      = 1716
LTE_HSS_IRUE_AGENT      = 1717
LTE_MRF_IRUE_AGENT      = 1718
LTE_SMSC_LOCS_AGENT     = 1719
LTE_MMSC_LOCS_AGENT     = 1720
LTE_IPLS_LOCS_AGENT     = 1721
LTE_UMC_IRUE_AGENT      = 1722
LTE_MGCF_IPGO_AGENT     = 1723
LTE_MGW_IPGO_AGENT      = 1724
FEMTO_PING_AGENT        = 1727
TRAP_AGENT              = 1728
SNMP_AGENT              = 1729
IMS_IBCF_IRUE_AGENT     = 1730
LTE_HSS_SDS_AGENT       = 1731
LTE_CSC_SDS_AGENT       = 1732
SFTP_TEST_AGENT         = 1733
IMS_IBCF_NABLE_AGENT    = 1734
REC_XCURE_AGENT         = 1735
# 5GNMS (2019~)
LTE_SAME_CSL_AGENT          = 1736
SG_SAME_AMF_AGENT           = 1737
SG_IRUE_UDM_AGENT           = 1738
SG_IRUE_UDR_AGENT           = 1739
SG_SAME_CSCF_AGENT          = 1740
SG_CICS_AMF_AGENT           = 1741
SG_CICS_SMF_AGENT           = 1742
SG_CICS_UPF_AGENT           = 1743
SG_SAME_CSL_AGENT           = 1744
SG_LGES_ENM_15M_AGENT       = 1745
SG_SAME_VSM_AGENT           = 1746
SG_NSNN_NETACT_AGENT        = 1747
SG_NSNN_NETACT_CM_AGENT     = 1748
SG_ARIE_ePCF_AGENT          = 1749
SG_SNET_PCF_AGENT           = 1750
SG_LGE_ENM_CM_CELL_AGENT    = 1751
SG_LGE_ENM_CM_SITE_AGENT    = 1752
SG_ARIE_SMLC_AGENT          = 1753
SG_IRUE_SMLC_AGENT          = 1754
SG_IRUE_VTAS_AGENT          = 1755
SG_SAME_VSM_5M_AGENT        = 1756
SG_SAME_VSM_15M_AGENT       = 1757
SG_NSNN_NETACT_5M_AGENT     = 1758
SG_VSM_SAME_CM_DU_AGENT     = 1759
SG_NSNN_NETACT_CM2_AGENT    = 1760
SG_SAME_VSM_CU_5M_AGENT     = 1761
SG_ARIE_DQE_AGENT           = 1762
SG_IRUE_iPgw_AGENT          = 1763
SG_LGES_ENM_15M_GZ_AGENT    = 1764
SG_SAME_AMF_CSL_AGENT       = 1765
SG_IRUE_UDAF_AGENT          = 1766
SG_SAME_USM_AGENT           = 1767
SG_IRUE_AUSF_AGENT          = 1768
SG_ARIE_PCC_AGENT           = 1769
SG_SAME_VSM_5M_DIV_AGENT    = 1770
SG_VSM_SAME_CM_CU_AGENT     = 1771
SG_IRUE_NRF_AGENT           = 1772
SG_ARIE_LMF_AGENT           = 1773
SG_IRUE_AUSF_CSL_AGENT      = 1774
SG_SNET_PCF_SA_AGENT        = 1775
SG_ARIE_IOTGW_AGENT         = 1776
SG_ARIE_ePCF_HH_AGENT       = 1777
SG_ARIE_EMG_AGENT           = 1778
SG_SAME_VSM_CU_DIV_AGENT    = 1779
SG_ARIE_FNPS_AGENT          = 1780
SG_SAME_USM_CU_5M_AGENT     = 1781
SG_SAME_USM_5M_AGENT        = 1782
SG_SAME_USM_60M_AGENT       = 1783
SG_LOCS_KPNS_AGENT          = 1784
SG_LOCS_IPSMGW_AGENT        = 1785
SG_LGE_ENM_COM_CELL_AGENT   = 1786
SG_ARIE_FNPSMP_AGENT        = 1787
SG_VSM_SAME_CM_AU_AGENT     = 1788
SG_LGE_ENM_COM_DU_AGENT     = 1789
SG_LGE_ES_GET_AGENT         = 1790
SG_ARIE_ESAN_AGENT          = 1791
SG_ARIE_GMG_AGENT           = 1792
SG_ARIE_SSPF_AGENT          = 1793
SG_IRUE_DRA_AGENT           = 1794
SG_BRGT_MRF_AGENT           = 1795
SG_LGE_ES_GET_NEW_AGENT     = 1796
SG_LGES_ENM_15M_GZ_PF_AGENT = 1797
SG_ARIE_CCS_AGENT           = 1798
SG_CICS_UPF2_AGENT          = 1799
ALARM_CHG_ASCII_AGENT       = 1800
SG_LGES_ENM_15M_GZ_DIV_AGENT= 1801
SG_SNET_PCRF_AGENT          = 1802
SG_LGES_ENM_60M_GZ_AGENT    = 1803
SG_IRUE_vIBCF_AGENT         = 1804
SG_ARIE_ERS_AGENT           = 1805
SG_USM_SAME_CM_DU30_AGENT   = 1806
SG_ARIE_LTE_PCC_AGENT       = 1807
SG_LGES_ENM_60M_GZ_DIV_AGENT= 1808

# ── PORT_TYPE (1401~1561) ──────────────────────────────────────────────
UNDEFINED               = -1
FM                      = 1401
TSPRT                   = 1402
LUCENT_ECP_FM           = 1404
PM1                     = 1405
LUCENT_DCS_FM           = 1406
PM2                     = 1407
CM                      = 1410
CMD                     = 1412
GATPRT                  = 1415
GATCRT                  = 1416
REVISE                  = 1417
VMS_SMS_HOURLY          = 1419
VMS_SMS_DAILY           = 1420
VMS_USER_DAILY          = 1421
VMS_TG_HOURLY           = 1422
SNMP_IF                 = 1423
SNMP_PING               = 1424
LUCENT_ECP_CMD          = 1426
LUCENT_DCS_CMD          = 1427
CORBA_IF                = 1428
LG3GBSS_CM_CMD          = 1429
F3000                   = 1430
LGXHOUR                 = 1431
SG_FM                   = 1432
NF3000                  = 1433
PREFIX                  = 1434
PSG_CDR                 = 1435
WIBRO_F3000             = 1436
WAVE1_CALL_TRACE        = 1437
WAVE2_CALL_TRACE        = 1438
WIBRO_FTP_LOG           = 1439
PCC                     = 1440
TM                      = 1441
TMA                     = 1442
WIBRO_NEW_AAA_RECOL     = 1443
WIBRO_DAY_AAA_RECOL     = 1444
WIBRO_DAY_AAA           = 1445
NESPOT_DAY_AAA          = 1446
WIFI_DAY_AAA            = 1447
BAS_DAY_AAA             = 1448
WIRED_DAY_AAA           = 1449
SPARE1                  = 1450
VMS_SMS_5MIN            = 1455
VMS_GW_HOURLY           = 1456
VMS_SUBCOUNT_HOURLY     = 1457
BC2G_PM1                = 1458
BC1X_PM1                = 1459
BCEV_PM1                = 1460
REMS_R5GATE             = 1461
REMS_SMS                = 1462
MOGABI_RFST             = 1463
MOGABI_RFSI             = 1464
MOGABI_RFMT             = 1465
MOGABI_RFSM             = 1466
REMS_R5GATE_MMC         = 1467
REMS_WAVE               = 1468
REMS_SKTI               = 1469
WIBRO_RF                = 1470
WIBRO_PDG_RECOL         = 1471
CM2                     = 1481
CMD2                    = 1482
WIBRO_NETIS             = 1483
SSF3000                 = 1484
TEST_TM                 = 1485
TM_NOTI                 = 1486
CSL                     = 1487
LTAS_LOG_KCC_R_APP          = 1548
LTAS_LOG_KCC_VoLTE          = 1549
LTAS_LOADER_LOG_KCC_R_APP   = 1558
LTAS_LOADER_LOG_KCC_VoLTE   = 1559
LTAS_LOADER_LOG_KCC_NEW_VoLTE = 1551
LTAS_LOG_KCC_NEW_VoLTE      = 1552
LTAS_LOG_KCC_APP            = 1546
LTAS_LOG_CALL_FTP           = 1547
LTAS_LOADER_LOG_KCC_APP     = 1556
LTAS_LOADER_LOG_CALL_FTP    = 1557
LTAS_LOADER_LOG_CTQ_UL      = 1560
LTAS_LOG_CTQ_UL             = 1561

# ── 기타 상수 ──────────────────────────────────────────────────────────
UNIX_DATAROUTER_LISTEN_PREFIX   = "/DATAROUTER_LISTEN_"
LUCENT_ECP_CMD_HEADER           = "ECP:"
LUCENT_DCS_CMD_HEADER           = "DCS:"

PORT_CONNECTED      = 1
PORT_NORMAL         = 2
PORT_DISCONNECTED   = 3
PORT_ELIMINATION    = 4

START   = 1
STOP    = 2

WAIT_NO     = 1
WAIT_START  = 2
WAIT_STOP   = 3
CREATE_DATA = 4
UPDATE_DATA = 5
DELETE_DATA = 6

PORT_STATUS_INFO    = 2901
PS_TEXT_LEN         = 512

PROCESS_STATUS_LIST_MAX = 20

INFO_ERROR      = 3011
INFO_ERROR_ACK  = 3012

INFO_SESSION_NAME       = 4000
NOT_ASSIGN              = 4001
SESSION_REPORTING       = 1003
CONNECTION_PORT_INFO    = 1005
PARSER_INTI_END         = 1006
ROUTER_PORT_INFO        = 1007

AS_PARSED_DATA          = 5001
PARSED_DATA_KEY_SIZE    = 60
MAX_RAW_MSG             = MAX_MSG - 4 - EQUIP_ID_LEN - EQUIP_ID_LEN - 4 - 4 - 2
PARSED_DATA_SIZE        = MAX_MSG - EQUIP_ID_LEN - EVENT_ID_LEN - EVENT_ID_LEN - MMC_CMD_LEN - (4 + 2 * 5)
PARSED_DATA_SEG_BLK_SIZE= PARSED_DATA_SIZE - PARSED_DATA_KEY_SIZE

MMC_LOG = 6001

# Session Identify
ASCII_SERVER            = 1200
ASCII_MANAGER           = 1201
ASCII_PARSER            = 1202
ASCII_CONNECTOR         = 1203
ASCII_DATA_HANDLER      = 1204
ASCII_MMC_GENERATOR     = 1205
ASCII_MMC_SCHEDULER     = 1206
ASCII_JOB_MONITOR       = 1207
GUI_RULE_EDITOR         = 1208
GUI_ASCII_CONFIG_INFO   = 1209
GUI_ASCII_STATUS_INFO   = 1210
ASCII_DATA_ROUTER       = 1211
ASCII_ROUTER            = 1212
ASCII_RULE_DOWNLOADER   = 1213
GUI_COMMAND_INFO        = 1214
ASCII_LOG_ROUTER        = 1215
NETFINDER_SESSION       = 1216
SNMP_CMD_SERVER         = 1217
SNMP_EVENT_SERVER       = 1218
SNMP_IP_POLLER          = 1219
CORBA_CMD_SERVER        = 1220
CORBA_EVENT_SERVER      = 1221
CORBA_IP_POLLER         = 1222
ORB_SCHEDULER           = 1223
ORB_DC_MANAGER          = 1224
ORB_GW_CMD_SERVER       = 1225
ORB_GW_EVENT_SERVER     = 1226
ASCII_SUB_PROCESS       = 1227
ASCII_CM_CMD            = 1228
SOAP_EMS_AGENT          = 1229
SNMP_SWITCH_CMD         = 1230
SNMP_ROIP_CMD           = 1231
SNMP_UPS_CMD            = 1232
TEST_PROCESS            = 1233
SG_ASCII_CMD_NMS        = 1235
SG_ASCII_CMD_OPER       = 1236
HTTP_AGENT_CMD          = 1237

CMD_ALIVE_CHECK             = 3000
PROC_INIT_END               = 3001
MANAGER_INIT_END            = 3002
MMC_CMD_RESULT              = 3003
PROC_CONTROL                = 3008
SESSION_CONTROL             = 3013
CONNECTOR_DATA              = 3004
CMD_PROC_TERMINATE          = 3100
PROC_TERMINATE_WAIT         = 3101
PROC_TERMINATE_WAIT_TIMEOUT = 20

MAX_ERR_MSG_BUF             = 32768
ACK_TIME_OUT                = 30
MMC_RESULT_TIMEOUT          = 30
NE_CONNECTION_TIME          = 3200
NE_CONNECTION_TIMEOUT       = 30
MANAGER_CONNECTION_TIME     = 3202
MANAGER_CONNECTION_TIMEOUT  = 5

PROCESS_INFO                = 3300
PROCESS_INFO_LIST           = 3301
PROCESS_INFO_SEND_TIME      = 3302
PROCESS_INFO_SEND_TIMEOUT   = 60

ORDER_KILL                  = 3400
MMCQUEUE_GABAGE_CLEAR       = 4101
CMD_PARSING_RULE_COPY       = 4102
CMD_PARSING_RULE_CHANGE     = 4103
CMD_CONNECTOR_DESC_CHANGE   = 4104

CMD_RESPONSE_TYPE_MSG_IDENT = 0
CMD_RESPONSE_TYPE_MSG_ID    = 1

# GUI Comm
ASCII_J     = 0
Q3_J        = 1
SNMP_J      = 2
CORBA_J     = 3

DB_LOAD_SQLLOADER   = 0
DB_LOAD_OCI         = 1
SAVE_FILE           = 2
BYPASS_SERVER       = 3
BYPASS_CLIENT       = 4
SAVE_FILE2          = 5
SAVE_FILE3          = 6
SAVE_FILE_BC        = 7

AS_MANAGER_INFO             = 11019
AS_CONNECTOR_INFO           = 11010
AS_CONNECTION_INFO          = 11011
AS_PROCESS_INFO             = 11012
AS_DATA_HANDLER_INFO        = 11013
AS_CONNECTION_INFO_LIST     = 11014
AS_COMMAND_AUTHORITY_INFO   = 11015
AS_SERVER_INFO              = 11016
AS_DB_SYNC_KIND             = 11017
AS_DB_SYNC_INFO_LIST        = 11018
AS_SUB_PROC_INFO            = 11020

CONNECTOR_MODIFY            = 11101
CONNECTOR_MODIFY_ACK        = 11102
MANAGER_MODIFY              = 11103
MANAGER_MODIFY_ACK          = 11104
CONNECTION_MODIFY           = 11105
CONNECTION_MODIFY_ACK       = 11106
DATAHANDLER_MODIFY          = 11107
DATAHANDLER_MODIFY_ACK      = 11108
CONNECTION_LIST_MODIFY      = 11109
CONNECTION_LIST_MODIFY_ACK  = 11110
COMMAND_AUTHORITY_MODIFY    = 11111
COMMAND_AUTHORITY_MODIFY_ACK= 11112
SUB_PROC_MODIFY             = 11113
SUB_PROC_MODIFY_ACK         = 11114

INIT_INFO_START             = 11201
INIT_INFO_END               = 11202
AS_SOCKET_STATUS_REQ        = 11203
AS_SOCKET_STATUS_RES        = 11204
FR_SOCKET_STATUS_REQ        = 11205
FR_SOCKET_STATUS_RES        = 11206
FR_SOCKET_SHUTDOWN_REQ      = 11207
FR_SOCKET_SHUTDOWN_RES      = 11208
FR_SOCKET_CHECK_REQ         = 11209
FR_SOCKET_CHECK_RES         = 11210
AS_DB_SYNC_INFO_REQ         = 11211
AS_DB_SYNC_INFO_REQ_ACK     = 11212
AS_DATA_HANDLER_INIT        = 11213
AS_DATA_ROUTING_INIT        = 11214
AS_SYSTEM_INFO              = 11301
AS_SESSION_CFG              = 11302

INFO_NO_SEG = 1
INFO_START  = 2
INFO_ING    = 3
INFO_END    = 4

CMD_PARSING_RULE_DOWN       = 12001
CMD_PARSING_RULE_DOWN_ACK   = 12002
CMD_MAPPING_RULE_DOWN       = 12003
CMD_MAPPING_RULE_DOWN_ACK   = 12004
CMD_COMMAND_RULE_DOWN       = 12005
CMD_COMMAND_RULE_DOWN_ACK   = 12006
CMD_SCHEDULER_RULE_DOWN     = 12007
CMD_SCHEDULER_RULE_DOWN_ACK = 12008
TAIL_RAW_DATA_REQ           = 12009
TAIL_LOG_DATA_REQ           = 12101
TAIL_LOG_DATA_RES           = 12102
TAIL_LOG_DATA               = 12103
TAIL_HOT_DATA_REQ           = 12111
TAIL_HOT_DATA_RES           = 12112
TAIL_HOT_DATA               = 12113
TAIL_HOT_DATA_CHG           = 12114

MAX_DB_SYNC_INFO_CNT        = 50
MAX_SOCKET_INFO_CNT         = 25

# ARG 문자열 상수
ARG_NAME                = "-name"
ARG_SVR_SOCKET_PATH     = "-svrpath"
ARG_SVR_IP              = "-svrip"
ARG_SVR_PORT            = "-svrport"
ARG_MANAGER_SOCKET_PATH = "-managersocketpath"
ARG_DB_USER             = "-dbuser"
ARG_DB_PASSWD           = "-dbpasswd"
ARG_DB_TNS              = "-dbtns"
ARG_ACT_DB_USER         = "-actdbuser"
ARG_ACT_DB_PASSWD       = "-actdbpasswd"
ARG_ACT_DB_TNS          = "-actdbtns"
ARG_RULEID              = "-ruleid"
ARG_CMD_IDENT_TYPE      = "-cmdidenttype"
ARG_DELAY_TIME          = "-delaytime"
ARG_CMD_RESPONSE_TYPE   = "-cmdrespontype"
ARG_NET_FINDER_PORT     = "-netfinderport"
ARG_PORT_NO             = "-portno"
ARG_TYPES               = "-type"
ARG_SVR_ACTIVE          = "active"
ARG_SVR_STANDBY         = "standby"
ARG_PROC_ID             = "-procid"
ARG_LOG_CYCLE           = "-logcycle"
ARG_LOG_DAY             = "DAY"
ARG_LOG_HOUR            = "HOUR"

STR_UNKNOWN_TYPE = "Unknown Type"

# ── 데이터클래스 ───────────────────────────────────────────────────────

@dataclass
class AsMmcGenCommand:
    """AS_MMC_GEN_COMMAND_T"""
    gen_id:        int = 0
    command_id:    int = 0
    command_set_id:int = 0
    result_mode:   ResultMode = ResultMode.FAIL
    mmc:           str = ""
    key:           str = ""
    id_string:     str = ""

@dataclass
class AsMmcGenResult:
    """AS_MMC_GEN_RESULT_T"""
    id:           int = 0
    ne:           str = ""
    response_mode: Any = None   # AS_MMC_RESPONSE_MODE
    publish_mode:  Any = None   # AS_MMC_PUBLISH_MODE
    result_mode:   Any = None   # AS_MMC_RESULT_MODE
    command_no:   int = 0
    commands:     list = field(default_factory=list)  # list[AsMmcGenCommand], max MMC_GEN_COMMAND_MAX
    err_msg:      str = ""
    cmd_delay_time:int= 0

@dataclass
class AsMmcPublish:
    """AS_MMC_PUBLISH_T"""
    id:            int = 0
    ne:            str = ""
    mmc:           str = ""
    id_string:     str = ""
    key:           str = ""
    response_mode: Any = None
    publish_mode:  Any = None
    cmd_delay_time:int = 0

@dataclass
class PkFinderReq:
    """PK_FinderReq"""
    ne_id:          str = ""
    ne_type:        str = ""
    start_time:     str = ""
    end_time:       str = ""
    key_word:       str = ""
    hostname:       str = ""
    conn_hist_info: str = ""

@dataclass
class PkResultMsg:
    """PK_ResultMsg"""
    find_result: int = 0
    tmpl_no:     int = 0
    seg_flag:    int = 0
    seg_no:      int = 0
    msg_size:    int = 0
    result_msg:  str = ""

@dataclass
class AsConnectorPortInfoReq:
    """AS_CONNECTOR_PORT_INFO_REQ_T"""
    connector_id: str = ""

@dataclass
class AsCmdOpenPort:
    """AS_CMD_OPEN_PORT_T"""
    id:               int = 0
    sequence:         int = 0
    equip_id:         str = ""
    agent_equip_id:   str = ""
    consumer:         str = ""
    name:             str = ""
    connector_id:     str = ""
    ip_address:       str = ""
    port_no:          int = 0
    port_path:        str = ""
    user_id:          str = ""
    password:         str = ""
    ascii_header:     str = ""
    protocol_type:    int = 0
    port_type:        int = 0
    gat_flag:         int = 0
    command_port_flag:int = 0
    dn_id:            str = ""

@dataclass
class AsCmdLogControl:
    """AS_CMD_LOG_CONTROL_T"""
    id:           int = 0
    process_type: int = 0
    type:         LogCtlType = LogCtlType.GET_LOG_INFO
    manager_id:   str = ""
    process_id:   str = ""
    package:      str = ""
    feature:      str = ""
    level:        int = 0

@dataclass
class AsLogStatus:
    """AS_LOG_STATUS_T"""
    name:   str = ""
    status: AsStatus = AsStatus.LOG_ADD
    logs:   str = ""

@dataclass
class AsPortStatusInfo:
    """AS_PORT_STATUS_INFO_T"""
    name:            str = ""
    manager_id:      str = ""
    connector_id:    str = ""
    agent_equip_id:  str = ""
    agent_port_no:   int = 0
    sequence:        int = 0
    protocol_type:   int = 0
    port_type:       int = 0
    status:          int = 0
    event_time:      str = ""
    additional_text: str = ""

@dataclass
class AsProcessStatus:
    """AS_PROCESS_STATUS_T"""
    manager_id:   str = ""
    process_id:   str = ""
    status:       int = 0
    pid:          int = 0
    process_type: int = 0
    start_time:   str = ""

@dataclass
class AsProcessStatusList:
    """AS_PROCESS_STATUS_LIST_T"""
    id:             int = 0
    proc_status_no: int = 0
    proc_status:    list = field(default_factory=list)  # list[AsProcessStatus]

@dataclass
class AsAsciiAck:
    """AS_ASCII_ACK_T"""
    id:          int = 0
    result_mode: int = 0
    result:      str = ""

@dataclass
class AsRouterPortInfo:
    """AS_ROUTER_PORT_INFO_T"""
    router_port_no: int = 0

@dataclass
class AsSessionInfo:
    """AS_SESSION_INFO_T"""
    session_type: int = 0
    name:         str = ""

@dataclass
class AsParsedData:
    """AS_PARSED_DATA_T"""
    ne_id:          str = ""
    event_id:       str = ""
    mapping_ne_id:  str = ""
    id_string:      str = ""
    event_time:     int = -1
    bsc_no:         int = 0
    equip_flag:     int = 0
    seg_blk_cnt:    int = 0
    list_sequence:  int = 0
    attribute_no:   int = 0
    guid:           str = ""
    result:         str = ""

@dataclass
class AsMmcLog:
    """AS_MMC_LOG_T"""
    id:             int = 0
    previous_id:    int = 0
    ne:             str = ""
    cmd_set_id:     int = 0
    cmd_id:         int = 0
    interfaces:     Any = None
    mmc:            str = ""
    id_string:      str = ""
    userid:         str = ""
    display:        str = ""
    retry_no:       int = 0
    cur_retry_no:   int = 0
    collect_mode:   Any = None
    response_mode:  Any = None
    publish_mode:   Any = None
    log_mode:       int = 0
    priority:       int = 0
    key:            str = ""
    cmd_delay_time: int = 0

@dataclass
class AsConnectorData:
    """AS_CONNECTOR_DATA_T"""
    msg_id:       int   = 0
    ne_id:        str   = ""
    agent_ne_id:  str   = ""
    port_no:      int   = 0
    logging_flag: int   = 0
    seg_flag:     SegFlag = SegFlag.NO_SEG
    length:       int   = 0
    raw_msg:      bytes = b""

@dataclass
class AsAsciiErrorMsg:
    """AS_ASCII_ERROR_MSG_T"""
    process_type: int = 0
    manager_id:   str = ""
    process_id:   str = ""
    priority:     int = 0
    err_msg:      str = ""

@dataclass
class AsRuleChangeInfo:
    """AS_RULE_CHANGE_INFO_T"""
    manager_id:     str = ""
    process_id:     str = ""
    rule_id:        str = ""
    mmc_ident_type: int = 0

@dataclass
class AsConnectorDescChangeInfo:
    """AS_CONNECTOR_DESC_CHANGE_INFO_T"""
    manager_id:   str = ""
    connector_id: str = ""
    description:  str = ""

@dataclass
class AsProcControl:
    """AS_PROC_CONTROL_T"""
    process_type:      int = 0
    manager_id:        str = ""
    host_name:         str = ""
    process_id:        str = ""
    junction_type:     int = 0
    rule_id:           str = ""
    mmc_ident_type:    int = 0
    cmd_response_type: int = 0
    connector_status:  int = 0
    parser_status:     int = 0
    status:            int = 0
    delay_time:        int = 0
    log_cycle:         int = 0
    desc:              str = ""
    reserve:           str = ""

@dataclass
class AsSessionControl:
    """AS_SESSION_CONTROL_T"""
    manager_id:   str = ""
    connector_id: str = ""
    sequence:     int = 0
    status:       int = 0
    desc:         str = ""

@dataclass
class AsGuiInitInfo:
    """AS_GUI_INIT_INFO_T"""
    count: int = 0

@dataclass
class AsManagerInfo:
    """AS_MANAGER_INFO_T"""
    manager_id:      str = ""
    old_manager_id:  str = ""
    ip:              str = ""
    request_status:  int = 0
    setting_status:  int = 0
    cur_status:      int = 0
    ssh_id:          str = ""
    ssh_pass:        str = ""

@dataclass
class AsConnectorInfo:
    """AS_CONNECTOR_INFO_T"""
    manager_id:       str = ""
    connector_id:     str = ""
    old_connector_id: str = ""
    junction_type:    int = 0
    rule_id:          str = ""
    mmc_ident_type:   int = 0
    cmd_response_type:int = 0
    request_status:   int = 0
    setting_status:   int = 0
    cur_status:       int = 0
    log_cycle:        int = 0
    create_date:      str = ""
    modify_date:      str = ""
    last_action_date: str = ""
    last_action_type: str = ""
    last_action_desc: str = ""
    desc:             str = ""
    reserve:          str = ""

@dataclass
class AsConnectionInfo:
    """AS_CONNECTION_INFO_T"""
    manager_id:       str = ""
    connector_id:     str = ""
    agent_equip_id:   str = ""
    sequence:         int = 0
    port_no:          int = 0
    protocol_type:    int = 0
    port_type:        int = 0
    user_id:          str = ""
    user_password:    str = ""
    gat_flag:         int = 0
    command_port_flag:int = 0
    request_status:   int = 0
    setting_status:   int = 0
    cur_status:       int = 0

@dataclass
class AsConnectionInfoList:
    """AS_CONNECTION_INFO_LIST_T"""
    size:           int  = 0
    request_status: int  = 0
    info_list:      list = field(default_factory=list)  # list[AsConnectionInfo]

@dataclass
class AsTargetIpInfo:
    """AS_TARGET_IP_INFO_T"""
    ip_address: str = ""
    port_no:    int = 0

@dataclass
class AsTargetIpInfoList:
    """AS_TARGET_IP_INFO_LIST_T"""
    size:           int  = 0
    target_ip_info: list = field(default_factory=list)  # list[AsTargetIpInfo]

@dataclass
class AsDataHandlerInfo:
    """AS_DATA_HANDLER_INFO_T"""
    data_handler_id:    str = ""
    old_data_handler_id:str = ""
    host_name:          str = ""
    ip_address:         str = ""
    listen_port:        int = 0
    time_mode:          int = 0
    log_mode:           int = 0
    oper_mode:          int = 0
    loading_interval:   int = 0
    bypass_listen_port: int = 0
    db_user_id:         str = ""
    db_password:        str = ""
    db_name:            str = ""
    request_status:     int = 0
    setting_status:     int = 0
    cur_status:         int = 0
    target_ip_info_list: AsTargetIpInfoList = field(default_factory=AsTargetIpInfoList)
    run_mode:           int = 0
    log_cycle:          int = 0
    ssh_id:             str = ""
    ssh_pass:           str = ""

@dataclass
class AsCommandAuthorityInfo:
    """AS_COMMAND_AUTHORITY_INFO_T"""
    id:              str = ""
    old_id:          str = ""
    max_cmd_queue:   int = 0
    priority:        int = 0
    log_mode:        int = 0
    ack_mode:        int = 0
    description:     str = ""
    request_status:  int = 0
    max_session_cnt: int = 0

@dataclass
class AsDataHandlerInit:
    """AS_DATA_HANDLER_INIT_T"""
    data_handler_id: str = ""
    init_mode:       int = 0
    desc:            str = ""
    reserve:         str = ""

@dataclass
class AsDataRoutingInit:
    """AS_DATA_ROUTING_INIT_T"""
    data_handler_id: str = ""
    init_mode:       int = 0
    desc:            str = ""
    reserve:         str = ""

@dataclass
class AsSubProcInfo:
    """AS_SUB_PROC_INFO_T"""
    proc_id:        int = 0
    proc_id_str:    str = ""
    old_proc_id_str:str = ""
    parent_proc:    int = 0
    parent_id:      str = ""
    ip_address:     str = ""
    host_name:      str = ""
    setting_status: int = 0
    cur_status:     int = 0
    request_status: int = 0
    log_cycle:      int = 0
    description:    str = ""
    binary_name:    str = ""
    args:           str = ""
    reserve:        str = ""

@dataclass
class AsLogTailDataReq:
    """AS_LOG_TAIL_DATA_REQ_T"""
    manager_id:   str = ""
    process_type: int = 0
    process_id:   str = ""
    log_cycle:    int = 0

@dataclass
class AsLogTailDataRes:
    """AS_LOG_TAIL_DATA_RES_T"""
    process_type: int = 0
    res_mode:     int = 0
    process_id:   str = ""
    result:       str = ""

@dataclass
class AsLogTailData:
    """AS_LOG_TAIL_DATA_T"""
    tail_data: str = ""

@dataclass
class AsHotTailDataReq:
    """AS_HOT_TAIL_DATA_REQ_T"""
    process_name: str = ""

@dataclass
class AsHotTailDataRes:
    """AS_HOT_TAIL_DATA_RES_T"""
    res_mode:     int = 0
    process_name: str = ""
    result:       str = ""

@dataclass
class AsHotTailData:
    """AS_HOT_TAIL_DATA_T"""
    tail_data: str = ""

@dataclass
class AsServerInfo:
    """AS_SERVER_INFO_T"""
    server_name:  str = ""
    act_db_user:  str = ""
    act_passwd:   str = ""
    act_db_tns:   str = ""

@dataclass
class AsDbSyncKind:
    """AS_DB_SYNC_KIND_T"""
    sync_kind: int = 0

@dataclass
class AsDbSyncInfo:
    """AS_DB_SYNC_INFO_T"""
    table_name: str = ""
    sync_time:  str = ""

@dataclass
class AsDbSyncInfoList:
    """AS_DB_SYNC_INFO_LIST_T"""
    active_svr_name:  str  = ""
    standby_svr_name: str  = ""
    standby_db:       str  = ""
    count:            int  = 0
    info_list:        list = field(default_factory=list)  # list[AsDbSyncInfo]

@dataclass
class AsSocketStatusReq:
    """AS_SOCKET_STATUS_REQ_T"""
    is_writerable_check: int = 0
    check_sec:           int = 0
    check_microsec:      int = 0

@dataclass
class AsSystemInfoData:
    """AS_SYSTEM_INFO_T"""
    process_type:    int = 0
    host_name:       str = ""
    host_ip:         str = ""
    process_id:      str = ""
    max_openable_fd: int = 0
    max_recv_buf:    int = 0
    max_send_buf:    int = 0

@dataclass
class AsSessionCfg:
    """AS_SESSION_CFG_T"""
    session_type:         int = 0
    session_buf_size:     int = 0
    socket_send_buf:      int = 0
    socket_recv_buf:      int = 0
    check_write_flag:     int = 0
    socket_timeout:       int = 0
    check_discon_cnt_flag:int = 0
    max_discon_count:     int = 0