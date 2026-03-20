#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import time


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def psql(container: str, db: str, user: str, sql: str) -> str:
    cmd = [
        'docker', 'exec', container,
        'psql', '-U', user, '-d', db, '-Atqc', sql,
    ]
    return run(cmd)


def lease_next(container: str, db: str, user: str, claimer: str):
    sql = f"select row_to_json(t) from public.lease_next_task('{claimer}', 30) as t;"
    out = psql(container, db, user, sql)
    return json.loads(out) if out else None


def complete_task(container: str, db: str, user: str, task_id: str, actor: str, summary: str):
    safe = summary.replace("'", "''")
    psql(container, db, user, f"select public.complete_task('{task_id}'::uuid, '{actor}', '{safe}');")


def queue_count(container: str, db: str, user: str) -> int:
    return int(psql(container, db, user, 'select count(*) from public.task_queue;'))


def queue_snapshot(container: str, db: str, user: str):
    sql = "select coalesce(json_agg(x), '[]'::json) from (select t.slug, q.status, q.leased_by from public.task_queue q join public.tasks t on t.id=q.task_id order by q.created_at) x;"
    return json.loads(psql(container, db, user, sql))


def task_snapshot(container: str, db: str, user: str):
    sql = "select coalesce(json_agg(x), '[]'::json) from (select slug, status from public.tasks order by created_at) x;"
    return json.loads(psql(container, db, user, sql))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--container', default='supabase-db')
    ap.add_argument('--db', default='postgres')
    ap.add_argument('--user', default='postgres')
    ap.add_argument('--claimer', default='overnight-smoke-test')
    ap.add_argument('--sleep-ms', type=int, default=200)
    args = ap.parse_args()

    history = []
    idle_loops = 0

    while True:
        remaining = queue_count(args.container, args.db, args.user)
        history.append({
            'event': 'queue_count',
            'remaining': remaining,
            'queue': queue_snapshot(args.container, args.db, args.user),
            'tasks': task_snapshot(args.container, args.db, args.user),
        })
        if remaining == 0:
            break

        leased = lease_next(args.container, args.db, args.user, args.claimer)
        if leased is None:
            idle_loops += 1
            history.append({'event': 'no_lease', 'idle_loops': idle_loops})
            if idle_loops >= 3:
                print(json.dumps(history, indent=2))
                raise SystemExit('Queue not empty but no task could be leased repeatedly')
            time.sleep(args.sleep_ms / 1000)
            continue

        idle_loops = 0
        history.append({'event': 'leased', 'task': leased})
        time.sleep(args.sleep_ms / 1000)
        complete_task(args.container, args.db, args.user, leased['task_id'], args.claimer, f"Completed {leased['slug']} in smoke test")
        history.append({'event': 'completed', 'task_id': leased['task_id'], 'slug': leased['slug']})
        time.sleep(args.sleep_ms / 1000)

    print(json.dumps(history, indent=2))


if __name__ == '__main__':
    main()
