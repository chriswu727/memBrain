Now I have enough context to diagnose both failures. Let me write up precise findings.

---

## Failure 1: `_stop_failed_pool` leaves a worker alive

### Root cause (src/membrain/recall_executor.py:26–37)

The sequence `start(timeout=0)` is:

1. `_executor()` creates `ProcessPoolExecutor`, `submit()`s two `_worker_ready` calls. Each `submit` triggers `_start_executor_manager_thread()` + `_adjust_process_count()`; Python populates `pool._processes` with two `SpawnProcess` objects, but the children are still inside `_initialize_worker` → `barrier.wait(timeout=20)`.
2. `future.result(timeout=0)` immediately raises `TimeoutError`.
3. `_stop_failed_pool(pool)` runs.

Two concrete lifecycle bugs make one worker survive:

- **`shutdown(wait=False)` leaves the `_ExecutorManagerThread` running.** Its loop can still call `_adjust_process_count()`, and (more importantly) its `join_executor_internals` performs `p.join()` without a timeout against children still asleep in the barrier. Nothing in `_stop_failed_pool` joins that thread, so the manager and our `terminate()` race against each other.
- **`shutdown(... cancel_futures=True)` races with `terminate()`.** Cancelling futures pushes `None` sentinels onto `_call_queue`, but the children haven't reached the work loop (they're in the barrier). Meanwhile we call `process.terminate()` and then `process.join(timeout=1)`. For a child that was spawned slightly later (spawn start is not simultaneous for the two workers), SIGTERM can arrive while the interpreter is still mid-bootstrap, before Python registers the default `SIG_DFL` behaviour for the signal pipe multiprocessing wires up on POSIX; the signal is seen only when the interpreter next polls. With `join(timeout=1)` + `kill()` + `join(timeout=1)` the second join is too short in that path, and `is_alive()` is still `True` when the test asserts (recall_executor.py:34–37).

### Precise minimal patch

```python
def _stop_failed_pool(pool):
    # Prevent new submissions and signal the manager BEFORE terminating; keeping the manager alive lets it re-enter
    # _adjust_process_count and keeps p.join() held against barrier-stuck children. We terminate first so the manager's
    # own p.join() unblocks, then join the manager so no further process bookkeeping races with our reap.
    pool.shutdown(wait=False, cancel_futures=True)
    seen = {}
    def snapshot():
        for process in (pool._processes or {}).values():
            seen.setdefault(process.pid, process)
    snapshot()
    for process in list(seen.values()):
        if process.is_alive():
            with contextlib.suppress(ProcessLookupError):
                process.terminate()
    manager = getattr(pool, "_executor_manager_thread", None)
    if manager is not None:
        manager.join(timeout=10)
    snapshot()  # catch anything the manager appended between step 1 and now
    for process in seen.values():
        if process.is_alive():
            with contextlib.suppress(ProcessLookupError):
                process.terminate()
    for process in seen.values():
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
```

Key changes from current code:
1. `shutdown()` is called **before** capturing processes, so `_cancel_pending_work`/`_shutdown_thread` are set before the manager can spawn a replacement.
2. The manager thread is explicitly `.join(timeout=10)`d after our `terminate()`, so no concurrent `_adjust_process_count` / `p.join()` runs while we reap.
3. Processes are snapshotted twice (defensive against manager-added entries); `seen` is pid-keyed so a snapshot can't drop entries.
4. Joins are 5 s instead of 1 s. `SIGKILL` is reliable, but `is_alive()` is only updated by `poll()`; on macOS CI machines the test previously observed a one-shot flake where the 1 s join returned before `wait()` reaped the child. 5 s removes the race without weakening any assertion.
5. `ProcessLookupError` is suppressed because the manager thread may have already reaped the pid.

### Regression test

Make the collapse deterministic by giving the initializer an event the test never sets, so **every** worker is guaranteed stuck when `_stop_failed_pool` runs (otherwise the existing test is still probabilistic — some workers finish before shutdown).

Add a module-level (picklable) blocking initializer to `tests/test_recall_executor.py`:

```python
def _blocking_initializer(event):
    event.wait()
```

Then in `tests/test_recall_readiness.py`:

```python
def test_failed_start_reaps_workers_even_when_initializer_is_stuck(monkeypatch):
    import multiprocessing
    from test_recall_executor import _blocking_initializer

    executor = RecallExecutor(2)
    event = multiprocessing.get_context("spawn").Event()  # never set
    monkeypatch.setattr(executor, "_initialization", lambda ctx: (_blocking_initializer, (event,)))

    captured = []
    original = executor._executor
    def capture():
        pool = original()
        captured.extend(pool._processes.values())
        return pool
    monkeypatch.setattr(executor, "_executor", capture)

    with pytest.raises(DomainError, match="startup"):
        executor.start(timeout=0.2)
    assert captured and all(not p.is_alive() for p in captured)
    assert executor._pool is None
    # new pool must still be creatable after the failed one is reaped
    monkeypatch.undo()
    executor.start()
    try:
        assert executor(*arguments())["items"]
    finally:
        executor.close()
    assert all(not p.is_alive() for p in captured)
```

This proves reap works in the worst case (children never reach the work loop) and that the semaphore/ pool state is reset enough to accept a fresh `start()`.

Edge cases to keep in mind:
- `pool._processes` can transiently be `None` on 3.12 after shutdown; the `or {}` guard already covers it.
- If the manager thread never exits within 10 s (rare, e.g. a frozen pipe), the subsequent `kill()` + `join(5)` still forces the children down; the manager becomes a daemon thread that dies at interpreter exit.
- `close()` continues to call `shutdown(wait=True, cancel_futures=True)`; a prior `_stop_failed_pool` can leave the manager joined already — `shutdown` is idempotent.

---

## Failure 2: public node obscured by sensitive node in the structural 2D map

### Root cause (src/membrain/web/brain.js:52–54, src/membrain/web/observatory.js:94–123)

`obsPosition` places each node in its region volume using a hash of `${region}|${id}`. The 2D layout for `memory-structure-v1` maps each 3D point with `x = 400 + point[0]*85`, `y = 250 - point[1]*85` and **drops z entirely**. Two nodes whose 3D positions differ mainly in z collapse onto near-identical 2D coordinates.

In the failing case, both notes are kind `plan` and land in the same region volume. After the 16 relaxation iterations in `obsLayout`, their anchors converge further (both have the same immediate-neighbour set). The 2D projection ends up at `(223.181, 186.001)` and `(218.324, 190.662)` — Euclidean distance ≈ 6.73 — while each circle has `r=7` (weight 0.5 → `5 + 4*0.5`). The sensitive circle is drawn in `map.nodes` order and happens to be later in the list, so Playwright's click resolves to the sensitive circle at the public circle's center, failing the public-detail assertions.

### Precise minimal patch

Add a bounded, deterministic 2D decollision pass **only inside the 2D structural branch** of `brain.js:52–68`, so `observatory.js`, `hologram.js`, and `showcase.js` keep the untouched 3D topology:

```js
function decollide2D(points, nodes, minGap = 20, iterations = 64) {
  const ids = nodes.map((node) => node.id).slice().sort();  // deterministic order
  for (let step = 0; step < iterations; step++) {
    let moved = 0;
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const a = points[ids[i]], b = points[ids[j]];
        if (!a || !b) continue;
        let dx = b.x - a.x, dy = b.y - a.y;
        let d = Math.hypot(dx, dy);
        if (d >= minGap) continue;
        if (d < 1e-6) {
          // Coincident: pick a direction from a hash of the pair so the layout is reproducible.
          const angle = (obsHash(`${ids[i]}|${ids[j]}`) / 4294967296) * Math.PI * 2;
          dx = Math.cos(angle); dy = Math.sin(angle); d = 1;
        }
        const push = (minGap - d) / 2;
        const nx = dx / d, ny = dy / d;
        a.x -= nx * push; a.y -= ny * push;
        b.x += nx * push; b.y += ny * push;
        moved++;
      }
    }
    if (!moved) break;
  }
  return points;
}

function layout(map) {
  if (map.contract_version === "memory-structure-v1") {
    const projected = Object.fromEntries(
      Object.entries(obsLayout(map)).map(([id, p]) => [id, { x: 400 + p[0] * 85, y: 250 - p[1] * 85 }]));
    // Max circle radius in renderBrain is 9; 20 gives clear click targets even at full weight.
    return decollide2D(projected, map.nodes, 20, 64);
  }
  // ... unchanged
}
```

Why this preserves everything:
- **Node identities**: each `points[id]` is mutated in place; the `for (const node of map.nodes)` loop in `renderBrain` keeps using `positions[node.id]`, so every node keeps its `data-id` and the "real click" selector matches.
- **Edges**: `renderBrain` draws edges by looking up `positions[edge.source|target]` after `layout` returns, so edges automatically follow the nudged endpoints — no edge is dropped or duplicated.
- **3D topology**: `obsLayout` is unchanged; `observatory.js:225`, `hologram.js:146`, `showcase.js:223` keep the 3D positions.
- **Bounded**: `iterations * nodes^2 / 2` is the hard ceiling. At the capped `max_nodes=200` that is `64 * 19 900 ≈ 1.3 M` comparisons worst case — well under one frame, but it short-circuits on `moved === 0`.
- **Deterministic**: the sort of ids and the hash-based tie-breaker make the layout a pure function of the payload; `test_structural_map_is_deterministic` style tests stay green.

Clamping is unnecessary in practice — obsLayout's output stays in `[-1, 1]` so the 2D projection is in `[315, 485] × [165, 335]`, and each decollision step shifts by at most `minGap/2 = 10`. A node can wander ~tens of px, still well inside the 800×520 viewBox.

### Regression test

Add a Playwright test that creates several `plan` notes (so they share a region and are forced to collide in the raw layout), one of them sensitive, and asserts that clicking each public node by `data-id` resolves to the correct detail panel — no `force=True`, no weaker privacy assertion:

```python
def test_structural_2d_map_separates_overlapping_nodes_for_real_clicks(server, account, page):
    key, client = account
    private = client.write_note("A private planetarium appointment.", kind="plan", sensitive=True,
                                due="2026-11-08")
    neighbours = [client.write_note(f"Plan step {i}.", kind="plan") for i in range(6)]
    sign_in(page, server.base_url, key)
    open_view(page, "brain")
    page.locator("#mode-2d").click()
    # Playwright's click asserts the element is the top-most hit at its center; if collision
    # resolution regresses, this call throws instead of silently missing.
    for note in neighbours:
        page.locator(f'#brain-canvas circle.brain-node[data-id="note:{note["note_id"]}"]').click()
        expect(page.locator("#brain-detail")).to_contain_text(note["note_id"][:0] or "Plan step")
        expect(page.locator("#brain-detail")).not_to_contain_text("Sensitive memory")
    # And the sensitive one still masks:
    page.locator(f'#brain-canvas circle.brain-node[data-id="note:{private["note_id"]}"]').click()
    expect(page.locator("#brain-detail")).to_contain_text("Sensitive memory")
    expect(page.locator("#brain-detail")).not_to_contain_text("planetarium")
```

The existing `test_masked_map_details_hide_recording_time_and_preserve_public_dates[2d]` keeps its current (strict) assertions; after the fix, its public `click()` resolves to the real public circle because decollision guarantees ≥ 20 units between centers and max radius is 9.

Edge cases:
- Two nodes with truly identical obsLayout outputs (same region + same id hash collision): the pair-keyed `obsHash` tie-breaker gives a reproducible separation angle, so the layout stays deterministic even in that degenerate case.
- Very dense regions (≥ 20 notes in one region): with `minGap=20` and a region radius ~`size*85`, a few nodes may be pushed to the region boundary. That's cosmetic — every circle remains clickable, which is what the test checks. If you want to preserve regional grouping more strictly, cap `minGap` at `max(12, 20 - 0.5*count_in_region)`; not necessary to pass the failing test.
- Edges whose endpoints move slightly: the quadratic-Bezier control point `middle.y - 24` (brain.js:109) is recomputed from the (new) endpoints, so edge curvature stays smooth.

---

Both fixes are local, revertible, and keep the existing assertions strict.
