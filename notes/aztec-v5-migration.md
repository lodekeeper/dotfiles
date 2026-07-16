# Aztec Sequencer v5 Node Migration — Prep Notes

**Source:** https://forum.aztec.network/t/v5-node-migration-guide/8596
**Read/verified:** 2026-07-09; **re-checked 2026-07-16**
**Migration:** v4.3.1 → **v5.0.1** (was rc.1 — see UPDATE below)
**Difficulty:** HIGH — major protocol upgrade, network-wide simultaneous L1 upgrade.

## ⚠️ UPDATE 2026-07-16 (rc.1 is obsolete — stable is out)
Release timeline (github.com/AztecProtocol/aztec-packages/releases):
- v5.0.0-rc.1 — Jun 15  → v5.0.0-rc.2 — Jun 29  → **v5.0.0 stable — Jul 13**  → **v5.0.1 — Jul 15 (latest)**
- **Deploy target = `aztecprotocol/aztec:5.0.1`** (skip rc entirely). v5.0.1 = v5.0.0 + prover-node clean-shutdown fix + `set-funding-account` validator CLI. NO consensus changes, NO new migration steps vs v5.0.0, non-mandatory over 5.0.0 but strictly newer → just use it.
- Core migration mechanics (below) are UNCHANGED rc.1 → stable. Notes still valid.
- **Slashing grace period:** ~1 week from the moment the v5 payload executes on L1 before non-compliant nodes are slashed; on-chain `SLASH_GRACE_PERIOD_L2_SLOTS` default 128 slots. If the L1 flip already happened, the clock is ticking — don't dawdle.
- **Governance signaling** (separate post, github forum t/8606, Jun 30): staked sequencer ops signal support by setting `GOVERNANCE_PROPOSER_PAYLOAD_ADDRESS=0x1bBde48410bF7Ad05208cD77dE2bFb0e8F8803D8` (v5 payload contract). Only matters if the vote has NOT yet executed. v5 Rollup contract: 0x91ff8bbd8ebb07893010d50a48a1609e5ebd8e34.
- **OPEN / can't confirm from web:** whether v5 is already canonical on L1 as of Jul 16. Best determined from our node's live state (still v4 & healthy? erroring? in standby?). Deploy action is the same either way (standby if early, catch-up if late).

## ✅✅ MIGRATION DONE + VERIFIED (2026-07-16 13:12 UTC — Nico executed; verified against live node 13:20)
- **Image `aztecprotocol/aztec:5.0.1`** (RPC `nodeVersion: 5.0.1`), entrypoint now `start --node --sequencer --network mainnet` → **`--archiver` correctly dropped**. RestartCount=0.
- **Guide checklist: all satisfied.** migrate-ha-db correctly skipped (local signer, `nodeId: local`). Env audited programmatically vs removed/renamed lists → **CLEAN**. DB auto-wipe fired as expected: `foundation:version-manager Rollup address has changed, resetting data directory`.
- **Out of standby**, on v5 rollup `0x91ff8bbd8ebb07893010d50a48a1609e5ebd8e34`, l1ChainId 1, rollupVersion 4248422647.
- **Synced**: tips proposed 1552 = checkpointed 1552, proven 1536. Archiver following L1 live; validator re-executing every proposal; 24 peers / 55 discv5.
- **Zero real errors** — the 2 "ERROR" grep hits were `L1RpcError` *inside WARNs* about L1 RPC not serving historical `debug_traceTransaction`/`trace_transaction`. Benign.
- **RPC**: `aztec_*` works; legacy `node_*` **still works too** (guide said temporary) → migrate any dashboards before it's removed.
- **All 5 attesters VALIDATING on-chain** (`getAttesterView` status=1, no exit). Stake carried to v5.
  - `inCommittee:false` is EXPECTED, not a fault: active set **3463**, committee ~48/slot → ~1.4%/validator/epoch. Sentinel tracking only 48 (one committee) since it started at slot 19503.
- **✅ RESOLVED — two attesters were slashed, but it's harmless.** On-chain `getActivationThreshold()` = **200,000** exactly → 200k IS the baseline everyone activates at, so the three at exactly 200,000 are pristine and `0x030a9f4d…`=198,000 / `0x6b077c71…`=196,000 definitively took 2k / 4k in penalties (1× and 2× a 2k penalty). **No risk:** `getEjectionThreshold()` = **100,000**, so they carry ~96–98k of headroom (~48 more penalties) and remain status=1 VALIDATING. Not actionable.
  - Dating not established: could be v4-era (stake lives in the GSE and carried across the rollup swap) or today. Leaning v4-era — the guide's ~1-week post-execution slashing grace would have covered today's standby window, and 3/5 are untouched (a long v5 outage would likely have hit all five).
- **⚠️ Blob sourcing is single-point** (my earlier "resync will stall" prediction did NOT materialize — zero blob failures, all checkpoints downloaded). v5 logs `consensusSuperNodes=0 archiveSources=0 blobSinks=1; 1 consensus client(s) ignored because they are not running in supernode or semi-supernode mode` → `consensus:5052` is ignored entirely as a blob source; we rely solely on 1 blob sink, no fallback. Fix: run paired beacon in supernode/semi-supernode mode, or add an archive source.

## CONFIRMED OUR SETUP + PRE-MIGRATION STATE (2026-07-16 ~09:52 UTC, from the running node)
- **Container:** `aztec-sequencer`, image `aztecprotocol/aztec:4.3.1`, restart=always, started 09:35:33Z.
- **Deployment:** docker-compose `sequencer` project at **`/home/ethereum/aztec/sequencer/docker-compose.yml`** — **ethereum-owned; openclaw CANNOT read/edit → Nico executes.** (openclaw can `docker inspect`/`exec` only.)
- **Command:** `start --node --archiver --sequencer --network mainnet` → **drop `--archiver`** for v5. No `--pxe` present.
- **Signer:** **LOCAL keystore** (bind `keys → /var/lib/keystore`, 8 KB). NOT HA/Postgres. → **`migrate-ha-db` does NOT apply.** No Aztec Postgres container exists.
- **Env:** `USE_NETWORK_CONFIG=true` + network defaults; `AZTEC_PORT=8082`, `AZTEC_ADMIN_PORT=8880`, `P2P_PORT=40400`, `DATA_DIRECTORY=/var/lib/data`, `ETHEREUM_HOSTS=https://rpc-mainnet-1.nflaig.dev,http://135.181.2.45:8545`, `L1_CONSENSUS_HOST_URLS=http://consensus:5052`. **NONE of the removed/renamed v5 env vars are set** → env cleanup is a **no-op** for us. `GOVERNANCE_PROPOSER_PAYLOAD_ADDRESS` not set (moot — vote already executed).
- **Data:** `/home/ethereum/aztec/sequencer/data` = **1.5 GB** (archiver, world_state, p2p, admin, sentinel, slasher, cache). Auto-wipes on v5 schema bump → resync.
- **🔴 LIVE STATE: node is STUCK IN STANDBY.** On the 09:35 restart it found the canonical L1 rollup is now the **v5 rollup `0x91ff8bbd8ebb07893010d50a48a1609e5ebd8e34`** (matches governance-post v5 Rollup addr) and logged `incompatible ... Entering standby mode. Will poll every 60s`. Mismatch on genesis archive root / VK tree root / protocol contracts hash (v4 image expects v4 roots, chain has v5 roots). **v4 image can never exit standby now — only the v5 image matches.** → We are LATE and offline for duties, not "early and waiting."
- **⚠️ Related pre-existing issue:** archiver blob fetch failing — `consensus:5052` returns 503 "Custody group count of 17 is not sufficient to serve blob sidecars, must custody at least 64 data columns". Post-upgrade the archiver resync refetches blobs from L1; if this beacon node still can't serve them the resync may stall. Fix: point `L1_CONSENSUS_HOST_URLS` at a blob-serving (≥64-column / full-custody) beacon endpoint.

## Protocol version gate (important behavior)
- v4 and v5 nodes **cannot** operate in the same network.
- A v5 node that detects a still-v4 (canonical) network **auto-enters standby** and waits for the L1 upgrade confirmation, then exits standby and syncs once the v5 rollup is canonical on L1.
- => We can deploy v5 early; it will sit in standby until the network flips. Coordinated cutover, not a race.

## Migration steps (in order)
1. **Backup all DBs** — archiver, PXE, HA Postgres.
2. **HA signer Postgres migration** (only if running the HA signer / Postgres):
   `aztec migrate-ha-db up --database-url postgresql://<user>:<password>@<host>:<port>/<database>`
   - Must run BEFORE starting any v5 node, else the node **crashes** (schema v1→v2).
   - k8s: run as an init container on the v5 image before validator pods start.
3. **Bump image tag → v5.0.0-rc.1** (guide uses `aztecprotocol/aztec:<v5-image-tag>` placeholder; exact string comes from the release page at go-time).
4. **Env var audit** — remove removed vars, apply renames (tables below).
5. **Deployment manifest** — remove `--archiver` and `--pxe` from `aztec start` (both now embedded).
6. **JSON-RPC clients / monitoring / dashboards** — update method prefixes `node_*`→`aztec_*`, `nodeAdmin_*`→`aztecAdmin_*`, `nodeDebug_*`→`aztecDebug_*` (legacy prefixes work temporarily, will be removed).
7. **Test RPC endpoints** against new method names.
8. **Deploy v5** — enters standby if v4 still canonical (expected).
9. **Monitor logs** for schema-mismatch / consensus-config-mismatch errors.

## CLI flag changes (`aztec start`)
- Remove `--archiver` (archiver embedded; use `--archiver.<option>` sub-flags for config).
- Remove `--pxe` (PXE embedded).

## Env var RENAMES (must update)
| v4.x | v5.x |
|---|---|
| `SEQ_GAS_PER_BLOCK_ALLOCATION_MULTIPLIER` | `SEQ_PER_BLOCK_ALLOCATION_MULTIPLIER` |
| `SENTINEL_HISTORIC_PROVEN_PERFORMANCE_LENGTH_IN_EPOCHS` | `SENTINEL_HISTORIC_EPOCH_PERFORMANCE_LENGTH_IN_EPOCHS` |
| `SLASH_ATTEST_DESCENDANT_OF_INVALID_PENALTY` | `SLASH_PROPOSE_DESCENDANT_OF_CHECKPOINT_WITH_INVALID_ATTESTATIONS_PENALTY` |

## Env var REMOVED (silently ignored — clean up)
- `ARCHIVER_MAX_LOGS` (log API redesigned)
- `SEQ_ENFORCE_TIME_TABLE` (timetable always enforced)
- `VALIDATOR_REEXECUTE`, `VALIDATOR_REEXECUTE_DEADLINE_MS` (reexec always on)
- `TX_COLLECTION_*` (slow tx-collection path removed)
- `P2P_DROP_TX`, `P2P_SLOT_CHECK_INTERVAL_MS`
- `SLASH_FACTORY_CONTRACT_ADDRESS`, `SLASH_MAX_PENALTY_PERCENTAGE`, `SLASH_MIN_PENALTY_PERCENTAGE`, `SLASH_PRUNE_PENALTY`

## Network-wide consensus config (must match network defaults or node fails to start)
Timing/protocol: `ETHEREUM_SLOT_DURATION`, `AZTEC_SLOT_DURATION`, `AZTEC_EPOCH_DURATION`, `SEQ_BLOCK_DURATION_MS` (net default 6000), `MAX_BLOCKS_PER_CHECKPOINT`, `CHECKPOINT_PROPOSAL_SYNC_GRACE_SECONDS`.
Identity/L1: `L1_CHAIN_ID`, `AZTEC_TARGET_COMMITTEE_SIZE`, staking lags/thresholds, `AZTEC_MANA_TARGET`, `AZTEC_PROVING_COST_PER_MANA`, `AZTEC_INITIAL_ETH_PER_FEE_ASSET`, governance/slashing params.
- Escape hatch: `ALLOW_OVERRIDING_NETWORK_CONFIG=true` (only if truly needed).

## DB schema changes
| Store | v4.3.1 → v5.0.0-rc.1 | Behavior |
|---|---|---|
| Archiver (LMDB) | 5 → 7 | auto-wipe (resync) |
| PXE data | 5 → 8 | auto-wipe (resync) |
| HA signer (Postgres) | 1 → 2 | **crash** — manual `migrate-ha-db` required |
| Local signing protection (LMDB) | new → 2 | **crash** on mismatch |

## New operator-relevant env vars (defaults)
- `ARCHIVER_SKIP_HISTORICAL_LOGS_CHECK=false` (set true if L1 RPC prunes logs)
- `ETHEREUM_HTTP_TIMEOUT_MS=10000`
- `BLOB_PREFER_FILESTORES=false`, `BLOB_FILE_STORE_TIMEOUT_MS=10000`
- `P2P_PEER_BAN_DURATION_SECONDS=86400`, `P2P_RPC_PRICE_BUMP_PERCENTAGE=10`
- `PUBLISHER_FUNDING_THRESHOLD` (unset), `PUBLISHER_FUNDING_AMOUNT` (unset) — auto top-up publisher balance
- `OTEL_MIN_TRACE_DURATION_MS=10`, `OTEL_BSP_MAX_QUEUE_SIZE=2048`

## JSON-RPC method changes (if we consume the RPC anywhere)
Prefixes: `node_*`→`aztec_*`, `nodeAdmin_*`→`aztecAdmin_*`, `nodeDebug_*`→`aztecDebug_*`.
Removed→replacement: `getL2Tips()`→`getChainTips()`; `getBlockHeader(n)`→`getBlock({number:n}).header`; `getBlockByHash(h)`→`getBlock({hash:h})`; `getProvenBlockNumber()`→`getBlockNumber({tag:'proven'})`; `getCheckpointedL2BlockNumber()`→`getBlockNumber({tag:'checkpointed'})`; `getFinalizedL2BlockNumber()`→`getBlockNumber({tag:'finalized'})`; log retrieval → `getPrivateLogsByTags`/`getPublicLogsByTags`.

## Troubleshooting quick-map
- "Database schema not initialized" / "schema version 1 is outdated" → run `aztec migrate-ha-db up --database-url <url>`.
- "Network consensus config mismatch" → drop custom overrides or set `ALLOW_OVERRIDING_NETWORK_CONFIG=true`.
- Node stuck in standby → expected pre-upgrade; exits once v5 canonical on L1.

## Open questions for Nico (to tailor the exact diff at go-time)
1. Deployment: docker-compose or k8s? (changes how the migrate-ha-db init step is wired)
2. Running the HA signer + Postgres, or single-node local signer? (gates step 2)
3. Any custom `SEQ_*` / `SLASH_*` / `P2P_*` / `TX_COLLECTION_*` overrides currently set? (rename/removal cleanup)
4. Anything external hitting the node's JSON-RPC with `node_*` methods (dashboards, scripts)?
5. Wait for stable v5, or move on the rc.1 when the network coordinates?
