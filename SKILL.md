---
name: overnight-queue-worker
description: Run overnight autonomous work from a DB-backed task system using `tasks` as the durable source of truth and `task_queue` as the temporal execution buffer. Use when: (1) planning work into task graphs with review/debug/bugfix steps, (2) deduplicating against existing tasks before inserting new ones, (3) polling `task_queue` until it is empty, (4) leasing the next task, executing it, self-reviewing, and creating follow-up tasks as needed, and (5) validating that queue-empty is the stop condition for overnight execution.
---

# Overnight Queue Worker

## Overview
Use this skill for autonomous overnight execution loops backed by Supabase/Postgres.
Keep **meaning** in `tasks`; keep only **currently executable work** in `task_queue`.

## Core rules
- Treat `tasks` as the permanent record.
- Treat `task_queue` as temporal. When a task completes, remove its queue row.
- Stop condition: `select count(*) from task_queue;` returns `0`.
- For DB debugging or verification, prefer **serial execution** over parallelism.
- Before inserting new tasks, check for duplicates by slug/title/goal and reuse existing tasks when possible.

## Standard loop
1. Read existing `tasks` and `task_queue`.
2. Create missing tasks only.
3. Sync queue admission.
4. While `task_queue` is not empty:
   - lease next task
   - execute work
   - self review
   - mark task status in `tasks`
   - delete queue row on completion
   - create follow-up review/debug/bugfix/re-review tasks if needed
   - sync queue again
5. Exit when `task_queue` row count is `0`.

## Task graph pattern
Preferred pattern:
- implementation
- review
- if failed: bugfix
- re-review
- next implementation

Treat `review`, `debugging`, `bugfix`, and `verification` as first-class tasks.

## Resources
### scripts/
- `task_queue_smoke_test.py` — verifies that polling, leasing, dependency unblocking, and queue-empty stop conditions work.

### references/
- `protocol.md` — compact operating protocol and task-type guidance.

## When to be careful
- Do not rely on queue history for meaning; keep meaning in `tasks` and `task_events`.
- Do not use active-queue subsets as stop conditions if the intended stop condition is total queue row count.
- Do not batch completion handling. When a task finishes, inspect, self-review, update DB state, and continue immediately.
