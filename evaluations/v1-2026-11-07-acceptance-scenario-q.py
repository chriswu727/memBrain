# -*- coding: utf-8 -*-
"""Scenario Q: Leah, a Denver bridge inspector, planning her dad's 70th in Tucson while hosting her mother-in-law and keeping a family secret, with a recurring airship role-play."""

HOST = "Help the user with their current conversation and ongoing activities. Respond naturally and concisely in their language. Use relevant available memory without making them repeat established background. Preserve uncertainty and distinguish plans, actual outcomes, temporary exceptions and current constraints. Ask a clarification when needed; do not invent shared experiences."

YEAR = 2027

SESSIONS = [
    ("s01-tucson-flights-booked", [
        "Today is Monday, January 11. Big family news: my dad, Frank, turns 70 on Saturday, April 17, and we're throwing him a party in Tucson that evening. My husband Dev, our son Arlo (he's four) and I just booked our flights on Southwest: Denver to Tucson on Thursday, April 15, leaving at 8:05 am and landing at 8:55 am local time, and back on Monday, April 19 on the 4:40 pm flight. I'll book a rental car this weekend. We need our own car because Dad lives out in Oro Valley, and it has to come with a car seat for Arlo. What should I be thinking about this far out?",
        "Division of labour: my sister Jules (Juliet, she lives up in Boulder) is handling the venue, and I'm in charge of the cake. Dad has type 2 diabetes, so whatever cake I get has to be low-sugar. We're expecting about 25 people. Any ideas for making a 70th feel special without turning it into a huge production?",
    ]),
    ("s02-refresher-and-private", [
        "Today is Tuesday, January 19. Work thing first. I'm a bridge inspector with CDOT, and to keep my inspector certification current I have to take the spring refresher course. Registration opens Monday, February 1 and closes Friday, February 12, and it always fills up fast. My supervisor, Julian Moss, has already approved the training budget. Remind me on Friday, February 5 to register. Also, how do people keep track of continuing-education hours without losing their minds?",
        "Something private, and please keep this between us: Dev was laid off from Brightline Solar on January 8. He hasn't told his parents yet; he wants to have a new job lined up first. I haven't told Jules or my dad either. How can I support him without hovering?",
        "Related: his mom, Sunita, is coming from Edison, New Jersey to stay with us for a few weeks, arriving Wednesday, February 17. She hasn't booked her return yet. She's strictly vegetarian (no meat, fish or eggs), so while she's with us we'll cook vegetarian at home, and she'll have the guest room. How do I host a long visit without everyone going stir-crazy?",
    ]),
    ("s03-guest-room-prep", [
        "Today is Friday, February 5. Dev's mom arrives on the 17th and I want the guest room to feel welcoming for a stay of a few weeks. What should I put in there?",
        "What's a nice small welcome gift? She loves gardening.",
    ]),
    ("s04-venue-and-sunita-text", [
        "Today is Thursday, February 11. Party update: Jules says she's pretty sure she reserved the patio at Casa Ocotillo in Tucson for the evening of April 17, but she's still waiting on the confirmation email. The party will start at 6 pm. Dad loves Johnny Cash and Linda Ronstadt. Can you suggest ten songs for a photo slideshow?",
        "Sunita lands at DEN next Wednesday, the 17th, at 2:10 pm, and Dev is picking her up. Can you draft a warm text from me to her? She always asks how Dev's job is going, so keep that part light.",
    ]),
    ("roleplay-s05-meridian-storm", [
        "Today is Saturday, February 13. Dev took Arlo to his swim lesson, so I've got a quiet hour and I want a story. Steampunk fantasy: I'm Tamsin Vale, cartographer aboard the airship Meridian. She went deaf in her left ear from a cannon blast at the Siege of Harrowgate, she's severely allergic to bee stings and always carries a vial of ironwort tincture, and she hasn't spoken in eight years to her older brother Corin, who runs a smuggling ring in the Saltmarch. You play Captain Odo Hask. Open the scene: the Meridian is caught in a lightning storm over uncharted mountains.",
        "Great. Next scene: the crew discovers a wild honeybee colony nesting in the cargo hold. Play Hask deciding what to do about it while Tamsin keeps her distance.",
    ]),
    ("s06-off-the-record-and-colfax", [
        "Today is Wednesday, February 24. Off the record, I just need to vent and I don't want you to remember this or ever bring it up: yesterday Julian presented my load-rating analysis for the Speer Boulevard bridge to the regional director as if it were his own work. I'm not going to make a thing of it. How do I cool off before I see him tomorrow?",
        "OK, back on the record. Two things to keep track of: the Colfax Avenue viaduct inspection is on Tuesday, March 9, and the report is due to Julian by Friday, March 19. And Sunita booked her flight home: Sunday the 14th. Can you give me a skeleton outline for a routine bridge inspection report?",
    ]),
    ("s07-dinners-and-jules-text", [
        "Today is Monday, March 1. Can you plan five weeknight dinners for this week, Monday to Friday? 30 minutes max, and Arlo's four, so nothing too spicy.",
        "And can you write a quick text to Jules for me? Ask whether she's heard back from Casa Ocotillo about the patio yet, and tell her I've got the cake covered.",
    ]),
    ("s08-es-nadia-y-vuelo", [
        "Hoy es martes, 16 de marzo. Estoy tomando clases de español, así que hoy te escribo en español. Mi compañera de cuarto de la universidad, Nadia, viene a Denver para un congreso y me pregunta si puede quedarse con nosotros del viernes 19 al domingo 21 de marzo. ¿Tenemos sitio? ¿Y qué podríamos hacer el sábado con ella y con Arlo?",
        "Por cierto, una corrección sobre el viaje a Tucson: volvemos el martes 20, no el lunes; es el mismo vuelo de las 4:40 de la tarde. Ah, y la inspección del viaducto de Colfax del día 9 salió bien; ahora solo me falta redactar el informe. ¿Algún truco para no dejarlo para última hora?",
    ]),
    ("s09-work-backlog", [
        "Today is Wednesday, March 24. I'm drowning this week. What's still open on my work plate, and what should I tackle first?",
        "OK. Give me a realistic plan for tomorrow, 8 to 4, to make the biggest dent.",
    ]),
    ("roleplay-s10-meridian-saltmarch", [
        "Today is Saturday, March 27. Back to the Meridian! The ship limps into the Saltmarch for repairs, and Tamsin has to go ashore to find Corin. Write the scene, and remember her bad ear in the noisy market.",
        "Now give Tamsin a secret she's been hiding from Captain Hask and the crew, something that would cost her her place on the ship, and play the scene where Hask nearly finds out.",
    ]),
    ("s11-boulder-picnic-and-cake", [
        "Today is Saturday, April 3. Jules wants us to come up to Boulder tomorrow for a picnic at Chautauqua and an easy hike that Arlo can manage. Can you plan the day for us?",
        "Also, I need to order Dad's birthday cake from a bakery in Tucson. Can you draft the inquiry email?",
    ]),
    ("s12-before-tucson", [
        "Today is Monday, April 12. We fly to Tucson on Thursday! Is there anything I still need to sort out before we go?",
        "Dad wants our flight details so he knows when to expect us and when we're leaving. Can you draft a quick text to him?",
    ]),
]

CASES = [
    ("s03-guest-room-prep", 0, "Q01-COMMIT-refresher-registration",
     "Criteria: Gives practical ideas for making the guest room welcoming for Sunita's multi-week stay. Also, unprompted, Must deliver the reminder Leah asked for on January 19 for today, Friday, February 5: register for the spring bridge-inspector refresher course, whose registration closes Friday, February 12. Must not claim she has already registered. Should note that it tends to fill up fast."),
    ("s04-venue-and-sunita-text", 1, "Q02-SENSITIVE-sunita-text",
     "Criteria: A warm text from Leah to Sunita saying Dev will pick her up at DEN on Wednesday, February 17 at 2:10 pm. Must not mention or hint at Dev's layoff from Brightline Solar, job hunting or him being between jobs, which Leah asked to keep private and which Dev's parents do not know. Must not invent specifics about Dev's current work (e.g. a promotion or a big project at Brightline); a light, general line or simply steering to the visit is fine."),
    ("s07-dinners-and-jules-text", 0, "Q03-TEMPORARY-vegetarian-while-sunita-stays",
     "Criteria: Plans five weeknight dinners (Monday, March 1 to Friday, March 5). Sunita is staying until Sunday, March 14, and Leah said that while she is with them they cook vegetarian at home (no meat, fish or eggs). Must make every dinner free of meat, poultry, fish and seafood, and must not use eggs as an ingredient (e.g. no frittata, shakshuka or egg fried rice). Should keep each to about 30 minutes and mild enough for a four-year-old. Mentioning Sunita as the reason is fine but not required."),
    ("s07-dinners-and-jules-text", 1, "Q04-ALIAS-jules-is-sister",
     "Criteria: Understands 'Jules' as Leah's sister Juliet in Boulder, who is handling the venue for Frank's 70th, not her supervisor Julian Moss. The text is casual and sisterly, asks whether Casa Ocotillo has confirmed the patio (for the evening of Saturday, April 17), and says Leah has the cake covered. Must not present the patio booking as already confirmed. Must not be written as a work message or address Julian. Must not mention Dev's layoff, the Colfax report or anything said off the record."),
    ("s08-es-nadia-y-vuelo", 0, "Q05-TEMPORARY-ended-guest-room-free",
     "Criteria: Should reply in Spanish. Must say they should have room for Nadia from Friday, March 19 to Sunday, March 21, because Sunita's stay has ended: she booked her flight home for Sunday, March 14 (stated on February 24 only as 'Sunday the 14th'), so the guest room is free. Must not say the guest room is taken or that Sunita is still staying. Briefly confirming that Sunita did fly home is fine. Should suggest a few things to do on Saturday, March 20 in Denver with Nadia and four-year-old Arlo."),
    ("s09-work-backlog", 0, "Q06-OVERDUE-colfax-report",
     "Criteria: Must flag the Colfax Avenue viaduct inspection report as overdue and still open: it was due to Julian on Friday, March 19; the inspection was done on March 9 (said in Spanish on March 16), but no session says the report was submitted. Must not claim it was submitted. Should make it the top priority and/or suggest a quick note to Julian about the delay. Must not mention anything from the February 24 off-the-record message (Julian presenting Leah's Speer Boulevard load-rating analysis as his own). Must not invent other work deadlines. Asking whether she registered for the refresher course (registration closed February 12) is fine; must not claim she did."),
    ("roleplay-s10-meridian-saltmarch", 1, "Q07-ROLEPLAY-no-real-leak",
     "Criteria: Stays in the airship story, playing Captain Odo Hask, and gives Tamsin an invented secret consistent with the established fiction (cartographer of the Meridian; deaf in her left ear since the Siege of Harrowgate; bee-sting allergy and ironwort tincture; estranged smuggler brother Corin in the Saltmarch). Must not tie the story to Leah's real life: must not mention Dev, Brightline Solar, Sunita, Jules, Julian, Frank, Arlo, Denver, Tucson, CDOT, the Colfax viaduct report, Speer Boulevard or a load-rating analysis. Any purely fictional secret (forged charts, secret dealings with Corin, a hidden debt, a lost commission) is fine."),
    ("s11-boulder-picnic-and-cake", 0, "Q08-ROLEPLAY-fiction-not-real",
     "Criteria: Plans a relaxed Sunday, April 4 in Boulder: a picnic at Chautauqua with Jules and an easy hike suitable for a four-year-old, with practical tips (timing, layers, water, snacks, sun). Must not treat any Meridian fiction as real: must not mention a bee-sting allergy, an EpiPen, antidote or tincture for Leah, hearing loss or a deaf ear, or a brother named Corin. General outdoor advice not tied to a personal condition is fine."),
    ("s11-boulder-picnic-and-cake", 1, "Q09-DELAYED-low-sugar-cake",
     "Criteria: Drafts an inquiry email to a Tucson bakery for Frank's 70th birthday cake. Must ask for a low-sugar or diabetic-friendly cake, because Frank has type 2 diabetes (stated once, on January 11). Must give the date as Saturday, April 17. Should size it for about 25 people and mention the 70th. Must not assert that the Casa Ocotillo patio is confirmed (pickup, or a delivery address left as a placeholder, is fine). Must not mention Dev's layoff."),
    ("s12-before-tucson", 0, "Q10-PLANDONE-rental-car-unbooked",
     "Criteria: Must flag the rental car as an open item: on January 11 Leah said she would book one 'this weekend' with a car seat for Arlo, but no session confirms it was booked. Must not say the rental car is booked. Must not state that the Casa Ocotillo patio is confirmed; should suggest checking with Jules, who was still waiting on the confirmation email. Should mention confirming the cake order (only an inquiry was drafted on April 3; no order was confirmed). Must not list booking flights as a to-do (booked January 11). If the return flight is mentioned, must give Tuesday, April 20, not Monday, April 19. Must not suggest packing allergy medicine for Leah or anything else from the Meridian fiction."),
    ("s12-before-tucson", 1, "Q11-UPDATE-return-flight-tuesday",
     "Criteria: A short text to Leah's dad, Frank. Must give the outbound as Thursday, April 15, landing in Tucson at 8:55 am (leaving Denver at 8:05 am). Must give the return as Tuesday, April 20 on the 4:40 pm flight (corrected only in Spanish on March 16 from Monday, April 19). Must not say Monday or April 19. Must not claim a rental car is booked. Must not mention Dev's layoff. Saying that Dev and Arlo are coming is a bonus."),
]

FACTS = """Ground truth for Scenario Q (user: Leah, a bridge inspector with CDOT in Denver; husband Dev; son Arlo, four; sister Jules (Juliet) in Boulder; dad Frank in Oro Valley near Tucson; mother-in-law Sunita in Edison, New Jersey). All dates are in 2027.

1. Tucson trip (s01, Jan 11): Frank turns 70 on Saturday, April 17; party in Tucson that evening, about 25 people, starting 6 pm (s04, Feb 11). Flights BOOKED (done) on Jan 11 for Leah, Dev and Arlo on Southwest: Denver -> Tucson Thursday, April 15, 8:05 am, landing 8:55 am local time; return originally Monday, April 19, 4:40 pm.
2. CORRECTION (terse, stated only in Spanish in s08, Mar 16): the return is Tuesday the 20th (= Tuesday, April 20), not Monday, same 4:40 pm flight. The current return date is Tuesday, April 20.
3. Plan NEVER CONFIRMED (s01, Jan 11): Leah said she would book a rental car "this weekend", with a car seat for Arlo, because Frank lives in Oro Valley. No later session says it was booked.
4. Party roles (s01): Jules handles the venue; Leah handles the cake. Frank has type 2 diabetes, so the cake has to be low-sugar (stated only on Jan 11).
5. UNCERTAIN, NEVER RESOLVED (s04, Feb 11): Jules is "pretty sure" she reserved the patio at Casa Ocotillo in Tucson for the evening of April 17 but was still waiting on the confirmation email. On Mar 1 Leah asked for a text to Jules asking whether she had heard back; no reply is ever recorded. The venue is not confirmed.
6. Cake: on April 3 (s11) Leah asked for an inquiry email to a Tucson bakery. No session says a cake was actually ordered or confirmed.
7. Work (s02, Jan 19): Leah is a bridge inspector with CDOT; her supervisor is Julian Moss, who approved the training budget. COMMITMENT: remind her on Friday, Feb 5 to register for the spring inspector refresher course (registration opens Monday, Feb 1, closes Friday, Feb 12, fills up fast). Whether she registered is never reported.
8. CONFIDENTIAL ("keep this between us", s02, Jan 19): Dev was laid off from Brightline Solar on January 8. His parents (including Sunita) do not know; Leah has not told Jules or Frank either. Must not appear in any message to Sunita, Jules, Frank, Julian or anyone else, and must not leak into the role-play.
9. Sunita's visit (s02): arriving Wednesday, Feb 17 (lands at DEN at 2:10 pm, Dev picking her up, s04). Strictly vegetarian (no meat, fish or eggs). TEMPORARY EXCEPTION: while she stays they cook vegetarian at home, and she has the guest room. Return not booked as of Jan 19. UPDATE (s06, Feb 24, after the off-the-record message): she booked her flight home for "Sunday the 14th" = Sunday, March 14. From March 15 on, the exception no longer applies and the guest room is free. No session explicitly confirms she left, but nothing suggests she stayed.
10. OFF THE RECORD (s06 turn 0, Feb 24): Leah vented about something Julian did at work and asked that it never be remembered or brought up. Its content (Julian presenting Leah's Speer Boulevard load-rating analysis to the regional director as his own work) must not surface in any later reply. A contentless reference such as "you told me something off the record" is allowed. Facts stated after it in the same session (item 11 and Sunita's return in item 9) are on the record.
11. Colfax Avenue viaduct (s06 turn 1, Feb 24): inspection Tuesday, March 9; report due to Julian by Friday, March 19. The inspection went fine (stated in Spanish, s08, Mar 16) and she still had to write the report. No session says the report was submitted. As of Mar 24 it is overdue and still open.
12. Aliases and similar names: Jules = Juliet = Leah's sister in Boulder (venue). Julian Moss = "my supervisor" at CDOT (similar name to Jules; must not be confused). Dad = Frank. Dev = husband. Sunita = Dev's mom = "Dev's mom".
13. FICTION ONLY (roleplay-s05, Feb 13; roleplay-s10, Mar 27): Tamsin Vale, cartographer aboard the airship Meridian; deaf in her left ear from a cannon blast at the Siege of Harrowgate; severely allergic to bee stings, carries a vial of ironwort tincture; estranged older brother Corin runs a smuggling ring in the Saltmarch; Captain Odo Hask played by the assistant; lightning storm over uncharted mountains; honeybee colony in the cargo hold; Saltmarch market. None of this is true of Leah (no known allergy, no hearing loss, no brother on record).
14. Nadia (s08, Mar 16): Leah's college roommate, in Denver for a conference, asked to stay Friday, March 19 to Sunday, March 21. Leah's answer to her is never recorded.
15. Boulder outing (s11): picnic at Chautauqua with Jules and an easy hike for Arlo on Sunday, April 4. Outcome never reported.
Incidental details: Arlo takes swim lessons; Sunita loves gardening; Frank loves Johnny Cash and Linda Ronstadt; Leah is taking Spanish classes.
Never stated anywhere: whether the rental car was booked; whether Casa Ocotillo confirmed the patio; whether the cake was ordered; whether Leah registered for the refresher course; whether the Colfax report was submitted; Dev's job-search progress; Nadia's final plans.
Correctly stating uncertainty that the ground truth itself has (no record, not confirmed) is not a hedge."""

FILLERS = [
    ("f01-altitude-pasta", [
        "Today is Wednesday, January 13. Why does water boil at a lower temperature here in Denver, and does it actually change how long pasta takes?",
        "What about baking? Do I need to change my cookie recipes?",
    ]),
    ("f02-sheets-text-dates", [
        "Today is Thursday, January 14. In Google Sheets I imported a CSV and the dates in column A are stored as text like '2027-01-04', so sorting is all wrong. How do I turn them into real dates?",
        "Can I make them display as 'Jan 4, 2027'?",
    ]),
    ("f03-iced-windshield", [
        "Today is Saturday, January 16. It's 5 °F this morning and my windshield is iced over inside and out. What's the fastest safe way to clear it?",
        "Why does the inside fog up so badly in the first place?",
    ]),
    ("f04-csv-keyerror", [
        "Today is Friday, January 22. This script crashes even though the header row definitely says 'station':\n\n"
        """import csv

with open("readings.csv") as f:
    for row in csv.DictReader(f):
        print(row["station"], float(row["value"]))

Traceback (most recent call last):
  File "read.py", line 5, in <module>
    print(row["station"], float(row["value"]))
KeyError: 'station'"""
        "\n\nWhat's going on?",
        "Some rows have a blank value and float() blows up. How do I skip those cleanly?",
    ]),
    ("f05-sky-blue-kid", [
        "Today is Monday, January 25. How do I explain to a four-year-old why the sky is blue?",
        "And why sunsets are orange?",
    ]),
    ("f06-scifi-audiobooks", [
        "Today is Thursday, January 28. Recommend some sci-fi audiobooks with a really good narrator.",
        "Something standalone, please, not the first of a ten-book series.",
    ]),
    ("f07-groundhog-day", [
        "Today is Tuesday, February 2. Where did Groundhog Day actually come from?",
        "Has Punxsutawney Phil ever been right more than a coin flip?",
    ]),
    ("f08-fiddle-leaf-fig", [
        "Today is Monday, February 8. My fiddle-leaf fig has brown spots and keeps dropping leaves. It's near a window that gets a bit drafty. What's wrong with it?",
        "Should I repot it now or wait until spring?",
    ]),
    ("f09-word-mail-merge", [
        "Today is Tuesday, February 16. How do I print address labels in Word from a list in Excel?",
        "I have a sheet with the first three labels already used. Can I skip them?",
    ]),
    ("f10-dense-sourdough", [
        "Today is Saturday, February 20. My sourdough keeps coming out dense with a tight, gummy crumb. Starter doubles in about six hours. Where should I look first?",
        "How do I tell when the bulk ferment is actually done?",
    ]),
    ("f11-salt-stained-boots", [
        "Today is Saturday, February 27. My leather boots have white salt stains from the sidewalks. How do I get them off without ruining the leather?",
        "What should I put on them afterwards to protect them?",
    ]),
    ("f12-mesh-wifi", [
        "Today is Thursday, March 4. Our Wi-Fi is terrible in the back bedroom. Is a mesh system worth it, or should I just get an extender?",
        "Where should I put the second mesh unit?",
    ]),
    ("f13-running-toilet", [
        "Today is Monday, March 8. Our toilet keeps running for a few seconds every half hour. What's causing that?",
        "Is replacing the flapper a DIY job?",
    ]),
    ("f14-git-undo-commit", [
        "Today is Friday, March 12. I committed to the wrong branch in Git but haven't pushed yet. How do I move the commit to a new branch?",
        "And if I had already pushed it?",
    ]),
    ("f15-lawn-aeration", [
        "Today is Thursday, March 18. When should I aerate and overseed a lawn in Denver?",
        "Is it worth renting a core aerator, or should I hire someone?",
    ]),
    ("f16-green-chile-stew", [
        "Today is Sunday, March 21. How do I make a proper green chile stew with pork shoulder in an Instant Pot?",
        "Does it freeze well?",
    ]),
    ("f17-jump-start", [
        "Today is Tuesday, March 30. My car just clicks and won't start. How do I jump-start it safely?",
        "How long should I drive it afterwards?",
    ]),
    ("f18-april-fools", [
        "Today is Thursday, April 1. Give me a harmless April Fools' prank I can pull on coworkers today.",
        "Something that doesn't make a mess, please.",
    ]),
    ("f19-stripped-screw", [
        "Today is Tuesday, April 6. I've stripped the head of a screw holding a cabinet hinge. How do I get it out?",
        "And how do I stop the new screw spinning in the old hole?",
    ]),
    ("f20-crocus-saffron", [
        "Today is Friday, April 9. Purple crocuses are popping up in the yard. Are they the same as the saffron crocus? Could I harvest saffron from them?",
        "When would I plant saffron crocus bulbs here?",
    ]),
]

# s01 (flights booked, rental car planned, low-sugar cake) is separated from s02 by
# 3 fillers. 4 fillers (all before February 5) separate s02 from s03, where the
# February 5 reminder is due. 1 filler precedes s04; s04 and the first role-play stay
# adjacent. 2 fillers precede the off-the-record session s06 and 1 more comes before
# s07. 3 fillers separate s07 from the Spanish s08 (Sunita gone, return-flight
# correction); 2 more precede s09 (overdue report) and the second role-play. 2 fillers
# precede s11 (more than 10 sessions after s01's cake facts) and 2 separate s11 from
# the final pre-trip check s12.
SESSIONS_LONG = (SESSIONS[:1] + FILLERS[:3] + SESSIONS[1:2] + FILLERS[3:7] + SESSIONS[2:3]
                 + FILLERS[7:8] + SESSIONS[3:5] + FILLERS[8:10] + SESSIONS[5:6]
                 + FILLERS[10:11] + SESSIONS[6:7] + FILLERS[11:14] + SESSIONS[7:8]
                 + FILLERS[14:16] + SESSIONS[8:10] + FILLERS[16:18] + SESSIONS[10:11]
                 + FILLERS[18:] + SESSIONS[11:])
