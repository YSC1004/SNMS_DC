import struct

# ==========================================================================
# 1. CONSTANTS (Defines & Enums)
# ==========================================================================

# --- [LENGTH CONSTANTS] ---
NAME_LEN                = 40
DATE_STRING_LEN         = 20    # "YYYY/MM/DD HH:MI:SS"
PATH_LEN                = 100
MAX_RESULT_LEN          = 2000
MAX_DESC_LEN            = 500
MAX_MSG                 = 4096
EQUIP_ID_LEN            = 40
MMC_CMD_LEN             = 128
MMC_CMD_LEN_EX          = 1000
MMC_CMD_LEN_EX2         = 500
MMC_VAL_LEN             = 128
USER_ID_LEN             = 16
PASSWORD_LEN            = 16
IP_ADDRESS_LEN          = 16
IP_ADDRESS_LEN_EX       = IP_ADDRESS_LEN
EVENT_ID_LEN            = 32

# --- [MESSAGE IDs] ---
MMC_GEN_REQ             = 1001
MMC_GEN_REQ_ACK         = 1002
MMC_GEN_RES             = 1011
MMC_GEN_RES_ACK         = 1012
MMC_PUB_REQ             = 1021
MMC_PUB_REQ_ACK         = 1022
AS_MMC_REQ              = 6
AS_MMC_REQ_ACK          = 2
AS_MMC_REQ_OLD          = 1
AS_MMC_RES              = 11
AS_MMC_RES_ACK          = 12
AS_MMC_FLOW_CONTROL     = 31

CMD_MMC_PUBLISH_REQ     = 1500
CMD_MMC_PUBLISH_ACK     = 1501
CMD_MMC_PUBLISH_RES     = 1502
MMC_RESPONSE_DATA_REQ   = 1503
MMC_RESPONSE_DATA       = 1504

NETFINDER_REQ           = 901
NETFINDER_REV           = 902

CMD_ALIVE               = 2001
CMD_ALIVE_ACK           = 2002
CMD_ALIVE_RECEIVE       = 2003
CMD_ALIVE_SEND          = 2004
CMD_OPEN_PORT           = 2011
CMD_OPEN_PORT_ACK       = 2012
CONNECTOR_PORT_INFO_REQ = 2013
DATAHANDLER_PORT_INFO_REQ = 2014
CMD_CLOSE_PORT          = 2021
CMD_CLOSE_PORT_ACK      = 2022
CMD_REOPEN_PORT         = 2031
CMD_REOPEN_PORT_ACK     = 2032
CMD_LOG_STATUS_CHANGE   = 2041
AS_LOG_INFO             = 2043
CMD_SET_LOG             = 2051
CMD_SET_LOG_ACK         = 2052
CMD_INIT_CFG            = 2061
CMD_INIT_CFG_ACK        = 2062
CMD_PS_STS              = 2081
CMD_PS_STS_ACK          = 2082
ASCII_ERROR_MSG         = 2090
CMD_PROC_INIT           = 2101

SESSION_REPORTING       = 1003
INFO_SESSION_NAME       = 4000
NOT_ASSIGN              = 4001
CONNECTION_PORT_INFO    = 1005
PARSER_INTI_END         = 1006
ROUTER_PORT_INFO        = 1007

AS_PARSED_DATA          = 5001
MMC_LOG                 = 6001
CONNECTOR_DATA          = 3004
PORT_STATUS_INFO        = 2901
PROCESS_INFO            = 3300
PROCESS_INFO_LIST       = 3301
PROC_CONTROL            = 3008
SESSION_CONTROL         = 3013
CMD_ALIVE_CHECK			= 3000
PROC_INIT_END			= 3001
MANAGER_INIT_END		= 3002
MMC_CMD_RESULT			= 3003
PROC_CONTROL			= 3008

CMD_PARSING_RULE_COPY         = 4102
CMD_PARSING_RULE_CHANGE       = 4103
CMD_CONNECTOR_DESC_CHANGE     = 4104

# GUI Comm
CMD_PARSING_RULE_DOWN         = 12001
CMD_PARSING_RULE_DOWN_ACK     = 12002
CMD_MAPPING_RULE_DOWN         = 12003
CMD_MAPPING_RULE_DOWN_ACK     = 12004
CMD_COMMAND_RULE_DOWN         = 12005
CMD_COMMAND_RULE_DOWN_ACK     = 12006
CMD_SCHEDULER_RULE_DOWN       = 12007
CMD_SCHEDULER_RULE_DOWN_ACK   = 12008
TAIL_RAW_DATA_REQ             = 12009
TAIL_LOG_DATA_REQ             = 12101
TAIL_LOG_DATA_RES             = 12102
TAIL_LOG_DATA                 = 12103
TAIL_HOT_DATA_REQ             = 12111
TAIL_HOT_DATA_RES             = 12112
TAIL_HOT_DATA                 = 12113
TAIL_HOT_DATA_CHG             = 12114

# Info/Modify
CONNECTOR_MODIFY              = 11101
CONNECTOR_MODIFY_ACK          = 11102
MANAGER_MODIFY                = 11103
MANAGER_MODIFY_ACK            = 11104
CONNECTION_MODIFY             = 11105
CONNECTION_MODIFY_ACK         = 11106
DATAHANDLER_MODIFY            = 11107
DATAHANDLER_MODIFY_ACK        = 11108
CONNECTION_LIST_MODIFY        = 11109
CONNECTION_LIST_MODIFY_ACK    = 11110
COMMAND_AUTHORITY_MODIFY      = 11111
COMMAND_AUTHORITY_MODIFY_ACK  = 11112
SUB_PROC_MODIFY               = 11113
SUB_PROC_MODIFY_ACK           = 11114
INIT_INFO_START               = 11201
INIT_INFO_END                 = 11202

# Socket Status
AS_SOCKET_STATUS_REQ          = 11203
AS_SOCKET_STATUS_RES          = 11204
FR_SOCKET_STATUS_REQ          = 11205
FR_SOCKET_STATUS_RES          = 11206
FR_SOCKET_SHUTDOWN_REQ        = 11207
FR_SOCKET_SHUTDOWN_RES        = 11208
FR_SOCKET_CHECK_REQ           = 11209
FR_SOCKET_CHECK_RES           = 11210

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

AS_DB_SYNC_INFO_REQ           = 11211
AS_DB_SYNC_INFO_REQ_ACK       = 11212
AS_DATA_HANDLER_INIT          = 11213
AS_DATA_ROUTING_INIT          = 11214
AS_SYSTEM_INFO                = 11301
AS_SESSION_CFG                = 11302

# --- [ENUMS] ---
SCH_RESERVE = 0; SCH_LOOP = 1; SCH_MONITOR = 2
RESPONSE_NOT_YET = 0; RESPONSE_CAPTURED = 1; RESPONSE_LOST = 2
ID_STRING_MMC = 0; ID_STRING_IDSTRING = 1
ACT_CREATE = 0; ACT_MODIFY = 1; ACT_START = 2; ACT_STOP = 3; ACT_DELETE = 4
FAIL = 0; SUCCEED = 1

GET_LOG_INFO = 0; SET_LOG = 1
LOG_ADD = 0; LOG_DEL = 1

PORT_CONNECTED = 1; PORT_NORMAL = 2; PORT_DISCONNECTED = 3; PORT_ELIMINATION = 4
START = 1; STOP = 2
WAIT_NO = 1; WAIT_START = 2; WAIT_STOP = 3; CREATE_DATA = 4; UPDATE_DATA = 5; DELETE_DATA = 6

INFO_NO_SEG = 1; INFO_START = 2; INFO_ING = 3; INFO_END = 4

# Data Handler Mode
DB_LOAD_SQLLOADER = 0; DB_LOAD_OCI = 1; SAVE_FILE = 2; BYPASS_SERVER = 3
BYPASS_CLIENT = 4; SAVE_FILE2 = 5; SAVE_FILE3 = 6; SAVE_FILE_BC = 7

# Junction Type
ASCII_J = 0; Q3_J = 1; SNMP_J = 2; CORBA_J = 3

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

# --- [PROCESS TYPES (Full List)] ---
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
NETFINDER               = 1216
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

# --- [PORT TYPES (Full List)] ---
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

LTAS_LOG_KCC_APP        = 1546
LTAS_LOG_CALL_FTP       = 1547
LTAS_LOG_KCC_R_APP      = 1548
LTAS_LOG_KCC_VoLTE      = 1549
LTAS_LOADER_LOG_KCC_NEW_VoLTE = 1551
LTAS_LOG_KCC_NEW_VoLTE  = 1552
LTAS_LOADER_LOG_KCC_APP = 1556
LTAS_LOADER_LOG_CALL_FTP= 1557
LTAS_LOADER_LOG_KCC_R_APP = 1558
LTAS_LOADER_LOG_KCC_VoLTE = 1559
LTAS_LOADER_LOG_CTQ_UL  = 1560
LTAS_LOG_CTQ_UL         = 1561

# --- [PROTOCOL TYPES (Full List)] ---
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
SNMP_AGENT              = 1729 # Used in AsUtil for SNMP_AGENT
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
IMS_IBCF_IRUE_AGENT     = 1730
LTE_HSS_SDS_AGENT       = 1731
LTE_CSC_SDS_AGENT       = 1732
SFTP_TEST_AGENT         = 1733
IMS_IBCF_NABLE_AGENT    = 1734
REC_XCURE_AGENT         = 1735
LTE_SAME_CSL_AGENT      = 1736
SG_SAME_AMF_AGENT       = 1737
SG_IRUE_UDM_AGENT       = 1738
SG_IRUE_UDR_AGENT       = 1739
SG_SAME_CSCF_AGENT      = 1740
SG_CICS_AMF_AGENT       = 1741
SG_CICS_SMF_AGENT       = 1742
SG_CICS_UPF_AGENT       = 1743
SG_SAME_CSL_AGENT       = 1744
SG_LGES_ENM_15M_AGENT   = 1745
SG_SAME_VSM_AGENT       = 1746
SG_NSNN_NETACT_AGENT    = 1747
SG_NSNN_NETACT_CM_AGENT = 1748
SG_ARIE_ePCF_AGENT      = 1749
SG_SNET_PCF_AGENT       = 1750
SG_LGE_ENM_CM_CELL_AGENT= 1751
SG_LGE_ENM_CM_SITE_AGENT= 1752
SG_ARIE_SMLC_AGENT      = 1753
SG_IRUE_SMLC_AGENT      = 1754
SG_IRUE_VTAS_AGENT      = 1755
SG_SAME_VSM_5M_AGENT    = 1756
SG_SAME_VSM_15M_AGENT   = 1757
SG_NSNN_NETACT_5M_AGENT = 1758
SG_VSM_SAME_CM_DU_AGENT = 1759
SG_NSNN_NETACT_CM2_AGENT= 1760
SG_SAME_VSM_CU_5M_AGENT = 1761
SG_ARIE_DQE_AGENT       = 1762
SG_IRUE_iPgw_AGENT      = 1763
SG_LGES_ENM_15M_GZ_AGENT= 1764
SG_SAME_AMF_CSL_AGENT   = 1765
SG_IRUE_UDAF_AGENT      = 1766
SG_SAME_USM_AGENT       = 1767
SG_IRUE_AUSF_AGENT      = 1768
SG_ARIE_PCC_AGENT       = 1769
SG_SAME_VSM_5M_DIV_AGENT= 1770
SG_VSM_SAME_CM_CU_AGENT = 1771
SG_IRUE_NRF_AGENT       = 1772
SG_ARIE_LMF_AGENT       = 1773
SG_IRUE_AUSF_CSL_AGENT  = 1774
SG_SNET_PCF_SA_AGENT    = 1775
SG_ARIE_IOTGW_AGENT     = 1776
SG_ARIE_ePCF_HH_AGENT   = 1777
SG_ARIE_EMG_AGENT       = 1778
SG_SAME_VSM_CU_DIV_AGENT= 1779
SG_ARIE_FNPS_AGENT      = 1780
SG_SAME_USM_CU_5M_AGENT = 1781
SG_SAME_USM_5M_AGENT    = 1782
SG_SAME_USM_60M_AGENT   = 1783
SG_LOCS_KPNS_AGENT      = 1784
SG_LOCS_IPSMGW_AGENT    = 1785
SG_LGE_ENM_COM_CELL_AGENT = 1786
SG_ARIE_FNPSMP_AGENT    = 1787
SG_VSM_SAME_CM_AU_AGENT = 1788
SG_LGE_ENM_COM_DU_AGENT = 1789
SG_LGE_ES_GET_AGENT     = 1790
SG_ARIE_ESAN_AGENT      = 1791
SG_ARIE_GMG_AGENT       = 1792
SG_ARIE_SSPF_AGENT      = 1793
SG_IRUE_DRA_AGENT       = 1794
SG_BRGT_MRF_AGENT       = 1795
SG_LGE_ES_GET_NEW_AGENT = 1796
SG_LGES_ENM_15M_GZ_PF_AGENT = 1797
SG_ARIE_CCS_AGENT       = 1798
SG_CICS_UPF2_AGENT      = 1799
ALARM_CHG_ASCII_AGENT   = 1800
SG_LGES_ENM_15M_GZ_DIV_AGENT = 1801
SG_SNET_PCRF_AGENT      = 1802
SG_LGES_ENM_60M_GZ_AGENT= 1803
SG_IRUE_vIBCF_AGENT     = 1804
SG_ARIE_ERS_AGENT       = 1805
SG_USM_SAME_CM_DU30_AGENT = 1806
SG_ARIE_LTE_PCC_AGENT   = 1807
SG_LGES_ENM_60M_GZ_DIV_AGENT = 1808

CMD_PROC_TERMINATE  =   3100

# Arguments
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

# Process Kill Types
ORDER_KILL = 1
NORMAL_EXIT = 0

# ==========================================================================
# 2. PACKET STRUCTURES
# ==========================================================================

class BasePacket:
    @classmethod
    def _decode_str(cls, byte_data):
        return byte_data.decode('utf-8', errors='ignore').strip('\x00')

    @classmethod
    def _encode_str(cls, str_data, size):
        return str_data.encode('utf-8')[:size]

class PacketT(BasePacket):
    HEADER_FMT = "!II"  
    HEADER_SIZE = struct.calcsize(HEADER_FMT)
    MAX_MSG_SIZE = 4096 * 10

    def __init__(self, msg_id=0, length=0, msg_body=b''):
        self.msg_id = msg_id
        self.length = length
        self.msg_body = msg_body

    def pack(self):
        if self.msg_body:
            self.length = len(self.msg_body)
        return struct.pack(self.HEADER_FMT, self.msg_id, self.length) + self.msg_body

    @classmethod
    def unpack_header(cls, data):
        msg_id, length = struct.unpack(cls.HEADER_FMT, data)
        return cls(msg_id, length)

class AsSessionInfoT(BasePacket):
    FMT = "!I100s"
    SIZE = struct.calcsize(FMT)

    def __init__(self, session_type=0, name=""):
        self.SessionType = session_type
        self.Name = name

    def pack(self):
        return struct.pack(self.FMT, self.SessionType, self._encode_str(self.Name, 100))

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        stype, name = struct.unpack(cls.FMT, data[:cls.SIZE])
        return cls(stype, cls._decode_str(name))

class AsAsciiAckT(BasePacket):
    FMT = f"!II{MAX_RESULT_LEN}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self, id_val=0, result_mode=0, result_msg=""):
        self.Id = id_val
        self.ResultMode = result_mode
        self.Result = result_msg

    def pack(self):
        return struct.pack(self.FMT, self.Id, self.ResultMode, self._encode_str(self.Result, MAX_RESULT_LEN))

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        return cls(t[0], t[1], cls._decode_str(t[2]))

class AsCmdOpenPortT(BasePacket):
    FMT = f"!II{NAME_LEN}s{NAME_LEN}s40s{NAME_LEN}s{NAME_LEN}s{IP_ADDRESS_LEN_EX}sI{PATH_LEN}s{USER_ID_LEN}s{PASSWORD_LEN}s{NAME_LEN}sIIII{NAME_LEN}s"
    SIZE = struct.calcsize(FMT)
    
    def __init__(self):
        self.Id = 0; self.Sequence = 0
        self.EquipId = ""; self.AgentEquipId = ""; self.Consumer = ""
        self.Name = ""; self.ConnectorId = ""; self.IpAddress = ""
        self.PortNo = 0; self.PortPath = ""; self.UserId = ""
        self.Password = ""; self.AsciiHeader = ""
        self.ProtocolType = 0; self.PortType = 0
        self.GatFlag = 0; self.CommandPortFlag = 0; self.DnId = ""

    def pack(self):
        return struct.pack(self.FMT,
            self.Id, self.Sequence,
            self._encode_str(self.EquipId, NAME_LEN), self._encode_str(self.AgentEquipId, NAME_LEN),
            self._encode_str(self.Consumer, 40), self._encode_str(self.Name, NAME_LEN),
            self._encode_str(self.ConnectorId, NAME_LEN), self._encode_str(self.IpAddress, IP_ADDRESS_LEN_EX),
            self.PortNo, self._encode_str(self.PortPath, PATH_LEN),
            self._encode_str(self.UserId, USER_ID_LEN), self._encode_str(self.Password, PASSWORD_LEN),
            self._encode_str(self.AsciiHeader, NAME_LEN), self.ProtocolType, self.PortType,
            self.GatFlag, self.CommandPortFlag, self._encode_str(self.DnId, NAME_LEN)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        obj = cls()
        obj.Id, obj.Sequence = t[0], t[1]
        obj.EquipId, obj.AgentEquipId = cls._decode_str(t[2]), cls._decode_str(t[3])
        obj.Consumer, obj.Name = cls._decode_str(t[4]), cls._decode_str(t[5])
        obj.ConnectorId, obj.IpAddress = cls._decode_str(t[6]), cls._decode_str(t[7])
        obj.PortNo, obj.PortPath = t[8], cls._decode_str(t[9])
        obj.UserId, obj.Password = cls._decode_str(t[10]), cls._decode_str(t[11])
        obj.AsciiHeader = cls._decode_str(t[12])
        obj.ProtocolType, obj.PortType, obj.GatFlag, obj.CommandPortFlag = t[13], t[14], t[15], t[16]
        obj.DnId = cls._decode_str(t[17])
        return obj

class AsCmdLogControlT(BasePacket):
    FMT = "!IIII40s80s128s128sI"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.Id = 0; self.ProcessType = 0; self.Type = 0
        self.ManagerId = ""; self.ProcessId = ""
        self.Package = ""; self.Feature = ""; self.Level = 0

    def pack(self):
        return struct.pack(self.FMT, self.Id, self.ProcessType, self.Type, 0, 
             self._encode_str(self.ManagerId, 40), self._encode_str(self.ProcessId, 80),
             self._encode_str(self.Package, 128), self._encode_str(self.Feature, 128),
             self.Level)

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        obj = cls()
        obj.Id, obj.ProcessType, obj.Type = t[0], t[1], t[2]
        obj.ManagerId, obj.ProcessId = cls._decode_str(t[4]), cls._decode_str(t[5])
        obj.Package, obj.Feature = cls._decode_str(t[6]), cls._decode_str(t[7])
        obj.Level = t[8]
        return obj

class AsLogStatusT(BasePacket):
    LOG_SIZE = 4088 - NAME_LEN - 4
    FMT = f"!{NAME_LEN}sI{LOG_SIZE}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self, name="", status=0, logs=""):
        self.name = name; self.status = status; self.logs = logs

    def pack(self):
        return struct.pack(self.FMT, self._encode_str(self.name, NAME_LEN), self.status, self._encode_str(self.logs, self.LOG_SIZE))
    
    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        return cls(cls._decode_str(t[0]), t[1], cls._decode_str(t[2]))

class AsProcessStatusT(BasePacket):
    FMT = f"!{NAME_LEN}s{NAME_LEN}sIII{DATE_STRING_LEN}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ManagerId = ""; self.ProcessId = ""; self.Status = 0
        self.Pid = 0; self.ProcessType = 0; self.StartTime = ""
    
    @classmethod
    def unpack(cls, data):
        t = struct.unpack(cls.FMT, data)
        obj = cls()
        obj.ManagerId = cls._decode_str(t[0])
        obj.ProcessId = cls._decode_str(t[1])
        obj.Status, obj.Pid, obj.ProcessType = t[2], t[3], t[4]
        obj.StartTime = cls._decode_str(t[5])
        return obj

class AsProcessStatusListT(BasePacket):
    def __init__(self):
        self.id = 0
        self.ProcStatusNo = 0
        self.ProcStatus = []

    @classmethod
    def unpack(cls, data):
        head_fmt = "!II"
        head_size = struct.calcsize(head_fmt)
        if len(data) < head_size: return None
        
        obj = cls()
        obj.id, obj.ProcStatusNo = struct.unpack(head_fmt, data[:head_size])
        
        item_size = AsProcessStatusT.SIZE
        offset = head_size
        for _ in range(obj.ProcStatusNo):
            if offset + item_size > len(data): break
            item_data = data[offset : offset + item_size]
            obj.ProcStatus.append(AsProcessStatusT.unpack(item_data))
            offset += item_size
        return obj

class AsSystemInfoT(BasePacket):
    FMT = "!I80s20s80sIII"
    SIZE = struct.calcsize(FMT)
    
    def __init__(self):
        self.ProcessType = 0; self.HostName = ""; self.HostIp = ""
        self.ProcessId = ""; self.m_MaxOpenableFd = 0
        self.m_MaxRecvBuf = 0; self.m_MaxSendBuf = 0

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        obj = cls()
        obj.ProcessType = t[0]
        obj.HostName, obj.HostIp = cls._decode_str(t[1]), cls._decode_str(t[2])
        obj.ProcessId = cls._decode_str(t[3])
        obj.m_MaxOpenableFd, obj.m_MaxRecvBuf, obj.m_MaxSendBuf = t[4], t[5], t[6]
        return obj
    
class AsManagerInfoT(BasePacket):
    """
    typedef struct {
        char    ManagerId[NAME_LEN];
        char    OldManagerId[NAME_LEN];
        char    IP[20];
        int     RequestStatus;
        int     SettingStatus;
        int     CurStatus;
        char    SshID[40];
        char    SshPass[40];
    } AS_MANAGER_INFO_T;
    """
    # 40s(MgrId) 40s(OldMgrId) 20s(IP) I(Req) I(Set) I(Cur) 40s(SshID) 40s(SshPass)
    # NAME_LEN = 40 가정
    FMT = f"!{NAME_LEN}s{NAME_LEN}s20sIII40s40s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ManagerId = ""
        self.OldManagerId = ""
        self.IP = ""
        self.RequestStatus = 0
        self.SettingStatus = 0
        self.CurStatus = 0
        self.SshID = ""
        self.SshPass = ""

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.ManagerId, NAME_LEN),
            self._encode_str(self.OldManagerId, NAME_LEN),
            self._encode_str(self.IP, 20),
            self.RequestStatus,
            self.SettingStatus,
            self.CurStatus,
            self._encode_str(self.SshID, 40),
            self._encode_str(self.SshPass, 40)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.ManagerId = cls._decode_str(t[0])
        obj.OldManagerId = cls._decode_str(t[1])
        obj.IP = cls._decode_str(t[2])
        obj.RequestStatus = t[3]
        obj.SettingStatus = t[4]
        obj.CurStatus = t[5]
        obj.SshID = cls._decode_str(t[6])
        obj.SshPass = cls._decode_str(t[7])
        return obj
    
# -------------------------------------------------------
# AS_CONNECTOR_INFO_T Structure
# -------------------------------------------------------
class AsConnectorInfoT(BasePacket):
    """
    typedef struct {
        char    ManagerId[NAME_LEN];        // 40
        char    ConnectorId[NAME_LEN];      // 40
        char    OldConnectorId[NAME_LEN];   // 40 (not use)
        int     JunctionType;               // 4
        char    RuleId[NAME_LEN];           // 40
        int     MmcIdentType;               // 4
        int     CmdResponseType;            // 4
        char    DescriptionXXX[NAME_LEN];   // 40
        int     RequestStatus;              // 4
        int     SettingStatus;              // 4
        int     CurStatus;                  // 4
        int     LogCycle;                   // 4
        char    CreateDate[DATE_STRING_LEN];      // 20
        char    ModifyDate[DATE_STRING_LEN];      // 20
        char    LastActionDate[DATE_STRING_LEN];  // 20
        char    LastActionType[NAME_LEN];         // 40
        char    LastActionDesc[MAX_DESC_LEN];     // 500
        char    Desc[MAX_DESC_LEN];               // 500
        char    Reserve[30];                      // 30
    } AS_CONNECTOR_INFO_T;
    """
    
    # Format String Construction
    # NAME_LEN=40, DATE_STRING_LEN=20, MAX_DESC_LEN=500
    FMT = (f"!{NAME_LEN}s{NAME_LEN}s{NAME_LEN}sI{NAME_LEN}sII{NAME_LEN}sIIII"
           f"{DATE_STRING_LEN}s{DATE_STRING_LEN}s{DATE_STRING_LEN}s"
           f"{NAME_LEN}s{MAX_DESC_LEN}s{MAX_DESC_LEN}s30s")
           
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ManagerId = ""
        self.ConnectorId = ""
        self.OldConnectorId = ""
        self.JunctionType = 0
        self.RuleId = ""
        self.MmcIdentType = 0
        self.CmdResponseType = 0
        self.DescriptionXXX = ""
        self.RequestStatus = 0
        self.SettingStatus = 0
        self.CurStatus = 0
        self.LogCycle = 0
        self.CreateDate = ""
        self.ModifyDate = ""
        self.LastActionDate = ""
        self.LastActionType = ""
        self.LastActionDesc = ""
        self.Desc = ""
        self.Reserve = ""

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.ManagerId, NAME_LEN),
            self._encode_str(self.ConnectorId, NAME_LEN),
            self._encode_str(self.OldConnectorId, NAME_LEN),
            self.JunctionType,
            self._encode_str(self.RuleId, NAME_LEN),
            self.MmcIdentType,
            self.CmdResponseType,
            self._encode_str(self.DescriptionXXX, NAME_LEN),
            self.RequestStatus,
            self.SettingStatus,
            self.CurStatus,
            self.LogCycle,
            self._encode_str(self.CreateDate, DATE_STRING_LEN),
            self._encode_str(self.ModifyDate, DATE_STRING_LEN),
            self._encode_str(self.LastActionDate, DATE_STRING_LEN),
            self._encode_str(self.LastActionType, NAME_LEN),
            self._encode_str(self.LastActionDesc, MAX_DESC_LEN),
            self._encode_str(self.Desc, MAX_DESC_LEN),
            self._encode_str(self.Reserve, 30)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.ManagerId = cls._decode_str(t[0])
        obj.ConnectorId = cls._decode_str(t[1])
        obj.OldConnectorId = cls._decode_str(t[2])
        obj.JunctionType = t[3]
        obj.RuleId = cls._decode_str(t[4])
        obj.MmcIdentType = t[5]
        obj.CmdResponseType = t[6]
        obj.DescriptionXXX = cls._decode_str(t[7])
        obj.RequestStatus = t[8]
        obj.SettingStatus = t[9]
        obj.CurStatus = t[10]
        obj.LogCycle = t[11]
        obj.CreateDate = cls._decode_str(t[12])
        obj.ModifyDate = cls._decode_str(t[13])
        obj.LastActionDate = cls._decode_str(t[14])
        obj.LastActionType = cls._decode_str(t[15])
        obj.LastActionDesc = cls._decode_str(t[16])
        obj.Desc = cls._decode_str(t[17])
        obj.Reserve = cls._decode_str(t[18])
        
        return obj

# -------------------------------------------------------
# AS_CONNECTION_INFO_T Structure
# -------------------------------------------------------
class AsConnectionInfoT(BasePacket):
    """
    typedef struct {
        char    ManagerId[NAME_LEN];
        char    ConnectorId [NAME_LEN];
        char    AgentEquipId[NAME_LEN];
        int     Sequence;
        int     PortNo;
        int     ProtocolType;
        int     PortType;
        char    UserId[USER_ID_LEN];
        char    UserPassword[PASSWORD_LEN];
        int     GatFlag;
        int     CommandPortFlag;
        int     RequestStatus; 
        int     SettingStatus;
        int     CurStatus;
    } AS_CONNECTION_INFO_T;
    """
    
    # NAME_LEN(40), USER_ID_LEN(20), PASSWORD_LEN(20) 가정
    # 40s 40s 40s I I I I 20s 20s I I I I I
    FMT = f"!{NAME_LEN}s{NAME_LEN}s{NAME_LEN}sIIII{USER_ID_LEN}s{PASSWORD_LEN}sIIIII"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ManagerId = ""
        self.ConnectorId = ""
        self.AgentEquipId = ""
        self.Sequence = 0
        self.PortNo = 0
        self.ProtocolType = 0
        self.PortType = 0
        self.UserId = ""
        self.UserPassword = ""
        self.GatFlag = 0
        self.CommandPortFlag = 0
        self.RequestStatus = 0
        self.SettingStatus = 0
        self.CurStatus = 0

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.ManagerId, NAME_LEN),
            self._encode_str(self.ConnectorId, NAME_LEN),
            self._encode_str(self.AgentEquipId, NAME_LEN),
            self.Sequence,
            self.PortNo,
            self.ProtocolType,
            self.PortType,
            self._encode_str(self.UserId, USER_ID_LEN),
            self._encode_str(self.UserPassword, PASSWORD_LEN),
            self.GatFlag,
            self.CommandPortFlag,
            self.RequestStatus,
            self.SettingStatus,
            self.CurStatus
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.ManagerId = cls._decode_str(t[0])
        obj.ConnectorId = cls._decode_str(t[1])
        obj.AgentEquipId = cls._decode_str(t[2])
        obj.Sequence = t[3]
        obj.PortNo = t[4]
        obj.ProtocolType = t[5]
        obj.PortType = t[6]
        obj.UserId = cls._decode_str(t[7])
        obj.UserPassword = cls._decode_str(t[8])
        obj.GatFlag = t[9]
        obj.CommandPortFlag = t[10]
        obj.RequestStatus = t[11]
        obj.SettingStatus = t[12]
        obj.CurStatus = t[13]
        return obj
    
# -------------------------------------------------------
# AS_GUI_INIT_INFO_T Structure
# -------------------------------------------------------
class AsGuiInitInfoT(BasePacket):
    """
    typedef struct {
        int		Count;
    } AS_GUI_INIT_INFO_T;
    """
    FMT = "!I64s"  # Integer + 64 bytes reserved
    SIZE = struct.calcsize(FMT)

    def __init__(self, count=0):
        self.Count = count

    def pack(self):
        return struct.pack(self.FMT, self.Count)

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        return cls(t[0])
    
# -------------------------------------------------------
# AS_CONNECTION_INFO_LIST_T Structure
# -------------------------------------------------------
class AsConnectionInfoListT(BasePacket):
    """
    typedef struct {
        int                     Size;
        int                     RequestStatus;
        AS_CONNECTION_INFO_T    InfoList[10];
    } AS_CONNECTION_INFO_LIST_T;
    """
    
    # Header: int + int
    HEADER_FMT = "!II"
    HEADER_SIZE = struct.calcsize(HEADER_FMT)
    
    # C++ Fixed Array Size
    MAX_ARRAY_SIZE = 10

    def __init__(self):
        self.Size = 0
        self.RequestStatus = 0
        self.InfoList = [] # List of AsConnectionInfoT

    def pack(self):
        # 현재 리스트 크기로 Size 갱신
        self.Size = len(self.InfoList)
        if self.Size > self.MAX_ARRAY_SIZE:
            self.Size = self.MAX_ARRAY_SIZE # 최대 10개 제한
            
        # 1. Header Packing
        packed_data = struct.pack(self.HEADER_FMT, self.Size, self.RequestStatus)
        
        # 2. Array Packing (Fixed size 10)
        for i in range(self.MAX_ARRAY_SIZE):
            if i < self.Size:
                # 유효한 데이터 Pack
                packed_data += self.InfoList[i].pack()
            else:
                # 빈 데이터(Padding) Pack - C++ 구조체 크기 맞춤
                packed_data += AsConnectionInfoT().pack()
                
        return packed_data

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.HEADER_SIZE: return None
        
        obj = cls()
        # 1. Header Unpack
        obj.Size, obj.RequestStatus = struct.unpack(cls.HEADER_FMT, data[:cls.HEADER_SIZE])
        
        # Safety Check (C++에서 쓰레기 값이 와서 10을 넘을 경우 방지)
        valid_count = min(obj.Size, cls.MAX_ARRAY_SIZE)
        
        # 2. Array Unpack
        offset = cls.HEADER_SIZE
        item_size = AsConnectionInfoT.SIZE
        
        for _ in range(valid_count):
            if offset + item_size > len(data): break
            
            item_data = data[offset : offset + item_size]
            obj.InfoList.append(AsConnectionInfoT.unpack(item_data))
            
            offset += item_size
            
        return obj
    
# -------------------------------------------------------
# AS_TARGET_IP_INFO_T Structure
# -------------------------------------------------------
class AsTargetIpInfoT(BasePacket):
    """
    typedef struct {
        char    IpAddress[IP_ADDRESS_LEN];
        int     PortNo;
    } AS_TARGET_IP_INFO_T;
    """
    # IP_ADDRESS_LEN(16) + int(4)
    FMT = f"!{IP_ADDRESS_LEN}sI"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.IpAddress = ""
        self.PortNo = 0

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.IpAddress, IP_ADDRESS_LEN),
            self.PortNo
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.IpAddress = cls._decode_str(t[0])
        obj.PortNo = t[1]
        return obj
    
# -------------------------------------------------------
# AS_TARGET_IP_INFO_LIST_T Structure
# -------------------------------------------------------
class AsTargetIpInfoListT(BasePacket):
    """
    typedef struct {
        int                     Size;
        AS_TARGET_IP_INFO_T     TargetIpInfo[20];
    } AS_TARGET_IP_INFO_LIST_T;
    """
    
    # Header: int
    HEADER_FMT = "!I"
    HEADER_SIZE = struct.calcsize(HEADER_FMT)
    
    # Fixed Array Size
    MAX_ARRAY_SIZE = 20

    def __init__(self):
        self.Size = 0
        self.TargetIpInfo = [] # List of AsTargetIpInfoT

    def pack(self):
        # 현재 리스트 크기로 Size 갱신
        self.Size = len(self.TargetIpInfo)
        if self.Size > self.MAX_ARRAY_SIZE:
            self.Size = self.MAX_ARRAY_SIZE

        # 1. Header Packing
        packed_data = struct.pack(self.HEADER_FMT, self.Size)

        # 2. Array Packing (Fixed size 20)
        # C++ 구조체 크기를 맞추기 위해 빈 공간은 더미 데이터로 채움
        for i in range(self.MAX_ARRAY_SIZE):
            if i < self.Size:
                packed_data += self.TargetIpInfo[i].pack()
            else:
                packed_data += AsTargetIpInfoT().pack()
        
        return packed_data

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.HEADER_SIZE: return None
        
        obj = cls()
        obj.Size = struct.unpack(cls.HEADER_FMT, data[:cls.HEADER_SIZE])[0]

        # Safety check
        valid_count = min(obj.Size, cls.MAX_ARRAY_SIZE)
        
        offset = cls.HEADER_SIZE
        item_size = AsTargetIpInfoT.SIZE # SIZE 속성 필요

        for _ in range(valid_count):
            if offset + item_size > len(data): break
            
            item_data = data[offset : offset + item_size]
            obj.TargetIpInfo.append(AsTargetIpInfoT.unpack(item_data))
            offset += item_size
            
        return obj
    
# -------------------------------------------------------
# AS_DATA_HANDLER_INFO_T Structure
# -------------------------------------------------------
class AsDataHandlerInfoT(BasePacket):
    """
    typedef struct {
        char    DataHandlerId[40];
        char    OldDataHandlerId[40];
        char    HostName[40];
        char    IpAddress[IP_ADDRESS_LEN];  // 16
        int     ListenPort;
        int     TimeMode;
        int     LogMode;
        int     OperMode;
        int     LoadingInterval;
        int     BypassListenPort;
        char    DbUserId[16];
        char    DbPassword[16];
        char    DbName[16];
        int     RequestStatus;
        int     SettingStatus;
        int     CurStatus;
        AS_TARGET_IP_INFO_LIST_T    TargetIpInfoList; // Nested Struct
        int     RunMode;
        int     LogCycle;
        char    SshID[40];
        char    SshPass[40];
    } AS_DATA_HANDLER_INFO_T;
    """
    
    # Part 1: TargetIpInfoList 이전
    # 40s 40s 40s 16s I I I I I I 16s 16s 16s I I I
    FMT_1 = f"!40s40s40s{IP_ADDRESS_LEN}sIIIIII16s16s16sIII"
    SIZE_1 = struct.calcsize(FMT_1)
    
    # Part 2: TargetIpInfoList (가변이 아닌 고정 크기 구조체)
    
    # Part 3: TargetIpInfoList 이후
    # I I 40s 40s
    FMT_2 = "!II40s40s"
    SIZE_2 = struct.calcsize(FMT_2)

    def __init__(self):
        self.DataHandlerId = ""
        self.OldDataHandlerId = ""
        self.HostName = ""
        self.IpAddress = ""
        self.ListenPort = 0
        self.TimeMode = 0
        self.LogMode = 0
        self.OperMode = 0
        self.LoadingInterval = 0
        self.BypassListenPort = 0
        self.DbUserId = ""
        self.DbPassword = ""
        self.DbName = ""
        self.RequestStatus = 0
        self.SettingStatus = 0
        self.CurStatus = 0
        
        # Nested Struct 초기화
        self.TargetIpInfoList = AsTargetIpInfoListT()
        
        self.RunMode = 0
        self.LogCycle = 0
        self.SshID = ""
        self.SshPass = ""

    def pack(self):
        # 1. 앞부분 Packing
        part1 = struct.pack(self.FMT_1,
            self._encode_str(self.DataHandlerId, 40),
            self._encode_str(self.OldDataHandlerId, 40),
            self._encode_str(self.HostName, 40),
            self._encode_str(self.IpAddress, IP_ADDRESS_LEN),
            self.ListenPort, self.TimeMode, self.LogMode, self.OperMode,
            self.LoadingInterval, self.BypassListenPort,
            self._encode_str(self.DbUserId, 16),
            self._encode_str(self.DbPassword, 16),
            self._encode_str(self.DbName, 16),
            self.RequestStatus, self.SettingStatus, self.CurStatus
        )
        
        # 2. 중간 중첩 구조체 Packing
        part2 = self.TargetIpInfoList.pack()
        
        # 3. 뒷부분 Packing
        part3 = struct.pack(self.FMT_2,
            self.RunMode, self.LogCycle,
            self._encode_str(self.SshID, 40),
            self._encode_str(self.SshPass, 40)
        )
        
        return part1 + part2 + part3

    @classmethod
    def unpack(cls, data):
        obj = cls()
        offset = 0
        
        # 1. 앞부분 Unpack
        if len(data) < cls.SIZE_1: return None
        t1 = struct.unpack(cls.FMT_1, data[:cls.SIZE_1])
        
        obj.DataHandlerId = cls._decode_str(t1[0])
        obj.OldDataHandlerId = cls._decode_str(t1[1])
        obj.HostName = cls._decode_str(t1[2])
        obj.IpAddress = cls._decode_str(t1[3])
        obj.ListenPort, obj.TimeMode, obj.LogMode = t1[4], t1[5], t1[6]
        obj.OperMode, obj.LoadingInterval, obj.BypassListenPort = t1[7], t1[8], t1[9]
        obj.DbUserId = cls._decode_str(t1[10])
        obj.DbPassword = cls._decode_str(t1[11])
        obj.DbName = cls._decode_str(t1[12])
        obj.RequestStatus, obj.SettingStatus, obj.CurStatus = t1[13], t1[14], t1[15]
        
        offset += cls.SIZE_1
        
        # 2. 중간 중첩 구조체 Unpack
        # AsTargetIpInfoListT의 전체 크기를 계산하거나 unpack 메서드에 위임
        # 여기서는 남은 데이터를 넘겨주면 unpack 내부에서 필요한 만큼만 읽음
        obj.TargetIpInfoList = AsTargetIpInfoListT.unpack(data[offset:])
        
        # AsTargetIpInfoListT의 실제 바이트 크기 계산 (Header + 20 * Item)
        list_size = AsTargetIpInfoListT.HEADER_SIZE + (AsTargetIpInfoListT.MAX_ARRAY_SIZE * AsTargetIpInfoT.SIZE)
        offset += list_size
        
        # 3. 뒷부분 Unpack
        if len(data) < offset + cls.SIZE_2: return obj # 데이터 부족 시 부분 반환
        t3 = struct.unpack(cls.FMT_2, data[offset : offset + cls.SIZE_2])
        
        obj.RunMode = t3[0]
        obj.LogCycle = t3[1]
        obj.SshID = cls._decode_str(t3[2])
        obj.SshPass = cls._decode_str(t3[3])
        
        return obj
    
# -------------------------------------------------------
# AS_COMMAND_AUTHORITY_INFO_T Structure
# -------------------------------------------------------
class AsCommandAuthorityInfoT(BasePacket):
    """
    typedef struct {
        char    Id[NAME_LEN];
        char    OldId[NAME_LEN]; // for update
        int     MaxCmdQueue;
        int     Priority;
        int     LogMode;
        int     AckMode;
        char    Description[NAME_LEN];
        int     RequestStatus;
        int     MaxSessionCnt;
    } AS_COMMAND_AUTHORITY_INFO_T;
    """
    
    # NAME_LEN=40 가정
    # 40s(Id) 40s(OldId) I(Max) I(Prio) I(Log) I(Ack) 40s(Desc) I(Req) I(MaxSess)
    FMT = f"!{NAME_LEN}s{NAME_LEN}sIIII{NAME_LEN}sII"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.Id = ""
        self.OldId = ""
        self.MaxCmdQueue = 0
        self.Priority = 0
        self.LogMode = 0
        self.AckMode = 0
        self.Description = ""
        self.RequestStatus = 0
        self.MaxSessionCnt = 0

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.Id, NAME_LEN),
            self._encode_str(self.OldId, NAME_LEN),
            self.MaxCmdQueue,
            self.Priority,
            self.LogMode,
            self.AckMode,
            self._encode_str(self.Description, NAME_LEN),
            self.RequestStatus,
            self.MaxSessionCnt
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.Id = cls._decode_str(t[0])
        obj.OldId = cls._decode_str(t[1])
        obj.MaxCmdQueue = t[2]
        obj.Priority = t[3]
        obj.LogMode = t[4]
        obj.AckMode = t[5]
        obj.Description = cls._decode_str(t[6])
        obj.RequestStatus = t[7]
        obj.MaxSessionCnt = t[8]
        
        return obj
    
# -------------------------------------------------------
# AS_DATA_HANDLER_INIT_T Structure
# -------------------------------------------------------
class AsDataHandlerInitT(BasePacket):
    """
    typedef struct {
        char    DataHandlerId[40];
        int     InitMode;
        char    Desc[256];
        char    Reserve[30];
    } AS_DATA_HANDLER_INIT_T;
    """
    # 40s(Id) I(Mode) 256s(Desc) 30s(Reserve)
    FMT = "!40sI256s30s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.DataHandlerId = ""
        self.InitMode = 0
        self.Desc = ""
        self.Reserve = ""

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.DataHandlerId, 40),
            self.InitMode,
            self._encode_str(self.Desc, 256),
            self._encode_str(self.Reserve, 30)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.DataHandlerId = cls._decode_str(t[0])
        obj.InitMode = t[1]
        obj.Desc = cls._decode_str(t[2])
        obj.Reserve = cls._decode_str(t[3])
        return obj
    
# -------------------------------------------------------
# AS_DATA_ROUTING_INIT_T Structure
# -------------------------------------------------------
class AsDataRoutingInitT(BasePacket):
    """
    typedef struct {
        char    DataHandlerId[40];
        int     InitMode;
        char    Desc[256];
        char    Reserve[30];
    } AS_DATA_ROUTING_INIT_T;
    """
    # 40s(Id) I(Mode) 256s(Desc) 30s(Reserve)
    FMT = "!40sI256s30s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.DataHandlerId = ""
        self.InitMode = 0
        self.Desc = ""
        self.Reserve = ""

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.DataHandlerId, 40),
            self.InitMode,
            self._encode_str(self.Desc, 256),
            self._encode_str(self.Reserve, 30)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.DataHandlerId = cls._decode_str(t[0])
        obj.InitMode = t[1]
        obj.Desc = cls._decode_str(t[2])
        obj.Reserve = cls._decode_str(t[3])
        return obj
    
# -------------------------------------------------------
# AS_SUB_PROC_INFO_T Structure
# -------------------------------------------------------
class AsSubProcInfoT(BasePacket):
    """
    typedef struct {
        int     ProcId;
        char    ProcIdStr[40];
        char    OldProcIdStr[40];
        int     ParentProc;         //0 : server, 1 : manager
        char    ParentId[40];
        char    IpAddress[20];
        char    HostName[40];
        int     SettingStatus;
        int     CurStatus;
        int     RequestStatus;
        int     LogCycle;           //0 : Day, 1 : Hour
        char    Description[MAX_DESC_LEN]; // 500
        char    BinaryName[40];
        char    Args[3000];
        char    Reserve[40];
    } AS_SUB_PROC_INFO_T;
    """
    
    # Format String
    # I 40s 40s I 40s 20s 40s I I I I 500s 40s 3000s 40s
    FMT = f"!I40s40sI40s20s40sIIII{MAX_DESC_LEN}s40s3000s40s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ProcId = 0
        self.ProcIdStr = ""
        self.OldProcIdStr = ""
        self.ParentProc = 0
        self.ParentId = ""
        self.IpAddress = ""
        self.HostName = ""
        self.SettingStatus = 0
        self.CurStatus = 0
        self.RequestStatus = 0
        self.LogCycle = 0
        self.Description = ""
        self.BinaryName = ""
        self.Args = ""
        self.Reserve = ""

    def pack(self):
        return struct.pack(self.FMT,
            self.ProcId,
            self._encode_str(self.ProcIdStr, 40),
            self._encode_str(self.OldProcIdStr, 40),
            self.ParentProc,
            self._encode_str(self.ParentId, 40),
            self._encode_str(self.IpAddress, 20),
            self._encode_str(self.HostName, 40),
            self.SettingStatus,
            self.CurStatus,
            self.RequestStatus,
            self.LogCycle,
            self._encode_str(self.Description, MAX_DESC_LEN),
            self._encode_str(self.BinaryName, 40),
            self._encode_str(self.Args, 3000),
            self._encode_str(self.Reserve, 40)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.ProcId = t[0]
        obj.ProcIdStr = cls._decode_str(t[1])
        obj.OldProcIdStr = cls._decode_str(t[2])
        obj.ParentProc = t[3]
        obj.ParentId = cls._decode_str(t[4])
        obj.IpAddress = cls._decode_str(t[5])
        obj.HostName = cls._decode_str(t[6])
        obj.SettingStatus = t[7]
        obj.CurStatus = t[8]
        obj.RequestStatus = t[9]
        obj.LogCycle = t[10]
        obj.Description = cls._decode_str(t[11])
        obj.BinaryName = cls._decode_str(t[12])
        obj.Args = cls._decode_str(t[13])
        obj.Reserve = cls._decode_str(t[14])
        return obj
    
# -------------------------------------------------------
# AS_ROUTER_PORT_INFO_T Structure
# -------------------------------------------------------
class AsRouterPortInfoT(BasePacket):
    """
    typedef struct {
        int RouterPortNo;
    } AS_ROUTER_PORT_INFO_T;
    """
    FMT = "!i" # int(4)
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.RouterPortNo = 0

    def pack(self):
        return struct.pack(self.FMT, self.RouterPortNo)

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.RouterPortNo = t[0]
        return obj
    
# -------------------------------------------------------
# AS_LOG_TAIL_DATA_REQ_T Structure
# -------------------------------------------------------
class AsLogTailDataReqT(BasePacket):
    """
    typedef struct {
        char    ManagerId[40];
        int     ProcessType;
        char    ProcessId[80];
        int     LogCycle;
    } AS_LOG_TAIL_DATA_REQ_T;
    """
    
    # Format String: 40s I 80s I
    # ManagerId(40), ProcessType(4), ProcessId(80), LogCycle(4)
    FMT = "!40sI80sI"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ManagerId = ""
        self.ProcessType = 0
        self.ProcessId = ""
        self.LogCycle = 0

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.ManagerId, 40),
            self.ProcessType,
            self._encode_str(self.ProcessId, 80),
            self.LogCycle
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.ManagerId = cls._decode_str(t[0])
        obj.ProcessType = t[1]
        obj.ProcessId = cls._decode_str(t[2])
        obj.LogCycle = t[3]
        return obj
    
# -------------------------------------------------------
# AS_LOG_TAIL_DATA_RES_T Structure
# -------------------------------------------------------
class AsLogTailDataResT(BasePacket):
    """
    typedef struct {
        int     ProcessType;
        int     ResMode; //0:NOK, 1:OK
        char    ProcessId[80];
        char    Result[1024];
    } AS_LOG_TAIL_DATA_RES_T;
    """
    
    # Format String: I I 80s 1024s
    FMT = "!II80s1024s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ProcessType = 0
        self.ResMode = 0
        self.ProcessId = ""
        self.Result = ""

    def pack(self):
        return struct.pack(self.FMT,
            self.ProcessType,
            self.ResMode,
            self._encode_str(self.ProcessId, 80),
            self._encode_str(self.Result, 1024)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.ProcessType = t[0]
        obj.ResMode = t[1]
        obj.ProcessId = cls._decode_str(t[2])
        obj.Result = cls._decode_str(t[3])
        return obj
    
# -------------------------------------------------------
# AS_LOG_TAIL_DATA_T Structure
# -------------------------------------------------------
class AsLogTailDataT(BasePacket):
    """
    typedef struct {
        char    TailData[MAX_MSG];
    } AS_LOG_TAIL_DATA_T;
    """
    
    # Format String: MAX_MSG bytes string
    FMT = f"!{MAX_MSG}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self, tail_data=""):
        self.TailData = tail_data

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.TailData, MAX_MSG)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.TailData = cls._decode_str(t[0])
        return obj
    
# -------------------------------------------------------
# AS_HOT_TAIL_DATA_REQ_T Structure
# -------------------------------------------------------
class AsHotTailDataReqT(BasePacket):
    """
    typedef struct {
        char    ProcessName[80];
    } AS_HOT_TAIL_DATA_REQ_T;
    """
    
    # Format String: 80s
    FMT = "!80s"
    SIZE = struct.calcsize(FMT)

    def __init__(self, proc_name=""):
        self.ProcessName = proc_name

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.ProcessName, 80)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        return cls(cls._decode_str(t[0]))
    
# -------------------------------------------------------
# AS_HOT_TAIL_DATA_RES_T Structure
# -------------------------------------------------------
class AsHotTailDataResT(BasePacket):
    """
    typedef struct {
        int     ResMode; //0:NOK, 1:OK
        char    ProcessName[80];
        char    Result[1024];
    } AS_HOT_TAIL_DATA_RES_T;
    """
    
    # Format String: I 80s 1024s
    FMT = "!I80s1024s"
    SIZE = struct.calcsize(FMT)

    def __init__(self, res_mode=0, proc_name="", result=""):
        self.ResMode = res_mode
        self.ProcessName = proc_name
        self.Result = result

    def pack(self):
        return struct.pack(self.FMT,
            self.ResMode,
            self._encode_str(self.ProcessName, 80),
            self._encode_str(self.Result, 1024)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        return cls(t[0], cls._decode_str(t[1]), cls._decode_str(t[2]))
    
# -------------------------------------------------------
# AS_HOT_TAIL_DATA_T Structure
# -------------------------------------------------------
class AsHotTailDataT(BasePacket):
    """
    typedef struct {
        char    TailData[MAX_MSG];
    } AS_HOT_TAIL_DATA_T;
    """
    
    # Format String: MAX_MSG bytes string
    FMT = f"!{MAX_MSG}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self, tail_data=""):
        self.TailData = tail_data

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.TailData, MAX_MSG)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        return cls(cls._decode_str(t[0]))
    
# -------------------------------------------------------
# SYNCDB_KIND Enum
# -------------------------------------------------------
UNDEFINDED_SYNC     = -1
ALL_SYNC            = 1
ORB_SYNC            = 2
CMD_SYNC            = 3
RULE_SYNC           = 4
ETC_SYNC            = 5
SESSIONIDENT_SYNC   = 6
EVENTCONSUMER_SYNC  = 7
JUNCTION_SYNC       = 8

# -------------------------------------------------------
# AS_SERVER_INFO_T Structure
# -------------------------------------------------------
class AsServerInfoT(BasePacket):
    """
    typedef struct {
        char    ServerName[40];
        char    ActDbUser[40];
        char    ActPasswd[40];
        char    ActDbTns[40];
    } AS_SERVER_INFO_T;
    """
    
    # Format String: 40s 40s 40s 40s
    FMT = "!40s40s40s40s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ServerName = ""
        self.ActDbUser = ""
        self.ActPasswd = ""
        self.ActDbTns = ""

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.ServerName, 40),
            self._encode_str(self.ActDbUser, 40),
            self._encode_str(self.ActPasswd, 40),
            self._encode_str(self.ActDbTns, 40)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.ServerName = cls._decode_str(t[0])
        obj.ActDbUser = cls._decode_str(t[1])
        obj.ActPasswd = cls._decode_str(t[2])
        obj.ActDbTns = cls._decode_str(t[3])
        return obj
    
# -------------------------------------------------------
# AS_DB_SYNC_KIND_T Structure
# -------------------------------------------------------
class AsDbSyncKindT(BasePacket):
    """
    typedef struct {
        int     SyncKind;
    } AS_DB_SYNC_KIND_T;
    """
    
    # Format String: I (4 bytes integer)
    FMT = "!I"
    SIZE = struct.calcsize(FMT)

    def __init__(self, sync_kind=0):
        self.SyncKind = sync_kind

    def pack(self):
        return struct.pack(self.FMT, self.SyncKind)

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        return cls(t[0])
    
# -------------------------------------------------------
# AS_DB_SYNC_INFO_T Structure
# -------------------------------------------------------
class AsDbSyncInfoT(BasePacket):
    """
    typedef struct {
        char    TableName[40];
        char    SyncTime[25];
    } AS_DB_SYNC_INFO_T;
    """
    
    # Format String: 40s 25s
    FMT = "!40s25s"
    SIZE = struct.calcsize(FMT)

    def __init__(self, table_name="", sync_time=""):
        self.TableName = table_name
        self.SyncTime = sync_time

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.TableName, 40),
            self._encode_str(self.SyncTime, 25)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.TableName = cls._decode_str(t[0])
        obj.SyncTime = cls._decode_str(t[1])
        return obj
    
MAX_DB_SYNC_INFO_CNT = 50

# -------------------------------------------------------
# AS_DB_SYNC_INFO_LIST_T Structure
# -------------------------------------------------------
class AsDbSyncInfoListT(BasePacket):
    """
    typedef struct {
        char                ActiveSvrName[30];
        char                StandbySvrName[30];
        char                StandbyDb[30];
        int                 Count;
        AS_DB_SYNC_INFO_T   InfoList[MAX_DB_SYNC_INFO_CNT]; // 50
    } AS_DB_SYNC_INFO_LIST_T;
    """
    
    # Constants
    MAX_ARRAY_SIZE = 50
    
    # Header Format: 30s 30s 30s I
    HEADER_FMT = "!30s30s30sI"
    HEADER_SIZE = struct.calcsize(HEADER_FMT)

    def __init__(self):
        self.ActiveSvrName = ""
        self.StandbySvrName = ""
        self.StandbyDb = ""
        self.Count = 0
        self.InfoList = [] # List of AsDbSyncInfoT

    def pack(self):
        # 리스트 개수 갱신
        self.Count = len(self.InfoList)
        if self.Count > self.MAX_ARRAY_SIZE:
            self.Count = self.MAX_ARRAY_SIZE

        # 1. Header Packing
        packed_data = struct.pack(self.HEADER_FMT,
            self._encode_str(self.ActiveSvrName, 30),
            self._encode_str(self.StandbySvrName, 30),
            self._encode_str(self.StandbyDb, 30),
            self.Count
        )

        # 2. Array Packing (Fixed size 50)
        # C++ 구조체 크기 호환을 위해 빈 공간은 더미 데이터로 채움
        for i in range(self.MAX_ARRAY_SIZE):
            if i < self.Count:
                packed_data += self.InfoList[i].pack()
            else:
                packed_data += AsDbSyncInfoT().pack()
        
        return packed_data

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.HEADER_SIZE: return None
        
        obj = cls()
        # 1. Header Unpack
        t = struct.unpack(cls.HEADER_FMT, data[:cls.HEADER_SIZE])
        obj.ActiveSvrName = cls._decode_str(t[0])
        obj.StandbySvrName = cls._decode_str(t[1])
        obj.StandbyDb = cls._decode_str(t[2])
        obj.Count = t[3]

        # Safety Check
        valid_count = min(obj.Count, cls.MAX_ARRAY_SIZE)
        
        # 2. Array Unpack
        offset = cls.HEADER_SIZE
        item_size = AsDbSyncInfoT.SIZE

        for _ in range(valid_count):
            if offset + item_size > len(data): break
            item_data = data[offset : offset + item_size]
            obj.InfoList.append(AsDbSyncInfoT.unpack(item_data))
            offset += item_size
            
        return obj
    
MAX_SOCKET_INFO_CNT		= 25

# ... (기존 Constants 아래에 추가) ...

MAX_SOCKET_INFO_CNT = 25
SOCK_INFO_LISTENER_NAME_MAX_LEN = 40

# ==========================================================================
# [SOCKET INFO STRUCTURES]
# ==========================================================================

# -------------------------------------------------------
# FR_SOCKET_INFO_T Structure (Dependency)
# -------------------------------------------------------
class FrSocketInfoT(BasePacket):
    """
    typedef struct {
        char    SessionName[40];
        char    ListenerName[40];
        char    Address[40];
        char    SessionTime[20];
        int     Fd;
        int     PortNo;
        short   SocketMode;
        short   UseType;
        short   WriterableStatus;
        short   DetailTime;
    } FR_SOCKET_INFO_T;
    """
    # 40s 40s 40s 20s I I H H H H
    # I(4) + I(4) + H(2) + H(2) + H(2) + H(2) = 16 bytes
    # Strings: 40+40+40+20 = 140 bytes
    # Total = 156 bytes
    FMT = "!40s40s40s20sIIHHHH"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.SessionName = ""
        self.ListenerName = ""
        self.Address = ""
        self.SessionTime = ""
        self.Fd = 0
        self.PortNo = 0
        self.SocketMode = 0
        self.UseType = 0
        self.WriterableStatus = 0
        self.DetailTime = 0

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.SessionName, 40),
            self._encode_str(self.ListenerName, 40),
            self._encode_str(self.Address, 40),
            self._encode_str(self.SessionTime, 20),
            self.Fd, self.PortNo,
            self.SocketMode, self.UseType,
            self.WriterableStatus, self.DetailTime
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.SessionName = cls._decode_str(t[0])
        obj.ListenerName = cls._decode_str(t[1])
        obj.Address = cls._decode_str(t[2])
        obj.SessionTime = cls._decode_str(t[3])
        obj.Fd, obj.PortNo = t[4], t[5]
        obj.SocketMode, obj.UseType, obj.WriterableStatus, obj.DetailTime = t[6], t[7], t[8], t[9]
        return obj

# -------------------------------------------------------
# AS_SOCKET_INFO_LIST_T Structure
# -------------------------------------------------------
class AsSocketInfoListT(BasePacket):
    """
    typedef struct {
        int                 Size;
        int                 Status;
        char                GroupName[SOCK_INFO_LISTENER_NAME_MAX_LEN];
        FR_SOCKET_INFO_T    InfoList[MAX_SOCKET_INFO_CNT];
    } AS_SOCKET_INFO_LIST_T;
    """
    
    # Header: I I 40s
    HEADER_FMT = f"!II{SOCK_INFO_LISTENER_NAME_MAX_LEN}s"
    HEADER_SIZE = struct.calcsize(HEADER_FMT)
    
    # Fixed Array Size: 25
    MAX_ARRAY_SIZE = MAX_SOCKET_INFO_CNT

    def __init__(self):
        self.Size = 0
        self.Status = 0
        self.GroupName = ""
        self.InfoList = [] # List of FrSocketInfoT

    def pack(self):
        self.Size = len(self.InfoList)
        if self.Size > self.MAX_ARRAY_SIZE:
            self.Size = self.MAX_ARRAY_SIZE

        # 1. Header
        packed_data = struct.pack(self.HEADER_FMT,
            self.Size, self.Status,
            self._encode_str(self.GroupName, SOCK_INFO_LISTENER_NAME_MAX_LEN)
        )

        # 2. Array Padding
        for i in range(self.MAX_ARRAY_SIZE):
            if i < self.Size:
                packed_data += self.InfoList[i].pack()
            else:
                packed_data += FrSocketInfoT().pack() # Dummy
        
        return packed_data

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.HEADER_SIZE: return None
        
        obj = cls()
        t = struct.unpack(cls.HEADER_FMT, data[:cls.HEADER_SIZE])
        obj.Size = t[0]
        obj.Status = t[1]
        obj.GroupName = cls._decode_str(t[2])

        valid_count = min(obj.Size, cls.MAX_ARRAY_SIZE)
        offset = cls.HEADER_SIZE
        item_size = FrSocketInfoT.SIZE

        for _ in range(valid_count):
            if offset + item_size > len(data): break
            item_data = data[offset : offset + item_size]
            obj.InfoList.append(FrSocketInfoT.unpack(item_data))
            offset += item_size
            
        return obj

# -------------------------------------------------------
# FR_SOCKET_CHECK_REQ_T Structure
# -------------------------------------------------------
class FrSocketCheckReqT(BasePacket):
    """
    typedef struct {
        int                 CheckSec;
        int                 CheckMiscroSec;
        FR_SOCKET_INFO_T    Info;
    } FR_SOCKET_CHECK_REQ_T;
    """
    
    # I I + Struct Body
    HEADER_FMT = "!II"
    HEADER_SIZE = struct.calcsize(HEADER_FMT)

    def __init__(self):
        self.CheckSec = 0
        self.CheckMiscroSec = 0
        self.Info = FrSocketInfoT()

    def pack(self):
        header = struct.pack(self.HEADER_FMT, self.CheckSec, self.CheckMiscroSec)
        return header + self.Info.pack()

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.HEADER_SIZE: return None
        
        obj = cls()
        obj.CheckSec, obj.CheckMiscroSec = struct.unpack(cls.HEADER_FMT, data[:cls.HEADER_SIZE])
        
        # 남은 데이터로 Info 구조체 파싱
        obj.Info = FrSocketInfoT.unpack(data[cls.HEADER_SIZE:])
        return obj
    
# -------------------------------------------------------
# AS_SOCKET_STATUS_REQ_T Structure
# -------------------------------------------------------
class AsSocketStatusReqT(BasePacket):
    """
    typedef struct {
        int IsWriterableCheck; // 0, 1
        int CheckSec;
        int CheckMiscroSec;
    } AS_SOCKET_STATUS_REQ_T;
    """
    
    # Format String: I I I (3 integers)
    # int(4) * 3 = 12 bytes
    FMT = "!III"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.IsWriterableCheck = 0
        self.CheckSec = 0
        self.CheckMiscroSec = 0

    def pack(self):
        return struct.pack(self.FMT,
            self.IsWriterableCheck,
            self.CheckSec,
            self.CheckMiscroSec
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.IsWriterableCheck = t[0]
        obj.CheckSec = t[1]
        obj.CheckMiscroSec = t[2]
        return obj
    
# -------------------------------------------------------
# AS_SYSTEM_INFO_T Structure
# -------------------------------------------------------
class AsSystemInfoT(BasePacket):
    """
    typedef struct {
        int     ProcessType;
        char    HostName[80];
        char    HostIp[20];
        char    ProcessId[80];
        int     m_MaxOpenableFd;
        int     m_MaxRecvBuf;
        int     m_MaxSendBuf;
    } AS_SYSTEM_INFO_T;
    """
    
    # Format String: I 80s 20s 80s I I I
    FMT = "!I80s20s80sIII"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ProcessType = 0
        self.HostName = ""
        self.HostIp = ""
        self.ProcessId = ""
        self.m_MaxOpenableFd = 0
        self.m_MaxRecvBuf = 0
        self.m_MaxSendBuf = 0

    def pack(self):
        return struct.pack(self.FMT,
            self.ProcessType,
            self._encode_str(self.HostName, 80),
            self._encode_str(self.HostIp, 20),
            self._encode_str(self.ProcessId, 80),
            self.m_MaxOpenableFd,
            self.m_MaxRecvBuf,
            self.m_MaxSendBuf
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.ProcessType = t[0]
        obj.HostName = cls._decode_str(t[1])
        obj.HostIp = cls._decode_str(t[2])
        obj.ProcessId = cls._decode_str(t[3])
        obj.m_MaxOpenableFd = t[4]
        obj.m_MaxRecvBuf = t[5]
        obj.m_MaxSendBuf = t[6]
        return obj
    
# -------------------------------------------------------
# AS_SESSION_CFG_T Structure
# -------------------------------------------------------
class AsSessionCfgT(BasePacket):
    """
    typedef struct {
        int     SessionType;
        int     SessionBufSize;
        int     SocketSendBuf;
        int     SocketRecvBuf;
        int     CheckWriteFlag;
        int     SocketTimeout; //unit is microsec
        int     CheckDisConCntFlag;
        int     MaxDisConCount;
    } AS_SESSION_CFG_T;
    """
    
    # Format String: 8 integers
    # 4 * 8 = 32 bytes
    FMT = "!IIIIIIII"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.SessionType = 0
        self.SessionBufSize = 0
        self.SocketSendBuf = 0
        self.SocketRecvBuf = 0
        self.CheckWriteFlag = 0
        self.SocketTimeout = 0
        self.CheckDisConCntFlag = 0
        self.MaxDisConCount = 0

    def pack(self):
        return struct.pack(self.FMT,
            self.SessionType,
            self.SessionBufSize,
            self.SocketSendBuf,
            self.SocketRecvBuf,
            self.CheckWriteFlag,
            self.SocketTimeout,
            self.CheckDisConCntFlag,
            self.MaxDisConCount
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.SessionType = t[0]
        obj.SessionBufSize = t[1]
        obj.SocketSendBuf = t[2]
        obj.SocketRecvBuf = t[3]
        obj.CheckWriteFlag = t[4]
        obj.SocketTimeout = t[5]
        obj.CheckDisConCntFlag = t[6]
        obj.MaxDisConCount = t[7]
        return obj
    
# -------------------------------------------------------
# AS_MMC_PARAMETER_T Structure (Helper for Request)
# -------------------------------------------------------
class AsMmcParameterT(BasePacket):
    """
    typedef struct {
        int     sequence;
        char    value[MMC_VAL_LEN]; // 256
    } AS_MMC_PARAMETER_T;
    """
    FMT = f"!I{MMC_VAL_LEN}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self, seq=0, val=""):
        self.sequence = seq
        self.value = val

    def pack(self):
        return struct.pack(self.FMT, self.sequence, self._encode_str(self.value, MMC_VAL_LEN))

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data)
        return cls(t[0], cls._decode_str(t[1]))

# -------------------------------------------------------
# AS_MMC_REQUEST_T Structure
# -------------------------------------------------------
class AsMmcRequestT(BasePacket):
    """
    typedef struct {
        int                     id;
        char                    ne [EQUIP_ID_LEN];      // 40
        AS_MMC_TYPE             type;                   // int
        int                     referenceId;
        AS_MMC_INTERFACE        interfaces;             // int
        AS_MMC_RESPONSE_MODE    responseMode;           // int
        AS_MMC_PUBLISH_MODE     publishMode;            // int
        AS_MMC_COLLECT_MODE     collectMode;            // int
        char                    mmc [MMC_CMD_LEN_EX];   // 256 (CommType.py 기준)
        char                    userid [USER_ID_LEN];   // 20
        char                    display [IP_ADDRESS_LEN]; // 16
        int                     cmdDelayTime;
        int                     retryNo;
        int                     curRetryNo;
        int                     parameterNo;
        int                     priority;
        int                     logMode;
        AS_MMC_PARAMETER_T      parameters [20];        // Array
        char                    Reserved[100];
    } AS_MMC_REQUEST_T;
    """
    
    # Header Format
    # I 40s I I I I I I 256s 20s 16s I I I I I I
    HEADER_FMT = (f"!I{EQUIP_ID_LEN}sIIIIII{MMC_CMD_LEN_EX}s{USER_ID_LEN}s"
                  f"{IP_ADDRESS_LEN}sIIIIII")
    HEADER_SIZE = struct.calcsize(HEADER_FMT)
    
    # Parameters Array Size
    PARAM_MAX = 20
    
    # Footer (Reserved)
    FOOTER_FMT = "!100s"
    FOOTER_SIZE = struct.calcsize(FOOTER_FMT)

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
        # 1. Header
        packed_data = struct.pack(self.HEADER_FMT,
            self.id, self._encode_str(self.ne, EQUIP_ID_LEN),
            self.type, self.referenceId, self.interfaces,
            self.responseMode, self.publishMode, self.collectMode,
            self._encode_str(self.mmc, MMC_CMD_LEN_EX),
            self._encode_str(self.userid, USER_ID_LEN),
            self._encode_str(self.display, IP_ADDRESS_LEN),
            self.cmdDelayTime, self.retryNo, self.curRetryNo,
            self.parameterNo, self.priority, self.logMode
        )
        
        # 2. Parameters Array (Fixed 20)
        for i in range(self.PARAM_MAX):
            if i < len(self.parameters):
                packed_data += self.parameters[i].pack()
            else:
                packed_data += AsMmcParameterT().pack() # Padding
                
        # 3. Footer
        packed_data += struct.pack(self.FOOTER_FMT, self._encode_str(self.Reserved, 100))
        
        return packed_data

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.HEADER_SIZE: return None
        
        obj = cls()
        offset = 0
        
        # 1. Header
        t = struct.unpack(cls.HEADER_FMT, data[:cls.HEADER_SIZE])
        obj.id = t[0]
        obj.ne = cls._decode_str(t[1])
        obj.type, obj.referenceId, obj.interfaces = t[2:5]
        obj.responseMode, obj.publishMode, obj.collectMode = t[5:8]
        obj.mmc = cls._decode_str(t[8])
        obj.userid = cls._decode_str(t[9])
        obj.display = cls._decode_str(t[10])
        obj.cmdDelayTime, obj.retryNo, obj.curRetryNo = t[11:14]
        obj.parameterNo, obj.priority, obj.logMode = t[14:17]
        
        offset += cls.HEADER_SIZE
        
        # 2. Parameters
        param_size = AsMmcParameterT.SIZE
        for _ in range(cls.PARAM_MAX):
            if offset + param_size > len(data): break
            p_data = data[offset : offset + param_size]
            obj.parameters.append(AsMmcParameterT.unpack(p_data))
            offset += param_size
            
        # 3. Footer
        if len(data) >= offset + cls.FOOTER_SIZE:
            t_foot = struct.unpack(cls.FOOTER_FMT, data[offset : offset + cls.FOOTER_SIZE])
            obj.Reserved = cls._decode_str(t_foot[0])
            
        return obj
    
# -------------------------------------------------------
# AS_MMC_REQUEST_OLD_T Structure
# -------------------------------------------------------
class AsMmcRequestOldT(BasePacket):
    """
    Legacy MMC Request Structure (mmc field length is 128)
    """
    # Header Format:
    # I 40s I I I I I I 128s 20s 16s I I I I I I
    # MMC_CMD_LEN = 128 (Defined in Constants)
    HEADER_FMT = (f"!I{EQUIP_ID_LEN}sIIIIII{MMC_CMD_LEN}s{USER_ID_LEN}s"
                  f"{IP_ADDRESS_LEN}sIIIIII")
    HEADER_SIZE = struct.calcsize(HEADER_FMT)
    
    PARAM_MAX = 20
    
    def __init__(self):
        self.id = 0
        self.ne = ""
        self.type = 0
        self.referenceId = 0
        self.interfaces = 0
        self.responseMode = 0
        self.publishMode = 0
        self.collectMode = 0
        self.mmc = "" # Short version (128)
        self.userid = ""
        self.display = ""
        self.cmdDelayTime = 0
        self.retryNo = 0
        self.curRetryNo = 0
        self.parameterNo = 0
        self.priority = 0
        self.logMode = 0
        self.parameters = [] # List of AsMmcParameterT

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.HEADER_SIZE: return None
        
        obj = cls()
        offset = 0
        
        # 1. Header
        t = struct.unpack(cls.HEADER_FMT, data[:cls.HEADER_SIZE])
        obj.id = t[0]
        obj.ne = cls._decode_str(t[1])
        obj.type, obj.referenceId, obj.interfaces = t[2:5]
        obj.responseMode, obj.publishMode, obj.collectMode = t[5:8]
        obj.mmc = cls._decode_str(t[8])
        obj.userid = cls._decode_str(t[9])
        obj.display = cls._decode_str(t[10])
        obj.cmdDelayTime, obj.retryNo, obj.curRetryNo = t[11:14]
        obj.parameterNo, obj.priority, obj.logMode = t[14:17]
        
        offset += cls.HEADER_SIZE
        
        # 2. Parameters
        param_size = AsMmcParameterT.SIZE
        for _ in range(cls.PARAM_MAX):
            if offset + param_size > len(data): break
            p_data = data[offset : offset + param_size]
            obj.parameters.append(AsMmcParameterT.unpack(p_data))
            offset += param_size
            
        return obj

# -------------------------------------------------------
# AS_MMC_GEN_COMMAND_T Structure
# -------------------------------------------------------
class AsMmcGenCommandT(BasePacket):
    """
    typedef struct {
        int                 genId;
        int                 commandId;
        int                 commandSetId;
        RESULT_MODE         resultMode; // Enum (int)
        char                mmc [MMC_CMD_LEN_EX];
        char                key [MMC_VAL_LEN];
        char                idString[MMC_CMD_LEN];
    } AS_MMC_GEN_COMMAND_T;
    """
    
    # Format String: 4 integers + 3 strings
    # I I I I 256s 256s 128s (상수 값 기준)
    FMT = f"!IIII{MMC_CMD_LEN_EX}s{MMC_VAL_LEN}s{MMC_CMD_LEN}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.genId = 0
        self.commandId = 0
        self.commandSetId = 0
        self.resultMode = 0 # FAIL=0, SUCCEED=1
        self.mmc = ""
        self.key = ""
        self.idString = ""

    def pack(self):
        return struct.pack(self.FMT,
            self.genId,
            self.commandId,
            self.commandSetId,
            self.resultMode,
            self._encode_str(self.mmc, MMC_CMD_LEN_EX),
            self._encode_str(self.key, MMC_VAL_LEN),
            self._encode_str(self.idString, MMC_CMD_LEN)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.genId = t[0]
        obj.commandId = t[1]
        obj.commandSetId = t[2]
        obj.resultMode = t[3]
        obj.mmc = cls._decode_str(t[4])
        obj.key = cls._decode_str(t[5])
        obj.idString = cls._decode_str(t[6])
        return obj
    
MAX_RESULT_MSG = 4080  # C++ Header: 4088 - 8
# -------------------------------------------------------
# AS_MMC_RESULT_T Structure
# -------------------------------------------------------
class AsMmcResultT(BasePacket):
    """
    typedef struct {
        int                 id;
        AS_MMC_RESULT_MODE  resultMode;
        char                result [MAX_RESULT_MSG]; // 4080
    } AS_MMC_RESULT_T;
    """
    
    # Format String: I I 4080s
    FMT = f"!II{MAX_RESULT_MSG}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self, id_val=0, result_mode=0, result=""):
        self.id = id_val
        self.resultMode = result_mode
        self.result = result

    def pack(self):
        return struct.pack(self.FMT,
            self.id,
            self.resultMode,
            self._encode_str(self.result, MAX_RESULT_MSG)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.id = t[0]
        obj.resultMode = t[1]
        obj.result = cls._decode_str(t[2])
        return obj
    
MMC_GEN_COMMAND_MAX	= 3
# -------------------------------------------------------
# AS_MMC_GEN_RESULT_T Structure
# -------------------------------------------------------
class AsMmcGenResultT(BasePacket):
    """
    typedef struct {
        int                     id;
        char                    ne[EQUIP_ID_LEN];
        AS_MMC_RESPONSE_MODE    responseMode;
        AS_MMC_PUBLISH_MODE     publishMode;
        AS_MMC_RESULT_MODE      resultMode;
        int                     commandNo;
        AS_MMC_GEN_COMMAND_T    commands[MMC_GEN_COMMAND_MAX]; // 3
        char                    ErrMsg[128];
        int                     cmdDelayTime;
    } AS_MMC_GEN_RESULT_T;
    """
    
    # Constants
    MMC_GEN_COMMAND_MAX = 3
    
    # 1. Header Format: id(I) ne(40s) resMode(I) pubMode(I) resultMode(I) cmdNo(I)
    # EQUIP_ID_LEN = 40
    HEADER_FMT = f"!I{EQUIP_ID_LEN}sIIII"
    HEADER_SIZE = struct.calcsize(HEADER_FMT)
    
    # 2. Commands Array: AsMmcGenCommandT * 3 (Handled in loop)
    
    # 3. Footer Format: ErrMsg(128s) delay(I)
    FOOTER_FMT = "!128sI"
    FOOTER_SIZE = struct.calcsize(FOOTER_FMT)

    def __init__(self):
        self.id = 0
        self.ne = ""
        self.responseMode = 0
        self.publishMode = 0
        self.resultMode = 0
        self.commandNo = 0
        self.commands = [] # List of AsMmcGenCommandT
        self.ErrMsg = ""
        self.cmdDelayTime = 0

    def pack(self):
        # 1. Header Packing
        packed_data = struct.pack(self.HEADER_FMT,
            self.id,
            self._encode_str(self.ne, EQUIP_ID_LEN),
            self.responseMode,
            self.publishMode,
            self.resultMode,
            self.commandNo
        )

        # 2. Commands Array Packing (Fixed size 3)
        # C++ 구조체 메모리 레이아웃을 맞추기 위해 빈 슬롯도 채워야 함
        for i in range(self.MMC_GEN_COMMAND_MAX):
            if i < len(self.commands):
                packed_data += self.commands[i].pack()
            else:
                packed_data += AsMmcGenCommandT().pack() # Dummy data
        
        # 3. Footer Packing
        packed_data += struct.pack(self.FOOTER_FMT,
            self._encode_str(self.ErrMsg, 128),
            self.cmdDelayTime
        )
        
        return packed_data

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.HEADER_SIZE: return None
        
        obj = cls()
        offset = 0
        
        # 1. Header Unpack
        t = struct.unpack(cls.HEADER_FMT, data[:cls.HEADER_SIZE])
        obj.id = t[0]
        obj.ne = cls._decode_str(t[1])
        obj.responseMode, obj.publishMode, obj.resultMode, obj.commandNo = t[2:6]
        
        offset += cls.HEADER_SIZE
        
        # 2. Commands Array Unpack
        cmd_size = AsMmcGenCommandT.SIZE
        for _ in range(cls.MMC_GEN_COMMAND_MAX):
            if offset + cmd_size > len(data): break
            
            cmd_data = data[offset : offset + cmd_size]
            # 리스트에는 모든 커맨드 객체를 다 넣거나, commandNo만큼만 사용할 수 있음.
            # 여기서는 구조체 복원 의미로 다 넣음.
            obj.commands.append(AsMmcGenCommandT.unpack(cmd_data))
            offset += cmd_size
            
        # 3. Footer Unpack
        if len(data) < offset + cls.FOOTER_SIZE: return obj
        
        t_foot = struct.unpack(cls.FOOTER_FMT, data[offset : offset + cls.FOOTER_SIZE])
        obj.ErrMsg = cls._decode_str(t_foot[0])
        obj.cmdDelayTime = t_foot[1]
        
        return obj
    
# -------------------------------------------------------
# AS_MMC_PUBLISH_T Structure
# -------------------------------------------------------
class AsMmcPublishT(BasePacket):
    """
    typedef struct {
        int                     id;
        char                    ne [EQUIP_ID_LEN];      // 40
        char                    mmc [MMC_CMD_LEN_EX];   // 256
        char                    idString[MMC_CMD_LEN];  // 128
        char                    key [MMC_VAL_LEN];      // 256
        AS_MMC_RESPONSE_MODE    responseMode;           // int
        AS_MMC_PUBLISH_MODE     publishMode;            // int
        int                     cmdDelayTime;
    } AS_MMC_PUBLISH_T;
    """
    
    # Format String Construction
    # I 40s 256s 128s 256s I I I
    FMT = f"!I{EQUIP_ID_LEN}s{MMC_CMD_LEN_EX}s{MMC_CMD_LEN}s{MMC_VAL_LEN}sIII"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.id = 0
        self.ne = ""
        self.mmc = ""
        self.idString = ""
        self.key = ""
        self.responseMode = 0
        self.publishMode = 0
        self.cmdDelayTime = 0

    def pack(self):
        return struct.pack(self.FMT,
            self.id,
            self._encode_str(self.ne, EQUIP_ID_LEN),
            self._encode_str(self.mmc, MMC_CMD_LEN_EX),
            self._encode_str(self.idString, MMC_CMD_LEN),
            self._encode_str(self.key, MMC_VAL_LEN),
            self.responseMode,
            self.publishMode,
            self.cmdDelayTime
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.id = t[0]
        obj.ne = cls._decode_str(t[1])
        obj.mmc = cls._decode_str(t[2])
        obj.idString = cls._decode_str(t[3])
        obj.key = cls._decode_str(t[4])
        obj.responseMode = t[5]
        obj.publishMode = t[6]
        obj.cmdDelayTime = t[7]
        return obj
    
MAX_RESULT_SIZE = 4068

# -------------------------------------------------------
# PK_FinderReq Structure
# -------------------------------------------------------
class PkFinderReq(BasePacket):
    """
    typedef struct{
        char    neId[32];       // NE ID
        char    neType[32];     // NE Type
        char    startTime[12];  // start time
        char    endTime[12];    // end time
        char    keyWord[64];    // key word
        char    hostname[16];
        char    connHistInfo[CONNECTOR_HIST_INFO_SIZE]; // Connector Change History
    } PK_FinderReq;
    """
    
    # 상수 계산 (MAX_MSG는 상단에 4096으로 정의됨)
    CONNECTOR_HIST_INFO_SIZE = MAX_MSG - 32 - 32 - 12 - 12 - 64 - 16
    
    # Format String: 32s 32s 12s 12s 64s 16s ...
    FMT = f"!32s32s12s12s64s16s{CONNECTOR_HIST_INFO_SIZE}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.neId = ""
        self.neType = ""
        self.startTime = ""
        self.endTime = ""
        self.keyWord = ""
        self.hostname = ""
        self.connHistInfo = ""

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.neId, 32),
            self._encode_str(self.neType, 32),
            self._encode_str(self.startTime, 12),
            self._encode_str(self.endTime, 12),
            self._encode_str(self.keyWord, 64),
            self._encode_str(self.hostname, 16),
            self._encode_str(self.connHistInfo, self.CONNECTOR_HIST_INFO_SIZE)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.neId = cls._decode_str(t[0])
        obj.neType = cls._decode_str(t[1])
        obj.startTime = cls._decode_str(t[2])
        obj.endTime = cls._decode_str(t[3])
        obj.keyWord = cls._decode_str(t[4])
        obj.hostname = cls._decode_str(t[5])
        obj.connHistInfo = cls._decode_str(t[6])
        return obj

# -------------------------------------------------------
# AS_CONNECTOR_PORT_INFO_REQ_T Structure
# -------------------------------------------------------
class AsConnectorPortInfoReqT(BasePacket):
    """
    typedef struct {
        char ConnectorId[NAME_LEN];
    } AS_CONNECTOR_PORT_INFO_REQ_T;
    """
    
    # Format String: 40s (NAME_LEN=40)
    FMT = f"!{NAME_LEN}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self, connector_id=""):
        self.ConnectorId = connector_id

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.ConnectorId, NAME_LEN)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        return cls(cls._decode_str(t[0]))
    
# -------------------------------------------------------
# AS_CMD_OPEN_PORT_T Structure
# -------------------------------------------------------
class AsCmdOpenPortT(BasePacket):
    """
    typedef struct {
        int     Id;
        int     Sequence;
        char    EquipId[NAME_LEN];      // 40
        char    AgentEquipId[NAME_LEN]; // 40
        char    Consumer[40];           // 40 (Fixed)
        char    Name[NAME_LEN];         // 40
        char    ConnectorId[NAME_LEN];  // 40
        char    IpAddress[IP_ADDRESS_LEN_EX]; // 16 or 40
        int     PortNo;
        char    PortPath[PATH_LEN];     // 100
        char    UserId[USER_ID_LEN];    // 20
        char    Password[PASSWORD_LEN]; // 20
        char    AsciiHeader[NAME_LEN];  // 40
        int     ProtocolType;
        int     PortType;
        int     GatFlag;
        int     CommandPortFlag;
        char    DnId[NAME_LEN];         // 40
    } AS_CMD_OPEN_PORT_T;
    """
    
    # Layout:
    # I I
    # NAME_LEN(40)s NAME_LEN(40)s 40s NAME_LEN(40)s NAME_LEN(40)s IP_ADDRESS_LEN_EX(16)s
    # I PATH_LEN(100)s USER_ID_LEN(20)s PASSWORD_LEN(20)s NAME_LEN(40)s
    # I I I I
    # NAME_LEN(40)s
    
    FMT = (f"!II{NAME_LEN}s{NAME_LEN}s40s{NAME_LEN}s{NAME_LEN}s{IP_ADDRESS_LEN_EX}s"
           f"I{PATH_LEN}s{USER_ID_LEN}s{PASSWORD_LEN}s{NAME_LEN}s"
           f"IIII{NAME_LEN}s")
           
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.Id = 0
        self.Sequence = 0
        self.EquipId = ""
        self.AgentEquipId = ""
        self.Consumer = ""
        self.Name = ""
        self.ConnectorId = ""
        self.IpAddress = ""
        self.PortNo = 0
        self.PortPath = ""
        self.UserId = ""
        self.Password = ""
        self.AsciiHeader = ""
        self.ProtocolType = 0
        self.PortType = 0
        self.GatFlag = 0
        self.CommandPortFlag = 0
        self.DnId = ""

    def pack(self):
        return struct.pack(self.FMT,
            self.Id,
            self.Sequence,
            self._encode_str(self.EquipId, NAME_LEN),
            self._encode_str(self.AgentEquipId, NAME_LEN),
            self._encode_str(self.Consumer, 40),
            self._encode_str(self.Name, NAME_LEN),
            self._encode_str(self.ConnectorId, NAME_LEN),
            self._encode_str(self.IpAddress, IP_ADDRESS_LEN_EX),
            self.PortNo,
            self._encode_str(self.PortPath, PATH_LEN),
            self._encode_str(self.UserId, USER_ID_LEN),
            self._encode_str(self.Password, PASSWORD_LEN),
            self._encode_str(self.AsciiHeader, NAME_LEN),
            self.ProtocolType,
            self.PortType,
            self.GatFlag,
            self.CommandPortFlag,
            self._encode_str(self.DnId, NAME_LEN)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.Id = t[0]
        obj.Sequence = t[1]
        obj.EquipId = cls._decode_str(t[2])
        obj.AgentEquipId = cls._decode_str(t[3])
        obj.Consumer = cls._decode_str(t[4])
        obj.Name = cls._decode_str(t[5])
        obj.ConnectorId = cls._decode_str(t[6])
        obj.IpAddress = cls._decode_str(t[7])
        obj.PortNo = t[8]
        obj.PortPath = cls._decode_str(t[9])
        obj.UserId = cls._decode_str(t[10])
        obj.Password = cls._decode_str(t[11])
        obj.AsciiHeader = cls._decode_str(t[12])
        obj.ProtocolType = t[13]
        obj.PortType = t[14]
        obj.GatFlag = t[15]
        obj.CommandPortFlag = t[16]
        obj.DnId = cls._decode_str(t[17])
        
        return obj
    
# -------------------------------------------------------
# AS_CMD_LOG_CONTROL_T Structure
# -------------------------------------------------------
class AsCmdLogControlT(BasePacket):
    """
    typedef struct {
        int             Id;
        int             ProcessType;
        LOG_CTL_TYPE    Type;           // enum -> int
        char            ManagerId[40];
        char            ProcessId[80];
        char            Package[128];
        char            Feature[128];
        int             Level;
    } AS_CMD_LOG_CONTROL_T;
    """
    
    # Format String Construction
    # I I I 40s 80s 128s 128s I
    FMT = "!III40s80s128s128sI"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.Id = 0
        self.ProcessType = 0
        self.Type = 0 # LOG_CTL_TYPE (GET_LOG_INFO=0, SET_LOG=1)
        self.ManagerId = ""
        self.ProcessId = ""
        self.Package = ""
        self.Feature = ""
        self.Level = 0

    def pack(self):
        return struct.pack(self.FMT,
            self.Id,
            self.ProcessType,
            self.Type,
            self._encode_str(self.ManagerId, 40),
            self._encode_str(self.ProcessId, 80),
            self._encode_str(self.Package, 128),
            self._encode_str(self.Feature, 128),
            self.Level
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.Id = t[0]
        obj.ProcessType = t[1]
        obj.Type = t[2]
        obj.ManagerId = cls._decode_str(t[3])
        obj.ProcessId = cls._decode_str(t[4])
        obj.Package = cls._decode_str(t[5])
        obj.Feature = cls._decode_str(t[6])
        obj.Level = t[7]
        return obj
    
# -------------------------------------------------------
# AS_LOG_STATUS_T Structure
# -------------------------------------------------------
class AsLogStatusT(BasePacket):
    """
    typedef struct {
        char        name[NAME_LEN];          // 40
        AS_STATUS   status;                  // 4 (Enum -> int)
        char        logs[4088-NAME_LEN-4];   // 4044
    } AS_LOG_STATUS_T;
    """
    
    # 로그 버퍼 크기 계산
    LOG_SIZE = 4088 - NAME_LEN - 4  # 4088 - 40 - 4 = 4044
    
    # Format String: 40s I 4044s
    FMT = f"!{NAME_LEN}sI{LOG_SIZE}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.name = ""
        self.status = 0 # AS_STATUS (LOG_ADD=0, LOG_DEL=1)
        self.logs = ""

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.name, NAME_LEN),
            self.status,
            self._encode_str(self.logs, self.LOG_SIZE)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.name = cls._decode_str(t[0])
        obj.status = t[1]
        obj.logs = cls._decode_str(t[2])
        return obj
    
# ... (기존 상수 섹션에 추가) ...
PS_TEXT_LEN = 512

# -------------------------------------------------------
# AS_PORT_STATUS_INFO_T Structure
# -------------------------------------------------------
class AsPortStatusInfoT(BasePacket):
    """
    typedef struct
    {
        char    Name[NAME_LEN];             // 40
        char    ManagerId[NAME_LEN];        // 40
        char    ConnectorId[NAME_LEN];      // 40
        char    AgentEquipId[EQUIP_ID_LEN]; // 40
        int     AgentPortNo;
        int     Sequence;
        int     ProtocolType;
        int     PortType;
        int     Status;
        char    EventTime[20];
        char    AdditionalText[PS_TEXT_LEN];// 512
    } AS_PORT_STATUS_INFO_T;
    """
    
    # Format String:
    # 40s 40s 40s 40s I I I I I 20s 512s
    FMT = f"!{NAME_LEN}s{NAME_LEN}s{NAME_LEN}s{EQUIP_ID_LEN}sIIIII20s{PS_TEXT_LEN}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.Name = ""
        self.ManagerId = ""
        self.ConnectorId = ""
        self.AgentEquipId = ""
        self.AgentPortNo = 0
        self.Sequence = 0
        self.ProtocolType = 0
        self.PortType = 0
        self.Status = 0
        self.EventTime = ""
        self.AdditionalText = ""

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.Name, NAME_LEN),
            self._encode_str(self.ManagerId, NAME_LEN),
            self._encode_str(self.ConnectorId, NAME_LEN),
            self._encode_str(self.AgentEquipId, EQUIP_ID_LEN),
            self.AgentPortNo,
            self.Sequence,
            self.ProtocolType,
            self.PortType,
            self.Status,
            self._encode_str(self.EventTime, 20),
            self._encode_str(self.AdditionalText, PS_TEXT_LEN)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.Name = cls._decode_str(t[0])
        obj.ManagerId = cls._decode_str(t[1])
        obj.ConnectorId = cls._decode_str(t[2])
        obj.AgentEquipId = cls._decode_str(t[3])
        obj.AgentPortNo = t[4]
        obj.Sequence = t[5]
        obj.ProtocolType = t[6]
        obj.PortType = t[7]
        obj.Status = t[8]
        obj.EventTime = cls._decode_str(t[9])
        obj.AdditionalText = cls._decode_str(t[10])
        return obj
    
# -------------------------------------------------------
# AS_PROCESS_STATUS_T Structure
# -------------------------------------------------------
class AsProcessStatusT(BasePacket):
    """
    typedef struct {
        char        ManagerId[NAME_LEN];    // 40
        char        ProcessId[NAME_LEN];    // 40
        int         Status;
        int         Pid;
        int         ProcessType;
        char        StartTime[DATE_STRING_LEN]; // 20
    } AS_PROCESS_STATUS_T;
    """
    
    # Format String: 40s 40s I I I 20s
    # NAME_LEN=40, DATE_STRING_LEN=20
    FMT = f"!{NAME_LEN}s{NAME_LEN}sIII{DATE_STRING_LEN}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ManagerId = ""
        self.ProcessId = ""
        self.Status = 0
        self.Pid = 0
        self.ProcessType = 0
        self.StartTime = ""

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.ManagerId, NAME_LEN),
            self._encode_str(self.ProcessId, NAME_LEN),
            self.Status,
            self.Pid,
            self.ProcessType,
            self._encode_str(self.StartTime, DATE_STRING_LEN)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.ManagerId = cls._decode_str(t[0])
        obj.ProcessId = cls._decode_str(t[1])
        obj.Status = t[2]
        obj.Pid = t[3]
        obj.ProcessType = t[4]
        obj.StartTime = cls._decode_str(t[5])
        return obj
    
# ... (상단 상수 정의에 추가) ...
PROCESS_STATUS_LIST_MAX = 20

# -------------------------------------------------------
# AS_PROCESS_STATUS_LIST_T Structure
# -------------------------------------------------------
class AsProcessStatusListT(BasePacket):
    """
    typedef struct {
        int id;
        int ProcStatusNo;
        AS_PROCESS_STATUS_T ProcStatus[PROCESS_STATUS_LIST_MAX]; // 20
    } AS_PROCESS_STATUS_LIST_T;
    """
    
    # Header: int(id) + int(count)
    HEADER_FMT = "!II"
    HEADER_SIZE = struct.calcsize(HEADER_FMT)
    
    MAX_ARRAY_SIZE = PROCESS_STATUS_LIST_MAX

    def __init__(self):
        self.id = 0
        self.ProcStatusNo = 0
        self.ProcStatus = [] # List of AsProcessStatusT

    def pack(self):
        # 개수 갱신
        self.ProcStatusNo = len(self.ProcStatus)
        if self.ProcStatusNo > self.MAX_ARRAY_SIZE:
            self.ProcStatusNo = self.MAX_ARRAY_SIZE
            
        # 1. Header
        packed_data = struct.pack(self.HEADER_FMT, self.id, self.ProcStatusNo)
        
        # 2. Array (Fixed 20)
        for i in range(self.MAX_ARRAY_SIZE):
            if i < self.ProcStatusNo:
                packed_data += self.ProcStatus[i].pack()
            else:
                packed_data += AsProcessStatusT().pack() # Dummy Padding
        
        return packed_data

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.HEADER_SIZE: return None
        
        obj = cls()
        # 1. Header
        obj.id, obj.ProcStatusNo = struct.unpack(cls.HEADER_FMT, data[:cls.HEADER_SIZE])
        
        valid_count = min(obj.ProcStatusNo, cls.MAX_ARRAY_SIZE)
        
        # 2. Array
        offset = cls.HEADER_SIZE
        item_size = AsProcessStatusT.SIZE
        
        for _ in range(valid_count):
            if offset + item_size > len(data): break
            
            item_data = data[offset : offset + item_size]
            obj.ProcStatus.append(AsProcessStatusT.unpack(item_data))
            
            offset += item_size
            
        return obj

# -------------------------------------------------------
# AS_ASCII_ACK_T Structure
# -------------------------------------------------------
class AsAsciiAckT(BasePacket):
    """
    typedef struct {
        int     Id;
        int     ResultMode; // 0: 실패, 1: 성공
        char    Result[MAX_RESULT_LEN];
    } AS_ASCII_ACK_T;
    """
    
    # Format String: I I 2000s
    # int(4) + int(4) + char[2000]
    FMT = f"!II{MAX_RESULT_LEN}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self, id_val=0, result_mode=0, result_msg=""):
        self.Id = id_val
        self.ResultMode = result_mode
        self.Result = result_msg

    def pack(self):
        return struct.pack(self.FMT,
            self.Id,
            self.ResultMode,
            self._encode_str(self.Result, MAX_RESULT_LEN)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        # t[0]: Id, t[1]: ResultMode, t[2]: Result(bytes)
        return cls(t[0], t[1], cls._decode_str(t[2]))
    
PARSED_DATA_SIZE = MAX_MSG - EQUIP_ID_LEN - EVENT_ID_LEN - EVENT_ID_LEN - MMC_CMD_LEN - (4 + 2*5)
# 4096 - 40 - 20 - 20 - 128 - 14 = 3874 bytes (예시)

PARSED_DATA_KEY_SIZE = 60
PARSED_DATA_SEG_BLK_SIZE = PARSED_DATA_SIZE - PARSED_DATA_KEY_SIZE

# -------------------------------------------------------
# AS_PARSED_DATA_T Structure
# -------------------------------------------------------
class AsParsedDataT(BasePacket):
    """
    typedef struct {
        char    neId[EQUIP_ID_LEN];         // 40
        char    eventId[EVENT_ID_LEN];      // 20
        char    mappingNeId[EVENT_ID_LEN];  // 20
        char    idString[MMC_CMD_LEN];      // 128
        int     eventTime;                  // 4
        short   bscNo;                      // 2
        short   equipFlag;                  // 2
        short   segBlkCnt;                  // 2
        short   listSequence;               // 2
        short   attributeNo;                // 2
        union {
            struct {
                char    guid[60];
                char    result[PARSED_DATA_SEG_BLK_SIZE];
            } resultEx;
            char    result[PARSED_DATA_SIZE];
        };
    } AS_PARSED_DATA_T;
    """
    
    # Format String: 
    # 40s 20s 20s 128s I H H H H H {PARSED_DATA_SIZE}s
    # Union 부분은 그냥 최대 크기(PARSED_DATA_SIZE)의 바이트/문자열로 처리
    FMT = f"!{EQUIP_ID_LEN}s{EVENT_ID_LEN}s{EVENT_ID_LEN}s{MMC_CMD_LEN}sIHHHHH{PARSED_DATA_SIZE}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.neId = ""
        self.eventId = ""
        self.mappingNeId = ""
        self.idString = ""
        self.eventTime = -1
        self.bscNo = 0
        self.equipFlag = 0
        self.segBlkCnt = 0
        self.listSequence = 0
        self.attributeNo = 0
        
        # Union Part (result로 통칭)
        self.result = "" 
        # resultEx가 필요한 경우, result 문자열을 파싱해서 사용 (guid = result[:60])

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.neId, EQUIP_ID_LEN),
            self._encode_str(self.eventId, EVENT_ID_LEN),
            self._encode_str(self.mappingNeId, EVENT_ID_LEN),
            self._encode_str(self.idString, MMC_CMD_LEN),
            self.eventTime,
            self.bscNo,
            self.equipFlag,
            self.segBlkCnt,
            self.listSequence,
            self.attributeNo,
            self._encode_str(self.result, PARSED_DATA_SIZE)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.neId = cls._decode_str(t[0])
        obj.eventId = cls._decode_str(t[1])
        obj.mappingNeId = cls._decode_str(t[2])
        obj.idString = cls._decode_str(t[3])
        obj.eventTime = t[4]
        obj.bscNo, obj.equipFlag, obj.segBlkCnt = t[5], t[6], t[7]
        obj.listSequence, obj.attributeNo = t[8], t[9]
        obj.result = cls._decode_str(t[10])
        
        return obj
        
    # Helper to access Union resultEx
    def get_guid(self):
        # result의 앞 60바이트
        return self.result[:PARSED_DATA_KEY_SIZE].strip('\x00')
        
    def get_result_ex_body(self):
        # result의 60바이트 이후
        return self.result[PARSED_DATA_KEY_SIZE:]
    
# -------------------------------------------------------
# AS_MMC_LOG_T Structure
# -------------------------------------------------------
class AsMmcLogT(BasePacket):
    """
    typedef struct {
        int                     id;
        int                     previousId;
        char                    ne [EQUIP_ID_LEN];      // 40
        int                     cmdSetId;
        int                     cmdId;
        AS_MMC_INTERFACE        interfaces;             // int
        char                    mmc [MMC_CMD_LEN_EX];   // 256
        char                    idString [MMC_CMD_LEN]; // 128
        char                    userid [USER_ID_LEN];   // 20
        char                    display [IP_ADDRESS_LEN]; // 16
        int                     retryNo;
        int                     curRetryNo;
        AS_MMC_COLLECT_MODE     collectMode;            // int
        AS_MMC_RESPONSE_MODE    responseMode;           // int
        AS_MMC_PUBLISH_MODE     publishMode;            // int
        int                     logMode;
        int                     priority;
        char                    key [MMC_VAL_LEN];      // 256
        int                     cmdDelayTime;
    } AS_MMC_LOG_T;
    """
    
    # Format String Construction
    # I I 40s I I I 256s 128s 20s 16s I I I I I I I 256s I
    FMT = (f"!II{EQUIP_ID_LEN}sIII{MMC_CMD_LEN_EX}s{MMC_CMD_LEN}s{USER_ID_LEN}s"
           f"{IP_ADDRESS_LEN}sIIIIIII{MMC_VAL_LEN}sI")
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.id = 0
        self.previousId = 0
        self.ne = ""
        self.cmdSetId = 0
        self.cmdId = 0
        self.interfaces = 0
        self.mmc = ""
        self.idString = ""
        self.userid = ""
        self.display = ""
        self.retryNo = 0
        self.curRetryNo = 0
        self.collectMode = 0
        self.responseMode = 0
        self.publishMode = 0
        self.logMode = 0
        self.priority = 0
        self.key = ""
        self.cmdDelayTime = 0

    def pack(self):
        return struct.pack(self.FMT,
            self.id,
            self.previousId,
            self._encode_str(self.ne, EQUIP_ID_LEN),
            self.cmdSetId,
            self.cmdId,
            self.interfaces,
            self._encode_str(self.mmc, MMC_CMD_LEN_EX),
            self._encode_str(self.idString, MMC_CMD_LEN),
            self._encode_str(self.userid, USER_ID_LEN),
            self._encode_str(self.display, IP_ADDRESS_LEN),
            self.retryNo,
            self.curRetryNo,
            self.collectMode,
            self.responseMode,
            self.publishMode,
            self.logMode,
            self.priority,
            self._encode_str(self.key, MMC_VAL_LEN),
            self.cmdDelayTime
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.id = t[0]
        obj.previousId = t[1]
        obj.ne = cls._decode_str(t[2])
        obj.cmdSetId = t[3]
        obj.cmdId = t[4]
        obj.interfaces = t[5]
        obj.mmc = cls._decode_str(t[6])
        obj.idString = cls._decode_str(t[7])
        obj.userid = cls._decode_str(t[8])
        obj.display = cls._decode_str(t[9])
        obj.retryNo = t[10]
        obj.curRetryNo = t[11]
        obj.collectMode = t[12]
        obj.responseMode = t[13]
        obj.publishMode = t[14]
        obj.logMode = t[15]
        obj.priority = t[16]
        obj.key = cls._decode_str(t[17])
        obj.cmdDelayTime = t[18]
        return obj
    
# -------------------------------------------------------
# AS_SEGFLAG Enum
# -------------------------------------------------------
NO_SEG          = 0
SEG_ING         = 1
SEG_END         = 2
SEG_COMPLETE    = 3

# -------------------------------------------------------
# AS_CONNECTOR_DATA_T Structure
# -------------------------------------------------------
class AsConnectorDataT(BasePacket):
    """
    typedef struct {
        int                 MsgId;
        char                NeId[EQUIP_ID_LEN];         // 40
        char                AgentNeId[EQUIP_ID_LEN];    // 40
        unsigned short int  PortNo;                     // 2
        short int           LoggingFlag;                // 2 (0:logging, 1: not logging)
        AS_SEGFLAG          SegFlag;                    // 4 (Enum -> int)
        short int           Length;                     // 2
        char                RawMsg[MAX_RAW_MSG];        // Calculated
    } AS_CONNECTOR_DATA_T;
    """
    
    # MAX_RAW_MSG 계산: 전체 4096에서 헤더 크기들을 뺌
    # 4(MsgId) + 40(NeId) + 40(AgentNeId) + 2(Port) + 2(Log) + 4(Seg) + 2(Len) = 94 bytes
    # 4096 - 94 = 4002 bytes
    MAX_RAW_MSG_SIZE = MAX_MSG - 4 - EQUIP_ID_LEN - EQUIP_ID_LEN - 2 - 2 - 4 - 2
    
    # Format String: I 40s 40s H h I h {MAX}s
    FMT = f"!I{EQUIP_ID_LEN}s{EQUIP_ID_LEN}sHhIh{MAX_RAW_MSG_SIZE}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.MsgId = 0
        self.NeId = ""
        self.AgentNeId = ""
        self.PortNo = 0
        self.LoggingFlag = 0
        self.SegFlag = 0 # NO_SEG
        self.Length = 0
        self.RawMsg = b"" # 바이너리 데이터일 수 있으므로 bytes로 초기화

    def pack(self):
        # RawMsg가 문자열이면 인코딩
        if isinstance(self.RawMsg, str):
            self.RawMsg = self.RawMsg.encode('utf-8')
            
        # 실제 데이터 길이 갱신
        self.Length = len(self.RawMsg)
        
        # MAX 사이즈에 맞춰 패딩 (struct.pack이 자동으로 해주지만 명시적 절삭)
        packed_msg = self.RawMsg[:self.MAX_RAW_MSG_SIZE]

        return struct.pack(self.FMT,
            self.MsgId,
            self._encode_str(self.NeId, EQUIP_ID_LEN),
            self._encode_str(self.AgentNeId, EQUIP_ID_LEN),
            self.PortNo,
            self.LoggingFlag,
            self.SegFlag,
            self.Length,
            packed_msg
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.MsgId = t[0]
        obj.NeId = cls._decode_str(t[1])
        obj.AgentNeId = cls._decode_str(t[2])
        obj.PortNo = t[3]
        obj.LoggingFlag = t[4]
        obj.SegFlag = t[5]
        obj.Length = t[6]
        
        # RawMsg는 Length만큼만 유효한 데이터로 간주
        # t[7]은 4002바이트 전체임
        obj.RawMsg = t[7][:obj.Length]
        
        return obj
    
# -------------------------------------------------------
# AS_ASCII_ERROR_MSG_T Structure
# -------------------------------------------------------
class AsAsciiErrorMsgT(BasePacket):
    """
    typedef struct {
        int     ProcessType;
        char    ManagerId[40];
        char    ProcessId[40];
        int     Priority;
        char    ErrMsg[4000];
    } AS_ASCII_ERROR_MSG_T;
    """
    
    # Format String: I 40s 40s I 4000s
    # NAME_LEN = 40
    FMT = f"!I{NAME_LEN}s{NAME_LEN}sI4000s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ProcessType = 0
        self.ManagerId = ""
        self.ProcessId = ""
        self.Priority = 0
        self.ErrMsg = ""

    def pack(self):
        return struct.pack(self.FMT,
            self.ProcessType,
            self._encode_str(self.ManagerId, NAME_LEN),
            self._encode_str(self.ProcessId, NAME_LEN),
            self.Priority,
            self._encode_str(self.ErrMsg, 4000)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.ProcessType = t[0]
        obj.ManagerId = cls._decode_str(t[1])
        obj.ProcessId = cls._decode_str(t[2])
        obj.Priority = t[3]
        obj.ErrMsg = cls._decode_str(t[4])
        return obj
    
# -------------------------------------------------------
# AS_RULE_CHANGE_INFO_T Structure
# -------------------------------------------------------
class AsRuleChangeInfoT(BasePacket):
    """
    typedef struct {
        char    ManagerId[EQUIP_ID_LEN]; // 40
        char    ProcessId[EQUIP_ID_LEN]; // 40
        char    RuleId[40];
        int     MmcIdentType;
    } AS_RULE_CHANGE_INFO_T;
    """
    
    # Format String: 40s 40s 40s I
    # EQUIP_ID_LEN = 40
    FMT = f"!{EQUIP_ID_LEN}s{EQUIP_ID_LEN}s40sI"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ManagerId = ""
        self.ProcessId = ""
        self.RuleId = ""
        self.MmcIdentType = 0

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.ManagerId, EQUIP_ID_LEN),
            self._encode_str(self.ProcessId, EQUIP_ID_LEN),
            self._encode_str(self.RuleId, 40),
            self.MmcIdentType
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.ManagerId = cls._decode_str(t[0])
        obj.ProcessId = cls._decode_str(t[1])
        obj.RuleId = cls._decode_str(t[2])
        obj.MmcIdentType = t[3]
        return obj
    
# -------------------------------------------------------
# AS_CONNECTOR_DESC_CHANGE_INFO_T Structure
# -------------------------------------------------------
class AsConnectorDescChangeInfoT(BasePacket):
    """
    typedef struct {
        char    ManagerId[EQUIP_ID_LEN];     // 40
        char    ConnectorId[EQUIP_ID_LEN];   // 40
        char    Description[MAX_DESC_LEN];   // 500
    } AS_CONNECTOR_DESC_CHANGE_INFO_T;
    """
    
    # Format String: 40s 40s 500s
    FMT = f"!{EQUIP_ID_LEN}s{EQUIP_ID_LEN}s{MAX_DESC_LEN}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ManagerId = ""
        self.ConnectorId = ""
        self.Description = ""

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.ManagerId, EQUIP_ID_LEN),
            self._encode_str(self.ConnectorId, EQUIP_ID_LEN),
            self._encode_str(self.Description, MAX_DESC_LEN)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.ManagerId = cls._decode_str(t[0])
        obj.ConnectorId = cls._decode_str(t[1])
        obj.Description = cls._decode_str(t[2])
        return obj
    
# -------------------------------------------------------
# AS_PROC_CONTROL_T Structure
# -------------------------------------------------------
class AsProcControlT(BasePacket):
    """
    typedef struct {
        int     ProcessType;
        char    ManagerId[40];
        char    HostName[40];
        char    ProcessId[40];
        int     JunctionType;
        char    RuleId[NAME_LEN];       // 40
        int     MmcIdentType;
        int     CmdResponseType;        // 0:MsgIdent, 1:MsgId
        int     ConnectorStatus;
        int     ParserStatus;
        int     Status;
        int     DelayTime;
        int     LogCycle;               // 0: Day, 1: Hour
        char    Desc[MAX_DESC_LEN];     // 500
        char    Resever[30];            // 30 (Reserve)
    } AS_PROC_CONTROL_T;
    """
    
    # Format String
    # I 40s 40s 40s I 40s I I I I I I I 500s 30s
    # NAME_LEN=40, MAX_DESC_LEN=500
    FMT = f"!I40s40s40sI{NAME_LEN}sIIIIIII{MAX_DESC_LEN}s30s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ProcessType = 0
        self.ManagerId = ""
        self.HostName = ""
        self.ProcessId = ""
        self.JunctionType = 0
        self.RuleId = ""
        self.MmcIdentType = 0
        self.CmdResponseType = 0
        self.ConnectorStatus = 0
        self.ParserStatus = 0
        self.Status = 0
        self.DelayTime = 0
        self.LogCycle = 0
        self.Desc = ""
        self.Reserve = ""

    def pack(self):
        return struct.pack(self.FMT,
            self.ProcessType,
            self._encode_str(self.ManagerId, 40),
            self._encode_str(self.HostName, 40),
            self._encode_str(self.ProcessId, 40),
            self.JunctionType,
            self._encode_str(self.RuleId, NAME_LEN),
            self.MmcIdentType,
            self.CmdResponseType,
            self.ConnectorStatus,
            self.ParserStatus,
            self.Status,
            self.DelayTime,
            self.LogCycle,
            self._encode_str(self.Desc, MAX_DESC_LEN),
            self._encode_str(self.Reserve, 30)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.ProcessType = t[0]
        obj.ManagerId = cls._decode_str(t[1])
        obj.HostName = cls._decode_str(t[2])
        obj.ProcessId = cls._decode_str(t[3])
        obj.JunctionType = t[4]
        obj.RuleId = cls._decode_str(t[5])
        obj.MmcIdentType = t[6]
        obj.CmdResponseType = t[7]
        obj.ConnectorStatus = t[8]
        obj.ParserStatus = t[9]
        obj.Status = t[10]
        obj.DelayTime = t[11]
        obj.LogCycle = t[12]
        obj.Desc = cls._decode_str(t[13])
        obj.Reserve = cls._decode_str(t[14])
        return obj

# -------------------------------------------------------
# AS_SESSION_CONTROL_T Structure
# -------------------------------------------------------
class AsSessionControlT(BasePacket):
    """
    typedef struct {
        char    ManagerId[40];
        char    ConnectorId[40];
        int     Sequence;
        int     Status;
        char    Desc[MAX_DESC_LEN]; // 500
    } AS_SESSION_CONTROL_T;
    """
    
    # Format String: 40s 40s I I 500s
    FMT = f"!40s40sII{MAX_DESC_LEN}s"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.ManagerId = ""
        self.ConnectorId = ""
        self.Sequence = 0
        self.Status = 0
        self.Desc = ""

    def pack(self):
        return struct.pack(self.FMT,
            self._encode_str(self.ManagerId, 40),
            self._encode_str(self.ConnectorId, 40),
            self.Sequence,
            self.Status,
            self._encode_str(self.Desc, MAX_DESC_LEN)
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.ManagerId = cls._decode_str(t[0])
        obj.ConnectorId = cls._decode_str(t[1])
        obj.Sequence = t[2]
        obj.Status = t[3]
        obj.Desc = cls._decode_str(t[4])
        return obj

# -------------------------------------------------------
# Message IDs (Router Info)
# -------------------------------------------------------
AS_ROUTER_INFO_REQ = 5001 # 예시 값 (실제 헤더 확인 필요)
AS_ROUTER_INFO_RES = 5002

# -------------------------------------------------------
# AS_ROUTER_INFO_REQ_T Structure
# -------------------------------------------------------
class AsRouterInfoReqT(BasePacket):
    """
    typedef struct {
        char userid[20];
        char password[20];
        int equipNo;
        // ... potentially more fields ...
    } AS_ROUTER_INFO_REQ_T;
    """
    FMT = "!20s20si" 
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.userid = ""
        self.password = ""
        self.equipNo = 0

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        obj = cls()
        obj.userid = cls._decode_str(t[0])
        obj.password = cls._decode_str(t[1])
        obj.equipNo = t[2]
        return obj
    
# -------------------------------------------------------
# AS_ROUTER_INFO_T Structure
# -------------------------------------------------------
class AsRouterInfoT(BasePacket):
    """
    typedef struct {
        int     resultMode;     // 0 : nok, 1 : ok
        char    equipId[EQUIP_ID_LEN]; // 40
        char    ipaddress[IP_ADDRESS_LEN]; // 16
        int     portNo;
    } AS_ROUTER_INFO_T;
    """
    
    # Format String: I 40s 16s I
    # EQUIP_ID_LEN=40, IP_ADDRESS_LEN=16
    FMT = f"!I{EQUIP_ID_LEN}s{IP_ADDRESS_LEN}sI"
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.resultMode = 0
        self.equipId = ""
        self.ipaddress = ""
        self.portNo = 0

    def pack(self):
        return struct.pack(self.FMT,
            self.resultMode,
            self._encode_str(self.equipId, EQUIP_ID_LEN),
            self._encode_str(self.ipaddress, IP_ADDRESS_LEN),
            self.portNo
        )

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.resultMode = t[0]
        obj.equipId = cls._decode_str(t[1])
        obj.ipaddress = cls._decode_str(t[2])
        obj.portNo = t[3]
        return obj

# -------------------------------------------------------
# AS_ROUTER_INFO_RES_T Structure (List)
# -------------------------------------------------------
class AsRouterInfoResT(BasePacket):
    """
    typedef struct {
        int                 routerNo;
        AS_ROUTER_INFO_T    routerInfos[50];
    } AS_ROUTER_INFO_RES_T;
    """
    
    MAX_ARRAY_SIZE = 50
    HEADER_FMT = "!I"
    HEADER_SIZE = struct.calcsize(HEADER_FMT)

    def __init__(self):
        self.routerNo = 0
        self.routerInfos = [] # List of AsRouterInfoT

    def pack(self):
        self.routerNo = len(self.routerInfos)
        if self.routerNo > self.MAX_ARRAY_SIZE:
            self.routerNo = self.MAX_ARRAY_SIZE
            
        packed_data = struct.pack(self.HEADER_FMT, self.routerNo)
        
        for i in range(self.MAX_ARRAY_SIZE):
            if i < self.routerNo:
                packed_data += self.routerInfos[i].pack()
            else:
                packed_data += AsRouterInfoT().pack() # Padding
        return packed_data

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.HEADER_SIZE: return None
        obj = cls()
        obj.routerNo = struct.unpack(cls.HEADER_FMT, data[:cls.HEADER_SIZE])[0]
        
        valid_count = min(obj.routerNo, cls.MAX_ARRAY_SIZE)
        offset = cls.HEADER_SIZE
        item_size = AsRouterInfoT.SIZE
        
        for _ in range(valid_count):
            if offset + item_size > len(data): break
            obj.routerInfos.append(AsRouterInfoT.unpack(data[offset:offset+item_size]))
            offset += item_size
        return obj
    
# -------------------------------------------------------
# AS_MMC_FLOW_CONTROL_T Structure
# -------------------------------------------------------
class AsMmcFlowControlT(BasePacket):
    """
    typedef struct {
        int controlMode;    // 0: STOP, 1: RESTART
        int msgId;          // STOP일 때 요청한 메시지 ID
        char controlInfo[64]; // 사유
    } AS_MMC_FLOW_CONTROL_T;
    """
    FMT = "!ii64s"  # int(4) + int(4) + char(64)
    SIZE = struct.calcsize(FMT)

    def __init__(self):
        self.controlMode = 0
        self.msgId = 0
        self.controlInfo = ""

    def pack(self):
        return struct.pack(self.FMT,
                           self.controlMode,
                           self.msgId,
                           self._encode_str(self.controlInfo, 64))

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.SIZE: return None
        t = struct.unpack(cls.FMT, data[:cls.SIZE])
        
        obj = cls()
        obj.controlMode = t[0]
        obj.msgId = t[1]
        obj.controlInfo = cls._decode_str(t[2])
        return obj
    
