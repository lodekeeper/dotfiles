# local-mainnet-debug — incident history

Dated write-ups moved out of SKILL.md (2026-10-04). The reusable procedures stay in SKILL.md.

## 2026-02-25 — "Unknown" peers (identify failures)

**Symptoms:** High ratio of "Unknown" in `lodestar_peers_by_client` metric.

**Root cause:** `@libp2p/prometheus-metrics` `trackProtocolStream()` attaches a `message` event listener that races with identify's `pb.read()` for the first data frame. The metrics listener can consume the identify response before the identify handler reads it.

**Fix:** The Lodestar-side workaround (skip `trackProtocolStream` for the `/ipfs/id/1.0.0` protocol, PR #8958) was closed without merging. The real fix is upstream `libp2p/js-libp2p#3378` ("fix: bytestream reads buffered data", merged 2026-02-25) — byteStream checks its own readBuffer before returning null.
