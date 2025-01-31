#!/bin/bash

###############################################################################
# Prints the usage information.
# Globals:
#  None
# Arguments:
#  None
# Returns:
#  None
###############################################################################
usage() {
    cat <<EOF
Usage: $0 [OPTIONS] -f <filename>

Generate and retrieve the SAI debug dump file from the syncd Docker container.

OPTIONS:
    -f <filename>   Specify the destination file path for the SAI debug dump.
    -h              Display this help and exit.

EXAMPLES:
    $0 -f /var/log/dbg_gen_dump.log
EOF
}

###############################################################################
# Copies a given file from a specified Docker container to the given target location.
# Globals:
#  TIMEOUT_MIN
# Arguments:
#  docker: Docker container name
#  filename: The filename to copy
#  destination: Destination filename
# Returns:
#  None
###############################################################################
copy_from_docker() {
    TIMEOUT_MIN="1"
    local docker=$1
    local filename=$2
    local dstpath=$3
    local timeout_cmd="timeout --foreground ${TIMEOUT_MIN}m"

    local touch_cmd="sudo docker exec ${docker} touch ${filename}"
    local cp_cmd="sudo docker cp ${docker}:${filename} ${dstpath}"

    RC=0
    eval "${timeout_cmd} ${touch_cmd}" || RC=$?
    if [ $RC -ne 0 ]; then
        echo "Command: $touch_cmd timed out after ${TIMEOUT_MIN} minutes."
    fi
    eval "${timeout_cmd} ${cp_cmd}" || RC=$?
    if [ $RC -ne 0 ]; then
        echo "Command: $cp_cmd timed out after ${TIMEOUT_MIN} minutes."
    fi
}

###############################################################################
# generate_sai_dump
# Description:
#  This function triggers the generation of a SAI debug dump file in the 
#  `syncd` Docker container through Redis and waits for the file to be ready.
# Arguments:
#  $1 - Filename for the SAI debug dump file.
#  $2 - Optional timeout for file readiness (default: 10 seconds).
# Returns:
#  0 - On success
#  1 - On failure
###############################################################################
generate_sai_dump() {
    local DB=0
    local KEY="DBG_GEN_DUMP_TABLE:DUMP"
    local STATUS_KEY="DBG_GEN_DUMP_STATUS_TABLE:DUMP"
    local FIELD="file"
    local STATUS_FIELD="status"
    local STATUS="1"

    local SYNCD_DUMP_FILE="$1"
    local TIMEOUT_FOR_GEN_DBG_DUMP_FILE_READYNESS="${2:-60}"
    local INTERVAL=1
    local TIME_PASSED=0

    if [ -z "$SYNCD_DUMP_FILE" ]; then
        echo "Error: No filename provided for the SAI debug dump file."
        return 1
    fi

    # Ensure the syncd container is running
    if [[ "$( docker container inspect -f '{{.State.Running}}' syncd )" != "true" ]]; then
        echo "Error: syncd container is not running."
        return 1
    fi

    # Extract the directory from the SYNCD_DUMP_FILE path
    local SYNCD_DUMP_DIR
    SYNCD_DUMP_DIR=$(dirname "$SYNCD_DUMP_FILE")

    # Ensure the directory exists in the syncd container; if not, create it
    if ! docker exec syncd test -d "$SYNCD_DUMP_DIR"; then
        #echo "Creating directory '$SYNCD_DUMP_DIR' inside the syncd container..."
        if ! docker exec syncd mkdir -p "$SYNCD_DUMP_DIR"; then
            echo "Error: Failed to create directory inside the syncd container."
            return 1
        fi
    fi

    # Delete the tables from STATE_DB before triggering the dump file
    redis-cli -n $DB DEL $KEY > /dev/null 2>&1
    redis-cli -n $DB DEL $STATUS_KEY > /dev/null 2>&1

    # Set the DBG_GEN_DUMP in the Redis DB to trigger the dump generation
    if ! redis-cli SADD "DBG_GEN_DUMP_TABLE_KEY_SET" "DUMP" > /dev/null 2>&1; then
        echo "Error: Failed to publish message to Redis DBG_GEN_DUMP_TABLE_CHANNEL."
        return 1
    fi

    if ! redis-cli -n $DB HSET "_$KEY" $FIELD $SYNCD_DUMP_FILE > /dev/null 2>&1; then
        echo "Error: Failed to set Redis key."
        return 1
    fi

    if ! redis-cli PUBLISH "DBG_GEN_DUMP_TABLE_CHANNEL@0" "G" > /dev/null 2>&1; then
        echo "Error: Failed to publish message to Redis DBG_GEN_DUMP_TABLE_CHANNEL."
        return 1
    fi

    # Timeout and interval for checking status of file readiness
    while [ $TIME_PASSED -lt $TIMEOUT_FOR_GEN_DBG_DUMP_FILE_READYNESS ]; do
        # Get the status field value
        STATUS=$(redis-cli -n $DB HGET "$STATUS_KEY" "$STATUS_FIELD" 2>/dev/null | grep -o '^[0-9]*$')

        # Check if STATUS is non-empty
        if [ -n "$STATUS" ]; then
            # STATUS field exists; you can use it as needed            
            break
        fi
        sleep $INTERVAL
        TIME_PASSED=$((TIME_PASSED + INTERVAL))
    done

    # Delete the tables from STATE_DB after triggering the dump file
    redis-cli -n $DB DEL $KEY > /dev/null 2>&1
    redis-cli -n $DB DEL $STATUS_KEY > /dev/null 2>&1

    if [ -n "$STATUS" ] && [ "$STATUS" -ne 0 ]; then
        echo "Error: dump file operation failed, Status $STATUS"
        return 1
    fi

    if [ $TIME_PASSED -ge $TIMEOUT_FOR_GEN_DBG_DUMP_FILE_READYNESS ]; then
        echo "Timeout reached. Status was not ready in time."
        return 1
    fi

    # Poll for file existence in the syncd container with a timeout
    TIME_PASSED=0
    while [ $TIME_PASSED -lt $TIMEOUT_FOR_GEN_DBG_DUMP_FILE_READYNESS ]; do
        if docker exec syncd test -f "$SYNCD_DUMP_FILE"; then
            #echo "SAI dump file successfully generated in the syncd container."
            break
        fi
        sleep $INTERVAL
        TIME_PASSED=$((TIME_PASSED + INTERVAL))
    done

    if [ $TIME_PASSED -ge $TIMEOUT_FOR_GEN_DBG_DUMP_FILE_READYNESS ]; then
        echo "Error: SAI dump file does not exist in the syncd container after waiting ${TIME_PASSED} seconds."
        return 1
    fi

    return 0
}

###############################################################################
# Main script logic
# Description:
#  This is the main entry point of the script, which handles the generation
#  and retrieval of the SAI debug dump file. It parses command-line arguments,
#  ensures necessary directories are available, and triggers the SAI debug dump
#  process through Redis. The script waits for the dump file to be generated and 
#  then copies it from the Docker container to the specified location on the local system.
#
# Globals:
#  None
#
# Arguments:
#  -f <filename> : Specifies the output filename for the SAI debug dump file.
#  -t <timeout>  : Optional timeout for file readiness (in seconds).
#  -h            : Displays usage information.
#
# Returns:
#  0 - On success
#  1 - On failure
###############################################################################
main() {
    local sai_dump_filename=""
    local timeout_for_file_readiness=""

    # Parse arguments
    while getopts ":f:t:h" opt; do
        case $opt in
            f) sai_dump_filename="$OPTARG" ;;
            t) timeout_for_file_readiness="$OPTARG" ;;
            h) usage; exit 0 ;;
            ?) echo "Invalid option: -$OPTARG" >&2; usage; exit 1 ;;
        esac
    done

    local syncd_sai_dump_filename="/var/log/dbg_gen_dump.log"

    # Ensure a filename was provided
    if [ -z "$sai_dump_filename" ]; then
        echo "Error: Missing filename."
        usage
        exit 1
    fi

    # Ensure the directory exists, create it if it doesn't
    if [ ! -d "$(dirname "$sai_dump_filename")" ]; then
        sudo mkdir -p "$(dirname "$sai_dump_filename")"
    fi
    
    # Call generate_sai_dump with or without the timeout argument
    if [ -n "$timeout_for_file_readiness" ]; then
        #echo  generate_sai_dump "$syncd_sai_dump_filename" "$timeout_for_file_readiness"
        generate_sai_dump "$syncd_sai_dump_filename" "$timeout_for_file_readiness"
    else
        #echo  generate_sai_dump "$syncd_sai_dump_filename"
        generate_sai_dump "$syncd_sai_dump_filename"
    fi

    if [ $? -ne 0 ]; then
        echo "Failed to generate SAI debug dump."
        exit 1
    fi

    # Copy the dump file from the Docker container     
    if ! copy_from_docker syncd $syncd_sai_dump_filename $sai_dump_filename; then
        echo "Error: Failed to copy the SAI dump file from the container."
        exit 1
    fi

    # Remove the dump file from the Docker container
    docker exec syncd rm -rf $syncd_sai_dump_filename
    echo "file '$sai_dump_filename' is ready!!!"
    exit 0
}

# Only call main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
