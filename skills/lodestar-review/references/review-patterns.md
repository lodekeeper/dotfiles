# Lodestar Review Patterns

Patterns mined from ~2000 review comments across ~1000 PRs. Use this to understand what Lodestar maintainers actually flag.

## Top Reviewers & Their Focus Areas

### nflaig (Lead maintainer — 576 comments)
**Primary concerns:**
- **Spec alignment:** "please check the spec reference", "check against CL spec and implement as per spec". Expects spec section citations for consensus-critical code.
- **Forward-compatible naming:** "naming that makes sense 2-3 forks from now". Avoid current fork codenames in identifiers (e.g., "epbs" in variable names). Use abstract names.
- **Type safety:** Specific generic type suggestions (`BeaconBlockBody<ForkPostGloas>`), removing type casts, narrowing types properly.
- **Inline suggestions:** Heavy use of GitHub suggestion blocks for quick fixes.
- **Cross-referencing:** Links to related PRs, issues, spec sections, and existing code patterns.
- **Pragmatism:** "keep it simple for now", "I rather keep the todos" — accepts incomplete implementations with TODOs for devnet milestones.
- **Comment-code consistency:** "this does the opposite of what the comment says" — catches stale comments.
- **CI/workflow:** Limits concurrency on workflows, correct trigger patterns (`push: unstable/stable only`, `pull_request`, `workflow_dispatch`).
- **Backward compat:** "we had users run with X, we need to keep that in mind" — remembers edge case configurations.
- **Dashboard awareness:** "these metrics are still used in dashboards, we should update those too."

### twoeths (Fork choice/state expert — 157 comments)
**Primary concerns:**
- **ProtoBlock variant correctness:** EMPTY/FULL/PENDING status tracking. "we want the correct parent variant", "ambiguous function when we have different branches with same root."
- **State cache management:** "need payloadPresent as part of key?", state access patterns.
- **Function signatures:** Specific parameter requirements for post-Gloas functions.
- **Getter vs function:** "use getters for mandatory properties, functions for one-time use."

### wemeetagain (Architecture — 80 comments)
**Primary concerns:**
- **Metrics:** "add a metric here", "tracking all interactions with EL via metrics."
- **Code simplification:** "can be simplified to just use sszTypesFor?"
- **Pattern suggestions:** Fork-aware if/else ordering, suggestion blocks.
- **Future TODOs:** "add a todo here for supporting non-self-builder."

### ensi321 (Correctness — 74 comments)
**Primary concerns:**
- **Edge cases:** "a single validator can only be chosen to attest for exactly one slot per epoch" — concrete validator lifecycle knowledge.
- **Spec divergence:** "definition here are not matching the ones in the spec."
- **Test correctness:** "I think this test is wrong" — verifies test logic matches production code.
- **Scope enforcement:** "Out of scope of this PR" — keeps PRs focused.

## Most Reviewed Packages (by comment count)
1. beacon-node (883) — core logic, networking, sync, API
2. state-transition (183) — spec implementation, consensus functions
3. fork-choice (110) — proto-array, fork choice rules
4. cli (72) — command-line interface
5. types (53) — SSZ type definitions
6. api (34) — REST API routes and codecs
7. validator (33) — validator client
8. reqresp (32) — libp2p request/response

## Common Review Themes (by frequency)

### 1. Spec References (very frequent)
Reviewers expect spec citations for consensus-critical logic. Not just "per spec" but exact links to spec sections.

### 2. Naming Conventions (frequent)
- Don't name things after the current fork (`epbs`, `gloas`) — use abstract names
- File names: no `Utils` suffix when file is in utils folder
- Variables/types: descriptive, forward-compatible

### 3. Type Safety (frequent)
- Avoid `any`, remove unnecessary type casts
- Use specific fork generics (`ForkPostGloas`, `ForkPostElectra`)
- Function signatures should be explicit

### 4. Comment Accuracy (moderate)
- Stale comments that contradict code get flagged
- Comments must match current behavior, not planned behavior

### 5. Metrics Coverage (moderate)
- New functionality should include relevant Prometheus metrics
- EL interactions should be tracked
- Check if existing dashboard definitions need updating

### 6. Test Quality (moderate)
- Tests should verify the right thing (test code reviewed carefully)
- Add assertion messages in loops
- Consider edge cases in test scenarios

### 7. CI/Workflow Hygiene (occasional)
- Limit concurrency to 1 for resource-heavy workflows
- Correct trigger patterns (not `push` to all branches)
- Allow manual dispatch

### 8. Backward Compatibility (occasional)
- Consider existing user configurations
- Don't break flags, config options, or metrics that users rely on
- Dashboard compatibility

## My Own Learnings (Lodekeeper)

### Code Writing
- **Fork choice `getHead()` caching:** After calling `validateLatestHash` or any proto-array mutation, must call `recomputeForkChoiceHead()` to refresh the cached head. Missed this in EIP-8025 work.
- **`push()` vs `pushWait()` semantics:** `push()` resolves when the job *finishes* (not when enqueued). Using `await pushWait()` in range sync means "wait for DB write to complete" — much stronger throttling than intended.
- **Fire-and-forget needs `.catch()`:** `void someAsyncFunction()` without `.catch()` creates unhandled rejection. Use `void someAsyncFunction().catch(logError)`.
- **Always run `pnpm lint` before pushing.** Biome formatting issues waste CI round-trips.

### Reviewing
- **Address ALL review comments** — including bot reviewers (Gemini, Codex). Nico expects every comment addressed within one heartbeat cycle.
- **Reply in-thread** — use `gh api -X POST repos/{owner}/{repo}/pulls/{pr_number}/comments -f body="..." -F in_reply_to={comment_id}`, not `gh pr comment`.
- **Read ALL comments before dismissing notifications** — new comments on already-read threads don't create new unread notifications.
- **Don't force push after review starts** — use incremental commits so reviewers can track changes.
- **Use merge, not rebase** for upstream changes — `git merge unstable`, not rebase + force-push.
