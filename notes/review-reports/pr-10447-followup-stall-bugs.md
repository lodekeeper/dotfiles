# PR #10447 follow-up: functional bug / response QA

## Commit affinity and scope

- Locally verified head: `9aec7dcad139b61f84eb4bc04a337081407f00f7`, `fix: avoid legacy column scans during archiving`, authored/committed by `lodekeeper <lodekeeper@users.noreply.github.com>` at `2026-10-20 20:04:03 +0000`.
- Worktree: `/home/openclaw/lodestar-archive-column-compaction`; clean before and after review. Reviewed exactly `git diff HEAD^..HEAD`, five allowlisted changed files.
- Parent-provided GitHub metadata: merged by Nico at `2026-10-20T21:36:17Z`, merge SHA `4bacee3dacfe04629dc167947bad12fa95ae96f1`. This child did not independently query GitHub metadata.
- Read-only source review under `review-bugs.md`; no source changes, tests, host actions, deployment or external posting. Only this report and the review subtask status in BACKLOG were written.

## Verdict

**No functional bugs found.** The change remains sound independently of whether tombstones explain Adrian's live stall.

1. Existing startup behavior already deletes the legacy hot bucket before beacon initialization proceeds: `beacon.ts:128-132`, awaited at `node/nodejs.ts:215-219`. History confirms #10223 (`cea8fba405a681a53cb59742e5b51e80ee58c153`) introduced that deletion; #10447 does not introduce a new legacy-data-loss policy.
2. New writes already go directly to flat files (`dataColumnStore.ts:78-80`; block persistence calls `dataColumns.putManyBinary`). Canonical legacy hot-to-cold migration therefore performs obsolete work after the hot bucket was cleared. Removing its whole helper/call is correct, not dependent on the cost of a particular seek.
3. Legacy cold fallback is untouched (`dataColumnStore.ts:50-53,68-74`), as are flat-column reads/writes. Existing archive data remains readable. Noncanonical cleanup still calls legacy-hot deletion (`archiveBlocks.ts:186-195`, `dataColumnStore.ts:82-85`); retention pruning still examines legacy-cold keys (`dataColumnStore.ts:87-92`). Do not say the PR removes all legacy scans.
4. Added compaction follows awaited full-bucket deletion and is awaited unconditionally, even when no live keys remain (`beacon.ts:132-137`). Encoded bounds target hot bucket 57 to the next bucket prefix 58. Controller implementation already existed (`level.ts:193-194`); the shared interface addition exposes that real capability, not an unimplemented API.
5. Changed tests check canonical Fulu/Gloas no-legacy-call behavior (including archived boundary), startup delete-before-compact ordering, prior-deleted bucket compaction, awaited completion and actual flat-column serving. This review inspected but did not re-run them.

## Live-stall claims

- Failed manual hot-only and hot+cold compaction weaken the original tombstone diagnosis; they do not establish that the now-obsolete canonical scan is necessary.
- The patch **bypasses the canonical migration scan**; it is **not yet verified to cure the live stall**. Other async operations/legacy DB paths remain. A log boundary is not an actual native stack.
- The supplied 90.37%-idle main-thread profile is compatible with native/async work but does not identify its cause, prove deadlock, or prove this PR fixes the live process. Actual live image/version and native busy-worker capture remain needed.
- Existing local tombstone reproduction demonstrates a reproducible performance problem in a test database, not the cause of this host's failure after compaction.

## Proposed response QA

The parent's response is safe. Keep “canonical” on the bypass claim; do not shorten it to “the fixed build avoids legacy DB scans.” Prefer “removes unnecessary per-block work” to an unqualified live-performance benefit. No need to re-state the now-weakened tombstone mechanism as a proven diagnosis.

Suggested concise wording:

> Yes—#10447 still makes sense. The main part removes the obsolete canonical hot-to-cold column scans; #10223 already clears that hot bucket on startup, new columns use flat files, and legacy cold reads remain. The failed manual compaction weakens my tombstone diagnosis, not the rationale for removing that work. It bypasses this canonical scan, but we have not verified it fixes Adrian's live stall.
