# Independent verification of the fork-choice dump gist

Reviewed 2026-10-10. Scope: existing `fork-choice-dump.md` and supporting research, not a new investigation or implementation. No GitHub/network mutations; no edits to the draft or tracking files.

## Verdict

The research is useful and the two principal goals—diagnostic export and restart recovery—are well supported. Correct the claims and artifact-fidelity gaps below before calling the published gist final. No credential, private hostname, key, or internal endpoint disclosure was found in the main draft. The supporting `chat-findings.md` contains private operational/transcript context and must not be published unchanged.

## Prioritized corrections

### P1 — Do not say that Lighthouse has no decoder or that no client has a loader

Lighthouse explicitly has a zstd/SSZ decoder, `PersistedForkChoiceV29::from_bytes`, and a persistence loader, `BeaconChain::load_fork_choice` → `ForkChoice::from_persisted`. Its proto-array types also derive deserialization. The defensible missing capability is a *supported external diagnostic-dump importer / standalone full-state repro command*, not decoding or internal persistence loading. The inspected `lcli parse-ssz` command does not list fork-choice containers; that proves a CLI gap, not a library-decoder gap.

Suggested wording: “At the inspected commits, I did not find a supported CLI/test workflow that imports the exported debug-API response as a full fork-choice state. Lighthouse already decodes and loads its internal persisted SSZ snapshot.” Change the comparison row to “External diagnostic dump importer found” and avoid “Nobody has one.”

Evidence:

- [Lighthouse persistence codec](https://github.com/sigp/lighthouse/blob/f31adcef15d7efea9433f55671027877959f139e/beacon_node/beacon_chain/src/persisted_fork_choice.rs#L58).
- [Lighthouse internal loader](https://github.com/sigp/lighthouse/blob/f31adcef15d7efea9433f55671027877959f139e/beacon_node/beacon_chain/src/beacon_chain.rs#L684).
- [Lighthouse CLI decoder types](https://github.com/sigp/lighthouse/blob/f31adcef15d7efea9433f55671027877959f139e/lcli/src/parse_ssz.rs#L66).

### P1 — The strawman is not yet sufficient for its full-fidelity promise

The container omits balance dependencies, queued attestations and optional FCR state. `ForkChoiceStore.justified` and `unrealizedJustified` each carry balances. Epoch-boundary `onTick` specifically reads `unrealizedJustified.balances`, so retaining only the currently justified state's vector is not enough when those checkpoints differ. The full diagnostic profile should retain both vectors or the exact states from which both can be reconstructed. The “don't persist balances” suggestion is conditional on retaining those states, not an unconditional optimization.

Also distinguish these two loader modes:

1. **Diagnostic:** load at captured time/config and reproduce a clearly defined result (`updateHead`, proposer-head/`should_build_on_full` checks), retaining current-slot queued votes and FCR context where applicable.
2. **Restart:** validate a coherent local DB point, advance time to wall clock, explicitly reset ephemeral boost/current-slot data if desired. The resulting head need not equal the captured-time head because the slot, boost and checkpoint pull-up have changed.

If normalized weights are recomputed from `voteNextIndices`, they need not equal *raw stored weights before the next updateHead*. Save observed/raw scores separately in the diagnostic profile or document that the artifact captures a normalized computation boundary.

Evidence:

- [Lodestar balances and queue](https://github.com/ChainSafe/lodestar/blob/b726a05a4df34068d21b254bf5c590ea75afd169/packages/fork-choice/src/forkChoice/forkChoice.ts#L127).
- [Store balance dependencies and FCR state](https://github.com/ChainSafe/lodestar/blob/b726a05a4df34068d21b254bf5c590ea75afd169/packages/fork-choice/src/forkChoice/store.ts#L44).
- [Epoch pull-up reads unrealized balances](https://github.com/ChainSafe/lodestar/blob/b726a05a4df34068d21b254bf5c590ea75afd169/packages/fork-choice/src/forkChoice/forkChoice.ts#L2263).

### P1 — Crash-tail orphan reconciliation is a separate requirement

An older periodic snapshot can be behind already-written hot blocks/envelopes. Orphans imported after that snapshot are still absent from restored fork choice, even when the snapshot itself is perfectly valid. Finalized fallback plus an fcU guard handles head regression but does not meet G2's no-stranded-orphans goal. Document an explicit reconciliation strategy or mark this goal incomplete: replay/index hot-DB tail records, durable orphan tracking, or finalization-time GC that discovers records independently of the restored DAG. Coherence is the core requirement; zero loss of every unpersisted vote is not.

The DB-membership rule must be variant-aware: only a FULL node requires an associated envelope. PENDING/EMPTY variants do not. In addition, restart validation applies to the restart profile; a forensic export should still be possible when live state is inconsistent, with its validation failures recorded rather than the capture being refused.

### P2 — Scope absence and persistence claims

- Six targeted source searches found no named `-38006` / `TooDeepReorg` / max-reorg-depth special case in the inspected execution-interface paths. This supports “no dedicated handling found at these commits,” not “No CL client handles it today.” Generic RPC-error handling exists and is handling of a different kind.
- “Lodestar persists nothing fork-choice related” and “Prysm/Nimbus/Grandine persist nothing” are too literal: the same draft describes checkpoints, blocks, head hints and/or envelopes they persist. Prefer “no restorable fork-choice snapshot/latest-message vectors” for clients that rebuild from those inputs.
- “The error is harmless” is stronger than the evidence. The confirmed claim is that this JSON-RPC refusal does not itself invoke Lodestar's fork-choice invalidation path. Temporary engine-state transitions and useful-head-update delays still exist.

### P2 — Correct import-cadence wording and identify the preset

- The pinned `importBlock.ts` sends fcU only when the head root **or finalized epoch changes**, import fcU is enabled, and proposer override does not suppress it. In a canonical sequential replay this is normally every head-advancing block; it is not every imported block generally. [Source](https://github.com/ChainSafe/lodestar/blob/b726a05a4df34068d21b254bf5c590ea75afd169/packages/beacon-node/src/chain/blocks/importBlock.ts#L452).
- PTC bitvectors are `PTC_SIZE` wide: **512 mainnet, 2 minimal**, as the Lodestar proto-array comments state. Hardcoded `Bitvector[512]` needs a mainnet-only label or preset-aware encoding/config verification. [Source](https://github.com/ChainSafe/lodestar/blob/b726a05a4df34068d21b254bf5c590ea75afd169/packages/fork-choice/src/protoArray/protoArray.ts#L101).
- Genesis validators root alone is not enough to recreate all fork-choice behavior: include/pin network preset, fork schedule/config digest, implementation/schema version and relevant enabled options, with rejection of mismatch on production restart. Clearly label references to external block/state dependencies rather than calling an incomplete standalone file “self-contained.”

### P2 — Make historical evidence directly reviewable

The chat evidence currently uses channel/date labels with only a repository-root link. Add direct pinned archive-file permalinks for the important G1–G8 examples; link issue/PR lists where possible. The parent found additional live provider-search history from internal ChainSafe conversations that the previous execution's transcript search missed. Preserve those citations locally; publish their generalized requirements, not internal excerpts or a claim that only public R&D history existed.

Shorten/paraphrase long issue quotes: G1 excerpts from #4000 and #8592 exceed 25 words apiece. Public findings do not need extensive verbatim quoting to preserve their meaning.

## Suggested acceptance checks

These are implementation success criteria, not claims that code/tests already exist:

- Same-slot diagnostic round trip preserves all branch/variant identities and reproduces normalized head plus PTC quorum/`should_build_on_full` decisions; repeat with queued current-slot votes, equivocations and FCR enabled.
- Restart at a later slot follows the documented tick/boost-reset semantics, across an epoch boundary with **different justified/unrealized balance vectors**.
- Clean shutdown flushes dependent hot writes before committing an atomic snapshot; a write failure or interrupted/truncated file leaves the previous usable generation or documented finalized fallback.
- Crash after snapshot but before shutdown recovers a coherent snapshot/DB point; hot-tail blocks/envelopes—including orphan records—are eventually reconciled and reclaimed without deleting required data.
- Missing FULL envelope, missing block, schema/config/genesis mismatch, invalid indices and stale finalization yield an explicit controlled fallback; debug inspection remains available.
- Long non-finality beyond the current regeneration horizon still restores a usable head state or explicitly documents the unsupported bound, rather than succeeding at fork choice and failing later in regen.
- Capture labels time/head/config and obtains a coherent cut; bounded async writing/compression and retention avoid blocking import or unbounded historical-file growth. Record measured sizes/latencies rather than asserting unmeasured performance.

## Checks performed

- Read existing draft and all supporting research notes; no wholesale research redo.
- Verified the Lighthouse SSZ decoder/internal loader, CLI accepted SSZ types, and proto-array persistence container at `f31adcef15d7efea9433f55671027877959f139e`.
- Verified Lodestar queue/latest-message representation, balances, unrealized balance pull-up, FCR store fields, index-based vote pruning, PTC preset comment and import-fcU gating at `b726a05a4df34068d21b254bf5c590ea75afd169`.
- Searched the pinned six execution-interface trees for named deep-reorg error handling; no matches. This is source-search evidence, not an exhaustive runtime proof or an all-time absence claim.
- Checked the main draft for private identifiers/secrets; no privacy blocker found. Do not publish the raw companion investigation notes unchanged.

## Final targeted pass after revision

Reviewed the revised main draft, including its fidelity profiles, 12-scenario acceptance matrix, balance/state dependencies, crash-tail reconciliation, trust/freshness checks, historical retention and pinned primary-source links. **The substantive P1 findings are addressed. No blocking privacy issue remains. Approve publication after these four small wording cleanups, sent to the parent:**

- TL;DR and Prysm/Nimbus/Grandine headings still say “persist nothing”/“nothing persisted”: change to “no fork-choice/latest-message snapshot,” since the text correctly documents durable blocks/checkpoints/hints.
- R7 still says “that nobody has today”: scope to the inspected diagnostic endpoints and their lack of the complete proposed capture.
- The fcU-guard paragraph still says crashes *will* restart from finalized: missing/rejected snapshots *can* require finalized fallback; an accepted periodic snapshot can survive a crash.
- Teku's inputs-and-rebuild option says “no drift”: say it avoids persisting an independent proto-array snapshot, not that every input can never lag.

No further redesign, research, implementation or runtime-test work is required for this documentation task. The proposed design and acceptance criteria are clearly labeled as unimplemented/unverified.
