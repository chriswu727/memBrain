#!/bin/sh
# One headless Claude Code turn: turn.sh <name> <brain> <sonnet|haiku> <new|resume> <session uuid> <message>
T=$TRIAL
name=$1; brain=$2; model=$3; mode=$4; session=$5; shift 5
case "$model" in sonnet|haiku) ;; *) echo "refused: model must be sonnet or haiku"; exit 2;; esac
[ -d "$T/$brain" ] || { echo "no brain $brain"; exit 2; }
[ -e "$T/logs/$name.jsonl" ] && { echo "log $name exists"; exit 2; }
if [ "$mode" = new ]; then flag="--session-id $session"; else flag="--resume $session"; fi
printf '%s' "$*" > "$T/logs/$name.prompt.txt"
cd "$T/${TRIAL_WORKDIR:-work}" || exit 1
env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_SSE_PORT TRIAL_TURN="$name" MEMBRAIN_DIRECTORY="$T/$brain" \
  claude -p "$*" --model "$model" --plugin-dir "$T/plugin" --output-format stream-json --verbose \
  --allowedTools "mcp__plugin_membrain_membrain" $flag > "$T/logs/$name.jsonl" 2> "$T/logs/$name.err"
rc=$?
python3 "$T/show.py" "$T/logs/$name.jsonl" | head -c 6000
echo "exit $rc"
