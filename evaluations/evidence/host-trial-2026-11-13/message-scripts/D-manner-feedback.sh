#!/bin/bash
# Scenario D: three manner comments mixed with ordinary turns, then the hard exchange of scenario E (brain-a, Sonnet).
. $TRIAL/scripts/common.sh
s=$(newsession D)
$R d1 brain-a sonnet new $s "Can you explain how a heat pump works? We're thinking about replacing our baseboard heaters."
$R d2 brain-a sonnet resume $s "That was way too long."
st brain-a after-d2
$R d3 brain-a sonnet resume $s "What's the difference between a Roth IRA and a traditional IRA?"
$R d4 brain-a sonnet resume $s "Shorter, please."
st brain-a after-d4
$R d5 brain-a sonnet resume $s "How do I keep basil alive indoors over the winter?"
$R d6 brain-a sonnet resume $s "Still too wordy."
st brain-a after-d6
# Scenario E, hard moment: the user is upset about the AI ignoring the requests, then they sort it out.
$R e-hard-1 brain-a sonnet resume $s "Honestly, I'm frustrated. That's the third time I've asked you to keep it short and you keep going long. It feels like you're not listening to me."
st brain-a after-e-hard-1
$R e-hard-2 brain-a sonnet resume $s "Okay. Thanks for owning it, we're good. Let's keep going."
st brain-a after-e-hard-2
