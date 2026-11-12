# memBrain memory proxy (any bot with a `base_url`)

Many bots reach their model through an OpenAI-compatible API: QQ bots built on NoneBot, Koishi or LangBot, AI VTubers that read Douyin or Bilibili live comments, SillyTavern, Discord and Telegram bots, and most DeepSeek integrations. `membrain proxy` sits between such a bot and its model provider and gives every person who talks to the bot their own long-term memory, without changing the bot.

## Start it

```sh
uv tool install --python 3.12 'membrain-ai[embedded,semantic] @ https://github.com/chriswu727/memBrain/archive/refs/heads/main.zip'
membrain proxy --upstream https://api.deepseek.com/v1
```

`--upstream` is the `base_url` your bot used before (DeepSeek, OpenAI, SiliconFlow, a local Ollama or vLLM...). Then change only the bot's `base_url` to `http://127.0.0.1:8790/v1`; keep its API key and model name. The first start creates a local database; memory is kept in your memBrain data directory (or `--directory`).

## Telling people apart

The proxy separates memories by:

1. the `X-Membrain-User` header, or
2. the standard `user` field of the chat-completions request (many bots and SDKs can set it, e.g. `user="qq:12345"`).

Optional headers: `X-Membrain-Platform` (for example `bilibili`), `X-Membrain-Group` (a group or live room; by default a person's group memory is kept apart from their private chats, change with `--group-memory shared`), and `X-Membrain-Session` (your own conversation ID; by default one day of one chat is a session). Requests with no user share one memory, which suits a personal companion chat.

For role-play (SillyTavern and similar), send `X-Membrain-Roleplay: <character name>`: that story gets its own memory, which never mixes with the person's real-life memory. Add `X-Membrain-Share-Real-Life: 1` to also show the person's real-life notes in the story, except those marked sensitive.

## What it does to each request

For `POST /v1/chat/completions` it puts a fenced memory block at the start of the person's latest message (not in a system message, so remembered text never carries the bot's own authority), containing the memory notice, their earlier messages from other days, and older messages related to the current one. The start of the conversation is left untouched so the provider's prompt cache (DeepSeek's included) keeps working. After the reply arrives (streamed or not) it stores the person's message and the reply. Every other endpoint is forwarded unchanged.

The proxy does not add tools, so the model cannot write notes or pause recording through it; text inside `<private>…</private>` and values that look like keys or passwords are still never stored.

## Notes from a model of your choice (optional)

**Frozen:** note extraction with a separate model, in which memBrain calls that model itself, is frozen and outside the product's main line; it stays off unless you set `MEMBRAIN_EXTRACT_MODEL`, and existing setups keep working until it is removed.

The proxy adds no tools, so the bot's own model cannot save notes. To give people notes, plans and people anyway, name a cheap model for note extraction:

```sh
export MEMBRAIN_EXTRACT_MODEL=deepseek-chat        # turns extraction on
export MEMBRAIN_EXTRACT_KEY=sk-your-provider-key   # defaults to MEMBRAIN_UPSTREAM_KEY
# MEMBRAIN_EXTRACT_BASE_URL defaults to --upstream
```

After each reply has been sent, the extraction model reads that exchange once, together with the person's current notes, and saves the lasting facts as typed notes, replacing notes they update. It runs in the background, skips greetings and thanks (short updates such as "cancelled it" are read, together with the exchange before them), never runs while recording is paused, and costs one extra model call per message worth reading. Notes it saves are linked to the messages they came from, so deleting those messages deletes the notes. A provider error is retried twice when it is temporary; a turn that still fails is skipped. `membrain plugin status`, `membrain doctor` and the memory page then report how many messages were not read for notes and the last error. The messages themselves are always recorded. Queued turns are kept in memory only, so turns not yet read when the proxy stops are not read.

## What it refuses

Without a token the proxy answers only requests addressed to `localhost`, `127.0.0.1` or `::1`, so a web page that points its own domain at your computer cannot use it. It also refuses requests that a browser sends on behalf of another site (an `Origin` header that is not this computer) and chat requests that are not `application/json`. If a browser-based front end calls the proxy directly, add its origin to `MEMBRAIN_PROXY_ORIGINS` (comma-separated, for example `http://localhost:8000,https://chat.example.com`). Request bodies above 32 MB are refused.

Every client that can reach the proxy chooses whose memory it uses through `user` or `X-Membrain-User`. Only point bots you control at it, and in token mode treat the token as access to every person's memory.

## Serving other machines

By default the proxy listens only on this computer and forwards the API key your bot sends. To let bots on other machines use it, keep the provider key on the proxy and give the bots a separate token:

```sh
export MEMBRAIN_UPSTREAM_KEY=sk-your-provider-key
export MEMBRAIN_PROXY_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
membrain proxy --upstream https://api.deepseek.com/v1 --host 0.0.0.0
```

Bots then use the token as their API key. The proxy refuses to listen beyond this computer without both settings, because anyone who can reach it could otherwise read memories.

With more than one bot, give each its own token and namespace instead, so one bot's token can never read the people of another:

```sh
export MEMBRAIN_PROXY_TOKENS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))'):qq,$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))'):douyin"
```

Each entry is `token:namespace`. The people a bot names are kept inside its namespace, even if it sends another platform in `X-Membrain-Platform`, and a request that names nobody is refused instead of falling into a shared memory.

## Checking whether an exchange was recorded

Every chat completion answer carries an `X-Membrain-Exchange` response header; the body is unchanged. Ask the proxy about it with the same token and person:

```bash
curl -H "X-Membrain-User: 12345" http://127.0.0.1:8790/v1/membrain/recording-outcomes/<exchange>
curl -H "X-Membrain-User: 12345" http://127.0.0.1:8790/v1/membrain/recording-outcomes   # recent, current session
```

Send the same `X-Membrain-Platform`, `X-Membrain-Group`, `X-Membrain-Roleplay` and `X-Membrain-Session` headers as the chat request (the person can also be `?user=`). Each message is reported as `recorded` (the memory service confirmed it), `queued` (kept locally, server storage not yet confirmed), `excluded` (a pause or policy, with its scope), `failed` or `unknown`, with when that was observed; a streamed reply is `awaiting_completion` until the stream ends. This is the last observation, not a live check, and says nothing about whether your bot delivered the reply. Another person's or another token's exchange is a 404, the same as one that never existed. The lookup reads local records only: nothing is stored, retried or sent to the provider. The header is absent when nothing is recorded for that speaker (for example group recording turned off). The operator can run `membrain plugin outcome --platform <platform> --user <id>` instead. Details and retention: [reference](../../docs/reference.md#looking-up-a-recording-outcome).

## Erasing or exporting one person

`membrain plugin export-user` and `membrain plugin forget-user` take the person as the proxy sees them: `--platform` is the `X-Membrain-Platform` value (default `api`, or `namespace/platform` with `MEMBRAIN_PROXY_TOKENS`) and `--user` the request's `user`. Add `--group` for a group's memory.

## Status

Tested with a stand-in provider and a real memBrain service (two live-stream viewers kept apart across days, streaming and non-streaming replies, token mode), and as a running process with an HTTP client. On Windows 11 it ran against the real DeepSeek API (`deepseek-chat` and the reasoning model `deepseek-v4-pro`): streaming and non-streaming replies passed through unchanged (reasoning chunks included), two people told apart by `X-Membrain-User` each recalled their own facts in a later session and not the other's, and `/v1/models` and provider errors were forwarded. Not yet run with a specific bot project.
