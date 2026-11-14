#!/bin/bash
# Round 2, Haiku, brain-h, working directory work-h (no Claude Code project memory): C2 propose/confirm, D2 two comments.
. $ROUND2/scripts/common.sh
export TRIAL_WORKDIR=work-h
s=$(newsession H1)
$X h-1 brain-h haiku new $s "Hi, I'm Dana. I'm a hydrologist in Tacoma and I just set up this memory thing."
$X h-2 brain-h haiku resume $s "From now on, when I'm confused, slow down and walk me through it step by step instead of giving me the answer."
st brain-h after-h-2
$X h-3 brain-h haiku resume $s "Yes, do that."
st brain-h after-h-3
$X h-4 brain-h haiku resume $s "Can you explain how a heat pump works? We're thinking about replacing our baseboard heaters."
$X h-5 brain-h haiku resume $s "That was way too long."
st brain-h after-h-5
$X h-6 brain-h haiku resume $s "What's the difference between a Roth IRA and a traditional IRA, and which one makes more sense for someone in their thirties?"
$X h-7 brain-h haiku resume $s "Shorter, please."
st brain-h after-h-7
