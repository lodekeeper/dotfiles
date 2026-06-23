# Autonomy Gaps — Daily Audit

> "What would I need to do this autonomously?"
> Updated: 2026-06-23 (68th pass)

---

## Daily Audit Snapshot — 2026-06-23 (self-improvement-audit-daily, 03:18 UTC)

### PR review
- **Status:** follow-up guard preflight verified through the consolidated domain runner and now through the audit preflight wrapper; no new PR-review blocker discovered this cycle.

### CI fix
- **Status:** fix-quality gate preflight verified through the consolidated domain runner and now through the audit preflight wrapper. The runner defaults to a dummy `OPENAI_API_KEY` only when the cron shell lacks one, so it can validate local package/import readiness without leaking or requiring a secret; strict mode remains available for real-key enforcement.

### Spec implementation
- **Status:** pre-PR spec-compliance preflight verified through the consolidated domain runner and now through the audit preflight wrapper; no new spec-implementation blocker discovered this cycle.

### Devnet debugging
- **Status:** devnet-triage JSON preflight verified through the consolidated domain runner and now through the audit preflight wrapper; optional telemetry warnings remain explicit when `GRAFANA_TOKEN` is absent, and no new devnet-debugging blocker discovered this cycle.

### Audit workflow
- **Status:** audit-preflight verification gap found and fixed this cycle: `run-autonomy-audit-preflight.sh` scaffolded/carried forward daily statuses but did not run `check-autonomy-domain-preflights.py`, so a scheduled audit could document healthy PR/CI/spec/devnet autonomy without first proving those domain checks still passed. Proposed fix was to make domain preflights part of the default audit preflight while preserving explicit strict-mode and skip flags. Gap fixed this cycle: added default domain preflight execution plus `--skip-domain-preflights`, `--strict-ci-api-key`, and `--require-devnet-grafana` options to `scripts/notes/run-autonomy-audit-preflight.sh`.

---
## Daily Audit Snapshot — 2026-06-22 (self-improvement-audit-daily, 03:18 UTC)

### PR review
- **Status:** follow-up guard preflight verified through the new consolidated domain runner; no new PR-review blocker discovered this cycle.

### CI fix
- **Status:** fix-quality gate preflight verified through the new consolidated domain runner. The runner defaults to a dummy `OPENAI_API_KEY` only when the cron shell lacks one, so it can validate local package/import readiness without leaking or requiring a secret; strict mode correctly fails when the real key is absent.

### Spec implementation
- **Status:** pre-PR spec-compliance preflight verified through the new consolidated domain runner; no new spec-implementation blocker discovered this cycle.

### Devnet debugging
- **Status:** devnet strict-telemetry gap found and fixed this cycle: the consolidated domain runner verified the devnet-triage JSON preflight only in optional telemetry mode, so autonomous live devnet-debugging wrappers could accidentally prove local shell readiness while missing `GRAFANA_TOKEN`. Proposed fix was to expose a strict devnet telemetry mode and keep optional mode explicit. Gap fixed this cycle: added `--require-devnet-grafana` to `scripts/notes/check-autonomy-domain-preflights.py`, added an optional-mode warning when `GRAFANA_TOKEN` is absent, verified the normal JSON preflight still passes, and verified strict mode now fails early with `status=missing_grafana` until the cron shell has Grafana credentials.

---
## Daily Audit Snapshot — 2026-06-21 (self-improvement-audit-daily, 03:18 UTC)

### PR review
- **Status:** follow-up guard preflight verified through the new consolidated domain runner; no new PR-review blocker discovered this cycle.

### CI fix
- **Status:** fix-quality gate preflight verified through the new consolidated domain runner. The runner defaults to a dummy `OPENAI_API_KEY` only when the cron shell lacks one, so it can validate local package/import readiness without leaking or requiring a secret; strict mode correctly fails when the real key is absent.

### Spec implementation
- **Status:** pre-PR spec-compliance preflight verified through the new consolidated domain runner; no new spec-implementation blocker discovered this cycle.

### Devnet debugging
- **Status:** devnet-triage JSON preflight verified through the new consolidated domain runner; telemetry remains optional in this shell because `GRAFANA_TOKEN` is absent, and no new devnet-debugging blocker was discovered this cycle.

---
## Daily Audit Snapshot — 2026-06-20 (self-improvement-audit-daily, 03:17 UTC)

### PR review
- **Status:** follow-up guard preflight verified through the new consolidated domain runner; no new PR-review blocker discovered this cycle.

### CI fix
- **Status:** fix-quality gate preflight verified through the new consolidated domain runner. The runner defaults to a dummy `OPENAI_API_KEY` only when the cron shell lacks one, so it can validate local package/import readiness without leaking or requiring a secret; strict mode correctly fails when the real key is absent.

### Spec implementation
- **Status:** pre-PR spec-compliance preflight verified through the new consolidated domain runner; no new spec-implementation blocker discovered this cycle.

### Devnet debugging
- **Status:** devnet-triage JSON preflight verified through the new consolidated domain runner; telemetry remains optional in this shell because `GRAFANA_TOKEN` is absent, and no new devnet-debugging blocker was discovered this cycle.

### Audit workflow
- **Status:** cross-domain audit verification gap found and fixed this cycle: the four required autonomy domains had separate preflight guards, but the daily audit had no single side-effect-free command to prove all of them were still runnable before carrying forward healthy status lines. Gap fixed this cycle: added `scripts/notes/check-autonomy-domain-preflights.py`, which runs PR-review, CI-fix, spec-implementation, and devnet-debugging preflights, normalizes JSON/exit codes, supports a strict CI-key mode, and returns a single cron-friendly pass/fail result.

---
## Daily Audit Snapshot — 2026-06-19 (self-improvement-audit-daily, 03:17 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; full-surface discussion scan + metadata/stale-finding guards remain healthy.

### CI fix
- **Status:** CI auto-fix quality-gate gap found and fixed this cycle: `scripts/ci/check_fix_quality.py` existed to catch masking flaky-test fixes, but autonomous runs had no cheap preflight for its API/package prerequisites and `scripts/ci/CRON_PROMPT.md` did not require the gate before committing/opening a fix PR. Proposed fix was to make the gate preflightable and wire it into the fix workflow. Gap fixed this cycle: added `--check-only` JSON prerequisite output to `check_fix_quality.py`, documented the mandatory per-fix preflight plus staged-diff gate in `CRON_PROMPT.md`, and verified Python syntax, success with a dummy API key, and the real missing-key failure path.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** devnet-triage telemetry preflight + JSON readiness path remain healthy; no new blocker discovered this cycle.

---

## Daily Audit Snapshot — 2026-06-18 (self-improvement-audit-daily, 03:16 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; existing review guardrails remain healthy.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** devnet-triage preflight machine-readability gap found and fixed this cycle: yesterday's `scripts/debug/devnet-triage.sh --check-only --require-grafana` made telemetry availability explicit, but autonomous wrappers still had to parse prose to decide whether Grafana/Loki/Prometheus were ready or intentionally unavailable. Gap fixed this cycle: added `--json` for check-only mode with structured node/window/query/tool/Grafana readiness fields, rejected `--json` outside preflight mode, documented the automation form in `skills/devnet-debug/SKILL.md`, and verified syntax, prose preflight, JSON success, JSON required-Grafana failure, and invalid non-preflight JSON usage.

---

## Daily Audit Snapshot — 2026-06-17 (self-improvement-audit-daily, 03:16 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; existing review guardrails remain healthy.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** devnet-triage telemetry preflight gap found and fixed this cycle: `scripts/debug/devnet-triage.sh` could intentionally degrade when `GRAFANA_TOKEN`, `curl`, or `jq` were missing, but there was no cheap dry-run for autonomous devnet-debugging wrappers to prove whether Loki/Prometheus telemetry would be present before starting a longer investigation. Gap fixed this cycle: added `--check-only` plus `--require-grafana`, made the live query helpers fail closed when `curl` is absent, documented the preflight in `skills/devnet-debug/SKILL.md`, and verified syntax, optional dry-run success, required-Grafana failure, and existing GitHub guard coverage.

---
## Daily Audit Snapshot — 2026-06-16 (self-improvement-audit-daily, 03:16 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; existing review guardrails remain healthy.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** spec-vector readiness preflight machine-readability gap found and fixed this cycle: `scripts/spec/check-test-vector-readiness.sh` only emitted prose and could pick generated cache/report files as its sample, so autonomous wrappers had to parse human output and could receive a misleading readiness signal. Gap fixed this cycle: added `--json` with structured readiness/staleness fields, filtered generated cache/report files from sample discovery, made the script executable, and verified human/JSON success plus stale failure paths.

### Devnet debugging
- **Status:** remote-devnet routing readiness preflight remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-06-15 (self-improvement-audit-daily, 03:27 UTC)

### PR review
- **Status:** PR follow-up wrapper preflight gap found and fixed this cycle: `scripts/review/run-followup-guards.sh` had guarded live execution, but autonomous wrappers could not validate the full helper chain without supplying a real PR and risking GitHub fetch/report side effects. Gap fixed this cycle: added `--check-only --json` to validate `python3`, `gh`, shell syntax, discussion fetcher preflight, finding tracker, metadata checker, GitHub access guard, and report-directory readiness without calling GitHub or writing artifacts; wired it into `scripts/github/check-github-guard-coverage.sh`; documented the machine-readable preflight in `skills/lodestar-review/SKILL.md`.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** remote-devnet routing readiness preflight remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-06-14 (self-improvement-audit-daily, 03:27 UTC)

### PR review
- **Status:** full-surface PR discussion scanner + metadata/stale finding guards remain healthy; no new blocker discovered this cycle.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** spec-compliance preflight machine-readability gap found and fixed this cycle: yesterday's `scripts/spec/prepr-compliance-gate.sh --check-only` made local prerequisite drift detectable before PR assembly, but autonomous wrappers still had to parse prose to tell a clean pass from missing tooling. Proposed fix was to add a JSON preflight output path and document it where spec implementations run the gate. Gap fixed this cycle: added `--check-only --json` with structured helper/pass fields, kept `--json` rejected outside preflight mode, and documented the automation form in `skills/dev-workflow/SKILL.md`.

### Devnet debugging
- **Status:** remote-devnet routing readiness preflight remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-06-13 (self-improvement-audit-daily, 03:27 UTC)

### PR review
- **Status:** full-surface PR discussion scanner + metadata/stale finding guards remain healthy; no new blocker discovered this cycle.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** spec-compliance gate preflight gap found and fixed this cycle: `scripts/spec/prepr-compliance-gate.sh` could only validate prerequisites after PR/tracker inputs were already assembled, so missing compliance helper/tooling state would surface late in a spec implementation. Gap fixed this cycle: added `--check-only` to validate `python3`, `check-compliance.py`, and `check-compliance-artifacts.sh` without PR inputs, and documented the preflight in `skills/dev-workflow/SKILL.md` before the Phase 4 spec-compliance command.

### Devnet debugging
- **Status:** remote-devnet routing readiness preflight remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-06-12 (self-improvement-audit-daily, 03:25 UTC)

### PR review
- **Status:** full-surface PR discussion scanner + metadata/stale finding guards remain healthy; no new blocker discovered this cycle.

### CI fix
- **Status:** CI log acquisition had no local-only preflight for `scripts/ci/fetch-run-logs.sh`: guard coverage could verify static strings, but could not execute the helper's prerequisite path without a real Actions run id. Gap fixed this cycle: added `--check-only` to validate `gh` + the cached GitHub access guard without calling GitHub, and wired that preflight into `scripts/github/check-github-guard-coverage.sh`.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** remote-devnet routing readiness preflight remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-06-11 (self-improvement-audit-daily, 03:25 UTC)

### PR review
- **Status:** full-surface PR discussion scanner + metadata/stale finding guards remain healthy; no new blocker discovered this cycle.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** remote-devnet routing readiness preflight remains healthy; no new blocker discovered this cycle.

### Audit workflow
- **Status:** delta-notification noise blocker found and fixed this cycle: when the previous snapshot included a one-off non-required section such as `Audit workflow`, a green carry-forward day with all four required status lines unchanged still looked meaningful because `check-autonomy-audit-delta.py` compared whole snapshot bodies and treated removal of the previous advisory section as an update. Gap fixed this cycle: the delta detector now treats required status changes plus added/changed current non-required sections as meaningful, while reporting removed non-required headings without forcing output; verified today’s green snapshot rendered `NO_REPLY` when the only difference was removal of yesterday’s advisory section.

---
## Daily Audit Snapshot — 2026-06-10 (self-improvement-audit-daily, 03:25 UTC)

### PR review
- **Status:** full-surface PR discussion scanner + metadata/stale finding guards remain healthy; no new blocker discovered this cycle.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** remote-devnet routing readiness preflight remains healthy; no new blocker discovered this cycle.

### Audit workflow
- **Status:** cadence drift blocker found this cycle: the previous snapshot was 2026-06-08, so 2026-06-09 is missing. The watchdog virtual cadence check detects the gap, but `close-autonomy-audit.sh` could still return `NO_REPLY` in advisory mode when the four required status lines carried forward unchanged. Gap fixed this cycle: close-out now treats advisory cadence gaps as meaningful output and returns a concise cadence-gap summary instead of `NO_REPLY`, so a missed daily snapshot cannot be silently masked by unchanged required sections.

---
## Daily Audit Snapshot — 2026-06-08 (self-improvement-audit-daily, 03:25 UTC)

### PR review
- **Status:** full-surface PR discussion scanner + metadata/stale finding guards remain healthy; no new blocker discovered this cycle.

### CI fix
- **Status:** CI log acquisition still had one direct-GitHub helper path outside the cached suspension guard coverage: `scripts/ci/fetch-run-logs.sh` calls `gh run view --log-failed` / full-log fallback directly, so an autonomous CI fixer could fail mid-triage during a known GitHub suspension instead of cleanly short-circuiting. The helper also lacked its executable bit despite being documented as a direct command. Gap fixed this cycle: added `bail_if_github_suspended()` to `fetch-run-logs.sh`, made it emit `GITHUB_SUSPENDED_SKIP` and exit `4` before any `gh run view` call when the cached guard reports suspension, set the helper executable, and expanded `scripts/github/check-github-guard-coverage.sh` to keep this CI helper covered.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** remote-devnet routing readiness preflight remains healthy; no new blocker discovered this cycle.

---

## Daily Audit Snapshot — 2026-06-07 (self-improvement-audit-daily, 03:25 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; existing review guardrails remain healthy.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** remote-devnet routing preflight gap found and fixed this cycle: the `investigate` skill asked agents to run `panda datasources --json`, but the command can exit successfully while returning `{"datasources": null}` when panda auth/server datasource access is not ready, which makes a missing-auth/tooling state look like "network not found." Gap fixed this cycle: added `scripts/debug/check-devnet-routing-readiness.py`, documented it in the `investigate` skill, and verified it returns `PANDA_DATASOURCES_UNAVAILABLE` exit `2` for the current `glamsterdam-devnet-5` auth-blocked state before any long investigation starts.

---
## Daily Audit Snapshot — 2026-06-06 (self-improvement-audit-daily, 03:25 UTC)

### PR review
- **Status:** PR discussion scanner machine-readable preflight gap found and fixed this cycle: yesterday's new `scripts/review/fetch-pr-discussion.py` had a JSON output path that depended on `datetime` / `timezone` without importing them, and `--check-only` never exercised JSON output, so autonomous wrappers could still discover the bug only during a live PR sweep. Gap fixed this cycle: imported the missing symbols, made `--check-only --json` emit a real JSON preflight payload, and wired `scripts/github/check-github-guard-coverage.sh` to execute that preflight so the full-discussion report's machine-readable path stays covered without calling GitHub.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-06-05 (self-improvement-audit-daily, 03:25 UTC)

### PR review
- **Status:** PR follow-up coverage gap found and fixed this cycle: `scripts/review/track-findings.py sync-gh` and the follow-up wrapper centered on inline review comments, so a sweep could falsely conclude that lodekeeper had not replied or that only bot chatter existed while issue-level PR comments or review bodies carried the real state. Gap fixed this cycle: added `scripts/review/fetch-pr-discussion.py` to fetch issue comments, inline review comments, and review bodies in one report; wired it into `scripts/review/run-followup-guards.sh` as the default first step; added guard-coverage checks; and documented the full-surface scan requirement in `skills/lodestar-review/SKILL.md`.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-06-04 (self-improvement-audit-daily, 03:24 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; existing review guardrails remain healthy.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** incident-bundle telemetry-preflight gap found and fixed this cycle: `scripts/debug/build-incident-bundle.sh` could intentionally degrade into partial bundles when Grafana token/tooling was missing, but there was no fast dry-run guard to make that choice explicit before a debugging run. Gap fixed this cycle: added `--check-only` and `--require-grafana` to validate helper scripts, output path, and telemetry prerequisites before fetching logs or writing bundles, and documented the preflight in `skills/local-mainnet-debug/SKILL.md`.

---
## Daily Audit Snapshot — 2026-06-03 (self-improvement-audit-daily, 03:24 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; existing review guardrails remain healthy.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy. Cron-watchdog testability gap found and fixed this cycle: the virtual autonomy-audit cadence check was hardwired to the live workspace/date/state, so regression-testing stale-audit alerts required mutating real notes/state or waiting for UTC date drift. Gap fixed this cycle: `scripts/cron/check_cron_health.py` now honors `CRON_JOBS_PATH`, `CRON_HEALTH_STATE_PATH`, `WORKSPACE_PATH`, `AUTONOMY_CADENCE_SCRIPT`, `AUTONOMY_CADENCE_FILE`, `AUTONOMY_CADENCE_REFERENCE_DATE`, and `AUTONOMY_CADENCE_EXPECTED_EVERY_DAYS` env overrides, so the virtual failure/recovery path is reproducible against temp fixtures without polluting production watchdog state.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-06-02 (self-improvement-audit-daily, 03:24 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; existing review guardrails remain healthy.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy. Cross-automation watchdog gap found and fixed this cycle: missed daily audit snapshots for 2026-05-30 and 2026-05-31 only surfaced inside the next audit preflight, not through the 30-minute cron watchdog. Gap fixed this cycle: `scripts/cron/check_cron_health.py` now treats `scripts/notes/check-autonomy-audit-cadence.py --latest-only --require-current --fail-on-gap` as a virtual failing cron with the existing state/dedup alert path, so future stale autonomy-audit cadence failures alert independently of the audit cron itself.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-06-01 (self-improvement-audit-daily, 03:24 UTC)

### PR review
- **Status:** PR follow-up guardrails still had a wrapper-level suspension gap: `scripts/review/run-followup-guards.sh` invoked `sync-gh` and metadata drift checks without its own pre-flight, so a suspended GitHub account could fail mid-wrapper or leave partial artifacts even though the child scripts now had guards. Gap fixed this cycle: added a wrapper-level `bail_if_github_suspended()` that honors `GITHUB_ACCESS_STATE_FILE` / `GITHUB_ACCESS_MAX_AGE_MINUTES`, exits `4` with `GITHUB_SUSPENDED_SKIP` before artifact creation, and expanded `scripts/github/check-github-guard-coverage.sh` so this wrapper remains covered.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-29 (self-improvement-audit-daily, 03:24 UTC)

### PR review
- **Status:** PR metadata-drift checking still had one standalone direct-GitHub path without the shared suspension pre-flight: `scripts/github/check-pr-metadata-drift.py` called `gh pr view` / `gh pr diff` directly, so direct metadata-drift checks could crash during the active account suspension instead of producing an explicit skip signal. Gap fixed this cycle: added `bail_if_github_suspended()` to the checker, made suspended-cache runs exit `4` with `GITHUB_SUSPENDED_SKIP` before any PR metadata fetch, and expanded `scripts/github/check-github-guard-coverage.sh` so this PR-review guard surface stays covered by future guard-drift checks.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-28 (self-improvement-audit-daily, 03:24 UTC)

### PR review
- **Status:** PR review follow-up automation still had one direct GitHub path without the shared suspension pre-flight: `scripts/review/track-findings.py import-gh` / `sync-gh` could start local review-state work and then crash on `gh api` during the active account suspension. Proposed fix was to push the existing cached GitHub guard into the finding tracker itself. Gap fixed this cycle: added `bail_if_github_suspended()` to `track-findings.py`, made suspended-cache runs exit `2` with `GITHUB_SUSPENDED_SKIP` before any review-comment fetch, and expanded `scripts/github/check-github-guard-coverage.sh` so this review workflow stays covered by future guard-drift checks.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-27 (self-improvement-audit-daily, 03:24 UTC)

### PR review
- **Status:** PR-review guardrails remain healthy; no new blocker discovered this cycle.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** catch-up/OOM repro setup had no deterministic guard against launching from a checkpoint that is too close to head, which wastes runs and masks the intended deep-sync backlog. Gap fixed this cycle: added `scripts/debug/check-catchup-depth.sh` and wired it into `skills/local-mainnet-debug/SKILL.md`; it validates head/checkpoint slot distance, supports Beacon API-assisted slot fetches, and exits `2` before launch when the checkpoint is too shallow.

---
## Daily Audit Snapshot — 2026-05-26 (self-improvement-audit-daily, 03:23 UTC)

### PR review
- **Status:** PR-review guardrails remain healthy; no new blocker discovered this cycle.

### CI fix
- **Status:** GitHub suspension handling was now implemented in scripts, but there was no coverage guard to prove the guard stayed wired into every GH-dependent cron path after future prompt/script edits. Gap fixed this cycle: added `scripts/github/check-github-guard-coverage.sh` and wired the CI auto-fix prompt to run it before any GitHub access. The verifier checks the shared access guard plus the current notification, PR-CI, and flaky-CI guard callsites and fails before `gh` calls if coverage drifts.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-25 (self-improvement-audit-daily, 03:23 UTC)

### PR review
- **Status:** PR-review guardrails remain healthy; no new blocker discovered this cycle.

### CI fix
- **Status:** prompt-level GitHub-access guards were not enough for CI autonomy: `scripts/ci/auto_fix_flaky.py` still went straight into `gh` calls when invoked directly, so future prompt drift or manual runs could crash during the active suspension. Gap fixed this cycle: added a script-level `bail_if_github_suspended()` guard to the detector. It calls the shared cached guard before scanning, prints the cron's expected `GITHUB_SUSPENDED_SKIP`, exits 0 on suspension, and exposes `GITHUB_ACCESS_STATE_FILE` / `GITHUB_ACCESS_MAX_AGE_MINUTES` overrides for deterministic tests.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-24 (self-improvement-audit-daily, 03:23 UTC)

### PR review
- **Status:** PR-review guardrails remain healthy; no new blocker discovered this cycle.

### CI fix
- **Status:** GH-dependent cron callers had no script-level guard against the active GitHub suspension, so each invocation crashed mid-`gh api` rather than short-circuiting cleanly. Gap fixed this cycle: pushed the access guard down into the scripts themselves. **Fix applied this cycle:** added `bail_if_github_suspended()` to `scripts/github/github_notifications_sweep.py` (288 runs/day at every-5-min cadence) and `scripts/github/monitor_open_pr_ci.py` (every 30 min). Both call `scripts/github/check-github-access.sh` at the top of `main()` and print the cron's expected silent signal (`HEARTBEAT_OK` / `NO_REPLY`) before any `gh api` call, so the bail is clean regardless of which cron/human invokes the script.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---

## Daily Audit Snapshot — 2026-05-23 (self-improvement-audit-daily, 03:24 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; existing review guardrails remain healthy.

### CI fix
- **Status:** no new CI-fix blocker discovered this cycle. Gap found and fixed this cycle: GH-dependent crons (github-notifications, ci-autofix-unstable, monitor-open-pr-ci) had no shared pre-flight guard to short-circuit when the account is suspended. Each fired independently, burned full prompt context, and only hit 403 mid-execution. **Fix applied this cycle:** added `scripts/github/check-github-access.sh` — a cached guard (10-min TTL) that cron prompts can call at startup; exits 0 when accessible, exits 2 when suspended, caches the result to avoid repeated API hammering.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-22 (self-improvement-audit-daily, 03:23 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; existing review guardrails remain healthy.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** tool-surface routing gap found and fixed this cycle: Discord / channel follow-up work that needed OpenClaw provider tools could still get bounced into plain Claude Code / CLI sessions with no provider access. **Fix applied this cycle:** codified a provider-surface routing guard in `AGENTS.md` and `HEARTBEAT.md` — keep Discord/Telegram/browser/message follow-ups in the OpenClaw main or channel session, and use `sessions_send` back to `agent:main:discord:channel:<ID>` / topic sessions instead of delegating those steps to plain CLI continuations.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-21 (self-improvement-audit-daily, 03:23 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; existing review guardrails remain healthy.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-19 (self-improvement-audit-daily, 03:23 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; existing review guardrails remain healthy.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-18 (self-improvement-audit-daily, 03:23 UTC)

### PR review
- **Status:** close-out targeting gap found and fixed this cycle: when `memory/<date>.md` had multiple unresolved `- Outcome: _fill in after close-out_.` lines (for example after a retried preflight), `close-autonomy-audit.sh --update-memory-outcome` replaced the **first** placeholder, which could update an older stub and leave today's latest audit outcome unresolved. **Fix applied this cycle:** switched replacement to target the **most recent** placeholder via `rsplit(..., 1)`, and updated the warning text accordingly.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-17 (self-improvement-audit-daily, 03:23 UTC)

### PR review
- **Status:** close-out ordering gap found and fixed this cycle: `close-autonomy-audit.sh` ran `finalize-autonomy-audit.py` **before** memory outcome guards, so a missing/placeholder outcome could fail close-out after mutating `notes/autonomy-gaps.md` (partial side effects and noisy rerun paths). **Fix applied this cycle:** moved `--update-memory-outcome` + daily-memory outcome guard to run **before** finalize/cadence, making close-out fail fast without touching audit snapshots when memory stubs are incomplete.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-16 (self-improvement-audit-daily, 03:23 UTC)

### PR review
- **Status:** audit-closeout safety gap found and fixed this cycle: `close-autonomy-audit.sh --update-memory-outcome` replaced **all** `_fill in after close-out_` placeholders in `memory/<date>.md`, which could overwrite multiple unresolved entries with one shared outcome and hide incomplete notes. **Fix applied this cycle:** replacement is now single-target (`replace(..., 1)`), and close-out emits a warning when multiple placeholders are detected so follow-up cleanup stays explicit.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-15 (self-improvement-audit-daily, 03:23 UTC)

### PR review
- **Status:** audit-closeout safety gap found and fixed this cycle: `close-autonomy-audit.sh --update-memory-outcome` previously used raw `sed` replacement, so outcome text containing replacement metacharacters (notably `&`) could be mangled during placeholder updates. **Fix applied this cycle:** replaced the `sed` substitution with a Python atomic rewrite (`read_text` → `replace` → temp-file + `mv`) so arbitrary outcome text is preserved exactly.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-13 (self-improvement-audit-daily, 12:18 UTC)

### PR review
- **Status:** audit-completion workflow gap found and fixed this cycle: `close-autonomy-audit.sh` had no inline way to fill the memory-outcome placeholder — prior flow required a separate manual file edit to replace `_fill in after close-out_.` before close-out could succeed, making incomplete-audit recovery error-prone. **Fix applied this cycle:** added `--update-memory-outcome <text>` flag to `close-autonomy-audit.sh`; atomically replaces the placeholder via tmp-file + mv so close-out becomes a single atomic command.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-12 (self-improvement-audit-daily, 09:31 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; existing review guardrails remain healthy.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-11 (self-improvement-audit-daily, 03:24 UTC)

### PR review
- **Status:** audit-side-effect gap found and fixed this cycle: preflight wrote `memory/<date>.md` scaffolding before duplicate/consistency/cadence guards, so failed preflight runs could leave orphaned placeholder notes without a corresponding snapshot. **Fix applied this cycle:** updated `scripts/notes/run-autonomy-audit-preflight.sh` to run note/stub writes only after all guard checks pass (new explicit step `[3/5]`), with snapshot insertion moved to `[4/5]`.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-10 (self-improvement-audit-daily, 03:24 UTC)

### PR review
- **Status:** audit-closeout continuity gap found and fixed this cycle: close-out could complete while today's seeded memory stub still had `Outcome: _fill in after close-out_.`, which made daily audit journaling easy to leave incomplete. **Fix applied this cycle:** added a default memory-outcome guard in `scripts/notes/close-autonomy-audit.sh` that requires `memory/<date>.md` to exist and rejects unresolved outcome placeholders unless explicitly overridden with `--skip-memory-outcome-check`.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-09 (self-improvement-audit-daily, 03:25 UTC)

### PR review
- **Status:** audit-trace continuity gap found and fixed this cycle: preflight could create `memory/<date>.md` but still leave the day without an explicit autonomy-audit note stub, making close-out journaling easy to forget. **Fix applied this cycle:** updated `scripts/notes/run-autonomy-audit-preflight.sh` to append a one-time `self-improvement-audit-daily (preflight)` entry stub in `memory/<date>.md` by default, with explicit opt-out via `--no-seed-audit-memory-entry`.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-08 (self-improvement-audit-daily, 03:24 UTC)

### PR review
- **Status:** audit-continuity gap found and fixed this cycle: daily autonomy preflight assumed `memory/<date>.md` already existed, so a fresh day could start without the required daily-note file and force manual repair later. **Fix applied this cycle:** updated `scripts/notes/run-autonomy-audit-preflight.sh` to ensure `memory/<date>.md` exists by default before snapshot insertion, with explicit opt-out via `--no-ensure-daily-memory-note`.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-07 (self-improvement-audit-daily, 03:23 UTC)

### PR review
- **Status:** audit-workflow ergonomics gap found and fixed this cycle: preflight inserted blank placeholder status lines by default even though stable carry-forward logic already existed, which adds avoidable manual churn and placeholder-leak risk. **Fix applied this cycle:** changed `scripts/notes/run-autonomy-audit-preflight.sh` to enable carry-forward status prefill by default, with explicit `--no-carry-forward-status` opt-out for intentional blank scaffolds.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-06 (self-improvement-audit-daily, 03:22 UTC)

### PR review
- **Status:** audit-workflow diagnostics gap found and fixed this cycle: cadence warnings reported only missing-day counts, which made backfill root-cause tracing slower during missed-cron investigations. **Fix applied this cycle:** extended `scripts/notes/check-autonomy-audit-cadence.py` to print explicit missing in-between dates (capped list + overflow count) for each detected cadence gap.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-05 (self-improvement-audit-daily, 03:19 UTC)

### PR review
- **Status:** audit-closeout integrity gap found and fixed this cycle: `close-autonomy-audit.sh` could emit `NO_REPLY` when finalize reported no delta even if `## Next Audit Priorities` still had live items. **Fix applied this cycle:** added a default guard in `scripts/notes/close-autonomy-audit.sh` that runs `check-next-audit-priorities.py --fail-if-live` before emitting `NO_REPLY`, with explicit override flag `--allow-live-priorities-no-reply` for intentional bypasses.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-05-03 (self-improvement-audit-daily, 03:19 UTC)

### PR review
- **Status:** audit-integrity gap found and fixed this cycle: consistency checks validated snapshot order/dedup metadata but did not verify required section structure across historical snapshots. **Fix applied this cycle:** extended `scripts/notes/check-autonomy-gaps-consistency.py` with snapshot-structure validation (required domains + structured status/blocker/fix markers), including backward-compatible handling for legacy snapshots that use `Blocker/Fix applied` bullets instead of normalized `Status` lines.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-30 (self-improvement-audit-daily, 00:57 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; existing review guardrails remain healthy.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-29 (self-improvement-audit-daily, 00:46 UTC)

### PR review
- **Status:** reviewer artifacts still depended on manual metadata stamping in reviewer prompts, so marker omissions could break `check-review-artifacts.sh` gating and force avoidable reruns. **Fix applied this cycle:** added `scripts/review/write-review-artifact.sh` to stamp `Reviewer:` + `Reviewed commit:` markers automatically from `--agent` and repo HEAD, and updated `skills/lodestar-review/SKILL.md` durable-output instructions to prefer the helper.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-28 (self-improvement-audit-daily, 00:46 UTC)

### PR review
- **Status:** reviewer artifact verification still accepted agent-swapped files when commit markers matched, so cross-agent copy mistakes could pass synthesis checks. **Fix applied this cycle:** extended `scripts/review/check-review-artifacts.sh` with `--require-agent-marker` (enforces `Reviewer: <agent-id>` per artifact) and updated `skills/lodestar-review/SKILL.md` durable-output + Step 4.1 verifier instructions to stamp and verify reviewer ownership markers.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-27 (self-improvement-audit-daily, 00:46 UTC)

### PR review
- **Status:** reviewer commit-affinity checks still relied on manually interpolating `Reviewed commit: <HEAD_SHA>` text in verifier commands, which is easy to mistype/skip during fast follow-up loops. **Fix applied this cycle:** extended `scripts/review/check-review-artifacts.sh` with `--require-reviewed-head` (auto-resolves `Reviewed commit: <HEAD_SHA>` from git) plus `--head-repo <path>`, and updated `skills/lodestar-review/SKILL.md` Step 4.1 to use the new deterministic guard.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-26 (self-improvement-audit-daily, 00:45 UTC)

### PR review
- **Status:** reviewer artifact freshness checks existed, but they still accepted files from the wrong head commit when those files were recently regenerated. **Fix applied this cycle:** extended `scripts/review/check-review-artifacts.sh` with repeatable `--require-text` markers and updated `skills/lodestar-review/SKILL.md` to stamp/verify `Reviewed commit: <HEAD_SHA>` in each reviewer artifact.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-25 (self-improvement-audit-daily, 00:44 UTC)

### PR review
- **Status:** reviewer artifact presence/size checks existed, but stale files from prior review rounds could still pass and be mistaken as fresh output. **Fix applied this cycle:** extended `scripts/review/check-review-artifacts.sh` with `--max-age-minutes` stale-artifact enforcement and updated `skills/lodestar-review/SKILL.md` Step 4.1 to run the verifier with age bounds (`--max-age-minutes 180`).

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-24 (self-improvement-audit-daily, 00:44 UTC)

### PR review
- **Status:** transport-failure fallback required reviewer artifacts, but there was no one-command guard to verify all expected reviewer files exist before synthesis. **Fix applied this cycle:** added `scripts/review/check-review-artifacts.sh` (checks `pr-<PR>-<agent-id>.md` presence/size and supports `--allow-empty-no-findings`) and wired its usage into `skills/lodestar-review/SKILL.md` Step 4.1 so missing reviewer outputs are caught immediately.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-23 (self-improvement-audit-daily, 00:44 UTC)

### PR review
- **Status:** reviewer-result transport can fail (completion pings without full findings payload), which can silently drop review input in follow-up loops. **Fix applied this cycle:** updated `skills/lodestar-review/SKILL.md` to require durable per-reviewer report artifacts in `notes/review-reports/pr-<PR>-<agent-id>.md` and added a mandatory transport-failure fallback step (read artifact/re-run missing reviewer before synthesis).

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-22 (self-improvement-audit-daily, 00:44 UTC)

### PR review
- **Status:** carry-forward status prefill could copy prior-cycle "implemented this cycle" wording into new snapshots, which created stale self-claims in fresh daily entries. **Fix applied this cycle:** `scripts/notes/prepend-autonomy-audit-snapshot.py` now sanitizes change-event wording (`fix applied` / `implemented` / `added` / `updated`) during `--carry-forward-status` and falls back to section steady-state status templates.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-21 (self-improvement-audit-daily, 00:40 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; implemented a close-out cadence guard in `scripts/notes/close-autonomy-audit.sh` so missing-day drift is checked even when someone runs close-out directly without preflight.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-20 (self-improvement-audit-daily, 00:40 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; latest-pair cadence noise is now naturally clear with consecutive snapshots (`2026-04-19` → `2026-04-20`). Implemented a stricter preflight control in `run-autonomy-audit-preflight.sh`: new `--strict-cadence` mode hard-fails on missing-day gaps instead of advisory-only warnings.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-19 (self-improvement-audit-daily, 00:39 UTC)

### PR review
- **Status:** audit-workflow integrity blocker found and fixed this cycle: duplicate snapshot dates could accumulate silently and drift `> Updated:` pass counts out of sync. Added a duplicate-snapshot guard to `run-autonomy-audit-preflight.sh` plus `--dedupe-apply` for one-command cleanup, then removed the stale duplicate `2026-03-15` snapshot block so preflight/finalize checks are deterministic again. Cadence guard still surfaces the historical 2026-03-20→2026-04-18 gap, but now does so explicitly on every run.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-18 (self-improvement-audit-daily, 00:38 UTC)

### PR review
- **Status:** audit-workflow blocker found and fixed this cycle: preflight cadence checks only compared the latest snapshot pair, so long outages after the latest snapshot could be silently missed. Added current-date freshness enforcement (`--require-current`) plus deterministic `--reference-date` support in `check-autonomy-audit-cadence.py`, and wired both into `run-autonomy-audit-preflight.sh`.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-03-20 (self-improvement-audit-daily, 23:46 UTC)

### PR review
- **Blocker:** follow-up guard wrapper handled GitHub delta sync + metadata drift, but stale unresolved critical/major findings were still a separate manual command, so reviewers could miss aging blockers in re-review loops.
- **Fix applied this cycle:** expanded `scripts/review/run-followup-guards.sh` into a 3-step guard:
  - runs `track-findings.py sync-gh`,
  - runs `check-pr-metadata-drift.py` and stores `pr-<PR>-metadata-drift.md`,
  - runs `track-findings.py stale --days 7 --severity critical major` and stores `pr-<PR>-stale-findings.md`.
- Added `--fail-on-stale`, `--stale-days`, and `--skip-stale-check` controls, and updated `skills/lodestar-review/SKILL.md` so this is the default follow-up path.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---

## Daily Audit Snapshot — 2026-03-19 (self-improvement-audit-daily, 23:46 UTC)

### PR review
- **Blocker (previous cycle):** PR metadata drift checker existed, but follow-up review workflow docs did not require running it before re-review.
- **Fix applied this cycle:** wired a mandatory metadata-drift guard step into `skills/lodestar-review/SKILL.md` Finding Resolution Tracking workflow:
  - run `scripts/github/check-pr-metadata-drift.py` on follow-up commits,
  - persist report to `notes/review-reports/pr-<PR>-metadata-drift.md`,
  - update title/body via `gh pr edit` when exit code `2` signals drift.

### CI fix
- **Status:** retry telemetry + `logs-unavailable` fallback path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** advisor timeout fallback policy remains codified and operational; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle path remains healthy; no new blocker discovered this cycle.

---

## Daily Audit Snapshot — 2026-03-18 (self-improvement-audit-daily, 23:46 UTC)

### PR review
- **Status:** finding tracker + stale escalation path are healthy; no new blocker discovered this cycle.

### CI fix
- **Status:** `logs-unavailable` fallback wiring is operational (auto-fetch + reclassification metadata); no new blocker discovered this cycle.

### Spec implementation
- **Blocker:** architecture consult loops can stall on repeated `gpt-advisor` `thinking: xhigh` timeouts, delaying convergence and wasting audit cycles.
- **Fix applied this cycle:** updated `skills/dev-workflow/SKILL.md` with a required timeout fallback policy:
  - start with `xhigh`,
  - allow one tighter retry max,
  - then fallback to `thinking: high` with practical scope,
  - log each round outcome in `TRACKER.md` for resumable context.

### Devnet debugging
- **Status:** triage/correlator/incident bundle path remains healthy; no new blocker discovered this cycle.

---

## Daily Audit Snapshot — 2026-03-17 (self-improvement-audit-daily, 23:46 UTC)

### PR review
- **Status:** finding tracker + stale-escalation cron path are operational; no new blocker discovered this cycle.

### CI fix
- **Blocker:** `logs-unavailable` CI classifications are still slow to triage because there was no one-command fallback to pull failed/full run logs into a local artifact.
- **Fix applied this cycle:** added `scripts/ci/fetch-run-logs.sh <run-id> [--repo owner/repo] [--output <path>]`.
  - tries `gh run view --log-failed` first, then falls back to `--log`,
  - saves logs under `tmp/ci-logs/` by default,
  - prints fetch mode + line/byte counts for quick auditability.

### Spec implementation
- **Status:** extraction + compliance + vector-readiness gates are operational; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage, correlator, incident bundle, and startup helper scripts are operational; no new blocker discovered this cycle.

---

## Daily Audit Snapshot — 2026-03-16 (self-improvement-audit-daily, 23:46 UTC)

### PR review
- **Status:** stale-finding weekly escalation cron is now live and reporting correctly; no new blocker discovered this cycle.

### CI fix
- **Status:** retry telemetry + rolling-window degradation detection are operational; no new blocker discovered this cycle.

### Spec implementation
- **Blocker (previous cycle):** test-vector freshness checks were implicit (easy to skip).
- **Fix applied this cycle:** added `scripts/spec/check-test-vector-readiness.sh` and wired it into `skills/dev-workflow/SKILL.md` spec-vector gate.
  - verifies `~/consensus-specs/tests/` exists and is populated,
  - reports `tests/` recency based on git history,
  - supports `--require-fresh` to hard-fail when vectors are stale.

### Devnet debugging
- **Status:** triage, correlator, incident bundle, and startup helper scripts are operational; no new blocker discovered this cycle.

---

## Daily Audit Snapshot — 2026-03-15 (self-improvement-audit-daily, 23:46 UTC)

### PR review
- **Blocker:** stale-finding report exists, but no scheduled escalation wrapper is wired yet.
- **Proposed fix:** add a weekly cron around `scripts/review/stale-findings-report.sh` that only emits when stale critical/major findings are present.

### CI fix
- **Blocker (previous cycle):** retry telemetry existed but no threshold-based sustained-degradation detection.
- **Fix applied this cycle:** added rolling-window escalation in `scripts/ci/auto_fix_flaky.py`:
  - persists `scan_history` with retry telemetry per run,
  - computes `llm_retry_escalation` over configurable window/thresholds,
  - emits escalation status in clean/failure JSON output,
  - stores escalation snapshot under `last_scan` for tracker visibility.
- **Workflow update:** updated `scripts/ci/CRON_PROMPT.md` to require explicit warning when `llm_retry_escalation.degraded=true`.

### Spec implementation
- **Status:** extraction + compliance gates operational; no new gap discovered this cycle.

### Devnet debugging
- **Status:** triage, correlator, and incident bundle scripts operational; no new gap discovered this cycle.

---

## Daily Audit Snapshot — 2026-03-14 (self-improvement-audit-daily)

### PR review
- **Blocker:** stale-finding query exists, but no automation path currently opens/refreshes a follow-up backlog item when stale critical findings are detected.
- **Proposed fix:** add a lightweight cron wrapper around `track-findings.py stale --fail-on-match` that writes/updates a single backlog-facing report.

### CI fix
- **Blocker:** retry telemetry now exists in detector output, but no threshold-based escalation policy is codified (e.g., retry_count spikes over rolling runs).
- **Proposed fix:** add a tracker-level threshold check (`llm_retry_count` / `llm_retry_wait_s`) with explicit warning output when sustained degradation is detected.

### Spec implementation
- **Blocker (previous cycle):** compliance checks were split across multiple commands and easy to run inconsistently.
- **Fix applied this cycle:** added one-command wrapper `scripts/spec/prepr-compliance-gate.sh` to run report generation + metadata checks and emit a single pass/fail summary.

### Devnet debugging
- **Blocker:** incident packaging is still manual (logs + metrics + timeline + environment metadata in one bundle).
- **Proposed fix:** add `scripts/debug/build-incident-bundle.sh` to produce one timestamped markdown bundle for sharing in topic threads/PRs.

---

## Daily Audit Snapshot — 2026-03-13 (self-improvement-audit-daily)

### PR review
- **Blocker (previous cycle):** no explicit escalation query for stale unresolved findings.
- **Fix applied this cycle:** added `python3 scripts/review/track-findings.py stale <PR>` (+ `--severity`, `--days`, `--use-created`, `--fail-on-match`) and documented it in `skills/lodestar-review/SKILL.md`.

### CI fix
- **Blocker:** retry/backoff exists, but concise cron summaries still do not surface retry telemetry (hard to spot degraded API health quickly).
- **Proposed fix:** include `retry_count`, `retry_wait_s`, and `retry_after_seen` in detector summary/tracker line items.

### Spec implementation
- **Blocker:** compliance artifact checks now exist for tracker + PR body, but there is no single pre-PR wrapper that runs the full compliance bundle and emits one pass/fail summary.
- **Proposed fix:** add `scripts/spec/prepr-compliance-gate.sh` to run checker + artifact-presence check and produce one markdown summary block for PR descriptions.

### Devnet debugging
- **Blocker:** incident packaging is still manual (logs + metrics + timeline + environment metadata in one bundle).
- **Proposed fix:** add `scripts/debug/build-incident-bundle.sh` to produce one timestamped markdown bundle for sharing in topic threads/PRs.

---

## Daily Audit Snapshot — 2026-03-12 (self-improvement-audit-daily)

### PR review
- **Blocker:** reviewer findings are tracked, but there is still no explicit escalation policy for stale unresolved findings (e.g., open >7 days with no author response).
- **Proposed fix:** add a `track-findings.py stale` command (or cron wrapper) that flags unresolved high-severity findings older than a threshold.

### CI fix
- **Blocker:** LLM retry/backoff exists, but retry telemetry is still not surfaced in concise cron summaries (hard to spot degraded API health quickly).
- **Proposed fix:** include retry-count/backoff stats in the final detector summary line and tracker notes for each run.

### Spec implementation
- **Blocker:** compliance artifacts were generated but still easy to omit from tracker/PR write-ups.
- **Fix applied this cycle:** updated `skills/dev-workflow/SKILL.md` to require recording compliance artifacts in `TRACKER.md` and including a dedicated "Spec Compliance" block in PR descriptions; added reusable template `notes/spec-compliance-pr-block.md`.
- **Next focus:** add lightweight lint/check script that validates tracker + PR body contain compliance artifact references before merge.

### Devnet debugging
- **Blocker:** incident packaging is still manual (logs + metrics + timeline + environment metadata in one bundle).
- **Proposed fix:** add `scripts/debug/build-incident-bundle.sh` to produce one timestamped markdown bundle for sharing in topic threads/PRs.

---

## 1. PR Review

### Current State
Multi-persona review via `lodestar-review` skill. Parallel spawning, persona prompts, inline GitHub comment posting. Works well when diff scope is clear.

### Gaps

#### ~~🟡 PR follow-up wrapper lacked machine-readable local preflight~~ ✅ FIXED (2026-06-15)
~~`scripts/review/run-followup-guards.sh` had guarded live execution, but autonomous PR-review wrappers could not validate the full helper chain without supplying a real PR and risking GitHub fetch/report side effects. That left helper drift detectable only during an actual follow-up run.~~

**Fix applied:** added `--check-only --json` to `scripts/review/run-followup-guards.sh`:
- validates `python3`, `gh`, wrapper shell syntax, `fetch-pr-discussion.py --check-only --json`, `track-findings.py --help`, `check-pr-metadata-drift.py --help`, the executable GitHub access guard, and review-report directory readiness,
- keeps the live follow-up path unchanged and rejects `--json` outside `--check-only`,
- wired the preflight into `scripts/github/check-github-guard-coverage.sh`,
- documented the machine-readable preflight in `skills/lodestar-review/SKILL.md`.

#### ~~🟡 PR follow-up wrapper lacked suspension pre-flight~~ ✅ FIXED (2026-06-01)
~~The review follow-up wrapper `scripts/review/run-followup-guards.sh` invoked `track-findings.py sync-gh` and `check-pr-metadata-drift.py` without a wrapper-level GitHub access pre-flight. During account suspension, the wrapper could fail after entering step 1 or after creating report paths instead of producing one explicit skip signal before side effects.~~

**Fix applied:** added `bail_if_github_suspended()` to `scripts/review/run-followup-guards.sh`:
- calls the shared cached `scripts/github/check-github-access.sh` guard before sync/artifact steps,
- supports `GITHUB_ACCESS_STATE_FILE` / `GITHUB_ACCESS_MAX_AGE_MINUTES` overrides for deterministic tests,
- exits `4` with `GITHUB_SUSPENDED_SKIP` before partial follow-up guard work when GitHub is known suspended,
- extended `scripts/github/check-github-guard-coverage.sh` to verify the wrapper remains in the guarded surface.

#### ~~🟡 PR metadata-drift checker lacked suspension pre-flight~~ ✅ FIXED (2026-05-29)
~~The metadata drift checker was part of the PR review follow-up guardrail surface, but `scripts/github/check-pr-metadata-drift.py` still invoked `gh pr view` / `gh pr diff` directly. During GitHub suspension, direct checker runs could fail only after entering the metadata workflow instead of taking the shared cached skip path.~~

**Fix applied:** added `bail_if_github_suspended()` to `scripts/github/check-pr-metadata-drift.py`:
- calls the shared cached `scripts/github/check-github-access.sh` guard before PR metadata/diff fetches,
- supports `GITHUB_ACCESS_STATE_FILE` / `GITHUB_ACCESS_MAX_AGE_MINUTES` overrides for deterministic tests,
- exits `4` with `GITHUB_SUSPENDED_SKIP` before direct `gh pr` calls when GitHub is known suspended,
- extended `scripts/github/check-github-guard-coverage.sh` to verify the metadata-drift checker remains guarded.

#### ~~🟡 GitHub review-comment import lacked suspension pre-flight~~ ✅ FIXED (2026-05-28)
~~The review finding tracker had `import-gh` / `sync-gh` commands for PR review-comment follow-up, but those commands invoked `gh api` directly. During GitHub suspension they could fail only after entering the review workflow, which made autonomous review follow-up brittle and inconsistent with the newer cron guards.~~

**Fix applied:** added `bail_if_github_suspended()` to `scripts/review/track-findings.py`:
- calls the shared cached `scripts/github/check-github-access.sh` guard before `import-gh` and `sync-gh`,
- supports `GITHUB_ACCESS_STATE_FILE` / `GITHUB_ACCESS_MAX_AGE_MINUTES` overrides for deterministic tests,
- exits `2` with `GITHUB_SUSPENDED_SKIP` before review-comment fetching when GitHub is known suspended,
- extended `scripts/github/check-github-guard-coverage.sh` to verify the finding tracker remains guarded.

#### ~~🔴 Reviewer false positives~~ ✅ FIXED (2026-03-08)
~~Sub-agents sometimes flag files **not in the PR diff** (confirmed on PR #8993: `dataColumns.ts`, `gloas.ts` flagged but not changed). This wastes effort and can lead to spurious follow-up commits.~~

**Fix applied:** mandatory false-positive guard in `lodestar-review/SKILL.md`:
- get `git diff --name-only` before acting on findings,
- include changed-file list in reviewer prompts,
- discard findings for files outside the diff.

#### ~~🟡 No reviewer task pre-injection of changed-file scope~~ ✅ FIXED (2026-03-08)
~~Reviewer prompts don't currently include the file list — so reviewers have to infer scope from the diff content, which they sometimes miss.~~

**Fix applied:** `lodestar-review/SKILL.md` Step 3 spawn task template now explicitly includes the `## Files Changed in This PR` block (from Step 1.5) between the persona and the diff, with the "IMPORTANT: Only flag issues in the files listed above" instruction baked into the template literal.

#### ~~🟢 No automated convergence triage~~ ✅ FIXED (2026-03-08)
~~When multiple reviewers flag the same issue, I manually merge.~~

**Fix applied:** `scripts/review/track-findings.py dedup <PR>` groups open findings by file+line proximity (±5 lines), showing which locations are flagged by multiple reviewers. Also added `import --markdown` to parse free-form reviewer output into structured findings, and `check --changed-files` to flag findings on files touched by a new commit.

#### ~~🟡 No stale unresolved-finding escalation query~~ ✅ FIXED (2026-03-13)
~~Reviewer findings are tracked, but there was no fast way to answer: "which open critical/major findings are stale (>7d)?"~~

**Fix applied:** extended `scripts/review/track-findings.py` with `stale` command:
- `track-findings.py stale <PR>` defaults to open `critical|major` findings older than 7 days (`updated` timestamp)
- supports `--severity`, `--days`, `--use-created`, and `--fail-on-match` (for cron/automation wrappers)
- wired usage into `skills/lodestar-review/SKILL.md` follow-up workflow

#### ~~🔴 No review finding resolution tracking~~ ✅ FIXED (2026-03-08)
~~After posting a review, when the author pushes new commits, I have no system for tracking which findings got addressed. I manually re-read everything.~~

**Fix applied:** added `scripts/review/track-findings.py` workflows (`check`, `resolve`, `sync-gh`, `dump`) for explicit re-verification after follow-up commits.

---

## 2. CI Fix

### Current State
CI autofix cron (`573d18ec`) runs hourly, classifies flaky failures, applies pattern-based fixes via Codex, opens PRs against `unstable`. Pattern library covers: shutdown-race, peer-count-flaky, timeout, vitest-crash.

### Gaps

#### ~~🟡 CI log fetch helper lacked local-only preflight~~ ✅ FIXED (2026-06-12)
~~`scripts/ci/fetch-run-logs.sh` had a guarded live path, but no `--check-only` mode. Guard coverage could assert strings/executable bits, but it could not execute the helper's local prerequisite path without a real Actions run id. That left a small gap where syntax/argument handling or missing local tooling could drift until the next live CI failure triage.~~

**Fix applied:** added `--check-only` to `fetch-run-logs.sh`:
- validates the `gh` CLI and `scripts/github/check-github-access.sh` executable guard without calling GitHub,
- allows preflight execution without a run id,
- keeps the live path unchanged for `gh run view --log-failed` / full-log fallback,
- wired the preflight into `scripts/github/check-github-guard-coverage.sh`.

#### ~~🟡 CI log fetch helper bypassed GitHub suspension guard~~ ✅ FIXED (2026-06-08)
~~`scripts/ci/fetch-run-logs.sh` called `gh run view --log-failed` / `--log` directly, so an autonomous CI fixer could still fail mid-triage during a known cached GitHub suspension. It also lacked the executable bit despite being documented as a direct command.~~

**Fix applied:** added `bail_if_github_suspended()` to `fetch-run-logs.sh`, set the helper executable, and expanded `scripts/github/check-github-guard-coverage.sh` to require its guard strings and executable bit. Suspended-cache runs now emit `GITHUB_SUSPENDED_SKIP` and exit `4` before any `gh run view` call.

#### ~~🟡 No auto-linkage to existing GitHub issues~~ ✅ FIXED (2026-03-07)
~~When CI autofix opens a fix PR, it doesn't check whether an open issue already tracks that failure, and doesn't reference/close it.~~

**Fix applied:** `CRON_PROMPT.md` Step 2 now has an "Issue linkage (mandatory)" step (Step 4): search `gh issue list --search "<test-name> in:title,in:body is:issue state:open"`, if hits found post a PR comment linking them, log linked issue IDs in the tracker update.

#### ~~🟡 Pattern-based classifier misses semantic failures~~ ✅ FIXED (2026-03-07)
~~The classifier matches keyword patterns. Failures with novel error messages or new test paths fall through unclassified.~~

**Fix applied:** Added `classify_with_llm()` to `auto_fix_flaky.py`. When keyword classifier returns `unknown-failure`, it now calls `gpt-4o-mini` with a structured system prompt and 13-category taxonomy. Returns `classification`, `confidence`, `fixable`, and `fix_hint`. Falls back gracefully if OPENAI_API_KEY is missing or call fails. `--no-llm` flag available for offline use.

#### ~~🟢 No confidence score in fix quality~~ ✅ FIXED (2026-03-07)
~~Codex applies fixes but there's no check on whether the fix actually addresses root cause vs. masking (e.g., bumping timeout). This leads to PRs that merge but don't fix the underlying issue.~~

**Fix applied:** Added `confidence` field (high/medium/low based on classification source) and `fix_confidence` field (`root-cause` | `likely-root-cause` | `masking-risk` | `unknown`) to all findings in `auto_fix_flaky.py`. `CRON_PROMPT.md` updated: if `fix_confidence` is `masking-risk`/`unknown`, cron agent must add PR comment flagging it for human review.

---

## 3. Spec Implementation

### Current State
Use `dev-workflow` skill for multi-agent development. Codex/Claude CLI for implementation. `~/consensus-specs` available locally. `scripts/pre-validate.mjs` for basic pre-flight checks.

### Gaps

#### ~~🟡 Spec vector readiness preflight lacked machine-readable output~~ ✅ FIXED (2026-06-16)
~~`scripts/spec/check-test-vector-readiness.sh` verified the local `~/consensus-specs/tests/` tree, but only emitted prose and could select generated cache/report files as its sample path. Autonomous spec-work wrappers needed brittle text parsing to distinguish ready/stale/missing-vector states, and the sample path could make a cache-only or report-only tree look healthier than it was.~~

**Fix applied:** added `--json` to `scripts/spec/check-test-vector-readiness.sh` and made the script executable.
- emits structured `ok`, `status`, `stale`, `testsAgeDays`, `maxAgeDays`, `sampleFile`, repo/head metadata, and failure statuses for missing repo/tests/vector data,
- preserves existing human-readable output and exit codes,
- filters `__pycache__`, `.pyc`, and `test-reports` files from sample discovery,
- verified JSON success, JSON stale failure (`--max-age-days 0 --require-fresh`), human output, shell syntax, and missing-repo JSON failure.

#### ~~🟡 Spec compliance preflight lacked machine-readable output~~ ✅ FIXED (2026-06-14)
~~`scripts/spec/prepr-compliance-gate.sh --check-only` could validate local prerequisites, but only emitted prose. Autonomous wrappers needed brittle text parsing to distinguish a clean pass from missing compliance tooling. Proposed fix: add a JSON output path for check-only preflight and document it in the dev workflow.~~

**Fix applied:** added `--check-only --json` to `scripts/spec/prepr-compliance-gate.sh` and documented the automation form in `skills/dev-workflow/SKILL.md`.
- emits structured `ok`, `python3Available`, workspace, and helper-specific `present` / `helpOk` / `syntaxOk` fields,
- exits `2` on failed preflight while preserving machine-readable stdout,
- rejects `--json` outside `--check-only` so the full PR-gate path remains unchanged.

#### ~~🔴 No automated spec section extraction~~ ✅ FIXED (2026-03-07)
~~I manually grep `~/consensus-specs` for relevant pseudocode when implementing. This is slow and error-prone (easy to miss related functions/types across files).~~

**Fix applied:** added `scripts/spec/extract-spec-section.sh` to search spec markdown and follow symbol-import chains for related definitions.

#### ~~🔴 No LLM spec compliance check (new — 2026-03-08)~~ ✅ FIXED (2026-03-09)
Before this was implemented, spec-function ports could ship without a structured pseudocode-vs-TS parity check, relying on slow and error-prone manual reading.

**Fix applied:** `scripts/spec/check-compliance.py <spec-function> <ts-file> <ts-function>` now:
- Extracts the pseudocode block from `~/consensus-specs`
- Compares it against the TS implementation with an LLM pass
- Emits a diff-style compliance report: implemented ✅ / missing ⚠️ / diverged ❌

#### ~~🟡 No test-vector auto-download awareness~~ ✅ FIXED (2026-03-16)
~~When implementing spec functions, I sometimes forget to run against official test vectors. The vectors live in `~/consensus-specs/tests/` but need a separate download step.~~

**Fix applied:** added `scripts/spec/check-test-vector-readiness.sh` and wired it into the `skills/dev-workflow/SKILL.md` spec-vector gate.
- validates `~/consensus-specs/tests/` exists and has vector files,
- reports staleness of `tests/` from git history,
- supports `--require-fresh` to fail fast when vectors are too old.

#### ~~🟢 No implementation checklist per fork type~~ ✅ FIXED (2026-03-07)
~~Each fork (Gloas, Fulu, etc.) has different patterns: new SSZ types, new gossip topics, new reqresp methods, new fork-choice fields, new API endpoints. No single checklist ensures all are covered.~~

**Fix applied:** added `notes/fork-implementation-checklist.md` covering fork surfaces, test matrix, interop gates, and PR readiness criteria.

---

## 4. Devnet Debugging

### Current State
`grafana-loki` skill for log queries. `join-devnet` skill for local beacon node. `kurtosis-devnet` skill for full multi-client devnets. `local-mainnet-debug` skill for mainnet simulation. `investigate` now has a routing preflight for local Kurtosis vs remote panda datasource readiness. Good tooling, but each debugging session starts from scratch.

### Gaps

#### ~~🟡 Devnet triage had no telemetry preflight~~ ✅ FIXED (2026-06-17)
~~`scripts/debug/devnet-triage.sh` could skip Loki/Prometheus sections when Grafana prerequisites were missing, but autonomous devnet-debugging wrappers had no no-side-effect way to validate that state before a longer investigation. That made it easy to discover missing telemetry only after starting data collection.~~

**Fix applied:** added `--check-only` and `--require-grafana` to `scripts/debug/devnet-triage.sh`, and documented the preflight in `skills/devnet-debug/SKILL.md`:
- validates local required tools without querying Grafana or writing a report,
- treats `--require-grafana` as a hard preflight for `GRAFANA_TOKEN`, `curl`, and `jq`,
- reports optional `lsof` / Grafana availability in the dry-run output,
- guards live Loki/Prometheus helpers against missing `curl`.

#### ~~🟡 Remote devnet routing treated panda datasource null as network absence~~ ✅ FIXED (2026-06-07)
~~The `investigate` skill routed remote deployments by asking agents to run `panda datasources --json`, but panda can exit successfully with `{"datasources": null}` when auth/server datasource access is not ready. That lets an auth/tooling blocker masquerade as "target network not found" and can waste a debugging session before any useful data collection starts.~~

**Fix applied:** added `scripts/debug/check-devnet-routing-readiness.py` and wired it into `~/.agents/skills/investigate/SKILL.md`:
- classifies a target as local Kurtosis or remote panda datasource,
- treats `datasources=null`, empty datasource names, invalid JSON, or panda command failure as explicit preflight failures,
- exits `2` with `PANDA_DATASOURCES_UNAVAILABLE` before long remote investigations when panda access is not ready,
- supports `--json` for wrapper/crons and verified the current auth-blocked `glamsterdam-devnet-5` state.

#### ~~🔴 No multi-node log correlator~~ ✅ FIXED (2026-03-09)
When debugging consensus failures across a devnet, logs from 4-8 nodes all matter. Today I query Loki once per node and manually cross-reference timestamps. A script that fetches logs from multiple nodes in parallel, merges + sorts by timestamp, and highlights consensus-relevant events (proposal, attestation, fork-choice updates) would turn a 30-min investigation into a 5-min one.

**Fix applied:** `scripts/debug/correlate-logs.sh [node1] [node2...] --from <ts> --to <ts>` now:
- Queries Loki for each node in parallel
- Merges results sorted by timestamp
- Highlights lines matching `/fork_choice|attestation|proposal|head_block|finalized/`
- Outputs a unified timeline with node-prefixed lines

#### ~~🔴 No scripted first-5-minutes diagnostic~~ ✅ FIXED (2026-03-09)
~~Every devnet debugging session starts with the same manual sequence: check zombie processes, check ports, check Loki for recent errors, compare Grafana metrics, check peer count. This takes 10-15 minutes every time.~~

**Fix applied:** added `scripts/debug/devnet-triage.sh` for one-command first-pass diagnostics (processes, ports, Loki errors, Prometheus probes, restart hints).

#### ~~🟡 No structured debugging session template~~ ✅ FIXED (2026-03-07)
~~When investigating complex issues (like feat4 QUIC crashes), I accumulate evidence across many tool calls without a clear structure. Later it's hard to reconstruct what was ruled out and why.~~

**Fix applied:** created `notes/debug-session-template.md` and integrated it into investigation workflow.

#### ~~🟡 Mixed-peer devnet startup is still manual~~ ✅ FIXED (2026-03-08)
~~Spinning up a mixed-peer devnet (e.g., Lodestar B2 + C2 nodes against ePBS devnet) requires multiple manual steps and ad-hoc configuration.~~

**Fix applied:** codified EPBS devnet-0 startup flow in `scripts/devnet/start-epbs-devnet.sh` for repeatable bring-up.

---

## Improvements Implemented This Cycle

### ✅ Daily autonomy audit preflight now verifies all domains by default (2026-06-23)
Updated `scripts/notes/run-autonomy-audit-preflight.sh`.
- runs `scripts/notes/check-autonomy-domain-preflights.py` before daily memory scaffolding and snapshot insertion,
- keeps explicit `--skip-domain-preflights` for intentional bypasses,
- passes through `--strict-ci-api-key` and `--require-devnet-grafana` so CI/devnet credential readiness can be enforced at audit-preflight time,
- verified shell syntax, standalone domain JSON output, and a rerun of the integrated preflight against the existing 2026-06-23 snapshot.

**Rationale:** the daily audit preflight should not carry forward PR-review, CI-fix, spec-implementation, or devnet-debugging status lines without first proving the corresponding domain checks still run.

### ✅ Daily autonomy audit now has one cross-domain preflight runner (2026-06-20)
Added `scripts/notes/check-autonomy-domain-preflights.py`.
- runs the side-effect-free PR-review, CI-fix, spec-implementation, and devnet-debugging preflights from one command,
- normalizes each helper's JSON/prose output plus exit code into one machine-readable payload,
- uses a dummy `OPENAI_API_KEY` only for local CI quality-gate package/import readiness when the shell lacks the real key, with `--strict-ci-api-key` available for hard enforcement,
- verified default JSON success, strict CI-key failure in the current no-key shell, and Python syntax.

**Rationale:** the daily audit should be able to prove the four autonomy guardrails are still runnable together instead of manually carrying forward "healthy" status lines from separate helpers.

### ✅ Devnet triage now has a no-side-effect telemetry preflight (2026-06-17)
Added `--check-only` and `--require-grafana` to `scripts/debug/devnet-triage.sh`, and wired the command into `skills/devnet-debug/SKILL.md`.
- validates required local tools without querying Grafana or writing a report,
- lets agents fail fast when Loki/Prometheus telemetry is required but `GRAFANA_TOKEN`, `curl`, or `jq` are missing,
- keeps partial, best-effort live triage behavior unchanged when telemetry is optional,
- verified `bash -n`, optional preflight success, required-Grafana missing-token failure, and existing GitHub guard coverage.

**Rationale:** autonomous devnet debugging should know before data collection whether it is about to produce a telemetry-backed report or a local-only partial report.

### ✅ Spec vector readiness now has JSON output (2026-06-16)
Added `--json` to `scripts/spec/check-test-vector-readiness.sh` and made the script executable.
- reports structured ready/stale/missing states with repo/head metadata and `testsAgeDays`,
- keeps existing human-readable output and exit codes unchanged,
- excludes generated cache/report files from sample discovery so readiness evidence points at source test content,
- verified success, stale-failure, missing-repo, syntax, and human-output paths.

**Rationale:** autonomous spec implementation needs a stable machine-readable vector-readiness preflight before spawning implementation/review workers or deciding whether a stale consensus-specs checkout must be refreshed.

### ✅ Spec compliance preflight now has JSON output (2026-06-14)
Added `--check-only --json` to `scripts/spec/prepr-compliance-gate.sh` and wired the command into `skills/dev-workflow/SKILL.md`.
- reports `ok`, `python3Available`, workspace, and helper-specific readiness fields,
- keeps the existing human-readable `--check-only` output unchanged,
- rejects `--json` for the full PR-gate mode to avoid implying a JSON summary for report generation.

**Rationale:** spec implementation autonomy needs a stable machine-readable preflight result before spawning implementation/review workers or assembling PR metadata.

### ✅ Spec compliance gate now has local-only preflight (2026-06-13)
Added `--check-only` to `scripts/spec/prepr-compliance-gate.sh` and wired it into `skills/dev-workflow/SKILL.md`.
- validates `python3` and the required compliance helper scripts without requiring tracker, PR body, or spec tuple inputs,
- checks `check-compliance.py --help` and shell syntax for `check-compliance-artifacts.sh`,
- keeps normal pre-PR report generation and metadata validation unchanged.

**Rationale:** spec implementation autonomy should fail fast on local compliance-gate drift before a PR body/tracker is assembled or review is requested.

### ✅ CI run-log fetch helper now has local-only preflight (2026-06-12)
Added `--check-only` to `scripts/ci/fetch-run-logs.sh` and wired it into `scripts/github/check-github-guard-coverage.sh`.
- validates local prerequisites (`gh` and the cached GitHub access guard) without requiring a workflow run id,
- lets the guard coverage script execute the helper's preflight path without calling GitHub,
- keeps live log fetching unchanged for `gh run view --log-failed` with full-log fallback.

**Rationale:** the CI fixer depends on run logs during triage. A cheap offline preflight makes helper drift visible before a live failed-run investigation needs it.

### ✅ Delta detector ignores removed one-off advisory sections (2026-06-11)
Updated `scripts/notes/check-autonomy-audit-delta.py` so routine green days after a one-off advisory section no longer produce notification noise.
- `hasDelta` now comes from changed required statuses, added non-required sections, changed current non-required sections, or removed required headings.
- Removed non-required headings are still included in JSON diagnostics but do not trigger output by themselves.
- Verified `render-autonomy-audit-response.py` returned `NO_REPLY` when the only current difference was removal of the prior `Audit workflow` section.

**Rationale:** daily audit autonomy should distinguish new current information from yesterday-only advisory context aging out. Otherwise a successful return to steady state can still generate a needless summary.

### ✅ Close-out now reports cadence gaps instead of silent NO_REPLY (2026-06-10)
Updated `scripts/notes/close-autonomy-audit.sh` so advisory cadence gaps become visible output even when finalization otherwise sees no snapshot delta.
- captures missing-day cadence details from `check-autonomy-audit-cadence.py`,
- preserves `--strict-cadence` as the hard-fail path,
- in advisory mode, prevents the `finalize NO_CHANGE -> NO_REPLY` branch from hiding missed daily snapshots.

**Rationale:** today’s preflight found a missing 2026-06-09 audit snapshot. The watchdog already detects this, but close-out should also refuse routine silence when cadence drift is present.

### ✅ CI run-log fetch helper now pre-flights GitHub suspension (2026-06-08)
Wired the shared GitHub-access guard into `scripts/ci/fetch-run-logs.sh`.
- calls `scripts/github/check-github-access.sh` before `gh run view --log-failed` / full-log fallback,
- supports `GITHUB_ACCESS_STATE_FILE` and `GITHUB_ACCESS_MAX_AGE_MINUTES` env overrides for deterministic tests,
- suspended-cache runs emit `GITHUB_SUSPENDED_SKIP` and exit `4` before touching GitHub,
- set the helper executable so its documented direct invocation works,
- expanded `scripts/github/check-github-guard-coverage.sh` to verify the guard wiring and executable bit.

**Rationale:** autonomous CI triage often starts by fetching failed run logs. That helper should degrade as cleanly as the detector and PR-CI monitor when GitHub access is externally blocked.

### ✅ Remote devnet routing preflight detects panda datasource readiness (2026-06-07)
Added `scripts/debug/check-devnet-routing-readiness.py` and documented it in the `investigate` skill.
- checks local Kurtosis enclaves and remote panda datasources in one preflight,
- classifies matching targets as `local-kurtosis` or `remote-panda`,
- treats `panda datasources --json` returning `{"datasources": null}` as an explicit `PANDA_DATASOURCES_UNAVAILABLE` exit `2`,
- supports `--json` output for future wrappers and cron guards.

**Rationale:** autonomous devnet debugging should distinguish "network absent" from "data access not ready" before spawning long investigations. The current panda-auth blocked state is exactly the failure mode this catches.

### ✅ PR follow-up guards now scan all PR discussion surfaces (2026-06-05)
Added `scripts/review/fetch-pr-discussion.py` and wired it into `scripts/review/run-followup-guards.sh`.
- fetches issue-level PR comments, inline review comments, and review bodies in one compact report,
- writes the default artifact to `notes/review-reports/pr-<PR>-discussion.md` through the follow-up wrapper,
- supports author filtering and compact body previews for fast "did we answer this?" checks,
- keeps the shared GitHub suspension guard and `GITHUB_ACCESS_STATE_FILE` / `GITHUB_ACCESS_MAX_AGE_MINUTES` overrides,
- expanded `scripts/github/check-github-guard-coverage.sh` so this new GitHub-dependent surface stays guarded,
- documented the full-surface scan requirement in `skills/lodestar-review/SKILL.md`.

**Rationale:** PR follow-up autonomy should not depend on remembering which GitHub endpoint carries the latest state. Inline-only scans can miss issue comments and review bodies, which recently produced a false "lodekeeper not in any thread" conclusion.

### ✅ Cron watchdog autonomy-cadence check now has deterministic test controls (2026-06-03)
Extended `scripts/cron/check_cron_health.py` so its virtual `autonomy-audit-cadence` check can be exercised against controlled fixtures.
- `CRON_JOBS_PATH` overrides the jobs registry,
- `CRON_HEALTH_STATE_PATH` overrides the watchdog state file,
- `WORKSPACE_PATH` overrides the workspace root used for default helper paths,
- `AUTONOMY_CADENCE_SCRIPT` overrides the cadence guard script path,
- `AUTONOMY_CADENCE_FILE` overrides the target autonomy-gaps markdown file,
- `AUTONOMY_CADENCE_REFERENCE_DATE` passes a deterministic freshness reference date,
- `AUTONOMY_CADENCE_EXPECTED_EVERY_DAYS` passes a deterministic expected spacing.

**Rationale:** the watchdog should be testable without editing the real `notes/autonomy-gaps.md`, touching production failure state, or waiting for live UTC-date drift. This makes stale-audit regression checks reproducible and keeps the virtual cron failure path easier to validate after future watchdog edits.

### ✅ Cron health watchdog now checks autonomy-audit cadence (2026-06-02)
Extended `scripts/cron/check_cron_health.py` with a virtual `autonomy-audit-cadence` failure source.
- it runs `scripts/notes/check-autonomy-audit-cadence.py --latest-only --require-current --fail-on-gap` on each watchdog pass,
- fresh stale-audit gaps and guard errors enter the existing cron-health active-failure state/dedup path,
- recovered cadence failures are reported through the same recovery path as real cron jobs.

**Rationale:** daily audit cadence drift can be the thing the audit cron is supposed to detect, so relying on the next successful audit run leaves blind spots. A virtual watchdog entry makes missed snapshots visible during the regular 30-minute cron-health sweep without adding a separate cron/config change.

### ✅ PR follow-up guard wrapper now pre-flights GitHub suspension (2026-06-01)
Wired the shared GitHub-access guard into `scripts/review/run-followup-guards.sh`.
- the wrapper now calls `bail_if_github_suspended()` before `sync-gh`, metadata-drift, stale-finding, or report-artifact work,
- suspended-cache runs exit `4` with `GITHUB_SUSPENDED_SKIP`, making the external blocker explicit without creating partial follow-up artifacts,
- the guard supports `GITHUB_ACCESS_STATE_FILE` and `GITHUB_ACCESS_MAX_AGE_MINUTES` env overrides for deterministic tests,
- `scripts/github/check-github-guard-coverage.sh` now verifies the follow-up wrapper remains in the guarded surface.

**Rationale:** PR review follow-up is normally run as a single wrapper command. Guarding only the child scripts still leaves the wrapper vulnerable to mid-step exits and partial side effects. A wrapper-level pre-flight turns a known external blocker into one clear skip signal before any PR review follow-up state is touched.

### ✅ PR metadata-drift checker now pre-flights GitHub suspension (2026-05-29)
Wired the shared GitHub-access guard into `scripts/github/check-pr-metadata-drift.py`.
- direct metadata checks now call `bail_if_github_suspended()` before `gh pr view` / `gh pr diff`,
- suspended-cache runs exit `4` with `GITHUB_SUSPENDED_SKIP`, making the external blocker explicit without doing partial PR metadata work,
- the guard supports `GITHUB_ACCESS_STATE_FILE` and `GITHUB_ACCESS_MAX_AGE_MINUTES` env overrides for deterministic tests,
- `scripts/github/check-github-guard-coverage.sh` now verifies the metadata-drift checker remains in the guarded surface.

**Rationale:** PR review follow-up depends on metadata drift checks before re-review. The checker should degrade as cleanly as comment sync and CI automation while GitHub access is suspended, especially when it is run standalone outside the wrapper flow.

### ✅ Review finding tracker now pre-flights GitHub suspension (2026-05-28)
Wired the shared GitHub-access guard into `scripts/review/track-findings.py`.
- `import-gh` and `sync-gh` now call `bail_if_github_suspended()` before `gh api` review-comment fetches,
- suspended-cache runs exit `2` with `GITHUB_SUSPENDED_SKIP`, making the external blocker explicit without doing partial GitHub work,
- the guard supports `GITHUB_ACCESS_STATE_FILE` and `GITHUB_ACCESS_MAX_AGE_MINUTES` env overrides for deterministic tests,
- `scripts/github/check-github-guard-coverage.sh` now verifies the finding tracker remains in the guarded surface.

**Rationale:** review follow-up should degrade as cleanly as CI/notification automation while the GitHub account is suspended. PR review autonomy depends on knowing the blocker before fetching comments, not after a mid-workflow `gh` crash.

### ✅ Catch-up repro checkpoint-depth guard added (2026-05-27)
Added `scripts/debug/check-catchup-depth.sh` to prevent shallow checkpoint starts for sync-depth and OOM repros.
- accepts direct `--head-slot` / `--checkpoint-slot` inputs or fetches slots through Beacon API URLs,
- enforces configurable `--min-epochs` / `--slots-per-epoch` thresholds,
- exits `2` with a clear `too_shallow` signal when the checkpoint cannot exercise the intended catch-up backlog,
- documented the guard in `skills/local-mainnet-debug/SKILL.md` before the launch workflow.

**Rationale:** the active OOM sync repro showed that a latest-finalized checkpoint can look like a successful setup while being too shallow to reproduce the failure. A pre-launch depth guard turns that assumption into a deterministic check and points the next run toward an older `--checkpointState` when needed.

### ✅ GitHub guard coverage verifier for CI automation (2026-05-26)
Added `scripts/github/check-github-guard-coverage.sh` to catch regression in the recent GitHub-suspension bail-out work.
- verifies `scripts/github/check-github-access.sh` exists and is executable,
- verifies the high-frequency GitHub automation callsites still include their script-level bail-out functions and expected silent outputs,
- verifies `scripts/ci/CRON_PROMPT.md` still requires the shared guard and `GITHUB_SUSPENDED_SKIP`,
- wired the CI auto-fix prompt to run this verifier before GitHub access, so prompt/script drift fails before any `gh` call.

**Rationale:** the previous fixes moved suspension handling into scripts, but nothing prevented a future edit from accidentally removing one guard. A cheap local coverage check makes that class of drift visible before a suspended cron burns context or crashes mid-run.

### ✅ CI auto-fix detector now has script-level GitHub-access bail-out (2026-05-25)
Wired the shared GitHub-access guard into `scripts/ci/auto_fix_flaky.py` itself.
- calls `scripts/github/check-github-access.sh` before `scan()`,
- exits cleanly with `GITHUB_SUSPENDED_SKIP` when the cached guard reports suspension,
- keeps unexpected guard failures non-blocking so normal detector errors still surface,
- supports `GITHUB_ACCESS_STATE_FILE` and `GITHUB_ACCESS_MAX_AGE_MINUTES` env overrides for deterministic suspended-cache tests,
- updated `scripts/ci/CRON_PROMPT.md` to document that Step 0 remains mandatory even though the detector now has this fail-safe.

**Rationale:** yesterday's guard covered high-frequency notification/PR-CI scripts, but `ci-autofix-unstable` still depended on prompt discipline. Moving the guard into the detector makes the suspension bail-out resilient to direct/manual runs and future cron prompt edits.

### ✅ Script-level GH-access guard for high-frequency cron callers (2026-05-24)
Wired the shared access guard into the two highest-frequency GH-dependent scripts so the bail is enforced at the script level, not just in cron prompts.
- added `bail_if_github_suspended()` to `scripts/github/github_notifications_sweep.py` — fires `HEARTBEAT_OK` and exits 0 cleanly when the guard returns rc=2,
- added `bail_if_github_suspended()` to `scripts/github/monitor_open_pr_ci.py` — fires `NO_REPLY` and exits 0 cleanly when the guard returns rc=2,
- guard call wraps `subprocess.run([...], timeout=20)` so transient guard failures degrade safely (return to normal flow rather than blocking),
- end-to-end verified: simulated suspended-cache run produces the expected silent signal with rc=0 and no `gh api` invocation.

**Rationale:** `github-notifications` runs every 5 min (288×/day) and `monitor-open-pr-ci` every 30 min. With GitHub suspension active, each previously burned ~18s of context per fire on a 403 crash. Pushing the guard from the cron prompt down into the script means *any* caller (cron, manual run, future cron prompt edits) benefits automatically, and the cached check keeps the bail near-zero-cost.

### ✅ Shared GitHub-access guard added for GH-dependent crons (2026-05-23)
Added `scripts/github/check-github-access.sh` as a pre-flight guard for any cron that calls `gh`.
- calls `gh api user --jq '.login'` with a short timeout
- exits 0 (ok) or 2 (suspended/inaccessible), never blocks unexpectedly
- caches the result in `tmp/github-access-state.json` for up to 10 minutes (configurable) to avoid repeated API calls when multiple crons fire close together
- clear status output: `GITHUB_ACCESS: ok` / `GITHUB_ACCESS: suspended — skip GH-dependent work`
- supports `--max-age-minutes` and `--state-file` overrides for testing

**Rationale:** during account suspension, crons like `github-notifications`, `ci-autofix-unstable`, and `monitor-open-pr-ci` each ran full prompt context before hitting the 403 wall. A single cached guard call at the top of any GH-dependent prompt lets the cron bail immediately, preserving tokens for productive work and reducing noise in cron logs.

### ✅ OpenClaw-only provider follow-ups now stay out of plain CLI sessions (2026-05-22)
Updated `AGENTS.md` and `HEARTBEAT.md` to codify a provider-surface routing guard for channel work.
- added an explicit rule that Discord/Telegram posting, thread follow-up, browser work, and other OpenClaw-only tooling stay in the OpenClaw main/channel session,
- directs tagged follow-up back through `sessions_send` to the real session (`agent:main:discord:channel:<ID>` / Telegram topic session) instead of Claude Code / Codex CLI continuation sessions,
- documents the concrete failure mode exposed by the consensus-specs Discord follow-up that landed in a provider-less CLI session.

**Rationale:** plain CLI coding sessions can continue code investigation, but they may lack provider access and channel context. Routing channel-bound follow-up there creates silent dead ends and missed replies.

### ✅ Close-out now updates the most recent unresolved memory outcome placeholder (2026-05-18)
Updated `scripts/notes/close-autonomy-audit.sh` so `--update-memory-outcome` no longer targets the first unresolved placeholder in `memory/<date>.md`.
- switched replacement logic from first-match `replace(..., 1)` to last-match replacement (`rsplit(..., 1)`),
- updated warning text to reflect the new behavior (`updated only the most recent one`),
- keeps single-target safety (does not rewrite all placeholders).

**Rationale:** if preflight is retried and multiple unresolved stubs exist in the same daily note, close-out should resolve the latest/current audit stub by default, not an older one.

### ✅ Close-out now fails memory-outcome guards before snapshot mutation (2026-05-17)
Updated `scripts/notes/close-autonomy-audit.sh` to reorder close-out steps so memory-note integrity checks run before snapshot finalization.
- moved `--update-memory-outcome` handling to pre-finalize phase,
- moved daily memory outcome placeholder guard (`--skip-memory-outcome-check` path) to pre-finalize phase,
- keeps finalize/cadence/render behavior unchanged once memory guards pass.

**Rationale:** close-out should fail fast before mutating `notes/autonomy-gaps.md` when today's memory outcome is missing/placeholder; this removes partial side effects and makes reruns deterministic.

### ✅ Close-out outcome updater now edits only one placeholder and warns on duplicates (2026-05-16)
Updated `scripts/notes/close-autonomy-audit.sh` to tighten `--update-memory-outcome` replacement scope.
- switched placeholder rewrite from global replacement to single-target replacement (`replace(..., 1)`),
- emit an explicit warning when multiple unresolved placeholders are detected in `memory/<date>.md`,
- preserves existing close-out guard behavior while preventing accidental bulk overwrite of unresolved entries.

**Rationale:** autonomous close-out should only resolve the current audit stub by default; silently rewriting every matching placeholder can hide journaling gaps and degrade note integrity.

### ✅ Close-out memory-outcome replacement now preserves arbitrary text safely (2026-05-15)
Updated `scripts/notes/close-autonomy-audit.sh` to remove shell-substitution edge cases from `--update-memory-outcome`.
- replaced raw `sed` substitution with a Python text rewrite (`placeholder` → `outcome`) written to a temp file,
- kept atomic replacement semantics via tmp-file + `mv`,
- prevents mangled output when the outcome text includes `&` or other replacement metacharacters.

**Rationale:** autonomous close-out should accept natural free-form outcome text (URLs, ampersands, punctuation) without requiring manual escaping.

### ✅ Preflight now writes memory scaffolding only after guard checks pass (2026-05-11)
Updated `scripts/notes/run-autonomy-audit-preflight.sh` to avoid side effects before guard validation.
- moved daily note creation + audit-stub append from pre-guard phase to post-cadence phase,
- new explicit `[3/5]` step now handles memory note/stub writes only when duplicate/consistency/cadence guards succeeded,
- snapshot scaffold insertion now runs at `[4/5]`,
- when note creation is intentionally disabled, preflight now logs explicit skip status for that step.

**Rationale:** failed preflight runs should be side-effect free on memory notes; guard-first ordering avoids orphaned `_fill in after close-out_` placeholders when a run aborts before snapshot insertion.

### ✅ Close-out now enforces daily memory-audit outcome completion (2026-05-10)
Updated `scripts/notes/close-autonomy-audit.sh` to guard against unresolved daily-note audit placeholders.
- added default check for `memory/<date>.md` presence during close-out,
- close-out now fails when the seeded preflight line still contains `- Outcome: _fill in after close-out_.`,
- added explicit override flag `--skip-memory-outcome-check` for intentional/manual bypass scenarios,
- updated usage/help text to document the new guard behavior.

**Rationale:** preflight now seeds daily audit stubs by default, so close-out should enforce that those stubs are actually completed rather than silently carrying placeholder text into archived notes.

### ✅ Autonomy preflight now seeds a daily audit memory-log stub (2026-05-09)
Updated `scripts/notes/run-autonomy-audit-preflight.sh` to bridge the last continuity gap between snapshot scaffolding and daily journaling.
- added default daily-note stub appender (`self-improvement-audit-daily (preflight)`) in `memory/<date>.md`,
- writes a one-time entry per day with snapshot date + close-out reminder,
- added explicit opt-out flag `--no-seed-audit-memory-entry` (and matching help text).

**Rationale:** creating the daily note file alone is not enough; seeding the audit stub makes it much harder to forget writing the same-day audit trace in memory notes.

### ✅ Autonomy preflight now auto-creates the daily memory note scaffold (2026-05-08)
Updated `scripts/notes/run-autonomy-audit-preflight.sh` to enforce daily-note continuity during audit runs.
- added default guard that ensures `memory/<date>.md` exists before autonomy snapshot insertion,
- creates missing daily note files with canonical heading `# Daily Notes — <YYYY-MM-DD>`,
- added explicit opt-out flag `--no-ensure-daily-memory-note` (and matching help text) for intentional bypasses.

**Rationale:** AGENTS continuity rules expect today's memory note to exist every session; making preflight enforce this removes a recurring manual setup step and prevents avoidable note-gap drift.

### ✅ Autonomy preflight now defaults to carry-forward status prefill (2026-05-07)
Updated `scripts/notes/run-autonomy-audit-preflight.sh` to reduce avoidable blank-snapshot churn.
- enabled `--carry-forward-status` behavior by default,
- added explicit `--no-carry-forward-status` override to intentionally insert blank placeholders,
- updated usage/help text + close-out hint wording to reflect review/update flow instead of fill-only flow.

**Rationale:** the audit pipeline already has carry-forward sanitization and delta guards; defaulting to prefilled status lines improves autonomous reliability by reducing manual placeholder handling and accidental `_fill in_` leakage.

### ✅ Cadence-gap output now includes exact missing dates (2026-05-06)
Updated `scripts/notes/check-autonomy-audit-cadence.py` to enrich missing-day diagnostics with concrete in-between dates.
- each gap line now includes a bounded list of missing dates (for example, `2026-05-04`),
- large gaps are still concise via `(+N more)` overflow suffix,
- freshness-gap output (`--require-current`) uses the same date-list format for consistency.

**Rationale:** when a daily audit is missed, concrete missing dates are faster to triage and backfill than raw day-counts alone, especially in autonomous cron runs where log context is limited.

### ✅ Close-out NO_REPLY guard against live priority leakage (2026-05-05)
Updated `scripts/notes/close-autonomy-audit.sh` so finalize `NO_CHANGE` no longer auto-emits `NO_REPLY` blindly.
- added default `Next Audit Priorities` live-item guard via `check-next-audit-priorities.py --fail-if-live`
- when live items still exist, close-out now fails fast with actionable stderr guidance
- added explicit override flag `--allow-live-priorities-no-reply` for deliberate/manual bypasses

**Rationale:** prevents silent routine replies from masking pending autonomy-follow-up items that should keep the audit loop active.

### ✅ Historical snapshot-structure guard added to autonomy consistency checks (2026-05-03)
Extended `scripts/notes/check-autonomy-gaps-consistency.py` so it now validates **every** daily snapshot block (not just top-level metadata):
- verifies required domains are present in each snapshot (`PR review`, `CI fix`, `Spec implementation`, `Devnet debugging`),
- requires structured progress markers per section,
- accepts both modern `- **Status:** ...` entries and legacy `Blocker/Fix applied/Proposed fix` formats for backward compatibility,
- fails with explicit per-snapshot/per-section errors when structure is missing.

**Rationale:** catches malformed historical snapshots early and keeps close-out consistency checks durable across both old and new audit formats.

### ✅ Reviewer artifact metadata writer helper added (2026-04-29)
Added `scripts/review/write-review-artifact.sh` to make reviewer artifact creation deterministic and marker-safe.
- writes `notes/review-reports/pr-<PR>-<agent-id>.md` with required metadata lines:
  - `Reviewer: <agent-id>`
  - `Reviewed commit: <HEAD_SHA>` (auto-resolved from `--head-repo`)
- accepts body via `--body-file` or stdin and falls back to `No findings.` when empty
- prints the artifact path for easy inclusion in reviewer completion messages
- updated `skills/lodestar-review/SKILL.md` durable-output section to recommend this helper in reviewer tasks

**Rationale:** we already verify metadata markers at synthesis time; this helper prevents marker drift at write time, reducing avoidable reruns from missing marker lines.

### ✅ Reviewer artifact ownership guard added (2026-04-28)
Extended `scripts/review/check-review-artifacts.sh` with a per-agent ownership check so artifact verification can reject cross-agent file mix-ups.
- new CLI option: `--require-agent-marker` (requires each artifact to contain `Reviewer: <agent-id>`)
- verifier summary now reports `missing_agent_marker=<count>` and fails with exit `2` when marker checks fail
- updated `skills/lodestar-review/SKILL.md` durable-output contract to require both metadata lines:
  - `Reviewer: <agent-id>`
  - `Reviewed commit: <HEAD_SHA>`
- updated Step 4.1 quick verifier command to include `--require-agent-marker`

**Rationale:** commit-affinity checks prove *which head* an artifact reviewed, but not *which reviewer* authored it. Agent-marker enforcement closes that integrity gap and prevents accidental cross-agent artifact reuse during autonomous synthesis loops.

### ✅ Reviewer HEAD-marker auto-resolution guard added (2026-04-27)
Extended `scripts/review/check-review-artifacts.sh` with built-in reviewed-commit marker resolution so follow-up verifier commands no longer rely on manual SHA interpolation.
- new CLI option: `--require-reviewed-head` (requires marker `Reviewed commit: <HEAD_SHA>`)
- new CLI option: `--head-repo <path>` (deterministic HEAD source; defaults to current directory)
- verifier now fails fast if HEAD cannot be resolved from the selected repo
- updated `skills/lodestar-review/SKILL.md` Step 4.1 quick verifier to use `--require-reviewed-head --head-repo /absolute/path/to/repo`

**Rationale:** keeps commit-affinity checks deterministic in autonomous follow-up loops and reduces accidental false passes from hand-written SHA marker strings.

### ✅ Reviewer-artifact commit-affinity guard added (2026-04-26)
Extended `scripts/review/check-review-artifacts.sh` with repeatable `--require-text <value>` markers so artifact validation can enforce run-specific metadata (for example, exact head SHA markers).
- new repeatable CLI option: `--require-text "..."`
- verifier now prints required markers and fails with exit `2` when a marker is missing (`missing_text=<count>` in summary)
- updated `skills/lodestar-review/SKILL.md` to require reviewer artifacts to include `Reviewed commit: <HEAD_SHA>` and to verify that marker during Step 4.1

**Rationale:** age checks catch stale files, but they do not prove the artifact belongs to the current head commit. Marker-based validation blocks fresh-but-wrong artifacts from previous review rounds.

### ✅ Reviewer-artifact freshness guard added (2026-04-25)
Extended `scripts/review/check-review-artifacts.sh` so the verifier can reject stale reviewer artifacts with a new `--max-age-minutes <n>` option.
- adds stale-age validation via artifact mtime (summary now reports `stale=<count>`)
- keeps existing missing/invalid checks and `--allow-empty-no-findings` behavior
- updated `skills/lodestar-review/SKILL.md` Step 4.1 quick verifier to include `--max-age-minutes 180` and stale-artifact guidance

**Rationale:** presence checks alone can pass old reviewer files from a previous diff. Age-bounding the artifact set ensures synthesis uses fresh findings from the current review round.

### ✅ Reviewer-artifact completeness guard script added (2026-04-24)
Added `scripts/review/check-review-artifacts.sh` and updated `skills/lodestar-review/SKILL.md` to call it during transport-failure fallback before synthesis.
- validates expected reviewer artifacts: `notes/review-reports/pr-<PR>-<agent-id>.md`
- flags missing/undersized files with exit `2`
- supports `--allow-empty-no-findings` so intentional "No findings" reports pass

**Rationale:** durable artifacts only help if every expected reviewer actually wrote one. This turns that check into a fast deterministic guard instead of a manual file-by-file scan.

### ✅ Durable reviewer-artifact fallback added to lodestar-review workflow (2026-04-23)
Updated `skills/lodestar-review/SKILL.md` to harden PR-review autonomy against flaky sub-agent result transport:
- reviewer spawn tasks now include a mandatory durable-output contract (`notes/review-reports/pr-<PR>-<agent-id>.md`),
- reviewers must always write a report artifact (including explicit "no findings" cases),
- synthesis workflow now includes a mandatory transport-failure fallback step (read artifact directly / re-run missing reviewer before proceeding).

**Rationale:** prevents silent loss of reviewer findings when completion announces arrive without full payloads, preserving deterministic review loops without depending on session-message transport alone.

### ✅ Carry-forward status sanitizer added to autonomy-audit snapshot scaffolding (2026-04-22)
Updated `scripts/notes/prepend-autonomy-audit-snapshot.py` so `--carry-forward-status` no longer blindly copies prior-cycle change-event language.
- Added change-event pattern detection (`fix applied this cycle`, `implemented`, `added`, `updated`).
- When detected, carry-forward now uses section-specific steady-state status templates instead of stale prior-cycle claims.
- Preserves normal carry-forward behavior for stable "no new blocker" status lines.

**Rationale:** daily snapshot scaffolding should accelerate status updates without accidentally copying yesterday’s "I implemented X this cycle" wording into today’s audit entry.

### ✅ Close-out cadence guard added to autonomy-audit wrapper (2026-04-21)
Updated `scripts/notes/close-autonomy-audit.sh` so daily close-out now runs `check-autonomy-audit-cadence.py` with `--require-current` against the selected audit date before rendering output.
- Added `--strict-cadence` to hard-fail on missing-day gaps when desired.
- Added `--skip-cadence-check` for explicit manual override/backfill flows.
- Preserved existing `NO_REPLY` behavior when finalize reports no meaningful delta.

**Rationale:** preflight already enforced cadence, but direct close-out calls could bypass that signal. This closes the workflow gap by keeping freshness/cadence checks on both entry and exit paths.

### ✅ Optional strict cadence enforcement added to autonomy-audit preflight (2026-04-20)
Updated `scripts/notes/run-autonomy-audit-preflight.sh` with a new `--strict-cadence` flag:
- keeps existing default behavior (cadence gaps are advisory warnings),
- allows strict runs to hard-fail immediately when `check-autonomy-audit-cadence.py` reports missing-day gaps,
- preserves deterministic preflight flow while giving scheduled runs a policy switch for stricter discipline.

**Rationale:** turns cadence handling from one-size-fits-all into an explicit policy choice, so autonomous runs can enforce daily-audit continuity when needed instead of relying on warning-only behavior.

### ✅ Duplicate-snapshot guard wired into autonomy-audit preflight (2026-04-19)
Updated `scripts/notes/run-autonomy-audit-preflight.sh` with a new step-zero duplicate check:
- runs `dedupe-autonomy-audit-snapshots.py` before consistency/cadence checks,
- fails fast when older duplicate snapshot dates exist,
- supports `--dedupe-apply` for one-command cleanup during preflight.

Also applied the cleanup to `notes/autonomy-gaps.md` this cycle (removed the stale duplicate `2026-03-15` block), then re-synced `> Updated:` metadata so pass counts match snapshot count.

**Rationale:** prevents silent drift in audit history where duplicate date blocks break pass-count metadata and make finalize/preflight checks flaky.

### ✅ Autonomy-audit freshness guard added to cadence checks (2026-04-18)
Updated `scripts/notes/check-autonomy-audit-cadence.py` with:
- `--require-current` to enforce latest-snapshot freshness against a reference date,
- `--reference-date YYYY-MM-DD` for deterministic backfill/manual runs.

Updated `scripts/notes/run-autonomy-audit-preflight.sh` to always run cadence checks with `--require-current`, and to pass the selected `--date` as `--reference-date` so preflight detects long audit outages instead of only comparing the latest two snapshot headings.

**Rationale:** closes a workflow-integrity gap where a long pause in daily audits could go unnoticed once historical snapshot spacing looked clean.

### ✅ Follow-up stale-finding guard fused into wrapper + skill docs (2026-03-20)
Expanded `scripts/review/run-followup-guards.sh` and refreshed `skills/lodestar-review/SKILL.md` so follow-up rounds now run three checks in one command:
- `track-findings.py sync-gh` delta sync,
- `check-pr-metadata-drift.py` artifact generation,
- `track-findings.py stale` artifact generation for unresolved critical/major findings.

Added wrapper controls: `--fail-on-stale`, `--stale-days`, `--skip-stale-check`, `--stale-use-created`, and default stale artifact path `notes/review-reports/pr-<PR>-stale-findings.md`.

**Rationale:** removes the last manual follow-up step where stale blockers could be missed during re-review, while keeping strict mode opt-in for teams that want stale findings to hard-block.

### ✅ Review-loop follow-up guard wrapper added (2026-03-20)
Created `scripts/review/run-followup-guards.sh` and wired usage into `skills/lodestar-review/SKILL.md`.
- runs `track-findings.py sync-gh` and `check-pr-metadata-drift.py` in one command,
- writes metadata artifact to `notes/review-reports/pr-<PR>-metadata-drift.md` by default,
- preserves exit-code semantics (`0` pass, `2` drift) and prints an explicit `gh pr edit` reminder command when drift is detected.

**Rationale:** closes the final follow-up ergonomics gap by replacing a fragile two-command manual sequence with a single repeatable guard command for re-review loops.

### ✅ Review-loop metadata drift guard wired into lodestar-review skill (2026-03-19)
Updated `skills/lodestar-review/SKILL.md` Finding Resolution Tracking workflow with a mandatory follow-up step:
- run `scripts/github/check-pr-metadata-drift.py --pr <PR>` before posting re-review,
- persist output to `notes/review-reports/pr-<PR>-metadata-drift.md`,
- treat exit code `2` as required metadata update (`gh pr edit`) before requesting re-review.

**Rationale:** closes the process gap between having the checker script and actually enforcing it in follow-up review loops.

### ✅ PR metadata drift guard script added (2026-03-19)
Created `scripts/github/check-pr-metadata-drift.py`:
- pulls live PR metadata + file list via `gh pr view --json title,body,changedFiles,files`,
- scans title/body for stale scope signals (path references not in current diff, narrow-scope wording vs broad file count),
- compares semver claims in metadata against semvers added/removed in the current patch,
- emits a concise markdown report and exits `2` on drift signals for cron/review-loop integration.

**Rationale:** catches title/body drift after follow-up commits before re-review, reducing mismatches like stale version claims or outdated scope descriptions.

### ✅ Spec architecture-consult timeout fallback policy codified (2026-03-18)
Updated `skills/dev-workflow/SKILL.md` Phase 1 with a required advisor fallback path:
- start architecture rounds with `gpt-advisor` `thinking: xhigh`,
- allow one tighter `xhigh` retry max on timeout/empty output,
- fallback to `thinking: high` instead of repeated `xhigh` loops,
- record round outcome metadata in `notes/<feature>/TRACKER.md`.

**Rationale:** converts an ad-hoc timeout workaround into a deterministic workflow rule, reducing stalled spec/design loops and preserving context across sessions.

### ✅ CI `logs-unavailable` fallback wiring added (2026-03-18)
Updated `scripts/ci/auto_fix_flaky.py` so `logs-unavailable` findings now automatically trigger `scripts/ci/fetch-run-logs.sh <run-id>` once per run, then:
- persist fallback metadata (`logs_fallback_status`, `logs_fallback_artifact`, `logs_fallback_command`, `logs_fallback_error`, `logs_fallback_reclassified`) into both detector findings and tracker entries,
- reuse fetched artifact logs for immediate re-classification when available.

**Rationale:** closes the handoff gap between detection and follow-up triage by attaching the exact log artifact path/command directly to the finding instead of leaving logs retrieval as a separate manual step.

### ✅ CI run-log fallback fetcher added (2026-03-17)
Created `scripts/ci/fetch-run-logs.sh`:
- fetches run logs by run ID with `gh run view --log-failed` first and `--log` fallback,
- supports explicit `--repo` and `--output` options,
- writes local artifacts under `tmp/ci-logs/` by default,
- prints deterministic output metadata (mode + line/byte counts) for tracker notes.

**Rationale:** closes the CI triage gap for `logs-unavailable` findings by making fallback log acquisition one command instead of ad-hoc/manual command hunting.

### ✅ Autonomy-gaps consistency guard added (2026-03-17)
Created `scripts/notes/check-autonomy-gaps-consistency.py`:
- parses `### Gaps` items and `## Improvements Implemented This Cycle` entries,
- flags contradictory status when the same gap appears both open and fixed,
- flags path-level contradictions when a script/doc path appears in both an open gap and an implemented improvement,
- exits with code `2` on contradictions for cron-friendly enforcement.

**Rationale:** prevents drift where autonomy-gap items are marked implemented but remain open elsewhere in the same file.

### ✅ Spec test-vector readiness gate added (2026-03-16)
Added `scripts/spec/check-test-vector-readiness.sh` and wired it into `skills/dev-workflow/SKILL.md`.
- validates local `~/consensus-specs/tests/` presence with a real sample file check,
- reports `tests/` freshness from git history,
- supports `--require-fresh` for fail-fast enforcement in pre-PR spec workflows.

**Rationale:** closes the last spec-vector gap where test vectors were available but freshness checks were manual/easy to skip.

### ✅ CI retry rolling-window escalation added (2026-03-15)
Updated `scripts/ci/auto_fix_flaky.py` to convert per-run retry telemetry into a sustained-health signal:
- persists bounded `scan_history` entries (`scanned_at`, `new_failures`, `llm_retry_telemetry`)
- computes `llm_retry_escalation` with configurable rolling-window thresholds for retry count, retry wait, and `Retry-After` frequency
- emits escalation data in detector JSON (`status=clean` and `status=failures_found`)
- stores escalation snapshot under `last_scan.llm_retry_escalation` when `--apply` is used

Also updated `scripts/ci/CRON_PROMPT.md` so cron summaries must explicitly warn when escalation is degraded.

**Rationale:** turns isolated retry counters into actionable trend detection so persistent API degradation is surfaced automatically instead of being noticed ad hoc.

### ✅ PR stale-finding cron wrapper added (2026-03-15)
Created `scripts/review/stale-findings-report.sh`:
- Scans all tracked PRs in findings directory for stale unresolved findings
- Supports `--days`, `--severity`, `--prs`, and `--output` options
- Exit code 2 when stale findings detected; writes timestamped markdown report to `notes/review-reports/`
- Reports include per-PR sections with stale finding details and resolution instructions
- Designed for cron usage: zero output (exit 0) when clean, actionable report when stale

**Rationale:** converts a manual "remember to check old findings" task into an automatable health signal that can feed into backlog or topic escalation.

### ✅ Devnet incident bundle script added (2026-03-15)
Created `scripts/debug/build-incident-bundle.sh` to produce one timestamped markdown artifact combining:
- environment metadata (host/tooling + repo branch/commit)
- `devnet-triage.sh` output (process, ports, logs, metrics, restart hints)
- optional multi-node timeline via `correlate-logs.sh` when peers + Grafana token are available
- structured incident-notes checklist for root-cause write-up

Also tightened `scripts/debug/devnet-triage.sh` process filtering so bundle generation commands are not misreported as node processes.

### ✅ One-command pre-PR compliance gate added (2026-03-14)
Created `scripts/spec/prepr-compliance-gate.sh` and wired usage into `skills/dev-workflow/SKILL.md`:
- accepts repeatable `--check "spec_query|ts_file|ts_symbol|report_out"` tuples
- runs `check-compliance.py` for each tuple and captures verdict/confidence
- runs `check-compliance-artifacts.sh` for tracker + PR body metadata enforcement
- emits one markdown pass/fail summary (stdout + optional `--summary-out`) including a reusable PR block snippet

**Rationale:** replaces a fragile multi-command sequence with one deterministic gate, so spec-compliance evidence is generated and validated consistently before PR/re-review.

### ✅ CI retry telemetry surfaced in detector output + tracker entries (2026-03-14)
Updated `scripts/ci/auto_fix_flaky.py` to expose retry/backoff health signals directly in the detector JSON and per-finding tracker line items:
- top-level summary now includes `llm_retry_count`, `llm_retry_wait_s`, and `llm_retry_after_seen`
- each finding + persisted tracker entry now carries per-classification retry telemetry (`llm_retry_*` fields)
- `--apply` runs now persist `last_scan.llm_retry_telemetry` in `memory/unstable-ci-tracker.json`

**Rationale:** makes degraded LLM/API health visible in concise cron summaries instead of hiding retries in stderr-only logs.

### ✅ Stale unresolved-finding escalation command added (2026-03-13)
Updated `scripts/review/track-findings.py` with `stale` command:
- lists open findings older than a threshold (default: `critical|major`, `updated >= 7d`)
- supports severity/age tuning (`--severity`, `--days`) and timestamp mode (`--use-created`)
- supports automation mode (`--fail-on-match`) for non-zero exit when stale findings exist
- updated `skills/lodestar-review/SKILL.md` workflow to run this in follow-up rounds

**Rationale:** converts stale-review escalation from a manual judgment call into a one-command query that can be scripted and monitored.

### ✅ Compliance artifact presence check script + workflow gate added (2026-03-13)
Created `scripts/spec/check-compliance-artifacts.sh` and wired it into `skills/dev-workflow/SKILL.md` Phase 5:
- verifies `notes/<feature>/TRACKER.md` has a populated `## Spec Compliance Artifacts` section
- verifies PR body has a populated `## Spec Compliance` section
- enforces either `spec-compliance-*.md` references **or** explicit `N/A` + reason
- enforces `Verdict:` when an artifact file is referenced

**Rationale:** this closes the final traceability gap between generating compliance artifacts and actually surfacing them in both tracker + PR metadata.

### ✅ Spec-compliance artifact traceability codified in dev-workflow (2026-03-12)
Updated `skills/dev-workflow/SKILL.md` so spec/protocol work now has explicit artifact linkage requirements:
- `TRACKER.md` template now includes **Spec Compliance Artifacts** section
- Phase 4 requires logging artifact path + verdict right after running compliance checks
- Phase 5 PR instructions require a dedicated **Spec Compliance** block with artifact path and verdict
- Added reusable snippet file: `notes/spec-compliance-pr-block.md`

**Rationale:** the compliance checker existed, but artifact references were easy to lose during PR prep. This closes the gap between "checker ran" and "evidence is attached to the review trail".

### ✅ Review-loop delta-sync step codified in lodestar-review skill (2026-03-12)
Updated `skills/lodestar-review/SKILL.md` finding-tracking workflow with a mandatory follow-up round step:
- run `python3 ~/.openclaw/workspace/scripts/review/track-findings.py sync-gh <PR> --repo ChainSafe/lodestar` whenever revisiting a PR with new review comments
- optional `--include-replies` guidance when reviewer discussion happens in threaded replies

**Rationale:** `sync-gh` existed, but without being part of the default loop it was easy to skip delta imports and miss re-verification handoffs.

### ✅ Dev-workflow spec-compliance gate codified (2026-03-11)
Updated `skills/dev-workflow/SKILL.md` Phase 4 with an explicit **Spec-compliance gate** for spec/protocol-facing changes:
- run `python3 scripts/spec/check-compliance.py --spec-query ... --ts-file ... --ts-symbol ... --output ...`
- if skipped, document reason in PR description

**Rationale:** the checker existed, but without an explicit workflow gate it was easy to omit during fast iterations.

### ✅ PR review false-positive guard added to lodestar-review SKILL.md
Added Step 1.5 between "Get the diff" and "Read persona prompts":
- Get `git diff --name-only origin/unstable...HEAD` before spawning reviewers
- Include file list in reviewer task prompt
- Mandatory post-review filter: discard findings for files not in the changed-file list

**Rationale:** PR #8993 — two reviewer sub-agents flagged `dataColumns.ts` and `gloas.ts`, which were not in the diff. I spent time verifying these before discovering they were noise. This is a repeating failure mode.

### ✅ Spec section extractor script implemented
Created `scripts/spec/extract-spec-section.sh`:
- supports query + `--spec-root`
- extracts primary pseudocode matches from specs markdown
- follows import chains for related symbol definitions
- emits markdown report to stdout or `--output`
- supports `rg` with `grep` fallback

### ✅ Devnet first-5-minutes triage script implemented
Created `scripts/debug/devnet-triage.sh`:
- process/uptime snapshot for matching local node processes
- listener/zombie check over configurable ports (default 9000/9596/5052)
- Loki error snapshot via Grafana datasource proxy (configurable window + query)
- Prometheus peer/attestation probes with fallback query candidates
- startup/restart hint count from logs
- markdown report output (`--output`) for easy sharing

### ✅ LLM fallback classification added to CI autofix detector
Updated `scripts/ci/auto_fix_flaky.py`:
- `classify_with_llm(job_name, logs)` using `gpt-4o-mini` + JSON response format
- 13-category taxonomy in system prompt; validated against known categories
- Graceful fallback if API key missing or call fails; `--no-llm` flag for offline
- `confidence` field on every finding: `high` (keyword), `medium` (LLM), `low` (no match)
- `fix_confidence` field: `root-cause` | `likely-root-cause` | `masking-risk` | `unknown`
- `fix_hint` field: LLM-generated short fix suggestion passed to cron agent
- `CRON_PROMPT.md` updated with guidance: flag masking-risk fixes for human review

### ✅ Fork implementation checklist template added
Created `notes/fork-implementation-checklist.md`:
- end-to-end fork coverage checklist (spec intake → types/state transition → fork choice → networking → API → storage)
- explicit test matrix (unit/integration/e2e/spec vectors)
- interop/devnet validation gates
- PR hygiene/review flow checks
- merge readiness/exit criteria summary block for PR descriptions

---

### ✅ Multi-node log correlator implemented (2026-03-09)
Created `scripts/debug/correlate-logs.sh`:
- accepts multiple node names + `--from/--to` range
- runs per-node Loki queries in parallel and merges results into a single timestamp-sorted timeline
- prefixes each line with node name and marks consensus-relevant lines (`fork_choice`, `attestation`, `proposal`, `head_block`, `finalized`)
- supports `--highlights-only`, custom query template (`{{NODE}}` placeholder), and markdown file output

### ✅ Review finding resolution tracker implemented (2026-03-08)
Created `scripts/review/track-findings.py`:
- `add <pr>` — store a finding (file, line, severity, reviewer, body)
- `list <pr> [--open-only]` — show findings sorted by severity
- `resolve <pr> <id> [--commit <sha>]` — mark as addressed/acknowledged/wontfix
- `check <pr> --changed-files <...>` — given new commit's file list, flag findings on changed files as "needs verification" vs. still-untouched
- `dump <pr>` — markdown summary for GitHub comment copy-paste
- `import <pr> --markdown <file>` — parse free-form reviewer output into structured findings
- `dedup <pr>` — group by file+line proximity (±5 lines), showing multi-reviewer overlap

Updated `lodestar-review/SKILL.md` with "Finding Resolution Tracking" section explaining the workflow.

**Rationale:** When PR authors push follow-up commits, I currently re-read my entire review and the new diff manually (10-15 min per follow-up). `check --changed-files` reduces this to <1 min: it immediately shows which of my findings are on changed files (go verify) vs. still-untouched (still open).

### ✅ CI auto-fix PRs now labeled `auto-fix` (2026-03-08)
Updated `CRON_PROMPT.md` Step 4 `gh pr create` command to include `--label "auto-fix"`, with a comment showing how to create the label if it doesn't exist yet. Makes auto-fix PRs instantly filterable in the ChainSafe/lodestar PR queue.

### ✅ Dev-workflow spec-vector gate added (2026-03-09)
Updated `skills/dev-workflow/SKILL.md` Phase 4 (Quality Gate) with an explicit **Spec-vector gate**:
- run `pnpm test:spec` when available before PR on spec/protocol-facing changes
- if unavailable/skipped, document reason in PR body

**Rationale:** test-vector checks were a known recurring omission risk in spec work. Making it a codified gate reduces regressions from "looks right" implementations that diverge from official vectors.

### ✅ Debug session template created
Created `notes/debug-session-template.md` (2026-03-07):
- Structured header (date, topic, linked PR, environment, time budget)
- Hypothesis-first section (list before looking at evidence)
- Timestamped evidence log with bash command blocks
- "Ruled out" table to track eliminated hypotheses
- Working theory + root cause + fix sections
- Lessons learned → feeds back into skill updates
- Quick-reference bash snippets for common starting points

### ✅ GitHub review-comment ingestion added to finding tracker (2026-03-10)
Updated `scripts/review/track-findings.py` with `import-gh` command:
- Fetches PR review comments via `gh api repos/<owner>/<repo>/pulls/<pr>/comments`
- Imports comments as structured findings with source metadata (`kind: github-review-comment`, comment id/url)
- Skips already-imported comments using source-id dedup
- Optional `--include-replies` to include in-thread reply comments

### ✅ Finding-tracker GitHub delta-sync added (2026-03-11)
Updated `scripts/review/track-findings.py` with `sync-gh` command:
- Checkpointed delta sync via persisted state (`data.sync.github[repo].last_comment_id`)
- Imports only new comments (`id > checkpoint`), with optional `--since-comment-id` override
- Optional `--include-replies` and configurable `--match-window-lines`
- Adds re-verification metadata to matching existing findings (`needs_reverify`, `reverify.events`)
- Supports `--dry-run` for safe validation

### ✅ CI LLM retry/backoff + fixability wiring in autofix detector (2026-03-10)
Updated `scripts/ci/auto_fix_flaky.py`:
- Added bounded retry behavior for OpenAI calls in `_openai_completion()`
- Added retryability detection for 429/5xx + transient errors
- Added `Retry-After` header/message parsing and exponential backoff fallback
- Fixed LLM fixability propagation: `classify_failure()` now returns `llm_fixable`, and `scan()` passes it to `is_fixable()`
- Persisted `llm_fixable` into findings/tracker entries for auditability

### ✅ Devnet incident-bundle preflight guard (2026-06-04)
Updated `scripts/debug/build-incident-bundle.sh` and `skills/local-mainnet-debug/SKILL.md`:
- Added `--check-only` to validate node/peer inputs, helper script presence, and output-path writability without querying Grafana or writing a bundle.
- Added `--require-grafana` to fail early when `GRAFANA_TOKEN`, `curl`, or `jq` are missing instead of silently producing a partial telemetry bundle.
- Documented the preflight command in the local mainnet debugging skill so longer devnet debugging runs can fail fast on missing observability prerequisites.
- Verified with `bash -n`, optional preflight success, and missing-token failure under `env -u GRAFANA_TOKEN`.

---

## Next Audit Priorities (next daily cycles)

All previously listed priority items in this section are complete as of **2026-04-18**. To avoid stale reminder churn:

1. Only add a new item here when the **latest daily audit snapshot** introduces a still-open blocker or concrete follow-up.
2. If the latest snapshot is fully green, leave this section empty of filler work and use `BACKLOG.md` for unrelated concrete tasks.
3. When repopulating the list, prefer one specific automation gap that is **not already marked `✅ done` elsewhere in this file**.
4. If a reminder fires while this section has no live items, the correct outcome is routine silence / `NO_REPLY`.

Helper: `python3 scripts/notes/check-next-audit-priorities.py --json` returns whether this section contains live items or only the default empty-state guidance. For shell/cron guards, use `python3 scripts/notes/check-next-audit-priorities.py --quiet --fail-if-live` (`exit 0` = no live items, `exit 3` = live items present).
