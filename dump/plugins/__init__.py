import os
import pkgutil
import importlib
from .executor import Executor
from sonic_py_common.syslogger import SysLogger

dump_modules = {}
pkg_dir = os.path.dirname(__file__)

log = SysLogger()
# import child classes automatically
for (module_loader, name, ispkg) in pkgutil.iter_modules([pkg_dir]):
    try:
        importlib.import_module('.' + name, __package__)
    except ModuleNotFoundError as e:
        if e.name != "dash_api":
            # dash_api is only used in a specific platform
            log.log_debug("dump utility - dash_api package not found for platform")
            raise

# Classes inheriting Executor
dump_modules = {cls.__name__.lower(): cls for cls in Executor.__subclasses__()}
