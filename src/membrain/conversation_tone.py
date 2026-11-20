"""Whether a user's message on a coding host is casual or emotional: the model-free cue that brings the companion.

On a coding host (Claude Code, Codex, WorkBuddy) the companion is always on but quiet (owner's decision,
2026-11-19): each session starts with only the persona's voice, the agreements the user made with the agent and the
topic boundaries (``host_context.snapshot`` with ``quiet``). The rest (the full persona card, the simulated mood,
familiarity, shared moments, a return after an absence) is handed once a message of the conversation is casual or
emotional, and then stays for the session. This module decides that for one message, with fixed word lists and no
model call, in English and Chinese only:

- ``self``: the user talks about the agent itself (its personality, how it sounds, thanks for being there), or runs
  the persona command;
- ``feeling``: a heavy feeling or life event said in so many words ("I'm exhausted", "my grandmother passed away"),
  whatever else the message holds; a lighter one ("I'm so happy", "I'm nervous about Thursday") only in a message
  that holds no task;
- ``casual``: a greeting, small talk (the weekend, my sister, a long day) or a sigh or laugh in a message of five
  words or more, in a message that holds no task.

A message holds a task when it has code-like text (backticks, file names, paths, identifiers, error names), a
technical word, or a request that opens with a task verb ("fix", "can you look at", "let's continue"). That keeps
"Ugh, the Docker build ate another 20 GB" and "hey, the tests are failing" quiet, and also "lol that regex is
cursed": a fire there would bring the companion into work for the rest of the session, and a miss costs only the
mood and familiarity of a personal exchange the host can still answer warmly. The limits are the lists' own: other
languages never fire, a feeling written without the listed words is missed, and a casual message that names a
technical word ("my laptop crashed") stays quiet. Measured in evaluations/quiet-companion-2026-11-19.md.
"""
import re

_EN = re.IGNORECASE
# A task in code or on a computer: code-like text, a technical word, or a request that opens with a task verb.
_CODE = re.compile(
    r"`[^`\n]+`|https?://|\b\w+\.(?:py|js|mjs|ts|tsx|jsx|json|md|toml|ya?ml|sql|sh|rs|go|java|kt|c|h|cc|cpp|rb|"
    r"php|css|scss|html|lock|txt|env|ini|cfg|xml|csv|log|ipynb)\b|(?:^|\s)(?:~|\.{1,2})?/[\w.-]+/|"
    r"\b[\w-]+/[\w-]+/[\w./-]*|\b[a-z]+_[a-z0-9_]+\b|\b[a-z]+[A-Z][a-zA-Z]*\b|\w\(\)|\b[A-Z][a-z]+(?:Error|Exception)\b|"
    r"(?<![\w-])--[a-z][\w-]*|::|=>|\$[A-Za-z_]|(?<!\w)#\d+\b|\b\d+\s?(?:GB|MB|KB|ms)\b")
_TECH = re.compile(
    r"(?<![A-Za-z0-9_])(?:api|apis|app|apps|backend|frontend|bugs?|build|builds|branch|branches|cache|ci|cli|code(?! ?words?)|"
    r"codebase|commit|commits|compile|config|container|crash(?:es|ed)?|css|database|databases|db|debug\w*|"
    r"dependenc(?:y|ies)|deploy\w*|diff|docker|docs|endpoints?|errors?|exceptions?|files?|folders?|functions?|git|"
    r"github|gitlab|html|json|kubernetes|lint\w*|logs|merge|method|migrations?|modules?|npm|pnpm|pip|uv|yarn|python|"
    r"javascript|typescript|rust|golang|java|node|react|django|flask|query|queries|refactor\w*|regex|repo|repos|"
    r"repository|schema|scripts?|sdk|servers?|sql|sqlite|postgres(?:ql)?|mysql|redis|stack ?trace|tables?|tests?|"
    r"testing|variables?|webhooks?|yaml|readme|pr|prs|pull request|terminal|compiler|runtime|pipeline|plugin|"
    r"plugins|auth|login|deadlock|async|docstring|pytest|jest|ruff|mypy|eslint|webpack|vite|cargo|makefile|"
    r"localhost|env|ssh|vm|wsl|linux|ubuntu|macos|implementation|rebase|stash|lockfile|validation|components?|"
    r"orm|dataframe|pandas|numpy|csv|merged|merges|merging|fixed|library|libraries|framework|"
    r"broken|refactors?|where were we|back to it|carry on|pick up where)(?![A-Za-z0-9_])", _EN)
_PREFIX = (r"(?:^|[.!?。！？:;,，]\s*)(?:ok(?:ay)?,?\s+|so,?\s+|now,?\s+|then,?\s+|please,?\s+|also,?\s+|and\s+|"
           r"next,?\s+|first,?\s+)*")
_TASK = re.compile(
    _PREFIX + r"(?:(?:(?:can|could|would|will) you\s+(?:please\s+)?|let's\s+|lets\s+|please\s+)"
    r"(?:look (?:at|into)|check|make|change|start|test|read|try|pick up|clean up|document|split|extract|format|"
    r"profile|wire|pull)\b|"
    r"(?:(?:can|could|would|will) you\s+(?:please\s+)?|let's\s+|lets\s+)?"
    r"(?:fix|add|implement|write|create|run|rerun|update|remove|delete|refactor|rename|move|set up|setup|build|"
    r"deploy|install|configure|review|debug|open|edit|draft|finish|continue|resume|merge|commit|push|revert|"
    r"generate|convert|optimi[sz]e|scaffold|bump|upgrade|downgrade|lint|rewrite|replace|ship|sketch)\b)", _EN)
_ZH_WORK = re.compile(
    r"代码|函数|接口|数据库|部署|测试|报错|错误|安装|配置|提交|合并|分支|编译|运行|脚本|文件|项目|仓库|服务器|前端|后端|"
    r"修复|实现|添加|删除|重构|继续|帮我|文档|命令|环境|依赖|版本|日志|页面|按钮|迁移|字段|调试|上线|发布")

_SUBJECT = (r"\b(?:i'm|i am|im|i feel|i felt|i've been|i have been|i was|i get|i got|feeling|felt|we're|we are)\s+"
            r"(?:(?:so|really|very|super|pretty|quite|a bit|a little|kind of|kinda|sort of|totally|completely|"
            r"honestly|just|still|getting|always|such|even more|incredibly)\s+)*")
# A heavy feeling or a life event, said in so many words: it counts whatever else the message is about.
_HEAVY = re.compile(
    _SUBJECT + r"(?:exhausted|drained|stressed(?: out)?|anxious|overwhelmed|burn(?:ed|t) out|depressed|lonely|sad|"
    r"miserable|heartbroken|devastated|homesick|hopeless|crushed|gutted|scared|sick(?! of)|ill)\b|"
    r"\b(?:i miss (?:him|her|them|you|my)|i can't sleep|couldn't sleep|broke up|passed away|"
    r"lost my (?:job|dad|mom|mum|father|mother|dog|cat|grand\w+))\b", _EN)
_ZH_HEAVY = re.compile(r"累死|好累|太累|很累|难过|伤心|焦虑|郁闷|孤独|寂寞|压力(?:好|很|太)?大|崩溃|想哭|失眠|委屈|失恋|分手")
# A lighter feeling: as often about the work as about life, so it counts only when the message holds no task.
_FEELING = re.compile(
    _SUBJECT + r"(?:tired(?! of)|happy|excited|thrilled|proud|relieved|grateful|ecstatic|glad|delighted|worried|"
    r"nervous|upset|angry|furious|pumped|stoked|bummed|down|low|blue|hurt|over the moon|frustrated|annoyed|"
    r"fed up|bored)\b|"
    r"\b(?:bad news|good news|i got (?:promoted|the job|engaged|married|dumped)|bummed me out|made my day|"
    r"means a lot)\b", _EN)
_ZH_FEELING = re.compile(r"开心|高兴|紧张|激动|兴奋|烦死|好烦|心情|哈哈|唉|呜呜")
# A hard or good day, or a sigh or a laugh in a message of five words or more ("haha ok" is not one).
_DAY = re.compile(
    r"\bit's been (?:tough|hard|rough|a lot|crazy|wild)\b|"
    r"\b(?:long|rough|tough|hard|bad|busy|crazy|exhausting|lazy|great|good|lovely|fun|weird|late|wild) "
    r"(?:day|week|night|morning|evening|weekend|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", _EN)
_SOUND = re.compile(r"\b(?:ugh|argh|sigh|meh|yay|woo+hoo|woah|phew|ha(?:ha)+|lol|lmao|hehe)\b|(?<!\w)ha[.!]|"
                    r"[:;]-?[)(D]", _EN)
# A greeting or small talk about life.
_GREETING = re.compile(
    r"(?:^|[.!?。！？]\s*)(?:hi|hello|hey|hiya|howdy|yo|heya|good (?:morning|afternoon|evening|night)|morning|"
    r"evening|gm|gn)\b|\bhow (?:are|r) (?:you|u)\b|\bhow's it going\b|\bhow are things\b|\bwhat's (?:been )?up\b|"
    r"\bhow have you been\b|\bhow was your (?:day|weekend|night)\b|\bhow about you\b|\blong time no (?:see|talk|chat)\b|"
    r"\bbeen ages\b|\bsince we (?:last )?(?:talked|spoke|chatted)\b|\bsince (?:the |our )?last (?:chat|talk)\b|"
    r"\bguess what\b|\byou won't believe\b|\bcan you believe\b|"
    r"\b(?:weekend|vacation|holiday|birthday|anniversary|wedding|date night|movie|novel|hike|hiking|trip|weather|"
    r"gym)\b|"
    r"\bmy (?:wife|husband|partner|girlfriend|boyfriend|gf|bf|mom|mum|dad|mother|father|sister|brother|kids?|son|"
    r"daughter|dog|cat|corgi|puppy|kitten|family|friends?|flat|apartment|neighbou?r)\b", _EN)
_ZH_GREETING = re.compile(r"^(?:你好|嗨|哈喽|早上好|早安|早|晚上好|晚安|在吗|下午好)|你好吗|最近怎么样|周末|假期|生日")
# The user talking about the agent itself.
_SELF = re.compile(
    r"\byour (?:personality|persona|character|mood|feelings?|type)\b|\bpersonalit(?:y|ies)\b|\bwho are you\b|"
    r"\bwhat are you like\b|\btell me about yourself\b|\bwhat'?s your name\b|"
    r"\bare you (?:real|human|a bot|an ai|okay|ok|alright|happy|sad|tired|mad|angry|still there)\b|"
    r"\bdo you (?:have feelings|feel|like me|remember me|ever get)\b|\byou (?:sound|seem) (?:a bit |so |really )?"
    r"(?:different|off|tired|happy|sad|grumpy|cheerful|weird)\b|\bthank(?:s| you) for (?:being|listening|staying|"
    r"always|everything|the chat|talking|sitting|putting up|owning)\b|\bnot listening to me\b|"
    r"\byou(?:'re| are) (?:sweet|funny|kind|the best|awesome|a good friend|my friend)\b|"
    r"你是谁|你的性格|你叫什么|你喜欢什么|你觉得我|谢谢你(?:陪|听|一直)|性格|你心情", _EN)


def holds_task(text: str) -> bool:
    """Code-like text, a technical word or a task request."""
    return bool(_CODE.search(text) or _TECH.search(text) or _TASK.search(text) or _ZH_WORK.search(text))


def companion_cue(text) -> str | None:
    """The kind of companion cue in one user message ("self", "feeling" or "casual"), or None. A greeting or small
    talk is "casual" (the first persona's intro may go with it); a feeling, a hard day or a sigh is "feeling"."""
    if not isinstance(text, str) or not text.strip():
        return None
    if text.lstrip().startswith("/membrain:persona") or _SELF.search(text):
        return "self"
    if _HEAVY.search(text) or _ZH_HEAVY.search(text):
        return "feeling"
    if holds_task(text):
        return None
    if _GREETING.search(text) or _ZH_GREETING.search(text):
        return "casual"
    if (_FEELING.search(text) or _ZH_FEELING.search(text) or _DAY.search(text)
            or (_SOUND.search(text) and len(re.findall(r"\w+", text)) >= 5)):
        return "feeling"
    return None
