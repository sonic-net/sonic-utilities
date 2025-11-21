#!/usr/bin/env python3

"""
bmc_techsupport script.
    This script is invoked by the generate_dump script for BMC techsupport fetching,
    but also can be invoked manually to trigger and collect BMC debug log dump.

    The usage of this script is divided into two parts:
        1. Triggering BMC debug log dump Redfish task
            * In this case the script triggers a POST request to BMC to start collecting debug log dump.
            * In this script we will print the new task-id to the console output
              to collect the debug log dump once the task-id has finished.
            * This step is non-blocking, task-id is returned immediately.
            * It is invoked with the parameter '--mode trigger'
              E.g.: /usr/local/bin/bmc_techsupport.py --mode trigger

        2. Collecting BMC debug log dump
            * In this step we will wait for the task-id to finish if it has not finished.
            * Blocking action until we get the file or encounter an ERROR or Timeout.
            * It is invoked with the parameter '--mode collect --task <task-id> --path <path>'
              E.g.: /usr/local/bin/bmc_techsupport.py --mode collect --path <path> --task <task-id>

    Basically, in the generate_dump script we will call the first method
    at the beginning of its process and the second method towards the end of the process.
"""


import argparse
import os
import sonic_platform
import time
from sonic_py_common.syslogger import SysLogger


TIMEOUT_FOR_GET_BMC_DEBUG_LOG_DUMP_IN_SECONDS = 60
SYSLOG_IDENTIFIER = "bmc_techsupport"
log = SysLogger(SYSLOG_IDENTIFIER)


class BMCDebugDumpExtractor:
    '''
        Class to trigger and extract BMC debug log dump
    '''

    INVALID_TASK_ID = '-1'
    TRIGGER_MODE = 'trigger'
    COLLECT_MODE = 'collect'

    def __init__(self):
        platform = sonic_platform.platform.Platform()
        chassis = platform.get_chassis()
        self.bmc = chassis.get_bmc()

    def trigger_debug_dump(self):
        '''
        Trigger BMC debug log dump and prints the running task id to the console output
        '''
        try:
            task_id = BMCDebugDumpExtractor.INVALID_TASK_ID
            log.log_info("Triggering BMC debug log dump Redfish task")
            (ret, (task_id, err_msg)) = self.bmc.trigger_bmc_debug_log_dump()
            if ret != 0:
                raise Exception(err_msg)
            log.log_info(f'Successfully triggered BMC debug log dump - Task-id: {task_id}')
        except Exception as e:
            log.log_error(f'Failed to trigger BMC debug log dump - {str(e)}')
        finally:
            # generate_dump script captures the task id from the console output via $(...) syntax
            print(f'{task_id}')

    def extract_debug_dump_file(self, task_id, filepath):
        '''
            Extract BMC debug log dump file for the given task id and save it to the given filepath
        '''
        try:
            if task_id is None or task_id == BMCDebugDumpExtractor.INVALID_TASK_ID:
                raise Exception('Invalid Task-ID')
            log_dump_dir = os.path.dirname(filepath)
            log_dump_filename = os.path.basename(filepath)
            if not log_dump_dir or not log_dump_filename:
                raise Exception(f'Invalid given filepath: {filepath}')
            if not log_dump_filename.endswith('.tar.xz'):
                raise Exception(f'Invalid given filepath extension, should be .tar.xz: {log_dump_filename}')

            start_time = time.time()
            log.log_info("Collecting BMC debug log dump")
            ret, err_msg = self.bmc.get_bmc_debug_log_dump(
                task_id=task_id,
                filename=log_dump_filename,
                path=log_dump_dir,
                timeout=TIMEOUT_FOR_GET_BMC_DEBUG_LOG_DUMP_IN_SECONDS
            )
            end_time = time.time()
            duration = end_time - start_time
            if ret != 0:
                timeout_msg = (
                    f'BMC debug log dump does not finish within '
                    f'{TIMEOUT_FOR_GET_BMC_DEBUG_LOG_DUMP_IN_SECONDS} seconds: {err_msg}'
                )
                log.log_error(timeout_msg)
                raise Exception(err_msg)
            log.log_info(f'Finished successfully collecting BMC debug log dump. Duration: {duration} seconds')
        except Exception as e:
            log.log_error(f'Failed to collect BMC debug log dump - {str(e)}')


def main(mode, task_id, filepath):
    try:
        extractor = BMCDebugDumpExtractor()
        if extractor.bmc is None:
            raise Exception('BMC instance is not available')
    except Exception as e:
        log.log_error(f'Failed to initialize BMCDebugDumpExtractor: {str(e)}')
        if mode == BMCDebugDumpExtractor.TRIGGER_MODE:
            print(f'{BMCDebugDumpExtractor.INVALID_TASK_ID}')
        return
    if mode == BMCDebugDumpExtractor.TRIGGER_MODE:
        extractor.trigger_debug_dump()
    elif mode == BMCDebugDumpExtractor.COLLECT_MODE:
        if not task_id or not filepath:
            log.log_error("Both --task and --path arguments are required for 'collect' mode")
            return
        extractor.extract_debug_dump_file(task_id, filepath)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BMC tech-support generator script.")
    parser.add_argument(
        '-m', '--mode',
        choices=['collect', 'trigger'],
        required=True,
        help="Mode of operation: 'collect' for collecting debug dump or 'trigger' for triggering debug dump task."
    )
    parser.add_argument('-p', '--path', help="Path to save the BMC debug log dump file.")
    parser.add_argument('-t', '--task', help="Task-ID to monitor and collect the debug dump from.")
    args = parser.parse_args()
    mode = args.mode
    task_id = args.task
    filepath = args.path
    main(mode, task_id, filepath)
