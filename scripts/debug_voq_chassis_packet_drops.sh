#!/usr/bin/bash
# defaults for env vars
sleep_period=${sleep_period:-0}
maxiter=${maxiter:-25} # all but 4 iterations will be polling Egress drops
log=${log:-/dev/stdout}
time_format="%D %T.%6N"
delim="END"
# options
ing_check_mc=${ing_check_mc:-1}
ing_check_macsec=${ing_check_macsec:-1}
egr_check_mc=${egr_check_mc:-1}
egr_check_pmf_hit_bits=${egr_check_pmf_hit_bits:-1} 
egr_diag_counter_g=${egr_diag_counter_g:-1}

declare -a cores=("0" "1")
declare -a asics=("0" "1")
queue_pair_mask_a=(0 0 0 0)
dsp_map_a=(0 0 0 0)

timestamp(){
    curr_time=$(date +"$time_format")
    echo "$curr_time $logmsg" >> $log
}

print_pqp_reasons() {
    disc_reasons=$((16#${disc_reasons}))
    if [ $disc_reasons -eq 0 ]; then echo "none" >> $log ; fi
    if [ $(($disc_reasons & 1))  -ne 0 ] ; then echo "0- Total PDs threshold violated" >> $log ; fi
    if [ $(($disc_reasons & 2))  -ne 0 ] ; then echo "1- Total PDs UC pool size threshold violated" >> $log ; fi
    if [ $(($disc_reasons & 4))  -ne 0 ] ; then echo "2- Per port UC PDs threshold" >> $log ; fi
    if [ $(($disc_reasons & 8))  -ne 0 ] ; then echo "3- Per queue UC PDs thresholds">> $log ; fi
    if [ $(($disc_reasons & 16)) -ne 0 ] ; then echo "4- Per port UC DBs threshold">> $log ; fi
    if [ $(($disc_reasons & 32)) -ne 0 ] ; then echo "5- Per queue UC DBs threshold">> $log ; fi
    if [ $(($disc_reasons & 64)) -ne 0 ] ; then echo "6- Per queue disable bit">> $log ; fi
    if [ $(($disc_reasons & 128)) -ne 0 ] ; then echo "7- Undefined">> $log ; fi
    if [ $(($disc_reasons & 256)) -ne 0 ] ; then echo "8- Total PDs MC pool size threshold">> $log ; fi
    if [ $(($disc_reasons & 512)) -ne 0 ] ; then echo "9- Per interface PDs threhold">> $log; fi
    if [ $(($disc_reasons & 1024)) -ne 0 ] ; then echo "10- MC SP threshold">> $log ; fi
    if [ $(($disc_reasons & 2048)) -ne 0 ] ; then echo "11- per MC-TC threshold">> $log ; fi
    if [ $(($disc_reasons & 4096)) -ne 0 ] ; then echo "12- MC PDs per port threshold">> $log ; fi
    if [ $(($disc_reasons & 8192)) -ne 0 ] ; then echo "13- MC PDs per queue threshold">> $log ; fi
    if [ $(($disc_reasons & 16384)) -ne 0 ] ; then echo "14- MC per port size (bytes) threshold">> $log ; fi
    if [ $(($disc_reasons & 32768)) -ne 0 ] ; then echo "15- MC per queue size(bytes) thresholds">> $log ; fi
}
print_rqp_reasons(){
    disc_reasons=$((16#${disc_reasons}))
    if [ $disc_reasons -eq 0 ]; then echo "none" >> $log ; fi
    if [ $(($disc_reasons & 1))  -ne 0 ] ; then echo "0- Total DBs threshold violated" >> $log ; fi
    if [ $(($disc_reasons & 2))  -ne 0 ] ; then echo "1- Total UC DBs pool size threshold violated" >> $log ; fi
    if [ $(($disc_reasons & 4))  -ne 0 ] ; then echo "2- UC packet discarded in EMR because UC FIFO is full" >> $log ; fi
    if [ $(($disc_reasons & 8))  -ne 0 ] ; then echo "3- MC HP packetd discarded in EMR because MC FIFO is full">> $log ; fi
    if [ $(($disc_reasons & 16)) -ne 0 ] ; then echo "4- MC LP packetd discarded in EMR because MC FIFO is full">> $log ; fi
    if [ $(($disc_reasons & 32)) -ne 0 ] ; then echo "5- Total MC DBs pool size threshold violated">> $log ; fi
    if [ $(($disc_reasons & 64)) -ne 0 ] ; then echo "6- Packet-DP is not eligible to take from shared DBs resources">> $log ; fi
    if [ $(($disc_reasons & 128)) -ne 0 ] ; then echo "7- USP DBs threshold violated">> $log ; fi
    if [ $(($disc_reasons & 256)) -ne 0 ] ; then echo "8- Discrete-Partitioning method: MC-TC DBs threshold violated">> $log ; fi
    if [ $(($disc_reasons & 512)) -ne 0 ] ; then echo "9- Strict-priority method: MC-TC mapped to SP0 DBs threshold violated">> $log; fi
    if [ $(($disc_reasons & 1024)) -ne 0 ] ; then echo "10- Strict-Priority method: MC-TC mapped to SP1 DBs threshold violated">> $log ; fi
}

# whenever port_disabled mask change, print the up ports
# (according to the queue-pair mask and DSP port mapping, which is what matters )

check_new_port_state() {
    last_queue_pair_mask=${queue_pair_mask_a[$index]}
    queue_pair_mask=$(bcmcmd -n $asic "g hex ECGM_CGM_QUEUE_PAIR_DISABLED.ECGM${core}" | head -n +2 | tail -1)
    if [ "$queue_pair_mask" == "$last_queue_pair_mask" ] ; then
        return
    fi
    queue_pair_mask_a[$index]=$queue_pair_mask
    logmsg="EGRESS_QPAIR asic $asic core $core new disabled mask: $queue_pair_mask"
    timestamp

    start_dsp=$core
    let amt=255-$core
    dsp_map_a[$index]=$(bcmcmd -n $asic "d SCH_DSP_2_PORT_MAP_DSPP.SCH${core} $start_dsp $amt")
 
    hr_num=0
    for pos in {-3..-129..-2}; do # todo
        byte=${queue_pair_mask:pos:2}
        if [ $hr_num -le 8 ] ; then
            hr_num_hex="HR_NUM=${hr_num}"
        else
            hr_num_hex=$(printf "HR_NUM=0x%x" $hr_num)
        fi
        hr_num=$(( hr_num + 8))
        entry=$(echo ${dsp_map_a[$index]} | sed -e "s/\r/\r\n/g" | grep -m 1 "$hr_num_hex")
        found=$?
        if [ $found -eq 1 ] ; then
            continue
        fi
        dsp_port=$(echo $entry |grep -o  "\[.*\]"| tr -dc '[:alnum:]')
        if [ "$byte" = "ff" ]; then
            printf "DOWN %3d ${entry}\n" $dsp_port >> $log
        else
            printf "UP   %3d ${entry}\n" $dsp_port >> $log
        fi
    done
    echo >> $log
}

decode_last_rqp_drop() {
    rqp_disc=$(bcmcmd -n $asic "g hex ECGM_RQP_DISCARD_REASONS.ECGM${core}" | head -n -1 | tail -1)
    prefix=${rqp_disc: 0: 2}
    if [ "$prefix" != "0x" ]; then
            return; # empty (0) or a failed read 
    fi
    logmsg="EGRESS_DROP RQP_DISCARD_REASONS asic $asic core $core index $index: $rqp_disc"
    timestamp
    disc_reasons=${rqp_disc: -4: 3}
    print_rqp_reasons
}

decode_last_pqp_drop() {
    pqp_disc=$(bcmcmd -n $asic "g hex ECGM_PQP_DISCARD_REASONS.ECGM${core}" | head -n -1 | tail -1 )
    prefix=${pqp_disc: 0: 2}
    if [ "$prefix" != "0x" ]; then
            return; # empty (0) or a failed read 
    fi
    logmsg="EGRESS_DROP PQP_DISCARD_REASONS asic $asic core $core: $pqp_disc"
    timestamp
    check_new_port_state # in case the DSP map has changed
    disc_reasons=${pqp_disc: -5: 4}
    last_reason=${pqp_disc: -9: 4}
    drop_cmd=${pqp_disc: -19: 10}
    queue=${drop_cmd: -8: 3} 
    queue=$((16#${queue}))
    queue=$(($queue / 4 ))
    queue=$(($queue & 248)) 
    hr_num_hex=$(printf "%02x" $queue)
    entry=$(echo ${dsp_map_a[$index]} | sed -e "s/\r/\r\n/g" | grep -m 1 "$hr_num_hex")
    found=$?
    dsp_port=$(echo $entry |grep -o  "\[.*\]"| tr -dc '[:alnum:]')
    if [ $found -eq 1 ] ; then
        echo "drop_reason 0x${disc_reasons} queue 0x${hr_num_hex} dsp_port not_found" >> $log
    else
        dsp_port=$(echo $entry |grep -o  "\[.*\]"| tr -dc '[:alnum:]')
        echo "drop_reason 0x${disc_reasons} queue 0x${hr_num_hex} dsp port $dsp_port" >> $log
    fi
    echo "pqp discard reasons (cumulative since last read):" >> $log
    print_pqp_reasons 
    echo "pqp last packet discard reasons:" >> $log
    disc_reasons=$last_reason
    print_pqp_reasons
    echo >> $log
}


clear_tcam_hit_bits() {
    cint_filename="/tmp/hitbits"
    cint=';print bcm_field_entry_hit_flush(0, BCM_FIELD_ENTRY_HIT_FLUSH_ALL, 0); exit;' 
    bcmcmd -n $asic "log off; rm $cint_filename;log file=$cint_filename quiet=yes; echo '$cint';log off;cint $cint_filename" >> /dev/null
}

dump_tcam_drop_action_hits() {
    echo "SAI_FG_TRAP hits:" >> $log
    bcmcmd -n $asic "dbal table dump Table=SAI_FG_TRAP" | grep "CORE" | awk -F'|' '{print $2,$34}' >> $log
    echo "EPMF_Cascade hits:" >> $log
    # entries 51,52,53,54,55,56 have drop action
    bcmcmd -n $asic "dbal table dump Table=EPMF_Cascade" | grep "CORE" | awk -F'|' '{print $2,$10}'>> $log
    clear_tcam_hit_bits
}

check_egress_drops() {
    hit=0
    pqp_uc_discard=$(bcmcmd -n $asic "g hex PQP_PQP_DISCARD_UNICAST_PACKET_COUNTER.PQP${core}"| head -n -1 | tail -n +2 | tr -dc '[:alnum:]')
    erpp_discard=$(bcmcmd -n $asic "g hex PQP_ERPP_DISCARDED_PACKET_COUNTER.PQP${core}"| head -n -1 | tail -n +2 | tr -dc '[:alnum:]')
    rqp_debug_counters=$(bcmcmd -n $asic "g RQP_PRP_DEBUG_COUNTERS.RQP${core}" | head -n -1 | tail -n +2 | sed -e 's/=/ /g'| sed -e 's/,/ /g'|tr -dc "[:alnum:] =_" )

    pqp_uc_discard=$(printf "%d" $pqp_uc_discard)
    erpp_discard=$(printf "%d" $erpp_discard)

    if [ $pqp_uc_discard -ne 0 ]; then
        logmsg="EGRESS_DROP UC_DROP on ASIC $asic CORE $core : PQP_DISCARD_UNICAST_PACKET_COUNTER = $pqp_uc_discard" 
        timestamp
        hit=1;
    fi
    if [ $erpp_discard -ne 0 ]; then
        logmsg="EGRESS_DROP ERPP_DROP on ASIC $asic CORE $core : PQP_ERPP_DISCARDED_PACKET_COUNTER = $erpp_discard"
        timestamp
        hit=1;
    fi

    sop_discard_uc=$(echo $rqp_debug_counters | awk {'print $4'})
    prp_discard_uc=$(echo $rqp_debug_counters | awk {'print $14'})
    dbf_err_cnt=$(echo $rqp_debug_counters | awk {'print $18'})

    sop_discard_uc=$(printf "%d" $sop_discard_uc)
    prp_discard_uc=$(printf "%d" $prp_discard_uc)
    dbf_err_cnt=$(printf "%d" $dbf_err_cnt)

    if [ $sop_discard_uc -ne 0 ]; then
        logmsg="EGRESS_DROP RQP_SOP_UC_DISCARD on ASIC $asic CORE $core : $sop_discard_uc"
        timestamp
        hit=1;
    fi
    if [ $prp_discard_uc -ne 0 ]; then
        logmsg="EGRESS_DROP RQP_PRP_UC_DISCARD on ASIC $asic CORE $core : $prp_discard_uc"
        timestamp
        hit=1;
    fi
    if [ $dbf_err_cnt -ne 0 ]; then
        logmsg="EGRESS_DROP RQP_DBF_ERR on ASIC $asic CORE $core : $dbf_err_cnt"
        timestamp
        hit=1;
    fi      
    if [ $egr_check_mc -ne 0 ]; then
        sop_discard_mc=$(echo $rqp_debug_counters | awk {'print $6'})
        prp_discard_mc=$(echo $rqp_debug_counters | awk {'print $16'})
        sop_discard_mc=$(printf "%d" $sop_discard_mc)
        prp_discard_mc=$(printf "%d" $prp_discard_mc)

        pqp_mc_discard=$(bcmcmd -n $asic "g hex PQP_PQP_DISCARD_MULTICAST_PACKET_COUNTER.PQP${core}" | head -n -1 | tail -n +2 | tr -dc '[:alnum:]')
        pqp_mc_discard=$(printf "%d" $pqp_mc_discard)
        if [ $pqp_mc_discard -ne 0 ]; then
            logmsg="EGRESS_DROP MC_DROP ASIC $asic CORE $core : PQP_DISCARD_MULTICAST_PACKET_COUNTER = $pqp_mc_discard"
            timestamp
            hit=1;
        fi
        if [ $sop_discard_mc -ne 0 ]; then
            logmsg="EGRESS_DROP RQP_SOP_MC_DISCARD on ASIC $asic CORE $core : $sop_discard_mc"
            timestamp
            hit=1;
        fi
        if [ $prp_discard_mc -ne 0 ]; then
            logmsg="EGRESS_DROP RQP_PRP_MC_DISCARD on ASIC $asic CORE $core : $prp_discard_mc"
            timestamp
            hit=1;
        fi
    fi
    if [ $hit -eq 0 ] ; then
        return 
    fi

    decode_last_pqp_drop
    # bcmcmd -n $asic "g chg ECGM_RQP_DISCARD_REASONS.ECGM${core}"  | grep "=" >> $log
    decode_last_rqp_drop
    bcmcmd -n $asic "g chg PQP_INTERRUPT_REGISTER.PQP${core}"| head -n -1 | tail -n +2 >> $log
    bcmcmd -n $asic "g chg RQP_INTERRUPT_REGISTER.RQP${core}"| head -n -1 | tail -n +2 >> $log
    bcmcmd -n $asic "s PQP_INTERRUPT_REGISTER.PQP${core} -1" > /dev/null
    bcmcmd -n $asic "s RQP_INTERRUPT_REGISTER.RQP${core} -1" > /dev/null

    bcmcmd -n $asic "g chg RQP_PACKET_REASSEMBLY_INTERRUPT_REGISTER.RQP${core}"| tail -2 | head -n -1 >> $log
    bcmcmd -n $asic "s RQP_PACKET_REASSEMBLY_INTERRUPT_REGISTER.RQP${core} -1" > /dev/null

    bcmcmd -n $asic "g chg FDR_INTERRUPT_REGISTER.FDR${core}"| head -n -1 | tail -n +2 >> $log
    # FDA0 block is shared by both cores
    bcmcmd -n $asic "g chg FDA_INTERRUPT_REGISTER.FDA0"| head -n -1 | tail -n +2 >> $log
    bcmcmd -n $asic "s FDR_INTERRUPT_REGISTER.FDR${core} -1" > /dev/null
    bcmcmd -n $asic "s FDA_INTERRUPT_REGISTER.FDA0 -1" > /dev/null
    
    bcmcmd -n $asic "g chg ERPP_INTERRUPT_REGISTER.ERPP${core}"| head -n -1 | tail -n +2>> $log
    bcmcmd -n $asic "g chg ERPP_ERPP_DISCARD_INTERRUPT_REGISTER.ERPP${core}"| head -n -1 | tail -n +2 >> $log
    bcmcmd -n $asic "g chg ERPP_ERPP_DISCARD_INTERRUPT_REGISTER_2.ERPP${core}"| head -n -1 | tail -n +2 >> $log
    bcmcmd -n $asic "s ERPP_ERPP_DISCARD_INTERRUPT_REGISTER.ERPP${core} -1" > /dev/null
    bcmcmd -n $asic "s ERPP_ERPP_DISCARD_INTERRUPT_REGISTER_2.ERPP${core} -1" > /dev/null
    bcmcmd -n $asic "s ERPP_INTERRUPT_REGISTER.ERPP${core} -1" > /dev/null

    bcmcmd -n $asic "g chg ERPP_ERPP_DISCARDS_INTERRUPT_REGISTER_MASK.ERPP${core}"| head -n -1 | tail -n +2 >> $log
    bcmcmd -n $asic "g chg ERPP_ERPP_DISCARDS_INTERRUPT_REGISTER_MASK_2.ERPP${core}"| head -n -1 | tail -n +2 >> $log

    #bcmcmd -n $asic "g chg IPT_FLOW_CONTROL_DEBUG.IPT${core}" >> $log
    bcmcmd -n $asic "tm egr con"| head -n -1 | tail -n +2 >> $log

    if [ $egr_check_pmf_hit_bits -eq 1 ]; then
        dump_tcam_drop_action_hits
    fi
    if [ $egr_diag_counter_g -eq 1 ]; then
        bcmcmd -n $asic "diag counter g nz core=${core}"| head -n -1 | tail -n +2  >> $log
    fi
    echo "$delim" >> $log
    echo >> $log
}

dump_ingress_traps() {
    bcmcmd -n $asic "g IPPB_DBG_FLP_DATA_PATH_TRAP.IPPB${core}" | head -n -1 | tail -n +2 >> $log
    bcmcmd -n $asic "s IPPB_DBG_FLP_DATA_PATH_TRAP.IPPB${core} -1"| head -n -1 | tail -n +2 >> $log
    bcmcmd -n $asic "g IPPE_DBG_LLR_TRAP_0.IPPE${core}"| head -n -1 | tail -n +2 >> $log
    bcmcmd -n $asic "s IPPE_DBG_LLR_TRAP_0.IPPE${core} -1"| head -n -1 | tail -n +2 >> $log
}
dump_macsec() {
    bcmcmd -n $asic "sec stat show; sec stat clear" >> $log
}

rjct_filename=rjct_status.txt

check_ingress_drops() {
    hit=0
    bcmcmd -n $asic "getreg chg CGM_REJECT_STATUS_BITMAP.CGM${core}" | awk '{split($0,a,":"); print a[2]}' > $rjct_filename
    while read -r line; do
            [ -z $line ] && continue
            res=$(echo $line |  grep -v "," | grep "<>")
            if [ -z $res ]; then
                    hit=1
            fi
    done < "$rjct_filename"

    if [ $hit == 1 ]; then
        logmsg="INGRESS_DROP asic $asic core $core" 
        timestamp
        cat $rjct_filename >> $log
        bcmcmd -n $asic "g CGM_MAX_VOQ_WORDS_QSIZE_TRACK.CGM${core}" | head -n -1 | tail -n +2 >> $log
        #bcmcmd -n $asic "g chg IPT_FLOW_CONTROL_DEBUG.IPT${core}"| head -n -1 | tail -n +2 >> $log
        bcmcmd -n $asic "tm ing cong core=$core" >> $log
        bcmcmd -n $asic "trap last info core=$core" >> $log
        bcmcmd -n $asic "pp vis ppi core=$core" >> $log
        bcmcmd -n $asic "pp vis fdt core=$core" >> $log
        bcmcmd -n $asic "pp vis ikleap core=$core" >> $log
        #bcmcmd -n $asic "pp vis last" >> $log
        if [ $ing_check_mc -eq 1 ] ; then
            bcmcmd -n $asic "dbal table dump  table=mcdb" >> $log
            bcmcmd -n $asic "g MTM_ING_MCDB_OFFSET" | head -n -1 | tail -n +2 >> $log
            bcmcmd -n $asic "g MTM_EGR_MCDB_OFFSET" | head -n -1 | tail -n +2 >> $log
        fi
        bcmcmd -n $asic "diag counter g nz core=${core}" >> $log
        echo "" >> $log
        dump_ingress_traps
        echo "" >> $log
        if [ $ing_check_macsec -eq 1 ] ; then
            dump_macsec
        fi
        echo "$delim" >> $log
    fi
}

# clear stats
for asic in "${asics[@]}" 
do
    bcmcmd -n $asic "sec stat clear; clear counter; clear interrupt all" >> /dev/null
done

iter_a=(0 0 0 0) 
while true; 
do 
  for asic in "${asics[@]}" 
  do
    for core in "${cores[@]}"
    do
        index=$(($asic*2+$core))
        iter=$((${iter_a[$index]}+1))
        if [ $iter -eq $maxiter ] ; then
            iter_a[$index]=0;
            sleep $sleep_period
            continue 
        fi
        iter_a[$index]=$iter
        # for majority of polling cycles, check the PQP drop reason and queue
        if [ $iter -gt 4 ] ; then
            decode_last_pqp_drop
            continue
        fi
        # check for any change in pqp disabled port mask 
        if [ $iter -eq 1 ] ; then
            check_new_port_state
            continue
        fi
        if [ $iter -eq 2 ] ; then
            check_egress_drops
            continue
        fi
        if [ $iter -eq 3 ]; then
            check_ingress_drops
            continue
        fi
        if [ $iter -eq 4 ]; then
            decode_last_rqp_drop
        fi
    done
  done
done

