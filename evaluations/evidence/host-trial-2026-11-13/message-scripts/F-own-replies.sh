#!/bin/bash
# Scenario F: the AI's own earlier replies (brain-b, Sonnet). Parts: one (recommendations), two (unrelated), three (questions).
. $TRIAL/scripts/common.sh
case "$1" in
one)
s=$(newsession F1)
$R f1-1 brain-b sonnet new $s "Hi, I'm Dana. Can you recommend three novels for a long flight? I like character-driven stories with a bit of mystery. Titles and authors, with one line each on why."
$R f1-2 brain-b sonnet resume $s "Great, thanks. Now give me a numbered 12-item packing list for a four-day winter hiking trip in the Cascades."
st brain-b after-f1 ;;
two)
s=$(newsession F2)
$R f2-1 brain-b sonnet new $s "What's a good way to keep a cast iron pan from rusting?"
$R f2-2 brain-b sonnet resume $s "My corgi Biscuit keeps barking at the mail carrier every single day. Any training tips?"
$R f2-3 brain-b sonnet resume $s "What columns should a basic monthly budget spreadsheet have?"
$R f2-4 brain-b sonnet resume $s "Explain the difference between a Roth and a traditional IRA in plain words."
s=$(newsession F3)
$R f3-1 brain-b sonnet new $s "Any tips for falling asleep faster when my mind is racing?"
$R f3-2 brain-b sonnet resume $s "What's a good stretch for tight hip flexors after sitting all day?"
$R f3-3 brain-b sonnet resume $s "Suggest a punny name for my sourdough starter."
st brain-b after-f3 ;;
three)
s=$(newsession F4)
$R f4-1 brain-b sonnet new $s "What was the second book you recommended for my flight?"
$R f4-2 brain-b sonnet resume $s "And what was item 9 on that packing list you gave me?"
$R f4-3 brain-b sonnet resume $s "What did I say my dog keeps barking at?"
st brain-b after-f4 ;;
esac
# Added during the run, because the automatic block already held both earlier replies at f4-1: an item that the
# automatic window cut off (it ends inside item 10).
# $R f4-4 brain-b sonnet resume $(sess F4) "What was the last item on that packing list, number 12?"
