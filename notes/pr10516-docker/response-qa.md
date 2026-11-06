# PR #10516 follow-up response QA

Reviewer: review-bugs
Reviewed commit: 86ec5cb64a582f4a5e5363283149c2aaf32763d4

## Scope and verdict

Bounded read-only review of `c3338e98c9ce3d30c861fe42fb0fb8eab965cd7f` and `86ec5cb64a582f4a5e5363283149c2aaf32763d4`, plus the replies to Nazar's `discussion_r4480449399` and `issuecomment-6658059092`. This is not a full PR review or merge approval.

Changed-file scope: `Dockerfile`, `Dockerfile.dev`, `AGENTS.md`, `CONTRIBUTING.md`, `docs/pages/faqs.md`, `lodestar`, `docker-compose.yml`, `.github/workflows/binaries.yml`. Verified the local worktree has the exact reviewed HEAD and is clean.

**No functional bugs found.** Both proposed replies are suitable for posting, with the small precision refinement below. The missing-Corepack P1 is addressed within the verified linux/amd64 build scope.

## Evidence reconciliation

- Both Dockerfiles explicitly install pinned `corepack@0.36.0` before enabling it. The production log shows successful activation of the packageManager-pinned `pnpm@11.0.0`, a successful build and the exact HEAD embedded in version metadata. Production build result: exit 0 after 258 seconds.
- The original dev build successfully installed/enabled Corepack, then failed while fetching a Zig dependency with `NameServerFailure`. The host-network resume successfully completed the exact-head image. The build logs' final image IDs match `image-smoke-results.json`.
- All six saved image smoke checks passed: version, native-addon import and Node/NODE_OPTIONS for each image. Both report version commit `86ec5cb`, Node `v26.13.0`, and `--max-old-space-size=8192 --max-semi-space-size=64`. These are linux/amd64 smoke checks, not sustained beacon-node operation or arm64 verification.
- The semi-space flag is present beside the existing old-space flag in both Docker images, the shell launcher, compose configuration and standalone-binary packaging command. The latter three were inspected, not independently built/run in this QA.
- `heap-limit-results.json` supports the precise reported configured-limit comparison: at old-space 8192 MiB, Node 26.13.0 changes from 8288 to 8384 MiB with the flag; Node 24.22.2 reports 8384 MiB in both cases. The reply correctly distinguishes this from peak dynamic `new_space` capacity.
- `heap-probe-results.json` does not reproduce Nazar's 128 MiB peak table, and the proposed reply explicitly acknowledges that limitation. It makes no independent runtime GC or benchmark-causality claim.
- Exact-head `ci-evidence.json` reports Benchmark failure at run `42027589761`; the workflow and check entries represent the same failing run. The replies do not claim CI is green. A feat2 redeploy and a fresh `processEffectiveBalanceUpdates` run remain outside the completed evidence.

## Reply precision refinement

In `reply-semispace-draft.md`, replace “The production image exposes it in `NODE_OPTIONS` and starts successfully on Node 26.13.0.” with:

> The production image exposes it in `NODE_OPTIONS`, and `--version` succeeds on Node 26.13.0.

This describes exactly the executed startup smoke check without implying a beacon-node/GC run. No substantive changes are needed to the Corepack reply.

## Actions

Inspected existing source, diff, comments, logs, results and drafts only. No source edits, builds or test reruns, GitHub writes, config changes, deployments or process changes were performed. This report is the only artifact written by this reviewer.
