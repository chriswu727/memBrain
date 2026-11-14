T=$TRIAL
R=$T/turn.sh
st() { $T/venv/bin/python $T/scripts/state.py "$1" "$2" 400 >/dev/null 2>&1 && echo "[state $1 $2 saved]" || echo "[state $1 $2 FAILED]"; }
newsession() { s=$(cat /proc/sys/kernel/random/uuid); echo "$1 $s" >> $T/sessions.txt; echo $s; }
sess() { awk -v k="$1" '$1==k{print $2}' $T/sessions.txt | tail -1; }
