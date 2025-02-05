from abc import ABC, abstractmethod
from dump.match_infra import MatchEngine


class Executor(ABC):
    """
    Abstract Class which should be extended from in
    order to be included in the dump state CLI
    """

    ARG_NAME = "id"  # Arg Identifier
    CONFIG_FILE = ""  # Path to config file, if any

    def __init__(self, match_engine=None):
        if not isinstance(match_engine, MatchEngine):
            self.match_engine = MatchEngine(None)
        else:
            self.match_engine = match_engine
        self.ret_temp = {}

    @abstractmethod
    def execute(self, params):
        pass

    @abstractmethod
    def get_all_args(self, ns):
        pass

    def return_pb2_obj(self):
        return None

    def add_to_ret_template(self, table, db, keys, err, add_to_tables_not_found=True):
        if db not in self.ret_temp:
            return []

        if not err and keys:
            self.ret_temp[db]["keys"].extend(keys)
            return keys
        elif add_to_tables_not_found:
            self.ret_temp[db]["tables_not_found"].extend([table])
        return []
