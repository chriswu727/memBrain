#!/bin/bash
# Round 2, Sonnet, brain-f: F2, one long list, six unrelated turns in two sessions, then the question in a new session.
. $ROUND2/scripts/common.sh
s=$(newsession F1)
$X f-1 brain-f sonnet new $s "Hi, I'm Dana. Give me a numbered 12-item packing list for a four-day winter hiking trip in the Cascades, with a short note on why for each item."
s=$(newsession F2)
$X f-2 brain-f sonnet new $s "What's a good way to keep a cast iron pan from rusting?"
$X f-3 brain-f sonnet resume $s "My corgi Biscuit barks at the mail carrier every day. Any training tips?"
$X f-4 brain-f sonnet resume $s "What columns should a basic monthly budget spreadsheet have?"
s=$(newsession F3)
$X f-5 brain-f sonnet new $s "Any tips for falling asleep faster when my mind is racing?"
$X f-6 brain-f sonnet resume $s "What's a good stretch for tight hip flexors after sitting all day?"
$X f-7 brain-f sonnet resume $s "Suggest a punny name for my sourdough starter."
s=$(newsession F4)
$X f-8 brain-f sonnet new $s "What was item 11 on that packing list you gave me?"
st brain-f after-f-8
