#!/bin/bash
set -euo pipefail

if [ ! -s coverage.xml ]; then
    echo "##vso[task.logissue type=error]coverage.xml is missing or empty."
    exit 1
fi

target_branch="${SYSTEM_PULLREQUEST_TARGETBRANCH:?Missing pull request target branch}"
target_branch="${target_branch#refs/heads/}"
git fetch --no-tags --no-recurse-submodules origin \
    "+refs/heads/$target_branch:refs/remotes/origin/$target_branch"

venv="${AGENT_TEMPDIRECTORY:?Missing agent temporary directory}/diff-cover"
python3 -m venv "$venv"
"$venv/bin/python" -m pip install diff-cover

report_dir="${BUILD_ARTIFACTSTAGINGDIRECTORY:?Missing artifact staging directory}/diff-coverage"
mkdir -p "$report_dir"
diff_args=(coverage.xml --ignore-unstaged "--compare-branch=origin/$target_branch")
"$venv/bin/diff-cover" "${diff_args[@]}" \
    --json-report="$report_dir/diff-cover.json" \
    --html-report="$report_dir/index.html"
echo "##vso[task.setvariable variable=DIFF_COVER_REPORTS_READY]true"

"$venv/bin/diff-cover" "${diff_args[@]}" \
    --fail-under="${DIFF_COVER_CHECK_THRESHOLD:?Missing diff coverage threshold}"
