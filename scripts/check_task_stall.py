#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List


def run_psql(container: str, db: str, user: str, sql: str) -> str:
    proc = subprocess.run(
        [
            "docker", "exec", "-i", container,
            "psql", "-U", user, "-d", db,
            "-F", "\t", "-Atqc", sql,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "psql failed")
    return proc.stdout.strip()


def parse_tsv_lines(text: str, expected: int) -> List[List[str]]:
    if not text:
        return []
    rows: List[List[str]] = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < expected:
            parts += [""] * (expected - len(parts))
        rows.append(parts[:expected])
    return rows


def load_json(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def save_json(path: Path, data: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def main() -> int:
    ap = argparse.ArgumentParser(description="Check whether task DB work has gone stale.")
    ap.add_argument("--slug-prefix", required=True, help="Task slug prefix, e.g. btcusdt-20xsearch-")
    ap.add_argument("--stale-minutes", type=float, default=10.0)
    ap.add_argument("--repeat-alert-minutes", type=float, default=60.0)
    ap.add_argument("--state-file", required=True)
    ap.add_argument("--container", default="supabase-db")
    ap.add_argument("--db", default="postgres")
    ap.add_argument("--user", default="postgres")
    args = ap.parse_args()

    prefix = args.slug_prefix.replace("'", "''")
    state_path = Path(args.state_file)
    now_ts = time.time()

    summary_sql = f"""
with target as (
  select slug, status, task_type, priority, updated_at
  from public.tasks
  where slug like '{prefix}%'
),
unfinished as (
  select * from target where status <> 'done'
),
queue_rows as (
  select count(*) as queue_count
  from public.task_queue q
  join public.tasks t on t.id = q.task_id
  where t.slug like '{prefix}%'
)
select
  (select count(*) from target),
  (select count(*) from unfinished),
  (select count(*) from unfinished where status in ('active', 'in_progress')),
  (select count(*) from unfinished where status = 'ready'),
  (select count(*) from unfinished where status = 'queued'),
  (select queue_count from queue_rows),
  coalesce(round(extract(epoch from (now() - max(updated_at))) / 60.0, 2)::text, ''),
  coalesce(to_char(max(updated_at) at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), '')
from unfinished;
"""
    latest_sql = f"""
select slug, status, task_type, priority,
       coalesce(round(extract(epoch from (now() - updated_at)) / 60.0, 2)::text, ''),
       to_char(updated_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
from public.tasks
where slug like '{prefix}%'
  and status <> 'done'
order by updated_at desc, slug asc
limit 5;
"""
    queue_sql = f"""
select t.slug, t.status, t.task_type, t.priority,
       coalesce(round(extract(epoch from (now() - t.updated_at)) / 60.0, 2)::text, ''),
       to_char(t.updated_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
from public.task_queue q
join public.tasks t on t.id = q.task_id
where t.slug like '{prefix}%'
order by q.created_at asc
limit 5;
"""

    summary_row = parse_tsv_lines(run_psql(args.container, args.db, args.user, summary_sql), 8)
    latest_rows = parse_tsv_lines(run_psql(args.container, args.db, args.user, latest_sql), 6)
    queue_rows = parse_tsv_lines(run_psql(args.container, args.db, args.user, queue_sql), 6)

    if not summary_row:
        total = unfinished = active = ready = queued = queue_count = 0
        last_change_min = 0.0
        last_change_at = ""
    else:
        row = summary_row[0]
        total = int(row[0] or 0)
        unfinished = int(row[1] or 0)
        active = int(row[2] or 0)
        ready = int(row[3] or 0)
        queued = int(row[4] or 0)
        queue_count = int(row[5] or 0)
        last_change_min = float(row[6] or 0.0)
        last_change_at = row[7]

    observed_ages = [last_change_min]
    observed_timestamps = [last_change_at] if last_change_at else []
    observed_active = active
    for rows in (latest_rows, queue_rows):
        for r in rows:
            if r[4]:
                observed_ages.append(float(r[4]))
            if r[5]:
                observed_timestamps.append(r[5])
            if r[1] in ("active", "in_progress"):
                observed_active = max(observed_active, 1)

    if observed_ages:
        last_change_min = min(observed_ages)
    if observed_timestamps:
        last_change_at = max(observed_timestamps)
    active = observed_active

    stale = unfinished > 0 and last_change_min >= args.stale_minutes
    fingerprint = f"{prefix}|{unfinished}|{active}|{ready}|{queued}|{queue_count}|{last_change_at}"
    state = load_json(state_path)
    last_alert_fp = str(state.get("last_alert_fingerprint", ""))
    last_alert_ts = float(state.get("last_alert_ts", 0.0) or 0.0)
    should_alert = stale and (
        fingerprint != last_alert_fp or (now_ts - last_alert_ts) >= args.repeat_alert_minutes * 60.0
    )

    out = {
        "slug_prefix": args.slug_prefix,
        "total_tasks": total,
        "unfinished_count": unfinished,
        "active_count": active,
        "ready_count": ready,
        "queued_count": queued,
        "queue_count": queue_count,
        "last_change_age_min": last_change_min,
        "last_change_at": last_change_at,
        "stale": stale,
        "should_alert": should_alert,
        "latest_unfinished": [
            {
                "slug": r[0], "status": r[1], "task_type": r[2], "priority": r[3],
                "age_min": float(r[4] or 0.0), "updated_at": r[5],
            }
            for r in latest_rows
        ],
        "queue_head": [
            {
                "slug": r[0], "status": r[1], "task_type": r[2], "priority": r[3],
                "age_min": float(r[4] or 0.0), "updated_at": r[5],
            }
            for r in queue_rows
        ],
    }

    if stale and should_alert:
        state.update({
            "last_alert_fingerprint": fingerprint,
            "last_alert_ts": now_ts,
        })
    elif not stale:
        state.update({
            "last_alert_fingerprint": "",
            "last_alert_ts": 0.0,
            "last_healthy_ts": now_ts,
        })
    save_json(state_path, state)

    if should_alert:
        reason = "likely_stalled_before_first_lease" if active == 0 and ready > 0 and queue_count > 0 else "stale_unfinished_work"
        print("ALERT\t" + json.dumps({**out, "reason": reason}, ensure_ascii=False))
    else:
        print("NO_ALERT\t" + json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print("ERROR\t" + json.dumps({"error": str(e)}, ensure_ascii=False))
        raise SystemExit(0)
