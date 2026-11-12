#!/bin/sh
# One headless Claude Code turn in the trial: turn.sh <name> <new|resume> <session uuid> <message>
T=TRIAL_DIR
name=$1; mode=$2; session=$3; shift 3
if [ "$mode" = new ]; then flag="--session-id $session"; else flag="--resume $session"; fi
cd "$T/work" || exit 1
env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_SSE_PORT MEMBRAIN_DIRECTORY="$T/brain2" \
  claude -p "$*" --model ${TRIAL_MODEL:-sonnet} --plugin-dir "$T/plugin" --output-format stream-json --verbose \
  --allowedTools "mcp__plugin_membrain_membrain" $flag > "$T/logs/$name.jsonl" 2> "$T/logs/$name.err"
echo "exit $?"
