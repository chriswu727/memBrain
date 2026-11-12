# memBrain 记忆代理（适用于任何可设置 `base_url` 的机器人）

很多机器人通过 OpenAI 兼容接口调用模型：基于 NoneBot、Koishi 或 LangBot 的 QQ 机器人，读取抖音或 B 站直播弹幕的 AI 虚拟主播，SillyTavern，Discord 和 Telegram 机器人，以及大多数接入 DeepSeek 的方案。`membrain proxy` 位于机器人和模型服务之间，为每一个和机器人聊天的人提供独立的长期记忆，无需修改机器人本身。

## 启动

```sh
uv tool install --python 3.12 'membrain-ai[embedded,semantic] @ https://github.com/chriswu727/memBrain/archive/refs/heads/main.zip'
membrain proxy --upstream https://api.deepseek.com/v1
```

`--upstream` 填机器人原来使用的 `base_url`（DeepSeek、OpenAI、硅基流动、本地 Ollama 或 vLLM 等）。然后只需把机器人的 `base_url` 改成 `http://127.0.0.1:8790/v1`，API key 和模型名保持不变。首次启动会创建本地数据库；记忆保存在 memBrain 的数据目录（或 `--directory` 指定的目录）。

## 区分不同的人

代理按以下方式区分记忆：

1. `X-Membrain-User` 请求头，或
2. chat-completions 请求中标准的 `user` 字段（很多机器人和 SDK 都可以设置，例如 `user="qq:12345"`）。

可选请求头：`X-Membrain-Platform`（例如 `bilibili`）、`X-Membrain-Group`（群或直播间；默认一个人在群里的记忆与私聊分开，可用 `--group-memory shared` 改为共用）、`X-Membrain-Session`（你自己的会话 ID；默认同一聊天的一天为一个会话）。没有用户标识的请求共用一份记忆，适合个人陪伴聊天。

用于角色扮演（SillyTavern 等）时，发送 `X-Membrain-Roleplay: <角色名>`：这个故事会有自己的记忆，永远不会和这个人的真实生活记忆混在一起。再加上 `X-Membrain-Share-Real-Life: 1`，可以在故事中同时看到这个人的真实生活笔记（标记为敏感的除外）。

## 对每个请求做了什么

对 `POST /v1/chat/completions`，代理把一段带标记的记忆放在这个人最新一条消息的开头（不是 system 消息，因此记住的内容不会带有机器人自身指令的权威），内容是记忆说明、他在其他日子发过的消息，以及与当前消息相关的早期消息。对话开头保持不变，因此模型服务（包括 DeepSeek）的提示词缓存仍然有效。回复返回后（流式或非流式），代理保存这个人的消息和回复。其他所有接口原样转发。

代理不会添加工具，因此模型无法通过它记笔记或暂停记录；`<private>…</private>` 中的文字以及看起来像密钥或密码的内容仍然不会被保存。

## 用你指定的模型生成笔记（可选）

**已冻结：** 用单独模型提取笔记（由 memBrain 自己调用该模型）的功能已冻结，不属于产品主线；除非设置了 `MEMBRAIN_EXTRACT_MODEL`，否则不会开启，已有配置在移除之前仍可继续使用。

代理不提供工具，所以机器人自己的模型无法保存笔记。如果想让用户也有笔记、计划和人物，可以指定一个便宜的模型来提取笔记：

```sh
export MEMBRAIN_EXTRACT_MODEL=deepseek-chat        # 开启提取
export MEMBRAIN_EXTRACT_KEY=sk-你的模型服务key       # 默认使用 MEMBRAIN_UPSTREAM_KEY
# MEMBRAIN_EXTRACT_BASE_URL 默认与 --upstream 相同
```

每次回复发出后，提取模型会读一遍这轮对话和这个人现有的笔记，把其中长期有用的事实保存为带类型的笔记，并替换被更新的旧笔记。它在后台运行，会跳过寒暄和道谢（“已取消”这类简短的更新会连同上一轮对话一起读），暂停记录期间不会运行；每条值得读的消息多一次模型调用。提取出的笔记关联到它来自的消息，删除这些消息时笔记也会一起删除。模型服务的临时错误会重试两次；仍然失败的那一轮会被跳过，`membrain plugin status`、`membrain doctor` 和记忆页面会显示有多少条消息没能提炼成笔记以及最近的错误。消息本身始终会被记录。排队中的轮次只保存在内存里，代理停止时还没读到的轮次不会再读。

## 代理会拒绝什么

没有设置令牌时，代理只响应发给 `localhost`、`127.0.0.1` 或 `::1` 的请求，因此把自己的域名指向你电脑的网页无法使用它。浏览器代表其他网站发出的请求（`Origin` 不是本机）以及不是 `application/json` 的聊天请求也会被拒绝。如果某个网页前端直接从浏览器调用代理，请把它的来源加入 `MEMBRAIN_PROXY_ORIGINS`（用逗号分隔，例如 `http://localhost:8000,https://chat.example.com`）。超过 32 MB 的请求体会被拒绝。

能访问代理的每个客户端都可以通过 `user` 或 `X-Membrain-User` 选择使用谁的记忆。只把你自己控制的机器人指向它；在令牌模式下，令牌就等于能访问所有人的记忆。

## 供其他机器使用

默认情况下代理只监听本机，并转发机器人发送的 API key。若要让其他机器上的机器人使用，请把模型服务的 key 保存在代理上，并给机器人一个单独的令牌：

```sh
export MEMBRAIN_UPSTREAM_KEY=sk-你的模型服务key
export MEMBRAIN_PROXY_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
membrain proxy --upstream https://api.deepseek.com/v1 --host 0.0.0.0
```

之后机器人把这个令牌当作 API key 使用。没有这两项设置时，代理拒绝监听本机以外的地址，否则任何能访问它的人都可能读取记忆。

有多个机器人时，改为给每个机器人一个独立的令牌和命名空间，这样一个机器人的令牌永远读不到另一个机器人的用户：

```sh
export MEMBRAIN_PROXY_TOKENS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))'):qq,$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))'):douyin"
```

每一项是 `令牌:命名空间`。机器人指明的用户都限定在它自己的命名空间里，即使它在 `X-Membrain-Platform` 里填了别的平台也一样；没有指明用户的请求会被拒绝，而不是落进一份共享的记忆。

## 查询一轮对话是否已记录

每个聊天补全的响应都带有 `X-Membrain-Exchange` 响应头，响应正文不变。用同样的令牌和用户身份向代理查询：

```bash
curl -H "X-Membrain-User: 12345" http://127.0.0.1:8790/v1/membrain/recording-outcomes/<exchange>
curl -H "X-Membrain-User: 12345" http://127.0.0.1:8790/v1/membrain/recording-outcomes   # 当前会话最近的几轮
```

请带上与聊天请求相同的 `X-Membrain-Platform`、`X-Membrain-Group`、`X-Membrain-Roleplay` 和 `X-Membrain-Session` 请求头（用户也可以用 `?user=` 指定）。每条消息的结果是 `recorded`（记忆服务已确认保存）、`queued`（已保存在本机，服务端是否保存尚未确认）、`excluded`（因暂停或策略未记录，并给出范围）、`failed` 或 `unknown`，同时给出观察到该结果的时间；流式回复在流结束前为 `awaiting_completion`。这是最后一次观察到的结果，不是实时检查，也不说明你的机器人是否把回复发了出去。查询别人的或另一个令牌的对话会得到 404，与从未存在的对话没有区别。查询只读取本机记录：不会保存、重试任何内容，也不会请求模型服务。如果某个说话人的内容本来就不记录（例如关闭了群聊记录），响应里不会有这个响应头。运营者也可以运行 `membrain plugin outcome --platform <平台> --user <用户>`。细节与保留期限见[参考文档](../../docs/reference.md#looking-up-a-recording-outcome)。

## 删除或导出某一个人的记忆

`membrain plugin export-user` 和 `membrain plugin forget-user` 按代理看到的身份指定这个人：`--platform` 是 `X-Membrain-Platform` 的值（默认 `api`；使用 `MEMBRAIN_PROXY_TOKENS` 时是 `命名空间/平台`），`--user` 是请求里的 `user`。群的记忆再加上 `--group`。

## 状态

已使用模拟的模型服务和真实的 memBrain 服务测试（两位直播观众跨天互相隔离、流式与非流式回复、令牌模式），并作为真实进程用 HTTP 客户端测试过。在 Windows 11 上已接入真实的 DeepSeek API（`deepseek-chat` 和推理模型 `deepseek-v4-pro`）运行：流式和非流式回复都原样转发（包括推理内容分片），用 `X-Membrain-User` 区分的两个人在之后的会话中各自召回了自己的信息、看不到对方的内容，`/v1/models` 和模型服务的错误也会被转发。尚未配合具体的机器人项目运行。
