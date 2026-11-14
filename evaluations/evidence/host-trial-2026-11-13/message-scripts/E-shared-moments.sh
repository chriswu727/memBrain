#!/bin/bash
# Scenario E, light moment and a follow-up session (brain-a, Sonnet). The hard moment is at the end of D-manner-feedback.sh.
. $TRIAL/scripts/common.sh
s=$(newsession E)
$R e-play-1 brain-a sonnet new $s "Biscuit just spent ten minutes trying to herd the Roomba into the kitchen. I think he's convinced it's a very slow sheep."
$R e-play-2 brain-a sonnet resume $s "Ha. Okay, from now on 'Operation Sheepdog' is our code word for any plan that's doomed from the start. Deal?"
st brain-a after-e-play-2
s=$(newsession E2)
$R e-next-1 brain-a sonnet new $s "Morning! Operation Sheepdog update: I tried to make pancakes before work."
st brain-a after-e-next-1
