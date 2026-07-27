from dump.helper import create_template_dict
from dump.match_infra import MatchRequest
from swsscommon.swsscommon import SonicDBConfig
from dash_api.qos_pb2 import Qos
from .executor import Executor


APPL_DB_SEPARATOR = SonicDBConfig.getSeparator("APPL_DB")


class Dash_Qos(Executor):
    """
    Debug Dump Plugin for DASH VNET Mapping
    """
    ARG_NAME = "dash_qos"

    def __init__(self, match_engine=None):
        super().__init__(match_engine)
        self.is_dash_object = True

    def get_all_args(self, ns=""):
        req = MatchRequest(db="APPL_DB", table="DASH_QOS_TABLE", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        appliance_tables = ret["keys"]
        return [key.split(APPL_DB_SEPARATOR)[-1] for key in appliance_tables]

    def execute(self, params):
        self.ret_temp = create_template_dict(dbs=["APPL_DB"])
        dash_qos_table_name = params[self.ARG_NAME]
        self.ns = params["namespace"]
        self.init_dash_qos_table_appl_info(dash_qos_table_name)
        return self.ret_temp

    def init_dash_qos_table_appl_info(self, dash_qos_table_name):
        req = MatchRequest(db="APPL_DB", table="DASH_QOS_TABLE",
                           key_pattern=dash_qos_table_name,
                           return_fields=["type"], ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def return_pb2_obj(self):
        return Qos()
