---
name: release-metrics
description: >
  Evaluate Lodestar release candidate readiness by comparing beta/RC metrics against stable.
  Use when deploying a new RC to beta nodes, reviewing metrics before cutting a release,
  or assessing whether a release candidate has regressions. Covers health checks, performance
  comparison, memory/resource analysis, validator effectiveness, networking quality, and
  PeerDAS-specific metrics. Requires Grafana/Prometheus access to the Lodestar monitoring stack.
---

# Release Metrics Acceptance

Evaluate whether a Lodestar release candidate is ready to ship by comparing RC nodes against
stable baseline. This skill codifies the team's release review process distilled from multiple
release cycles (v1.34–v1.40).

## When to Run

- After deploying an RC to beta (or feat) group nodes
- Minimum **3 days soak time** before release decision (shorter only if hotfix)
- Before the team standup where the release decision is made
- When asked to compare beta/RC vs stable metrics

## Quick Start

1. Read `references/prometheus-queries.md` — contains all PromQL queries organized by category
2. Run queries against the Grafana Prometheus datasource comparing RC group vs stable group
3. Evaluate each metric category against the acceptance criteria below
4. Generate a release readiness report with a GO / NO-GO / INVESTIGATE recommendation

## Metric Categories & Acceptance Criteria

### 1. Node Health (P0 — must pass)

| Metric | Criteria | Action if Failed |
|--------|----------|-----------------|
| Sync status | 0 slots behind head | NO-GO |
| Finalization | Finalizing (distance ≤ 2 epochs) | NO-GO |
| Reorgs | Zero or same as stable | INVESTIGATE if higher |
| Peer count | 150–250, stable (not spiky) | INVESTIGATE if volatile |
| Block processor queue | Empty (≤ 1) | INVESTIGATE if growing |
| Error rate | No new error types vs stable | INVESTIGATE |

### 2. Attestation & Validator Performance (P0)

| Metric | Criteria | Action if Failed |
|--------|----------|-----------------|
| Head vote accuracy | ≥ stable (compare 6h+ windows) | NO-GO if consistently worse |
| Target/source hit rate | ≥ 99.5% | NO-GO if below |
| Wrong head ratio | ≤ stable | NO-GO if regression |
| Inclusion distance | Avg ≈ 1 (compare to stable) | INVESTIGATE if higher |
| ATTESTER miss ratio | ≤ stable | INVESTIGATE |
| TARGET miss ratio | ≤ stable | INVESTIGATE |

### 3. Block Processing (P0)

| Metric | Criteria | Action if Failed |
|--------|----------|-----------------|
| Block gossip → set as head | ≤ stable avg (typically < 3s) | INVESTIGATE if > 4s |
| Process block time (avg) | ≤ stable | INVESTIGATE if regression |
| Blocks set as head after 4s | Rate ≤ stable | INVESTIGATE |
| Process block count per slot | ≈ 1 | INVESTIGATE if consistently > 1 |
| Epoch transition time | ≤ stable | INVESTIGATE if regression |
| Epoch transitions per epoch | ≈ 1 | INVESTIGATE if > 1 |

### 4. Memory & Resources (P1)

| Metric | Criteria | Action if Failed |
|--------|----------|-----------------|
| RSS memory | Within ±20% of stable (same node type) | INVESTIGATE if higher |
| V8 heap used | Flat trend, no leaks, within ±20% of stable | INVESTIGATE |
| External memory | Flat, no growth trend | NO-GO if unbounded growth |
| Process heap bytes | Flat or declining after startup | INVESTIGATE if growing |
| GC pause rate | < 20% of slot time | INVESTIGATE if higher |
| CPU usage | Within ±30% of stable | INVESTIGATE |
| Disk usage | No abnormal growth rate | INVESTIGATE if > 85% |

**Important:** Fresh processes have higher RSS than long-running ones (Node.js returns memory
to OS over time). Compare at similar uptimes — a 2-day-old beta vs 10-day-old stable will
show ~20-40% higher RSS naturally. This is NOT a regression.

### 5. Networking (P1)

| Metric | Criteria | Action if Failed |
|--------|----------|-----------------|
| Gossip validation job time | ≤ stable | INVESTIGATE |
| Gossip validation dropped jobs | 0 or ≤ stable | INVESTIGATE |
| Gossip block received delay | ≤ stable | INVESTIGATE |
| Avg mesh peers (attestation subnets) | ≥ stable | INVESTIGATE |
| Peer score distribution | No increase in negative-score peers | INVESTIGATE |
| Gossip RPCs tx/rx per sec | Similar to stable | INVESTIGATE |
| Dial errors / timeouts | ≤ stable baseline | INVESTIGATE if spike |
| req/resp error rate | ≤ stable | INVESTIGATE |

### 6. DB & I/O (P1)

| Metric | Criteria | Action if Failed |
|--------|----------|-----------------|
| Archive blocks time | ≤ stable (watch supernodes) | INVESTIGATE if > 10s |
| Hot-to-cold migration time | ≤ stable | INVESTIGATE |
| DB write queue depth | Low, not growing | INVESTIGATE |
| Prometheus scrape duration | ≤ stable | INVESTIGATE if slower |

### 7. PeerDAS-Specific (P1, post-Fulu)

| Metric | Criteria | Action if Failed |
|--------|----------|-----------------|
| Custody column availability | Columns served matches custody groups | INVESTIGATE |
| Missing custody columns | Rate ≤ stable (counters grow but rate matters) | INVESTIGATE |
| Reconstructed columns | 0 in steady state | INVESTIGATE if non-zero |
| Data column gossip time | ≤ stable | INVESTIGATE |
| Column sampling success rate | ≥ stable | INVESTIGATE |

## Node Type Comparison Matrix

Compare metrics across matching node types between RC and stable:

| Type | Custody Groups | Key Focus |
|------|---------------|-----------|
| solo | 4-8 | Baseline: should match stable closely |
| semi | 64 | Memory scaling with custody |
| super | 128 | Stress test: memory, CPU, head votes |
| SAS (supernode+validator+EL) | 128 | Worst case: CPU, event loop, GC |
| arm64 | 4-8 | Architecture: binary compatibility, perf parity |
| mainnet | varies | Real-world: actual block sizes, peer diversity |

**Key insight:** Regressions in solo/semi that don't appear in super = likely not custody-related.
Regressions only in super/SAS = investigate custody group scaling.

## Comparison Methodology

1. **Same timeframe:** Compare RC and stable over the same wall-clock period
2. **Same hardware:** Compare nodes on identical server specs (watch for Hetzner variance)
3. **Rate interval:** Use 6h or 12h for smoothed comparisons, 1h for recent trends
4. **Multiple nodes:** A regression must appear on ≥ 2 nodes of same type to be signal, not noise
5. **Uptime normalization:** Note uptime difference when comparing memory metrics
6. **Check all networks:** Don't forget gnosis/chiado — config edge cases lurk there

## Report Template

```markdown
# Release Readiness Report: v{VERSION}

**Date:** {date}
**RC deployed:** {rc_version} on {date}
**Soak time:** {days} days
**Groups compared:** {rc_group} vs {stable_group}

## Summary: {GO | NO-GO | NEEDS INVESTIGATION}

## Node Health
- Sync: ✅/❌
- Finalization: ✅/❌
- Reorgs: ✅/❌
- Peers: ✅/❌

## Performance
- Head vote accuracy: {rc}% vs {stable}% — ✅/❌
- Block gossip → head: {rc}s vs {stable}s — ✅/❌
- Epoch transition: {rc}ms vs {stable}ms — ✅/❌

## Resources
- RSS: {comparison table}
- Memory trend: {flat/growing/declining}
- GC: {rc}% vs {stable}%
- CPU: {rc} vs {stable} cores

## Networking
- Peers: {count}, stability: {stable/spiky}
- Gossip job time: ✅/❌
- Error rate: ✅/❌

## PeerDAS (if applicable)
- Custody columns: ✅/❌
- Missing rate: ✅/❌

## Items to Watch
1. {any metrics that need continued monitoring}

## Recommendation
{GO / NO-GO / INVESTIGATE with reasoning}
```

## Additional Checks (Non-Metric)

These are not Prometheus metrics but are part of the release process:

- [ ] Docker image size unchanged (no unintended bloat from dependency changes)
- [ ] Binary builds work on amd64 and arm64
- [ ] No breakage for downstream deployments (eth-docker, rocketpool, dappnode)
- [ ] `lodestar dev` sanity check passes
- [ ] No new deprecation warnings in logs
- [ ] CI benchmarks show no performance regression

## References

- `references/prometheus-queries.md` — All PromQL queries by category
- `references/grafana-dashboards.md` — Dashboard UIDs and panel descriptions

---

## Self-Maintenance

If any commands, file paths, URLs, or configurations in this skill are outdated or no longer work, update this SKILL.md with the correct information after completing your current task. Skills should stay accurate and self-healing — fix what you find broken.

