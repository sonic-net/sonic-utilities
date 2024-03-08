from dump.match_infra import MatchEngine, MatchRequest, ConnectionPool
from dump.match_helper import get_matched_keys
from .db import Db
import copy

def get_port_acl_binding(db_wrap, port, ns):
    """
    Verify if the port is not bound to any ACL Table
    
    Args:
        db_wrap: utilities_common.Db() object
        port: Iface name
        ns: namespace

    Returns:
        list: ACL_TABLE names if found, 
                otherwise empty
    """ 
    ACL = "ACL_TABLE" # Table to look for port bindings
    if not isinstance(db_wrap, Db):
        raise Exception("db_wrap object is not of type utilities_common.Db")

    conn_pool = ConnectionPool()
    conn_pool.fill(ns, db_wrap.db_clients[ns], db_wrap.db_list)
    m_engine = MatchEngine(conn_pool)
    req = MatchRequest(db="CONFIG_DB",
                      table=ACL,
                      key_pattern="*",
                      field="ports@",
                      value=port,
                      ns=ns,
                      match_entire_list=False)
    ret = m_engine.fetch(req)
    acl_tables, _ = get_matched_keys(ret)
    return acl_tables


def get_port_pbh_binding(db_wrap, port, ns):
    """
    Verify if the port is not bound to any PBH Table
    
    Args:
        db_wrap: Db() object
        port: Iface name
        ns: namespace

    Returns:
        list: PBH_TABLE names if found, 
                otherwise empty
    """ 
    PBH = "PBH_TABLE" # Table to look for port bindings
    if not isinstance(db_wrap, Db):
        raise Exception("db_wrap object is not of type utilities_common.Db")

    conn_pool = ConnectionPool()
    conn_pool.fill(ns, db_wrap.db_clients[ns], db_wrap.db_list)
    m_engine = MatchEngine(conn_pool)
    req = MatchRequest(db="CONFIG_DB",
                      table=PBH,
                      key_pattern="*",
                      field="interface_list@",
                      value=port,
                      ns=ns,
                      match_entire_list=False)
    ret = m_engine.fetch(req)
    pbh_tables, _ = get_matched_keys(ret)
    return pbh_tables


def update_config(current_config, config_input, deepcopy=True):
    """
    Override current config with golden config
    Shallow copy only copies the references to the original object,
    so any changes to one object will also change the other.
    Therefore, we should be careful when using shallow copy to avoid unwanted modifications.

    Args:
        current_config: current config
        config_input: input golden config
        deepcopy: True for deep copy, False for shallow copy

    Returns:
        Final config after overriding
    """
    if deepcopy:
        # Deep copy for safety
        updated_config = copy.deepcopy(current_config)
    else:
        # Shallow copy for better performance
        updated_config = current_config
    # Override current config with golden config
    for table in config_input:
        updated_config[table] = config_input[table]
    return updated_config
