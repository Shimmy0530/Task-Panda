# PR #4 Review Findings — Status Tracker

**Branch:** `task-panda-v0.2` · **PR:** [Shimmy0530/Task-Panda#4](https://github.com/Shimmy0530/Task-Panda/pull/4)
**Reviewed by:** four parallel agents (general code, silent failures, type design, comments)
**Last updated:** 2026-05-07 after commit `2c9bd02`

## Summary

| Severity | Found | Addressed | Open | Policy-resolved |
|---|---|---|---|---|
| Critical | 6 | 5 | 0 | 1 |
| Important | 9 | 0 | 9 | 0 |
| Suggestion | 5 | 0 | 5 | 0 |

Top-3-to-fix-before-merge from the original review are all addressed (#1, #2, #3). The OPSEC question (#6) is resolved as project policy — retired by owner. Important and suggestion items remain open and are candidates for a follow-up PR.

---

## 🔴 Critical

### #1 — Frog-in-backlog state is reachable ✅ **ADDRESSED** (commit `2c9bd02`)

`focus/backend/app/routers/tasks.py:116-128` — PATCH with `day_date: null` previously cleared the day but kept `is_frog=True`, producing a `(day_date=None, is_frog=True)` row that violated the documented invariant.

**Fix shipped:**
- `schemas.py` — `model_validator` on `TaskCreate` rejects `is_frog=True and day_date is None`. `TaskUpdate` rejects the same combo when both fields are explicitly set in one PATCH.
- `tasks.py` — when a PATCH demotes `day_date` to None, the handler now clears `is_frog` automatically.

### #2 — AI subtasks endpoint conflates "atomic" with "broken" ✅ **ADDRESSED** (commit `2c9bd02`)

`focus/backend/app/llm.py:108-113` — `json.loads` failure / network blip / malformed response all returned `[]`, identical to the LLM legitimately saying "no subtasks needed." Frontend treated all three as success.

**Fix shipped:**
- `llm.py` — `subtasks_from_task` now returns `None` on parse failure; `[]` is reserved for genuinely-atomic.
- `capture.py` — `/api/llm/subtasks` surfaces 503 on `None` so the frontend shows an actual error instead of "looks fine, already small."

### #3 — Silent PATCH failure on focus screen ✅ **ADDRESSED** (commit `2c9bd02`)

`focus/frontend/src/routes/focus/+page.svelte:131-133` — bare `catch {}` on subtask toggle PATCH. Auth expiry, validation 400, server 500 all caused the UI to show the box checked while DB stayed unchanged.

**Fix shipped:**
- `focus/+page.svelte` — `toggleSub` snapshots the previous list, applies the optimistic update, and reverts on rejection. New `subErr` state renders an inline rust-colored error under the subtask list, auto-dismissing after 4s.

### #4 — Weekly-review cache poisons on bad output ✅ **ADDRESSED** (commit `2c9bd02`)

`focus/backend/app/routers/capture.py:170-174` — `_WEEKLY_CACHE[key] = (summary, now)` ran unconditionally. Empty string or refusal text would stick for 24 hours; "regenerate" just re-rendered the poisoned value.

**Fix shipped:**
- `capture.py` — pre-cache check rejects empty / whitespace-only summaries and any output missing `## ` headings (the prompt requires three of them, so a refusal almost certainly won't have any). Returns 503 instead of caching.

### #5 — Stale-prompt comment hardcodes "30 days" ✅ **ADDRESSED** (commit `2c9bd02`)

`focus/backend/app/routers/morning.py:226` — comment referenced "30 days" by value rather than the source-of-truth constant `STALE_BACKLOG_DAYS = 30`. Would silently lie if the constant ever changed.

**Fix shipped:**
- `morning.py` — comment rewritten to "re-stamp so it falls outside the stale window" (constant-agnostic).

### #6 — OPSEC redaction removed from prompts ⚙️ **RESOLVED — POLICY**

The PR retired the `[SUBJECT]/[LOCATION]/[DATE]/[CASE_REF]` redaction lines from `SYSTEM_OUTLINE` and never added them to the new `SYSTEM_SUBTASKS` / `SYSTEM_WEEKLY_REVIEW` prompts. UI banners ("no case data") and the README's OPSEC section were also stripped.

**Resolution:** Owner confirmed that prompt-level redaction is intentionally retired and OPSEC is not a concern that needs to be considered for this app. The OPSEC section in `CLAUDE.md` was also removed in commit `2c9bd02`. No code changes needed; this is a project policy decision.

---

## 🟡 Important — open

### #7 — Subtask JSON column lacks write-time validation outside `TaskUpdate` ❌ **OPEN**

`focus/backend/app/models.py` — `subtasks: Mapped[list]` is unparameterized. Direct `Task(...)` construction in `morning.py` carry-prune and `tasks.py` copy paths trusts dict shape; a malformed entry would 500 on the next `TaskOut.from_attributes` read.

**Proposed fix:** small helper in `tasks.py` or `models.py`:
```python
def _validate_subtasks(items) -> list[dict]:
    return [SubtaskItem.model_validate(x).model_dump() for x in items][:MAX_SUBTASKS]
```
Call from PATCH, copy, and morning carry. Centralizes validation across all write paths.

### #8 — Morning ritual rollback loses work without recovery path ❌ **OPEN**

`focus/backend/app/routers/morning.py:198-205` — day-cap check happens *after* mutating rows. On `today_count > 5` a `db.rollback()` wipes everything; user lands back on confirm step with no per-section breakdown of where to trim.

**Proposed fix:** project the count *before* mutating; return a structured 400 (e.g. `{carries: 3, frog: 1, support: 2, pulls: 2, max: 5}`) so the morning UI can highlight the bucket(s) to trim.

### #9 — Morning silently skips bad backlog / stale IDs ❌ **OPEN**

`focus/backend/app/routers/morning.py:159-211` — `Task.id.in_(...)` filters scoped by `user_id` + `day_date.is_(None)` are correct for safety, but mismatches (stale tab, deleted row, raced edit) get silently dropped. User sees "set." on `/plan` with missing tasks.

**Proposed fix:** count matched rows; if `len(matched) != len(payload.pull_from_backlog)` raise 409 with the missing IDs in the response so the frontend can re-sync.

### #10 — Subtask `id` uniqueness not validated ❌ **OPEN**

`focus/backend/app/schemas.py` `SubtaskItem` accepts any 1–64 char string; backend doesn't dedup. Two clients (or buggy retry) could collide; toggle / move / remove all match by `findIndex` on id.

**Proposed fix:** in `update_task` (or via the helper from #7), reject when `len({s.id for s in subtasks}) != len(subtasks)`.

### #11 — Subtask PATCH races itself ❌ **OPEN**

`focus/frontend/src/lib/Subtasks.svelte` — `commit()` always sends the full local list. Two rapid clicks (toggle then add) fire two PATCH requests with overlapping bodies; whichever returns last wins. Compounded by `await load()` in `onSubtasksChange` racing the in-flight PATCH.

**Proposed fix:** serialize PATCHes per task with an in-flight queue (Promise chain) or version with an `etag` / `version` integer column. The fix on `focus/+page.svelte:124-134` (now reverting on failure) helps the symptoms but not the root race.

### #12 — `OperationalError`-swallow in `init_db` is too broad ❌ **OPEN**

`focus/backend/app/db.py:26-41` — `OperationalError` covers more than "duplicate column": disk full, locked DB, permission denied, table doesn't exist. The 4 new ALTERs swallow all of them silently. On a corrupt DB the app boots and the first query against `tasks.subtasks` returns NULL and the JSON decoder dies in a much harder-to-trace location.

**Proposed fix:** check `str(e).lower()` for "duplicate column" before swallowing; log and re-raise otherwise. Or use `PRAGMA table_info(tasks)` to test column existence before issuing ALTER.

### #13 — `carried_count` and `stuck_threshold_days` are unbounded ints ❌ **OPEN**

`focus/backend/app/models.py:18, 36` — no CHECK constraint. Off-by-one decrement could silently underflow.

**Proposed fix:**
```python
__table_args__ = (
    CheckConstraint("carried_count >= 0", name="ck_tasks_carried_count_nonneg"),
)
```
Same for `stuck_threshold_days >= 1`. Cheap insurance.

### #14 — `TaskUpdate.subtasks: None` vs `[]` footgun ❌ **OPEN**

`focus/backend/app/schemas.py:35` + `tasks.py:147` — client sending `{"subtasks": null}` falls into `data["subtasks"] or []` and silently *clears* subtasks even though the intent could be "don't touch."

**Proposed fix:** in `update_task`, branch explicitly: `if data.get("subtasks") is None: pass` (no-op) vs `if data.get("subtasks") == []: clear`. Or drop `| None` from the schema so unset is the only "don't touch" path.

### #15 — Plan page swallows backlog-count failures ❌ **OPEN**

`focus/frontend/src/routes/plan/+page.svelte:30-31` — empty catch hides auth/server/network failures. Footer reads "📦 backlog" with no signal that anything broke.

**Proposed fix:** at minimum `console.error` the rejection. Better: render a small error indicator near the footer chip.

---

## 🔵 Suggestions — open

### #S1 — Numbered section markers in `morning.py` restate code ❌ **OPEN**

`focus/backend/app/routers/morning.py:472+` — `# 1.` / `# 2.` / etc. headers narrate what the code already shows. Per project rule (CLAUDE.md), comments should explain WHY, not WHAT.

**Action:** delete the numbered headers wholesale; keep only `# 5. Stale-backlog acknowledgements.` if anything stays (least obvious of the bunch).

### #S2 — `Subtasks.svelte` inline prop-shape comments duplicate `export let` ❌ **OPEN**

`focus/frontend/src/lib/Subtasks.svelte:907-908` — `// must include subtasks: [{id, title, done}]` and `// (newSubtasks: list) => Promise<void>` will rot the moment the schema changes.

**Action:** delete both; rely on the caller-site contract or convert to JSDoc `@type` if type hints are wanted.

### #S3 — `_WEEKLY_CACHE` is process-local and never evicted ❌ **OPEN** (low priority)

`focus/backend/app/routers/capture.py:103` — module-level dict survives until container restart; grows by one entry per day forever. For single-user, bounded by ~365 entries/yr; not a real leak. A backend restart silently re-bills Groq on the next click.

**Action:** persist in a tiny `weekly_review_cache` table, or prune entries older than 7 days on each access. Defer until the cost actually shows up.

### #S4 — `copy_task` strips frog flag silently ❌ **OPEN** (low priority)

`focus/backend/app/routers/tasks.py:817` — hardcodes `is_frog_target=False` (correct semantics for copy) but the user gets no signal that the source's frog flag was dropped.

**Action:** include `frog_demoted: bool` in the response, or surface a toast in the frontend after a successful copy of a frog.

### #S5 — `renderSummary()` in `/review` uses `{@html}` on LLM output ❌ **OPEN** (low priority)

`focus/frontend/src/routes/review/+page.svelte:84` — escape pass on each line is correct, but the trust boundary is implicit. A future contributor refactoring `renderSummary` could break the escape without realizing.

**Action:** add a one-line comment naming the trust assumption: `// Renders LLM output; relies on esc() escaping all HTML metacharacters per line.`

---

## Recommended next steps

1. **Merge PR #4** — top-3 critical fixes are in; remaining open items are not blockers for shipping the v0.2 feature set.
2. **Open a follow-up PR** for the Important items (#7 – #15). The cluster around subtask validation (#7, #10, #14) is naturally one PR; database hardening (#12, #13) another; and the morning-ritual UX gaps (#8, #9) a third. The frontend race (#11) and silent catch (#15) can ride with whichever PR happens first.
3. **Defer Suggestions** — these are quality-of-life polish, not correctness issues. Roll up into a "review nits" PR when convenient.
4. **Verify on chemex** post-merge — run through verification list 1-12 from the original spec (`~/.claude/plans/ok-as-drafted-also-eager-panda.md`) against `focus.baltito.com` to confirm no regressions.
