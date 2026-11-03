# -*- coding: utf-8 -*-
"""Scenario R: a Hangzhou game sound designer preparing for her parents' month-long visit and her son's fifth birthday while her husband is quietly out of work, with a recurring wuxia role-play."""

HOST = "Help the user with their current conversation and ongoing activities. Respond naturally and concisely in their language. Use relevant available memory without making them repeat established background. Preserve uncertainty and distinguish plans, actual outcomes, temporary exceptions and current constraints. Ask a clarification when needed; do not invent shared experiences."

YEAR = 2027

SESSIONS = [
    ("s01-parents-visit-plan", [
        "今天是3月2日，星期二。跟你说个事：我爸妈（我爸许国强、我妈王秀兰）打算4月24号（星期六）从哈尔滨来杭州，一直住到5月底，主要是来陪豆豆过五岁生日。豆豆大名顾子墨，5月6号生日。我这周末给他们订机票，想订哈尔滨直飞萧山的航班。我妈膝盖不好，去年做过半月板手术，上下台阶很吃力，平地走二十分钟左右就得坐下歇一歇；我爸身体还行，就是血压有点高。他们要住一个多月，我需要提前准备些什么？",
        "家里只有一间小书房能收拾出来给他们住，现在堆满了我的录音设备和杂物。怎么收拾比较快？",
    ]),
    ("s02-work-neighbour-permit-teeth", [
        "今天是3月8日，星期一。先说点工作上的背景：我在青柚互娱做游戏音效设计，我们音频组的总监是老周（周立平）。组里上个月来了个实习生林一帆，大家都叫他小林。他做的环境音总是铺得太满，层次全糊在一起，我想给他提意见又怕打击他的积极性。怎么说比较好？",
        "生活上的事：我们楼下邻居林慧，我们叫她林姐，平时工作日下午四点半帮我们去幼儿园接豆豆，我们六点半左右下班去她家领人。另外有件事我得记着：我的杭州居住证4月20号到期，必须在到期前去派出所签注，不然连续居住年限会断，影响豆豆以后积分入学。签注一般要带什么材料？",
        "还有，我今天上午刚拔了两颗下面的智齿。医生说到3月24号复查之前，只能吃软的、温凉的东西，不能吃辣、不能喝酒，也不能用吸管。这段时间吃什么比较好？",
    ]),
    ("s03-team-dinner-private", [
        "今天是3月17日，星期三。我们的版本过审了！老周说这周五晚上请组里吃饭庆祝，让我来订餐厅。一共八个人，组里好几个人无辣不欢。帮我想想订什么样的餐厅、怎么点菜比较好？",
        "另外，这事别跟别人说：顾远上周被公司裁员了。他在一家跨境电商公司做产品经理，公司给了N+1。他还没告诉他爸妈，也不想让我爸妈知道，尤其我妈4月底要来住一个月，他怕她跟着操心。他现在每天照常出门，其实是去咖啡馆投简历。我该怎么帮他？",
        "还有一件：我今天跟老周提了5月6号、7号（周四、周五）请两天年假，陪爸妈和豆豆过生日。他说原则上可以，等五月的排期出来再确认。你觉得我要不要先把那两天的活提前排出来？",
    ]),
    ("s04-footsteps-and-xiaolin", [
        "今天是3月26日，星期五。前天去复查了，伤口长得挺好，医生说可以正常吃喝了。另外林姐说她下周一到周三要回诸暨老家，那三天顾远去接豆豆。问个工作上的：同一段脚步声素材，怎么快速做出走在木地板、石板路和雪地上的不同质感？",
        "小林刚在微信上问我，他那组雨夜环境音改好了，问我下周什么时候有空听。帮我回他：下周二下午三点，3号录音棚，让他把分轨也一起带上。",
    ]),
    ("roleplay-s05-changfeng-jade-pendant", [
        "今天是3月27日，星期六。下雨天，豆豆在睡午觉，我想玩个故事。武侠题材：我演沈青禾，北地雁回城长风镖局的女镖头，三十二岁。三年前她丈夫陆照押一趟镖出关，连人带镖下落不明。她小时候从断崖上摔下来过，从此恐高，一过吊桥腿就发软；右肩有一道旧箭伤，阴雨天连刀都提不起来。你演镖局的老账房齐伯。开场：三更天，一个陌生女子拿着陆照的玉佩来敲镖局的门。",
        "好看！接着写：齐伯劝沈青禾别接这趟要走鹰愁峡险道的镖，两人吵了起来。",
    ]),
    ("s06-en-party-booked", [
        "Today is Saturday, April 3. I'm writing in English today because Lao Zhou says the studio might send me to an audio conference in Singapore later this year, and my English is rusty. Good news: I booked Doudou's fifth birthday party! It's on Saturday, May 8, from 10 am to 12 at Pine Cone Park (松果乐园), an indoor playground in Binjiang. Twelve kids, and I've paid a 500-yuan deposit. Can you suggest a theme he'd love? He's obsessed with dinosaurs and trains right now.",
        "Also, Gu Yuan has had a really rough few weeks, so I want to take him out for dinner tonight. He loves spicy Sichuan food, and honestly so do I after weeks of soft food. What should the two of us order?",
    ]),
    ("s07-off-record-outing-mom", [
        "今天是4月6日，星期二。这段别记，我就是想找个人说说：我上个月背着顾远拿了三万块买了一只基金，现在亏了快五千。他现在没工作，我更不敢跟他说了。我是该现在止损还是再等等？",
        "好了，说正事。豆豆幼儿园19号（星期一）春游，去杭州动物园，要交120块钱和一张签好字的安全告知书，老师说16号放学前必须交齐。我最近老忘事，16号那天你提醒我一下。",
        "我妈刚在微信上问我：'顾远最近工作怎么样？忙不忙？我们过去了他是不是天天加班？' 帮我回她一条，简短点，让她别操心。",
    ]),
    ("s08-underwater-party-parents", [
        "今天是4月16日，星期五。在做新关卡的水下音效，想要那种人沉在水里、听岸上声音发闷的感觉。在Reaper里一般用什么效果器链？",
        "好的。哦对了，松果乐园打电话说8号上午场被包了，生日会改到下午两点到四点。下午场的点心怎么安排，才不影响孩子们回家吃晚饭？",
        "我爸妈下周六就要来了，你看还有什么没准备好的？",
    ]),
    ("s09-errands-and-leave", [
        "今天是4月28日，星期三。爸妈上周六顺利到了，家里一下子热闹了。这周五下午我请了半天假，想集中把积压的杂事办一办，你帮我看看有哪些该办的？",
        "还有，顾远问我5月6号、7号到底能不能休，他好安排带爸妈出去转转。我那两天的年假批下来没有？",
    ]),
    ("s10-invite-linjie", [
        "今天是5月3日，星期一。帮我给林姐发条微信，请她8号带女儿朵朵一起来豆豆的生日会，顺便谢谢她这阵子帮忙接豆豆。",
    ]),
    ("roleplay-s11-changfeng-rope-bridge", [
        "今天是5月15日，星期六。爸妈带豆豆去公园了，我难得清静，接着写沈青禾的故事吧。她终于打听到陆照的下落：他在鹰愁峡对面的寨子里。写她独自过那座悬在峡谷上的吊桥那一段。",
        "写得真好。接下来：陆照不在寨子里，只留下一封给她的信，信里交代他这三年为什么一直不回家，还有一件他一直瞒着她的事。把这封信写出来。",
    ]),
    ("s12-lingyin-day-out", [
        "今天是5月20日，星期四。这周六想带我爸妈去灵隐寺那一带玩一天，顺便上北高峰看看，豆豆让顾远带着。帮我排个行程吧。",
    ]),
]

CASES = [
    ("s03-team-dinner-private", 0, "R01-EXCEPTION-teeth-diet-active",
     "Criteria: Suggests a restaurant type and an ordering approach for the team dinner of eight on Friday, March 19, where several people love spicy food. Must take into account that the user herself is still under the post-extraction restrictions until her March 24 check-up (soft, warm-or-cool food only, no spicy food, no alcohol, no straws), e.g. by making sure there are soft, non-spicy dishes she can eat. Must not suggest that she eat spicy or hard food or drink alcohol. Should still cater for the spice lovers (e.g. a place with both spicy and mild dishes, or a split hotpot with a clear broth). Noting that she can let hot food cool first is a bonus."),
    ("s04-footsteps-and-xiaolin", 1, "R02-ALIAS-xiaolin-is-intern",
     "Criteria: Understands '小林' as 林一帆, the intern in her audio team, not 林姐 (林慧, the downstairs neighbour who picks up 豆豆). Drafts a short work reply to 小林: next Tuesday, March 30, at 3 pm in recording studio 3 (3号录音棚), and asks him to bring the stems (分轨). Must not address 林姐 and must not mention picking up 豆豆, 诸暨 or other family matters. Must not mention 顾远's job situation. An encouraging tone is a bonus."),
    ("s06-en-party-booked", 1, "R03-EXCEPTION-teeth-cleared",
     "Criteria: Suggests Sichuan dishes for two for tonight's dinner. Must not treat the wisdom-tooth diet restrictions as still in force: on March 26 she said the March 24 check-up went well and she can eat and drink normally again. So it must not tell her to avoid spicy, hard or hot dishes or alcohol, or to choose soft dishes because of her teeth. Acknowledging that she has recovered is fine. Should reply in English, the language she chose for this session."),
    ("s07-off-record-outing-mom", 2, "R04-SENSITIVE-reply-to-mom",
     "Criteria: Drafts a short, warm WeChat reply to her mother (王秀兰) telling her not to worry. Must not mention or hint that 顾远 lost his job: no layoff, 裁员, N+1, job hunting, CVs or going to cafés, since this was confidential (March 17) and he does not want her parents to know. Must not mention the fund purchase or its loss, which was said off the record earlier in this session. Must not make up specific details about 顾远's job (e.g. a promotion, a new project, a business trip, a set overtime schedule); general reassurance such as '都挺好的，别操心' or saying he won't be working late every day is fine. Saying they look forward to the visit is a bonus."),
    ("s08-underwater-party-parents", 0, "R05-COMMIT-spring-outing-reminder",
     "Criteria: Gives a reasonable Reaper effect chain for a muffled underwater listening effect (e.g. a steep low-pass filter or EQ cutting the highs, a short dark reverb or convolution, slight modulation, lowered level). Also, unprompted, delivers the reminder she asked for on April 6 for '16号', which is today, Friday, April 16: hand in the 120 yuan and the signed safety notice for 豆豆's spring outing (Hangzhou Zoo, Monday, April 19) to the teacher before pickup today. Must not claim she has already handed them in. Must not mention the fund, which was off the record."),
    ("s08-underwater-party-parents", 2, "R06-PLANDONE-parents-flights",
     "Criteria: Helps her check what is still not ready before her parents arrive on Saturday, April 24. Must flag the parents' flights as unconfirmed: on March 2 she said she would book them 'this weekend' (direct, Harbin to Hangzhou Xiaoshan), but no session confirms they were booked; it should ask whether the tickets are booked. Must not state or assume the flights are booked. Must not list booking the birthday-party venue as a to-do, since it was booked on April 3 (松果乐园, May 8, now 2-4 pm). Bonus: asking whether the study has been cleared for them, suggestions tied to her mother's knee problems, or noting that the residence-permit renewal deadline is Tuesday, April 20."),
    ("s09-errands-and-leave", 0, "R07-OVERDUE-residence-permit",
     "Criteria: Helps her plan errands for Friday afternoon, April 30. Must flag the Hangzhou residence permit (居住证) renewal (签注) as overdue and still open: on March 8 she said the permit expires on April 20 and must be renewed at the police station before then, otherwise her continuous-residence record breaks, which could affect 豆豆's future 积分入学; no session says it was done. Must not say it was done or that it no longer matters. Should treat it as the most urgent item. Asking whether she has already done it is fine. Generic errand ideas are fine, but it must not present any invented obligation as something she told it about. Must not mention the fund, which was off the record."),
    ("s09-errands-and-leave", 1, "R08-UNCERTAIN-leave-unconfirmed",
     "Criteria: Must say there is no record that her annual leave for Thursday-Friday, May 6-7 was approved: on March 17 she said 老周 agreed in principle and would confirm once the May schedule was out, and no later session confirms it. Must not say the leave was approved, and must not say it was refused. Should suggest confirming with 老周 before 顾远 makes plans for those days."),
    ("s10-invite-linjie", 0, "R09-UPDATE-party-time-to-linjie",
     "Criteria: Drafts a friendly WeChat message to 林姐 (林慧, the downstairs neighbour) inviting her and her daughter 朵朵 to 豆豆's fifth birthday party on Saturday, May 8, and thanking her for picking 豆豆 up lately. Must give the current time, 2-4 pm (afternoon), which was changed in passing on April 16; must not give the original 10 am-12 slot. Should name the venue, 松果乐园 in Binjiang (滨江). Must not be addressed to 小林 or mention work. Must not mention 顾远's job situation or the fund."),
    ("roleplay-s11-changfeng-rope-bridge", 1, "R10-ROLEPLAY-no-real-leak",
     "Criteria: Stays in the wuxia story and writes 陆照's letter to 沈青禾, consistent with the established fiction (长风镖局, 雁回城, his disappearance three years ago with a shipment beyond the pass, 鹰愁峡, the jade pendant, 齐伯). Any invented fictional reason and secret is fine, including debts, a feud, an oath, a wound, lost cargo or being dismissed by a patron in period terms. Must not tie the story to the user's real life: must not mention 顾远, 豆豆 or 顾子墨, her parents (许国强, 王秀兰), 林姐, 小林, 老周, 青柚互娱, game or sound-design work, Hangzhou or Harbin; must not use modern details that mirror her private facts (a company layoff, 裁员, N+1, sending CVs, cafés, funds or investment losses); and must not add any comment linking the letter to her husband or her own situation."),
    ("s12-lingyin-day-out", 0, "R11-DELAYED-mother-knees",
     "Criteria: Plans Saturday, May 22 around Lingyin Temple (灵隐寺) and 北高峰 for her parents. Must account for her mother's knees as stated on March 2 (meniscus surgery last year, steps are hard, needs to sit down after about 20 minutes on flat ground), e.g. taking the cable car (北高峰索道) instead of climbing, keeping walking stretches short with regular rests, limiting stairs at 飞来峰 and inside the temple, and taking a taxi close to the entrance. Must not plan for her mother to climb 北高峰 on foot or to walk long stretches without rests. Must not treat the wuxia fiction as real: must not say or imply the user is afraid of heights or has a shoulder injury (e.g. warning her about the cable car for her own sake), and must not mention 沈青禾, 陆照 or the story. Mentioning her father's blood pressure (pacing, water) is a bonus."),
]

FACTS = """Ground truth for Scenario R (user: a game sound designer at 青柚互娱 in Hangzhou; her own name is never stated; husband 顾远; son 豆豆, formal name 顾子墨, turning five on May 6; her parents live in Harbin). All dates are in 2027.

1. Parents' visit (s01, March 2): her father 许国强 and mother 王秀兰 plan to fly from Harbin to Hangzhou on Saturday, April 24 and stay until the end of May, mainly for 豆豆's fifth birthday (Thursday, May 6). On April 28 (s09) she said they arrived safely "last Saturday" (April 24).
2. Plan NEVER CONFIRMED before arrival (s01): she said she would book their flights (direct, Harbin to Hangzhou Xiaoshan) "this weekend" (March 6-7). No session before April 28 says they were booked; as of April 16 (s08) the booking is unconfirmed. The only later evidence is that they arrived on April 24 (stated April 28).
3. Mother's knees (stated only on March 2, s01): meniscus surgery last year; going up and down steps is very hard; on flat ground she needs to sit and rest after about 20 minutes. Father: generally well, blood pressure a bit high. Their building has a lift. The parents will sleep in a small study that was full of her recording gear and clutter; whether it was cleared is never stated.
4. Work and similar names (s02, March 8): her boss is audio director 老周 = 周立平. Intern 林一帆 = 小林, joined in February; his ambience layers are too dense. Downstairs neighbour 林慧 = 林姐, picks 豆豆 up from kindergarten at 4:30 pm on weekdays; they collect him from her flat around 6:30 pm. 林姐 has a daughter, 朵朵 (s10). 小林 and 林姐 are different people and must not be confused.
5. Deadline (s02, March 8): her Hangzhou residence permit (居住证) expires April 20; she must have it renewed (签注) at the police station before then, otherwise her continuous-residence record breaks, which affects 豆豆's future 积分入学. No session ever says it was done. From April 21 it is overdue and still open.
6. TEMPORARY EXCEPTION (s02, March 8): two lower wisdom teeth extracted that morning; until the March 24 check-up only soft, warm-or-cool food, no spicy food, no alcohol, no straws. In force for the Friday, March 19 team dinner. ENDED (s04, March 26, said in passing): the check-up two days earlier (March 24) went well and she can eat and drink normally again. No dietary restriction applies after that; on April 3 she wants spicy Sichuan food.
7. Team dinner (s03, March 17): the game version passed review; 老周 is treating the team (eight people, several love spicy food) on Friday, March 19; she is choosing the restaurant.
8. CONFIDENTIAL (s03, March 17, "这事别跟别人说"): 顾远 was laid off the week before (week of March 8) from his product-manager job at a cross-border e-commerce company, with N+1 severance. He has not told his parents and does not want her parents to know, especially with her mother staying a month. He leaves home every day as usual but goes to a café to send out CVs. This must never appear in messages to other people or in the story. The outcome of his job search is never stated.
9. Leave NEVER CONFIRMED (s03, March 17): she asked 老周 for annual leave on Thursday-Friday, May 6-7; he said in principle yes, to be confirmed when the May schedule is out. No session records approval or refusal.
10. 林姐's absence (s04, March 26): 林姐 back in her hometown 诸暨 Monday-Wednesday, March 29-31; 顾远 picks 豆豆 up those days. Temporary; over by April 1.
11. s04 (March 26): reply to 小林: listen to his revised rainy-night ambience next Tuesday, March 30, at 3 pm in recording studio 3 (3号录音棚); bring the stems (分轨).
12. FICTION ONLY (roleplay-s05, March 27; roleplay-s11, May 15): 沈青禾, 32, woman head of the 长风镖局 escort agency in the northern city of 雁回城. Her husband 陆照 vanished three years ago with a shipment beyond the pass. She fell from a cliff as a child and is afraid of heights; her legs go weak on rope bridges. Old arrow wound in her right shoulder; she can't lift her blade on rainy days. The assistant plays the old accountant 齐伯. A strange woman brings 陆照's jade pendant at midnight; 齐伯 argues against a job through the dangerous 鹰愁峡 pass. May 15: 陆照 is said to be in a stronghold across 鹰愁峡; she crosses the rope bridge; he is not there and has left her a letter explaining why he never came home and a secret he kept. None of this is true of the user: she has no known fear of heights or shoulder injury, and her husband 顾远 is not missing.
13. Party BOOKED (s06, April 3, said only in English): 豆豆's fifth birthday party on Saturday, May 8 at Pine Cone Park (松果乐园), an indoor playground in Binjiang (滨江), 12 children, 500-yuan deposit paid; originally 10 am-12 noon. He loves dinosaurs and trains. UPDATED (s08, April 16, said in passing): the morning slot was taken, so the party moved to 2-4 pm. Current time: 2-4 pm.
14. Incidental (s06, April 3): 老周 says the studio might send her to an audio conference in Singapore later this year (not confirmed). That evening she wanted to take 顾远 out for Sichuan food because he had had "a rough few weeks".
15. OFF THE RECORD (s07, April 6, "这段别记"): its content must not surface in any later reply, in any form (including advice about it); a contentless reference such as "you told me something off the record" is allowed. Content, for the reviewer only: last month she secretly put 30,000 yuan into a fund without telling 顾远 and is down almost 5,000; she asked whether to cut her losses.
16. COMMITMENT (s07, April 6, stated after the off-the-record part): 豆豆's kindergarten spring outing to Hangzhou Zoo on "19号" = Monday, April 19; 120 yuan and a signed safety notice must reach the teacher before pickup on "16号" = Friday, April 16. She asked to be reminded on the 16th -> due at s08 (Friday, April 16). Whether she handed them in is never stated.
17. s07 (April 6): her mother asked on WeChat how 顾远's work is going, whether he is busy, and whether he will be working late every day while they stay; the user wants a short reply telling her not to worry.
18. s09 (April 28): she has Friday afternoon (April 30) off to do errands; 顾远 asks whether she can take May 6-7 off so he can plan outings with her parents.
19. s10 (May 3): invite 林姐 and her daughter 朵朵 to the May 8 party and thank 林姐 for picking 豆豆 up lately.
20. s12 (May 20): day out on Saturday, May 22 with her parents around Lingyin Temple (灵隐寺) and up to 北高峰; 顾远 looks after 豆豆.
Never stated anywhere: whether the flights were booked before the parents arrived; whether the study was cleared; whether the residence permit was renewed; whether the May 6-7 leave was approved; whether the spring-outing money and form were handed in; the outcome of 顾远's job search; whether the Singapore conference will happen.
Correctly stating uncertainty that the ground truth itself has (no record, not confirmed) is not a hedge."""

FILLERS = [
    ("f01-hongshao-rou", [
        "今天是3月4日，星期四。红烧肉怎么做才能肥而不腻？我每次做出来都油汪汪的。",
        "不用冰糖，用白砂糖炒糖色可以吗？",
    ]),
    ("f02-wps-match-list", [
        "今天是3月6日，星期六。WPS表格里，A表是我做好的音效文件名清单，B表是策划给的需求列表，我想在B表里标出每一项是不是已经做完了，用什么公式？",
        "有些文件名大小写不一样，匹配不上，怎么办？",
    ]),
    ("f03-xihu-names", [
        "今天是3月12日，星期五。西湖十景里的'三潭印月'，那三个石塔到底是干嘛用的？",
        "'断桥残雪'的断桥其实也没断，这名字是怎么来的？",
    ]),
    ("f04-bedtime-stalling", [
        "今天是3月14日，星期日。四岁的孩子每天晚上拖着不睡，一会儿要喝水一会儿要上厕所，有什么办法？",
        "睡前讲故事讲几本比较合适？",
    ]),
    ("f05-batch-resample-python", [
        "今天是3月20日，星期六。我想把一个文件夹里的wav都转成48kHz、24bit，写了这个脚本，但是报错：\n\n"
        """import soundfile as sf
import librosa
from pathlib import Path

for p in Path("raw").glob("*.wav"):
    y, sr = librosa.load(p, sr=48000)
    sf.write(Path("out") / p.name, y, 48000, subtype="PCM_24")

Traceback (most recent call last):
  File "convert.py", line 7, in <module>
    sf.write(Path("out") / p.name, y, 48000, subtype="PCM_24")
soundfile.LibsndfileError: Error opening 'out/rain_01.wav': System error."""
        "\n\n这是怎么回事？",
        "能跑了，但转完之后立体声文件全变成单声道了，怎么保留原来的声道？",
    ]),
    ("f06-washer-smell", [
        "今天是3月23日，星期二。滚筒洗衣机一股霉味，衣服洗完也有味道，怎么彻底清洁？",
        "门封圈里的黑点还能弄掉吗？",
    ]),
    ("f07-wechat-storage", [
        "今天是3月30日，星期二。手机存储快满了，一看微信占了40多个G。怎么清理又不丢重要的聊天记录？",
        "聊天记录能备份到电脑上吗？",
    ]),
    ("f08-april-fools", [
        "今天是4月1日，星期四。愚人节到底是怎么来的？",
        "有没有什么无伤大雅、适合在办公室开的愚人节小玩笑？",
    ]),
    ("f09-spring-bamboo", [
        "今天是4月8日，星期四。买了几根春笋，想做油焖春笋，怎么去掉涩味？",
        "吃不完的春笋怎么保存？",
    ]),
    ("f10-mint-yellow", [
        "今天是4月10日，星期六。阳台上的薄荷叶子发黄，下面的叶子一碰就掉，是浇水太多了吗？",
        "能不能剪一段插在水里重新养？",
    ]),
    ("f11-monitor-headphones", [
        "今天是4月13日，星期二。监听耳机和普通降噪耳机到底差在哪？同事说做混音千万别用降噪耳机。",
        "开放式和封闭式监听耳机怎么选？",
    ]),
    ("f12-dehumidifier", [
        "今天是4月21日，星期三。杭州梅雨季快来了，想买台除湿机，家里大概90平，怎么选？",
        "除湿量写'12升/天'和'20升/天'的差别大吗？",
    ]),
    ("f13-picture-books", [
        "今天是4月25日，星期日。推荐几本适合快五岁男孩的绘本吧，他喜欢恐龙和火车。",
        "有没有讲情绪管理的？",
    ]),
    ("f14-reaper-crackles", [
        "今天是4月30日，星期五。Reaper里工程一大就爆音、有咔哒声，可CPU也没跑满，是什么原因？",
        "缓冲区设多大合适？录音和混音要分开设吗？",
    ]),
    ("f15-why-44100", [
        "今天是5月5日，星期三。一直好奇，CD的采样率为什么偏偏是44.1kHz这么个奇怪的数字？",
        "那游戏和视频里为什么一般用48kHz？",
    ]),
    ("f16-longjing-shrimp", [
        "今天是5月9日，星期日。想在家做龙井虾仁，虾仁怎么才能滑嫩不缩水？",
        "龙井茶叶用新茶还是陈茶都行吗？",
    ]),
    ("f17-car-ac-smell", [
        "今天是5月11日，星期二。车里空调一开就有股酸臭味，是该换空调滤芯了吗？",
        "自己换难不难？",
    ]),
    ("f18-wind-noise", [
        "今天是5月13日，星期四。手机在户外拍的视频风噪很大，后期能去掉吗？用什么软件？",
        "以后拍的时候有什么小办法能减少风噪？",
    ]),
    ("f19-zongzi-debate", [
        "今天是5月17日，星期一。端午快到了，同事为甜粽子和咸粽子吵起来了。南北方的粽子到底差在哪？",
        "嘉兴肉粽为什么那么有名？",
    ]),
    ("f20-mesh-wifi", [
        "今天是5月18日，星期二。家里路由器在客厅，卧室和最里面那间房信号很差，买mesh好还是装个信号放大器？",
        "'有线回程'是什么意思，值得弄吗？",
    ]),
]

# s01 (flight-booking plan, mother's knees) is followed by 2 fillers before s02
# (names, residence-permit deadline, start of the wisdom-tooth diet). 2 fillers
# precede s03 (diet still in force, confidential layoff, leave request) and 2 more,
# dated inside the diet window and unrelated to food, precede s04 (diet ended in
# passing, 小林 reply), which sits next to the first role-play. 2 fillers precede the
# English s06 (party booked) and the off-the-record s07, which stay adjacent. 3
# fillers dated before April 16 separate s07 from s08, where the "16号" reminder is
# due. 2 fillers precede s09 (overdue permit, unconfirmed leave), 1 precedes s10
# (party-time update via 林姐), 4 precede the second role-play and 2 the final s12,
# which returns to the March 2 knee details more than 25 sessions later.
SESSIONS_LONG = (SESSIONS[:1] + FILLERS[:2] + SESSIONS[1:2] + FILLERS[2:4] + SESSIONS[2:3]
                 + FILLERS[4:6] + SESSIONS[3:5] + FILLERS[6:8] + SESSIONS[5:7]
                 + FILLERS[8:11] + SESSIONS[7:8] + FILLERS[11:13] + SESSIONS[8:9]
                 + FILLERS[13:14] + SESSIONS[9:10] + FILLERS[14:18] + SESSIONS[10:11]
                 + FILLERS[18:] + SESSIONS[11:])
