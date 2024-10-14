import os
import sys
import pkgutil
import importlib
from .executor import Executor

dump_modules = {}
pkg_dir = os.path.dirname(__file__)

# import child classes automatically
for (module_loader, name, ispkg) in pkgutil.iter_modules([pkg_dir]):
    try:
        importlib.import_module('.' + name, __package__)
    except ImportError as e:
        pass

# Classes inheriting Executor
dump_modules = {cls.__name__.lower(): cls for cls in Executor.__subclasses__()}
