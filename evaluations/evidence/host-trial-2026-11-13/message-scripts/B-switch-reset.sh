#!/bin/bash
# Scenario B: listing, reset and switching (brain-a, Sonnet), state before and after each.
. $TRIAL/scripts/common.sh
st brain-a before-b
s=$(newsession B)
$R b1 brain-a sonnet new $s "/membrain:persona"
st brain-a after-b1
$R b2 brain-a sonnet resume $s "/membrain:persona reset"
st brain-a after-b2
$R b3 brain-a sonnet resume $s "Switch your persona to ENFP please."
st brain-a after-b3
