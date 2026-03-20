# overnight-queue-worker

A compact AgentSkill for overnight autonomous work driven by a DB-backed `tasks` + `task_queue` model.

## What it does
- treats `tasks` as the durable source of truth
- treats `task_queue` as the temporal execution buffer
- supports queue polling until row count reaches zero
- supports leasing next work item and completing it cleanly
- encourages review/debug/bugfix/re-review as first-class task types

## Files
- `SKILL.md`
- `references/protocol.md`
- `scripts/task_queue_smoke_test.py`
- `overnight-queue-worker.skill`

## Usage
Use this skill when you want an agent to:
- plan tasks into a DB-backed work graph
- sync queue admission
- poll the queue until empty
- execute work overnight in bounded steps

## Notes
This repo is the GitHub home for the skill. ClawHub publishing can be done separately when authenticated.
