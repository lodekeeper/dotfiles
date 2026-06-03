#!/usr/bin/env python3
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

JOBS_PATH = Path(os.environ.get('CRON_JOBS_PATH', '/home/openclaw/.openclaw/cron/jobs.json'))
STATE_PATH = Path(os.environ.get('CRON_HEALTH_STATE_PATH', '/home/openclaw/cron-health-state.json'))
WORKSPACE_PATH = Path(os.environ.get('WORKSPACE_PATH', '/home/openclaw/.openclaw/workspace'))
AUTONOMY_CADENCE_JOB_ID = 'virtual:autonomy-audit-cadence'
AUTONOMY_CADENCE_NAME = 'autonomy-audit-cadence'


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


def compact_details(output):
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    interesting = [
        line for line in lines
        if (
            line.startswith('- ')
            or 'missing' in line.lower()
            or 'File not found' in line
        )
    ]
    return ' | '.join(interesting[:6]) or (lines[-1] if lines else 'no output')


def check_autonomy_audit_cadence(now):
    """Return a virtual failing-job entry when the daily audit snapshot is stale.

    Cron status alone can miss a successful-looking job that failed to update
    notes/autonomy-gaps.md. Treat the latest-pair cadence guard as a virtual
    cron failure so the existing watchdog state/dedup logic handles it.
    """
    script = Path(os.environ.get(
        'AUTONOMY_CADENCE_SCRIPT',
        str(WORKSPACE_PATH / 'scripts/notes/check-autonomy-audit-cadence.py'),
    ))
    target = Path(os.environ.get(
        'AUTONOMY_CADENCE_FILE',
        str(WORKSPACE_PATH / 'notes/autonomy-gaps.md'),
    ))
    reference_date = os.environ.get('AUTONOMY_CADENCE_REFERENCE_DATE')
    expected_every_days = os.environ.get('AUTONOMY_CADENCE_EXPECTED_EVERY_DAYS')

    if not script.exists():
        output = f'MISSING guard script: {script}'
        return {
            'name': AUTONOMY_CADENCE_NAME,
            'id': AUTONOMY_CADENCE_JOB_ID,
            'signature': f'{AUTONOMY_CADENCE_JOB_ID}:missing-script:{script}',
            'lastStatus': 'missing-script',
            'lastDeliveryStatus': 'n/a',
            'consecutiveErrors': 1,
            'lastRunAtMs': now,
            'nextRunAtMs': None,
            'details': output,
        }

    cmd = [
        'python3',
        str(script),
        '--file',
        str(target),
        '--latest-only',
        '--require-current',
        '--fail-on-gap',
    ]
    if reference_date:
        cmd.extend(['--reference-date', reference_date])
    if expected_every_days:
        cmd.extend(['--expected-every-days', expected_every_days])

    try:
        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or '') if isinstance(exc.stdout, str) else ''
        output = output.strip() or 'autonomy cadence guard timed out'
        return {
            'name': AUTONOMY_CADENCE_NAME,
            'id': AUTONOMY_CADENCE_JOB_ID,
            'signature': f'{AUTONOMY_CADENCE_JOB_ID}:timeout:{output}',
            'lastStatus': 'timeout',
            'lastDeliveryStatus': 'n/a',
            'consecutiveErrors': 1,
            'lastRunAtMs': now,
            'nextRunAtMs': None,
            'details': compact_details(output),
        }

    if result.returncode == 0:
        return None

    output = result.stdout or ''
    return {
        'name': AUTONOMY_CADENCE_NAME,
        'id': AUTONOMY_CADENCE_JOB_ID,
        'signature': f'{AUTONOMY_CADENCE_JOB_ID}:{result.returncode}:{output.strip()}',
        'lastStatus': 'gap' if result.returncode == 2 else f'guard-error-{result.returncode}',
        'lastDeliveryStatus': 'n/a',
        'consecutiveErrors': 1,
        'lastRunAtMs': now,
        'nextRunAtMs': None,
        'details': compact_details(output),
    }


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

    cadence_failure = check_autonomy_audit_cadence(now)
    if cadence_failure is not None:
        current[AUTONOMY_CADENCE_JOB_ID] = cadence_failure
        prev = active_failures.get(AUTONOMY_CADENCE_JOB_ID)
        if prev is None or prev.get('signature') != cadence_failure.get('signature'):
            new_alerts.append(cadence_failure)

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
            if a.get('details'):
                lines.append(f"  details: {a['details']}")
        lines.append('Action: investigate and fix the failing cron(s) now.')

    if recovered:
        lines.append('')
        lines.append(f"Recovered since last check: {len(recovered)}")
        for r in recovered:
            lines.append(f"- {r.get('name')} ({r.get('id')})")

    print('\n'.join(lines))


if __name__ == '__main__':
    main()
