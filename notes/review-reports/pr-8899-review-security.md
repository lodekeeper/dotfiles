# Review Findings — review-security — 8899

Reviewer: review-security
Reviewed commit: c99107c83538666d6e65da5597bee83b6a99798d
Generated at: 2026-08-05 21:06 UTC

Reviewer: review-security
Reviewed commit: c99107c83538666d6e65da5597bee83b6a99798d

## Findings

### packages/beacon-node/src/network/reqresp/handlers/blobSidecarsByRange.ts:24

**Vulnerability:** Unbounded peer-triggered fork-choice walk before serving archived blob ranges (CWE-400).

**Attack vector:** A remote peer can send valid `BlobSidecarsByRange` requests for a small finalized range, for example `count=1`. The handler always calls `chain.forkChoice.getAllAncestorBlocks(...)` and builds `canonicalBlocksBySlot` before checking whether the requested range actually needs fork-choice data. That work is proportional to the full hot ancestor chain from head back to the finalized boundary, not to the requested `count`. During prolonged non-finality or a large hot fork-choice window, repeated low-count requests can force large array and Map allocations and CPU work while the rate limiter charges only the requested sidecar count.

**Severity:** Medium.

**Mitigation:** Defer the `getAllAncestorBlocks()` call and `canonicalBlocksBySlot` allocation until the request intersects the non-finalized range or a bounded finalized-boundary window that still needs canonical-root disambiguation. For older finalized slots, serve via `getBlobSidecarsBinaryBySlot()` directly. If fork-choice lookup is needed, iterate only the requested slot window or cap the walk by request bounds instead of materializing the whole hot chain.

### packages/beacon-node/src/network/reqresp/handlers/dataColumnSidecarsByRange.ts:61

**Vulnerability:** Unbounded peer-triggered fork-choice walk before serving archived data-column ranges (CWE-400).

**Attack vector:** A remote peer can send a valid `DataColumnSidecarsByRange` request for one finalized slot and one custodied column. After request validation, the handler still calls `chain.forkChoice.getAllAncestorBlocks(...)` and builds `canonicalBlocksBySlot` for the entire hot ancestor chain. The cost scales with the node's unfinalized fork-choice history rather than `count * columns.length`, so under finality stalls a cheap request can repeatedly trigger large memory allocations and CPU work.

**Severity:** Medium.

**Mitigation:** Lazily compute canonical fork-choice context only when the requested slots overlap the hot/non-finalized region or the bounded finalized-boundary case. For purely archived finalized ranges, use the flat-file slot cache directly. If canonical context is necessary, walk only as far as the requested slot range requires and avoid building a full-chain Map per request.
