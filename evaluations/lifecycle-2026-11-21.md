# Stopping, uninstalling and removing memBrain, in a sandbox

Start commit `93e9a587`. No migration, no new dependency, no model call of memBrain's own, no new tool for the host; two new commands for the user (`membrain plugin stop`, `membrain plugin uninstall`) and a listing added to `membrain plugin status`. Linux x86_64 (WSL2), uv 0.13.6, system Python 3.12.3. **No host was started**: a driver played Claude Code's part with the plugin's real hook command lines and tool server, as in [first-run-fix](first-run-fix-2026-11-19.md). Every location was redirected into the sandbox (`HOME`, `XDG_*`, `UV_TOOL_DIR`, `UV_TOOL_BIN_DIR`, `UV_CACHE_DIR`, `MEMBRAIN_DIRECTORY`, `CLAUDE_PLUGIN_DATA`); the service ran in a private network namespace and reached the internet only through a counting proxy; the runtime came from a source archive of this change's tree built as GitHub builds one. The user's commands ran in a terminal (a pseudo-terminal) with none of the variables a host sets for its hooks. Driver, transcripts and `find` listings: `~/.local/state/membrain-setup/runs/lifecycle-20261121/` (not in the repository).

## Why

The real-host install check of [2026-11-21](forget-and-first-install-on-a-real-host-2026-11-21.md) found no command to stop the plugin's service (only `membrain desktop stop --directory …`), and an outsider's review found no uninstall instructions. A product that says "your memory is yours, on your machine" has to make leaving complete.

## The commands

- `membrain plugin stop` stops the service and its database. The plugin starts them again with the agent's next message, tool call or session; the command says so and names how to keep it stopped (Claude Code: `claude plugin disable membrain@membrain`; for Codex, WorkBuddy and OpenClaw the repository documents no off switch, so it says to remove the plugin, which keeps the memory).
- `membrain plugin status` adds `on_this_computer`: the data directory and its size, the record of erasures kept beside it, the program uv installed and its command, the database engine cache, uv's download cache and Python, ONNX Runtime's old folder if present, where each agent keeps the plugin (written by the session-start hook from the host's own variables), and memBrain's running processes (Linux and macOS; Windows is not listed). In a terminal it prints plain lines; piped, the JSON as before with the new key.
- `membrain plugin uninstall --keep-data` stops everything and removes the program (`uv tool uninstall membrain-ai`), the engine cache and memBrain's entries in uv's cache (`uv cache clean membrain-ai`).
- `membrain plugin uninstall` also removes the data directory and the record of erasures, after offering an export (`--export FILE` without asking). A data directory chosen with `MEMBRAIN_DIRECTORY` or `--directory` loses only what memBrain writes; anything else in it is left and named. With the Docker engine it also runs `docker compose down --volumes` (not run here: no Docker).
- Both forms ask for a typed word (`UNINSTALL`, `ERASE`) unless `--yes`; without a terminal and without `--yes` they refuse. They refuse inside an agent session even with `--yes` (any of `CLAUDECODE`, `CLAUDE_CODE_ENTRYPOINT`, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, `PLUGIN_ROOT`, `PLUGIN_DATA`, `CODEX_SANDBOX`, `CODEX_SANDBOX_NETWORK_DISABLED`, `CODEBUDDY_PLUGIN_ROOT` set), and while a tool server of an open session, an installation or another memBrain command is running for the same data directory. memBrain never edits the host's configuration; the last lines name the host's own command.

## What remained after each step (`find` over the sandbox's home)

| Step | memBrain's files | Processes |
| --- | --- | --- |
| Installed, session open (two messages, one note, local model) | data 221 MB, erasure record 60 KB, program 302 MB (+ `~/.local/bin/membrain`), engine cache 37 MB, uv cache 56 MB (the rest hard-linked into the program) | service and its workers, database, the session's tool server (`uv tool run` and the runtime) |
| `uninstall --keep-data` with the session open | refused: "Nothing was removed: memBrain is in use. … Still running: a tool server of an open agent session (process 1655291)." | unchanged |
| `plugin stop` | unchanged | none |
| next message of a session | unchanged | service and database again |
| `uninstall --keep-data` (typed `UNINSTALL`) | data 237 MB and erasure record kept; program, command, engine cache and memBrain's uv cache entries gone; uv cache 288 MB (the wheels, no longer hard-linked) | none |
| a session-start hook of a session still open | unchanged: the hook said the runtime is not ready, nothing was installed or created | none |
| plugin's next session (reinstall) | program and engine cache back (engine extracted again); the session-start block held the pnpm note, a search found the PostgreSQL message | service and database |
| `uninstall` with export (typed the file name, then `ERASE`) | 22 entries left, all uv's: `~/.local/bin/uv`, `uvx`, uv's empty tool directory with its lock and `.gitignore`, uv's download cache (288 MB; `uv cache prune` found nothing unused); the export (40,929 bytes, mode 0600, holds the messages) | none |
| a session-start hook after that | unchanged | none |

The Claude Code plugin itself, its data folder and the host's own transcripts were not in the sandbox: they belong to the host and were not exercised (no host was started).

## What memBrain cannot remove, and says so

The agent's plugin (the host's command: `claude plugin uninstall membrain@membrain`; until it runs, the next session installs memBrain again), the agent's own conversation history and memory files (`~/.claude`, `~/.codex`) and anything the agent wrote into the user's projects (the [real-host trial](forget-and-first-install-on-a-real-host-2026-11-21.md) saw the agent write a preference into a README), uv's shared download cache and any Python uv installed, ONNX Runtime's `~/.cache/Microsoft/DeveloperTools/.onnxruntime/` from releases before [2026-11-19](network-audit-2026-11-19.md), and backups the user made with `membrain desktop backup` (restoring one brings back what it holds; the record of erasures that would have stopped that is removed with everything else).

## Found and fixed on the way

- **A cleared cache folder broke the installation.** With the engine cache removed (`rm -rf ~/.cache/membrain/native`, or any cache cleaner) the next start failed with `native_transition_target: The pinned target engine failed verification`, a tool call answered "memBrain is starting" for good, and `membrain desktop stop` ended in a traceback (seen on the start commit in this sandbox). The recorded engine is now extracted again when its path is the one this runtime's bundle makes, and verified file by file as before; another missing engine stays an error.
- **The erasure record lives outside the data directory** (`~/.local/share/.agent-memory-recovery/<installation>`); deleting the data folder by hand left it. `uninstall` removes it, and the plan names it.

## Windows path length

`embedded_database_cache_failed` is raised by `native_bundle.prepare` for any file error while extracting the engine into `%LOCALAPPDATA%\memBrain\Cache\native`. The longest path it writes is the staging directory plus the supplier archive's top folder plus the deepest file (`include/server/snowball/libstemmer/stem_ISO_8859_1_portuguese.h`, 63 characters): about 185 characters plus the length of the user name in the default location (computed with the Windows archive named as the Linux one is; the exact name was not checked), so a long user name or a redirected `LOCALAPPDATA` crosses Windows' 260. That length is now computed before extracting; when Windows reports long paths off (`RtlAreLongPathsEnabled`, or the `LongPathsEnabled` registry value) and the path is longer, the error is `embedded_database_path_too_long`, naming the length, the folder and what to do; when Windows cannot say, the same error replaces the generic one after a failed extraction. **Unverified:** no Windows machine was used; the tests supply the limit as Windows would report it. Whether PostgreSQL itself then runs from a path that long with long paths on is not known. The embedded database creates no Unix socket (`unix_socket_directories = ''`; every client connects to 127.0.0.1), so a long data directory cannot reach the socket limit on Linux or macOS (read in the code and pinned by a test).

## Tested versions in installations

`uv tool install` ignores `uv.lock`: on 2026-11-19, 26 of 68 installed packages differed from it. The launchers now pass `constraints.txt`, generated from `uv.lock` by `scripts/write_constraints.py` (70 packages: the runtime with its `embedded` and `semantic` extras; a test fails while it differs from the lock), and install without it when uv refuses it. The file sits beside the launchers (`plugins/membrain/`, and `integrations/openclaw/membrain/` for OpenClaw, which installs from the source archive; neither is export-ignored).

| Install | Result |
| --- | --- |
| uv 0.13.6, real start hook, constraints | 68 packages, all at the locked versions; second session's install 0.9 s |
| uv 0.4.30 (no `--constraints`) | the constrained call exits 2 at once, the plain one installs: 27 of 67 differ from the lock |
| uv 0.13.6, a constraint with no wheel for the platform (`onnxruntime==1.16.0`, no Python 3.12 wheel) | the constrained call exits 1, the plain one installs: 27 differ |
| resolution only, `uv pip compile` per platform | Linux x86_64 and ARM, Windows x86_64 and macOS 14+ ARM resolve with the constraints; macOS on Intel and macOS 13 ARM do not (onnxruntime 1.31.1 has no wheel there) and fall back, resolving onnxruntime 1.23.2 |

**Limits:** a fallback drops every constraint, not only the one that failed; on Intel Macs and macOS 13 each session start resolves once more and fails before the plain install (about a second, from uv's cache). Claude Code sets `CLAUDE_PLUGIN_ROOT` for hooks; whether Codex sets `PLUGIN_ROOT` or `CLAUDE_PLUGIN_ROOT` is not known here (without either the Codex hook installs as before). The `.cmd` launcher now runs itself in the background to install, read line by line but not run (no Windows). The tool server's `uv tool run --from` entry is unchanged: it serves from the installed tool once that matches.

## Verification

| Check | Result |
| --- | --- |
| `tests/test_lifecycle.py` (real service for stop, status, both uninstalls, refusal while a tool server runs; the confirmation in a pseudo-terminal; refusal in an agent session; pieces; path length) | 25 passed |
| Related focused set (plugin, CLI errors, no outbound connections, native bundle/transition/adoption/dependencies, desktop upgrade and life cycle, embedded database, first run, easy start, launchers, constraints, lifecycle, installation pin, host, MCP) | 455 passed, 2 failed: the pin test, by design before the pin; and the stop test, which found a start a hook had begun in the background still running (the test now waits for it). Rerun of the lifecycle, constraints and pin files: 30 passed, the pin test failed by design |
| Sandbox above | every step as listed |

Not run: macOS, Windows, a real host, Docker. Host commands other than Claude Code's are worded from this repository's documentation and not checked.

## On a real host (2026-11-21, after the launchers were pinned to `302c19d2`)

The documented install command was run again in an empty Claude configuration directory on Claude Code 2.1.322, and two Sonnet turns followed with the installed plugin unmodified (uv's tool directories and memBrain's data directory redirected into a sandbox; per-turn summaries in [evidence](evidence/host-trial-install-2026-11-21/), files `second-install-*`).

- The plugin directory holds `constraints.txt`, and the installation it made has the locked versions (checked: onnxruntime 1.31.1, fastapi 0.161.0, numpy 2.5.4, starlette 1.9.0, psycopg 3.3.6).
- Turn 1, runtime not installed yet: the user was told memory was still installing; the host saved the decision once memory answered.
- Turn 2, a new session: nine tools offered; asked what was decided about the database, it answered from memory.
- `membrain plugin stop` then stopped the service, printed that the memory is kept and how to keep it stopped, and no process was left.

One run, Linux, with the wheels and the bundled engine already cached on the machine; `plugin uninstall` was exercised in the sandbox walk above, not here.
