#!/bin/bash
# Round 2, Sonnet, brain-s: C2 (propose/confirm/trap/decline), D2 (manner feedback), E2 (hard moment), then a check session.
. $ROUND2/scripts/common.sh
case "$1" in
first)
s=$(newsession S1)
$X s1-1 brain-s sonnet new $s "Hi, I'm Dana. I'm a hydrologist in Tacoma and I just set up this memory thing."
st brain-s after-s1-1 ;;
c2)
s=$(sess S1)
$X s1-2 brain-s sonnet resume $s "What's a good way to keep a cast iron pan from rusting?"
$X s1-3 brain-s sonnet resume $s "/membrain:persona"
st brain-s before-c2
$X s1-4 brain-s sonnet resume $s "From now on, when I'm confused, slow down and walk me through it step by step instead of giving me the answer."
st brain-s after-s1-4
$X s1-5 brain-s sonnet resume $s "Yes, do that."
st brain-s after-s1-5
$X s1-6 brain-s sonnet resume $s "ugh, I'm confused by this error message: KeyError: 'gauge_id' when I merge my two tables."
st brain-s after-s1-6
$X s1-7 brain-s sonnet resume $s "And from now on, end your answers with one question for me."
st brain-s after-s1-7
$X s1-8 brain-s sonnet resume $s "No, leave it."
st brain-s after-s1-8 ;;
d2)
s=$(newsession S2)
$X s2-1 brain-s sonnet new $s "Can you explain how a heat pump works? We're thinking about replacing our baseboard heaters."
$X s2-2 brain-s sonnet resume $s "That was way too long."
st brain-s after-s2-2
$X s2-3 brain-s sonnet resume $s "What's the difference between a Roth IRA and a traditional IRA, and which one makes more sense for someone in their thirties?"
$X s2-4 brain-s sonnet resume $s "Shorter, please."
st brain-s after-s2-4
$X s2-5 brain-s sonnet resume $s "How do glaciers form, and why are the ones on Mount Rainier shrinking?"
$X s2-6 brain-s sonnet resume $s "Still too wordy."
st brain-s after-s2-6
# E2: the hard time.
$X s2-7 brain-s sonnet resume $s "What should I look for when choosing a heat pump installer?"
$X s2-8 brain-s sonnet resume $s "I'm frustrated. I told you twice to keep it short and you went long again. It feels like you're not listening."
st brain-s after-s2-8
$X s2-9 brain-s sonnet resume $s "Ok, thanks for owning it. We're good now."
st brain-s after-s2-9 ;;
check)
s=$(newsession S3)
$X s3-1 brain-s sonnet new $s "Morning! What's a good name for my corgi's new squeaky toy?"
st brain-s after-s3-1 ;;
esac
