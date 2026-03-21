# Log Format Catalog — Lodestar & EL Clients

**Date:** 2026-03-21  
**Author:** Subagent (log-research-format-catalog)  
**Purpose:** Catalog Lodestar beacon node log formats, module names, verbosity levels, structured fields, and EL client formats for the log-reader skill design.

---

## 1. Logger Implementation

Lodestar uses **Winston** as its logging backend (`packages/logger/src/winston.ts`). The logger is a custom `WinstonLogger` class wrapping Winston with per-module level filtering via a custom `ConsoleDynamicLevel` transport.

### Key architecture points

- `WinstonLogger` is the base class; `WinstonLoggerNode` extends it for CLI (node) usage.
- Child loggers are created with `.child({module: "subname"})`, which **concatenates** module names: `parent/child` (e.g. `network/peers`).
- **Per-module log level filtering** is supported via `--logLevelModule chain=debug,network=debug`. This uses a `Map<module, level>` checked in the custom transport's `_write` before emitting.
- Log level is controlled **per transport**, not globally — allows console at `info` while file at `debug`.
- Default log level on startup: `info` (console), `debug` (log file).

---

## 2. Log Formats

Two formats are supported: **human** (default) and **json** (via `--logFormat json`).

### 2a. Human-Readable Format (default)

```
MMM-DD HH:mm:ss.SSS [MODULE]              LEVEL: message key1=value1, key2=value2
```

**Full example:**
```
Mar-21 14:23:11.042 [chain]                 info: Checkpoint finalized epoch=123456, root=0x1234…5678
Mar-21 14:23:11.042 [network]              debug: Discovered peer via discv5 peer=16…a3b4f2, status=connected, cgc=8
Mar-21 14:23:11.042 [network]              debug: Req  dialing peer method=beacon_blocks_by_range, version=1, encoding=ssz_snappy, peer=16…a3b4f2, requestId=42
Mar-21 14:23:11.042 [chain]                warn: Head state not available, triggering regen
Mar-21 14:23:11.042 [chain]                warn: foo bar meta=data, code=SAMPLE_ERROR, data=foo=bar
                                                  ^stack trace on next line for errors^
```

**Template function (from source):**
```
{timestamp} [{module}] {level (right-padded to ~30)}: {message} {context_kv_pairs} [- error_message]
```

- **Timestamp:** `MMM-DD HH:mm:ss.SSS` by default (e.g. `Mar-21 14:23:11.042`)  
- **Timestamp alt — EpochSlot mode:** `Eph EPOCH/SLOT_INDEX SLOT_SECONDS` (e.g. `Eph 312/3 5.123`) — enabled with `--logFormatGenesisTime`  
- **Module field:** padded so level column aligns at character 30  
- **Level field:** right-padded within the padding zone  
- **Context:** appended as `key=value, key=value` pairs  
- **Errors:** appended as ` - error_message\nstack` (plain Error) or `, key=value` (LodestarError with code metadata)  
- **Colors:** ANSI color codes in console output (warn=yellow, error=red, etc.)  

### 2b. JSON Format (`--logFormat json`)

```json
{"timestamp":"2026-03-21T14:23:11.042Z","level":"info","message":"Checkpoint finalized","module":"chain","context":{"epoch":123456,"root":"0x1234…5678"}}
{"timestamp":"2026-03-21T14:23:11.042Z","level":"warn","message":"foo bar","module":"test","context":{"meta":"data"},"error":{"code":"SAMPLE_ERROR","data":{"foo":"bar"},"stack":"..."}}
```

**JSON fields:**
- `timestamp` — ISO 8601
- `level` — `error|warn|info|verbose|debug|trace`
- `message` — string
- `module` — module/context name (may be empty string)
- `context` — object with structured key-value pairs (may be absent)
- `error` — object with `message` + `stack` (plain Error) or `code` + metadata (LodestarError)

**BigInt values** are serialized to strings in JSON format.  
**Uint8Array values** are serialized as hex strings (`0x...`).

---

## 3. Log Levels

Levels in priority order (lowest number = highest priority):

| Level   | Numeric | Description |
|---------|---------|-------------|
| `error` | 0       | Fatal/critical failures requiring attention |
| `warn`  | 1       | Non-fatal issues, degraded operation |
| `info`  | 2       | Normal operational status |
| `verbose` | 3    | Detailed lifecycle events (entry/exit of operations) |
| `debug` | 4       | High-frequency internal state, per-message events |
| `trace` | 5       | Exists in interface, **zero actual callsites** in codebase |

### Volume counts (production code, non-test files):

| Level   | Call count |
|---------|-----------|
| error   | 126 |
| warn    | 70  |
| info    | 142 |
| verbose | 157 |
| debug   | 218 |
| trace   | 0   |

**Volume ratio at debug vs info:** roughly **2.5× more call sites** at debug/verbose than info/warn. In practice, debug is far more voluminous because many debug callsites fire **per slot, per peer, per message** (gossip validators, reqresp, peer discovery heartbeat, sync batches).

### By package:

| Package | Total log callsites |
|---------|-------------------|
| beacon-node | 461 |
| validator | 97 |
| cli | 89 |
| prover | 49 |
| reqresp | 9 |
| light-client | 7 |
| db | 1 |

### Within beacon-node:

| Sub-package | Callsites |
|-------------|-----------|
| chain | 178 |
| network | 125 |
| sync | 78 |
| api | 51 |
| execution | 11 |
| node | 10 |
| monitoring | 5 |
| metrics | 3 |

---

## 4. Module Names

Top-level modules (from `LoggerModule` enum in `packages/beacon-node/src/node/nodejs.ts`):

| Module name | Description |
|------------|-------------|
| `api` | REST API server |
| `backfill` | Backfill sync |
| `chain` | Fork choice, state transitions, block import |
| `execution` | Engine API / EL connection |
| `metrics` | Prometheus metrics |
| `monitoring` | Remote monitoring service |
| `network` | libp2p, gossipsub, peer manager |
| `vmon` | Validator monitor |
| `rest` | REST transport layer |
| `sync` | Range sync, unknown block sync |

Child loggers append `/subname`:
- `network` → internal classes may use `network/peers`, `network/gossip`, etc. (child module naming)
- `chain/blocks`, `chain/regen`, etc. (implied by code structure, some use the parent logger directly)

**No separate `reqresp` module at top level** — reqresp logs go to `network` (it receives the parent logger).

**Validator client** (`packages/validator/`) uses its own logger instance, not a child of beacon-node's logger.

---

## 5. Structured Data in Logs

Logs use rich structured context objects. Key field patterns by module:

### Block/chain fields:
```js
{slot, blockRoot, timeCreatedSec}                    // LogMetaBasic
{slot, blockRoot, timeCreatedSec, expectedBlobs, receivedBlobs}  // LogMetaBlobs (EIP-4844)
{slot, blockRoot, timeCreatedSec, expectedColumns, receivedColumns}  // LogMetaColumns (PeerDAS)
```

### Network/peer fields:
```js
{peer: "16…a3b4f2"}   // prettyPrintPeerId: first 2 + last 6 chars
{peerId: "16Uiu2..."}  // full peer ID sometimes
{status, cgc: 8}       // connection status, custody group count
{addresses: [...]}
```

### ReqResp fields:
```js
{method: "beacon_blocks_by_range", version: 1, encoding: "ssz_snappy", 
 client: "lighthouse", peer: "16…a3b4f2", requestId: 42}
```

### Sync fields:
```js
{id: "SyncChainId", localFinalizedEpoch, targetSlot, peer}
{epoch: startEpoch, ...batch.getMetadata()}
```

### Execution fields:
```js
{oldState: "syncing", newState: "synced"}
{urls: "http://localhost:8551"}
```

### Block root formatting:
- `prettyBytes()`: `0x1234…5678` — 4 hex chars prefix + ellipsis + 4 chars suffix  
- `prettyBytesShort()`: `0x1234…` — prefix only  
- `truncBytes()`: `0x123456789abc` — 12-char hex (6 bytes, no ellipsis)

### Peer ID formatting:
- `prettyPrintPeerId()`: `16…a3b4f2` — first 2 + last 6 chars of the base58-encoded peer ID

---

## 6. Common Error and Warning Messages

### Most common errors (from `logger.error()` callsites):
- `"Error starting REST api server"`
- `"Gossip validations failed while publishing the block"`
- `"Consensus checks failed while publishing the block"`
- `"Error pushing notifyForkchoiceUpdate()"` 
- `"Error on head state regen"`
- `"Builder disabled as the check status api failed"`
- `"BlsMultiThreadWorkerPool error"`
- `"Execution client authentication failed. Verify if the JWT secret matches on both clients"`
- `"Network worker thread error"`
- `"PeerDiscovery: discv5 has no boot enr"`
- `"Error on discv5.findNode()"`
- `"Error onDiscovered"`
- `"Error on ReqResp.unregisterProtocol"` / `"Error on ReqResp.registerProtocol"`

### Most common warnings (from `logger.warn()` callsites):
- `"Low peer count"` (when peers ≤ 1)
- `"Execution client is offline"`
- `"Execution client is syncing"`
- `"Engine failed to produce the block within cutoff time"`
- `"Builder failed to produce the block within cutoff time"`
- `"REST API server is exposed, ensure untrusted traffic cannot reach this API"`
- `"Checkpoint sync recommended, please use --help to see checkpoint sync options"`
- `"Proposer duties re-org. This may happen from time to time"`
- `"Multiple block proposers"` 
- `"Node is syncing"` (from validator client)
- `"Primary beacon node is unhealthy"` (from validator)
- `"Skipped slot due to task taking more than one slot to run"` (from validator)
- `"Published data columns to 0 peers, increased risk of reorg"` (PeerDAS)

### Notifier (regular `info` status line):
Every ~half-slot, a status line like:
```
info: Syncing 4d 2h left - 3.42 slots/s - slot: 1234567 - head: (slot -15) 0x1234…5678 - exec: 0x4567… - finalized: 0xabcd…ef12:123450 - peers: 35
```
or when synced:
```
info: Synced - slot: 1234567 - head: 0x1234…5678 - exec: 0x4567… - finalized: 0xabcd…ef12:123450 - peers: 67
```

---

## 7. Debug Log Verbosity — Key Sources

The most verbose modules at debug/verbose level and why:

### Network (125 callsites total, ~84 debug/verbose)
- **Peer discovery** (`network/peers/discover.ts`): fires per discovered ENR, per dial attempt, per discv5 query result
- **PeerManager** heartbeat: fires every ~12s with peer connect/disconnect events, score updates, goodbye messages
- **GossipHandlers** (`network/processor/gossipHandlers.ts`): fires for **every received gossip message** — blocks, blobs, data columns, attestations. At 1-second slots with PeerDAS this can be very high (hundreds of messages/slot)
- **GossipValidatorFn**: fires per message validation result (accept/reject/ignore)

### Sync (78 callsites, ~60 debug/verbose)
- **Range sync** (`sync/range/chain.ts`): per batch download/processing — fires continuously during initial sync
- **Unknown block sync** (`sync/unknownBlock.ts`): 19 debug callsites — per unknown block root download attempt
- **Backfill sync**: per batch

### ReqResp (`packages/reqresp/`): 9 callsites total
- Fires per request/response stream: dial → send → sent → received → done/error
- With many peers, this multiplies quickly

### Chain (178 callsites, but mostly verbose/debug per-block)
- `blocks/` directory: 19 debug callsites — fires per block import (verified signatures, state transition, persisted to DB)
- `stateCache/`: 9 debug callsites — cache hits/misses per slot
- `regen/`: 3 debug callsites

**At debug level during sync:** expect hundreds to thousands of lines per minute. Network gossip alone at mainnet rates can produce 50-200 debug lines per second (attestations, sync committees, blocks, blobs).

---

## 8. Geth (EL Client) Log Format

Geth uses a completely different log format from Lodestar. **Not JSON by default.**

### Default (human-readable, terminal-colored):
```
INFO [10-04|10:20:52.028] Starting Geth on Ethereum mainnet...
INFO [10-04|10:20:52.028] Bumping default cache on mainnet         provided=1024 updated=4096
WARN [10-04|10:20:55.123] Peer count low                           peers=3 threshold=5
DEBUG[10-04|10:20:55.200] Received block from peer                 peer=abcd1234 block=0x... number=21456789
```

**Format:** `LEVEL [MM-DD|HH:MM:SS.mmm] message key=value key=value`

**Geth log levels (verbosity flags):**
- `0` = silent
- `1` = error
- `2` = warn (default behavior)
- `3` = info (default `--verbosity 3`)
- `4` = debug
- `5` = detail

**JSON mode:** Geth supports `--log.json` flag (added ~2023) which outputs:
```json
{"t":"2026-03-21T14:23:11.042+0000","lvl":"info","msg":"Starting Geth on Ethereum mainnet"}
{"t":"2026-03-21T14:23:11.050+0000","lvl":"info","msg":"Bumping default cache","provided":1024,"updated":4096}
```
Fields: `t` (ISO timestamp), `lvl` (level string), `msg` (message), then additional key-value pairs at top level.

**Key differences from Lodestar:**
- Geth level tag is uppercase, uncolored in format string (colors separately)
- Timestamp format `[MM-DD|HH:MM:SS.mmm]` vs Lodestar's `MMM-DD HH:mm:ss.SSS`
- JSON uses `t`/`lvl`/`msg` vs Lodestar's `timestamp`/`level`/`message`
- Geth KV pairs are positional slog key-value pairs, not a nested `context` object
- No module/namespace field in Geth (no child logger pattern)

---

## 9. Per-Module Level Filtering (Lodestar Feature)

Lodestar supports runtime per-module log level overrides:
```bash
lodestar beacon --logLevel info --logLevelModule network=debug,chain=verbose
```

This is critical for targeted debugging — you can increase verbosity for just `network` or `sync` without drowning in chain debug output.

The `ConsoleDynamicLevel` transport checks `info.module` against the module level map on every log call. **Module matching is exact string match** (not prefix). So `network` matches `[network]` but NOT `[network/peers]` if that's how the child was named.

---

## 10. Summary — Log Format Quick Reference

| Property | Value |
|----------|-------|
| Logger backend | Winston |
| Default format | Human-readable (colored) |
| JSON format flag | `--logFormat json` |
| Timestamp (default) | `MMM-DD HH:mm:ss.SSS` |
| Timestamp (epoch mode) | `Eph EPOCH/SLOT SECS` via `--logFormatGenesisTime` |
| Module separator | `/` (e.g. `network/peers`) |
| Context serialization | `key=value, key=value` (human) or `{"context":{...}}` (JSON) |
| Error serialization | ` - message\nstack` (human) or `{"error":{...}}` (JSON) |
| LodestarError | Inline with context: `, code=X, field=Y` |
| Block root format | `0x1234…5678` (8 chars + ellipsis) |
| Peer ID format | `16…a3b4f2` (first 2 + last 6) |
| Default log file level | `debug` |
| Log file rotation | Daily (configurable, default 5 files) |
| Levels (in order) | error, warn, info, verbose, debug, trace |
| trace callsites | 0 (unused) |
| Most verbose module | network (gossip handlers fire per message) |
| EL (Geth) format | `LEVEL [MM-DD|HH:MM:SS.mmm] msg key=val` |
| Geth JSON flag | `--log.json` → `{t, lvl, msg, key: val}` |
