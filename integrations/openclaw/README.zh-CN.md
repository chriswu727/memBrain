# OpenClaw 的 memBrain 插件

为你的 [OpenClaw](https://github.com/openclaw/openclaw) 助手在它服务的每个渠道（WhatsApp、Telegram、Discord、iMessage 等）上提供长期记忆，它与 OpenClaw 自带的记忆并行工作，不占用记忆插槽。

你自己和助手的私聊，与同一台电脑上的 Claude Code、Codex 和 Hermes 共用你的记忆。助手在渠道上交谈的其他所有人，会按 OpenClaw 自己判定的记忆归属，在各自的对话里拥有独立的记忆；群里的陌生人既看不到你的笔记，也写不进去。旧版 OpenClaw 不提供记忆归属时，只要消息来自渠道上的发送者或会话，也会这样处理。无法对应到所属记忆的对话里调用记忆工具会被拒绝。

## 安装

需要 Gateway 的 `PATH` 中有 [uv](https://docs.astral.sh/uv/)。

```sh
curl -L https://github.com/chriswu727/memBrain/archive/refs/heads/main.zip -o membrain.zip
unzip -q membrain.zip 'memBrain-main/integrations/openclaw/membrain/*'
openclaw plugins install ./memBrain-main/integrations/openclaw/membrain --force --accept-capabilities
openclaw config set plugins.entries.membrain.hooks.allowConversationAccess true
```

OpenClaw 2026.10 在你接受本地插件声明的能力（`--accept-capabilities`）之前会拒绝安装，并要求任何读取提示词或回复的非内置插件都获得明确的会话访问授权。当前的 OpenClaw 版本需要 Node 24.22.1 或更高版本。首次加载时，插件会用 uv 安装 memBrain 运行时并在后台启动本地服务；就绪之前的对话照常进行，只是没有记忆。

## 功能

| OpenClaw hook | memBrain 行为 |
| --- | --- |
| `before_prompt_build` | 以 `appendSystemContext` 加入会话说明、已保存的笔记和早期消息（每个会话五分钟内保持不变，以便模型服务的提示词缓存生效），并以 `prependContext` 加入与本次请求相关的早期消息。暂存本次请求。 |
| `agent_end` | 对成功的运行，保存请求和最终的助手回复。 |
| 工具 | `membrain_note`、`membrain_search`（设置 `my_replies` 可检索助手自己之前的回复）、`membrain_boundary`、`membrain_pause`、`membrain_resume`、`membrain_consolidate`、`membrain_manner_feedback`、`membrain_persona`。 |

当用户有五条或更多早期消息等待索引时，会话说明会请模型调用一次 `membrain_consolidate`：第一次调用返回一批这样的消息、操作说明和一个 `reviewed_through` 编号；第二次调用传回检索线索和这个编号。memBrain 不为此调用任何模型，线索由 OpenClaw 自己的模型编写。

用户要求不要主动提起某个话题时，使用 `membrain_boundary`。它只作用于当前对话所属用户的记忆，支持任意语言的别名；除非用户主动提起，否则自动上下文和检索不会带出该话题。用户可在记忆页面移除边界。通过 `membrain_note` 的 `kind: "milestone", shared: true` 可记录共同经历，`affect` 可附上有来源依据的情绪记录。用户评价智能体的说话方式（太长、太正式、表情太多）时，`membrain_manner_feedback` 会报告反馈类型及其来源消息；同类评价累计三次后，用户可在记忆页面接受或拒绝对人设的修改。录制暂停时它不发送任何内容。

新的记忆会随机选用五个预设人设之一（沉稳 Steady、明快 Bright、冷幽默 Wry、温柔 Gentle、直率 Blunt），会话说明会请智能体在第一条回复里提一次。`membrain_persona` 可列出预设人设、在用户要求时切换（并附上用户的消息），也可以提议修改人设，只有用户在之后的消息里同意才会保存。memBrain 没有为 OpenClaw 提供这方面的斜杠命令：用户直接用文字提出即可。切换只改变智能体的表现方式，模拟心情和熟悉程度都会保留。录制暂停时拒绝所有修改操作。

设置插件的 `directory` 可以让这个助手的记忆与其他宿主分开。`membrain plugin ui` 可打开记忆页面；`<private>…</private>` 中的文字和看起来像凭据的内容永远不会被保存。

## 状态

插件逻辑已用 Node 针对真实的 memBrain 运行时测试：两个会话共享记忆、笔记、检索和暂停。清单文件按 OpenClaw 的插件文档和源码编写。在 Windows 11 上，真实的 OpenClaw 2026.10.8 Gateway（模型为 DeepSeek V4 Pro）用上面的命令加载了它：hook 保存了每一轮对话，模型用 `membrain_note` 保存了笔记；在关闭 OpenClaw 自带的 `memory-core` 插件、且工作区文件中没有该事实的情况下，新会话召回了之前会话中告知的车牌号和车位。尚未在消息渠道上运行。
