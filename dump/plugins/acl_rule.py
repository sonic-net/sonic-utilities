from dump.helper import create_template_dict
from dump.match_infra import MatchRequest
from swsscommon.swsscommon import SonicDBConfig

from dump.match_helper import fetch_acl_counter_oid
from .executor import Executor


CFG_DB_SEPARATOR = SonicDBConfig.getSeparator("CONFIG_DB")
ASIC_DB_SEPARATOR = SonicDBConfig.getSeparator("ASIC_DB")
APP_DB_SEPARATOR = SonicDBConfig.getSeparator("APPL_DB")
APP_RULE_NAME = "ACL_RULE_TABLE"


class Acl_Rule(Executor):
    """
    Debug Dump Plugin for ACL Rule Module
    """
    ARG_NAME = "acl_rule_name"

    def __init__(self, match_engine=None):
        super().__init__(match_engine)

    def get_all_args(self, ns=""):
        req = MatchRequest(db="CONFIG_DB", table="ACL_RULE", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        req_app = MatchRequest(db="APPL_DB", table=APP_RULE_NAME, key_pattern="*", ns=ns)
        ret_app = self.match_engine.fetch(req_app)
        return [f"{CFG_DB_SEPARATOR}".join(key.split(CFG_DB_SEPARATOR)[1:]) for key in ret.get("keys")] + \
               [f"{APP_DB_SEPARATOR}".join(key.split(APP_DB_SEPARATOR)[1:]) for key in ret_app.get("keys")]

    def execute(self, params):
        self.ret_temp = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB"])
        invalid = False
        try:
            acl_table_name, acl_rule_name = params[self.ARG_NAME].split(CFG_DB_SEPARATOR, 1)
        except ValueError:
            invalid = True

        if invalid:
            try:
                acl_table_name, acl_rule_name = params[self.ARG_NAME].split(APP_DB_SEPARATOR, 1)
            except ValueError:
                raise ValueError(f"Invalid rule name passed {params[self.ARG_NAME]}")

        self.ns = params["namespace"]
        self.init_acl_rule_config_info(acl_table_name, acl_rule_name)
        self.init_acl_rule_appl_info(acl_table_name, acl_rule_name)
        self.init_acl_rule_asic_info(acl_table_name, acl_rule_name)
        return self.ret_temp

    def init_acl_rule_config_info(self, acl_table_name, acl_rule_name):
        req = MatchRequest(db="CONFIG_DB", table="ACL_RULE",
                           key_pattern=CFG_DB_SEPARATOR.join([acl_table_name, acl_rule_name]), ns=self.ns)
        ret = self.match_engine.fetch(req)
        if ret["keys"]:
            self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_acl_rule_appl_info(self, acl_table_name, acl_rule_name):
        req = MatchRequest(db="APPL_DB", table=APP_RULE_NAME,
                           key_pattern=APP_DB_SEPARATOR.join([acl_table_name, acl_rule_name]), ns=self.ns)
        ret = self.match_engine.fetch(req)
        if ret["keys"]:
            self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_acl_rule_asic_info(self, acl_table_name, acl_rule_name):
        counter_oid = fetch_acl_counter_oid(self.match_engine, acl_table_name, acl_rule_name, self.ns)
        if not counter_oid:
            return

        req = MatchRequest(db="ASIC_DB", table=ASIC_DB_SEPARATOR.join(["ASIC_STATE", "SAI_OBJECT_TYPE_ACL_COUNTER"]),
                           key_pattern=counter_oid, return_fields=["SAI_ACL_COUNTER_ATTR_TABLE_ID"], ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

        return_values = ret["return_values"]
        counter_object = return_values.get(ASIC_DB_SEPARATOR.join(["ASIC_STATE", "SAI_OBJECT_TYPE_ACL_COUNTER", counter_oid]), {})
        table_oid = counter_object.get("SAI_ACL_COUNTER_ATTR_TABLE_ID")
        if not table_oid:
            raise Exception("Invalid counter object without table OID in ASIC_DB")

        req = MatchRequest(db="ASIC_DB", table=ASIC_DB_SEPARATOR.join(["ASIC_STATE", "SAI_OBJECT_TYPE_ACL_ENTRY"]), key_pattern="*",
                           field="SAI_ACL_ENTRY_ATTR_TABLE_ID", value=table_oid,
                           return_fields=["SAI_ACL_ENTRY_ATTR_FIELD_ACL_RANGE_TYPE"], ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

        range_oids = set()
        for _, entry in ret["return_values"].items():
            range_attr_value = entry.get("SAI_ACL_ENTRY_ATTR_FIELD_ACL_RANGE_TYPE")
            if not range_attr_value:
                continue
            ranges_attr_value = range_attr_value.split(ASIC_DB_SEPARATOR, 1)
            if len(range_attr_value) < 2:
                raise Exception("Invalid SAI_ACL_ENTRY_ATTR_FIELD_ACL_RANGE_TYPE field format")
            for oid in ranges_attr_value[1].split(','):
                range_oids.add(oid)

        for range_oid in range_oids:
            req = MatchRequest(db="ASIC_DB", table=ASIC_DB_SEPARATOR.join(["ASIC_STATE", "SAI_OBJECT_TYPE_ACL_RANGE"]),
                               key_pattern=range_oid, ns=self.ns)
            ret = self.match_engine.fetch(req)
            self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
