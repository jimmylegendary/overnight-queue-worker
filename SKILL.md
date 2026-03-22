---
name: overnight-queue-worker
description: "Run overnight autonomous work from a DB-backed task system using `tasks` as the durable source of truth and `task_queue` as the temporal execution buffer. Use when: (1) planning work into task graphs with review/debug/bugfix steps, (2) deduplicating against existing tasks before inserting new ones, (3) polling `task_queue` until it is empty, (4) leasing the next task, executing it, self-reviewing, and creating follow-up tasks as needed, (5) comparing expected vs actual results and branching honestly when work diverges, and (6) checking for stale/hung overnight work before assuming progress."
---

# Overnight Queue Worker

Use this skill for autonomous overnight execution loops backed by Supabase/Postgres.
Keep **meaning** in `tasks`; keep only **currently executable work** in `task_queue`.

## Core rules
- Treat `tasks` as the permanent record.
- Treat `task_queue` as temporal. When a task completes, remove its queue row.
- Stop condition: `select count(*) from task_queue;` returns `0`.
- For DB debugging or verification, prefer **serial execution** over parallelism.
- Before inserting new tasks, check for duplicates by slug/title/goal and reuse existing tasks when possible.
- For research-heavy or branch-heavy work, lock a mainline plan and success criteria before implementation.
- At each meaningful step, compare expected vs actual. If divergence is material, create explicit review/debug/replan tasks and cancel obsolete downstream tasks instead of silently continuing.
- Keep artifacts in predictable folders so later sessions can resume without reconstructing the whole run from chat.

## Standard loop
1. Read current `tasks`, `task_queue`, and recent `task_events`.
2. If needed, write or refresh the mainline plan / branch contract.
3. Create missing tasks only.
4. Sync queue admission.
5. While total `task_queue` row count is not zero:
   - lease one task
   - execute work
   - self review
   - compare expected vs actual
   - mark task status in `tasks`
   - delete the queue row on completion
   - create follow-up review/debug/bugfix/re-review/replan tasks if needed
   - sync queue again
6. Exit only when total `task_queue` row count is `0`.

## Task graph pattern
Preferred slice:
- decision / design / setup
- implementation
- review
- if failed: debugging / bugfix
- re-review / verification
- next slice

Treat `review`, `debugging`, `bugfix`, `verification`, and branch-review / replan tasks as first-class work.

## Monitoring
If unfinished work shows no task-table state change for more than 10 minutes, check whether it is actually stalled before assuming progress. Use `scripts/check_task_stall.py` for slug-prefix freshness checks and alert only on real stalls.

## Resources
### scripts/
- `task_queue_smoke_test.py` — verifies that polling, leasing, dependency unblocking, and queue-empty stop conditions work.
- `check_task_stall.py` — checks whether unfinished work for a slug prefix has gone stale and emits `ALERT` / `NO_ALERT` JSON for monitors.

### references/
- `protocol.md` — compact operating protocol, branching rules, and monitoring guidance.

## When to be careful
- Do not rely on queue history for meaning; keep meaning in `tasks` and `task_events`.
- Do not use active-queue subsets as stop conditions if the intended stop condition is total queue row count.
- Do not batch completion handling. When a task finishes, inspect, self-review, update DB state, and continue immediately.
- Do not keep reusing the same evaluation slice as if it were fresh evidence; branch-heavy research work should tighten its validation protocol, not just try more variants.
