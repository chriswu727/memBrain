#!/usr/bin/env bash
# Run one C5 scenario's three arms (P, E, F) in parallel, each in a new directory, and wait for them.
#
#   evaluations/c5-run-scenario.sh SCENARIO.py OUT_ROOT KEY
#
# As v1-2026-11-05-run-scenario.sh, with the C5 harness (scenario clock, page actions, memory_boundary, persona in F).
# Arm X runs in OUT_ROOT/KEY-X and logs to OUT_ROOT/KEY-X/run.log; an existing run directory is refused.
# Needs MEMBRAIN_MODEL_CACHE, and DEEPSEEK_API_KEY unless C5_STUB=1 (the zero-network dry run, practice scenarios
# only). MEMBRAIN_SRC must be unset. C5_PYTHON overrides the interpreter (default: uv run python). The launchers never
# set MEMBRAIN_EVALUATION_CLOCK; only the harness does, for the disposable profiles it creates.
set -euo pipefail
scenario=$1 root=$2 key=$3
: "${MEMBRAIN_MODEL_CACHE:?set MEMBRAIN_MODEL_CACHE}"
if [ "${C5_STUB:-}" = 1 ]; then
  case "$(basename "$scenario")" in *practice*) ;; *) echo "the dry run takes only a practice scenario" >&2; exit 2;; esac
else
  : "${DEEPSEEK_API_KEY:?set DEEPSEEK_API_KEY}"
  : "${C5_BILLING_LEDGER:?set the approved shared C5_BILLING_LEDGER}"
  : "${C5_ATTEMPT_ID:?set the frozen attempt ID}"
  : "${C5_BILLING_POLICY_SHA256:?set the frozen billing policy hash}"
fi
if [ -n "${MEMBRAIN_SRC:-}" ]; then echo "MEMBRAIN_SRC must be unset" >&2; exit 2; fi
if [ -n "${MEMBRAIN_EVALUATION_CLOCK:-}" ]; then echo "MEMBRAIN_EVALUATION_CLOCK must be unset" >&2; exit 2; fi
if [ -n "${C5_PYTHON:-}" ]; then python=("$C5_PYTHON"); else python=(uv run python); fi
cd "$(dirname "$0")/.."
if [ "${C5_STUB:-}" != 1 ]; then "${python[@]}" evaluations/c5-harness.py --preflight; fi
for arm in P E F; do
  if [ -e "$root/$key-$arm" ]; then echo "$root/$key-$arm exists: a run directory is never reused" >&2; exit 2; fi
done
pids=() labels=() started=0
cleanup() {
  local status=$?
  trap - EXIT
  if [ "$status" -ne 0 ] && [ "$started" -gt 0 ] && [ "${C5_STUB:-}" != 1 ]; then
    "${python[@]}" evaluations/c5-harness.py --stop || true
  fi
  if [ "${#pids[@]}" -gt 0 ]; then
    for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
    for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null || true; done
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
check_arms() {
  local index pid status failed=0
  if [ "${#pids[@]}" -eq 0 ]; then return 0; fi
  for index in "${!pids[@]}"; do
    pid=${pids[$index]}
    if ! kill -0 "$pid" 2>/dev/null; then
      status=0
      wait "$pid" || status=$?
      if [ "$status" -ne 0 ]; then
        if [ "$failed" -eq 0 ]; then echo "arm ${labels[$pid]} failed with exit $status" >&2; fi
        failed=1
      fi
      unset 'pids[index]'
      unset 'labels[pid]'
    fi
  done
  return "$failed"
}
bindable() {
  python3 - "$@" <<'PY'
import socket, sys
for port in map(int, sys.argv[1:]):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            sys.exit(1)
PY
}
wait_bindable() {
  local waited=0
  until bindable "$@"; do
    if [ "$waited" -ge 300 ]; then echo "ports $* still not free after 300 s" >&2; return 1; fi
    sleep 5; check_arms || return 1; waited=$((waited + 5))
  done
  echo "ports $* free after ${waited} s"
}
wait_bindable 8893 55533 8894 55534 || exit 2  # Before any arm starts: a timeout here costs nothing.
for spec in "P 8893,55533" "E 8894,55534" "F -"; do
  set -- $spec
  dir="$root/$key-$1"
  if [ "$2" != "-" ] && ! wait_bindable ${2//,/ }; then
    exit 2
  fi
  mkdir -p "$dir"
  if [ "$2" = "-" ]; then
    env -u MEMBRAIN_PORTS "${python[@]}" -u evaluations/c5-harness.py "$1" "$scenario" "$dir" >> "$dir/run.log" 2>&1 &
  else
    MEMBRAIN_PORTS=$2 "${python[@]}" -u evaluations/c5-harness.py "$1" "$scenario" "$dir" >> "$dir/run.log" 2>&1 &
  fi
  pid=$!
  pids+=("$pid")
  labels[$pid]=$1
  started=$((started + 1))
  for delay in {1..15}; do sleep 1; check_arms || exit 1; done
done
while [ "${#pids[@]}" -gt 0 ]; do
  check_arms || exit 1
  if [ "${#pids[@]}" -gt 0 ]; then sleep 1; fi
done
