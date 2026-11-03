"use strict";
// Chinese for the memory page. Interface text is matched whole (whitespace normalised) as it appears, so memory.js
// stays in English; elements with the class "user-text" hold what people wrote and are never translated.

const ZH = {
  "memBrain · Your memory": "memBrain · 你的记忆",
  "Memory views": "记忆视图",
  "Notes": "笔记", "Plans and dates": "计划与日期", "People": "人物", "Conversations": "对话", "Search": "搜索",
  "Privacy": "隐私",
  "Brain": "大脑", "derived from:": "来源：", "about person:": "相关人物：", "replaces:": "取代：", "(not shown)": "（未显示）", "(no text)": "（无文字）", "Your memory as a brain": "你的记忆大脑",
  "Each dot is one memory, placed in the area for its kind. Lines are links that memory records, such as a note and the message it came from. The layout is illustrative: dot size is not memory strength. The brightest dots are the newest.":
    "每个点是一条记忆，按类型放在大脑的对应区域。连线是记忆中记录的关联，比如一条笔记和它来自的消息。布局只是示意：点的大小不代表记忆强度。最亮的点是最新的。",
  "Demo: fictional memories, not anyone's data.": "演示：虚构的记忆，不是任何人的数据。",
  "Plans": "计划", "Commitments": "承诺", "Preferences": "偏好", "Health and constraints": "健康与限制",
  "Routines": "日常", "Recent messages": "最近的消息", "Relationship": "关系", "Milestones and dates": "里程碑与日期",
  "Other notes": "其他笔记", "Sensitive note (hidden)": "敏感笔记（已隐藏）", "Sensitive memory": "敏感记忆",
  "Memory is busy updating. Retry the map shortly.": "记忆正在更新，请稍后再打开记忆图。",
  "No memories yet. Talk with your agent, then come back.": "还没有记忆。先和你的 agent 聊聊，再回来看看。",
  "Your memory as a brain: each dot is one memory, grouped by kind": "你的记忆大脑：每个点是一条记忆，按类型分组",
  "Checking memory…": "正在检查记忆…", "Refresh status": "刷新状态",
  "Your agent's memory": "你的 agent 的记忆",
  "Connect once, then talk normally. Your agent records conversations and brings useful memories into later sessions. You can review and correct them here.":
    "只需连接一次，之后正常对话即可。你的 agent 会记录对话，并在之后的会话里带上有用的记忆。你可以在这里查看和更正。",
  "Connection checks": "连接检查", "Local memory": "本地记忆", "Checking…": "检查中…",
  "Messages from your agent": "来自 agent 的消息", "Waiting for a message…": "等待消息…",
  "Recall by meaning": "按语义召回", "Enable recall by meaning": "启用按语义召回",
  "Connect Claude Code or Codex": "连接 Claude Code 或 Codex", "Your agent": "你的 agent",
  "Run this in a terminal, then open a new agent session. Approve its memory tools and hooks when asked.":
    "在终端里运行下面的命令，然后打开一个新的 agent 会话。提示时请允许它的记忆工具和 hook。",
  "Copy install command": "复制安装命令", "Try remembering across sessions": "试试跨会话记忆",
  "Tell your agent a real preference, such as “I prefer short answers.” Open a new session and ask “How should you format answers for me?” Check the saved note or original message here.":
    "告诉你的 agent 一个真实的偏好，比如“我喜欢简短的回答”。然后打开一个新会话，问它“你应该怎样给我排版回答？”，再到这里查看保存的笔记或原始消息。",
  "Receiving messages confirms recording. The new-session exercise checks whether your agent actually uses them. You do not need to maintain notes by hand.":
    "能收到消息说明记录正常；新会话的测试检查 agent 是否真的用上了它们。你不需要手动维护笔记。",
  "Add a preference here": "在这里添加一个偏好", "Your memory": "你的记忆", "Open this page with": "用",
  ". It starts the local service and opens a single-use link, so you never copy a key.":
    " 打开这个页面。它会启动本地服务并打开一个一次性链接，你不需要复制任何密钥。",
  "Use an access key instead": "改用访问密钥", "Access key": "访问密钥", "Open": "打开",
  "Lasting facts your agent keeps about you. Every session starts with these. Correct anything that is wrong; your corrections take precedence over the agent's notes.":
    "agent 记下的关于你的长期事实，每个会话开始时都会带上。有错就更正：你的更正优先于 agent 的笔记。",
  "Add a note": "添加笔记",
  "Open plans, upcoming dates and promises. A plan stays open until you confirm it is done.":
    "未完成的计划、即将到来的日期和承诺。在你确认完成之前，计划一直保持未完成。",
  "Include completed and cancelled plans": "包括已完成和已取消的计划",
  "People your agent remembers, with their names and aliases.": "agent 记住的人，以及他们的名字和别名。",
  "Original messages, as recorded. Linked notes show the original messages they refer to.":
    "按记录保存的原始消息。关联了来源的笔记会显示它们依据的原始消息。",
  "The same recall your agent uses before replying.": "和 agent 回复前使用的召回相同。",
  "Search memory": "搜索记忆", "What did I say about…": "我说过关于……的什么",
  "Memory is stored on this computer. Recalled text is sent to the agent you use; configured model providers may also process it.":
    "记忆保存在这台电脑上。召回的内容会发送给你使用的 agent；你配置的模型服务商也可能处理这些内容。",
  "Recording": "记录", "Pause duration": "暂停时长", "for 1 hour": "1 小时", "for 24 hours": "24 小时",
  "until I resume": "直到我恢复", "Pause recording": "暂停记录", "Resume recording": "恢复记录",
  "While paused nothing new is stored; recall of earlier memory keeps working. Text inside":
    "暂停期间不会保存任何新内容，已有记忆的召回照常工作。写在",
  "and values that look like passwords or keys are never stored.": "里的文字，以及看起来像密码或密钥的内容，永远不会被保存。",
  "Export": "导出", "Download everything, with original text and sources, as one JSON file.": "把全部内容连同原文和来源下载为一个 JSON 文件。",
  "Export memory": "导出记忆", "Erase everything": "全部清除",
  "Deletes the content of every message and note. Erasure is recorded, so it also holds if an older backup is restored. This cannot be undone.":
    "删除所有消息和笔记的内容。清除会被记录下来，即使从旧备份恢复也不会回来。此操作无法撤销。",
  "Type ERASE to confirm": "输入 ERASE 确认",
  "Person": "人物", "Health or constraint": "健康或限制", "Preference": "偏好", "Plan": "计划", "Routine": "习惯",
  "Milestone": "重要日子", "Relationship": "相处方式", "Agent promise": "agent 的承诺", "Other": "其他",
  "This is a partial list. Some older notes did not fit; use Search to find them.": "这不是完整列表，部分较早的笔记没有显示；可以用搜索找到它们。",
  "No notes yet. Add a lasting fact above, or ask your connected agent to remember one.": "还没有笔记。可以在上面添加一条长期事实，或者让已连接的 agent 记住一件事。",
  "Nothing here yet. Add a note with the matching kind.": "这里还没有内容。添加一条对应类型的笔记即可。",
  "Note text": "笔记内容", "Kind": "类型", "Plan status": "计划状态", "Person or topic": "人物或主题",
  "Other names, separated by commas": "其他称呼，用逗号分隔", "Due date": "截止日期", "Event date": "发生日期",
  "Pin this note": "置顶这条笔记", "Sensitive: mention only when I bring it up": "敏感：只在我主动提起时才提",
  "Link original messages": "关联原始消息",
  "Choose messages this note is based on. Unlinked notes stay clearly labelled.": "选择这条笔记依据的消息。没有关联来源的笔记会明确标出。",
  "Original messages": "原始消息", "Save correction": "保存更正", "Add note": "添加笔记", "Cancel": "取消",
  "Note corrected. Your version takes precedence.": "笔记已更正，以你的版本为准。", "Note added.": "笔记已添加。",
  "Loading original messages…": "正在加载原始消息…", "Some original messages are no longer available.": "部分原始消息已不存在。",
  "Edit": "编辑", "Delete": "删除", "Date has passed; completion is not confirmed.": "日期已过，但尚未确认完成。",
  "Waiting for the source message to finish recording.": "正在等待来源消息记录完成。",
  "Standalone note written by you.": "你单独写的笔记。",
  "Original message not linked. Edit to attach its source.": "没有关联原始消息。可以编辑并补上来源。",
  "Merge duplicate": "合并重复项", "Delete this note? Its content is erased.": "删除这条笔记？它的内容会被清除。",
  "Note deleted.": "笔记已删除。", "No conversations recorded yet.": "还没有记录任何对话。", "Load older messages": "加载更早的消息",
  "You": "你", "Agent": "agent", "Save as note": "保存为笔记",
  "Delete this message? Its content is erased everywhere it was used.": "删除这条消息？它在所有用到的地方都会被清除。",
  "Message deleted.": "消息已删除。", "Delete this conversation": "删除这段对话",
  "Delete every message in this conversation?": "删除这段对话里的所有消息？", "Conversation deleted.": "对话已删除。",
  "Nothing found.": "没有找到。", "note": "笔记",
  "Recording controls are available when this page is opened from the local service.": "从本地服务打开这个页面时，才能控制记录。",
  "Recording paused": "记录已暂停", "Recording on": "正在记录",
  "Recording is paused. New messages are not stored.": "记录已暂停，新消息不会被保存。",
  "New messages and replies are being stored.": "新的消息和回复正在被保存。",
  "Exported. The file contains your original messages; store it securely.": "已导出。文件里有你的原始消息，请妥善保存。",
  "Type ERASE to confirm.": "请输入 ERASE 确认。", "Everything was erased.": "已全部清除。",
  "Install command copied.": "安装命令已复制。", "Select and copy the install command above.": "请选中并复制上面的安装命令。",
  "Preparing recall by meaning. Keyword search keeps working; this page will update automatically.":
    "正在准备按语义召回。关键词搜索照常可用，页面会自动更新。",
  "Messages are arriving": "正在收到消息", "Finish connecting your agent": "请完成 agent 的连接",
  "Running on this computer.": "正在这台电脑上运行。", "Needs attention. Run membrain doctor for a diagnosis.": "需要处理。运行 membrain doctor 查看诊断。",
  "No agent messages received yet. Connect below, send a message and wait for its reply, then refresh.":
    "还没有收到 agent 的消息。请在下面完成连接，发一条消息并等它回复，然后刷新。",
  "Downloading the local model (about 135 MB). Keyword search already works.": "正在下载本地模型（约 135 MB）。关键词搜索已经可用。",
  "The download failed. Check your connection and retry below; keyword search still works.": "下载失败。请检查网络后在下面重试；关键词搜索仍然可用。",
  "The model is downloaded. Finish enabling it below.": "模型已下载，请在下面完成启用。",
  "Local model support is missing. Reinstall using the documented semantic extra.": "缺少本地模型支持。请按文档带上 semantic 附加组件重新安装。",
  "Optional local model; no API key or usage charge. Keyword search already works.": "可选的本地模型，不需要 API key，也不产生费用。关键词搜索已经可用。",
  "Retry model download": "重新下载模型", "Finish enabling recall": "完成启用召回",
  "Memory service needs attention": "记忆服务需要处理", "Messages waiting for delivery": "有消息等待写入",
  "Note extraction needs attention": "笔记提炼需要处理",
  "Indexing your messages": "正在为你的消息建立索引", "Memory is ready": "记忆已就绪", "Keyword memory is ready": "关键词记忆已就绪",
  "Unable to check memory": "无法检查记忆状态", "This link has expired.": "这个链接已过期。",
  "No memory installation found. Run membrain plugin start first.": "没有找到记忆安装。请先运行 membrain plugin start。",
  "written by you": "你写的", "saved by your agent": "agent 保存的",
  "pinned": "置顶", "sensitive": "敏感", "intended": "打算", "scheduled": "已安排", "done": "已完成", "cancelled": "已取消",
  "superseded": "已被取代", "person": "人物", "constraint": "限制", "preference": "偏好", "plan": "计划", "routine": "习惯",
  "milestone": "重要日子", "relationship": "相处方式", "agent promise": "agent 的承诺", "other": "其他",
  "中文": "中文", "English": "English",
  // Personality (persona card)
  "Personality": "个性",
  "How your companion presents itself: its name, character, voice, values and boundaries. Your agent receives it in its own block, apart from what it remembers about you. Every save keeps the earlier versions. How you like replies, as your agent learns it, stays in your preference notes.":
    "你的伙伴如何展现自己：名字、性格、说话方式、价值观和边界。agent 会在单独的区块里收到它，和它记得的关于你的内容分开。每次保存都会保留之前的版本。agent 学到的你喜欢的回复方式，仍然放在你的偏好笔记里。",
  "Current card": "当前设定", "Edit personality": "编辑个性", "Reset personality": "重置个性",
  "Name": "名字", "Traits, one per line (up to 8)": "性格特点，每行一个（最多 8 个）", "Voice": "说话方式",
  "Register": "语体", "casual, formal…": "随意、正式……", "Typical length": "通常长度", "short, a few sentences…": "简短、几句话……",
  "Emoji use": "表情符号", "rarely, never…": "很少、从不……", "Language": "语言", "follows the user…": "跟随用户……",
  "Values, one per line": "价值观，每行一个",
  "Boundaries: what the companion will not do, one per line": "边界：伙伴不会做的事，每行一个",
  "Baseline mood": "基础心情", "Mood": "心情", "calm, cheerful…": "平静、开朗……", "Valence": "情绪倾向",
  "-2 very low": "-2 很低落", "-1 low": "-1 低落", "0 neutral": "0 平和", "+1 positive": "+1 积极", "+2 very positive": "+2 很积极",
  "Energy": "活力", "0 resting": "0 休息", "1 calm": "1 平静", "2 lively": "2 活泼", "3 very lively": "3 很活泼",
  "Leave the mood empty for no baseline. It is the resting point a later mood step returns to; it is not a feeling.":
    "心情留空表示没有基础心情。它是之后的心情功能回归的起点，不是一种真实的感受。",
  "Why this change (optional)": "修改原因（可选）",
  "The card is limited to 1,200 characters. Values that look like passwords or keys are removed.":
    "设定最多 1,200 个字符。看起来像密码或密钥的内容会被移除。",
  "Save as a new version": "保存为新版本", "Versions": "版本",
  "Newest first. Restoring a version saves its content as a new version.": "最新的在前。恢复某个版本会把它的内容保存为一个新版本。",
  "Delete personality history": "删除个性历史",
  "Persona card field baseline_mood.label: give the mood a name.": "个性字段 baseline_mood.label：请给这个心情起个名字。",
  "Only the host sets the default persona card.": "只有宿主应用可以设定默认个性。",
  "Erases every version, including the current card. Deletion is recorded, so it also holds if an older backup is restored. Notes and messages are not touched.":
    "清除所有版本，包括当前设定。删除会被记录下来，即使从旧备份恢复也不会回来。笔记和消息不受影响。",
  "Traits": "性格特点", "Values": "价值观", "Boundaries": "边界", "register": "语体", "length": "长度", "emoji": "表情符号",
  "language": "语言", "No versions yet": "还没有版本",
  "No personality card is set. Your agent keeps its usual manner.": "还没有设定个性。agent 会保持它平常的方式。",
  "No versions yet. Edit the personality to save the first one.": "还没有版本。编辑个性即可保存第一个版本。",
  "Only the most recent versions are listed.": "只列出了最近的版本。",
  "set by you": "你设定的", "set by the host": "宿主设定的", "from accepted feedback": "来自已接受的反馈",
  "reset to no card": "重置为无设定", "reset to the host's default": "重置为宿主默认设定", "host default": "宿主默认", "edited": "已编辑",
  "current": "当前", "Restore": "恢复", "No card.": "无设定。",
  "No change: that is already the current card.": "没有变化：这已经是当前设定。",
  "Reset the personality to the host's default, or to no card? Earlier versions are kept and can be restored. Notes and messages are not touched.":
    "把个性重置为宿主的默认设定，或者清空设定？之前的版本会保留，可以恢复。笔记和消息不受影响。",
  "Delete every personality version, including the current card? This cannot be undone.": "删除所有个性版本，包括当前设定？此操作无法撤销。",
  "Personality history deleted.": "个性历史已删除。",
};

// Sentences built from numbers and names; the captured parts are kept as they are.
const ZH_PATTERNS = [
  [/^(\d+) message\(s\) recorded(?:; latest from (.+?))?(?: on (.+?))?\.$/, (m, n, from, on) =>
    `已记录 ${n} 条消息${from ? `，最近一条来自 ${from}` : ""}${on ? `（${on}）` : ""}。`],
  [/^Enabled\. (\d+) memory item\(s\) still preparing\.$/, (m, n) => `已启用。还有 ${n} 条记忆在准备中。`],
  [/^Enabled\. Finds related wording across languages\.$/, () => "已启用。能跨语言找到意思相近的说法。"],
  [/^(.+?)\. (?:(\d+) message\(s\) waiting for indexing\.|Message index is up to date\.)\s*(?:(\d+) queued record\(s\)\.)?\s*(?:(\d+) background job\(s\) need attention\. Run membrain doctor\.)?\s*$/,
    (m, recall, lag, queued, failed) => `${translate(recall)}。${lag ? `${lag} 条消息等待建立索引。` : "消息索引已是最新。"}`
      + `${queued ? `${queued} 条记录在排队。` : ""}${failed ? `${failed} 个后台任务需要处理，请运行 membrain doctor。` : ""}`],
  [/^(\d+) message\(s\) could not be read for notes \(last error: (.+?)\)\. They are still stored and recalled; notes from them are missing\. Run membrain doctor\.$/,
    (m, n, error) => `有 ${n} 条消息未能提炼成笔记（最近的错误：${error}）。这些消息仍然保存并可召回，只是缺少从中提炼的笔记。请运行 membrain doctor。`],
  [/^Keyword and semantic recall enabled$/, () => "关键词和语义召回均已启用"],
  [/^Keyword recall ready; semantic model downloading$/, () => "关键词召回已就绪；语义模型下载中"],
  [/^Keyword recall ready; model download needs a retry$/, () => "关键词召回已就绪；模型下载需要重试"],
  [/^Keyword recall ready; semantic model needs activation$/, () => "关键词召回已就绪；语义模型需要启用"],
  [/^Keyword recall ready; semantic model not enabled$/, () => "关键词召回已就绪；未启用语义模型"],
  [/^Keyword recall available; local model status unknown$/, () => "关键词召回可用；本地模型状态未知"],
  [/^(.*) Run membrain doctor for help\.$/, (m, error) => `${error} 运行 membrain doctor 获取帮助。`],
  [/^Linked message (.+)$/, (m, id) => `已关联消息 ${id}`],
  [/^imported from (.+)$/, (m, host) => `从 ${host} 导入`],
  [/^due (.+)$/, (m, date) => `截止 ${date}`],
  [/^on (\d{4}-\d{2}(?:-\d{2})?)$/, (m, date) => `日期 ${date}`],
  [/^about (.+)$/, (m, name) => `关于 ${name}`],
  [/^aka (.+)$/, (m, names) => `又名 ${names}`],
  [/^(\S+ · )(You|Agent)(: .*)?$/s, (m, date, who, rest) => `${date}${who === "You" ? "你" : "agent"}${rest || ""}`],
  [/^(\S+) · (\d+) messages · (.*)$/s, (m, date, n, first) => `${date} · ${n} 条消息 · ${first}`],
  [/^Request failed \((\d+)\)$/, (m, status) => `请求失败（${status}）`],
  [/^Version (\d+)$/, (m, n) => `版本 ${n}`],
  [/^History deleted on (.+)$/, (m, date) => `个性历史已于 ${date} 删除`],
  [/^Saved as version (\d+)\.$/, (m, n) => `已保存为版本 ${n}。`],
  [/^Personality reset as version (\d+)\.$/, (m, n) => `个性已重置，保存为版本 ${n}。`],
  [/^restored from version (\d+)$/, (m, n) => `从版本 ${n} 恢复`],
  [/^Restore version (\d+)\? Its content becomes a new version\.$/, (m, n) => `恢复版本 ${n}？它的内容会成为一个新版本。`],
  [/^\(valence ([+-]?\d), energy (\d) of 3\)$/, (m, valence, energy) => `（情绪倾向 ${valence}，活力 ${energy}/3）`],
  [/^Persona version (\d+) is not available\.$/, (m, version) => `个性版本 ${version} 已不存在。`],
  [/^A reason is text of at most (\d+) characters\.$/, (m, n) => `原因最多 ${n} 个字符。`],
  // Field checks name the field; the detail after it comes from the validator and stays in English.
  [/^Persona card field ([\w.\[\]]+): (.+)$/s, (m, where, detail) => `个性字段 ${where}：${detail}`],
  [/^The persona card is (\d+) characters when rendered; the limit is 1,200\. Shorten it\. Nothing was saved and nothing was cut\.$/,
    (m, n) => `这份个性设定有 ${n} 个字符，上限是 1,200。请缩短后再保存。没有保存任何内容，也没有截断。`],
  [/^(\d+) memories and (\d+) links( \(the most recent; more exist\))?\.$/, (m, n, e, more) =>
    `${n} 条记忆，${e} 条关联${more ? "（只显示最近的，还有更多）" : ""}。`],
  [/^(derived from|about person|replaces) \((source event ids|about|replaces)\)$/, (m, type) => BRAIN_EDGES[type]],
  [/^(Status|Date|Saved): .+$/, (m) => m.replace(/Status: (\w+)/, (x, status) => `状态：${BRAIN_STATUS[status] || status}`)
    .replace(/Date: /g, "日期：").replace(/Saved: /g, "保存于：")],
  [/^(Plans|Commitments|Preferences|Health and constraints|Routines|Recent messages|People|Relationship|Milestones and dates|Other notes): (.*)$/s,
    (m, region, text) => `${ZH[region]}：${text}`],
];
const BRAIN_STATUS = { intended: "打算中", scheduled: "已安排", done: "已完成", cancelled: "已取消", superseded: "已被取代" };
const BRAIN_EDGES = { "derived from": "来自这条消息", "about person": "关于这个人", replaces: "取代了这条" };

let language = "en";
// Read now: memory.js removes the query string (with its single-use code) before the page finishes loading.
const ASKED = new URLSearchParams(location.search).get("lang");

function chooseLanguage() {
  const asked = ASKED;
  if (asked) {
    try { localStorage.setItem("membrain-lang", asked.toLowerCase().startsWith("zh") ? "zh" : "en"); } catch { /* ignore */ }
  }
  let saved = null;
  try { saved = localStorage.getItem("membrain-lang"); } catch { /* storage may be unavailable */ }
  const wanted = asked || saved || (navigator.language || "en");
  return wanted.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function translate(text) {
  if (language !== "zh" || typeof text !== "string") return text;
  const key = text.replace(/\s+/g, " ").trim();
  if (!key) return text;
  if (Object.prototype.hasOwnProperty.call(ZH, key)) {
    // Keep the surrounding spaces (they separate inline elements); the text itself may span several lines.
    return text.match(/^\s*/)[0] + ZH[key] + text.match(/\s*$/)[0];
  }
  for (const [pattern, render] of ZH_PATTERNS) {
    const match = key.match(pattern);
    if (match) return render(...match);
  }
  return text;
}

const ATTRIBUTES = ["placeholder", "aria-label", "title"];

function translateNode(node) {
  if (language !== "zh") return;
  if (node.nodeType === Node.TEXT_NODE) {
    if (node.parentElement?.closest(".user-text, pre, code, script, style")) return;
    const translated = translate(node.nodeValue);
    if (translated !== node.nodeValue) node.nodeValue = translated;
    return;
  }
  if (node.nodeType !== Node.ELEMENT_NODE || node.closest(".user-text")) return;
  for (const name of ATTRIBUTES) {
    const value = node.getAttribute(name);
    if (value) {
      const translated = translate(value);
      if (translated !== value) node.setAttribute(name, translated);
    }
  }
  for (const child of node.childNodes) translateNode(child);
}

function startTranslation() {
  language = chooseLanguage();
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  const toggle = document.createElement("button");
  toggle.id = "language";
  toggle.className = "link";
  toggle.textContent = language === "zh" ? "English" : "中文";
  toggle.addEventListener("click", () => {
    try { localStorage.setItem("membrain-lang", language === "zh" ? "en" : "zh"); } catch { /* ignore */ }
    const url = new URL(location.href);
    url.searchParams.delete("lang");
    location.replace(url.toString());
  });
  document.querySelector("header")?.append(toggle);
  if (language !== "zh") return;
  document.title = translate(document.title);
  translateNode(document.body);
  const original = window.confirm.bind(window);
  window.confirm = (message) => original(translate(message));
  new MutationObserver((changes) => {
    for (const change of changes) {
      if (change.type === "characterData") translateNode(change.target);
      else if (change.type === "attributes") translateNode(change.target);
      else for (const node of change.addedNodes) translateNode(node);
    }
  }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true,
    attributeFilter: ATTRIBUTES });
}

document.addEventListener("DOMContentLoaded", startTranslation);
