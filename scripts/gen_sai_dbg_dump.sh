#!/bin/sh

. /usr/local/bin/gen_sai_dbg_dump_lib.sh

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
# Main script logic
# Description:
#  This is the main entry point of the script, which handles the generation
#  and retrieval of the SAI debug dump file. It parses command-line arguments,
#  ensures necessary directories and the `syncd` container are available, and
#  triggers the SAI debug dump process through Redis. The script waits for the
#  dump file to be generated and then copies it from the Docker container to
#  the specified location on the local system.
#
# Globals:
#  None
#
# Arguments:
#  -f <filename> : Specifies the output filename for the SAI debug dump file.
#  -h            : Displays usage information.
#
# Returns:
#  0 - On success
#  1 - On failure
###############################################################################
main() {
    # Parse arguments
    while getopts ":f:h" opt; do
        case $opt in
            f)
                sai_dump_filename="$OPTARG"
                ;;
            h)
                usage
                exit 0
                ;;
            /?)
                echo "Invalid option: -$OPTARG" >&2
                usage
                exit 1
                ;;
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

    # Ensure the syncd container is running
    if [ "$(docker container inspect -f '{{.State.Running}}' syncd)" != "true" ]; then
        echo "Error: syncd container is not running."
        exit 1
    fi

    generate_sai_dump "$syncd_sai_dump_filename"
    if [ $? -ne 0 ]; then
        echo "Failed to generate SAI debug dump."
        exit 1
    fi

    # Copy the dump file from the Docker container
    local 
    if ! copy_from_docker syncd $syncd_sai_dump_filename $sai_dump_filename; then
        echo "Error: Failed to copy the SAI dump file from the container."
        exit 1
    fi

    # Remove the dump file from the Docker container
    docker exec syncd rm -rf $syncd_sai_dump_filename;
    echo "$sai_dump_filename is ready!!!"
    exit 0
}

main "$@"
