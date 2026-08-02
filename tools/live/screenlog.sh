#!/bin/bash
# screenlog.sh -- catch the screen-blanking culprit with timestamps.
# Logs, once per second, ONLY on change: X monitor power (xset q), every DRM
# connector's link status, and its dpms state. A blank event then shows up as
# either  (a) Monitor Off/Standby  -> something is DPMS-blanking us,
#         (b) connector disconnected -> HDMI signal drop (cable/EMI/monitor),
#         (c) NOTHING logged        -> the monitor itself is sleeping; the Pi
#             never stopped driving it (points at the monitor / its power).
# Correlate timestamps with gui.md / mesa.log (was the machine moving?).
LOG=/home/brains/Documents/ned/screen.log
export DISPLAY=:0
XAUTHORITY=$(ls /var/run/lightdm/root/:0 2>/dev/null | head -1)
[ -n "$XAUTHORITY" ] && export XAUTHORITY
prev=""
echo "$(date '+%F %T') screenlog start" >> "$LOG"
while true; do
  mon=$(xset q 2>/dev/null | grep -oE "Monitor is [A-Za-z]+")
  drm=""
  for c in /sys/class/drm/card*-HDMI*; do
    [ -e "$c/status" ] || continue
    drm="$drm $(basename $c)=$(cat $c/status 2>/dev/null),$(cat $c/dpms 2>/dev/null)"
  done
  # HDMI AUDIO stream open/close: starting/stopping an audio stream renegotiates the
  # HDMI link on some monitors -> brief self-recovering black screen. Operator reports
  # blanks correlate with the GUI being up -- catch any PCM state change here.
  aud=$(grep -h "state:" /proc/asound/card*/pcm*/sub*/status 2>/dev/null | tr -d ' ' | tr '\n' ',')
  [ -n "$aud" ] || aud=closed
  # X WINDOW LIST: the blanks leave DRM/DPMS/audio untouched, so the black is likely a
  # WINDOW (dialog/overlay/keyboard) appearing. Log every window-list change with names.
  win=$(xprop -root _NET_CLIENT_LIST 2>/dev/null | grep -oE '0x[0-9a-f]+' | while read -r id; do
          printf '%s=%s; ' "$id" "$(xprop -id "$id" WM_NAME 2>/dev/null | sed 's/.*= //;s/"//g' | cut -c1-24)"
        done)
  act=$(xprop -root _NET_ACTIVE_WINDOW 2>/dev/null | grep -oE '0x[0-9a-f]+' | head -1)
  cur="$mon |$drm |aud:$aud |act:$act |win:$win"
  if [ "$cur" != "$prev" ]; then
    echo "$(date '+%F %T.%3N') $cur" >> "$LOG"
    prev="$cur"
  fi
  # keep the log bounded
  if [ $(( $(date +%s) % 300 )) -eq 0 ]; then
    tail -n 500 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"
  fi
  sleep 1
done
