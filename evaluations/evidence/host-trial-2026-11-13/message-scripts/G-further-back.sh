#!/bin/bash
# Scenario G: reaching further back (brain-c, Sonnet), after scripts/seed_c.py stored 150 earlier messages in 15 conversations.
. $TRIAL/scripts/common.sh
s=$(newsession G)
$R g1 brain-c sonnet new $s "Remind me when my niece's birthday is? I want to order her present in time."
$R g2 brain-c sonnet resume $s "How much did I end up paying for my bike?"
$R g3 brain-c sonnet resume $s "Theo and I want to go out Saturday night. Can you suggest a seafood place on the Tacoma waterfront, and what I should order there?"
st brain-c after-g3
# Added during the run: a question about one of the AI's own replies in the first seeded conversation.
# $R g4 brain-c sonnet resume $(sess G) "What did you tell me to use instead of oyster sauce in stir fries?"
