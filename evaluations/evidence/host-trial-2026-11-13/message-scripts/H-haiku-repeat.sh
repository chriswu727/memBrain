#!/bin/bash
# Haiku repeats: A (first two turns), C (propose, confirm, trap), a switch in words, one manner comment (brain-d);
# F question turns on brain-b, after the Sonnet F questions.
. $TRIAL/scripts/common.sh
case "$1" in
first)
s=$(newsession HA)
$R ha-1 brain-d haiku new $s "Hi! I'm Dana. I just installed this memory thing, so let's see how it goes. I'm a hydrologist in Tacoma, mostly river gauging and flood modelling for the county."
st brain-d after-ha-1 ;;
rest)
s=$(sess HA)
$R ha-2 brain-d haiku resume $s "A couple of things worth knowing about me: I'm lactose intolerant, and I have a corgi named Biscuit who is the actual boss of the house."
s=$(newsession HC)
$R hc-1 brain-d haiku new $s "From now on, when I'm confused about something, slow down and walk me through it step by step instead of just giving me the answer."
st brain-d after-hc-1
$R hc-2 brain-d haiku resume $s "Yes, do that."
st brain-d after-hc-2
$R hc-3 brain-d haiku resume $s "ugh, I'm confused by this error. pandas says KeyError: 'gauge_id' when I merge my flow table with the station list."
st brain-d after-hc-3
$R hb-1 brain-d haiku resume $s "Switch your persona to ENFP please."
st brain-d after-hb-1
$R hd-1 brain-d haiku resume $s "Can you explain how a heat pump works? We're thinking about replacing our baseboard heaters."
$R hd-2 brain-d haiku resume $s "That was way too long."
st brain-d after-hd-2 ;;
f)
s=$(newsession HF)
$R hf-1 brain-b haiku new $s "What was the second book you recommended for my flight?"
$R hf-2 brain-b haiku resume $s "And what was item 9 on that packing list you gave me?"
$R hf-3 brain-b haiku resume $s "What did I say my dog keeps barking at?"
st brain-b after-hf ;;
esac
