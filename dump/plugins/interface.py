from sonic_py_common.interface import get_interface_table_name, get_intf_longname, VLAN_SUB_INTERFACE_SEPARATOR
from sonic_py_common.multi_asic import DEFAULT_NAMESPACE
from dump.match_infra import MatchRequest
from dump.helper import create_template_dict, handle_error
from dump.match_helper import fetch_port_oid, fetch_vlan_oid, fetch_lag_oid
from swsscommon.swsscommon import SonicDBConfig
from .executor import Executor


class Interface(Executor):
    """
    Debug Dump Plugin for Interface Module.
    Interface can be of Ethernet, PortChannel, Loopback, Vlan or SubInterface type
    Human readable intf string names are supported
    """
    ARG_NAME = "intf_name"

    def __init__(self, match_engine=None):
        super().__init__(match_engine)
        self.ns = DEFAULT_NAMESPACE
        self.intf_type = ""
        self.ret_temp = dict()
        self.valid_cfg_tables = set(["INTERFACE", 
                                    "PORTCHANNEL_INTERFACE", 
                                    "VLAN_INTERFACE",
                                    "LOOPBACK_INTERFACE",
                                    "VLAN_SUB_INTERFACE"])
        
    def get_all_args(self, ns=DEFAULT_NAMESPACE):
        """
        Fetch all the interfaces from the valid cfg tables
        """
        req = MatchRequest(db="CONFIG_DB", table="*INTERFACE", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        all_intfs = ret["keys"]
        filtered_keys = []
        for key in all_intfs:
            num_sep = key.count("|")
            if num_sep == 1:
                filtered_keys.append(key.split("|")[-1])
        return filtered_keys

    def execute(self, params):
        self.ret_temp = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "STATE_DB", "ASIC_DB"])
        self.intf_name = params[Interface.ARG_NAME]
        self.ns = params["namespace"]
        # CONFIG_DB
        self.intf_type = self.init_intf_config_info()
        # APPL_DB
        self.init_intf_appl_info()
        # STATE_DB
        self.init_intf_state_info()
        # ASIC_DB
        self.init_intf_asic_info()
        return self.ret_temp

    def get_sep(self, db):
        return SonicDBConfig.getSeparator(db)

    def add_intf_keys(self, db_name, table_name):
        # Fetch Interface Keys
        req = MatchRequest(db=db_name, table=table_name, key_pattern=self.intf_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
        # Fetch IP & Interface Related keys
        req = MatchRequest(db=db_name, table=table_name, key_pattern=self.intf_name+self.get_sep(db_name)+"*", ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"], False)

    def init_intf_config_info(self):
        intf_table_name = get_interface_table_name(self.intf_name)
        if not intf_table_name:
            self.ret_temp["CONFIG_DB"]["tables_not_found"].extend(list(self.valid_cfg_tables))
        else:
            self.add_intf_keys("CONFIG_DB", intf_table_name)
        return intf_table_name

    def init_intf_appl_info(self):
        self.add_intf_keys("APPL_DB", "INTF_TABLE")

    def init_intf_state_info(self):
        self.add_intf_keys("STATE_DB", "INTERFACE_TABLE")

    def init_intf_asic_info(self):
        """
        Fetch SAI_OBJECT_TYPE_ROUTER_INTERFACE ASIC Object for the corresponding interface
        To find the relevant ASIC RIF object, this method would need the following:
        1) INTERFACE - SAI_OBJECT_TYPE_PORT oid
        2) PORTCHANNEL - SAI_OBJECT_TYPE_LAG oid
        3) VLAN - SAI_OBJECT_TYPE_VLAN
        4) SUB_INTERFACE - SAI_OBJECT_TYPE_PORT/SAI_OBJECT_TYPE_LAG & SAI_ROUTER_INTERFACE_ATTR_OUTER_VLAN_ID
        """
        rif_obj = RIF.initialize(self)
        rif_obj.collect()
        return 

class RIF(object):
    """
    Base Class for RIF type
    """
    @staticmethod
    def initialize(intf_obj):
        if intf_obj.intf_type == "INTERFACE":
            return PortRIF(intf_obj)
        elif intf_obj.intf_type == "PORTCHANNEL_INTERFACE":
            return LagRIF(intf_obj)
        elif intf_obj.intf_type == "VLAN_INTERFACE":
            return VlanRIF(intf_obj)
        elif intf_obj.intf_type == "LOOPBACK_INTERFACE":
            return LpbRIF(intf_obj)
        elif intf_obj.intf_type == "VLAN_SUB_INTERFACE":
            return SubIntfRif(intf_obj)
        return RIF(intf_obj)

    def __init__(self, intf_obj):
        self.intf = intf_obj
    
    def fetch_rif_keys_using_port_oid(self, port_oid, rfs=["SAI_ROUTER_INTERFACE_ATTR_TYPE"]):
        if not port_oid:
            port_oid = "INVALID"
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE", key_pattern="*", field="SAI_ROUTER_INTERFACE_ATTR_PORT_ID",
              value=port_oid, return_fields=rfs, ns=self.intf.ns)
        ret = self.intf.match_engine.fetch(req)
        return req, ret

    def verify_valid_rif_type(self, ret, exp_rif_type=""):
        if not ret or not exp_rif_type:
            return True, ""

        rif_type = ""
        if not ret["error"] and ret["keys"]:
            rif_key = ret["keys"][-1]
            rif_type = ret.get("return_values", {}).get(rif_key, {}).get("SAI_ROUTER_INTERFACE_ATTR_TYPE", "")

        if rif_type == exp_rif_type:
            return True, rif_type
        else:
            return False, rif_type

    def sanity_check_rif_type(self, ret, rif_oid, exp_type, str_name):
        # Sanity check to see if the TYPE is SAI_ROUTER_INTERFACE_TYPE_PORT
        _, recv_type = self.verify_valid_rif_type(ret, exp_type)
        if exp_type != recv_type:
            err_str = "TYPE Mismatch on SAI_OBJECT_TYPE_ROUTER_INTERFACE, {} oid:{}, expected type:{}, recieved type:{}"
            handle_error(err_str.format(str_name, rif_oid, exp_type, recv_type), False)
        return

    def collect(self):
        self.intf.ret_temp["ASIC_DB"]["tables_not_found"].extend(["ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE"])
        return 


class LpbRIF(RIF):
    """
    Handler for Loopback Interface
    """
    def collect(self):
        # When an ip is added to Loopback interface, 
        # no ROUTER_INTERFACE asic obj is created, so skipping it
        # and not adding to tables not found
        return


class PortRIF(RIF):
    """
    Handler for Port type Obj
    """
    def collect(self):
        # Get port oid from port name
        _, port_oid, _ = fetch_port_oid(self.intf.match_engine, self.intf.intf_name, self.intf.ns)
        # Use Port oid to get the RIF
        req, ret = self.fetch_rif_keys_using_port_oid(port_oid)
        rif_oids = self.intf.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
        if rif_oids:
            # Sanity check to see if the TYPE is SAI_ROUTER_INTERFACE_TYPE_PORT
            exp_type = "SAI_ROUTER_INTERFACE_TYPE_PORT"
            self.sanity_check_rif_type(ret, rif_oids[-1], exp_type, "PORT")


class VlanRIF(RIF):
    """
    Handler for Vlan type Obj
    """
    def fetch_rif_keys_using_vlan_oid(self, vlan_oid):
        if not vlan_oid:
            vlan_oid = "INVALID"
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE", key_pattern="*", field="SAI_ROUTER_INTERFACE_ATTR_VLAN_ID",
              value=vlan_oid, return_fields=["SAI_ROUTER_INTERFACE_ATTR_TYPE"], ns=self.intf.ns)
        ret = self.intf.match_engine.fetch(req)
        return req, ret

    def collect(self):
        # Get vlan oid from vlan name
        _, vlan_oid, _ = fetch_vlan_oid(self.intf.match_engine, self.intf.intf_name, self.intf.ns)
        # Use vlan oid to get the RIF
        req, ret = self.fetch_rif_keys_using_vlan_oid(vlan_oid)
        rif_oids = self.intf.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
        if rif_oids:
            # Sanity check to see if the TYPE is SAI_ROUTER_INTERFACE_TYPE_VLAN
            exp_type = "SAI_ROUTER_INTERFACE_TYPE_VLAN"
            self.sanity_check_rif_type(ret, rif_oids[-1], exp_type, "VLAN")
    

class LagRIF(RIF):
    """
    Handler for PortChannel/LAG type Obj
    """
    def collect(self):
        # Get lag oid from lag name 
        lag_oid = fetch_lag_oid(self.intf.match_engine, self.intf.intf_name, self.intf.ns)
        # Use vlan oid to get the RIF
        req, ret = self.fetch_rif_keys_using_port_oid(lag_oid)
        rif_oids = self.intf.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
        if rif_oids:
            # Sanity check to see if the TYPE is SAI_ROUTER_INTERFACE_TYPE_PORT
            exp_type = "SAI_ROUTER_INTERFACE_TYPE_PORT"
            self.sanity_check_rif_type(ret, rif_oids[-1], exp_type, "LAG")


class SubIntfRif(RIF):
    """
    Handler for PortChannel/LAG type Obj
    """
    def fetch_vlan_id_subintf(self, sub_intf):
        req = MatchRequest(db="CONFIG_DB", table="VLAN_SUB_INTERFACE", key_pattern=sub_intf, return_fields=["vlan"], ns=self.intf.ns)
        ret = self.intf.match_engine.fetch(req)
        vlan_id = ""
        if not ret["error"] and ret["keys"]:
            key = ret["keys"][-1]
            vlan_id = ret["return_values"].get(key, {}).get("vlan", "")
        return vlan_id

    def collect(self):
        """
        To match the RIF object, two checks have to be performed, 
        1) SAI_ROUTER_INTERFACE_ATTR_PORT_ID 
           - This can either be SAI_OBJECT_TYPE_PORT or SAI_OBJECT_TYPE_LAG
        2) SAI_ROUTER_INTERFACE_ATTR_OUTER_VLAN_ID
           - This will be Vlan Number (uint16)
        """
        intf_oid = ""
        parent_port, _ = self.intf.intf_name.split(VLAN_SUB_INTERFACE_SEPARATOR)
        parent_port = get_intf_longname(parent_port)
        vlan_id = self.fetch_vlan_id_subintf(self.intf.intf_name)
        if parent_port.startswith("Eth"):
            _, intf_oid, _ = fetch_port_oid(self.intf.match_engine, parent_port, self.intf.ns)
        else:
            intf_oid = fetch_lag_oid(self.intf.match_engine, parent_port, self.intf.ns)
        
        # Use vlan oid to get the RIF
        return_fields = ["SAI_ROUTER_INTERFACE_ATTR_OUTER_VLAN_ID", "SAI_ROUTER_INTERFACE_ATTR_TYPE"]
        req, ret = self.fetch_rif_keys_using_port_oid(intf_oid, rfs=return_fields)

        # Search for keys who has SAI_ROUTER_INTERFACE_ATTR_OUTER_VLAN_ID field
        filtered_keys = []
        if not ret["error"] and len(ret['keys']) > 0:
            for key in ret["keys"]:
                rcv_vlan_id = ret.get("return_values", {}).get(key, {}).get("SAI_ROUTER_INTERFACE_ATTR_OUTER_VLAN_ID", "")
                if rcv_vlan_id == vlan_id:
                    filtered_keys.append(key)
                    break

        rif_oids = self.intf.add_to_ret_template(req.table, req.db, filtered_keys, ret["error"])
        if rif_oids:
            exp_type = "SAI_ROUTER_INTERFACE_TYPE_SUB_PORT"
            self.sanity_check_rif_type(ret, rif_oids[-1], exp_type, "SUB_INTERFACE")
