#!/bin/bash

GENERATE_DUMP_FILE="/tmp/generate_dump_tmp"
ROUTE_FILE="/tmp/route_summary.txt"
shopt -s expand_aliases
alias eval="mock_eval"
alias save_cmd="mock_save_cmd"

source $GENERATE_DUMP_FILE

mock_route_summary(){
    local routenum=$1
    echo "\
    {
    \"routesTotal\":$routenum
    }" > $ROUTE_FILE
}

route_num=0
save_cmd_arguments=""

# Mock eval command in function get_route_table_size_by_asic_id_and_ipver
mock_eval(){
    mock_route_summary $route_num
}

# Mock function save_cmd called in function save_saidump_by_route_size
mock_save_cmd(){    
    save_cmd_arguments="$save_cmd_arguments$*\n"
}

test_saidump(){
    NUM_ASICS=$1
    route_num=$2
    save_saidump_by_route_size > /dev/null
    echo -e $save_cmd_arguments
    local ret=$save_cmd_arguments
    save_cmd_arguments=""
    rm $ROUTE_FILE
    return $ret    
}