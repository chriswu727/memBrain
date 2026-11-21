# Every item on the memory page traceable and deletable; what the host is told, consistent and shorter

Runtime `5f16fd7f`; launcher pin: the commit that adds this record. No migration, no new dependency, no model call of memBrain's own, no new tool, route or control. **It closes no release gate**, and no acceptance run has been made on this runtime.

This runtime also carries four changes with records of their own: [the companion kept quiet on coding hosts](quiet-companion-2026-11-19.md) (tried on a real host), [a new user's first minutes](first-run-fix-2026-11-19.md) (measured in a sandbox [before](first-run-2026-11-19.md) and after), [ONNX Runtime's reporting to Microsoft stopped](network-audit-2026-11-19.md), and a [tool for real-host trials](host-recheck-2026-11-19.md). A real-host check of 2026-11-19 found that **asking the agent to forget something erases nothing**; that is not fixed in this runtime.

## 1. The memory page: whatever it shows, the user can see what it rests on and delete it

The page has had one job since 2026-11-18: look, check where something came from, delete. Notes did it; the rest did not.

| Item | Before | Now |
| --- | --- | --- |
| A message (Conversations, Search) | did not say what rests on it | lists the notes resting on it, as links; deleting it names the agent's reply and those notes |
| A search result, a message on the map | no link, no delete | links to its conversation; can be deleted |
| A feeling, a mood trigger | no link to its message | links to its note; a trigger lists its messages |
| A promise | no source, no delete | shows its messages and its note; can be deleted |
| A shared moment | source messages only | links to its note |
| A persona version, an agreement | the citing message was not shown | links to the message where the user asked or agreed |
| Deleting the personality history | one fixed question | names the agreements and suggestions it removes |
| A boundary | no source | says that no message is linked, because none is stored |

**The question before a delete and the erasure cannot disagree.** Before deleting, the page reads the item again with what will be erased along with it, computed by the same dependency walk the erasure takes (one SQL text for both). A test per kind compares the list the page was given with the records the erasure removed, read independently from exports taken before and after.

Two questions were wrong before and are corrected: the map's note Delete always asked "Delete this note? Its content is erased." even when an earlier note or a feeling went with it; and the relationship reset said feelings stay, though it erases a feeling recorded on a shared moment.

**Still not so:** a boundary has no source (recording one needs the boundary tool to carry the current message, as the note tool does); deleting the message where the user agreed does not end the agreement; a single persona version or suggestion cannot be deleted on its own.

## 2. What the host is told

Everything memBrain hands a host was read side by side: the standing instructions, the session notice, the block headers, the consolidation texts and the tool descriptions.

| Text | Before | After |
| --- | --- | --- |
| Standing instructions | 1,388 characters (budget 1,400) | 1,179 |
| A new user's session start, in all | 3,977 | about 3,660 |
| `memory_note` description | 2,481 | 1,970 |

- **Not true, corrected.** The persona header said the card "was set by the host or the user"; a new user's type is drawn at random. A tool answer sent the user to a page editor that no longer exists.
- **Could be misread, reworded.** "Never a plan or fact they did not state" (as "never note a plan") became "a lasting fact the user stated, never your own suggestion or something they only asked about". "Never say you cannot show the source" became "If it fails, say so; never claim there is no way to show the source."
- **Said several times, now once.** The definition of a shared moment stood in five places; the standing instructions no longer repeat the session notice.

### One shortening was taken back after a probe

The clean-up had moved the definition of a hard shared moment out of the standing instructions into the note tool's field descriptions, which a host reads only after it looks the tool up. The provider's host model (`deepseek-v4-pro`, emulated host, eight trials each of one hard exchange; replies read by the lead, not scored blind; [evidence](evidence/host-text-probe-2026-11-21/)):

| Standing instructions | Saved as a hard shared moment | In the turn the user said it | With the user's feeling |
| --- | --- | --- | --- |
| Before the clean-up | 7 of 8 | 7 of 8 | 7 of 8 |
| Shortened | 6 of 8 | 3 of 8 | 5 of 8 |
| With the sentence restored (this runtime) | 8 of 8 | 8 of 8 | 8 of 8 |

On the shortened wording the other companion tools behaved as before in two trials each (boundary, manner feedback, type switch, a stated and an inferred feeling, a playful moment, the question about feelings). Conservative cost bound of these probes: 10.3 CNY.

## Limits

- The page change and the wording are **not tried on a real host**. The sentences dropped from the consolidation texts ("do not describe the indexing to the user") rest on the tool's last answer saying the same; that was not probed.
- One model through an emulated host; eight trials of one exchange.
- A request such as "from now on, run the tests before committing" is still sent to the persona tool, which asks before saving; it belongs in a note. Not changed here.

## Verification

Local, on Linux under WSL2; nothing was run in CI or on another platform.

| Check | Result | On |
| --- | --- | --- |
| Full source suite, sharded over four workers | 5,036 passed, 1 failed (the pin test, by design before the pin), 11 strict expected failures, 4 skipped (three desktop end-to-end tests that need Docker; one trust case that applies only to a three-note chain); 9 minutes | `5f16fd7f` |
| Pin test after pinning | passes | the commit that adds this record |

The suite now runs through a sharded runner, each worker in a network of its own. An earlier run of it on 2026-11-20 with six workers beside other work exhausted the machine's memory and was lost; the counts above are from a later, complete run.
