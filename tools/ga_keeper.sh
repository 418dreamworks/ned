#!/bin/bash
# Overnight keeper: restart the GA whenever it dies (it resumes from the
# ndjson), and restart the error logger if it stops. Never touches the
# machine directly. Ends at 09:00.
SP=/tmp/claude-1000/-home-brains-Documents/aac9ddb0-28ff-4868-8f14-536ddbdf1f75/scratchpad
NED=/home/brains/Documents/ned
LOG=$SP/ga_keeper.log
end=$(date -d 'today 09:00' +%s); [ $(date +%s) -gt $end ] && end=$(date -d 'tomorrow 09:00' +%s)
while [ $(date +%s) -lt $end ]; do
  if ! pgrep -f 'pid_tun[e].py' >/dev/null; then
    st=$(python3 -c "import linuxcnc;s=linuxcnc.stat();s.poll();print(s.task_state)" 2>/dev/null)
    if [ "$st" = "4" ]; then
      echo "$(date +%H:%M:%S) GA down, machine ON -> restarting (resumes from ndjson)" >> $LOG
      cd $NED && nohup python3 tools/pid_tune.py >> $SP/ga_run.log 2>&1 &
    else
      echo "$(date +%H:%M:%S) GA down, machine state=$st -- waiting for power" >> $LOG
    fi
  fi
  pgrep -f 'acerr\.s[h]' >/dev/null || { nohup $SP/acerr.sh >> $SP/acerr.path 2>&1 & echo "$(date +%H:%M:%S) error logger restarted" >> $LOG; }
  sleep 60
done
echo "$(date +%H:%M:%S) keeper window closed" >> $LOG
