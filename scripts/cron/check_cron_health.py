#!/usr/bin/env python3
import json
import time
from pathlib import Path
from datetime import datetime, timezone

JOBS_PATH = Path('/home/openclaw/.openclaw/cron/jobs.json')
STATE_PATH = Path('/home/openclaw/cron-health-state.json')


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def fmt_ms(ms):
    if not ms:
        return 'n/a'
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')


def build_failure_signature(job):
    st = job.get('state', {})
    return f"{job.get('id')}:{st.get('lastRunAtMs')}:{st.get('lastStatus')}:{st.get('lastDeliveryStatus')}:{st.get('consecutiveErrors')}"


def is_job_failing(job):
    if not job.get('enabled', False):
        return False

    # Ignore the watchdog itself to avoid loops.
    if job.get('name') == 'cron-health-watchdog':
        return False

    st = job.get('state', {})
    last_status = st.get('lastStatus') or st.get('lastRunStatus')
    last_delivery = st.get('lastDeliveryStatus')
    errors = int(st.get('consecutiveErrors') or 0)

    if errors > 0:
        return True
    if last_status and str(last_status).lower() not in {'ok', 'success'}:
        return True
    if last_delivery and str(last_delivery).lower() in {'failed', 'error', 'timeout'}:
        return True

    return False


def main():
    now = int(time.time() * 1000)

    jobs_root = load_json(JOBS_PATH, {})
    jobs = jobs_root.get('jobs', [])

    state = load_json(STATE_PATH, {'activeFailures': {}, 'updatedAtMs': now})
    active_failures = state.get('activeFailures', {})

    current = {}
    new_alerts = []
    recovered = []

    for job in jobs:
        if not is_job_failing(job):
            continue

        sig = build_failure_signature(job)
        job_id = job.get('id')
        info = {
            'name': job.get('name'),
            'id': job_id,
            'signature': sig,
            'lastStatus': job.get('state', {}).get('lastStatus') or job.get('state', {}).get('lastRunStatus'),
            'lastDeliveryStatus': job.get('state', {}).get('lastDeliveryStatus'),
            'consecutiveErrors': int(job.get('state', {}).get('consecutiveErrors') or 0),
            'lastRunAtMs': job.get('state', {}).get('lastRunAtMs'),
            'nextRunAtMs': job.get('state', {}).get('nextRunAtMs'),
        }
        current[job_id] = info

        prev = active_failures.get(job_id)
        if prev is None or prev.get('signature') != sig:
            new_alerts.append(info)

    # detect recoveries (was failing before, not now)
    for old_id in active_failures.keys():
        if old_id not in current:
            recovered.append(active_failures[old_id])

    state['activeFailures'] = current
    state['updatedAtMs'] = now
    save_json(STATE_PATH, state)

    if not new_alerts and not recovered:
        print('NO_REPLY')
        return

    lines = []
    if new_alerts:
        lines.append(f"Cron watchdog: detected {len(new_alerts)} failing job(s).")
        for a in new_alerts:
            lines.append(
                f"- {a['name']} ({a['id']}): lastStatus={a['lastStatus']}, "
                f"delivery={a['lastDeliveryStatus']}, consecutiveErrors={a['consecutiveErrors']}, "
                f"lastRun={fmt_ms(a['lastRunAtMs'])}, nextRun={fmt_ms(a['nextRunAtMs'])}"
            )
        lines.append('Action: investigate and fix the failing cron(s) now.')

    if recovered:
        lines.append('')
        lines.append(f"Recovered since last check: {len(recovered)}")
        for r in recovered:
            lines.append(f"- {r.get('name')} ({r.get('id')})")

    print('\n'.join(lines))


if __name__ == '__main__':
    main()
