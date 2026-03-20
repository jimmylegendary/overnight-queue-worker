# Overnight Queue Worker Protocol

## Semantic split
- `tasks`: durable record of intent, state, outcome, and context
- `task_queue`: temporal execution buffer only

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
1. Read current tasks and queue state.
2. Detect duplicate or already-covered work before inserting tasks.
3. Insert only missing tasks.
4. Poll queue.
5. Lease one task.
6. Execute.
7. Self review.
8. Create follow-up tasks if needed.
9. Remove queue row on completion.
10. Continue until queue row count is zero.

## Failure branching
If review finds a problem:
- create a `bugfix` task
- create a `re-review` / `review` task after the bugfix if needed
- use dependencies so the next implementation slice does not open too early

## Reliability notes
- Prefer serial execution for DB state changes and assertions.
- Completion handling should be immediate.
- Queue-empty should be tested directly, not inferred.
