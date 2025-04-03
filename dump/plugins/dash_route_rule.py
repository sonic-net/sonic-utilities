from dump.helper import create_template_dict
from dump.match_infra import MatchRequest
from swsscommon.swsscommon import SonicDBConfig
from dash_api.route_rule_pb2 import RouteRule
from .executor import Executor
from .dash_eni import Dash_Eni
import ipaddress

APPL_DB_SEPARATOR = SonicDBConfig.getSeparator("APPL_DB")


def get_route_rule_pattern(cidr_src_ip, eni_oid, vni, prio):
    network = ipaddress.IPv4Network(cidr_src_ip)
    ip_address = str(network.network_address)
    mask = str(network.netmask)
    ret_string = (
        f"*\"eni_id\":\"oid:{eni_oid}\","
        f"\"priority\":\"{prio}\","
        f"\"sip\":\"{ip_address}\","
        f"\"sip_mask\":\"{mask}\","
        f"*\"vni\":\"{vni}\"*")
    return ret_string


class Dash_Route_Rule(Executor):
    """
    Debug Dump Plugin for DASH Route Rule
    """
    ARG_NAME = "dash_route_rule_name"

    def __init__(self, match_engine=None):
        super().__init__(match_engine)
        self.is_dash_object = True
        self.src_ip = None
        self.eni = None
        self.vni = None
        if match_engine:
            self.eni_obj = Dash_Eni(match_engine)
        else:
            self.eni_obj = None

    def get_all_args(self, ns=""):
        req = MatchRequest(db="APPL_DB", table="DASH_ROUTE_RULE_TABLE", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        route_rule_tables = ret["keys"]
        return [key.split(APPL_DB_SEPARATOR, 1)[1] for key in route_rule_tables]

    def execute(self, params):
        self.ret_temp = create_template_dict(dbs=["APPL_DB", "ASIC_DB"])
        dash_route_rule_table_name = params[self.ARG_NAME]
        self.ns = params["namespace"]
        self.init_dash_route_table_appl_info(dash_route_rule_table_name)
        self.init_dash_route_table_asic_info()
        return self.ret_temp

    def init_dash_route_table_appl_info(self, dash_route_rule_table_name):
        req = MatchRequest(db="APPL_DB",
                           table="DASH_ROUTE_RULE_TABLE",
                           key_pattern=dash_route_rule_table_name,
                           return_fields=["priority"], ns=self.ns, pb=RouteRule())
        ret = self.match_engine.fetch(req)
        if not ret["error"] and len(ret["keys"]) != 0:
            split_key = ret["keys"][0].split(":")
            self.src_ip = split_key[-1]
            self.vni = split_key[-2]
            self.eni = split_key[-3]
            self.priority = str(ret['return_values'][ret['keys'][0]]['priority'])
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_dash_route_table_asic_info(self):
        if not self.src_ip:
            return
        print(self.eni)
        if not self.eni_obj:
            self.eni_obj = Dash_Eni()
        params = {Dash_Eni.ARG_NAME: self.eni, "namespace": self.ns}
        self.eni_obj.execute(params)
        eni_oid = self.eni_obj.eni_oid
        if not eni_oid:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_INBOUND_ROUTING_ENTRY")
            return
        req = MatchRequest(db="ASIC_DB",
                           table="ASIC_STATE:SAI_OBJECT_TYPE_INBOUND_ROUTING_ENTRY",
                           key_pattern=get_route_rule_pattern(self.src_ip,
                                                              eni_oid,
                                                              self.vni,
                                                              self.priority),
                           ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def return_pb2_obj(self):
        return RouteRule()
