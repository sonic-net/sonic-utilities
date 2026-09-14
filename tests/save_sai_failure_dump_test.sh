#!/bin/bash
#
# Unit test for the save_sai_failure_dump() function in scripts/generate_dump.
#
# save_sai_failure_dump() collects SAI failure dumps from
# /var/log/sai_failure_dump/ into the techsupport tarball.  generate_dump runs
# main() at the bottom and cannot be sourced, so this test extracts just that
# function (via sed) and runs it with a couple of mocked collaborators.
#
# Scope is deliberately narrow -- we only assert on externally observable
# behaviour that is worth guarding against regression, NOT on internal wiring
# such as which do_gzip flag is handed to save_file:
#   - a *.tar dump is gzip-compressed before collection and leaves no leftover;
#   - if gzip FAILS, the *.tar is NOT collected and is left in place for manual
#     recovery (no data loss -- deleting the only intact copy is the bug the
#     compression change could reintroduce);
#   - an empty dump dir is a harmless no-op.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GENERATE_DUMP="${SCRIPT_DIR}/../scripts/generate_dump"

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

assert_dir_clean() {
    # assert_dir_clean <dir> <message>
    # The dump dir itself must survive cleanup (only the files inside are
    # removed) and be empty afterwards.  Checking existence first prevents a
    # false pass if cleanup ever regressed to removing the whole directory --
    # `ls` on a missing dir also yields an empty string.
    if [ ! -d "$1" ]; then
        fail "$2 (dump dir '$1' was removed)"
        return
    fi
    assert_eq "" "$(ls "$1")" "$2"
}

# basenames of the files handed to the save_file mock during the last run_case.
collected_basenames() {
    printf "%b" "${COLLECTED}" | sed '/^$/d' | xargs -n1 basename 2>/dev/null
}

# Extract save_sai_failure_dump() from generate_dump, rewriting its hard-coded
# production dump path to the test's scratch dir.  The production code keeps the
# path hard-coded (nothing outside the box may redirect where dumps are
# collected); test isolation lives here via this local sed rewrite.  mktemp -d
# paths contain no sed-special characters, and we use '|' as the delimiter.
extract_function() {
    local dumpdir="$1"
    sed -n '/^save_sai_failure_dump()/,/^}/p' "${GENERATE_DUMP}" \
        | sed "s|/var/log/sai_failure_dump/|${dumpdir}/|g"
}

# Define mocks + the function under test, then run it.
#   $1 dumpdir      : fake /var/log/sai_failure_dump
#   $2 gzip_behavior: "fail_gzip" to simulate gzip failing (leaves file intact)
#   $3 only_file    : if set, find_files yields ONLY this path (lets a test
#                     drive a single iteration in isolation, e.g. "process one
#                     pre-existing *.gz" without the loop also touching a
#                     sibling file)
#   $4 save_behavior: "fail_save" makes save_file return non-zero, to simulate a
#                     failed tech-support append (the file still gets recorded in
#                     COLLECTED so the test can see it was attempted)
#   $5 tar_behavior : "match_tar" makes the TAR mock list the file as already
#                     collected under log/, so the code takes the save_symlink
#                     branch instead of the save_file (copy) branch
run_case() {
    local dumpdir="$1"
    local gzip_behavior="${2:-}"
    local only_file="${3:-}"
    local save_behavior="${4:-}"
    local tar_behavior="${5:-}"

    COLLECTED=""   # files handed to save_file
    SYMLINKED=""   # files handed to save_symlink

    if [ "$gzip_behavior" == "fail_gzip" ]; then
        gzip() { return 1; }   # mimic gzip failing, leaving the source in place
    else
        unset -f gzip 2>/dev/null || true
    fi

    if [ -n "$only_file" ]; then
        find_files() { echo "$only_file"; }
    else
        find_files() { find -L "$1" -type f; }
    fi

    # The real code uses `$TAR -tf $TARFILE | grep ...` to pick symlink-vs-copy.
    # Default: the techsupport tar never contains the file, so that grep fails
    # (TAR mock lists nothing) and we take the save_file (copy) path.  With
    # "match_tar" the TAR mock echoes the expected `$BASE/log/<basename>` line
    # so the grep matches and the save_symlink branch is exercised instead.
    TARFILE="/nonexistent.tar"; BASE="dumpbase"; CMD_PREFIX=""
    if [ "$tar_behavior" == "match_tar" ]; then
        TAR="mock_tar"; mock_tar() { find -L "$dumpdir" -type f -printf "$BASE/log/%f\n"; }
    else
        TAR="mock_tar"; mock_tar() { return 0; }
    fi

    # "fail_save" makes whichever collector runs (save_file on the copy path,
    # save_symlink on the link path) return non-zero, to simulate a failed
    # tech-support append.  The file is still recorded so the test can see it
    # was attempted, and the outer cleanup must then keep it on disk.
    local save_rc=0
    [ "$save_behavior" == "fail_save" ] && save_rc=1
    save_file() { COLLECTED="${COLLECTED}${1}\n"; return "$save_rc"; }
    # Record what save_symlink was asked to reference.  The real save_symlink
    # (with the default do_tar_append=true) removes the on-disk file itself
    # after appending it to the tarball; the mock skips that so the test can
    # separately assert the outer cleanup behaviour.
    save_symlink() { SYMLINKED="${SYMLINKED}${1}\n"; return "$save_rc"; }

    eval "$(extract_function "${dumpdir}")"
    save_sai_failure_dump
}

# basenames of the files handed to the save_symlink mock during the last run_case.
symlinked_basenames() {
    printf "%b" "${SYMLINKED}" | sed '/^$/d' | xargs -n1 basename 2>/dev/null
}

# ===========================================================================
# Case 1: a *.tar dump is gzipped, collected once, and leaves the dir clean.
# ===========================================================================
echo "Case 1: .tar dump is gzipped and no leftover tar/tar.gz remains"
TMP1="$(mktemp -d)"
mkdir -p "${TMP1}/dump"
echo "sai-dump-payload" > "${TMP1}/payload.txt"
tar -cf "${TMP1}/dump/sai_sdk_dump_x.tar" -C "${TMP1}" payload.txt

run_case "${TMP1}/dump"

assert_eq "sai_sdk_dump_x.tar.gz" "$(collected_basenames)" "collected file is the gzipped dump"
assert_dir_clean "${TMP1}/dump" "source dir is clean after collection (no leftover tar/tar.gz)"

rm -rf "${TMP1}"

# ===========================================================================
# Case 2: gzip fails on a *.tar dump (e.g. a full filesystem).  A gzip failure
#         usually means the subsequent save_file/tar-append would fail too, so
#         the function must NOT delete the only intact copy -- it skips the file
#         entirely, leaving the original tar under /var/log/sai_failure_dump/
#         for manual recovery and collecting nothing for it.
# ===========================================================================
echo "Case 2: gzip failure leaves the original .tar in place (no data loss)"
TMP2="$(mktemp -d)"
mkdir -p "${TMP2}/dump"
echo "sai-dump-payload" > "${TMP2}/payload.txt"
tar -cf "${TMP2}/dump/sai_sdk_dump_f.tar" -C "${TMP2}" payload.txt

run_case "${TMP2}/dump" fail_gzip

# Nothing is collected for this file -- the iteration is skipped on gzip failure.
assert_eq "" "$(collected_basenames)" "nothing is collected when gzip fails"
# The original tar must survive on disk so it can be recovered manually.
if [ -f "${TMP2}/dump/sai_sdk_dump_f.tar" ]; then
    pass "original .tar is preserved on disk after gzip failure"
else
    fail "original .tar was wrongly removed after gzip failure"
fi

rm -rf "${TMP2}"

# ===========================================================================
# Case 3: a pre-existing *.gz dump must NOT drag a similarly named sibling with
#         it during cleanup.  Processing X.tar.gz that this run did NOT create
#         should collect and remove only X.tar.gz, never a separate X.tar.
# ===========================================================================
echo "Case 3: pre-existing .gz cleanup does not remove a sibling .tar"
TMP3="$(mktemp -d)"
mkdir -p "${TMP3}/dump"
echo "already-compressed" | gzip -c > "${TMP3}/dump/sai_sdk_dump_g.tar.gz"
# A separate, independent file that shares the de-gz'd name; it must survive.
echo "unrelated-tar-content" > "${TMP3}/dump/sai_sdk_dump_g.tar"

# Drive just the .gz iteration in isolation.
run_case "${TMP3}/dump" "" "${TMP3}/dump/sai_sdk_dump_g.tar.gz"

assert_eq "sai_sdk_dump_g.tar.gz" "$(collected_basenames)" "the pre-existing .gz is the collected file"
# The sibling .tar this run never touched must still be there, intact.
if [ -f "${TMP3}/dump/sai_sdk_dump_g.tar" ]; then
    pass "sibling .tar is preserved (not deleted by \${file%.gz})"
else
    fail "sibling .tar was wrongly removed during .gz cleanup"
fi

rm -rf "${TMP3}"

# ===========================================================================
# Case 4: compressing a *.tar must NOT clobber a pre-existing, independent
#         *.tar.gz of the same base name.  gzip would overwrite the sibling
#         archive (replacing its content with this tar's) -- the code must skip
#         the in-place gzip when "$file.gz" already exists and collect the .tar
#         as-is instead.
# ===========================================================================
echo "Case 4: compressing a .tar does not clobber a pre-existing .tar.gz"
TMP4="$(mktemp -d)"
mkdir -p "${TMP4}/dump"
# Independent .tar.gz whose content must survive untouched.
echo "precious-existing-gz-content" | gzip -c > "${TMP4}/dump/sai_sdk_dump_c.tar.gz"
# A same-base-name .tar with DIFFERENT content, processed this run.
echo "raw-tar-content" > "${TMP4}/dump/sai_sdk_dump_c.tar"

# Drive just the .tar iteration in isolation.
run_case "${TMP4}/dump" "" "${TMP4}/dump/sai_sdk_dump_c.tar"

# The .tar is collected as-is (in-place gzip skipped because .tar.gz exists).
assert_eq "sai_sdk_dump_c.tar" "$(collected_basenames)" "the .tar is collected as-is when a sibling .tar.gz exists"
# The pre-existing .tar.gz content must be intact (not overwritten by the tar).
if [ -f "${TMP4}/dump/sai_sdk_dump_c.tar.gz" ] && \
   [ "$(gzip -cd "${TMP4}/dump/sai_sdk_dump_c.tar.gz")" == "precious-existing-gz-content" ]; then
    pass "pre-existing .tar.gz content preserved (not clobbered by gzip)"
else
    fail "pre-existing .tar.gz was clobbered when compressing the sibling .tar"
fi

rm -rf "${TMP4}"

# ===========================================================================
# Case 5: collection failure must NOT delete the compressed dump.  After a
#         successful gzip the original .tar is already gone (gzip removed it),
#         so the .tar.gz is the only copy; if appending it to tech support
#         fails, cleanup must keep it on disk for recovery / retry.
# ===========================================================================
echo "Case 5: failed collection keeps the .tar.gz on disk (no data loss)"
TMP5="$(mktemp -d)"
mkdir -p "${TMP5}/dump"
echo "sai-dump-payload" > "${TMP5}/payload.txt"
tar -cf "${TMP5}/dump/sai_sdk_dump_s.tar" -C "${TMP5}" payload.txt

# Real gzip runs (produces sai_sdk_dump_s.tar.gz, removes the .tar); save_file
# then fails.
run_case "${TMP5}/dump" "" "" fail_save

# The gzipped artifact was attempted...
assert_eq "sai_sdk_dump_s.tar.gz" "$(collected_basenames)" "the gzipped dump is the file handed to save_file"
# ...and, because collection failed, must still be on disk (not rm'd away).
if [ -f "${TMP5}/dump/sai_sdk_dump_s.tar.gz" ]; then
    pass ".tar.gz preserved on disk after failed collection"
else
    fail ".tar.gz was wrongly deleted after a failed collection"
fi

rm -rf "${TMP5}"

# ===========================================================================
# Case 6: a freshly-compressed *.tar -> *.tar.gz that is already present under
#         the techsupport log/ dir takes the save_symlink branch (not the copy
#         branch).  The compressed artifact handed to save_symlink is the
#         *.tar.gz, and cleanup must leave the dump dir empty afterwards -- the
#         original *.tar (removed by gzip) and the *.tar.gz (removed by cleanup)
#         must both be gone, with no leftover.
# ===========================================================================
echo "Case 6: freshly-compressed .tar.gz already under log/ takes the symlink branch"
TMP6="$(mktemp -d)"
mkdir -p "${TMP6}/dump"
echo "sai-dump-payload" > "${TMP6}/payload.txt"
tar -cf "${TMP6}/dump/sai_sdk_dump_l.tar" -C "${TMP6}" payload.txt

# match_tar makes the TAR mock report the (post-gzip) file as already collected
# under log/, so the code links instead of copying.
run_case "${TMP6}/dump" "" "" "" match_tar

# The .tar is gzipped first, then the resulting .tar.gz is the file linked.
assert_eq "sai_sdk_dump_l.tar.gz" "$(symlinked_basenames)" "the gzipped dump is the file handed to save_symlink"
# Nothing should go through the save_file (copy) path in this case.
assert_eq "" "$(collected_basenames)" "nothing is collected via the copy path"
# Cleanup removes the compressed artifact; gzip already removed the original
# .tar -- the dump dir must be clean with no leftover.
assert_dir_clean "${TMP6}/dump" "source dir is clean after the symlink branch (no leftover tar/tar.gz)"

rm -rf "${TMP6}"

# ===========================================================================
# Case 7: a failed save_symlink must NOT delete the freshly-compressed dump.
#         Mirrors Case 5 for the link path: after a successful gzip the
#         original *.tar is gone, so the *.tar.gz is the only copy; if linking
#         it into tech support fails, cleanup must keep it on disk for recovery
#         / retry rather than removing the only intact artifact.
# ===========================================================================
echo "Case 7: failed save_symlink keeps the .tar.gz on disk (no data loss)"
TMP7="$(mktemp -d)"
mkdir -p "${TMP7}/dump"
echo "sai-dump-payload" > "${TMP7}/payload.txt"
tar -cf "${TMP7}/dump/sai_sdk_dump_k.tar" -C "${TMP7}" payload.txt

# match_tar drives the symlink branch; fail_save makes save_symlink return
# non-zero (real gzip still runs and removes the original .tar).
run_case "${TMP7}/dump" "" "" fail_save match_tar

# The gzipped artifact was the file handed to save_symlink...
assert_eq "sai_sdk_dump_k.tar.gz" "$(symlinked_basenames)" "the gzipped dump is the file handed to save_symlink"
# ...and, because linking failed, must still be on disk (not rm'd away).
if [ -f "${TMP7}/dump/sai_sdk_dump_k.tar.gz" ]; then
    pass ".tar.gz preserved on disk after failed save_symlink"
else
    fail ".tar.gz was wrongly deleted after a failed save_symlink"
fi

rm -rf "${TMP7}"

# ===========================================================================
# Case 8: empty dump dir is a harmless no-op.
# ===========================================================================
echo "Case 8: empty dump dir is a no-op"
TMP8="$(mktemp -d)"
mkdir -p "${TMP8}/dump"
run_case "${TMP8}/dump"
assert_eq "" "$(collected_basenames)" "nothing collected from empty dir"
assert_dir_clean "${TMP8}/dump" "empty source dir remains present and clean"
rm -rf "${TMP8}"

# ---------------------------------------------------------------------------
echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[ "${FAIL}" -eq 0 ]
