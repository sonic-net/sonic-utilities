try:
    from sonic_platform.platform import Platform
    from . import main
except ImportError as e:
    raise ImportError("Required module not found: {}".format(str(e)))
