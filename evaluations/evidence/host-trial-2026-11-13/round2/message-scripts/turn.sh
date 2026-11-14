#!/bin/sh
# One headless Claude Code turn: turn.sh <name> <brain> <sonnet|haiku> <new|resume> <session uuid> <message>
R=$ROUND2
name=$1; brain=$2; model=$3; mode=$4; session=$5; shift 5
case "$model" in sonnet|haiku) ;; *) echo "refused: model must be sonnet or haiku"; exit 2;; esac
[ -d "$R/$brain" ] || { echo "no brain $brain"; exit 2; }
[ -e "$R/logs/$name.jsonl" ] && { echo "log $name exists"; exit 2; }
if [ "$mode" = new ]; then flag="--session-id $session"; else flag="--resume $session"; fi
printf '%s' "$*" > "$R/logs/$name.prompt.txt"
cd "$R/${TRIAL_WORKDIR:-work-s}" || exit 1
env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_SSE_PORT TRIAL_TURN="$name" MEMBRAIN_DIRECTORY="$R/$brain" \
  claude -p "$*" --model "$model" --plugin-dir "$R/plugin" --output-format stream-json --verbose \
  --allowedTools "mcp__plugin_membrain_membrain" $flag > "$R/logs/$name.jsonl" 2> "$R/logs/$name.err"
rc=$?
python3 "$R/show.py" "$R/logs/$name.jsonl" | grep -v "^  CONTEXT <membrain-source>" | head -c 7000
echo "exit $rc"
