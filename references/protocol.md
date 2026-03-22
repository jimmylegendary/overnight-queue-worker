# Overnight Queue Worker Protocol

## Semantic split
- `tasks`: durable record of intent, state, outcome, and context
- `task_queue`: temporal execution buffer only

## Plan before run
- Freeze a mainline plan when the work is research-heavy, branch-heavy, or likely to diverge.
- Record expected result, artifact root, and success criteria for each major slice.
- Change the plan through explicit `decision` / `review` / `replan` tasks instead of silent drift.

## Required task types
- `implementation`
- `review`
- `debugging`
- `bugfix`
- `verification`
- `design`
- `decision`
- `setup`
- `deploy`
- `meta`

## Required execution behavior
1. Read current tasks, queue state, and recent events.
2. Detect duplicate or already-covered work before inserting tasks.
3. Insert only missing tasks.
4. Sync queue admission.
5. Lease one task.
6. Execute.
7. Self review.
8. Compare expected vs actual.
9. If divergence is material, create follow-up review/debug/replan tasks and cancel obsolete downstream tasks when necessary.
10. Remove the queue row on completion.
11. Sync queue again.
12. Continue until total queue row count is zero.

## Failure branching
If review finds a problem:
- create a `bugfix` or `debugging` task
- create a `re-review` / `review` task after the fix if needed
- use dependencies so the next implementation slice does not open too early
- if the problem invalidates the branch direction itself, create a `decision` / `replan` task and explicitly stop obsolete downstream work

## Monitoring / stall handling
- If unfinished work shows no `updated_at` movement for more than the agreed threshold (for example 10 minutes), run `scripts/check_task_stall.py --slug-prefix ...`.
- Alert only on real stalls; stay quiet on healthy checks.
- Distinguish between "nothing leased yet" and "leased but stale" when reporting.

## Reliability notes
- Prefer serial execution for DB state changes and assertions.
- Completion handling should be immediate.
- Queue-empty should be tested directly, not inferred.
- Branch reviews should say explicitly whether realism improved, alpha improved, both improved, or neither improved.
