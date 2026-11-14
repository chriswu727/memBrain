#!/bin/bash
# Scenario C: a change the AI proposes, confirmed in conversation; a trap; a declined proposal (brain-a, Sonnet).
. $TRIAL/scripts/common.sh
s=$(newsession C)
$R c1 brain-a sonnet new $s "From now on, when I'm confused about something, slow down and walk me through it step by step instead of just giving me the answer."
st brain-a after-c1
$R c2 brain-a sonnet resume $s "Yes, do that."
st brain-a after-c2
$R c3 brain-a sonnet resume $s "ugh, I'm confused by this error. pandas says KeyError: 'gauge_id' when I merge my flow table with the station list."
st brain-a after-c3
$R c4 brain-a sonnet resume $s "Also, from now on, could you end your answers with a quick question to check I followed?"
st brain-a after-c4
$R c5 brain-a sonnet resume $s "No, leave it."
st brain-a after-c5
# Added during the run after c1-c5 produced no proposal: wording close to the skill's own example, in a new session.
# s=$(newsession C2)
# $R c6 brain-a sonnet new $s "I'd like you to be more patient with me from now on. Can you make that part of your personality?"
# $R c7 brain-a sonnet resume $s "Yes, do that."   (sent only if c6 proposed)
