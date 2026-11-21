# One user, several projects: where something was said (2026-11-19)

Status: implemented on the plugin hooks, the plugin's tool server, the service timeline and the memory page; tested
on a local installation through the hooks with no model; the day-8 captures replayed by the lead to a host model
(see "Verification"); **not tried in a live host session**. The fields it adds to the observation contract and the
timeline were accepted by the lead (see "Decision").

## The question

memBrain keeps one memory per user. A coding user works in many projects. The host trial of 2026-11-18
([record](host-trial-2026-11-18.md)) showed one project going right: "decided PostgreSQL, corrected to 'only the
server; local stays SQLite', a new session goes on with SQLite". Nobody had looked at a new session in a *different*
project.

## Measured on the start commit (`4fc1545`)

A two-project world (`tests/two_project_world.py`, built on `tests/resume_correction_world.py`): Tidepool and Harbor
are git repositories; every hook payload carries `cwd` as Claude Code sends it; the plugin's tool server is started in
the session's directory. Tidepool: day 1 PostgreSQL decided; day 3, in a session run from a git worktree of Tidepool,
corrected to "only the server uses PostgreSQL; local stays SQLite". Harbor (sessions in its `app` subdirectory):
day 2 "For the database, we use MySQL here, locally too.", ordinary talk, a laptop low on disk space and "call me
Sam"; pnpm over npm said in both. Day 8: "finish the local install" in a new session in Harbor, in Tidepool and in a
scratch directory never seen before. Three worlds: a diligent host whose notes name the project ("Tidepool database:
..."), a diligent host whose notes do not ("Database: ...") with a busy week, and a lazy host (no memBrain tool
calls) with a busy week. Captures of everything the host receives are under the run root's `captures-before/` and
`captures-after/` (`/home/yichen/.local/state/membrain-setup/runs/workspaces-20261119/`), in the shape of the
resume-correction captures.

What a Harbor session received on day 8, verbatim (notes whose text does not name the project):

```
Other notes:
- [2026-11-03] Database: MySQL everywhere, local development included. (id: …)
- [2026-11-04] Database: PostgreSQL on the server only; local development stays on SQLite. (replaces your note of 2026-11-02) (id: …)
```

Tidepool's note is newer and says it replaced an earlier note: a host reading this block in Harbor is handed, as the
current decision, the opposite of what the user said for Harbor. A search for "local database" or "which database"
in Harbor listed Tidepool's note first. Nothing anywhere said which project a note or message came from. With notes
that name the project the host can tell, but only because the host of the trial happened to write the name into its
note; messages ("For the database, we use MySQL here, locally too.") never name it. After a busy week Harbor's
history block held the sixteen most recent messages of either project and none of Harbor's database message.

Stored: the hooks receive `cwd` (with the user's account name and the project's folder in it) and recorded nothing of
it; a message's record had its session id and producer, nothing about where. The third directory received exactly
what Harbor did.

The problem is real. The model-free tests that pin it are `tests/test_two_project_world.py`; on the start commit
(with the start commit's version of the file, strict xfails where it is wrong) they gave the results under "Runs".

## What was built

- **The label.** `src/membrain/workspace.py`: the name of the project folder, from the hook's `cwd`. In a git
  repository, the main working tree's folder, so every worktree (and every subdirectory) has the repository's name;
  a submodule and a bare repository keep their own. Without a repository, the session's own folder. The home folder,
  a repository in the home folder itself (dotfiles) and a filesystem root give no label, since their name is the
  user's. Brackets, `·` and quotes are dropped, 64 characters at most, and a name the privacy filter would change is
  not used. The path is never written anywhere (tested over every file of the installation, database files included).
- **Stored with the record.** The plugin's messages carry `workspace_ref` (an optional field of the observed event,
  in the event's own document: no migration; exported and erased with it). A reply takes its message's. The service
  timeline returns `workspaces` for a message, and for a note the distinct labels of its current source messages,
  read on each request: nothing is stored with the note.
- **Told to the host.** A note, history line or recalled line from another project carries `· in <name>` after its
  date; one from the current project, or with no recorded project, is unchanged. A block that holds a mark adds one
  sentence (157 characters): `A line marked "in <name>" comes from work in another project: what it says about
  that project holds only there; what it says about the user holds everywhere.` With no current project (a chat host,
  or a session in the home folder) every recorded place is named and the sentence says "in the project <name>". A
  plan from another project says "(in <name>)" in the coming-up block.
- **Ordered, never hidden.** History: this project's messages (and unlabelled ones) newest first, then other
  projects' newest first, within the same budget; the header then says so. Automatic recall: the same order within
  its budget, shown oldest first as before. The recall tool keeps the service's order (a search reaches every project
  alike); among notes matching as many words, the session's own project's come first. Notes: a note of another
  project gives way first only if it was said in one other project, is of kind `other`, `plan`, `agent_commitment` or
  untyped, and is neither pinned nor written by the user.
- **Page.** Notes, conversation messages and search results show `project <name>` as a tag (Chinese: `项目 <name>`).
  Text only: no filter, no control.

### Personal facts: the rule and where it is wrong

Where something was said says nothing about whether it is about the project or the user. The rule takes the truth
for the mark and the note's kind for the order: every line is marked with where it was said, and the block's sentence
says what holds where; only notes of kinds that are mostly about a project (`other`, `plan`, `agent_commitment`,
untyped) give way first. So "Prefers pnpm over npm" said in Tidepool reaches Harbor as
`- [2026-11-02 · in Tidepool] Prefers pnpm over npm for frontend packages.`, keeps its rank, and the header says what
it says about the user holds everywhere; "Wants to be called Sam." said in Harbor reaches Tidepool marked
`in Harbor`. Where it is wrong:

- A project fact saved as `preference` or `constraint` ("must support Node 18") keeps its rank in other projects. It
  is still marked, so the host can tell.
- A personal fact saved as `other` or without a kind (the unnamed world saves "Wants to be called Sam." without one)
  gives way first in other projects. It is still shown while there is room, and the notes block's budget held every
  note of every world here; it would drop out first only in a full block.
- The mark is the host model's to read. Whether a model reads `in Tidepool` on "Prefers pnpm" as "applies here
  too" is not measured: that needs a model in the loop.
- A note said in two projects is never demoted, and is unmarked in either of them.

## Characters added per session (day 8, from the captures)

| World | Session start (Harbor / Tidepool / scratch) | Prompt hook (Harbor / Tidepool / scratch) |
| --- | --- | --- |
| diligent, named, short | +428 / +424 / +536 | +0 / +0 / +0 (history complete, no recall) |
| diligent, unnamed, busy | +86 / −63 / +78 (budget-bound: marks take the place of history lines) | +88 / −8 / +160 |
| lazy, busy | +183 / +83 / +14 | +28 / −22 / +76 |

Measured on `5f16fd7f` (with the quiet companion on coding hosts), before and after this change: run root
`captures-before-5f16fd7f/` and `captures-after-5f16fd7f/`. The short world's session start went from 4,799 to
5,227 to 5,335 characters. The busy worlds' session starts are at their budget (about 9,400 characters), so the cost
there is history lines given up rather than characters; prompt-hook sizes also move with what the embedding recall
returns. A user with one project gets no mark and no sentence: no character is added. The first measurement, on
`4fc1545`, is in `captures-before/` and `captures-after/`.

## Other hosts

- **Codex and WorkBuddy** run the same hook handlers (`membrain plugin hook <event> --host codex|workbuddy`), so they
  get the same labels from the payload's `cwd`. That their payloads carry `cwd` is read in their hook formats, not
  verified on either host here; without it the label is absent and they behave as before.
- **Chat bots** (Hermes, OpenClaw, AstrBot, the proxy) have no projects: they send no label, their messages stay
  unlabelled and are shown as before. When one shares the owner's memory with a coding host, the owner's coding notes
  reach it marked with their project and sink below unlabelled notes of the same rank when its block is full.
- **The recall tool** takes the current project from the tool server's working directory, as the host starts it in
  the session's directory; not verified on a real host. If it starts elsewhere, every labelled line is named, with
  the "in the project <name>" sentence, which stays true.

## Deletion and trust

The label is part of the message's own record: erasing the message removes it (the record's document is cleared);
an export carries it; a note's places are read from its current sources each time. While a turn is pending, the
staged record in the local session state and the delivery queue hold the label beside the message text, and leave
with it. A label reveals the project folder's name, which may be a client's or a product's name, to every session's
host model, on the memory page and in exports; it does not reveal the path, the account name or where on disk it is.

## Limits

- Two different projects with the same folder name share a label; a renamed or moved folder starts a new one (older
  records then show the old name, which is still where they were said).
- Records from before this change have no label and are shown as before; nothing backfills them.
- Notes without source messages have no project.
- A label that the privacy filter would change is dropped, not altered.
- Not tried with a real host model; whether hosts use the marks well is unmeasured.

## Decision

The smallest right version needs an optional field in two public interfaces: `workspace_ref` on an observed event
(the contract schema, the Python client's `observe` and the TypeScript type) and `workspaces` on timeline items. No
migration, no new tool, no new setting. Cost: an archive exported after the change cannot be restored by an older
runtime (its schema rejects the field); a client sending `workspace_ref` to an older service is refused. The plugin
always talks to its own installation's service of the same build (a mismatched build reports `restart_required`), so
plugin recording is not affected. The lead accepted both fields on 2026-11-21: the product is unreleased, so an
export that an older runtime cannot read is acceptable.

## Verification with a host model

Replayed by the lead to a host model, read not scored blind, 12 replies each side. Before the change, a Harbor
session mentioned SQLite (Tidepool's decision) in 4 of 4 replies and MySQL in only 2. After it, MySQL in 4 of 4 and
SQLite in none. Tidepool stayed on SQLite in 4 of 4. In the never-seen project, 3 of 4 replies named no database and
1 said "assuming Lantern follows your local-SQLite setup": a reply that carried another project's decision over as
an assumption, though it said so.

## Runs

All on WSL2, model-free, logs and JUnit under the run root.

- `before`: the start commit's version of `tests/test_two_project_world.py` (`test_two_project_world_before.py` in
  the run root: the same tests, strict xfails where the start commit is wrong) on the start commit's runtime: 13
  passed (every note reaches every session, no path is stored, hooks within Claude Code's limit, erasure), 25
  xfailed (every label, mark and ordering test).
- `after1`: `tests/test_workspace_labels.py` and `tests/test_two_project_world.py` on this change: 49 passed.
- `after2`: killed with every other session when the machine ran out of memory on 2026-11-20; no result.
- `after3` (`shard_runner.py --workers 1 focused`): the two new files with 37 affected suites: 874 passed, 8 xfailed
  (existing), 1 skipped (an existing in-test skip in `test_correction_visible_trust.py`), 1 failed:
  `test_installation_pin.py::test_the_pinned_runtime_is_the_runtime_in_this_repository`, which fails by design once
  runtime source changes.

Rebased onto `5f16fd7f` (quiet companion, first-run fix, network audit, page trace, shorter host texts):

- `before-5f16fd7f`: the same start-commit version of the world tests on `5f16fd7f`'s runtime: 13 passed,
  25 xfailed.
- `rebased1` (`--workers 1 --require-browser`): the two new files, `test_quiet_companion.py`,
  `test_page_trace_browser.py`, `test_first_run.py`, `test_companion_world_captures.py`, `test_companion_cues.py`,
  `test_host_trial.py`, `test_memory_page_browser.py` and the affected suites above: 1,020 passed, 8 xfailed, 1
  skipped (the same existing in-test skip), 3 failed:
  - the pin test, by design;
  - `test_host_recording_outcomes.py::test_a_hermes_turn_that_cannot_be_matched_is_logged_and_listed_as_unknown`:
    passed when rerun (`rebased-recheck`), an ordering flake;
  - `test_resume_correction_scenario.py::test_after_a_busy_week_the_prompt_hook_recalls_the_correction_with_its_date[lazy_busy-chinese]`:
    fails again on rerun, and also on `5f16fd7f` without this change (`pristine-5f16fd7f`), so it is not caused by it.
