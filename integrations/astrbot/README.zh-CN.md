# AstrBot 的 memBrain 插件

为每一个和你的 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 机器人聊天的人提供长期记忆。支持 QQ（NapCat／aiocqhttp、QQ 官方）、微信、Telegram、飞书、钉钉、Discord、Slack 等 AstrBot 支持的所有平台，以及任何模型服务（包括 DeepSeek）。记忆保存在机器人所在的机器上，不需要额外的 API key。

## 安装

把插件复制到 AstrBot 的插件目录，然后重启 AstrBot（或在管理面板中重载插件）。AstrBot 加载插件时会按 `requirements.txt` 自动安装 Python 依赖。

```sh
cd AstrBot/data/plugins     # Docker 部署时为挂载的 data/plugins 目录
curl -L https://github.com/chriswu727/memBrain/archive/refs/heads/main.zip -o membrain.zip
unzip -q membrain.zip 'memBrain-main/integrations/astrbot/astrbot_plugin_membrain/*'
mv memBrain-main/integrations/astrbot/astrbot_plugin_membrain . && rm -rf memBrain-main membrain.zip
```

首次启动会在 AstrBot 的 `data/plugin_data/membrain` 中创建本地 PostgreSQL 数据库，因此容器升级后记忆仍然保留，并会包含在 AstrBot 的数据备份中。需要 Linux x86_64、macOS 或 Windows；暂不支持 ARM Linux（例如树莓派）。

## 功能

- **每次请求模型前**，在系统提示词末尾加入：机器人为这个人保存的笔记、他在之前几天发过的消息，以及与当前消息相关的早期消息。
- **每次回复后**，保存这个人的消息和机器人的回复。
- **给模型的工具**：`membrain_note`（记下一条持久事实，并可替换过时的笔记）、`membrain_search`、`membrain_boundary`（此人要求不要主动提起的话题）、`membrain_pause` 和 `membrain_resume`（当有人说“别记这个”时使用）。

话题边界支持任意语言的别名，与笔记采用相同的用户和群聊隔离。除非此人主动提起，否则自动上下文和检索不会带出该话题；用户可在记忆页面移除边界。通过笔记的 `kind: "milestone", shared: true` 可记录共同经历，`affect` 可附上有来源依据的情绪记录。

每个人的记忆彼此独立：Alice 告诉机器人的事，永远不会出现在给 Bob 的回复里。默认情况下，一个人在群里说的话也与他的私聊分开保存，因此群聊回复不会泄露私聊内容。

## 设置

| 设置 | 默认值 | 含义 |
| --- | --- | --- |
| `group_memory` | `separate` | 设为 `shared` 时，一个人的群聊消息和私聊共用同一份记忆。 |
| `record_groups` | 开 | 关闭后，群消息既不召回也不保存。只有到达模型的消息（例如 @ 机器人时）才会被看到。 |
| `roleplay_character` | 空 | 如果机器人扮演一个虚构角色，填写角色名：故事的记忆会与每个人的真实生活记忆分开保存。 |
| `share_real_life` | 关 | 在角色扮演中显示每个人的非敏感真实生活笔记，并标明是真实生活。 |
| `directory` | 空 | 记忆保存位置；留空即 `data/plugin_data/membrain`。 |

用 `<private>…</private>` 包住的文字不会被记住；看起来像密码、API key 或 token 的内容会在保存前被移除。

## 机器人的模型不支持工具调用时

插件会给 AstrBot 的模型提供 `membrain_note` 工具。如果你用的模型不会调用工具，请填写三个提取设置（一个 OpenAI 兼容模型的名称、地址和 key，例如 `deepseek-chat`）：每次回复后，这个模型会把这轮对话读一遍，把长期有用的事实保存为笔记。每条值得读的消息多一次模型调用。

## 删除或导出某一个人的记忆

用户自己发送 `/membrain_forget confirm` 就能删除机器人记住的关于他的内容（这是用户发的命令，模型无法被诱导去执行）。作为运营者，你可以在命令行删除或导出任意一个人的记忆：

```sh
membrain plugin export-user --directory <数据目录>/membrain --platform aiocqhttp --user 1001 --out alice.json
membrain plugin forget-user --directory <数据目录>/membrain --platform aiocqhttp --user 1001
```

群聊里留下的记忆加上 `--group <群号>`。删除会永久清除内容，包括还在排队的记录；从备份恢复也不会让它回来。导出文件里有这个人的原始消息，请妥善保存。

## 状态

已使用 AstrBot 插件 API 的替身和真实的 memBrain 服务测试（两个 QQ 用户互相隔离、群聊与私聊隔离、暂停记录），工具的文档字符串也已按 AstrBot 的参数格式检查。在 Windows 11 上，它已在 AstrBot 4.29.3（源码安装，Python 3.12）中配合 DeepSeek、通过 AstrBot 自带的 WebChat 实际运行：AstrBot 按 `requirements.txt` 安装了依赖，首次启动在 `data/plugin_data/membrain` 中创建了记忆，模型通过插件工具保存了笔记并进行了检索，两个用户各自在新对话中召回了自己的信息，且互相看不到对方的内容。这次运行发现了一个会让每次首次启动都失败的问题（已修复）。尚未通过 NapCat 接入 QQ 测试。
