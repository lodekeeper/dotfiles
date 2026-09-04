#!/usr/bin/env python3
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

JOBS_PATH = Path(os.environ.get('CRON_JOBS_PATH', '/home/openclaw/.openclaw/cron/jobs.json'))
STATE_PATH = Path(os.environ.get('CRON_HEALTH_STATE_PATH', '/home/openclaw/cron-health-state.json'))
WORKSPACE_PATH = Path(os.environ.get('WORKSPACE_PATH', '/home/openclaw/.openclaw/workspace'))
OPENCLAW_BIN = Path(os.environ.get(
    'OPENCLAW_BIN',
    '/home/openclaw/.nvm/versions/node/v22.22.0/bin/openclaw',
))
AUTONOMY_CADENCE_JOB_ID = 'virtual:autonomy-audit-cadence'
AUTONOMY_CADENCE_NAME = 'autonomy-audit-cadence'
SELF_IMPROVEMENT_AUDIT_JOB_ID = 'd7f95873-f30c-4f41-b944-3345542c5261'
SELF_IMPROVEMENT_AUDIT_NAME = 'self-improvement-audit-daily'
NIGHTLY_MEMORY_JOB_NAME = 'nightly-memory-consolidation'
NIGHTLY_MEMORY_QMD_JOB_ID = 'virtual:nightly-memory-qmd-index-health'
NIGHTLY_MEMORY_QMD_NAME = 'nightly-memory-qmd-index-health'
NEXT_AUDIT_PRIORITIES_JOB_NAME = 'next-audit-priorities-reminder'
NIGHTLY_MEMORY_COMPLETE_RE = re.compile(r'^\[(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z\] Nightly memory cycle complete$', re.MULTILINE)
QMD_EMBED_DURATION_RE = re.compile(r'Done! Embedded .+ in (?P<minutes>\d+)m (?P<seconds>\d+)s')
QMD_ANOMALY_PATTERNS = (
    re.compile(r'Error embedding ".+": SqliteError: UNIQUE constraint failed on vectors_vec primary key'),
    re.compile(r'RangeError: Invalid count value: -?\d+'),
    re.compile(r'Error: handelize: path ".+" has no valid filename content'),
)


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


def load_cron_jobs():
    jobs_root = load_json(JOBS_PATH, None)
    if isinstance(jobs_root, dict) and isinstance(jobs_root.get('jobs'), list):
        return jobs_root.get('jobs', [])

    if not OPENCLAW_BIN.exists():
        return []

    try:
        result = subprocess.run(
            [str(OPENCLAW_BIN), 'cron', 'list', '--json'],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return []

    if result.returncode != 0:
        return []

    try:
        live_root = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    jobs = live_root.get('jobs', [])
    return jobs if isinstance(jobs, list) else []


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


def load_cron_run_history(job_id, limit=8):
    if not OPENCLAW_BIN.exists():
        return []

    try:
        result = subprocess.run(
            [
                str(OPENCLAW_BIN),
                'cron',
                'runs',
                '--id',
                job_id,
                '--limit',
                str(limit),
                '--timeout',
                '10000',
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return []

    if result.returncode != 0:
        return []

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    entries = payload.get('entries', [])
    return entries if isinstance(entries, list) else []


def run_history_reason(entry):
    error = entry.get('error')
    if isinstance(error, str) and error:
        return error

    diagnostics = entry.get('diagnostics')
    if isinstance(diagnostics, dict):
        summary = diagnostics.get('summary')
        if isinstance(summary, str) and summary:
            return summary

    reason = entry.get('errorReason') or entry.get('cause') or entry.get('status')
    return str(reason) if reason else 'unknown failure'


def summarize_recent_run_failures(entries):
    index = 0
    while index < len(entries):
        status = str(entries[index].get('status') or '').lower()
        if status not in {'ok', 'success'}:
            break
        index += 1

    failures = []
    for entry in entries[index:]:
        status = str(entry.get('status') or '').lower()
        if status in {'ok', 'success'}:
            break
        failures.append(entry)

    if not failures:
        return None

    oldest = failures[-1]
    newest = failures[0]
    reason = run_history_reason(newest)
    first_run = fmt_ms(oldest.get('runAtMs') or oldest.get('ts'))
    latest_run = fmt_ms(newest.get('runAtMs') or newest.get('ts'))
    label = 'consecutive failure(s)' if index == 0 else 'consecutive prior failure(s)'
    return (
        f'{SELF_IMPROVEMENT_AUDIT_NAME} recent run history: '
        f'{len(failures)} {label} from {first_run} to {latest_run} '
        f'({reason})'
    )


def describe_recent_self_improvement_failures():
    return summarize_recent_run_failures(load_cron_run_history(SELF_IMPROVEMENT_AUDIT_JOB_ID))


def ms_to_utc_date(ms):
    if not ms:
        return datetime.now(timezone.utc).strftime('%Y-%m-%d')
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d')


def parse_utc_log_timestamp(ts):
    return int(datetime.strptime(ts, '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc).timestamp() * 1000)


def newest_mtime_ms(paths):
    newest = None
    for path in paths:
        try:
            mtime_ms = int(path.stat().st_mtime * 1000)
        except OSError:
            continue
        newest = mtime_ms if newest is None else max(newest, mtime_ms)
    return newest


def describe_nightly_memory_timeout(job):
    """Annotate chronic nightly-memory timeout failures with local pipeline evidence."""
    if job.get('name') != NIGHTLY_MEMORY_JOB_NAME:
        return None

    st = job.get('state', {})
    last_status = str(st.get('lastStatus') or st.get('lastRunStatus') or '').lower()
    last_duration_ms = st.get('lastDurationMs')
    timeout_seconds = (
        job.get('timeoutSeconds')
        or job.get('payload', {}).get('timeoutSeconds')
    )
    looks_like_timeout = 'timeout' in last_status
    if not looks_like_timeout and timeout_seconds and last_duration_ms:
        looks_like_timeout = int(last_duration_ms) >= int(timeout_seconds) * 1000
    if not looks_like_timeout:
        return None

    last_run_ms = st.get('lastRunAtMs') or st.get('runningAtMs') or int(time.time() * 1000)
    run_date = ms_to_utc_date(last_run_ms)
    log_path = WORKSPACE_PATH / 'memory' / f'memory-cycle-{run_date}.log'
    if not log_path.exists():
        return f'nightly memory local check: log missing for {run_date} ({log_path}); timeout root cause still unknown'

    try:
        log_text = log_path.read_text(encoding='utf-8', errors='replace')
    except OSError as exc:
        return f'nightly memory local check: could not read {log_path}: {exc}'

    complete_matches = list(NIGHTLY_MEMORY_COMPLETE_RE.finditer(log_text))
    completion_ms = None
    completion_label = None
    if complete_matches:
        completion_label = complete_matches[-1].group('ts') + 'Z'
        completion_ms = parse_utc_log_timestamp(complete_matches[-1].group('ts'))

    artifact_paths = [
        WORKSPACE_PATH / 'bank' / 'state.json',
        WORKSPACE_PATH / '.memory' / 'index.sqlite',
    ]
    entity_root = WORKSPACE_PATH / 'bank' / 'entities'
    if entity_root.exists():
        for child in entity_root.glob('*/*'):
            artifact_paths.append(child)
    newest_artifact_ms = newest_mtime_ms(artifact_paths)

    fresh_cutoff_ms = int(last_run_ms) - (5 * 60 * 1000)
    completed_after_run = completion_ms is not None and completion_ms >= fresh_cutoff_ms
    artifacts_fresh = newest_artifact_ms is not None and newest_artifact_ms >= fresh_cutoff_ms
    cpu_fallback = any(
        marker in log_text
        for marker in (
            'no GPU acceleration, running on CPU',
            'Falling back to CPU',
            'CUDA Toolkit not found',
            'Could not find nvcc',
        )
    )
    duration_match = list(QMD_EMBED_DURATION_RE.finditer(log_text))
    embed_duration = None
    if duration_match:
        last_duration = duration_match[-1]
        embed_duration = f"{last_duration.group('minutes')}m{last_duration.group('seconds')}s"

    if completed_after_run and artifacts_fresh:
        parts = [f'nightly memory local check: pipeline completed at {completion_label} and core artifacts are fresh']
        if cpu_fallback:
            parts.append('QMD used CPU fallback')
        if embed_duration:
            parts.append(f'embedding step took {embed_duration}')
        if timeout_seconds:
            parts.append(f'cron timeoutSeconds={timeout_seconds} is likely too low; proposed config fix remains raising it to ~2700s')
        return '; '.join(parts)

    if completion_ms is None:
        return f'nightly memory local check: no completion marker in {log_path}; timeout may reflect a real incomplete run'

    if not artifacts_fresh:
        return f'nightly memory local check: completion marker exists at {completion_label}, but core artifacts were not fresh relative to last run'

    return f'nightly memory local check: latest completion at {completion_label} predates the cron timeout window'


def describe_mtime_evidence_timeout(job, target_paths, label):
    """Generalized version of describe_nightly_memory_timeout for jobs with no dedicated
    per-run log: treats a target artifact's mtime landing inside the run window as evidence
    the harness-reported timeout masked a run that actually finished (same harness behavior
    documented for nightly-memory-consolidation: the detached process outlives the harness's
    own timeoutSeconds and keeps running to real completion)."""
    st = job.get('state', {})
    last_status = str(st.get('lastStatus') or st.get('lastRunStatus') or '').lower()
    last_duration_ms = st.get('lastDurationMs')
    timeout_seconds = (
        job.get('timeoutSeconds')
        or job.get('payload', {}).get('timeoutSeconds')
    )
    looks_like_timeout = 'timeout' in last_status
    if not looks_like_timeout and timeout_seconds and last_duration_ms:
        looks_like_timeout = int(last_duration_ms) >= int(timeout_seconds) * 1000
    if not looks_like_timeout:
        return None

    last_run_ms = st.get('lastRunAtMs') or st.get('runningAtMs') or int(time.time() * 1000)
    newest_ms = newest_mtime_ms(target_paths)
    if newest_ms is None:
        return f'{label} local check: no target artifact found; timeout root cause still unknown'

    # Grace window past timeoutSeconds accounts for the detached process finishing after the
    # harness gives up but before a human or the next scheduled run notices.
    window_end_ms = last_run_ms + ((int(timeout_seconds) if timeout_seconds else 900) * 1000) + (30 * 60 * 1000)
    newest_label = datetime.fromtimestamp(newest_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    if last_run_ms <= newest_ms <= window_end_ms:
        return (
            f'{label} local check: target artifact modified at {newest_label}, inside the run window; '
            'harness timeout likely masked a completed run'
        )
    return f'{label} local check: target artifact mtime ({newest_label}) falls outside the run window; timeout may reflect a real incomplete run'


def check_nightly_memory_qmd_health(job, now):
    """Return a virtual failure when the latest memory-cycle log contains QMD index errors."""
    if job.get('name') != NIGHTLY_MEMORY_JOB_NAME:
        return None

    st = job.get('state', {})
    last_run_ms = st.get('lastRunAtMs') or int(time.time() * 1000)
    run_date = ms_to_utc_date(last_run_ms)
    log_path = WORKSPACE_PATH / 'memory' / f'memory-cycle-{run_date}.log'
    if not log_path.exists():
        return None

    try:
        log_text = log_path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None

    complete_matches = list(NIGHTLY_MEMORY_COMPLETE_RE.finditer(log_text))
    if not complete_matches:
        return None

    completion_ms = parse_utc_log_timestamp(complete_matches[-1].group('ts'))
    if completion_ms < int(last_run_ms) - (5 * 60 * 1000):
        return None

    matches = []
    for pattern in QMD_ANOMALY_PATTERNS:
        matches.extend(pattern.findall(log_text))
    if not matches:
        return None

    unique_matches = []
    seen = set()
    for match in matches:
        if match in seen:
            continue
        seen.add(match)
        unique_matches.append(match)

    detail = '; '.join(unique_matches[:4])
    if len(unique_matches) > 4:
        detail += f'; ... {len(unique_matches) - 4} more'

    return {
        'name': NIGHTLY_MEMORY_QMD_NAME,
        'id': NIGHTLY_MEMORY_QMD_JOB_ID,
        'signature': f'{NIGHTLY_MEMORY_QMD_JOB_ID}:{run_date}:{len(matches)}:{completion_ms}',
        'lastStatus': 'qmd-index-anomaly',
        'lastDeliveryStatus': 'n/a',
        'consecutiveErrors': 1,
        'lastRunAtMs': last_run_ms,
        'nextRunAtMs': job.get('state', {}).get('nextRunAtMs'),
        'details': (
            f'{log_path} completed but contains {len(matches)} QMD index anomaly marker(s); '
            f'{detail}. This is likely caused by the 900s timeout allowing an overlapping retry '
            'while the first memory cycle is still updating QMD.'
        ),
    }


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
    details = compact_details(output)
    run_history = describe_recent_self_improvement_failures()
    if run_history:
        details = f'{details}; {run_history}'
    return {
        'name': AUTONOMY_CADENCE_NAME,
        'id': AUTONOMY_CADENCE_JOB_ID,
        'signature': f'{AUTONOMY_CADENCE_JOB_ID}:{result.returncode}:{output.strip()}',
        'lastStatus': 'gap' if result.returncode == 2 else f'guard-error-{result.returncode}',
        'lastDeliveryStatus': 'n/a',
        'consecutiveErrors': 1,
        'lastRunAtMs': now,
        'nextRunAtMs': None,
        'details': details,
    }


def main():
    now = int(time.time() * 1000)

    jobs = load_cron_jobs()

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
        details = describe_nightly_memory_timeout(job)
        if details is None and job.get('name') == NEXT_AUDIT_PRIORITIES_JOB_NAME:
            details = describe_mtime_evidence_timeout(
                job,
                [WORKSPACE_PATH / 'notes' / 'autonomy-gaps.md'],
                NEXT_AUDIT_PRIORITIES_JOB_NAME,
            )
        if details:
            info['details'] = details
        current[job_id] = info

        prev = active_failures.get(job_id)
        if prev is None or prev.get('signature') != sig:
            new_alerts.append(info)

    for job in jobs:
        qmd_failure = check_nightly_memory_qmd_health(job, now)
        if qmd_failure is None:
            continue
        current[NIGHTLY_MEMORY_QMD_JOB_ID] = qmd_failure
        prev = active_failures.get(NIGHTLY_MEMORY_QMD_JOB_ID)
        if prev is None or prev.get('signature') != qmd_failure.get('signature'):
            new_alerts.append(qmd_failure)
        break

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
