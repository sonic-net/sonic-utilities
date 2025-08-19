#!/bin/bash

# Simple verification script for PFC storm detection in fast-reboot
# Tests the exact logic used in check_pfc_storm_active() function

echo "===== PFC Storm Detection Test ====="
echo ""

# Copy exact function from fast-reboot (with test modifications)
function debug() { echo "[DEBUG] $*"; }
function error() { echo "[ERROR] $*"; }
EXIT_PFC_STORM_DETECTED=25

function check_pfc_storm_active()
{
    debug "Checking for active PFC storms..."
    
    # Get all queue OIDs from COUNTERS_DB (exact same as fast-reboot)
    local queue_oids=$(sonic-db-cli COUNTERS_DB HVALS COUNTERS_QUEUE_NAME_MAP)
    local storm_detected=false
    local stormed_queues=""
    
    # Check PFC_WD_STATUS for each queue (exact same as fast-reboot)
    for queue_oid in $queue_oids; do
        if [ -n "$queue_oid" ]; then
            local pfc_status=$(sonic-db-cli COUNTERS_DB HGET "COUNTERS:${queue_oid}" PFC_WD_STATUS)
            if [[ "${pfc_status}" == "stormed" ]]; then
                storm_detected=true
                local queue_name=$(sonic-db-cli COUNTERS_DB HGETALL COUNTERS_QUEUE_NAME_MAP | grep -B1 "${queue_oid}" | head -n1)
                stormed_queues="${stormed_queues} ${queue_name}"
            fi
        fi
    done
    
    if [ "$storm_detected" = true ]; then
        error "PFC storm detected on queues:${stormed_queues}. Aborting warm-reboot to prevent failure in recovery path..."
        return ${EXIT_PFC_STORM_DETECTED}  # Return instead of exit for testing
    else
        debug "No active PFC storms detected. Safe to proceed with warm-reboot..."
        return 0
    fi
}

echo "Step 1: Test without storm"
check_pfc_storm_active
echo "Result: $?"
echo ""

echo "Step 2: Inject storm on Ethernet80:3 (monitored queue)"
QUEUE_OID=$(sonic-db-cli COUNTERS_DB HGET COUNTERS_QUEUE_NAME_MAP "Ethernet80:3")
echo "Queue OID: $QUEUE_OID"
sonic-db-cli COUNTERS_DB HSET "COUNTERS:${QUEUE_OID}" DEBUG_STORM enabled
sonic-db-cli COUNTERS_DB HSET "COUNTERS:${QUEUE_OID}" PFC_WD_STATUS stormed
echo ""

echo "Step 3: Verify pfcwd detects it"
pfcwd show stats | grep -q stormed && echo "✓ pfcwd detects storm" || echo "✗ pfcwd does NOT detect storm"
echo ""

echo "Step 4: Test function with storm"
check_pfc_storm_active
echo "Result: $? (should be 25)"
echo ""

echo "Step 5: Clean up"
sonic-db-cli COUNTERS_DB HDEL "COUNTERS:${QUEUE_OID}" DEBUG_STORM
sonic-db-cli COUNTERS_DB HDEL "COUNTERS:${QUEUE_OID}" PFC_WD_STATUS
echo ""

echo "Step 6: Test after cleanup"  
check_pfc_storm_active
echo "Result: $? (should be 0)"
echo ""

echo "===== CONCLUSION ====="
echo "If Step 4 result is NOT 25, the fast-reboot function has a bug and won't detect storms."
echo "If pfcwd does NOT detect storm in Step 3, the queue isn't properly monitored."