#!/bin/sh

###############################################################################
# generate_sai_dump
# Description:
#  This function triggers the generation of a SAI debug dump file in the 
#  `syncd` Docker container through Redis and waits for the file to be ready.
#
# Arguments:
#  $1 - Filename for the SAI debug dump file.
#
# Returns:
#  0 - On success
#  1 - On failure
###############################################################################
generate_sai_dump() {
    local DB=4
    local KEY="DBG_GEN_DUMP_TABLE|DUMP"
    local STATUS_KEY="DBG_GEN_DUMP_STATS_TABLE|DUMP"
    local FIELD="file"
    local STATUS_FIELD="status"
    local STATUS="1"

    local TIMEOUT_FOR_GEN_DBG_DUMP_FILE_READYNESS=10
    local INTERVAL=1
    local TIME_PASSED=0
    local EXISTS
    
    local SYNCD_DUMP_FILE="$1"
    if [ -z "$SYNCD_DUMP_FILE" ]; then
        echo "Error: No filename provided for the SAI debug dump file."
        return 1
    fi

    # Extract the directory from the SYNCD_DUMP_FILE path
    local SYNCD_DUMP_DIR
    SYNCD_DUMP_DIR=$(dirname "$SYNCD_DUMP_FILE")

    # Ensure the directory exists in the syncd container; if not, create it
    if ! docker exec syncd test -d "$SYNCD_DUMP_DIR"; then
        echo "Directory '$SYNCD_DUMP_DIR' does not exist in the syncd container. Creating it..."
        if ! docker exec syncd mkdir -p "$SYNCD_DUMP_DIR"; then
            echo "Error: Failed to create directory '$SYNCD_DUMP_DIR' inside the syncd container."
            return 1
        fi
    fi

    # Delete the tables from STATE_DB before triger the dump file
    redis-cli -n $DB DEL $KEY > /dev/null 2>&1
    redis-cli -n $DB DEL $STATUS_KEY > /dev/null 2>&1

    # Set the DBG_GEN_DUMP in the Redis DB to trigger the dump generation
    if ! redis-cli -n $DB HSET $KEY $FIELD $SYNCD_DUMP_FILE > /dev/null 2>&1; then
        echo "Error: Failed to set Redis key."
        return 1
    fi

    # Timeout and interval for checking status of file readiness

    while [ $TIME_PASSED -lt $TIMEOUT_FOR_GEN_DBG_DUMP_FILE_READYNESS ]; do
        EXISTS=$(redis-cli -n $DB EXISTS "$STATUS_KEY" 2>/dev/null | grep -o '^[0-9]*$')
        if [ "$EXISTS" -eq 1 ]; then
            STATUS=$(redis-cli -n $DB HGET "$STATUS_KEY" "$STATUS_FIELD" 2>/dev/null | grep -o '^[0-9]*$')
            break
        fi

        sleep $INTERVAL
        TIME_PASSED=$((TIME_PASSED + INTERVAL))
    done

    # Delete the tables from STATE_DB after triger the dump file
    redis-cli -n $DB DEL $KEY > /dev/null 2>&1
    redis-cli -n $DB DEL $STATUS_KEY > /dev/null 2>&1

    if [ "$STATUS" -ne 0 ]; then
        echo "Error: dump file operation failed, Status $STATUS"
        return 1
    fi

    if [ $TIME_PASSED -ge $TIMEOUT_FOR_GEN_DBG_DUMP_FILE_READYNESS ]; then
        echo "Timeout reached. Status was not ready in time."
        return 1
    fi

    # Ensure the file exists in the Docker container
    if ! docker exec syncd test -f $SYNCD_DUMP_FILE; then
        echo "Error: SAI dump file does not exist in the syncd container."
        return 1
    fi

    return 0
}
