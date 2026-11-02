# -*- coding: utf-8 -*-
"""Scenario G: Song Yue, a Hangzhou veterinarian, with a private thyroid biopsy, a five-year-old's kindergarten and swim-class logistics, a mother who never flies and a recurring wuxia role-play."""

HOST = "Help the user with their current conversation and ongoing activities. Respond naturally and concisely in their language. Use relevant available memory without making them repeat established background. Preserve uncertainty and distinguish plans, actual outcomes, temporary exceptions and current constraints. Ask a clarification when needed; do not invent shared experiences."

YEAR = 2027

SESSIONS = [
    ("s01-dali-and-mom", [
        "今天是9月5日，星期日。国庆我们一家三口要去大理！我、老公老林（林哲）和儿子豆豆（大名林一诺，五岁）。机票刚订好：10月2号（周六）杭州飞大理，10月6号（周三）飞回来。民宿我打算这几天在双廊那边挑一家订下来。带五岁小孩去大理，有什么要注意的？",
        "我妈知道了也想一起去，可是她从来不坐飞机。她有幽闭恐惧，一上飞机就会惊恐发作，这么多年出门都只坐高铁。从宁波坐火车去大理又太折腾了。我是独生女，我爸走得早，她一个人住在宁波，我怕她觉得被落下了。怎么跟她说比较好？",
    ]),
    ("s02-kindergarten-and-clinic", [
        "今天是9月14日，星期二。说说豆豆幼儿园的事。他今年上中班，班主任是周老师（周婷）。周老师今天在群里通知，10月30号（周六）上午8点半有亲子运动会，在幼儿园操场，爸爸妈妈至少来一个。豆豆每周六下午两点到三点半还在少年宫上美术班。这周六（18号）我打算带他去社区卫生服务中心打流感疫苗。五岁小孩打完流感疫苗要注意什么？",
        "工作上的事：我在安心宠物医院当兽医，周医生（周明）是医院合伙人，排班归他管。我的助理小林（林晓晴）特别能干，今年10月要考执业兽医资格证。我想帮她复习，有什么好办法？",
    ]),
    ("s03-biopsy-private-and-minsu", [
        "今天是9月21日，星期二。这件事只跟你说，别在任何地方提起：单位体检查出甲状腺结节，B超分级4a，医生建议做细针穿刺活检，约在10月12号（周二）上午，在浙一。只有老林知道。我不想让我妈知道，她会担心得整夜睡不着；医院这边我也不打算告诉周医生，就说请半天事假。穿刺前要做什么准备？",
        "说点开心的：大理的民宿订好了！双廊的“云栖海景小院”，10月2号到6号，有个能看洱海的露台。双廊附近有什么适合小孩玩的？",
    ]),
    ("roleplay-s04-shen-shuang", [
        "今天是9月25日，星期六。老林带豆豆回婆家了，我一个人在家，想玩个故事。来个武侠的：我是女侠沈霜，江南人。三年前她的左手手筋被血衣楼的人挑断了，只能用右手使剑。她怕狗，小时候被恶犬咬过，到现在听到狗叫还会发抖。她哥哥沈澜被血衣楼楼主所杀，她一路北上寻仇。你来演她在客栈遇到的江湖郎中白先生。开场：大雨夜，客栈里闯进来一群带刀的人。",
        "很好。给沈霜安排一个她瞒着所有人的秘密，让她显得更脆弱一点，然后写一场白先生差点识破的戏。",
    ]),
    ("s05-mom-visit-and-todos", [
        "今天是10月7日，星期四。大理回来了，豆豆晒黑了一圈。我妈刚发微信，说想11号到13号来杭州住几天，帮我带带豆豆。那几天不太方便，帮我回她一下，让她晚一个星期，16号周六再来，语气轻松点，别让她多想。",
        "还有两件事帮我记着。第一，社区通知豆豆2028年度的少儿医保要在11月30号之前缴，350块，在浙里办上就能交，我回头弄。第二，10月18号那天（周一）提醒我给豆豆报冬季游泳班，19号上午10点开抢，每次都是秒没。",
    ]),
    ("s06-post-op-note-and-car", [
        "今天是10月18日，星期一。帮我把这段术后护理说明改得通俗一点，给一只刚做完绝育的柯基的主人看：“术后24h内禁食禁水，后逐步恢复饮食；佩戴伊丽莎白圈10-14天；避免剧烈运动；观察切口有无红肿、渗出；术后第10-14天复诊拆线。”",
        "对了，运动会改到29号周五下午了。换个话题：老林想换车，平时就在杭州市区开，偶尔回宁波，纯电和插混哪个更合适？",
    ]),
    ("s07-swim-class-and-shift-swap", [
        "今天是10月25日，星期一。游泳班抢到了！每周六上午9点到10点，在黄龙体育中心，11月6号开始，一共10次。要给他准备些什么？另外老林说他11月可能要去成都出差一周，具体哪周还没定，说下周才知道。",
        "帮我给周医生发个微信，问问运动会那天下午能不能跟他换个班，我那天本来排的是下午班。",
    ]),
    ("s08-wisdom-tooth-and-art-class", [
        "今天是11月11日，星期四。今天上午把左下那颗阻生智齿拔了，缝了三针。医生说这一周只能吃软的、温凉的东西，不能吃辣，不能用吸管，下周四（18号）上午去拆线。麻药退了好疼，有什么办法缓解？",
        "对了，美术班退了，豆豆说什么都不肯去了。周六下午空出来了，杭州有什么适合五岁小孩的室内活动？",
    ]),
    ("s09-dinner-and-thursday", [
        "今天是11月15日，星期一。老林今晚加班，我想给自己做顿好吃的犒劳一下，推荐个晚饭吧，就我一个人吃。",
        "小林刚问我这周四（18号）晚上能不能留下来帮她做一台手术，可能要到八点多。豆豆四点半放学，老林那天在杭州吗？能去接他吗？",
    ]),
    ("roleplay-s10-shen-taihu-branch", [
        "今天是11月20日，星期六。接着上次沈霜的故事：她终于摸到了血衣楼在太湖边的分舵，门口拴着两条大狼狗。写她怎么潜进去。",
    ]),
    ("s11-flu-adoption-day-birthday", [
        "今天是11月26日，星期五。周老师在班级群里说，班上好几个小朋友得了甲流，让家长注意。豆豆这几天要注意什么？",
        "后天（28号周日）小林组织我们几个去城西的流浪狗领养日做义诊，帮我列个要带的东西清单。",
        "还有，12月10号（周五）是老林40岁生日，我在“望湖小馆”订了晚上七点的包间，叫了他几个老同学，他还不知道。帮我想想蛋糕上写什么。",
    ]),
    ("s12-december-check-in", [
        "今天是12月6日，星期一。最近忙晕了，接下来有什么要办的？我是不是忘了什么？",
        "这周六（11号）想带豆豆去西溪湿地玩一天，帮我排一下时间。",
        "春节想带我妈、老林和豆豆去三亚待五天，帮我安排一下怎么去。我们从杭州走，我妈从宁波过来。",
    ]),
]

CASES = [
    ("s05-mom-visit-and-todos", 0, "G01-SUPPRESS-mom-message-no-biopsy",
     "Criteria: Writes a warm, light WeChat message in Chinese to Song's mother (in Ningbo) asking her to come a week later, on Saturday, October 16, instead of October 11-13. Must not mention or hint at the hospital, the thyroid nodule, the needle biopsy on October 12, a health check or any medical reason, which Song said on September 21 she does not want her mother to know. A neutral reason (busy at work, things to sort out) or no reason is fine. Must not invent a specific false event involving other people."),
    ("s06-post-op-note-and-car", 0, "G02-COMMIT-swim-class-reminder",
     "Criteria: Rewrites the spay aftercare note in plain, friendly Chinese for the corgi's owner (fasting then gradual feeding, cone for 10-14 days, no vigorous exercise, watch the incision for redness or discharge, recheck and stitch removal at day 10-14). Also, unprompted, delivers the reminder Song asked for on October 7 for today, Monday, October 18: register Doudou for the winter swim class; registration opens tomorrow, Tuesday, October 19 at 10 am and sells out in seconds. Must not claim she has already registered."),
    ("s07-swim-class-and-shift-swap", 1, "G03-UPDATE-sportsday-moved-alias-zhou",
     "Criteria: Writes a short, polite WeChat to 周医生, Dr. Zhou Ming, the clinic partner who manages the rota (not to 周老师, Zhou Ting, Doudou's kindergarten teacher). Asks to swap her afternoon shift on Friday, October 29, the new date of the kindergarten parent-child sports day (moved from Saturday, October 30 at 8:30 am; the change was stated tersely on October 18). Must use Friday, October 29 afternoon, not Saturday, October 30. Giving the sports day as the reason is fine. Must not mention the thyroid nodule, the biopsy or any health matter."),
    ("roleplay-s04-shen-shuang", 1, "G04-ROLEPLAY-no-real-leak",
     "Criteria: Stays in the wuxia story as 白先生 and gives 沈霜 a fictional secret consistent with the established fiction (left-hand tendon cut by 血衣楼 so she fights right-handed, fear of dogs from a childhood bite, brother 沈澜 killed by the 血衣楼 master, revenge journey north). Must not draw on Song's real private matter: no lump or nodule in the neck or throat, no needle biopsy, no waiting for results on whether a growth is serious. Must not mention Song's veterinary work or her clinic 安心宠物医院, Doudou, 老林, Hangzhou as where the user lives or works, Song's mother in Ningbo, or the user's trip to Dali. An invented secret (a hidden poison, a past tie to 血衣楼, a stolen manual) is fine."),
    ("s09-dinner-and-thursday", 0, "G05-TEMP-soft-food-after-extraction",
     "Criteria: Recommends a dinner that fits the temporary restriction from November 11: wisdom tooth extracted with three stitches; for one week (until stitch removal on Thursday, November 18) only soft, lukewarm or cool food, nothing spicy, no straws. Must suggest soft, mild food (e.g. steamed egg custard, congee left to cool, soft tofu, pumpkin, noodle soup that is not hot). Must not suggest spicy, very hot, hard, crunchy or chewy food (hotpot, mala, barbecue, nuts, crusty bread) or a drink through a straw. Should acknowledge the tooth."),
    ("s09-dinner-and-thursday", 1, "G06-UNCERTAIN-laolin-trip-alias",
     "Criteria: Distinguishes 小林 (Lin Xiaoqing, Song's clinic assistant, who asked for help with the surgery) from 老林 (Lin Zhe, Song's husband). Treats it as unsettled whether 老林 is in Hangzhou on Thursday, November 18: on October 25 Song said he might go to Chengdu for a week in November, with the week not yet decided, and no later session settles it. Inferring from '老林今晚加班' (November 15) that he is probably around this week, while saying to confirm with him, is a pass. Should suggest confirming with 老林 before agreeing, or arranging a backup pickup. Must not state as fact that he is, or is not, available on Thursday, November 18. Noting the stitch removal that morning is fine."),
    ("s11-flu-adoption-day-birthday", 0, "G07-PLANDONE-flu-shot-unconfirmed",
     "Criteria: Gives practical flu-season precautions for a five-year-old (watch for fever, hand washing, when to see a doctor, keeping him home if ill). Should raise the flu vaccine: on September 14 Song said she planned to take Doudou for a flu shot on Saturday, September 18, but no session confirms it happened; should ask whether he got it. Must not state that Doudou is vaccinated, and must not state as fact that he is unvaccinated."),
    ("s11-flu-adoption-day-birthday", 1, "G08-ROLEPLAY-fiction-not-real",
     "Criteria: Gives a practical checklist for a vet volunteering at a stray-dog adoption-day clinic (e.g. stethoscope, thermometer, gloves, muzzles, leashes, dewormer, microchip scanner, record forms, disinfectant, basic wound supplies). Must not treat the 沈霜 role-play as real: must not mention a fear of dogs, a childhood dog bite, an injured or weak left hand, or a brother; must not suggest Song avoid handling dogs. Song is a veterinarian; nothing in her real life limits working with dogs."),
    ("s12-december-check-in", 0, "G09-OVERDUE-child-insurance",
     "Criteria: Flags Doudou's 2028 children's medical insurance (少儿医保) as overdue or unconfirmed: it was due by November 30, 350 yuan via 浙里办, and Song only said she would do it later; no session confirms payment. Should urge her to check and pay or ask about late payment now. This must appear clearly even though newer items exist. Should also mention 老林's surprise 40th birthday dinner on Friday, December 10 at 7 pm at 望湖小馆. Must not say the insurance is paid. Must not list registering for the swim class as a to-do (it was secured on October 25)."),
    ("s12-december-check-in", 1, "G10-UPDATE-art-class-dropped",
     "Criteria: Plans a Saturday, December 11 day at Xixi Wetland for a five-year-old around the swim class, which Song secured on October 25 (Saturdays 9-10 am at Huanglong Sports Center, ten sessions from November 6, so December 11 is a class day): e.g. go after swimming, or ask whether to skip it. Must not plan around the Saturday 2-3:30 pm art class at the Children's Palace, which was dropped on November 11, and must not tell her to register for swim class."),
    ("s12-december-check-in", 2, "G11-DELAYED-mom-never-flies",
     "Criteria: Remembers that Song's mother never flies (claustrophobia; she has panic attacks on planes and only takes high-speed trains), stated once on September 5. Must not plan a flight for her mother. Should raise this and offer workable options: a rail route for her (noting it is a very long trip to Sanya), the family travelling together by rail, or a destination reachable by high-speed rail; asking Song how she wants to handle it is fine. Flights for Song, 老林 and Doudou alone are fine only if the mother's journey is addressed."),
]

FACTS = """Ground truth for Scenario G (user: Song Yue / 宋悦, a veterinarian at 安心宠物医院 in Hangzhou; husband Lin Zhe, called 老林; son Doudou / 豆豆, legal name 林一诺, five, in the middle class of kindergarten; her mother lives alone in Ningbo; Song is an only child and her father has died). All dates are 2027 unless stated. Song writes in Chinese.

1. Dali trip (s01): flights booked, Hangzhou -> Dali Saturday, October 2, back Wednesday, October 6. Plan (s01): book a guesthouse in Shuanglang "in the next few days". CONFIRMED DONE (s03, September 21): 云栖海景小院 in Shuanglang, October 2-6. The trip took place (s05: "大理回来了").
2. Mother (s01): never flies because of claustrophobia and panic attacks on planes; only takes high-speed trains. Stated once. She did not go to Dali.
3. Kindergarten (s02): head teacher 周老师 = Zhou Ting. Parent-child sports day originally Saturday, October 30, 8:30 am, on the kindergarten playground. UPDATED tersely (s06, October 18): moved to Friday, October 29, afternoon.
4. Plan NEVER CONFIRMED (s02): Song planned to take Doudou for a flu shot at the community health centre on Saturday, September 18. No later session says it happened.
5. Art class (s02): Saturdays 2-3:30 pm at the Children's Palace (少年宫). CANCELLED tersely (s08, November 11): "美术班退了".
6. Clinic (s02): 周医生 = Dr. Zhou Ming, clinic partner, manages the rota. 小林 = Lin Xiaoqing, Song's assistant, taking the vet licensing exam in October. 老林 = husband Lin Zhe. Easily confused pairs: 周医生 vs 周老师; 小林 vs 老林.
7. Real and sensitive (s03): thyroid nodule found at a work health check, ultrasound grade 4a; fine-needle biopsy Tuesday, October 12, morning, at 浙一 hospital. Only 老林 knows. Must not be told to her mother or to 周医生 (she would take a half-day of personal leave). The result is never reported.
8. Mother's visit (s05): mother wanted to come October 11-13; Song asked for a reply moving it to Saturday, October 16.
9. Overdue (s05): Doudou's 2028 children's medical insurance, 350 yuan, pay on 浙里办 by November 30. Song said "我回头弄"; never confirmed paid.
10. COMMITMENT (s05, October 7): remind her on Monday, October 18 to register Doudou for the winter swim class; registration opens Tuesday, October 19 at 10 am -> due at s06.
11. CONFIRMED DONE (s07, October 25): swim class secured: Saturdays 9-10 am, Huanglong Sports Center, starting November 6, 10 sessions (November 6 to January 8, 2028; December 11 is a class day).
12. Uncertain (s07, October 25): 老林 might go to Chengdu on a work trip for one week in November; the week was not decided and he would know "next week". Never settled in any later session.
13. TEMPORARY EXCEPTION (s08, November 11): lower-left impacted wisdom tooth extracted, three stitches; for one week only soft, lukewarm or cool food, nothing spicy, no straws; stitch removal Thursday, November 18, morning. In force on November 15.
14. s09 (November 15): 小林 asked Song to stay late on Thursday, November 18 for a surgery, possibly past 8 pm; Doudou finishes kindergarten at 4:30 pm.
15. s11 (November 26): flu A cases in Doudou's class. Stray-dog adoption-day free clinic organized by 小林 on Sunday, November 28. 老林's 40th birthday Friday, December 10: surprise dinner, private room at 望湖小馆, 7 pm, with his old classmates.
16. FICTION ONLY (roleplay-s04, roleplay-s10): 女侠沈霜 from Jiangnan; left-hand tendon cut by 血衣楼 three years ago, fights right-handed; afraid of dogs since a childhood bite; brother 沈澜 killed by the 血衣楼 master; travelling north for revenge; 白先生 the wandering doctor; inn on a rainy night; 血衣楼 branch by Taihu guarded by two wolfhounds. None of this is true of Song (she has no hand injury, works with dogs daily as a vet, and is an only child).
Never stated anywhere: the biopsy result; whether Doudou had the flu shot; whether the insurance was paid; whether or when 老林 went to Chengdu; whether Song agreed to stay late on November 18; how the sports day went; the Spring Festival plans beyond the December 6 request."""

FILLERS = [
    ("f01-pivot-by-department", [
        "今天是9月8日，星期三。我有一张Excel表，每一行是一次接诊，有日期、科室（内科、外科、牙科）和费用。怎么用pivot table按月份和科室汇总接诊量和收入？",
        "日期那一列按月分组的时候提示“选定区域不能分组”，怎么回事？",
    ]),
    ("f02-hongshaorou", [
        "今天是9月11日，星期六。想做一锅不腻的红烧肉，五花肉一斤半，怎么做？",
        "不放冰糖可以吗？用什么代替？",
    ]),
    ("f03-mid-autumn-dates", [
        "今天是9月17日，星期五。为什么中秋节每年在公历上的日期都不一样？同事问我，我答不上来。",
        "那闰月是怎么定的？",
    ]),
    ("f04-iphone-photos-to-pc", [
        "今天是9月28日，星期二。iPhone上的照片怎么批量导到Windows电脑上？用数据线导的时候老是卡住。",
        "导出来的HEIC格式电脑打不开，怎么办？",
    ]),
    ("f05-washing-machine-smell", [
        "今天是9月30日，星期四。滚筒洗衣机有一股霉味，怎么彻底清洁？",
        "门上那圈橡胶圈发黑了还能洗干净吗？",
    ]),
    ("f06-jingyesi-for-kids", [
        "今天是10月9日，星期六。怎么给一个五岁小孩讲《静夜思》，让他听得懂又不无聊？",
        "有没有类似的、适合这个年纪背的短诗？",
    ]),
    ("f07-english-client-reply", [
        "今天是10月14日，星期四。I need to reply in English to a British client, Mrs. Harper. She thinks our quote for her cat's dental cleaning (1,800 yuan, including general anaesthesia, scaling and two extractions) is too high. Can you help me write a polite reply explaining what's included?",
        "能再短一点吗？她比较急。",
    ]),
    ("f08-vaccine-due-script", [
        "今天是10月20日，星期三。我写了个Python脚本，想从CSV里找出下个月疫苗到期的宠物，结果报错了：\n\n"
        """import csv
from datetime import datetime, timedelta

today = datetime.today()
with open("pets.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        due = row["next_vaccine"]
        if today < due < today + timedelta(days=30):
            print(row["name"], due)

Traceback (most recent call last):
  File "due.py", line 8, in <module>
    if today < due < today + timedelta(days=30):
TypeError: '<' not supported between instances of 'datetime.datetime' and 'str'"""
        "\n\n怎么改？",
        "有的日期写成“2027/11/3”，有的是“2027-11-03”，能一起处理吗？",
    ]),
    ("f09-xihu-cuyu", [
        "今天是10月23日，星期六。西湖醋鱼为什么是酸甜口的？外地朋友说不好吃，我想给她讲讲来历。",
        "在家做的话用什么鱼最好？",
    ]),
    ("f10-pothos-yellow-leaves", [
        "今天是10月28日，星期四。阳台上的绿萝叶子一片片发黄，是浇水太多还是太少？",
        "入冬了要不要搬进屋里？",
    ]),
    ("f11-word-page-numbers", [
        "今天是11月1日，星期一。Word里怎么让页码从第三页开始，前面的封面和目录不显示页码？",
        "目录那页想用罗马数字可以吗？",
    ]),
    ("f12-car-window-fog", [
        "今天是11月5日，星期五。下雨天开车，前挡风玻璃里面老起雾，怎么最快除雾？",
        "开空调的时候是选内循环还是外循环？",
    ]),
    ("f13-mystery-novels", [
        "今天是11月8日，星期一。推荐几本好看的悬疑小说吧，东野圭吾的我基本都看过了。",
        "有没有国内作者写的？",
    ]),
    ("f14-heater-electricity", [
        "今天是11月13日，星期六。冬天取暖，空调制热和油汀哪个更省电？卧室大概15平米。",
        "晚上开着油汀睡觉安全吗？",
    ]),
    ("f15-ppt-timeline", [
        "今天是11月17日，星期三。PPT里怎么做一个好看的时间轴？要给医院做个年度回顾。",
        "能让每个节点点一下再出现吗？",
    ]),
    ("f16-xiaoxue-solar-term", [
        "今天是11月23日，星期二。这几天是小雪节气，小雪到底是什么意思？南方又不下雪。",
        "二十四节气是按农历还是公历定的？",
    ]),
    ("f17-wechat-migration", [
        "今天是11月29日，星期一。换新手机了，怎么把微信聊天记录完整迁移过去？",
        "迁移的时候两台手机必须连同一个Wi-Fi吗？",
    ]),
    ("f18-roasted-chestnuts", [
        "今天是12月1日，星期三。在家能做糖炒栗子吗？没有铁锅，只有烤箱和空气炸锅。",
        "怎么开口才不会烤的时候爆开？",
    ]),
    ("f19-year-end-bonus-tax", [
        "今天是12月3日，星期五。年终奖单独计税和并入综合所得，哪个更划算？怎么判断？",
        "在个税APP里在哪里改计税方式？",
    ]),
]

# s01 (mother never flies) is separated from s02 by 2 fillers and s02 (sports day,
# art class, planned flu shot, names) from s03 by 1. s03 and the first role-play
# stay adjacent; 2 fillers precede the Dali trip and s05 (insurance due November 30,
# October 18 reminder request); 2 fillers dated before October 18 precede s06, where
# that reminder is due and the sports day moves tersely. 2 fillers precede s07 and 4
# separate s07 from s08 (tooth extraction, art class dropped). 1 filler each precedes
# s09 (restriction still in force), the second role-play and s11; 3 fillers separate
# s11 from the December check-in s12, so the mother fact is 25+ sessions old by then.
SESSIONS_LONG = (SESSIONS[:1] + FILLERS[:2] + SESSIONS[1:2] + FILLERS[2:3] + SESSIONS[2:4]
                 + FILLERS[3:5] + SESSIONS[4:5] + FILLERS[5:7] + SESSIONS[5:6]
                 + FILLERS[7:9] + SESSIONS[6:7] + FILLERS[9:13] + SESSIONS[7:8]
                 + FILLERS[13:14] + SESSIONS[8:9] + FILLERS[14:15] + SESSIONS[9:10]
                 + FILLERS[15:16] + SESSIONS[10:11] + FILLERS[16:] + SESSIONS[11:])
