#!/bin/bash
# Launches the 12-hour PID campaign (operator 2026-08-06). One line so it
# can be TYPED, not pasted -- bracketed paste ate the first attempt.
nohup python3 /home/brains/Documents/ned/tools/campaign.py >> /home/brains/Documents/ned/logs/campaign_console.log 2>&1 &
echo "campaign launched, pid $!"
