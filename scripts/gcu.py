#!/usr/bin/env python3

"""
Generic Config Updater (GCU) Script
====================================
Thin wrapper that delegates all logic to ``generic_config_updater.main``.
Kept for backward compatibility as a host-level script entry point.
"""

import os
import sys

# Add the parent directory to Python path to import sonic-utilities modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from generic_config_updater.main import main  # noqa: E402

if __name__ == '__main__':
    main()
