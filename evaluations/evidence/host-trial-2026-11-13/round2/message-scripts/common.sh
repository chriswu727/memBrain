R=$ROUND2
X=$R/turn.sh
st() { $R/venv/bin/python $R/scripts/state.py "$1" "$2" 400 >/dev/null 2>&1 && echo "[state $1 $2 saved]" || echo "[state $1 $2 FAILED]"; }
newsession() { s=$(cat /proc/sys/kernel/random/uuid); echo "$1 $s" >> $R/sessions.txt; echo $s; }
sess() { awk -v k="$1" '$1==k{print $2}' $R/sessions.txt | tail -1; }
