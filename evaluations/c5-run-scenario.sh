#!/usr/bin/env bash
# Run one scenario's two arms, P (plugin path) then F (whole history), ONE AFTER THE OTHER, each in a new directory.
#
#   evaluations/c5-run-scenario.sh SCENARIO.py OUT_ROOT KEY
#
# Arm X runs in OUT_ROOT/KEY-X and logs to OUT_ROOT/KEY-X/run.log; an existing run directory is refused. F starts
# only after P has exited, P's installations have been stopped (`c5-harness.py --cleanup`) and P's ports are free
# again, so at most one host request is ever open against the billing ledger. Each arm's directory gets
# supervisor.log ("started", "finished", "cleaned" with epoch seconds), which validity reads to show that the arms
# never overlapped. The proxy-with-extraction arm E of attempts 1 to 5 no longer exists and is never started.
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
for arm in P F; do
  if [ -e "$root/$key-$arm" ]; then echo "$root/$key-$arm exists: a run directory is never reused" >&2; exit 2; fi
done
pids=() labels=() started=0 dirs=() cleaned=()
stamp() {
  printf '%s %s\n' "$2" "$(python3 -c 'import time; print(f"{time.time():.3f}")')" >> "$1/supervisor.log"
}
cleanup_arm() {  # Stop the arm's own installations and check their ports, once per arm.
  local dir=$1 done_dir
  for done_dir in "${cleaned[@]+"${cleaned[@]}"}"; do
    if [ "$done_dir" = "$dir" ]; then return 0; fi
  done
  cleaned+=("$dir")
  if "${python[@]}" evaluations/c5-harness.py --cleanup "$dir" >> "$dir/cleanup.log" 2>&1; then
    stamp "$dir" cleaned
    return 0
  fi
  echo "cleanup of $(basename "$dir") failed: see its cleanup.log" >&2
  return 1
}
cleanup() {
  local status=$? dir
  trap - EXIT
  if [ "$status" -ne 0 ] && [ "$started" -gt 0 ] && [ "${C5_STUB:-}" != 1 ]; then
    "${python[@]}" evaluations/c5-harness.py --stop || true
  fi
  if [ "${#pids[@]}" -gt 0 ]; then
    for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
    for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null || true; done
  fi
  for dir in "${dirs[@]+"${dirs[@]}"}"; do
    if ! cleanup_arm "$dir" && [ "$status" -eq 0 ]; then status=1; fi
  done
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
wait_bindable 8893 55533 || exit 2  # Before any arm starts: a timeout here costs nothing.
for spec in "P 8893,55533" "F -"; do
  set -- $spec
  dir="$root/$key-$1"
  # P's ports must be free before every arm: after P they are closed by its cleanup, checked here again.
  if ! wait_bindable 8893 55533; then exit 2; fi
  mkdir -p "$dir"
  dirs+=("$dir")
  stamp "$dir" started
  if [ "$2" = "-" ]; then
    env -u MEMBRAIN_PORTS "${python[@]}" -u evaluations/c5-harness.py "$1" "$scenario" "$dir" >> "$dir/run.log" 2>&1 &
  else
    MEMBRAIN_PORTS=$2 "${python[@]}" -u evaluations/c5-harness.py "$1" "$scenario" "$dir" >> "$dir/run.log" 2>&1 &
  fi
  pid=$!
  pids+=("$pid")
  labels[$pid]=$1
  started=$((started + 1))
  while [ "${#pids[@]}" -gt 0 ]; do
    check_arms || exit 1
    if [ "${#pids[@]}" -gt 0 ]; then sleep 1; fi
  done
  stamp "$dir" finished
  cleanup_arm "$dir" || exit 1
done
