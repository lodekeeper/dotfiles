# EL implementation status — REST-SSZ Engine API (execution-apis#793)

**Date:** 2026-09-27 · **Asked by:** nflaig (Discord #ssz-engine-api)
**Question:** which ELs already implement the SSZ engine per the latest execution-apis spec?

> Supersedes the 2026-03-05 `EL-TARGET-MATRIX` note, which was against the since-closed
> #764 draft (SSZ-over-REST at `/engine/v1/...` legacy routes). The spec has since moved to #793.

## The spec: ethereum/execution-apis#793
- **"engine: add Rest-SSZ spec"**, author **MariusVanDerWijden (Geth)**.
- **MERGED to `main` on 2026-09-02**; still iterating on main ("keep iterating on it on main if necessary").
- Full refactor JSON-RPC → **REST + SSZ**:
  - `engine_newPayloadV*` → `POST /{fork}/payloads`; `engine_forkchoiceUpdatedV*` → `POST /{fork}/forkchoice`;
    `engine_getPayloadV*` → `GET /{fork}/payloads/{id}`; bodies-by-hash → `POST /{fork}/bodies/hash`;
    bodies-by-range → `GET /{fork}/bodies?from=&count=`; getBlobs → `POST /blobs/v{1..4}`;
    clientVersion → `GET /identity` + `X-Engine-Client-Version`; capabilities → `GET /capabilities`;
    exchangeTransitionConfiguration → removed.
  - Fork moved **into the `Eth-Execution-Version` header, out of the URL path** (commit `d39e9a27`);
    base path renumbered `/engine/v2/` → `/engine/v1/`.
  - Plan (ACDC #2132, 2026-06-26): JSON and SSZ **coexist**, SSZ becomes **compulsory past a future fork**,
    then JSON engine RPC retired; clients can ship behind a flag as fast as they want.
- Spec files: `src/engine/refactor.md`, `src/engine/refactor-ssz.md`.
- `MAX_BAL_BYTES` / `MAX_BYTES_PER_EXECUTION_REQUEST` still placeholders.

## EL status (verified via `gh` on 2026-09-27)

### Merged to default branch
- **Nethermind — furthest along.** Full REST+SSZ surface merged: #11887 (merged 2026-06-14),
  then kept in sync: #11998, #12193 (fork→`Eth-Execution-Version` header), #13023 (merged 2026-08-30),
  #13050 (MaxBlobsRequest in GetBlobs). LukaszRozmej is a primary implementer-reviewer of the spec.
- **Reth — partial, merged.** SSZ payload-bodies endpoints #26394 (merged 2026-09-05);
  REST-SSZ wire types landed in alloy (alloy-rs/alloy#4038). Earlier experimental
  `/new-payload-with-witness` #24617 was closed. Building up incrementally.

### Implemented on open / draft branches
- **Erigon — draft, interop-proven.** #21729 (open DRAFT, upd 2026-08-05) "switch Engine API SSZ to #793";
  tracking issue #21600; #23045 adds Amsterdam blob/custody. **Prysm interop-tested against #21729** (syjn99, Jun 2026).
  One of the first three implementations (per yperbasis).
- **ethrex (lambdaclass) — open, active.** #6770 "engine REST/SSZ API" (upd 2026-09-22); #6741 witness endpoint.
  One of the first three implementations.
- **Geth — draft, stalled.** #35171 (open DRAFT), created 2026-06-14 by the spec author, **not touched since 2026-06-29.**
- **Nimbus-eth1 (status-im) — in progress.** #4653 "EL: engine rest ssz api" (open, upd 2026-09-24).

### Not started
- **Besu** — no PR/issue referencing REST-SSZ engine or #793 (confirmed via 3 negative searches).
- **EthereumJS** — not present in #793 cross-references.

### Maturity
- No EL ships this in a **stable release** — all behind flags / on branches / draft, against a spec still moving on main.
- Interop demonstrated: **Erigon ↔ Prysm** (Jun 2026).

## Relevance to Lodestar
- #10155 (nazarhussain, CL side) PR body says *"No EL serves #793 yet, so there is no interop coverage."*
  **Partly stale** — Nethermind has #793 merged to `master` (aligned Aug 30), so interop coverage IS possible.
  Best live interop target on trunk: **Nethermind** (merged + current). **Erigon caveat (corrected 2026-09-27):**
  its `main` has only an *older* pre-#793 SSZ-REST (#21203, merged May 15); the switch to current #793 (#21729)
  is an open DRAFT untouched since Aug 5, and the Jun Erigon↔Prysm interop was against that draft, not trunk.
  So Erigon is NOT a ready trunk-level target for the current spec yet — #21729 must land + be refreshed first.
- CL peers also in flight: Prysm (#16901/#17046), Lighthouse (#9652), Nimbus-eth2 (#8895/#9048), Lodestar (#10155).
