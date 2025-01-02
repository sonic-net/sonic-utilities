from dump.helper import create_template_dict
from dump.match_infra import MatchRequest
from swsscommon.swsscommon import SonicDBConfig
from dash_api.route_pb2 import Route
from .executor import Executor
from .dash_eni import Dash_Eni

APPL_DB_SEPARATOR = SonicDBConfig.getSeparator("APPL_DB")


def get_route_pattern(dest, eni_oid):
    return "*\"destination\":\"" + dest + "\",\"eni_id\":\"oid:" + eni_oid + "\"*"


class Dash_Route(Executor):
    """
    Debug Dump Plugin for DASH Route
    """
    ARG_NAME = "dash_route_name"

    def __init__(self, match_engine=None):
        super().__init__(match_engine)
        self.is_dash_object = True
        self.dest = None
        if match_engine:
            self.eni_obj = Dash_Eni(match_engine)
        else:
            self.eni_obj = None

    def get_all_args(self, ns=""):
        req = MatchRequest(db="APPL_DB", table="DASH_ROUTE_TABLE", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        appliance_tables = ret["keys"]
        return [key.split(APPL_DB_SEPARATOR, 1)[1] for key in appliance_tables]

    def execute(self, params):
        self.ret_temp = create_template_dict(dbs=["APPL_DB", "ASIC_DB"])
        dash_route_table_name = params[self.ARG_NAME]
        self.ns = params["namespace"]
        self.init_dash_route_table_appl_info(dash_route_table_name)
        self.init_dash_route_table_asic_info()
        return self.ret_temp

    def init_dash_route_table_appl_info(self, dash_route_table_name):
        req = MatchRequest(db="APPL_DB", table="DASH_ROUTE_TABLE", key_pattern=dash_route_table_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        if not ret["error"] and len(ret["keys"]) != 0:
            split_key = ret["keys"][0].split(":")
            self.dest = split_key[-1]
            self.eni = split_key[-2]
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_dash_route_table_asic_info(self):
        if not self.dest:
            return
        if not self.eni_obj:
            self.eni_obj = Dash_Eni()
        params = {Dash_Eni.ARG_NAME: self.eni, "namespace": self.ns}
        self.eni_obj.execute(params)
        eni_oid = self.eni_obj.eni_oid
        if not eni_oid:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_OUTBOUND_ROUTING_ENTRY")
            return
        req = MatchRequest(db="ASIC_DB",
                           table="ASIC_STATE:SAI_OBJECT_TYPE_OUTBOUND_ROUTING_ENTRY",
                           key_pattern=get_route_pattern(self.dest, eni_oid),
                           ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
        return

    def return_pb2_obj(self):
        return Route()
