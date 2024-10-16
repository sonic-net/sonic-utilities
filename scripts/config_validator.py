#!/usr/bin/env python3
import json
import argparse
import sonic_yang

from sonic_py_common import logger

YANG_MODELS_DIR = "/usr/local/yang-models"
SYSLOG_IDENTIFIER = 'config_validator'

# Global logger instance
log = logger.Logger(SYSLOG_IDENTIFIER)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c',
                        dest='config',
                        metavar='config file',
                        type=str,
                        required=True,
                        help='the config file to be validated',
                        default=None)

    args = parser.parse_args()
    config_file = args.config
    with open(config_file) as fp:
        config = json.load(fp)
    # Run yang validation
    yang_parser = sonic_yang.SonicYang(YANG_MODELS_DIR)
    yang_parser.loadYangModel()
    try:
        yang_parser.loadData(configdbJson=config)
        yang_parser.validate_data_tree()
    except sonic_yang.SonicYangException as e:
        log.log_error("Yang validation failed: " + str(e))
        raise
    if len(yang_parser.tablesWithOutYang):
        log.log_error("Tables without yang models: " + str(yang_parser.tablesWithOutYang))
        raise Exception("Tables without yang models: " + str(yang_parser.tablesWithOutYang))


if __name__ == "__main__":
    main()
