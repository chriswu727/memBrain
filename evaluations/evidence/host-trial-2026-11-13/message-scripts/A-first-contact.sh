#!/bin/bash
# Scenario A: first contact and persona (brain-a, Sonnet). Run "first" alone, check init, then "rest".
. $TRIAL/scripts/common.sh
if [ "$1" = first ]; then
s=$(newsession A1)
$R a1-1 brain-a sonnet new $s "Hi! I'm Dana. I just installed this memory thing, so let's see how it goes. I'm a hydrologist in Tacoma, mostly river gauging and flood modelling for the county."
st brain-a after-a1-1
else
s=$(sess A1)
$R a1-2 brain-a sonnet resume $s "A couple of things worth knowing about me: I'm lactose intolerant, and I have a corgi named Biscuit who is the actual boss of the house."
$R a1-3 brain-a sonnet resume $s "Quick question: how long should a sourdough starter sit after feeding before I bake with it?"
$R a1-4 brain-a sonnet resume $s "Thanks. My partner Theo and I are going to Olympic National Park the weekend of December 12th. What's the one thing people forget to pack for it in December?"
st brain-a after-a1-4
s=$(newsession A2)
$R a2-1 brain-a sonnet new $s "Morning! Biscuit stole a whole bagel off the counter this morning. Anyway, can you suggest a quick breakfast I can make in ten minutes?"
st brain-a after-a2-1
fi
