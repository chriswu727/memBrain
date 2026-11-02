#!/usr/bin/env bash
# Run one acceptance scenario's three arms (P, E, F) in parallel, each in a new directory, and wait for them.
#
#   evaluations/v1-2026-11-05-run-scenario.sh SCENARIO.py OUT_ROOT KEY
#
# Arm X runs in OUT_ROOT/KEY-X and logs stdout and stderr to OUT_ROOT/KEY-X/run.log. A run directory that already
# exists is refused: the harness skips turns already in a results file, so starting it twice on one directory would
# resume a run, which the acceptance plan does not allow. Needs DEEPSEEK_API_KEY and MEMBRAIN_MODEL_CACHE;
# MEMBRAIN_SRC must be unset so the arms use this checkout.
set -euo pipefail
scenario=$1 root=$2 key=$3
: "${DEEPSEEK_API_KEY:?set DEEPSEEK_API_KEY}" "${MEMBRAIN_MODEL_CACHE:?set MEMBRAIN_MODEL_CACHE}"
if [ -n "${MEMBRAIN_SRC:-}" ]; then echo "MEMBRAIN_SRC must be unset" >&2; exit 2; fi
cd "$(dirname "$0")/.."
for arm in P E F; do
  if [ -e "$root/$key-$arm" ]; then echo "$root/$key-$arm exists: a run directory is never reused" >&2; exit 2; fi
done
pids=()
for spec in "P 8893,55533" "E 8894,55534" "F -"; do
  set -- $spec
  dir="$root/$key-$1"
  mkdir -p "$dir"
  if [ "$2" = "-" ]; then
    env -u MEMBRAIN_PORTS uv run python -u evaluations/v1-2026-10-29-phase-b-harness.py "$1" "$scenario" "$dir" \
      >> "$dir/run.log" 2>&1 &
  else
    MEMBRAIN_PORTS=$2 uv run python -u evaluations/v1-2026-10-29-phase-b-harness.py "$1" "$scenario" "$dir" \
      >> "$dir/run.log" 2>&1 &
  fi
  pids+=($!)
  sleep 15
done
status=0
for pid in "${pids[@]}"; do wait "$pid" || status=1; done
exit $status
