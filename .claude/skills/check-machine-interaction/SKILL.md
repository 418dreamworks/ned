---
name: check-machine-interaction
description: Use when the user says "check machine interaction" (or "check the machine interaction", "what just happened on the machine", "check terminal IO / the logs against mesa"). Reads the two rolling 1-hour logs — terminal IO and Mesa pin logging — correlates them by timestamp, summarizes the MOST RECENT event, and asks the user to confirm that is the event to troubleshoot before diagnosing.
---

# Check machine interaction

When the user asks to **check machine interaction**, do exactly this — in order — and then STOP and ask.

## The two logs (both roll for the last 1 hour)
- **Terminal IO** — `/home/brains/Documents/ned/term.log`
  Everything the user typed + its output. Captured with `script -f /home/brains/Documents/ned/term.log`.
- **Mesa pin log** — `/home/brains/Documents/ned/mesa.log`
  Timestamped Mesa output/gate states, written every ~0.2 s by `ned/tools/mesalog.sh`.
  Both self-prune to the last hour.

## Steps
1. **Verify both are live.** Read the tail of each and check the newest timestamps are recent (seconds–minutes old, not stale).
   - If `mesa.log` tail is old or reads `--- no HAL session ---`, or `term.log` hasn't updated: say so plainly and name which logger isn't running (`ned/tools/mesalog.sh` for mesa; `script -f .../term.log` for terminal). Do not fabricate an event from stale data.
2. **Read both logs** with their timestamps.
3. **Correlate by timestamp.** Line up the most recent user action/command in `term.log` with the Mesa pin changes in `mesa.log` at the same clock time — what was commanded vs how the hardware pins actually responded.
4. **Summarize the single MOST RECENT event**, tersely: what the user did (command / action), the timestamp, and how the machine responded (which pins/signals changed, any error, io_error, estop drop, enable state, motion or lack of it).
5. **STOP and ask:** "Is this the event you want to troubleshoot?" Do **not** start diagnosing until the user confirms — the most recent event may not be the one they care about.

## Rules
- Read the actual log bytes — never guess or reason from memory about what happened (this is the whole point of the logs).
- Keep the summary terse (project CLAUDE.md rules still apply): the event, the timestamp, the machine's response. No speculation about cause yet — that waits for the user's confirmation.
- If the two logs disagree (command sent but no pin change, or a pin change with no command), state that discrepancy — it is usually the clue.
