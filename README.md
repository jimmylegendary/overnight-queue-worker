# overnight-queue-worker

A compact AgentSkill for overnight autonomous work driven by a DB-backed `tasks` + `task_queue` model.

## What it does
- treats `tasks` as the durable source of truth
- treats `task_queue` as the temporal execution buffer
- supports queue polling until total row count reaches zero
- supports leasing next work item and completing it cleanly
- encourages review / debug / bugfix / re-review as first-class task types
- supports branch-aware execution with explicit **expected vs actual** reviews and replans
- includes a small watchdog helper for detecting stale / hung overnight work

## Files
- `SKILL.md`
- `references/protocol.md`
- `scripts/task_queue_smoke_test.py`
- `scripts/check_task_stall.py`
- `overnight-queue-worker.skill`

## Usage
Use this skill when you want an agent to:
- plan tasks into a DB-backed work graph
- freeze a mainline plan before overnight execution
- sync queue admission
- poll the queue until empty
- execute work overnight in bounded steps
- branch honestly when actual results diverge from expectations
- monitor for stale task-table state during long runs

## Quick checks
Smoke test the queue lifecycle:

```bash
python3 scripts/task_queue_smoke_test.py --container supabase-db --db postgres --user postgres
```

Check whether a slug prefix looks stalled:

```bash
python3 scripts/check_task_stall.py \
  --slug-prefix btcusdt-20xsearch- \
  --stale-minutes 10 \
  --state-file /tmp/overnight-watch.json
```

The script prints one of:
- `NO_ALERT\t{...}`
- `ALERT\t{...}`
- `ERROR\t{...}`

## Notes
This repo is the GitHub home for the skill. ClawHub publishing can be done separately when authenticated.
