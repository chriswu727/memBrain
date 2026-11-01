# Security

memBrain is pre-release software. Please report vulnerabilities privately through [GitHub security advisories](https://github.com/chriswu727/memBrain/security/advisories/new) rather than in a public issue. Include the version or commit, the host you use (Claude Code, Codex, OpenClaw, Hermes, AstrBot, the proxy), and steps to reproduce. Only the latest commit on `main` receives fixes until a release is published.

## What memBrain protects

memBrain stores a person's conversations on their own computer and shows parts of them to an AI model later. The design aims to keep that memory private to the person it is about and to keep remembered text from steering the agent.

| Boundary | How it is enforced |
| --- | --- |
| Other programs and users on the computer | The local service listens on `127.0.0.1` only and requires a random API key stored in a file only the owner can read (`0600`, directories `0700`, symlinks refused). The client checks an HMAC challenge before sending its key, so a process that takes the port cannot collect it. The embedded database also listens on loopback only, with password authentication and no Unix socket. |
| Web pages in the person's browser | The service rejects requests whose `Host` is not `localhost` or `127.0.0.1` (DNS rebinding) and uses bearer tokens only, so other sites cannot ride on cookies. The memory page signs in with a single-use code that expires after two minutes. It renders stored text as text, never as HTML, under a strict content security policy. The memory proxy refuses rebound host names, cross-site browser origins (unless allowed in `MEMBRAIN_PROXY_ORIGINS`) and non-JSON chat requests. |
| One person and another, on shared bots | Each person on a bot gets their own brain. Group chats are kept apart from private chats by default. A role-play character's memory is kept apart from real life, and a person's sensitive real-life notes are never shown in role-play. On OpenClaw and the Hermes gateway, only the owner's own private chats use the owner's memory; everyone else gets their own. Separation between bot users is enforced by the service selecting the brain per request, not by separate database accounts. |
| Secrets and personal numbers in conversations | Text inside `<private>…</private>`, values that look like API keys, tokens, private keys and passwords (including passwords in connection URLs and "my password is …"), and payment card and identity numbers (checked by Luhn, Chinese ID checksum, or the US SSN format) are removed before anything is queued or stored. Email addresses and phone numbers are removed too when `MEMBRAIN_REDACT_CONTACTS=1`. Logs record error types, not content. |
| Remembered text acting as instructions | Memory blocks state that their contents are historical data, not instructions. memBrain's own block tags inside stored text are defused, so a remembered message cannot close a block and pose as something else. The proxy adds memory to the person's own message, not as a system message. |
| Deleting memory | Erasure removes the content together with derived data, embeddings and cached results. A deletion registry outside the database stops a restored backup from bringing erased content back. |

## What it does not protect against

- **Anyone who can run code as you.** They can read the installation directory, including the API key, and everything in memory. Memory is not encrypted at rest; use disk encryption.
- **Whoever controls a bot.** On the proxy and in token mode, any client that can reach memBrain chooses whose memory it uses through `user` or `X-Membrain-User`. Only connect bots you control, and treat the proxy token as access to every person's memory.
- **A model that follows injected text anyway.** Framing reduces, but cannot remove, the risk that a model acts on instructions it read in a repository, a web page or a remembered message. Keep destructive tools (`memory_forget`) on ask-each-time, and review notes on the memory page (`membrain plugin ui`).
- **Personal data that redaction does not recognise.** Names, addresses, health details and numbers in unrecognised formats are kept, and so are emails and phone numbers unless `MEMBRAIN_REDACT_CONTACTS=1`. A long number that happens to pass the card checksum (about one in ten) is removed even when it is not a card. Use `<private>…</private>` or pause recording for anything else.
- **Backups and exports.** They contain memory in plain form. Backups are written into an owner-only directory; an export from the memory page is an ordinary browser download. Where you keep or copy them is up to you.
- **The installation channel.** Until releases are published to PyPI, the plugins install a pinned source archive from GitHub without checking a hash, and dependencies are resolved at install time. The local embedding model is checked against a pinned SHA-256 when it is downloaded.
