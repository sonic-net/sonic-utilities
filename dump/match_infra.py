import json
import fnmatch
import copy
from abc import ABC, abstractmethod
from dump.helper import verbose_print
from swsscommon.swsscommon import SonicV2Connector, SonicDBConfig
from sonic_py_common import multi_asic
from utilities_common.constants import DEFAULT_NAMESPACE
import redis


# Constants
CONN = "conn"
CONN_TO = "connected_to"

EXCEP_DICT = {
    "INV_REQ": "Argument should be of type MatchRequest",
    "INV_DB": "DB provided is not valid",
    "NO_MATCHES": "No Entries found for Table|key_pattern provided",
    "NO_SRC": "Either one of db or file in the request should be non-empty",
    "NO_TABLE": "No 'table' name provided",
    "NO_KEY": "'key_pattern' cannot be empty",
    "NO_VALUE": "Field is provided, but no value is provided to compare with",
    "SRC_VAGUE": "Only one of db or file should be provided",
    "CONN_ERR": "Connection Error",
    "JUST_KEYS_COMPAT": "When Just_keys is set to False, return_fields should be empty",
    "BAD_FORMAT_RE_FIELDS": "Return Fields should be of list type",
    "NO_ENTRIES": "No Keys found after applying the filtering criteria",
    "FILE_R_EXEP": "Exception Caught While Reading the json cfg file provided",
    "INV_NS": "Namespace is invalid"
}


class MatchRequest:
    """
    Request Object which should be passed to the MatchEngine

    Attributes:
    "table"             : A Valid Table Name
    "key_pattern"       : Pattern of the redis-key to match. Defaults to "*". Eg: "*" will match all the keys.
                          Supports these glob style patterns. https://redis.io/commands/KEYS
    "field"             : Field to check for a match,Defaults to None
    "value"             : Value to match, Defaults to None
    "return_fields"     : An iterable type, where each element woudld imply a field to return from all the filtered keys
    "db"                : A Valid DB name, Defaults to "".
    "file"              : A Valid Config JSON file, Eg: copp_cfg.json, Defaults to "".
                          Only one of the db/file fields should have a non-empty string.
    "just_keys"         : If true, Only Returns the keys matched. Does not return field-value pairs. Defaults to True
    "ns"                : namespace argument, if nothing is provided, default namespace is used
    "match_entire_list" : When this arg is set to true, entire list is matched including the ",".
                          When False, the values are split based on "," and individual items are matched with
    """

    def __init__(self, **kwargs):
        self.table = kwargs["table"] if "table" in kwargs else None
        self.key_pattern = kwargs["key_pattern"] if "key_pattern" in kwargs else "*"
        self.field = kwargs["field"] if "field" in kwargs else None
        self.value = kwargs["value"] if "value" in kwargs else None
        self.return_fields = kwargs["return_fields"] if "return_fields" in kwargs else []
        self.db = kwargs["db"] if "db" in kwargs else ""
        self.file = kwargs["file"] if "file" in kwargs else ""
        self.just_keys = kwargs["just_keys"] if "just_keys" in kwargs else True
        self.ns = kwargs["ns"] if "ns" in kwargs else ""
        self.match_entire_list = kwargs["match_entire_list"] if "match_entire_list" in kwargs else False
        self.PbObj = kwargs["pb"] if "pb" in kwargs else None
        err = self.__static_checks()
        verbose_print(str(err))
        if err:
            raise Exception("Static Checks for the MatchRequest Failed, Reason: \n" + err)

    def __static_checks(self):

        if not self.db and not self.file:
            return EXCEP_DICT["NO_SRC"]

        if self.db and self.file:
            return EXCEP_DICT["SRC_VAGUE"]

        if not self.db:
            try:
                with open(self.file) as f:
                    json.load(f)
            except Exception as e:
                return EXCEP_DICT["FILE_R_EXEP"] + str(e)

        if not self.file and self.db not in SonicDBConfig.getDbList():
            return EXCEP_DICT["INV_DB"]

        if not self.table:
            return EXCEP_DICT["NO_TABLE"]

        if not isinstance(self.return_fields, list):
            return EXCEP_DICT["BAD_FORMAT_RE_FIELDS"]

        if not self.just_keys and self.return_fields:
            return EXCEP_DICT["JUST_KEYS_COMPAT"]

        if self.field and not self.value:
            return EXCEP_DICT["NO_VALUE"]

        if self.ns != DEFAULT_NAMESPACE and self.ns not in multi_asic.get_namespace_list():
            return EXCEP_DICT["INV_NS"] + " Choose From {}".format(multi_asic.get_namespace_list())

        verbose_print("MatchRequest Checks Passed")

        return ""

    def __str__(self):
        str = "----------------------- \n MatchRequest: \n"
        if self.db:
            str += "db:{} , ".format(self.db)
        if self.file:
            str += "file:{} , ".format(self.file)
        if self.table:
            str += "table:{} , ".format(self.table)
        if self.key_pattern:
            str += "key_pattern:{} , ".format(self.key_pattern)
        if self.field:
            str += "field:{} , ".format(self.field)
        if self.value:
            str += "value:{} , ".format(self.value)
        if self.just_keys:
            str += "just_keys:True ,"
        else:
            str += "just_keys:False ,"
        if len(self.return_fields) > 0:
            str += "return_fields: " + ",".join(self.return_fields) + " "
        if self.ns:
            str += "namespace: , " + self.ns
        if self.match_entire_list:
            str += "match_list: True , "
        else:
            str += "match_list: False , "
        return str


class SourceAdapter(ABC):
    """ Source Adaptor offers unified interface to Data Sources """

    def __init__(self):
        pass

    @abstractmethod
    def connect(self, db, ns):
        """ Return True for Success, False for failure """
        return False

    @abstractmethod
    def getKeys(self, db, table, key_pattern):
        return []

    @abstractmethod
    def get(self, db, key):
        return {}

    @abstractmethod
    def hget(self, db, key, field):
        return ""

    @abstractmethod
    def get_separator(self, db):
        return ""

    @abstractmethod
    def hgetall(self, db, key):
        raise NotImplementedError


class RedisSource(SourceAdapter):
    """ Concrete Adaptor Class for connecting to Redis Data Sources """

    def __init__(self, conn_pool):
        self.conn = None
        self.pool = conn_pool

    def connect(self, db, ns):
        try:
            self.conn = self.pool.get(db, ns)
        except Exception as e:
            verbose_print("RedisSource: Connection Failed\n" + str(e))
            return False
        return True

    def get_separator(self, db):
        return self.conn.get_db_separator(db)

    def getKeys(self, db, table, key_pattern):
        return self.conn.keys(db, table + self.get_separator(db) + key_pattern)

    def get(self, db, key):
        return self.conn.get_all(db, key)

    def hget(self, db, key, field):
        return self.conn.get(db, key, field)

    def hgetall(self, db, key):
        return self.conn.get_all(db, key)


class RedisPySource(SourceAdapter):
    """ Concrete Adaptor Class for connecting to APPL_DB using Redis library"""

    def __init__(self, conn_pool, pb_obj):
        self.conn = None
        self.pool = conn_pool
        self.pb_obj = pb_obj

    def get_decoded_value(self, pb_obj, key_val):
        try:
            from dump.dash_util import get_decoded_value
        except ModuleNotFoundError as e:
            verbose_print("RedisPySource: decoded value cannot be obtained \
                          since dash related library import issues\n" + str(e))
            return
        return get_decoded_value(pb_obj, key_val)

    def connect(self, db, ns):
        try:
            self.conn = self.pool.get_dash_conn(ns)
        except Exception as e:
            verbose_print("RedisPySource: Connection Failed\n" + str(e))
            return False
        return True

    def get_separator(self):
        return ":"

    def getKeys(self, db, table, key_pattern):
        bin_keys = self.conn.keys(table + self.get_separator() + key_pattern)
        return [key1.decode() for key1 in bin_keys]

    def get(self, db, key):
        key_val = self.conn.hgetall(key)
        return self.get_decoded_value(self.pb_obj, key_val)

    def hget(self, db, key, field):
        key_val = self.conn.hgetall(key)
        decoded_dict = self.get_decoded_value(self.pb_obj, key_val)
        return decoded_dict.get(field)

    def hgetall(self, db, key):
        key_val = self.conn.hgetall(key)
        return self.get_decoded_value(self.pb_obj, key_val)

class JsonSource(SourceAdapter):
    """ Concrete Adaptor Class for connecting to JSON Data Sources """

    def __init__(self):
        self.json_data = None

    def connect(self, db, ns):
        try:
            with open(db) as f:
                self.json_data = json.load(f)
        except Exception as e:
            verbose_print("JsonSource: Loading the JSON file failed" + str(e))
            return False
        return True

    def get_separator(self, db):
        return SonicDBConfig.getSeparator("CONFIG_DB")

    def getKeys(self, db, table, key_pattern):
        if table not in self.json_data:
            return []
        # https://docs.python.org/3.7/library/fnmatch.html
        kp = key_pattern.replace("[^", "[!")
        kys = fnmatch.filter(self.json_data[table].keys(), kp)
        return [table + self.get_separator(db) + ky for ky in kys]

    def get(self, db, key):
        sep = self.get_separator(db)
        table, key = key.split(sep, 1)
        return self.json_data.get(table, {}).get(key, {})

    def hget(self, db, key, field):
        sep = self.get_separator(db)
        table, key = key.split(sep, 1)
        return self.json_data.get(table, "").get(key, "").get(field, "")

    def hgetall(self, db, key):
        sep = self.get_separator(db)
        table, key = key.split(sep, 1)
        return self.json_data.get(table, {}).get(key)


class ConnectionPool:
    """ Caches SonicV2Connector objects for effective reuse """
    def __init__(self):
        self.cache = dict()  # Pool of SonicV2Connector objects

    def initialize_connector(self, ns):
        if not SonicDBConfig.isInit():
            if multi_asic.is_multi_asic():
                SonicDBConfig.load_sonic_global_db_config()
            else:
                SonicDBConfig.load_sonic_db_config()
        return SonicV2Connector(namespace=ns, use_unix_socket_path=True)

    def initialize_redis_conn(self, ns):
        """Return redis connection for APPL_DB,
        as APPL_DB is the only one which stores data in protobuf
        format which is not obtained fully by the SonicV2Connector
        get_all API
        """
        # The get_all function for a SonicV2Connector does not support binary data due to which we
        # have to use the redis Library. Relevant Issue: https://github.com/sonic-net/sonic-swss-common/issues/886
        return redis.Redis(unix_socket_path=SonicDBConfig.getDbSock("APPL_DB", ns),
                           db=SonicDBConfig.getDbId("APPL_DB", ns))

    def get(self, db_name, ns, update=False):
        """ Returns a SonicV2Connector Object and caches it for further requests """
        if ns not in self.cache:
            self.cache[ns] = {}
        if CONN not in self.cache[ns]:
            self.cache[ns][CONN] = self.initialize_connector(ns)
        if CONN_TO not in self.cache[ns]:
            self.cache[ns][CONN_TO] = set()
        if update or db_name not in self.cache[ns][CONN_TO]:
            self.cache[ns][CONN].connect(db_name)
            self.cache[ns][CONN_TO].add(db_name)
        return self.cache[ns][CONN]

    def get_dash_conn(self, ns):
        """ Returns a Redis Connection Object and caches it for further requests """
        if ns not in self.cache:
            self.cache[ns] = {}
        if "DASH_"+CONN not in self.cache[ns]:
            self.cache[ns]["DASH_"+CONN] = self.initialize_redis_conn(ns)
        return self.cache[ns]["DASH_"+CONN]

    def clear(self, namespace=None):
        if not namespace:
            self.cache.clear()
        elif namespace in self.cache:
            del self.cache[namespace]

    def fill(self, ns, conn, connected_to, dash_object=False):
        """ Update internal cache """
        if ns not in self.cache:
            self.cache[ns] = {}
        if dash_object:
            self.cache[ns]["DASH_"+CONN] = conn
            return
        self.cache[ns][CONN] = conn
        self.cache[ns][CONN_TO] = set(connected_to)


class MatchEngine:
    """
    Provide a MatchRequest to fetch the relevant keys/fv's from the data source
    Usage Guidelines:
    1) Instantiate the class once for the entire execution,
                to effectively use the caching of redis connection objects
    """
    def __init__(self, pool=None):
        if not isinstance(pool, ConnectionPool):
            self.conn_pool = ConnectionPool()
        else:
            self.conn_pool = pool

    def clear_cache(self, ns):
        self.conn_pool(ns)

    def get_redis_source_adapter(self):
        return RedisSource(self.conn_pool)

    def get_json_source_adapter(self):
        return JsonSource()

    def get_redis_py_adapter(self, pb_obj):
        return RedisPySource(self.conn_pool, pb_obj)

    def __get_source_adapter(self, req):
        src = None
        d_src = ""
        if req.PbObj:
            d_src = req.db
            src = self.get_redis_py_adapter(req.PbObj)
        elif req.db:
            d_src = req.db
            src = self.get_redis_source_adapter()
        else:
            d_src = req.file
            src = self.get_json_source_adapter()
        return d_src, src

    def __create_template(self):
        return {"error": "", "keys": [], "return_values": {}}

    def __display_error(self, err):
        template = self.__create_template()
        template['error'] = err
        verbose_print("MatchEngine: \n" + template['error'])
        return template

    def __filter_out_keys(self, src, req, all_matched_keys):
        # TODO: Custom Callbacks for Complex Matching Criteria
        if not req.field:
            return all_matched_keys

        filtered_keys = []
        for key in all_matched_keys:
            f_values = src.hget(req.db, key, req.field)
            if not f_values:
                continue
            if "," in f_values and not req.match_entire_list:
                f_value = f_values.split(",")
            else:
                f_value = [f_values]
            if req.value in f_value:
                filtered_keys.append(key)
        return filtered_keys

    def __fill_template(self, src, req, filtered_keys, template):
        for key in filtered_keys:
            temp = {}
            if not req.just_keys:
                temp[key] = src.get(req.db, key)
                template["keys"].append(temp)
            elif len(req.return_fields) > 0:
                template["keys"].append(key)
                template["return_values"][key] = {}
                for field in req.return_fields:
                    template["return_values"][key][field] = src.hget(req.db, key, field)
            else:
                template["keys"].append(key)
        verbose_print("Return Values:" + str(template["return_values"]))
        return template

    def fetch(self, req):
        """ Given a request obj, find its match in the data source provided """
        if not isinstance(req, MatchRequest):
            return self.__display_error(EXCEP_DICT["INV_REQ"])

        verbose_print(str(req))

        if not req.key_pattern:
            return self.__display_error(EXCEP_DICT["NO_KEY"])

        d_src, src = self.__get_source_adapter(req)
        if not src.connect(d_src, req.ns):
            return self.__display_error(EXCEP_DICT["CONN_ERR"])

        template = self.__create_template()
        all_matched_keys = src.getKeys(req.db, req.table, req.key_pattern)
        if not all_matched_keys:
            return self.__display_error(EXCEP_DICT["NO_MATCHES"])

        filtered_keys = self.__filter_out_keys(src, req, all_matched_keys)
        verbose_print("Filtered Keys:" + str(filtered_keys))
        if not filtered_keys:
            return self.__display_error(EXCEP_DICT["NO_ENTRIES"])
        return self.__fill_template(src, req, filtered_keys, template)


class MatchRequestOptimizer():
    """
    A Stateful Wrapper which reduces the number of calls to redis by caching the keys
    The Cache saves all the fv-pairs for a key
    Caching would only happen when the "key_pattern" is an absolute key and is not a glob-style pattern
    """

    def __init__(self, m_engine):
        self.__key_cache = {}
        self.m_engine = m_engine

    def __mutate_request(self, req):
        """
        Mutate the Request to fetch all the fv pairs, regardless of the original request
        Save the return_fields and just_keys args of original request
        """
        fv_requested = []
        ret_just_keys = req.just_keys
        fv_requested = copy.deepcopy(req.return_fields)
        if ret_just_keys:
            req.just_keys = False
            req.return_fields = []
        return req, fv_requested, ret_just_keys

    def __mutate_response(self, ret, fv_requested, ret_just_keys):
        """
        Mutate the Response based on what was originally asked.
        """
        if not ret_just_keys:
            return ret
        new_ret = {"error": "", "keys": [], "return_values": {}}
        for key_fv in ret["keys"]:
            if isinstance(key_fv, dict):
                keys = key_fv.keys()
                new_ret["keys"].extend(keys)
                for key in keys:
                    new_ret["return_values"][key] = {}
                    for field in fv_requested:
                        new_ret["return_values"][key][field] = key_fv[key].get(field, "")
        return new_ret

    def __fill_cache(self, ret):
        """
        Fill the cache with all the fv-pairs
        """
        for key_fv in ret["keys"]:
            keys = key_fv.keys()
            for key in keys:
                self.__key_cache[key] = key_fv[key]

    def __fetch_from_cache(self, key, req):
        """
        Cache will have all the fv-pairs of the requested key
        Response will be tailored based on what was asked
        """
        new_ret = {"error": "", "keys": [], "return_values": {}}
        if not req.just_keys:
            new_ret["keys"].append(self.__key_cache[key])
        else:
            new_ret["keys"].append(key)
            if req.return_fields:
                new_ret["return_values"][key] = {}
                for field in req.return_fields:
                    new_ret["return_values"][key][field] = self.__key_cache[key][field]
        return new_ret

    def fetch(self, req_orig):
        req = copy.deepcopy(req_orig)
        sep = "|"
        if req.db:
            sep = SonicDBConfig.getSeparator(req.db)
        key = req.table + sep + req.key_pattern
        if key in self.__key_cache:
            verbose_print("Cache Hit for Key: {}".format(key))
            return self.__fetch_from_cache(key, req)
        else:
            verbose_print("Cache Miss for Key: {}".format(key))
            req, fv_requested, ret_just_keys = self.__mutate_request(req)
            ret = self.m_engine.fetch(req)
            if ret["error"]:
                return ret
            self.__fill_cache(ret)
            return self.__mutate_response(ret, fv_requested, ret_just_keys)
