# Network audit: what memBrain's processes contact (2026-11-19)

The [first-run sandbox](first-run-2026-11-19.md) counted, through a local proxy, two or three HTTPS connections to `mobile.events.data.microsoft.com` about nine seconds after `import onnxruntime` (14–22 KB down, 7–8 KB up per service start). This record reproduces that, finds what turns it off, audits every other outbound connection of the product and records the fix. Linux x86_64 (WSL2, Ubuntu 24.04), no paid model call, no real memBrain profile: every run had its own home directory.

## Method

Each process ran in an unprivileged network namespace (`unshare --map-current-user --net --mount --keep-caps`) whose only interface is loopback, with every IPv4 and IPv6 address routed to it. Inside the namespace only, `/etc/resolv.conf` named a resolver on 127.0.0.1 that logged each name and answered it with its own address in 198.18.0.0/15, and a packet socket on loopback logged every TCP SYN and UDP datagram with its payload bytes. For the payload, a listener on port 443 completed TLS with a certificate from a CA made for the run, which ONNX Runtime accepted through `SSL_CERT_FILE` (its 1DS client reads that variable); the decompressed request bodies (deflate, Bond compact binary) were read for their strings and searched for canary texts put into the messages, notes, queries and documents of the run. No traffic left the machine, and no third party's traffic was decrypted. Python-level connections of the model download (outside the namespace, since it needs the network) were logged with CPython audit hooks.

## ONNX Runtime

| Run (1.31.1, the locked version, unless noted) | Lookups and connections | Left in the home directory |
| --- | --- | --- |
| `import numpy`, `import tokenizers` | none | nothing |
| `import onnxruntime`, then idle | `mobile.events.data.microsoft.com` (A and AAAA), one TLS connection to port 443 at 9.1–9.9 s, in one run a second at 10.7 s; refused connections are retried at about 15 s and 24 s | `~/.cache/Microsoft/DeveloperTools/.onnxruntime/deviceid`, `onnxruntime.db` |
| creating memBrain's session; embedding a document and a query | the same, nothing more, also over 8 minutes of idling | the same |
| `import onnxruntime`, exit at once | none (the process ends first) | the identifier, and its report queued (one 982-byte event) |
| `onnxruntime.disable_telemetry_events()` right after the import | unchanged | unchanged |
| `ORT_DISABLE_TELEMETRY=1` in the environment, or set in `os.environ` before the import | none | nothing |
| `membrain.local_embeddings.runtime_available()`, start commit | as for the import | as for the import |
| 1.32.0 (what a fresh installation resolves today), start commit, full product tour below | the same endpoint | the same |
| 1.32.0 and 1.31.1 with the fix | none | nothing |

Each upload was `POST /OneCollector/1.0` with `APIKey: 5ad963bd…`, `Content-Type: application/bond-compact-binary`, `Content-Encoding: deflate` and `SDK-Version: EVT-Linux-C++-No-3.10.279.1` (1.32.0: `3.10.309.1`), a 759–922-byte body. Every event seen was `ProcessInfo`, holding: the operating system and version ("Ubuntu 24.04.5 LTS (Noble Numbat)"), the CPU model, architecture, device class, container and virtual-machine detection ("containerOnVirtualMachine", "wsl"), network type ("Wired", "Unmetered"), the ONNX Runtime and SDK versions, the full path of the Python executable (in a user's installation `/home/<user>/.local/share/uv/tools/membrain-ai/bin/python`, which names the user), the process name, a hashed device identifier ("c:" and 64 hex digits), session identifiers, and whether the device was new. No canary, no memory text, no file name of the model and no input appeared in any upload. The library also holds field names for model-session and run-count events (model producer, file name, graph and weight hashes, runs since last report); none was sent in any run here (up to ten minutes per process), which does not prove they never are.

The second upload of a service start carried, besides the service's own event, the events queued by earlier, shorter processes. Which processes load ONNX Runtime (Python's import profile, start commit): `plugin start`, `plugin status`, `plugin ui`, `desktop restart`, `doctor` and the service do (they ask `local_embeddings.runtime_available()` for the semantic state); the session-start, user-prompt and stop hooks, `plugin tool search` and `plugin mcp` do not. In the full tour, the service sent one batch at its start and nothing in the ten idle minutes after; three events (doctor, status, ui) were still queued at the end, for its next start.

Wheels on PyPI (files' contents and the bundled `Privacy.md`; cp312): Linux x86_64 1.17.3 to 1.28.0 contain no 1DS client; 1.29.0 (2026-08-17) to 1.32.0 contain the endpoint, the SDK and `ORT_DISABLE_TELEMETRY`, and `Privacy.md` says "Telemetry is turned **ON** by default in the official builds" and that `ORT_DISABLE_TELEMETRY=1` "prevents the uploader, events, and persistent device identifier from being created for the process lifetime", while the API "can suppress non-essential telemetry. ONNX Runtime may already have emitted a minimal initialization event before the API can be called". macOS arm64: the same split (1.28.0 without, 1.29.0 and later with, SDK `EVT-MacOSX-C++-No-3.10.309.1`). Windows amd64 1.28.0 to 1.32.0: no 1DS endpoint (ASCII or UTF-16) and no `ORT_DISABLE_TELEMETRY`, but the `TraceLoggingProvider` of the Windows event-tracing backend; per `Privacy.md` that backend "does not use this environment variable" and is turned off through the API. ONNX Runtime's source repository could not be reached from this machine (`github.com/microsoft/onnxruntime` answered 404), so its source was not read; the documentation used is the `Privacy.md` inside each wheel and the Python API page on onnxruntime.ai.

## Every other connection

The same namespace, with the plugin's real commands as separate programs: `plugin start` (a new installation), `desktop restart` with the model in place, the three hooks, `plugin tool note` and `search`, `plugin mcp` (initialize, list tools, one recall, then 12 s open), `doctor`, `plugin status`, `plugin ui --no-browser`, the memory page in headless Chromium (load and five views), ten minutes of idling, `desktop stop`.

| Process | Destination | When | Bytes | Started by | After the fix |
| --- | --- | --- | --- | --- | --- |
| service and the model-state commands | `mobile.events.data.microsoft.com:443` (ONNX Runtime) | ~10 s after each service start; shorter commands queue | ~1.1–1.3 KB requests here; 7–8 KB up, 14–22 KB down through the first-run proxy | the library, by default | none |
| everything else in the tour, the page and Chromium included | loopback only (service, database) | — | — | — | loopback only |
| `plugin fetch-model` (started by the first `plugin start`) | `huggingface.co:443`, redirected to `us.aws.cdn.hf.co:443` | once | two GETs, about 135 MB down; plain httpx, no token or usage report | memBrain, documented | unchanged |
| `uv tool install` in the session-start hook | `github.com`, `codeload.github.com`, `pypi.org`, `files.pythonhosted.org` | first install (27 s, 531 MB cache here) and each plugin update | first-run record: 151 MB archive, 11 MB index, 98 MB wheels | the user installing the plugin | unchanged |
| the same command at a later session; the tool server's `uv tool run --from <archive>` | none (run offline in the namespace: no lookup) | — | — | — | — |
| `membrain proxy` | the `--upstream` the user names | each bot request | — | the user | unchanged |
| Docker setup (no embedded database) | Docker Hub, `pgvector/pgvector:pg17` | setup | — | the user's Docker | unchanged |

Loaded in the service but silent: `opentelemetry` (the API, imported by the MCP package, with no SDK or exporter installed). Not imported by any product process: `huggingface_hub` (installed as a dependency of `tokenizers`; the model download does not use it), so its telemetry switches do not apply. The JSON schemas have no remote `$ref`. The memory page's Content-Security-Policy is `default-src 'self'`, its three.js files are served from the package, and Chromium's 20 requests all went to `http://127.0.0.1:8788`; the headless browser itself looked up no name.

## Fix

`membrain/__init__.py` sets `ORT_DISABLE_TELEMETRY=1` in the process environment, so it is set before any entry point (service, hooks, tool server, CLI, adapters) can load ONNX Runtime, and every process memBrain starts inherits it. `local_embeddings` calls `onnxruntime.disable_telemetry_events()` after each import, the documented switch of the Windows backend (not observed on Windows). With the fix, the full tour on the locked versions made no lookup and no connection outside loopback and wrote no identifier; on 1.32.0 the import and the embedding path did the same. `tests/test_no_outbound_connections.py` runs a real installation, the hooks, a tool call, the tool server and the doctor in such a namespace and fails on any name but the model host; with the start commit's `__init__.py` swapped back in, both its checks fail (the identifier directory appears; the tour looks up `mobile.events.data.microsoft.com` besides the model host), also inside the sharded test runner, whose workers have no route out: the test records attempts, not successful connections.

## Not settled

- macOS and Windows were not run. macOS wheels carry the same 1DS client and switch, so the fix should apply; Windows wheels log through Windows event tracing, which Windows itself may upload according to its diagnostic-data setting, and only the API call addresses it.
- A host that loads ONNX Runtime itself before importing memBrain (using the Python package as a library) has started the reporting before the switch is set.
- Machines that ran memBrain before keep `~/.cache/Microsoft/DeveloperTools/.onnxruntime/` (this one has had it since 2026-11-09, written by test and development runs with the real home directory). memBrain does not delete it, since other programs may use it.
- What the real collector answers, and how many connections and bytes a real upload takes, was not measured again; the first-run proxy numbers stand.
- Fallbacks if the switch ever stops working: pinning `onnxruntime<1.29` (1.28.0 has no 1DS client on Linux and macOS; it forgoes later fixes and may lose wheels for newer Pythons), or running the model without ONNX Runtime (nothing else in the dependency set runs ONNX; a NumPy implementation of the twelve-layer encoder would need the weights dequantized, roughly 470 MB of memory instead of 118 MB, and is untested for speed and agreement).
