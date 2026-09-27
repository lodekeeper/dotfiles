# SSZ (REST + SSZ) Engine API — status snapshot

*Compiled 2026-09-27. Sources: `ethereum/execution-apis`, `ethereum/pm`, individual client repos, and the [Ethereum R&D Discord archive](https://github.com/ethereum/eth-rnd-archive). All PR/issue states verified via the GitHub API on 2026-09-27.*

## TL;DR

- The engine API is being refactored off JSON-RPC onto **REST + SSZ**. The base spec, [execution-apis#793](https://github.com/ethereum/execution-apis/pull/793), **merged to `main` on 2026-09-02** and has been refined incrementally since — no fundamental churn.
- **Nethermind** is the only execution client with the current spec **merged to its trunk** and kept in sync. **Erigon**'s trunk carries an *older*, pre-#793 version; its switch to the current spec is a stale draft. Every other client is draft / partial / not started.
- **No client ships this in a stable release.** Under the agreed plan, JSON and SSZ coexist; SSZ becomes compulsory only "past a future fork" (Amsterdam onward), after which JSON engine RPC is retired. Clients can ship behind a flag as fast as they like.
- The dedicated **"SSZ Engine API" breakout-call series has wound down** (4 calls, Jun–Aug 2026). Further work now happens through PRs and ad-hoc calls rather than a standing series.

## The spec — execution-apis#793

- **"engine: add Rest-SSZ spec"**, authored by **MariusVanDerWijden (Geth)**. **Merged to `main` 2026-09-02**, iterating on main.
- Full refactor of the transport, JSON-RPC → **REST + SSZ**:

| Old (JSON-RPC) | New (REST) |
|---|---|
| `engine_newPayloadV*` | `POST /{fork}/payloads` |
| `engine_forkchoiceUpdatedV*` | `POST /{fork}/forkchoice` |
| `engine_getPayloadV*` | `GET /{fork}/payloads/{id}` |
| `engine_getPayloadBodiesByHashV*` | `POST /{fork}/bodies/hash` |
| `engine_getPayloadBodiesByRangeV*` | `GET /{fork}/bodies?from=&count=` |
| `engine_getBlobsV*` | `POST /blobs/v{1..4}` |
| `engine_getClientVersionV1` | `GET /identity` + `X-Engine-Client-Version` |
| `engine_exchangeCapabilities` | `GET /capabilities` |
| `engine_exchangeTransitionConfiguration` | removed |

- The fork identifier moved **into the `Eth-Execution-Version` header, out of the URL path** (commit `d39e9a27`); base path renumbered `/engine/v2/` → `/engine/v1/`.
- Spec files: `src/engine/refactor.md`, `src/engine/refactor-ssz.md`.
- **Coexistence plan** (ACDC, `ethereum/pm#2132`, 2026-06-26): JSON and SSZ coexist; SSZ becomes compulsory past a future fork; JSON engine RPC then retired.

### Is the spec in good shape?

Yes as a **foundation**, but not finalized:

- Since the Sep 2 merge, only incremental refinements — e.g. [#898](https://github.com/ethereum/execution-apis/pull/898) (full uint64 gas-limit decoding), [#886](https://github.com/ethereum/execution-apis/pull/886)/[#864](https://github.com/ethereum/execution-apis/pull/864) (inclusion-list edge cases), [#856](https://github.com/ethereum/execution-apis/pull/856) (custody/cell bit ordering).
- One active feature proposal: [#885](https://github.com/ethereum/execution-apis/pull/885) (jsign) — `POST /engine/v1/payloads/witness` for stateless / zkVM provers (returns validation result + execution witness + tx sender pubkeys in one call; optional from Amsterdam, advertised via capabilities). In review as of 2026-09-25.
- Still open: a few constants remain placeholders (`MAX_BAL_BYTES`, `MAX_BYTES_PER_EXECUTION_REQUEST`), and the **JSON-RPC → SSZ migration / deprecation path is explicitly undecided** (raised by m.kalinin — see R&D discussion below).

## Execution-layer client status

Legend: ✅ merged to trunk & current · ◐ partial / older-version on trunk · ○ open PR / draft · ✗ not started

| Client | Trunk (default branch) | Tracks current #793? | Key PRs |
|---|---|---|---|
| **Nethermind** | ✅ merged to `master` | ✅ yes (aligned 2026-08-30) | [#11887](https://github.com/NethermindEth/nethermind/pull/11887), [#12193](https://github.com/NethermindEth/nethermind/pull/12193) (fork→header), [#13023](https://github.com/NethermindEth/nethermind/pull/13023) (align w/#793), [#13111](https://github.com/NethermindEth/nethermind/pull/13111) (blob parity test) |
| **Reth** | ◐ partial merged | partial | [#26394](https://github.com/paradigmxyz/reth/pull/26394) (SSZ payload bodies, merged 2026-09-05); wire types in [alloy#4038](https://github.com/alloy-rs/alloy/pull/4038) |
| **Erigon** | ◐ *older* pre-#793 on `main` | ❌ no | [#21203](https://github.com/erigontech/erigon/pull/21203) (old SSZ-REST, merged 2026-05-15); [#21729](https://github.com/erigontech/erigon/pull/21729) (switch to #793, **open draft, stale since 2026-08-05**) |
| **ethrex** | ○ open PR | in progress | [#6770](https://github.com/lambdaclass/ethrex/pull/6770) (engine REST/SSZ), [#6741](https://github.com/lambdaclass/ethrex/pull/6741) (witness) |
| **Geth** | ○ draft (stalled) | — | [#35171](https://github.com/ethereum/go-ethereum/pull/35171) (open draft, untouched since 2026-06-29) |
| **Nimbus-eth1** | ○ open PR | in progress | [#4653](https://github.com/status-im/nimbus-eth1/pull/4653) |
| **Besu** | ✗ not started | — | no PR/issue referencing REST-SSZ engine or #793 |

Notes:
- **Nethermind** is furthest along and the only EL both merged-to-trunk and current; LukaszRozmej is a primary implementer/reviewer of the spec.
- **Erigon**'s trunk has the pre-#793 transport; the current-spec switch (#21729) is an unmerged draft. The June Erigon↔Prysm interop was against that draft branch, **not trunk**.
- No EL ships this in a **stable release** — all behind flags / on branches / draft, against a spec still iterating on main.

## Consensus-layer client status

| Client | Status | Key PRs |
|---|---|---|
| **Lodestar** | open PR | [#10155](https://github.com/ChainSafe/lodestar/pull/10155) (ssz-rest engine api transport) |
| **Prysm** | prototype (open) | [#16901](https://github.com/OffchainLabs/prysm/pull/16901) |
| **Lighthouse** | draft | [#9652](https://github.com/sigp/lighthouse/pull/9652) |
| **Nimbus-eth2** | open PR | [#9048](https://github.com/status-im/nimbus-eth2/pull/9048) (supersedes closed #8895) |

*(Teku / Grandine / Caplin not surveyed for this snapshot.)*

## Breakout calls — status

The dedicated **"SSZ Engine API"** breakout-call series has been wound down:

- Series created via [`ethereum/pm#2127`](https://github.com/ethereum/pm/issues/2127) (2026-06-16); bi-weekly cadence, organized by RazorClient and driven by a contributor whose internship has since ended.
- **4 calls total:** #1 Jun 26 ([#2132](https://github.com/ethereum/pm/issues/2132)), #2 Jul 10 ([#2145](https://github.com/ethereum/pm/issues/2145)), #3 Jul 24 ([#2168](https://github.com/ethereum/pm/issues/2168)), #4 Aug 28 ([#2196](https://github.com/ethereum/pm/issues/2196)).
- The Sep 11 slot was intended as the series finale but never got an agenda or PM issue.
- On 2026-09-10, jtraglia asked PM to remove all remaining SSZ calls from the Ethereum calendar (they were booked through Jan 15 2027), citing the intern's departure and waning interest. MariusVanDerWijden agreed there was little value in keeping a standing series — "one-off calls if necessary."
- No SSZ call issue has been created since, and the `#ssz` R&D channel has been silent since 2026-09-11.

## Eth R&D discussion (Discord `#ssz`, 2026-09-10/11)

- **m.kalinin** has been reviewing the merged spec ("looks good so far"). What he flags as missing: the **migration path to REST+SSZ and future maintenance**.
- **MariusVanDerWijden**: clients are currently mid-implementation (he characterized Geth's own implementation as an early proof-of-concept). Migration paths get discussed once there are real implementations and test cases.
- **kalinin's proposal for the path forward:** snapshot the Engine API at a given fork, use it as the base for REST+SSZ, apply all further Engine API updates to that spec version, and deprecate the JSON-RPC one over time — feasible only once every client has an implementation.

## Bottom line

- The REST+SSZ direction is settled and the base spec is merged; the remaining work is client implementations, test coverage, and an agreed migration/deprecation plan.
- For **interop against the current spec today, Nethermind is effectively the only ready trunk-level EL target.** Erigon needs #21729 to land and be refreshed first; the other ELs are earlier still.

---
*Snapshot by @lodekeeper. Corrections welcome — the underlying spec is still moving on `main`.*
