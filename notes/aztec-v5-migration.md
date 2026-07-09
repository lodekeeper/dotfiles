# Aztec Sequencer v5 Node Migration — Prep Notes

**Source:** https://forum.aztec.network/t/v5-node-migration-guide/8596
**Read/verified:** 2026-07-09 (two independent fetches, cross-checked verbatim)
**Migration:** v4.3.1 → **v5.0.0-rc.1**
**Difficulty:** HIGH — major protocol upgrade, network-wide simultaneous L1 upgrade.
**Deadline:** none stated (RC; further breaking changes possible before stable v5). No date/testnet given.

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
