"""Seed brain-c with 15 earlier synthetic conversations (75 user and 75 assistant messages) through the calls the
LoCoMo harness uses (host.message_record + host.deliver), then wait for embeddings. Three facts sit in the first three
conversations: a shellfish allergy (1), the niece's birthday (2), the bike's price (3). Fictional user: Dana."""
import json
import sys
import time
from pathlib import Path

from seed_users import U

from membrain import host

T = Path("$TRIAL")
C = [
    [  # 1 cooking, shellfish allergy
        ("I'm trying to cook more at home this year. Any easy weeknight dinners that aren't pasta again?",
         "A few that stay off the pasta rotation: sheet-pan chicken thighs with chickpeas and lemon, vegetable fried rice with leftover rice, black bean tacos with quick-pickled onions, or miso-glazed salmon with rice and greens. Each takes about thirty minutes and one or two pans, and most of them reheat well for lunch the next day."),
        ("Fish is fine but I have to be careful: I found out last spring that I'm allergic to shellfish. Shrimp and crab sent me to urgent care, so anything with shellfish is out.",
         "That's important, thanks for telling me. Finfish like salmon is usually a separate allergy, but cross-contact is a real risk in restaurants, and shellfish hides in fish sauces, some stocks, shrimp paste and oyster sauce, so labels are worth a second look."),
        ("Good point about oyster sauce, I hadn't thought of that. What's a substitute for stir fries?",
         "Mushroom-based 'vegetarian oyster sauce' is the closest swap: it's made from shiitake and has the same savoury depth. Hoisin thinned with a little soy sauce also works. A few brands still list oyster extract, so check the label."),
        ("Perfect. I'll grab some this weekend.",
         "Sounds good. An opened bottle keeps for months in the fridge, so it's an easy staple to have around."),
        ("Do you think I should carry an epinephrine pen?",
         "That's a question for your doctor or an allergist. After a reaction that needed urgent care many people are prescribed one, and an allergist can also test which shellfish you react to. It's worth asking at your next appointment."),
    ],
    [  # 2 niece's birthday
        ("My niece Priya turns seven on March 3rd and she's completely obsessed with octopuses right now. Gift ideas?",
         "Seven and octopus-mad is a fun brief. Ideas: a reversible octopus plush, a picture book about cephalopods, an ocean craft kit, a kids' marine biology activity book, or an experience such as an aquarium visit where she can see a real one."),
        ("An aquarium trip is a great idea. The one at Point Defiance has a giant Pacific octopus.",
         "That would be perfect. Feeding or talk times are often posted on the aquarium's site, so you could plan the visit around the octopus talk if they have one."),
        ("Should I get her something to unwrap too?",
         "A small wrapped item helps on the day itself. A book about octopuses or a printed 'ticket' for the aquarium trip inside a card both work, so she has something to open even if the trip is later."),
        ("Her mom, my sister Leena, says Priya already has too many plushies.",
         "Then skip the plush. A book plus the aquarium ticket keeps it clutter-free, and Leena will probably appreciate an experience gift."),
        ("Okay, the aquarium plus a book it is.",
         "Great plan. If you want, a short note in the card about what you'll look for at the aquarium together makes the unwrapping part feel special too."),
    ],
    [  # 3 the bike
        ("I finally bought a bike! A used green 2019 Trek FX 2. I paid $340 for it from a guy in Fircrest.",
         "Congratulations! That's a fair price for an FX 2 in decent condition. It's a comfortable hybrid for commuting and paved trails, and parts are easy to find."),
        ("What should I check first since it's used?",
         "Start with the brakes, tyre wear and pressure, and the chain. Spin each wheel to check that it runs true, squeeze the brakes hard, and shift through every gear. If anything feels off, a basic tune-up at a shop is usually worth it."),
        ("The chain looks a little rusty.",
         "Light surface rust usually cleans off: wipe it with a rag and degreaser, scrub with a brush, dry it, then apply chain lube and wipe off the excess. If the links are stiff or it skips under load, replace the chain."),
        ("Do I need a special lock?",
         "For street parking, a solid U-lock through the frame and rear wheel is the standard. Add a cable for the front wheel if it has a quick release. Cable locks alone are easy to cut."),
        ("Thanks, I'll get a U-lock.",
         "Good choice. Lock it to something solid and immovable, and register the serial number somewhere in case it ever goes missing."),
    ],
    [  # 4 Spanish
        ("I want to get back into Spanish. I took it in high school but forgot most of it.",
         "Coming back to a language is easier than starting fresh. A short daily habit beats long weekly sessions: fifteen minutes of an app or a graded reader, plus listening to slow Spanish podcasts on your commute."),
        ("Any podcast recommendations for that?",
         "Look for podcasts aimed at learners with slow, clear speech and transcripts. Many have episodes graded by level, so you can start with beginner stories and move up."),
        ("Should I focus on grammar or vocabulary first?",
         "Both, in small doses, but prioritise high-frequency vocabulary and the present tense so you can say useful things quickly. Grammar sticks better once you have words to hang it on."),
        ("How long until I can hold a basic conversation?",
         "With steady daily practice and some speaking time, many people manage simple conversations in three to six months. Speaking with a tutor or a language exchange partner speeds that up a lot."),
        ("Okay, I'll try fifteen minutes a day.",
         "Sounds like a good plan. Tie it to something you already do every day, like your morning coffee, so it becomes automatic."),
    ],
    [  # 5 volleyball
        ("I joined a Tuesday night rec volleyball league. I haven't played in years.",
         "That sounds fun. Rec leagues are usually relaxed about skill, and the first few weeks are mostly about getting your timing back."),
        ("My forearms are bruised from passing. Is that normal?",
         "Very normal at first, especially if you're passing with your arms slightly bent or hitting the ball on the wrists. Keep a flat platform with straight arms and contact the ball on the forearms; the bruising fades as technique improves."),
        ("Any tips for serving? Mine keep going into the net.",
         "Toss the ball a bit higher and in front of your hitting shoulder, keep your eyes on it, and follow through toward the target. An underhand serve is fine in rec play while you build consistency."),
        ("We lost all three sets but it was fun.",
         "That's the right attitude for a first night back. Most teams improve a lot over the first month as people learn each other's habits."),
        ("Should I stretch before playing?",
         "A short dynamic warm-up works better than static stretching before play: arm circles, leg swings, light jogging and a few easy passes. Save longer static stretches for afterwards."),
    ],
    [  # 6 work report
        ("I have to write a summary of our flood modelling results for the county board. They're not technical.",
         "For a non-technical board, lead with what the results mean for them: which areas are at risk, how often, and what decisions it informs. Put the methods in an appendix."),
        ("How do I explain a 100-year flood without people thinking it happens once a century?",
         "Describe it as a flood with a 1 percent chance of happening in any given year. You can add that over a 30-year mortgage, that's roughly a one-in-four chance of at least one such flood."),
        ("That mortgage framing is good. Should I include maps?",
         "Yes, maps are usually the most persuasive part. Keep them simple: a clear base map, the flood extent in one strong colour, and labelled landmarks people recognise."),
        ("How long should the summary be?",
         "Two pages is a good target for the main summary, with a one-paragraph overview at the top. Board members often read only the first page."),
        ("Thanks, that helps a lot.",
         "Glad it helps. If you'd like, I can review a draft structure once you have one."),
    ],
    [  # 7 houseplants
        ("My pothos has yellow leaves. What am I doing wrong?",
         "Yellowing on a pothos is most often overwatering. Let the top couple of inches of soil dry out between waterings and make sure the pot drains well."),
        ("It's in a pot without a drainage hole.",
         "That's likely the cause: water pools at the bottom and the roots rot. Repot it into a pot with a drainage hole, or use the decorative pot as a cover with a plastic nursery pot inside."),
        ("Should I cut off the yellow leaves?",
         "Yes, remove fully yellow leaves; they won't turn green again. Trimming them also lets the plant put energy into healthy growth."),
        ("It's near a north window. Is that enough light?",
         "Pothos tolerates low light, so a north window is fine, though growth will be slower and the variegation may fade a bit."),
        ("Great, I'll repot it this weekend.",
         "Good plan. Water it lightly after repotting, then wait until the top of the soil dries before the next watering."),
    ],
    [  # 8 Biscuit
        ("Biscuit, my corgi, keeps pulling on the leash. Any tips?",
         "Stop walking whenever the leash goes tight and only move forward when it's slack. Reward him with a treat at your side often in the first weeks. It takes patience, but corgis are smart and learn the rule quickly."),
        ("He's very food motivated.",
         "That helps a lot. Use small, soft treats you can give quickly, and keep them for walks so they stay special."),
        ("Should I use a harness instead of a collar?",
         "A front-clip harness often reduces pulling and takes pressure off the neck, which is good for long-backed breeds like corgis."),
        ("How long should our walks be?",
         "Most adult corgis do well with about an hour of activity a day, split into two or three walks, plus some play. Adjust for his age and weight."),
        ("Okay, I'll try the harness.",
         "Sounds good. Let him sniff it and reward him the first few times you put it on, so he associates it with good things."),
    ],
    [  # 9 budget
        ("I want to start a monthly budget. Where do I begin?",
         "Start by tracking what you actually spend for a month, then group it into fixed costs, variable needs and wants. That shows where the money goes before you set targets."),
        ("Is the 50/30/20 rule realistic?",
         "It's a useful starting point: half to needs, about a third to wants, a fifth to savings and debt. In high-rent areas needs often take more than half, so adjust it to your situation."),
        ("Should I use an app or a spreadsheet?",
         "Either works. Apps categorise automatically; a spreadsheet gives you full control and costs nothing. Pick the one you'll actually open every week."),
        ("What about an emergency fund?",
         "A common target is three to six months of essential expenses in a separate savings account. Start with a smaller goal, like one month, so it feels achievable."),
        ("Okay, I'll track this month first.",
         "That's the right first step. At the end of the month, look for one or two categories that surprised you."),
    ],
    [  # 10 podcasts and sleep
        ("I can't fall asleep lately. My mind keeps racing at night.",
         "That's common when a lot is going on. A consistent wind-down routine helps: dim lights, no work email an hour before bed, and writing down tomorrow's to-dos so they're out of your head."),
        ("I do look at my phone in bed a lot.",
         "Try leaving the phone to charge outside the bedroom or across the room. The light and the endless scrolling both keep the brain alert."),
        ("Is it bad to read in bed?",
         "Reading a paper book in dim light is usually fine and helps many people relax. If you find yourself lying awake for a long time, get up for a bit and come back when you feel sleepy."),
        ("What about melatonin?",
         "Some people find low-dose melatonin helpful for short periods, but it's worth checking with a doctor or pharmacist, especially if you take other medications."),
        ("I'll try the phone-outside-the-room thing.",
         "Good plan. Give it a week or two before judging; sleep habits take a little while to shift."),
    ],
    [  # 11 Theo's birthday
        ("Theo's birthday is coming up. He's my partner. I want to plan something low-key.",
         "Low-key can be the best kind. A favourite home-cooked meal, a small hike he likes, or an evening built around one of his hobbies tends to mean more than something elaborate."),
        ("He loves board games and Thai food.",
         "Then a Thai takeout feast and a new board game you can play together that night would be a lovely evening. You could invite a couple of close friends for a game night if he likes company."),
        ("Any board game recommendations for two players?",
         "Popular two-player picks include cooperative puzzle games and quick card games. Look for ones with short play times so you can play several rounds."),
        ("He already has a lot of games though.",
         "Then an experience might be better: a board game café visit, or a nice set of card sleeves and an organiser for his collection."),
        ("Thanks, I'll think about it.",
         "Happy to help. Whatever you choose, a handwritten card usually makes it."),
    ],
    [  # 12 bike tune-up (distractor, no price)
        ("I took my bike in for a tune-up. They said the brake pads were worn.",
         "That's common on a used bike. New brake pads are inexpensive and make a big difference to stopping power, especially in the wet."),
        ("They also said I should get wider tyres for gravel.",
         "If you ride on gravel paths, slightly wider tyres with a bit of tread add comfort and grip. Check your frame's clearance first."),
        ("How often should I get it serviced?",
         "For regular riding, a basic service once or twice a year is typical, plus your own quick checks of tyres, brakes and chain every few weeks."),
        ("I rode 20 miles last weekend!",
         "Nice work, that's a solid ride. Remember to eat and drink on longer rides, even when it's cool."),
        ("I'm thinking about commuting by bike once a week.",
         "A great way to start. Plan a quiet route, get lights and fenders for the Northwest weather, and keep a change of clothes at work."),
    ],
    [  # 13 10K
        ("I signed up for a 10K in April. I've never run one.",
         "Congratulations on signing up! With a few months, a gradual plan of three runs a week will get you there comfortably."),
        ("How should I structure the weeks?",
         "Two easy runs and one slightly longer run each week, increasing the long run by about ten percent at a time. Add a rest day after the long run."),
        ("My knees ache a bit after running.",
         "Mild aches can come from increasing too quickly or worn shoes. Keep the easy runs truly easy, check your shoes, and see a physio if the pain is sharp or persistent."),
        ("What should I eat before a run?",
         "A small, easily digested snack an hour or so before, such as toast or a banana, works for most people. Avoid trying new foods on race day."),
        ("Alright, three runs a week starting Monday.",
         "Sounds like a plan. Log your runs; seeing the progress is great motivation."),
    ],
    [  # 14 heating bill
        ("My heating bill doubled this winter. Any ideas?",
         "Start with the cheap fixes: seal drafts around windows and doors, use thermal curtains at night, and lower the thermostat a couple of degrees when you're out or asleep."),
        ("We rent, so I can't change much.",
         "Renters can still use removable weatherstripping, draft stoppers, window insulation film and a programmable thermostat if the landlord allows it. Ask the landlord about any obvious leaks too."),
        ("Is a space heater cheaper?",
         "Heating only the room you're in with a space heater can be cheaper than heating the whole home, especially with electric baseboard heat. Use one with tip-over and overheat protection."),
        ("The windows are single pane.",
         "Insulation film on single-pane windows makes a noticeable difference and comes off cleanly in spring."),
        ("Okay, I'll try the window film.",
         "Good choice. Clean the glass first and use a hair dryer to tighten the film for a clear finish."),
    ],
    [  # 15 photography
        ("I got a used camera to take better photos on hikes.",
         "Nice! Hiking is a great way to learn because the light changes so much. Start with aperture priority mode and experiment from there."),
        ("What settings for waterfalls?",
         "For silky water, use a slow shutter speed of around half a second to a couple of seconds with a tripod. For crisp water, use a fast shutter speed."),
        ("I don't have a tripod yet.",
         "Brace the camera on a rock or your pack, and use the self-timer to avoid shake. A small travel tripod is a good next purchase."),
        ("How do I avoid blown-out skies?",
         "Expose for the sky and lift the shadows later, or shoot during softer light in the morning and evening. A graduated filter also helps."),
        ("Thanks! Going to Snoqualmie Falls next week.",
         "Enjoy it. Go early for softer light and fewer people, and bring a lens cloth for the spray."),
    ],
]


def main():
    directory = T / "brain-c"
    stored = 0
    with host.ready_client(directory) as client:
        for number, conversation in enumerate(C, 1):
            session = f"seed-dana-{number:02d}"
            for turn, (_short, assistant) in enumerate(conversation, 1):
                user = U[number - 1][turn - 1]
                turn_id = f"c{number:02d}t{turn}"
                stored += host.deliver(directory, client, host.message_record(session, "user", user, turn_id=turn_id))
                stored += host.deliver(directory, client, host.message_record(session, "assistant", assistant,
                                                                              turn_id=turn_id))
    print("stored", stored, "user characters", sum(len(u) for c in U for u in c), "assistant characters", sum(len(a) for c in C for _, a in c))
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        with host.ready_client(directory) as client:
            status = client.dashboard()["status"]
        if status.get("pending_jobs") == 0 and status.get("index_lag", 0) == 0:
            print("embeddings done", json.dumps(status)[:400])
            return
        time.sleep(5)
    sys.exit(f"embeddings not done: {status}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "count":
        print(len(C), sum(len(c) for c in C) * 2, sum(len(u) + len(a) for c in C for u, a in c))
    else:
        main()
