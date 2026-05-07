# KtfConWorld.py
from libConnector.DCAsciiAgent import DCAsciiAgent
from libConnector.DCSnmpAgent  import DCSnmpAgent
# ...

AGENT_REGISTRY = {
    "ASCII_AGENT":     DCAsciiAgent,
    "SNMP_AGENT":      DCSnmpAgent,
    "TRAP_AGENT":      DCTrapAgent,
    "SG_SAME_AMF_AGENT": DC5GSameAmfMultiAgent,
    # ... 70여 개
}

class KtfConWorld(ConnectorWorld):
    def AppStart(self, argc, argv):
        return super().AppStart(argc, argv)