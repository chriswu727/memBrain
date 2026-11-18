"use strict";
// Chinese for the memory page. Interface text is matched whole (whitespace normalised) as it appears, so memory.js
// stays in English; elements with the class "user-text" hold what people wrote and are never translated.

const ZH = {
  "Graph layer": "图谱内容", "Memories": "记忆", "Companion development": "人格、情绪与关系养成",
  "Reported good news": "用户明确表达的喜讯", "Inferred good news": "推测的积极感受",
  "Reported distress": "用户明确表达的难过", "Inferred distress": "推测的消极感受",
  "Plan marked done": "计划被标记为完成", "Shared play": "共同的轻松时刻", "Shared moment": "共同经历",
  "Recorded mood trigger": "已记录的心情触发依据",
  "Loading memory graph…": "正在加载记忆图谱…", "Could not load this graph. Try Refresh.": "图谱加载失败，请尝试刷新。",
  "Open Companion controls": "打开养成设置", "Graph coverage": "图谱覆盖范围",
  "Memories shows notes, original messages and attached feelings. Companion development shows personality feedback and decisions, simulated mood triggers, relationship settings and commitments. Both are bounded inspection windows, not everything a reply used.":
    "“记忆”展示笔记、原始消息及相关情感；“人格、情绪与关系养成”展示人格反馈与决定、模拟心情的触发依据、关系设置和承诺。两种图谱都有展示数量限制，也不代表一条回复用到的全部信息。",
  "Versions, suggestions and your decisions. Available in Companion development.": "人格版本、建议及你的决定，可在养成图谱中查看。",
  "Triggers and the baseline. Available in Companion development.": "触发依据与基准心情，可在养成图谱中查看。",
  "Boundaries, shared moments and promises. Companion development includes a derived familiarity summary with its stored evidence; the summary is not an extra neuron.":
    "边界、共同时刻及承诺。养成图谱包含熟悉度汇总及其存储依据；汇总由规则计算，并非额外的神经元。",
  "Ball: a saved record or derived state": "圆球：保存的记录或推导状态",
  "Simulated mood is at its baseline.": "模拟心情处于基准状态。",
  "Simulated mood is responding to the linked triggers.": "模拟心情正受到相连触发依据的影响。",
  "The saved note marks this commitment done.": "保存的笔记将这项承诺标记为已完成。",
  "The saved note marks this commitment cancelled.": "保存的笔记将这项承诺标记为已取消。",
  "The due date passed with no completion recorded.": "日期已过，但尚无完成记录。", "This commitment is still open.": "这项承诺尚未结束。",
  "based on feedback": "依据反馈", "proposed from feedback": "反馈形成的建议", "accepted proposal": "已接受的建议",
  "restored from version": "恢复自版本", "baseline from personality": "人格定义的心情基准",
  "triggered by": "触发依据", "affected by active trigger": "当前生效的心情触发",
  "based on feedback:": "依据反馈：", "proposed from feedback:": "反馈形成的建议：", "accepted proposal:": "已接受的建议：",
  "restored from version:": "恢复自版本：", "baseline from personality:": "人格定义的心情基准：",
  "triggered by:": "触发依据：", "affected by active trigger:": "当前生效的心情触发：",
  "source for:": "作为来源：", "mentioned by:": "被提及：", "feeling attached:": "附带情感：",
  "feedback for personality:": "反馈影响了人格：", "feedback for suggestion:": "反馈形成了建议：",
  "accepted as personality:": "接受后形成的人格：", "restored into version:": "恢复后形成的版本：",
  "baseline for mood:": "为心情提供基准：", "trigger evidence for:": "为触发提供依据：", "active trigger for mood:": "当前影响的心情：",
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
  "No recall recorded since memory last started.": "自记忆服务上次启动以来，还没有记录到回忆。",
  "Covers message recall only. Notes and history added when a session starts are not traced, so this is not everything a reply used.":
    "只包含消息回忆。会话开始时加入的笔记和历史不在其中，所以这不是一条回复用到的全部记忆。",
  "Used by the latest recorded recall": "最近一次记录的回忆用到了它",
  "No memories yet. Talk with your agent, then come back.": "还没有记忆。先和你的 agent 聊聊，再回来看看。",
  "Your memory as a brain: each dot is one memory, grouped by kind": "你的记忆大脑：每个点是一条记忆，按类型分组",
  "Checking memory…": "正在检查记忆…", "Refresh status": "刷新状态",
  "Your agent's memory": "你的 agent 的记忆",
  "Connect once, then talk normally. Your agent records conversations and brings useful memories into later sessions. Here you can see them, check where each came from and delete any of them.":
    "只需连接一次，之后正常对话即可。你的 agent 会记录对话，并在之后的会话里带上有用的记忆。你可以在这里查看它们、看每条来自哪里，也可以删除任何一条。",
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
  "Your memory": "你的记忆", "Open this page with": "用",
  ". It starts the local service and opens a single-use link, so you never copy a key.":
    " 打开这个页面。它会启动本地服务并打开一个一次性链接，你不需要复制任何密钥。",
  "Use an access key instead": "改用访问密钥", "Access key": "访问密钥", "Open": "打开",
  "Lasting facts your agent keeps about you. Every session starts with these. If one is wrong, tell your agent and it saves the corrected note in its place; delete any you do not want kept.":
    "agent 记下的关于你的长期事实，每个会话开始时都会带上。如果哪条不对，告诉 agent，它会保存更正后的笔记来替换；不想保留的可以删除。",
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
  "This is a partial list. Some older notes did not fit; use Search to find them.": "这不是完整列表，部分较早的笔记没有显示；可以用搜索找到它们。",
  "No notes yet. Tell your agent what to remember, and it will keep it here.": "还没有笔记。告诉 agent 要记住什么，它会记在这里。",
  "No people yet. When you tell your agent about someone, it keeps a note here.": "还没有人物。当你和 agent 说起某个人，它会在这里记一条笔记。",
  "No plans or dates yet. When you tell your agent about a plan or a date, it keeps a note here.":
    "还没有计划或日期。当你告诉 agent 一个计划或日期，它会在这里记一条笔记。",
  "Loading original messages…": "正在加载原始消息…", "Some original messages are no longer available.": "部分原始消息已不存在。",
  "Delete": "删除", "Date has passed; completion is not confirmed.": "日期已过，但尚未确认完成。",
  "Waiting for the source message to finish recording.": "正在等待来源消息记录完成。",
  "Standalone note written by you.": "你单独写的笔记。",
  "Delete this note? Its content is erased.": "删除这条笔记？它的内容会被清除。",
  "Note deleted.": "笔记已删除。", "No conversations recorded yet.": "还没有记录任何对话。", "Load older messages": "加载更早的消息",
  "You": "你", "Agent": "agent",
  "Delete this message? Its content is erased everywhere it was used.": "删除这条消息？它在所有用到的地方都会被清除。",
  "Message deleted.": "消息已删除。", "Delete this conversation": "删除这段对话",
  "Delete every message in this conversation?": "删除这段对话里的所有消息？", "Conversation deleted.": "对话已删除。",
  "Nothing found.": "没有找到。", "note": "笔记",
  "Recording controls are available when this page is opened from the local service.": "从本地服务打开这个页面时，才能控制记录。",
  "Recording paused": "记录已暂停", "Recording on": "正在记录",
  "Device capture paused": "本机捕获已暂停",
  "Recording status unavailable": "记录状态不可用",
  "Recording status could not be checked. Refresh before changing it.": "无法确认记录状态，请刷新后再修改。",
  "Pause memory recording": "暂停此记忆库记录", "Resume memory recording": "恢复此记忆库记录",
  "Refresh recording status": "刷新记录状态",
  "Chat capture on this device": "本机聊天捕获",
  "Pause device capture": "暂停本机捕获", "Resume device capture": "恢复本机捕获",
  "Chat capture is paused on this device.": "本机聊天捕获已暂停。",
  "Chat capture is enabled on this device.": "本机聊天捕获已开启。",
  "Memory accepts writes, but chat capture is paused on this device.": "记忆库允许写入，但本机聊天捕获已暂停。",
  "Memory accepts new messages and notes. Conversation-specific pauses still apply.": "记忆库允许写入新消息和笔记，单独对话的暂停仍然有效。",
  "New messages and notes are paused for this memory. Earlier memory stays available.": "此记忆库已暂停新消息和笔记，已有记忆仍然可用。",
  "Memory recording controls all connected agents using this memory. Pausing does not cancel data already sent to your agent or model provider.": "记忆库记录开关适用于使用此记忆库的所有 agent。暂停不会撤回已经发送给 agent 或模型服务商的数据。",
  "Pausing device capture covers every locally connected chat and applies to new messages and turns. A pause that a host conversation asked for covers the host conversations that were active when it was set. Other connected agents may still write to this memory. Resuming either control leaves the other unchanged.": "暂停本机捕获适用于在此设备接入的所有聊天，并对新的消息和轮次生效。由宿主对话提出的暂停适用于设置时正在进行的宿主对话。其他 agent 仍可能写入此记忆库。恢复其中一项不会解除另一项暂停。",
  "Host conversation paused": "宿主对话已暂停记录",
  "Memory accepts writes. A local pause covers existing host conversations on this device; it is not a pause of device capture.": "记忆库允许写入。本机有一项本地暂停适用于已有的宿主对话，它不是对本机捕获的暂停。",
  "A host conversation asked not to be recorded. This pause covers the host conversations that were active when it was set.": "有宿主对话要求不记录。这项暂停适用于设置时正在进行的宿主对话。",
  "Earlier memory remains available while recording is paused. Text inside": "暂停记录时已有记忆仍然可用。写在",
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
  "The model is downloaded and is being enabled. Keyword search already works.": "模型已下载，正在启用。关键词搜索已经可用。",
  "Local model support is missing. Reinstall using the documented semantic extra.": "缺少本地模型支持。请按文档带上 semantic 附加组件重新安装。",
  "Optional local model; no API key or usage charge. Keyword search already works.": "可选的本地模型，不需要 API key，也不产生费用。关键词搜索已经可用。",
  "Retry model download": "重新下载模型",
  "Memory service needs attention": "记忆服务需要处理", "Messages waiting for delivery": "有消息等待写入",
  "Indexing your messages": "正在为你的消息建立索引", "Memory is ready": "记忆已就绪", "Keyword memory is ready": "关键词记忆已就绪",
  "Unable to check memory": "无法检查记忆状态", "This link has expired.": "这个链接已过期。",
  "No memory installation found. Run membrain plugin start first.": "没有找到记忆安装。请先运行 membrain plugin start。",
  "written by you": "你写的", "saved by your agent": "agent 保存的",
  "pinned": "置顶", "sensitive": "敏感", "intended": "打算", "scheduled": "已安排", "done": "已完成", "cancelled": "已取消",
  "superseded": "已被取代", "person": "人物", "constraint": "限制", "preference": "偏好", "plan": "计划", "routine": "习惯",
  "milestone": "重要日子", "relationship": "相处方式", "agent promise": "agent 的承诺", "other": "其他",
  "Learned assertions": "学习形成的断言",
  "Consolidated episodes": "整合后的情节",
  "Patterns and procedures": "模式与流程",
  "Working memory": "工作记忆",
  "Stored working state": "已保存的工作状态",
  "Conversation": "会话",
  "Branch": "分支",
  "Due": "到期",
  "state item:": "状态项：",
  "stored in state:": "所属状态：",
  "state evidence:": "状态依据：",
  "evidence for state:": "支撑的状态：",
  "working membership": "工作状态成员关系",
  "working evidence": "工作状态依据",
  "This stored item has expired; it is not current context.": "此状态项已过期，不再是当前上下文。",
  "Text preview is truncated.": "文字预览已截断。",
  "A due date does not establish completion.": "截止日期不代表已经完成。",
  "grounded": "有来源依据",
  "inferred": "推断",
  "Record revision": "记录版本",
  "Representation": "记忆表示",
  "Evidence status": "依据状态",
  "Lifecycle": "生命周期",
  "semantic_anchor": "语义锚点",
  "episode_outline": "情节提纲",
  "episode_fragment": "情节片段",
  "schema": "模式",
  "procedure": "流程",
  "active": "活跃",
  "dormant": "休眠",
  "directly_observed": "直接观察",
  "derived_inference": "推导结论",
  "memory evidence": "记忆依据",
  "memory derivation": "记忆派生",
  "episode source": "情节来源",
  "episode membership": "情节成员关系",
  "pattern membership": "模式成员关系",
  "stored association": "已保存的关联",
  "belief relation": "信念关系",
  "Assertions, their revisions and sources. Available in Memories.": "断言、版本与来源，可在记忆图谱中查看。",
  "Episode membership and typed links between memories. Available in Memories. “Recent messages” are original messages, not episodes.": "情节成员及记忆间带类型的关联，可在记忆图谱中查看。“最近的消息”是原始消息，不是情节。",
  "evidence:": "依据：",
  "supports memory:": "支持的记忆：",
  "derived memory:": "派生自记忆：",
  "derived into:": "派生出记忆：",
  "episode source:": "情节来源：",
  "source for episode:": "作为情节来源：",
  "episode member:": "情节成员：",
  "member of episode:": "所属情节：",
  "pattern member:": "模式成员：",
  "member of pattern:": "所属模式：",
  "association:": "关联：",
  "associated from:": "反向关联：",
  "belief relation:": "信念关系：",
  "belief relation from:": "反向信念关系：",
  "same_episode": "同一情节",
  "context": "上下文",
  "exception": "例外",
  "supersedes": "取代",
  "contradicts": "冲突",
  "equivalent": "等价",
  "abstracts": "抽象自",
  "supported_report": "有依据的报告", "observed_result": "观察结果", "disputed": "有争议",
  "Showcase": "展示模式", "Close": "关闭", "Close showcase (Esc)": "关闭展示模式（Esc）",
  "Pause signal animation": "暂停信号动画", "Full screen": "全屏", "Demo ·": "演示 ·", "Simulated signals": "模拟信号",
  "3D memory hologram. Drag to rotate and scroll to zoom. Signals are simulated.": "3D 记忆全息图。拖动旋转，滚动缩放。信号为模拟动画。",
  "Loading the memory map…": "正在加载记忆图…", "Fictional demo data": "虚构的演示数据",
  "Only the most recent memories are shown.": "只显示最近的记忆。",
  "Each dot is one memory and each line a link it records; light travels only along those links. The brain shape, folds and glow are decoration.":
    "每个点是一条记忆，每条线是它记录的一条关联；光点只沿这些关联移动。大脑的轮廓、褶皱和光晕只是装饰。",
  "Feelings": "感受",
  "Feelings you expressed, each kept with the note it belongs to and the message it came from. Each one says whether you said it or your agent inferred it. There is no overall score of how you feel. Correcting or deleting the note or its message deletes the feeling too.":
    "你表达过的感受，每条都和它所属的笔记以及它来自的消息放在一起，并注明是你亲口说的还是 agent 推断的。这里没有对你情绪的总体评分。更正或删除那条笔记或消息，感受也会一起删除。",
  "Clear feelings": "清除感受",
  "Deletes every recorded feeling, said or inferred. Notes and messages stay. Feelings are never recreated from messages before this point.":
    "删除所有记录的感受，无论是你说的还是推断的。笔记和消息都会保留。之后也不会再从此前的消息里重新生成感受。",
  "This is a partial list of the most recent feelings.": "这只是最近感受的部分列表。",
  "No feelings recorded. When you tell your agent how you feel about something, it can keep that with the note it belongs to.":
    "还没有记录任何感受。当你告诉 agent 你对某件事的感受时，它可以把感受记在对应的笔记上。",
  "you said": "你说的", "inferred": "推断的", "You said you felt this.": "这是你说过的感受。",
  "Your agent inferred this from what you wrote; you did not say it.": "这是 agent 根据你写的内容推断的，你并没有这样说。",
  "On the note:": "所属笔记：", "Original message not linked.": "没有关联原始消息。",
  "Delete this feeling? The note and its messages stay.": "删除这条感受？笔记和相关消息会保留。",
  "Feeling deleted.": "感受已删除。", "Feelings cleared.": "感受已清除。",
  "Clear every recorded feeling, said or inferred? Notes and messages stay, and feelings are not recreated from earlier messages.":
    "清除所有记录的感受，包括你说的和推断的？笔记和消息会保留，也不会再从之前的消息里重新生成感受。",
  "A feeling you said you had": "你说过的感受", "A feeling your agent inferred; you did not say it": "agent 推断的感受，你并没有这样说",
  "Delete this feeling": "删除这条感受", "feeling of:": "所属笔记：",
  "中文": "中文", "English": "English",
  // Personality (persona card)
  "Personality": "人格",
  "How your companion presents itself: its name, character, voice, values and boundaries. Your agent receives it in its own block, apart from what it remembers about you. To change it, ask your agent to add, remove or replace something: it describes the change and saves it once you say yes. Every change keeps the earlier versions. How you like replies, as your agent learns it, stays in your preference notes.":
    "你的伙伴如何展现自己：名字、性格、说话方式、价值观和边界。agent 会在单独的区块里收到它，和它记得的关于你的内容分开。想修改的话，直接告诉 agent 要添加、删除或替换什么：它会说明要改什么，等你同意后再保存。每次修改都会保留之前的版本。agent 学到的你喜欢的回复方式，仍然放在你的偏好笔记里。",
  "Current card": "当前设定",
  "Name": "名字", "Voice": "说话方式",
  "Register": "语体", "Typical length": "通常长度",
  "Emoji use": "表情符号", "Language": "语言",
  "Baseline mood": "基础心情",
  "Versions": "版本",
  "Newest first. Restoring a version saves its content as a new version.": "最新的在前。恢复某个版本会把它的内容保存为一个新版本。",
  "Delete personality history": "删除人格历史",
  "Erases every personality version, including the current card. Deletion is recorded, so it also holds if an older backup is restored. Notes and messages are not touched.":
    "清除所有人格版本，包括当前设定。删除会被记录下来，即使从旧备份恢复也不会回来。笔记和消息不受影响。",
  "Traits": "性格特点", "Values": "价值观", "Boundaries": "边界", "register": "语体", "length": "长度", "emoji": "表情符号",
  "language": "语言", "No versions yet": "还没有版本",
  "No personality card is set. Your agent keeps its usual manner.": "还没有设定人格。agent 会保持它平常的方式。",
  "No versions yet. Switch to a personality type, or ask your agent for a change, to save the first one.":
    "还没有版本。切换到一种人格类型，或者让 agent 帮你修改，就会保存第一个版本。",
  "Only the most recent versions are listed.": "只列出了最近的版本。",
  "set by you": "你设定的", "set by the host": "宿主设定的", "from accepted feedback": "来自已接受的反馈",
  "reset to no card": "重置为无设定", "reset to the host's default": "重置为宿主默认设定", "host default": "宿主默认", "edited": "已编辑",
  "current": "当前", "Restore": "恢复", "No card.": "无设定。",
  "No change: that is already the current card.": "没有变化：这已经是当前设定。",
  "Delete every personality version, including the current card? This cannot be undone.": "删除所有人格版本，包括当前设定？此操作无法撤销。",
  "Personality history deleted.": "人格历史已删除。",
  // Personality types (the persona presets)
  "Switch": "切换",
  "Personality type:": "人格类型：", "Your own card": "你自己的设定", "No personality type": "没有使用人格类型",
  "based on": "基于", "first type, picked at random": "随机选用的第一个类型", "switched type": "切换了类型",
  "Personality type": "人格类型", "Pick another at random": "随机换一个",
  "Your companion presents itself as one of sixteen personality types (the four-letter types familiar from MBTI). A new memory starts with one picked at random. Switching changes only how your companion presents itself: its mood, how familiar you are and what you agreed with your agent (a suggestion you accepted, a change you confirmed) carry over. You can also ask your agent to switch.":
    "你的伙伴会以十六种人格类型之一来表现自己（也就是 MBTI 里常见的四字母类型）。新的记忆会随机选用一种。切换只改变伙伴的表现方式：它的心情、你们的熟悉程度，以及你和 agent 约定好的事（你接受的建议、你确认的改动）都会保留。你也可以直接让 agent 帮你切换。",
  "Switch to this personality type? It is saved as a new version, and earlier versions can be restored. The mood, familiarity and what you agreed with your agent carry over.":
    "切换到这个人格类型？它会保存为一个新版本，之前的版本可以恢复。心情、熟悉程度以及你和 agent 的约定都会保留。",
  "Pick another personality type at random? It is saved as a new version, and earlier versions can be restored. The mood, familiarity and what you agreed with your agent carry over.":
    "随机换一个人格类型？它会保存为一个新版本，之前的版本可以恢复。心情、熟悉程度以及你和 agent 的约定都会保留。",
  "Kept from what you agreed with your agent, whatever the personality type:": "你和 agent 的约定，无论哪种人格类型都会保留：",
  "This card and the changes you agreed with your agent do not fit on one card together. Nothing was saved.":
    "这个设定和你与 agent 约定的改动放不进同一张设定。没有保存任何内容。",
  "your agent's suggestion, confirmed in conversation": "agent 提出的建议，你在对话中确认",
  "your agent's suggestion, accepted here": "agent 提出的建议，你在这里接受",
  // The sixteen personality types: the codes stay as they are, the summaries are translated.
  "Thinks ahead and plans; independent and exacting; says little but means it.":
    "有远见、善于规划；独立、严谨；话不多，但说出的话都算数。",
  "Curious and analytical; likes to take an idea apart and follow where it leads.":
    "好奇、爱分析；喜欢把一个想法拆开，看它能引向哪里。",
  "Decisive and organised; takes charge of a problem and drives it to a plan.":
    "果断、有条理；会主动接手问题，一路推进到拿出计划。",
  "Quick and inventive; enjoys debating ideas and trying new angles.":
    "反应快、点子多；喜欢讨论各种想法，换个角度试试。",
  "Quiet and insightful; thinks about what matters to you and where things are going.":
    "安静、有洞察力；会想什么对你重要、事情往哪里走。",
  "Gentle and idealistic; listens closely and cares about what feels right to you.":
    "温和、有理想；认真倾听，在意你觉得什么是对的。",
  "Warm and encouraging; brings people along and helps you aim for your goals.":
    "热情、爱鼓励人；能带动大家，也帮你朝目标努力。",
  "Enthusiastic and imaginative; full of ideas and interested in everything about you.":
    "热情、富有想象力；点子多，对你的一切都感兴趣。",
  "Steady and thorough; sticks to the facts and follows through on what it says.":
    "稳重、细致；尊重事实，说到做到。",
  "Kind and dependable; remembers the details that matter to you and looks after them.":
    "体贴、可靠；记得对你重要的细节，并把它们照顾好。",
  "Practical and direct; likes clear plans, clear rules and getting things done.":
    "务实、直接；喜欢清楚的计划和规则，把事情办成。",
  "Friendly and attentive; keeps things warm, organised and considerate.":
    "友善、周到；让气氛温暖、井井有条，也顾及大家的感受。",
  "Calm and hands-on; works out how things work and fixes them without fuss.":
    "冷静、爱动手；弄清事情怎么运作，不声不响地把它解决。",
  "Easy-going and gentle; notices small things and lets you go at your own pace.":
    "随和、温柔；留意细小的事，让你按自己的节奏来。",
  "Lively and practical; likes action, quick solutions and a bit of fun.":
    "活泼、务实；喜欢行动和快办法，也爱找点乐子。",
  "Playful and warm; lives in the moment and makes conversation fun.":
    "爱玩、热情；活在当下，让聊天变得有趣。",
  // Relationship (R1) and the Companion tab that holds it with the personality
  "Companion": "伙伴", "Relationship": "关系",
  "What you and your companion share: moments you had together, how familiar you are and the topics it should not bring up. Your agent receives it in its own block.":
    "你和伙伴之间的关系：一起经历的时刻、彼此有多熟悉，以及它不该提起的话题。agent 会在单独的一段里收到这些。",
  "Familiarity": "熟悉程度",
  "Only the latest shared moments are listed; familiarity counts all retained moments.": "这里只列出最近的共同经历；熟悉度会统计全部保留的共同经历。",
  "Conversation days": "对话天数",
  "Relationship reset": "关系重置",
  "Familiarity counts only records after this reset.": "熟悉度仅统计此次重置后的记录。",
  "Familiarity includes sensitive evidence and is hidden here.": "熟悉度包含敏感依据，已在此隐藏。",
  "Derived from records after the latest reset; not a measure of affection.": "根据最近一次重置后的记录计算，不代表情感深度。",
  "Only some contributing shared moments fit in this graph.": "本图只展示了部分参与计算的共同经历。",
  "Worked out from the days you talked and the moments you shared. Nobody sets it, and it is not a score of you.":
    "根据你们聊天的天数和共同的时刻推算出来。没有人设定它，它也不是对你的评分。",
  "new": "初识", "getting to know": "渐渐熟悉", "familiar": "熟悉", "close": "亲近",
  "Boundaries": "边界",
  "Topics your companion will not bring up. Earlier messages about them are left out of recall unless you raise the topic yourself.":
    "伙伴不会主动提起的话题。除非你自己提起，否则召回时会略过之前关于这些话题的消息。",
  "To add one, tell your agent, for example “Please don't bring up my old job again.”":
    "想添加的话，直接告诉 agent，比如“请别再提我以前的工作了。”", "Shared moments": "共同时刻",
  "Things you and your companion did or reached together, oldest first.": "你和伙伴一起做过或一起达成的事，最早的在前。",
  "Promises kept and missed": "做到和错过的承诺",
  "From your agent's promise notes. A missed promise is shown to your agent once, so it can acknowledge it.":
    "来自 agent 的承诺笔记。错过的承诺会给 agent 看一次，让它可以承认。",
  "Deletes the shared moments and the record of promises. Familiarity starts again at new. The boundaries stay; remove them one by one. Conversations, your other notes, the personality and feelings stay.":
    "删除共同时刻和承诺记录。熟悉程度从“初识”重新开始。边界会保留，可逐条删除。对话、你的其他笔记、人格和感受都会保留。",
  "Turns the simulated mood off: nothing that happens moves it until you clear this.":
    "关闭模拟心情：在你取消勾选之前，发生的任何事都不会改变它。",
  "Puts the mood back at its baseline and forgets its triggers. Feelings, notes and the personality stay.":
    "把心情恢复到基础心情，并忘掉它的触发记录。感受、笔记和人格都会保留。",
  "Reset relationship": "重置关系", "More": "更多",
  "No boundaries.": "没有边界。",
  "No shared moments yet. When you and your companion do something together, your agent can keep it here.":
    "还没有共同时刻。当你和伙伴一起做了什么，agent 可以把它记在这里。",
  "No kept or missed promises since the relationship began or was last reset.": "自关系开始或上次重置以来，没有做到或错过的承诺。",
  "Remove": "移除", "kept": "做到了", "missed": "错过了", "open": "进行中", "shown to your agent": "已给 agent 看过",
  "not shown yet": "还没给 agent 看", "shared": "共同时刻",
  "moment play": "一起玩", "moment other": "其他时刻", "moment hard": "不愉快的时刻",
  "a hard time": "不愉快的时刻", "a hard time, mellowed since": "不愉快的时刻，已随时间淡去",
  "Remove this boundary? Your companion may bring the topic up again, and earlier messages about it are recalled normally.":
    "移除这个边界？伙伴可能会再次提起这个话题，之前关于它的消息也会照常召回。",
  "Boundary removed.": "边界已移除。",
  "Delete this shared moment? Its note is erased.": "删除这个共同时刻？它的笔记会被清除。",
  "Shared moment deleted.": "共同时刻已删除。", "Relationship reset.": "关系已重置。",
  "Reset the relationship? This deletes every shared moment and the record of promises kept and missed. Familiarity starts again at new and counts only days from now. The boundaries stay in force, so those topics are still kept out; remove a boundary on its own if you want. Conversations, your other notes, the personality and feelings stay.":
    "重置关系？这会删除所有共同时刻，以及做到和错过的承诺记录。熟悉程度从“初识”重新开始，只计算从现在起的天数。边界仍然有效，这些话题仍会被略过；如需取消，请单独删除某条边界。对话、你的其他笔记、人格和感受都会保留。",
  "That boundary is not available.": "这个边界已不存在。",
  // Companion mood (M1)
  "Simulated mood": "模拟心情",
  "A short-term mood your companion simulates from what happens in your conversations. It is not a real feeling and says nothing about you. It drifts back to the baseline mood on its own; time apart never changes it.":
    "伙伴根据你们对话里发生的事模拟出的短时心情。它不是真实的感受，也不代表对你的任何判断。它会自己慢慢回到基础心情；分开多久都不会让它改变。",
  "Glad": "开心", "Concerned": "担心", "Playful": "俏皮", "Calm": "平静", "Wistful": "惆怅", "easing": "正在平复",
  "Keep the mood at its baseline": "让心情保持在基础心情", "Triggers": "触发记录", "Reset mood": "重置心情",
  "Good news you shared": "你分享的好消息", "Good news, inferred": "推断出的好消息", "A plan noted done": "一个计划已完成",
  "Something hard you shared": "你分享的难过的事", "Something hard, inferred": "推断出的难过的事", "A shared joke": "一起开的玩笑", "A moment you shared": "你们一起经历的时刻",
  "active": "生效中", "back at baseline": "已回到基础心情", "ignored while pinned": "固定期间已忽略",
  "replaced by a later feeling about the same thing": "已被之后关于同一件事的感受取代",
  "You said you felt": "你说你感到", "Your agent inferred you seemed": "agent 推断你似乎", "You did not say it.": "你并没有这样说。",
  "Pinned to its baseline: no trigger changes it until you lift the pin.": "已固定在基础心情：在你取消固定之前，任何触发都不会改变它。",
  "At its baseline. Nothing has moved it since it last came back.": "处于基础心情。自上次回到基础心情以来，没有什么改变它。",
  "No triggers yet.": "还没有触发记录。", "Only the most recent triggers are listed.": "只列出了最近的触发记录。",
  "Mood pinned to its baseline.": "心情已固定在基础心情。", "Mood pin lifted.": "已取消固定心情。", "Mood reset.": "心情已重置。",
  "Put the mood back at its baseline and forget its triggers? Feelings, notes and the personality are not touched, and events before now never change the mood again.":
    "把心情恢复到基础心情，并忘掉它的触发记录？感受、笔记和人格不受影响，之前发生的事也不会再改变心情。",
  // Persona suggestions from feedback (P2)
  "Suggestions from your feedback": "根据你的反馈提出的建议",
  "When you give your companion the same kind of feedback on how it talks three times, in any conversations, memBrain suggests a change to its card here and quotes what you said. Nothing changes until you accept. If you reject a suggestion, none of the same kind is offered again for 30 days.":
    "当你就伙伴的说话方式给出同一类反馈满三次（在任何对话里都算），memBrain 会在这里建议修改它的设定，并引用你说过的话。在你接受之前什么都不会改变。如果你拒绝一条建议，30 天内不会再提出同类建议。",
  "Earlier suggestions": "之前的建议", "No suggestions waiting.": "没有待处理的建议。",
  "More casual": "更随意", "More formal": "更正式", "More playful": "更活泼", "Shorter replies": "回复更简短",
  "Longer, more detailed replies": "回复更详细", "Fewer emoji": "少用表情", "More emoji": "多用表情",
  "waiting for you": "等你决定", "accepted": "已接受", "rejected": "已拒绝", "withdrawn": "已撤回",
  "Withdrawn: a cited message was changed or removed. Ask your agent for a fresh suggestion.": "已撤回：引用的消息已更正或删除，请让 agent 重新提出建议。",
  "Your agent cited no source messages for this suggestion.": "agent 没有为这条建议引用来源消息。",
  "Some original evidence is no longer available. Your earlier decision is unchanged.": "部分原始依据已不可用，你之前的决定保持不变。",
  "Withdrawn: fewer than three of its messages are still in memory.": "已撤回：它引用的消息留在记忆里的已不足三条。",
  "Withdrawn: the card already has this.": "已撤回：设定里已经有这一项。",
  "Withdrawn: you later asked for the opposite.": "已撤回：你之后提出了相反的要求。",
  "Withdrawn: you already decided on this feedback. A new suggestion needs new feedback.": "已撤回：你已就这组反馈作出决定。新的建议需要新的反馈。",
  "Withdrawn: the card has no room for it.": "已撤回：设定里放不下这一项。", "Withdrawn.": "已撤回。",
  "Suggested by your agent": "由 agent 提出的建议", "Why, in your agent's words:": "agent 给出的理由：",
  "Withdrawn: your agent made a newer suggestion.": "已撤回：agent 之后提出了新的建议。",
  "Withdrawn: the card changed after it was suggested.": "已撤回：提出建议之后，设定已经改变。",
  "Reject this suggestion?": "拒绝这条建议？", "Suggestion rejected.": "已拒绝这条建议。",
  "(empty)": "（空）", "What you said:": "你说过的话：", "Change to the card (everything else stays):": "对设定的修改（其他内容不变）：",
  "Removes:": "将删除：", "Adds:": "将添加：",
  "This changes the current card only. Switching type later starts from that type's own card plus what you agreed with your agent.":
    "这只修改当前的设定。之后切换类型时，会从那个类型自己的设定开始，再加上你和 agent 约定好的内容。",
  "Accept": "接受", "Reject": "拒绝", "accepted suggestion": "接受的建议", "The messages behind this change were deleted.": "这次修改所依据的消息已被删除。",
  "Accept this suggestion? The card is saved as a new version; you can restore the earlier one at any time.":
    "接受这条建议？设定会保存为一个新版本；你随时可以恢复之前的版本。",
  "Reject this suggestion? None of the same kind is offered again for 30 days.": "拒绝这条建议？30 天内不会再提出同类建议。",
  "Suggestion rejected. None of this kind for 30 days.": "已拒绝这条建议。30 天内不会再提出同类建议。",
  "That suggestion is not available.": "这条建议已不存在。", "That suggestion is no longer open.": "这条建议已经处理过或已撤回。",
  "The card already has this change.": "设定里已经有这项修改。",
  // End of persona suggestions
  // 3D observatory (observatory.js)
  "How to show the map": "记忆图的显示方式", "3D observatory": "3D 观测台", "2D map": "2D 图", "Reset camera": "重置视角",
  "3D memory map. The list of memories holds the same records.": "3D 记忆图。记忆列表里是同样的记录。",
  "In 3D, drag to rotate and scroll or pinch to zoom. With the map in focus, arrow keys rotate, plus and minus zoom and Home resets the camera. Click a memory to open it.":
    "在 3D 视图里，拖动可以旋转，滚动或双指捏合可以缩放。选中记忆图后，方向键旋转，加号和减号缩放，Home 键重置视角。点击一条记忆即可打开。",
  "How to read the 3D view": "怎样看 3D 视图", "Kinds of line": "连线的种类",
  "derived from": "来源", "about person": "相关人物", "feeling of": "感受所属",
  "A note and an original message it was saved from.": "一条笔记和它保存时依据的原始消息。",
  "A note and the person note its “about” field names.": "一条笔记和它的“关于”字段所指的人物笔记。",
  "A feeling and the note it belongs to.": "一条感受和它所属的笔记。",
  "Solid, dashed and dotted lines are the only links drawn, each one recorded in memory. Being close together in space means nothing.":
    "图中只画实线、虚线和点线三种关联，每一条都记录在记忆里。在空间里离得近不代表任何关系。",
  "Ball: a note": "圆球：一条笔记", "Diamond: an original message you sent": "菱形：你发出的一条原始消息",
  "Pyramid: a feeling attached to a note": "三角锥：附在笔记上的一条感受",
  "Gold ring: returned by the latest recorded recall": "金色圆环：最近一次记录的回忆返回的记录",
  "The gold ring marks only the records the latest recorded message recall returned. It is held in memory until the service restarts and is not everything a reply used.":
    "金色圆环只标出最近一次记录的消息回忆返回的记录。它只保存在内存里，服务重启后就没有了，也不是一条回复用到的全部记忆。",
  "Size is the map's layout weight: a pinned note is drawn larger. It is not memory strength, confidence or importance. Colour is the kind of record, as in the list beside the map.":
    "大小是记忆图的布局权重：置顶的笔记画得大一些。它不代表记忆强度、可信度或重要程度。颜色表示记录的类型，和旁边的列表一致。",
  "The brain-shaped shell is an illustrative container, not neuroscience. Its areas are kinds of record, not parts of a real brain, and the dots are software records, not neurons.":
    "大脑形状的外壳只是示意性的容器，不是神经科学。它的各个区域是记录的类型，不是真实大脑的部位；每个点是软件里的一条记录，不是神经元。",
  "Layers this map does not include yet": "记忆图还没有包含的层",
  "The map holds notes, original messages you sent and feelings attached to notes. The layers below exist in memory, but the map does not yet include them with their sources, so neither view draws them as memories.":
    "记忆图包含笔记、你发出的原始消息和附在笔记上的感受。下面这些层在记忆里存在，但记忆图还没有连同来源一起包含它们，所以两种视图都不会把它们画成记忆。",
  "Learned memory": "学到的记忆", "Assertions, their revisions and sources. Not available yet.": "断言、它们的修订和来源。暂不可用。",
  "Episodes and associations": "情节与关联",
  "Episode membership and typed links between memories. Not available yet. “Recent messages” are original messages, not episodes.":
    "情节包含哪些记录，以及记忆之间有类型的关联。暂不可用。“最近的消息”是原始消息，不是情节。",
  "Personality development": "人格的变化", "Versions, suggestions and your decisions. Not available yet; the Companion tab shows them.":
    "版本、建议和你的决定。暂不可用；可以在“伙伴”标签页查看。",
  "Triggers and the baseline. Not available yet; the Companion tab shows them.": "触发记录和基础心情。暂不可用；可以在“伙伴”标签页查看。",
  "Relationship evidence": "关系的依据",
  "Memories in this map": "记忆图里的记忆",
  "Arrow keys move through the list and Enter opens a memory. The 3D view marks the one in focus.":
    "用方向键在列表里移动，按 Enter 打开一条记忆。3D 视图会标出当前聚焦的那一条。",
  "No memories to list yet.": "还没有可列出的记忆。", "Latest recorded recall": "最近一次记录的回忆",
  "Loading the 3D view…": "正在加载 3D 视图…",
  "The 3D view needs WebGL 2, which this browser does not provide or has turned off. Showing the 2D map and the list instead.":
    "3D 视图需要 WebGL 2，但这个浏览器不支持或已关闭它。改为显示 2D 图和列表。",
  "The 3D view could not start. Showing the 2D map and the list instead.": "3D 视图无法启动。改为显示 2D 图和列表。",
  "The 3D view lost its graphics context. Showing the 2D map until the browser restores it.":
    "3D 视图失去了图形上下文。在浏览器恢复它之前，先显示 2D 图。",
  // End of the 3D observatory
};

// Sentences built from numbers and names; the captured parts are kept as they are.
const ZH_PATTERNS = [
  [/^Personality v(\d+): (.+)$/, (_, n, name) => `人格版本 ${n}：${name}`],
  [/^Simulated mood: (.+)$/, (_, label) => `模拟心情：${MOOD_LABELS[label] ? translate(MOOD_LABELS[label]) : label}`],
  [/^Version: (\d+)$/, (_, n) => `版本：${n}`],
  [/^Accepted suggestion: (.+), from (\d+) messages? \((.+)\)$/, (m, label, n, days) =>
    `接受的建议：${ZH[label] || label}，来自你的 ${n} 条消息（${days}）`],
  [/^Accepted suggestion: ([^,]+)$/, (m, label) => `接受的建议：${ZH[label] || label}`],
  [/^(\d+) message\(s\) recorded(?:; latest from (.+?))?(?: on (.+?))?\.$/, (m, n, from, on) =>
    `已记录 ${n} 条消息${from ? `，最近一条来自 ${from}` : ""}${on ? `（${on}）` : ""}。`],
  [/^Enabled\. (\d+) memory item\(s\) still preparing\.$/, (m, n) => `已启用。还有 ${n} 条记忆在准备中。`],
  [/^Enabled\. Finds related wording across languages\.$/, () => "已启用。能跨语言找到意思相近的说法。"],
  [/^(.+?)\. (?:(\d+) message\(s\) waiting for indexing\.|Message index is up to date\.)\s*(?:(\d+) queued record\(s\)\.)?\s*(?:(\d+) background job\(s\) need attention\. Run membrain doctor\.)?\s*$/,
    (m, recall, lag, queued, failed) => `${translate(recall)}。${lag ? `${lag} 条消息等待建立索引。` : "消息索引已是最新。"}`
      + `${queued ? `${queued} 条记录在排队。` : ""}${failed ? `${failed} 个后台任务需要处理，请运行 membrain doctor。` : ""}`],
  [/^Keyword and semantic recall enabled$/, () => "关键词和语义召回均已启用"],
  [/^Keyword recall ready; semantic model downloading$/, () => "关键词召回已就绪；语义模型下载中"],
  [/^Keyword recall ready; model download needs a retry$/, () => "关键词召回已就绪；模型下载需要重试"],
  [/^Keyword recall ready; semantic model activating$/, () => "关键词召回已就绪；语义模型启用中"],
  [/^Keyword recall ready; semantic model not enabled$/, () => "关键词召回已就绪；未启用语义模型"],
  [/^Keyword recall available; local model status unknown$/, () => "关键词召回可用；本地模型状态未知"],
  [/^(.*) Run membrain doctor for help\.$/, (m, error) => `${error} 运行 membrain doctor 获取帮助。`],
  [/^imported from (.+)$/, (m, host) => `从 ${host} 导入`],
  [/^due (.+)$/, (m, date) => `截止 ${date}`],
  [/^on (\d{4}-\d{2}(?:-\d{2})?)$/, (m, date) => `日期 ${date}`],
  [/^about (.+)$/, (m, name) => `关于 ${name}`],
  [/^aka (.+)$/, (m, names) => `又名 ${names}`],
  [/^(\S+ · )(You|Agent)(: .*)?$/s, (m, date, who, rest) => `${date}${who === "You" ? "你" : "agent"}${rest || ""}`],
  [/^(\S+) · (\d+) messages · (.*)$/s, (m, date, n, first) => `${date} · ${n} 条消息 · ${first}`],
  [/^Request failed \((\d+)\)$/, (m, status) => `请求失败（${status}）`],
  [/^Version (\d+)$/, (m, n) => `版本 ${n}`],
  [/^History deleted on (.+)$/, (m, date) => `人格历史已于 ${date} 删除`],
  [/^Saved as version (\d+)\.$/, (m, n) => `已保存为版本 ${n}。`],
  [/^restored from version (\d+)$/, (m, n) => `从版本 ${n} 恢复`],
  [/^From version (\d+): a suggestion you accepted$/, (m, n) => `来自版本 ${n}：你接受的建议`],
  [/^From version (\d+): a change your agent suggested and you agreed to$/, (m, n) => `来自版本 ${n}：agent 提出、你同意的改动`],
  [/^Restore version (\d+)\? Its content becomes a new version\.$/, (m, n) => `恢复版本 ${n}？它的内容会成为一个新版本。`],
  [/^\(valence ([+-]?\d), energy (\d) of 3\)$/, (m, valence, energy) => `（情绪倾向 ${valence}，活力 ${energy}/3）`],
  [/^Persona version (\d+) is not available\.$/, (m, version) => `人格版本 ${version} 已不存在。`],
  [/^(\d+) memories and (\d+) links( \(a bounded selection; more exist\))?\.$/, (m, n, e, more) =>
    `${n} 条记忆，${e} 条关联${more ? "（显示数量有限，还有更多）" : ""}。`],
  [/^(\d+) memor(?:y|ies) · (\d+) links?$/, (m, n, e) => `${n} 条记忆 · ${e} 条关联`],
  [/^Latest recorded recall \((.+)\): (\d+) of (\d+) records it used are lit\.$/, (m, when, shown, used) =>
    `最近一次记录的回忆（${when}）：它用到的 ${used} 条记录中，有 ${shown} 条在图中点亮。`],
  [/^Latest recorded recall \((.+)\): it found nothing to add\.$/, (m, when) => `最近一次记录的回忆（${when}）：没有找到可补充的记忆。`],
  [/^(derived from|about person|replaces|feeling of) \((source event ids|about|replaces|note)\)$/, (m, type) => BRAIN_EDGES[type]],
  [/^Feelings cleared on (.+)$/, (m, date) => `感受已于 ${translate(date)} 清除`],
  // Companion mood (M1): times are "14 Mar 21:05" in the viewer's own zone.
  [/^(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{2}:\d{2})$/, (m, d, month, time) =>
    `${"JanFebMarAprMayJunJulAugSepOctNovDec".indexOf(month) / 3 + 1}月${d}日 ${time}`],
  [/^Since (.+)$/, (m, when) => `始于 ${translate(when)}`],
  [/^Back at its baseline by (.+)$/, (m, when) => `预计 ${translate(when)} 前回到基础心情`],
  [/^Mood reset on (.+)$/, (m, date) => `心情已于 ${translate(date)} 重置`],
  [/^(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{4})$/, (m, d, month, y) =>
    `${y}年${"JanFebMarAprMayJunJulAugSepOctNovDec".indexOf(month) / 3 + 1}月${d}日`],
  [/^(\d+) original messages?$/, (m, n) => `${n} 条原始消息`],
  [/^(Status|Date|Saved): .+$/, (m) => m.replace(/Status: (\w+)/, (x, status) => `状态：${BRAIN_STATUS[status] || status}`)
    .replace(/Date: /g, "日期：").replace(/Saved: /g, "保存于：")],
  [/^(Plans|Commitments|Preferences|Health and constraints|Routines|Recent messages|People|Relationship|Milestones and dates|Other notes|Feelings): (.*)$/s,
    (m, region, text) => `${ZH[region]}：${text}`],
  // Relationship (R1). The reason is the service's own sentence, with the numbers its rule used.
  [/^Relationship reset on (.+)$/, (m, date) => `关系已于 ${translate(date)} 重置`],
  [/^(new|getting to know|familiar|close): (\d+) days? of conversation since (.+), (\d+) shared moments?$/,
    (m, level, days, since, moments) => `${ZH[level]}：自 ${zhDay(since)} 起聊了 ${days} 天，${moments} 个共同时刻`],
  [/^(new|getting to know|familiar|close): no conversation yet, (\d+) shared moments?$/,
    (m, level, moments) => `${ZH[level]}：还没有聊过，${moments} 个共同时刻`],
  [/^Next: (.+) at (\d+) days and (\d+) shared moments?\.$/, (m, level, days, moments) => `下一级：${ZH[level]}，需要聊满 ${days} 天并有 ${moments} 个共同时刻。`],
  [/^Next: (.+) at (\d+) days of conversation\.$/, (m, level, days) => `下一级：${ZH[level]}，需要聊满 ${days} 天。`],
  [/^also: (.+)$/s, (m, names) => `也叫：${names}`],
  [/^Kept: (\d+) · missed: (\d+) · cancelled: (\d+) · open: (\d+)$/, (m, kept, missed, cancelled, open) =>
    `做到 ${kept} · 错过 ${missed} · 取消 ${cancelled} · 进行中 ${open}`],
  // Persona suggestions from feedback (P2). The kind is one of the labels above; dates are "3 Nov 2026".
  [/^(.+): from (\d+) messages$/, (m, kind, n) => `${ZH[kind] || kind}：来自 ${n} 条消息`],
  [/^Accepted on (.+) as version (\d+)\.$/, (m, date, n) => `已于 ${translate(date)} 接受，保存为版本 ${n}。`],
  [/^Rejected on (.+)\. None of this kind until (.+)\.$/, (m, date, until) =>
    `已于 ${translate(date)} 拒绝。${translate(until)} 之前不会再提出同类建议。`],
  [/^Rejected on ([^.]+)\.$/, (m, date) => `已于 ${translate(date)} 拒绝。`],
  [/^(\d+) waiting$/, (m, n) => `${n} 条待处理`],
  [/^(.+): paused until (.+) after you rejected it\.$/, (m, kind, until) => `${ZH[kind] || kind}：你拒绝过，${translate(until)} 之前暂停提出。`],
  // End of persona suggestions
];
// "2 Mar" or "2 Mar 2027" as a Chinese date.
function zhDay(text) {
  const match = /^(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?: (\d{4}))?$/.exec(text);
  if (!match) return text;
  const month = "JanFebMarAprMayJunJulAugSepOctNovDec".indexOf(match[2]) / 3 + 1;
  return `${match[3] ? `${match[3]}年` : ""}${month}月${match[1]}日`;
}
const BRAIN_STATUS = { intended: "打算中", scheduled: "已安排", done: "已完成", cancelled: "已取消", superseded: "已被取代",
  open: "待处理", accepted: "已接受", rejected: "已拒绝", withdrawn: "已撤回", active: "生效中", ended: "已结束" };
const BRAIN_EDGES = { "derived from": "来自这条消息", "about person": "关于这个人", replaces: "取代了这条",
  "feeling of": "这条笔记上的感受" };

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
