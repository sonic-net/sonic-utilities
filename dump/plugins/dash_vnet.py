from dump.helper import create_template_dict
from dump.match_infra import MatchRequest
from swsscommon.swsscommon import SonicDBConfig
from dash_api.vnet_pb2 import Vnet
from .executor import Executor


APPL_DB_SEPARATOR = SonicDBConfig.getSeparator("APPL_DB")


class Dash_Vnet(Executor):
    """
    Debug Dump Plugin for DASH VNET
    """
    ARG_NAME = "dash_vnet_name"

    def __init__(self, match_engine=None):
        super().__init__(match_engine)
        self.is_dash_object = True
        self.vni = None

    def get_all_args(self, ns=""):
        self.ns = ns
        req = MatchRequest(db="APPL_DB", table="DASH_VNET_TABLE", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        vnet_tables = ret["keys"]
        return [key.split(APPL_DB_SEPARATOR, 1)[1] for key in vnet_tables]

    def execute(self, params):
        self.ret_temp = create_template_dict(dbs=["APPL_DB", "ASIC_DB"])
        dash_vnet_table_name = params[self.ARG_NAME]
        self.ns = params["namespace"]
        self.init_dash_vnet_table_appl_info(dash_vnet_table_name)
        self.init_dash_vnet_table_asic_info()
        return self.ret_temp

    def init_dash_vnet_table_appl_info(self, dash_vnet_table_name):
        req = MatchRequest(db="APPL_DB",
                           table="DASH_VNET_TABLE",
                           key_pattern=dash_vnet_table_name,
                           return_fields=["vni"], ns=self.ns, pb=Vnet())
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
        if not ret["error"] and len(ret["keys"]) != 0:
            self.vni = str(ret['return_values'][ret['keys'][0]]['vni'])

    def init_dash_vnet_table_asic_info(self):
        if not self.vni:
            return
        req = MatchRequest(db="ASIC_DB",
                           table="ASIC_STATE:SAI_OBJECT_TYPE_VNET",
                           key_pattern="*", field="SAI_VNET_ATTR_VNI",
                           value=str(self.vni), ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def return_pb2_obj(self):
        return Vnet()
