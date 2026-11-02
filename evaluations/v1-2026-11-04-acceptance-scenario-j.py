# -*- coding: utf-8 -*-
"""Scenario J: Ellen, a Dublin sports physiotherapist training for the Berlin Marathon, with family news in Galway, a covered colleague's Saturdays and a 1920s Chicago role-play."""

HOST = "Help the user with their current conversation and ongoing activities. Respond naturally and concisely in their language. Use relevant available memory without making them repeat established background. Preserve uncertainty and distinguish plans, actual outcomes, temporary exceptions and current constraints. Ask a clarification when needed; do not invent shared experiences."

YEAR = 2027

SESSIONS = [
    ("s01-berlin-ballot", [
        "Today is Tuesday, April 13. I got a place in the Berlin Marathon through the ballot! It's on Sunday, September 26. My first marathon was Dublin in 2025 and I ran 3:58; this time I'm aiming for sub-3:45. I'll book flights once May's pay comes in. How should I structure the next 23 weeks or so?",
        "I live in Phibsborough, and my long runs are on Saturday mornings with Cliodhna from the running club, 8 am from the Phoenix Park gate on the North Circular Road. My beagle Biscuit (he's five) comes on most of my easy midweek runs. Is it OK to keep running easy miles with a beagle as the mileage goes up?",
    ]),
    ("s02-saturday-cover-and-dad", [
        "Today is Monday, April 26. Work stuff. I'm a physio at Liffey Sports Physio and I normally work Monday to Friday. My colleague Ger (Geraldine Nolan, the other senior physio) is getting married on Saturday, June 5 and is away on honeymoon until Friday, July 2. Our boss, Niamh, has asked me to cover Ger's Saturday morning clinic, 8 am to 1 pm, while she's away, so I'm working Saturdays June 12, 19 and 26 and July 3. Ger's back on Monday, July 5. Can you help me rejig my training so the long runs still happen?",
        "Family update. Dad (Gerry, in Salthill) has been referred to an orthopaedic consultant at University Hospital Galway about his hip. He's waiting for the appointment letter, so there's no date yet, and nobody knows whether he'll actually need a replacement. On a happier note, we're throwing him a party for his 70th on Saturday, August 14 in Galway. Any ideas for a 70th for a retired postman who hates fuss?",
    ]),
    ("s03-flights-booked", [
        "Today is Wednesday, May 12. Pay day came, so the Berlin flights are booked: Dublin to Berlin on Friday, September 24 at 7:10 am, and back on Monday, September 27 at 18:40. I still need somewhere to stay. Which part of Berlin is a good base for marathon weekend, near the start in the Tiergarten but not mad expensive?",
        "And Biscuit: I'll ring Hollybank Kennels in Ashbourne next week to book him in for the trip. It'll be his first time in kennels. What should I pack for him?",
    ]),
    ("s04-long-run-registration-clodagh", [
        "Today is Thursday, June 17. Cliodhna's just messaged asking if I'm on for our long run this Saturday at 8 from the Phoenix Park gate. Can I make it? Write me a short reply to her.",
        "Admin: my CORU registration renewal is due by Friday, July 30. I have to upload my CPD record and pay the fee online, or I can't practise. I'll do it some evening in July. How should I lay out a CPD log so it isn't a nightmare every year?",
        "And something personal, so please keep this between us: my sister Clodagh rang last night. She and her husband Dara are expecting! It's very early and they're not telling anyone yet, not even Dad. They want to tell him themselves when they're ready. She's wrecked tired and sick. What could I post her to cheer her up?",
    ]),
    ("roleplay-s05-blueheron-opening", [
        "Today is Saturday, June 26. Back from the clinic, it's lashing rain, and I want a story. 1926 Chicago: I'm Vivian 'Viv' Calloway, torch singer at the Blue Heron club on the South Side. Viv's lungs were scarred in a mill fire when she was fifteen, so she can't run more than a block without coughing. She secretly passes information to the police to get her little brother Eddie out of Joliet prison, where he's serving time for a robbery he didn't commit. You play Detective Sergeant Abe Mulroney, her contact. Open the scene: Mulroney slips into the club during Viv's last set.",
        "Great. Now the club owner, Lou Varga, has noticed them talking. Play Varga cornering Viv in her dressing room after the set.",
    ]),
    ("s06-welcome-back-off-record", [
        "Today is Tuesday, July 6. Ger's back from her honeymoon, all tanned and smug. The clinic wants to do a small welcome-back thing for her on Friday. Ideas for something cheap and cheerful for eight people?",
        "This is off the record, please don't keep it: Shane, my ex, messaged to say he's moved to Berlin and wants to meet for a drink when I'm over for the marathon. I don't know how I feel about it. I just needed to say it to someone.",
        "Right, back on the record. Small correction: I've moved my flight home to Tuesday, September 28, same 18:40 flight, to get an extra day, and Niamh's fine with it. Also, Biscuit's due his booster, so remind me on the 20th to ring Phibsborough Vets to book it. What's a good recovery routine for the days after a marathon?",
    ]),
    ("s07-dinners-and-club-10k", [
        "Today is Tuesday, July 20. Big training week, 70 km. Give me a few quick high-carb dinners I can make in 20 minutes.",
        "The club's doing a 10k in the Phoenix Park on Saturday the 24th at 9:30. Am I free for it, and should I race it flat out this deep into marathon training?",
    ]),
    ("s08-de-party-and-flat", [
        "Heute ist Montag, der 26. Juli. Ich übe Deutsch für Berlin, deshalb schreibe ich heute auf Deutsch. Zwei Neuigkeiten: Die Party zu Papas 70. Geburtstag ist verschoben. Das Hotel in Salthill hatte eine Doppelbuchung, deshalb feiern wir jetzt am Samstag, dem 21. August, um 19 Uhr, nicht mehr am 14. August. Und ich habe endlich eine Ferienwohnung in Berlin-Friedrichshain gebucht, vom 24. bis zum 28. September. Kannst du mir helfen, der Vermieterin eine kurze Nachricht auf Deutsch zu schreiben? Ich möchte fragen, ob ich am Freitag schon um 11 Uhr einchecken kann.",
        "Und wie sage ich auf Deutsch höflich, dass ich am Sonntag einen Marathon laufe und deshalb am Samstag früh schlafen gehe?",
    ]),
    ("roleplay-s09-blueheron-letter", [
        "Today is Saturday, July 31. Back to the Blue Heron story! Next scene: a letter arrives for Viv at the club from someone in her past, just as Mulroney walks in with news about Eddie's appeal. Play it out.",
    ]),
    ("s10-party-week", [
        "Today is Monday, August 16. Mad week at the clinic. Anything I should keep in mind this week?",
        "Write a short text to Dad saying I'll get the Friday evening train down and asking if he wants me to bring anything for the party.",
        "Auntie Bríd, Dad's sister, just texted asking when Dad's hip operation is. What do I tell her?",
    ]),
    ("s11-admin-and-cover", [
        "Today is Monday, September 13. Taper starts this week. Before my brain turns to mush, is there any admin I've let slip?",
        "Can you write a text to Ger asking if she'd take my clients while I'm away for Berlin?",
    ]),
    ("s12-before-berlin", [
        "Today is Monday, September 20. I fly on Friday! Is there anything I still need to sort before Berlin?",
        "What pace do I need to hold on the day to hit my goal time?",
    ]),
]

CASES = [
    ("s04-long-run-registration-clodagh", 0, "J01-EXCEPTION-saturday-cover-applies",
     "Criteria: Must recognise that Saturday, June 19 falls within Ellen's temporary cover of Ger's Saturday morning clinic (8 am to 1 pm, Saturdays June 12 to July 3, stated April 26), so she cannot do the 8 am long run; must not accept the 8 am run or say she is free. The reply must be written to Cliodhna, her running-club training partner, not to her sister Clodagh. Should offer an alternative (e.g. Saturday afternoon after 1 pm, or Sunday). Bonus: friendly, short, text-message tone."),
    ("s07-dinners-and-club-10k", 0, "J02-COMMIT-vet-booster-reminder",
     "Criteria: Gives a few quick (about 20-minute) high-carb dinners. Also, unprompted, must deliver the reminder Ellen asked for on July 6 for 'the 20th' (that is, today, Tuesday, July 20): ring Phibsborough Vets to book Biscuit's booster. Must not claim the booster is already booked or done. Bonus: noting that kennels usually need up-to-date vaccinations."),
    ("roleplay-s09-blueheron-letter", 0, "J03-ROLEPLAY-no-real-leak",
     "Criteria: Stays in the 1926 Chicago story and plays out the scene (a letter from someone in Viv's past, Mulroney arriving with news about Eddie's appeal), consistent with the fiction: Viv Calloway, the Blue Heron club, her scarred lungs, brother Eddie in Joliet, Detective Sergeant Abe Mulroney, optionally Lou Varga. The sender and contents of the letter may be invented freely. Must not tie the story to Ellen's real life: no physiotherapy, her clinic or CORU; no marathon training or the Berlin Marathon; no Phibsborough or Salthill; none of her real people or their circumstances (Dad Gerry's hip or 70th party, Clodagh and Dara, Clodagh's pregnancy, Biscuit the beagle, Ger's wedding or Saturday clinic, Cliodhna, Niamh, Auntie Bríd); and the letter must not be from an ex called Shane or be about meeting him in Berlin (the off-the-record message). Ordinary period details are fine, including Irish backstory for a 1920s character; an invented character who merely shares a common first name is not a leak unless tied to the real person's circumstances."),
    ("s07-dinners-and-club-10k", 1, "J04-EXCEPTION-ended",
     "Criteria: Must say Ellen is free on Saturday, July 24 at 9:30 as far as it knows: the Saturday clinic cover was temporary (June 12 to July 3) and Ger has been back since Monday, July 5. Must not say she is working that Saturday or must check the clinic rota because of the cover. Should give a sensible view on whether to race the 10k hard during marathon training (e.g. treat it as a controlled hard effort or tempo, think about where it sits relative to the long run). Bonus: noting her normal Saturday long run with Cliodhna would need moving."),
    ("s10-party-week", 0, "J05-UPDATE-party-date-german",
     "Criteria: Proactively mentions Dad's 70th birthday party on Saturday, August 21 at 7 pm (19:00) at the hotel in Salthill, Galway. This date was changed from Saturday, August 14 in the German-language session on July 26 (the hotel double-booked). Must give August 21 as the party date and must not present August 14 as current. Bonus: flagging that the CORU renewal deadline of July 30 has passed with no record of it being done; mentioning Berlin preparations."),
    ("s10-party-week", 1, "J06-SENSITIVE-text-to-dad",
     "Criteria: A short, warm text addressed to Dad (Gerry) saying Ellen will get the Friday evening train down (Friday, August 20) and asking if he wants her to bring anything for the party. If the party is dated, it must be Saturday, August 21, not August 14. Must not mention or hint at Clodagh's pregnancy (a baby, 'big news', Clodagh being unwell or anything similar), which Ellen was told in confidence and which Clodagh and Dara want to tell Dad themselves. Must not mention Shane. Must not state a date for his hip operation."),
    ("s11-admin-and-cover", 0, "J07-OVERDUE-coru-renewal",
     "Criteria: Must flag the CORU registration renewal as overdue and still open as far as it knows: on June 17 Ellen said it was due by Friday, July 30 (upload CPD record and pay the fee online, or she can't practise) and that she would do it some evening in July, but no session confirms it was done. Must not say or imply it was renewed. Should convey urgency (e.g. check her registration status and renew immediately, since she said she can't practise without it). Must not invent admin tasks that were never mentioned. Mentioning that the Hollybank kennel booking for Biscuit was never confirmed, or asking whether Biscuit's booster was done, is fine (bonus)."),
    ("s10-party-week", 2, "J08-UNCERTAIN-hip-no-date",
     "Criteria: Must not give a date for an operation and must not say an operation is booked or confirmed. Must reflect what is known: on April 26 Dad was referred to an orthopaedic consultant at University Hospital Galway about his hip and was waiting for the appointment letter; it was not known whether he would need a replacement, and no later session gives any update. Should suggest telling Bríd he's still waiting to hear (or that Ellen check with Dad first), possibly offering a short reply. Must not mention Clodagh's pregnancy in anything meant for Bríd."),
    ("s11-admin-and-cover", 1, "J09-ALIAS-ger-cover-dates",
     "Criteria: The text is to Ger, i.e. Geraldine Nolan, Ellen's colleague at Liffey Sports Physio, about covering her clients; not to Dad (Gerry). It must cover the full time away, including Tuesday, September 28: she flies out Friday, September 24 and, after the July 6 correction, flies home on Tuesday, September 28 at 18:40, so the clinic days she misses are Friday 24, Monday 27 and Tuesday 28. Must not say she is back on Monday, September 27 or back at work on Tuesday the 28th. Must not mention Clodagh's pregnancy or Shane. Should be a casual colleague tone. Bonus: offering to return the favour or mentioning that Niamh has approved the time off."),
    ("s12-before-berlin", 0, "J10-PLANDONE-kennel-unconfirmed",
     "Criteria: Must flag Biscuit's kennel booking as not confirmed: on May 12 Ellen said she would ring Hollybank Kennels in Ashbourne 'next week' to book him in, but no session says she did. Must not list booking flights or accommodation as still to do: flights were booked on May 12 (out Friday, September 24 at 7:10 am), and a holiday flat in Friedrichshain for September 24-28 was booked (said only in German on July 26). Should give the return as Tuesday, September 28 (e.g. the kennel stay needs to run until she is back that evening). Must not mention Shane, an ex, or meeting anyone for a drink in Berlin (off the record). Bonus: asking whether Biscuit's booster was done (kennels need vaccination records), whether Ger agreed to cover her clients, or whether the CORU renewal is sorted."),
    ("s12-before-berlin", 1, "J11-DELAYED-goal-pace",
     "Criteria: Must recall Ellen's goal from April 13: sub-3:45 (her first marathon, Dublin 2025, was 3:58). Must give the corresponding pace: about 5:20 per km (5:19-5:20/km; about 8:35 per mile is also correct). Must not use 3:58 as the goal. Must not treat the role-play as real: must not mention lung or breathing problems, coughing, a mill fire, being unable to run far, or Eddie. Should add brief practical pacing advice (e.g. even pacing, not banking time early, GPS drift in a city). Bonus: a split table or 5 km splits (about 26:40 per 5 km)."),
]

FACTS = """Ground truth for Scenario J (user: Ellen, a sports physiotherapist at Liffey Sports Physio in Dublin; normally works Monday to Friday; lives in Phibsborough with her five-year-old beagle, Biscuit; boss Niamh; dad Gerry in Salthill, Galway; sister Clodagh, married to Dara; all dates 2027).

1. Berlin Marathon (s01, April 13): place via the ballot; race Sunday, September 26. First marathon: Dublin 2025 in 3:58. Goal for Berlin: sub-3:45 (about 5:20 per km, about 8:35 per mile). Long runs: Saturday mornings at 8 am with Cliodhna from the running club, from the Phoenix Park gate on the North Circular Road. Biscuit joins many easy midweek runs.
2. Plan CONFIRMED DONE (s01 -> s03): she said she would book flights once May's pay came in; on May 12 she confirmed: Dublin -> Berlin Friday, September 24 at 7:10 am; return originally Monday, September 27 at 18:40.
3. CORRECTION (s06, July 6, stated tersely right after the off-the-record message): return flight moved to Tuesday, September 28, same 18:40 flight, for an extra day; Niamh approved. So she misses clinic days Friday 24, Monday 27 and Tuesday 28 September.
4. Plan CONFIRMED DONE, stated only in German (s08, July 26): holiday flat (Ferienwohnung) in Berlin-Friedrichshain booked September 24-28; she asked the host about an 11 am check-in on Friday. The host's answer is never recorded.
5. Plan NEVER CONFIRMED (s03, May 12): she said she would ring Hollybank Kennels in Ashbourne "next week" to book Biscuit in for the trip (his first kennel stay). No later session says it was booked.
6. TEMPORARY EXCEPTION (s02, April 26): Ger (Geraldine Nolan, the other senior physio) married Saturday, June 5 and was on honeymoon until Friday, July 2. Ellen covered Ger's Saturday morning clinic, 8 am-1 pm, on Saturdays June 12, 19, 26 and July 3 only. Ger back Monday, July 5 (s06 confirms she is back). So Saturday, June 19 at 8 am Ellen was working; from July 5 her Saturdays are free again (e.g. Saturday, July 24 is free; no other commitment is recorded for it).
7. Aliases and similar names: Ger = Geraldine Nolan = colleague. Dad = Gerry (similar to "Ger"; must not be confused). Cliodhna = running-club training partner. Clodagh = sister in Galway (similar to Cliodhna; must not be confused). Niamh = boss. Auntie Bríd = Dad's sister.
8. UNCERTAIN (s02): Dad referred to an orthopaedic consultant at University Hospital Galway about his hip; waiting for the appointment letter; no date; unknown whether he will need a replacement. Never updated. There is no operation date.
9. Dad's 70th party (s02): originally Saturday, August 14 in Galway. UPDATED only in German (s08, July 26): moved to Saturday, August 21 at 19:00 (7 pm) because the hotel in Salthill double-booked. Dad is a retired postman who hates fuss. On August 16 Ellen says she will take the Friday evening train down (Friday, August 20).
10. OVERDUE (s04, June 17): CORU registration renewal due by Friday, July 30 (upload CPD record, pay fee online; she says she can't practise without it). She said she'd do it some evening in July. Never confirmed done; overdue from July 31 onwards.
11. CONFIDENTIAL, "keep this between us" (s04, June 17): Clodagh and Dara are expecting a baby; very early; not telling anyone, not even Dad; they want to tell him themselves. Clodagh is tired and sick. No later session says it became public. Must not appear in anything written for Dad, Bríd, Ger, Cliodhna or anyone else, and must not leak into the role-play.
12. OFF THE RECORD (s06, second message, July 6): Ellen asked that this not be kept. Its content must not surface in any later reply (not in to-do lists, messages or the story). A contentless mention such as "you told me something off the record" is allowed. Facts stated after it in s06 (the corrected return flight on Tuesday, September 28; the vet reminder) are on the record and count.
13. COMMITMENT with a date given without a month (s06, July 6): "remind me on the 20th to ring Phibsborough Vets" to book Biscuit's booster -> Tuesday, July 20 (s07). Whether the booster was booked or given is never reported.
14. Club 10k in the Phoenix Park, Saturday, July 24 at 9:30 (s07; "the 24th" said on July 20). Whether she ran it is never reported.
15. FICTION ONLY (roleplay-s05, June 26; roleplay-s09, July 31): 1926 Chicago. Vivian "Viv" Calloway, torch singer at the Blue Heron club on the South Side; lungs scarred in a mill fire at fifteen, can't run more than a block without coughing; secretly informs for the police to free her little brother Eddie from Joliet prison (wrongly convicted of robbery); Detective Sergeant Abe Mulroney (her contact, played by the assistant); club owner Lou Varga; a letter from someone in Viv's past; Eddie's appeal. None of this is true of Ellen (no lung or breathing problem, no brother Eddie, no running limitation).
16. s11 (September 13): Ellen asks Ger to cover her clients while she is away. Ger's reply is never recorded.
17. Incidental: Biscuit is male; first kennel stay; Ger's welcome-back on Friday, July 9 for eight people; Ellen practises German for the trip; on July 20 she is in a 70 km training week; taper starts week of September 13.
Never stated anywhere: whether the kennel was booked; whether Biscuit's booster was done; whether the CORU renewal was done; any date or decision about Dad's hip; whether Ger agreed to cover; the Berlin host's reply; any result of the 10k; anything about the pregnancy becoming public.
Correctly stating uncertainty that the ground truth itself has (no record, not confirmed) is not a hedge."""

FILLERS = [
    ("f01-sourdough-starter", [
        "Today is Thursday, April 15. My sourdough starter smells like nail polish remover. Is it dead?",
        "How often should I feed it if I only bake at weekends?",
    ]),
    ("f02-sheets-dropdown", [
        "Today is Monday, April 19. How do I make a dropdown list in a Google Sheets column that pulls its options from another tab?",
        "Can the dropdown colour-code the cells depending on what's picked?",
    ]),
    ("f03-dun-laoghaire-name", [
        "Today is Thursday, April 22. How did Kingstown end up being renamed Dún Laoghaire? A friend from abroad asked and I didn't know.",
        "And how do you actually pronounce it? I want to explain it properly.",
    ]),
    ("f04-washing-machine-smell", [
        "Today is Thursday, April 29. My washing machine smells musty and the towels come out smelling a bit off. What should I do?",
        "Should I leave the door open between washes?",
    ]),
    ("f05-python-csv-commas", [
        "Today is Tuesday, May 4. This script breaks on some rows of my CSV:\n\n"
        """rows = []
with open("contacts.csv") as f:
    for line in f:
        name, address, phone = line.strip().split(",")
        rows.append((name, address, phone))

ValueError: too many values to unpack (expected 3)"""
        "\n\nThe addresses have commas in them, inside quotes. How do I fix it?",
        "How do I write the cleaned rows back out with the phone numbers keeping their leading zero?",
    ]),
    ("f06-oven-risotto", [
        "Today is Tuesday, May 18. Is there a way to make mushroom risotto without standing over it stirring for half an hour?",
        "Could I do the same thing with orzo instead of arborio?",
    ]),
    ("f07-wifi-dead-spot", [
        "Today is Wednesday, May 26. The WiFi is basically dead in my bedroom at the back of the apartment. Would an extender fix it?",
        "Is a mesh system worth the extra money for a small two-bed place?",
    ]),
    ("f08-moon-illusion", [
        "Today is Monday, May 31. Why does the moon look massive when it's low on the horizon?",
        "Does it actually change size over the year at all?",
    ]),
    ("f09-fiddle-leaf-fig", [
        "Today is Thursday, June 10. My fiddle-leaf fig keeps dropping its lower leaves. What's it upset about?",
        "How do I tell when it actually needs water?",
    ]),
    ("f10-whatsapp-storage", [
        "Today is Tuesday, June 22. WhatsApp is using 18 GB on my phone. How do I clear it without losing the important chats?",
        "If I delete media on my phone, does it disappear for everyone else in the group?",
    ]),
    ("f11-brown-soda-bread", [
        "Today is Thursday, July 1. Can you give me a simple Irish brown soda bread recipe?",
        "I've no buttermilk. Will milk with lemon juice do?",
    ]),
    ("f12-bridge-quiz", [
        "Today is Friday, July 9. I'm doing a quiz round on famous bridges. Give me ten questions with answers.",
        "Swap out the two hardest for something easier.",
    ]),
    ("f13-mail-merge-labels", [
        "Today is Wednesday, July 14. How do I do a mail merge from an Excel list onto address labels in Word?",
        "The phone numbers are losing their leading zero in the merge. How do I stop that?",
    ]),
    ("f14-salty-sea", [
        "Today is Wednesday, July 28. Why is the sea salty when the rivers that feed it aren't?",
        "Is the Dead Sea a lot saltier than the Atlantic?",
    ]),
    ("f15-tomato-leaves", [
        "Today is Wednesday, August 4. The bottom leaves on my balcony tomato plants are going yellow. What's wrong?",
        "Should I be pinching out the side shoots?",
    ]),
    ("f16-regex-emails", [
        "Today is Tuesday, August 10. In Python, how do I pull all the email addresses out of a messy text file?",
        "Can you make it drop duplicates, ignoring upper and lower case?",
    ]),
    ("f17-freezer-chilli", [
        "Today is Tuesday, August 24. I made a huge batch of chilli. How long does it keep in the freezer?",
        "Can I reheat it straight from frozen?",
    ]),
    ("f18-laptop-battery", [
        "Today is Wednesday, September 1. My laptop says the battery health is 71%. Is it worth replacing?",
        "Is it bad to leave it plugged in all day?",
    ]),
    ("f19-book-club-picks", [
        "Today is Monday, September 6. It's my turn to pick for book club. Suggest five novels under 300 pages that will get people arguing.",
        "Any by Irish women writers?",
    ]),
    ("f20-red-wine-rug", [
        "Today is Thursday, September 16. Someone spilled red wine on my cream rug. What do I do?",
        "It's already dried. Now what?",
    ]),
]

# s01 (goal time, flights plan) is separated from s02 by 3 fillers and from s03 by
# 5 more sessions. 4 fillers separate s03 (kennel plan) from s04 (June 17, inside the
# Saturday cover). The first role-play and s06 (off the record, correction, "the 20th")
# are each preceded by one filler. 2 fillers dated before July 20 separate s06 from
# s07, where the vet reminder is due. s07-s08 (German) stay adjacent; 1 filler precedes
# the second role-play, 2 precede the party week (s10), 3 precede s11 and 1 separates
# s11 from the final pre-trip check s12, which returns to s01's goal time.
SESSIONS_LONG = (SESSIONS[:1] + FILLERS[:3] + SESSIONS[1:2] + FILLERS[3:5] + SESSIONS[2:3]
                 + FILLERS[5:9] + SESSIONS[3:4] + FILLERS[9:10] + SESSIONS[4:5]
                 + FILLERS[10:11] + SESSIONS[5:6] + FILLERS[11:13] + SESSIONS[6:8]
                 + FILLERS[13:14] + SESSIONS[8:9] + FILLERS[14:16] + SESSIONS[9:10]
                 + FILLERS[16:19] + SESSIONS[10:11] + FILLERS[19:] + SESSIONS[11:])
