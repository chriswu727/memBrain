# Recall readiness and companion integration

Runtime commit: `96e80d7`. Publication remains frozen. The earlier installed runtime `47fcb96` passed 49 installation checks but failed two of 36 R5 windows; neither result qualifies this changed runtime.

## Implemented behavior

Codex moved initialization of the configured recall process pool into API startup. Every worker prepares the contract validator before the application becomes ready. Startup failure closes resources and terminates incomplete workers; a subsequent executor start can recover. Request deadlines, admission limits, computation and source semantics remain unchanged. Inline and externally supplied services retain their existing ownership.

Claude supplied persona changes at `67243f3c` and `60c438d`, integrated as `ceab039` and `21c35ff`. Latest opposite feedback withdraws an incompatible suggestion, feedback predating an accepted opposite change is not reused, and the withdrawal lookup pages through complete relevant history. Codex identified the long-history issue during review; Claude reproduced it with both a reduced window and 5,010 later messages before fixing it. Deleting contradictory evidence may reopen a suggestion supported by remaining live sources. There is no hidden permanent withdrawal record.

## Verification

- Readiness regressions initially failed four tests before implementation. The focused executor/configuration group subsequently passed 57 tests.
- Independent combined integration passed **345 tests in 102.95 seconds** with real PostgreSQL, covering readiness, executor behavior, API, persona growth, persona, localization, mood, affect, relationship and host integration. No skips were reported. Source/test hashes stayed unchanged during the run and owned ports closed.
- Ruff and Git whitespace checks passed. All nine launchers point to `96e80d7`; both launcher pin checks passed.
- Earlier-source CI [42110535525](https://github.com/chriswu727/memBrain/actions/runs/42110535525), at `99d3133`, passed 7,431 Python tests with three warnings, 50 TypeScript tests, type checking and package builds. Native CI [42110535366](https://github.com/chriswu727/memBrain/actions/runs/42110535366) passed five platform jobs. These results precede the changes in this report.

## Cold startup diagnostic

A separate worker creates the app only under its main guard. Four launches use baseline / readiness / readiness / baseline order against the retained synthetic database. Each launch makes one first recall followed by one subsequent recall directly through the SDK, without the host fallback or retries. No model calls occur.

| Measurement, ms | Baseline 1 | Readiness 1 | Readiness 2 | Baseline 2 |
| --- | ---: | ---: | ---: | ---: |
| Process launch to health ready | 708.28 | 552.68 | 499.73 | 417.23 |
| First direct recall | 832.35 | 320.87 | 321.06 | 401.72 |
| Subsequent direct recall | 94.19 | 181.33 | 118.34 | 85.93 |

All eight calls completed with identical context hashes and 31,976 context characters. Inputs remained unchanged and all owned ports closed. This small startup diagnostic is not a statistical performance claim, a warm-latency improvement, or R5 qualification. Baseline variation remains visible.

The first attempt to construct the baseline source tree omitted its migrations and failed before the API started. Its driver result and error log remain in the evidence. Adding the unchanged baseline migrations corrected the setup; no runtime check was bypassed.

The prior instrumented worker constructed the app at module import, which repeats work during process spawn. Its 5,138.42 ms rejected request remains evidence of that diagnostic run, but the timeout did not reproduce through this import-safe entry point. Readiness work addresses when worker initialization occurs; it does not claim to have proved or resolved an ordinary-production five-second timeout.

## Remaining work

Claude is implementing conservative successive feelings about the same explicit topic while Codex retains performance and integration ownership. That mood change is not part of this report. New-runtime full CI, native process lifecycle coverage, appropriate installed checks, concurrent R5 qualification and the remaining behavior gates are still required. No release or merge occurred.

The [evidence manifest](evidence/maturity-recall-readiness-2026-11-05/manifest.json) contains 16 payloads, including failed setup evidence. Every copied payload was checked byte for byte and by SHA-256. Exact scans against three credential values from the owned benchmark profile found no matches; this is not a universal secret audit.
