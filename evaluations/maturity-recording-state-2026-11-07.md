# Recording-state visibility repair

Runtime `89d510360fbdfa55b97801204c277259c783548b` makes a mid-conversation pause visible before every subsequent reply, even when saved memory is unchanged or the service is unavailable. It names the current host's actual resume tool only when that tool is supplied. Tool-less hosts receive a memory-controls instruction. The chatbot adapter now passes its tool contract to both lifecycle calls. Pausing, permission to resume, user/role-play scope and persistence rules are unchanged; no text-driven automatic resume is introduced.

## Public verification

A new public synthetic regression suite first reported 9 failures and 1 pass on the preceding runtime. The first repair passed those 10 cases. An additional cached-tool-contract regression checks that a stale session cannot hide a newly available resume tool or advertise one to a tool-less caller. The final source passes 189 related tests, including all 11 recording-context cases, host privacy and persistence, first-use behavior, Claude/Codex/OpenClaw hooks, chatbot/Hermes adapters and proxy behavior (124.84 seconds, zero skips). Ruff and whitespace checks pass.

The initial broader run is preserved: 3 failures and 50 passes, then operator interruption. The parent imported current source through PYTHONPATH, while isolated service children used the preceding execution checkout's interpreter environment. Their build identities differed, and service readiness timed out. A separate development interpreter whose isolated imports point to this worktree corrected the test environment. No runtime startup check was weakened. The corrected complete run above passed.

All nine launchers pin this runtime. Exact-head CI, a fresh installation check and public deterministic rehearsal are pending; results from earlier runtimes are not claimed for this one.

## Acceptance limit

The [fourth attempt](maturity-fourth-attempt-2026-11-07.md) remains stopped and invalid. Its execution checkout, hidden inputs, accounting ledger and unscored outputs remain sealed. This repair was developed with public synthetic fixtures and establishes a context-visibility defect independently of that attempt. It does not establish why the hidden request lacked a resume invocation, or demonstrate improved real-agent behavior. No new paid or subscription-backed behavior run has started or been authorized. R4/C5 and publication remain blocked.
