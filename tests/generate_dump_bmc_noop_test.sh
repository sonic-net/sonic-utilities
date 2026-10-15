#!/bin/bash
#
# Unit test for the BMC debug log dump steps of scripts/generate_dump in noop
# (-n) and real mode.
#
# generate_dump runs main() at the bottom and cannot be sourced, so, like
# save_sai_failure_dump_test.sh, this extracts the BMC functions and the
# trigger call site of main() and runs them with python3 and is_bmc_supported
# mocked.  Asserted behaviour:
#   - noop mode never runs bmc_techsupport.py and prints both commands;
#   - real mode still triggers, then collects with the returned task id;
#   - noop mode on a platform without a BMC stays a no-op.

# shellcheck disable=SC2034,SC2154  # globals are read and set by the eval'd generate_dump code
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GENERATE_DUMP="${SCRIPT_DIR}/../scripts/generate_dump"
BMC_TECHSUPPORT="/usr/local/bin/bmc_techsupport.py"

PASS=0
FAIL=0

pass() { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
fail() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

assert_eq() {
    # assert_eq <expected> <actual> <message>
    if [ "$1" == "$2" ]; then
        pass "$3"
    else
        fail "$3 (expected='$1' actual='$2')"
    fi
}

assert_has_line() {
    # assert_has_line <line> <text> <message>
    if printf '%s\n' "$2" | grep -qxF -- "$1"; then
        pass "$3"
    else
        fail "$3 (missing line '$1' in: $2)"
    fi
}

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
CALLS="${TMP}/python3.calls"
TARBALL="${TMP}/bmc_debug_log_dump.tar.xz"

# The production tarball path is rewritten so the test never touches /tmp.
extract_function() {
    sed -n "/^$1()/,/^}/p" "${GENERATE_DUMP}" \
        | sed "s|/tmp/bmc_debug_log_dump.tar.xz|${TARBALL}|g"
}

# The trigger call site in main(), up to its closing fi.
extract_call_site() {
    sed -n '/# Trigger BMC debug log dump task - Must be the first task to run/,/^    fi$/p' "${GENERATE_DUMP}"
}

eval "$(grep '^BMC_NOOP_TASK_ID=' "${GENERATE_DUMP}")"
eval "$(extract_function trigger_bmc_debug_log_dump)"
eval "$(extract_function collect_bmc_files)"
CALL_SITE="$(extract_call_site)"
if [[ "${CALL_SITE}" != *"=\$(trigger_bmc_debug_log_dump)"* ]] || ! declare -F trigger_bmc_debug_log_dump collect_bmc_files > /dev/null; then
    echo "Could not extract the BMC steps from ${GENERATE_DUMP}"
    exit 1
fi

handle_error() { :; }

# Records each call; "-m trigger" returns a task id, "-m collect" writes the -p file.
python3() {
    echo "$*" >> "${CALLS}"
    local prev=""
    for arg in "$@"; do
        [ "${prev}" == "-p" ] && echo "bmc-dump" > "${arg}"
        prev="${arg}"
    done
    case "$*" in
        *"-m trigger"*) echo "task-42" ;;
    esac
}

# setup <noop: true|false> <platform: bmc|no-bmc>
setup() {
    NOOP=$1
    if [ "$2" == "bmc" ]; then
        is_bmc_supported() { return 0; }
    else
        is_bmc_supported() { return 1; }
    fi
    if $NOOP; then
        MKDIR="echo mkdir"; CP="echo cp"
    else
        MKDIR="mkdir"; CP="cp"
    fi
    V=""
    TARDIR="${TMP}/tardir"
    TECHSUPPORT_TIME_INFO="${TMP}/time_info"
    rm -rf "${TARDIR}" "${TARBALL}"
    : > "${CALLS}"
    : > "${TECHSUPPORT_TIME_INFO}"
}

# The trigger call site, then collection behind the same "-1" guard main() uses.
run_bmc_steps() {
    eval "${CALL_SITE}"
    if [ "$bmc_debug_log_dump_task_id" != "-1" ]; then
        collect_bmc_files "$bmc_debug_log_dump_task_id"
    fi
}

# ===========================================================================
echo "Case 1: noop mode on a BMC platform prints both commands and runs neither"
setup true bmc
OUT="$(run_bmc_steps)"
assert_eq "" "$(cat "${CALLS}")" "bmc_techsupport.py is never run"
assert_has_line "python3 ${BMC_TECHSUPPORT} -m trigger" "${OUT}" "trigger command is printed"
assert_has_line "python3 ${BMC_TECHSUPPORT} -m collect -p ${TARBALL} -t ${BMC_NOOP_TASK_ID:-}" "${OUT}" \
    "collect command is printed with the placeholder task id"

# ===========================================================================
echo "Case 2: real mode on a BMC platform triggers, then collects with the task id"
setup false bmc
OUT="$(run_bmc_steps)"
assert_eq "${BMC_TECHSUPPORT} -m trigger
${BMC_TECHSUPPORT} -m collect -p ${TARBALL} -t task-42" "$(cat "${CALLS}")" \
    "trigger and collect run in order, collect with the returned task id"
if [ -f "${TARDIR}/bmc/bmc_debug_log_dump.tar.xz" ]; then
    pass "collected dump is copied into the techsupport bmc dir"
else
    fail "collected dump is missing from the techsupport bmc dir"
fi
if grep -q '^\[ collect_bmc_files \]' "${TECHSUPPORT_TIME_INFO}"; then
    pass "collect_bmc_files timing entry is written"
else
    fail "collect_bmc_files timing entry is missing"
fi

# ===========================================================================
echo "Case 3: noop mode on a platform without a BMC stays a no-op"
setup true no-bmc
OUT="$(run_bmc_steps)"
assert_eq "" "$(cat "${CALLS}")" "bmc_techsupport.py is never run"
assert_has_line "INFO: BMC is not found on this platform. Skipping..." "${OUT}" \
    "missing BMC is reported"

# ---------------------------------------------------------------------------
echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[ "${FAIL}" -eq 0 ]
