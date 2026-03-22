---
name: memory-profiling
description: Profile Node.js memory leaks with heap snapshots and retention-chain analysis. Use when debugging memory growth, object retention, listener leaks, timer leaks, stream leaks, or worker-thread memory issues (especially Lodestar network/discv5 threads).
---

# Memory Profiling

Profile a suspected memory leak by comparing heap snapshots over time and tracing retention chains.

## Quick workflow

1. **Run the target process with stable load** (enough traffic to reproduce growth).
2. **Capture baseline snapshot** (`T0`).
3. **Wait under real workload** (10-30+ min).
4. **Capture later snapshot** (`T1`, optionally `T2`).
5. **Diff by constructor growth** with `scripts/analyze-heap.mjs`.
6. **Trace retention** for suspicious constructors with:
   - `scripts/find-retainers.mjs`
   - `scripts/trace-chains.mjs`
7. **Validate hypothesis** by patching suspected cleanup path and re-running.

## Lodestar (network worker) commands

Use Lodestar REST profiling endpoints:

```bash
# Network worker heap snapshot
curl -s -X POST "http://127.0.0.1:19597/eth/v1/lodestar/write_heapdump?thread=network&dirpath=/tmp/heap"

# Main thread heap snapshot
curl -s -X POST "http://127.0.0.1:19597/eth/v1/lodestar/write_heapdump?thread=main&dirpath=/tmp/heap"

# Discv5 worker heap snapshot
curl -s -X POST "http://127.0.0.1:19597/eth/v1/lodestar/write_heapdump?thread=discv5&dirpath=/tmp/heap"
```

## Analyze snapshots

```bash
# Constructor-level growth between two snapshots
node scripts/analyze-heap.mjs <snap1.heapsnapshot> <snap2.heapsnapshot>

# Who retains a constructor
node scripts/find-retainers.mjs <snap.heapsnapshot> <ConstructorName> [limit]

# Retention chains for sample objects
node scripts/trace-chains.mjs <snap.heapsnapshot> <ConstructorName>
```

## What to look for

- **Unbounded growth in long-lived infra objects**:
  - `Listener`, `Timeout`, `AbortSignal`, stream/muxer objects, `Map`, `Set`
- **Asymmetry signals**:
  - opened vs closed streams counters diverge over time
  - peer/stream maps grow faster than active peer count
- **Retention chain signatures**:
  - object retained by topology/filter maps after disconnect
  - event-listener linked lists retaining closed stream contexts

## Validate fixes

After patching cleanup logic, rerun the same scenario and confirm:

- lower or flat slope for heap used / old-space
- fewer retained stream/listener/timer objects between `T0` and `T1`
- map sizes track live peers instead of cumulative churn


## Self-Maintenance

If any commands, file paths, URLs, or configurations in this skill are outdated or no longer work, update this SKILL.md with the correct information after completing your current task. Skills should stay accurate and self-healing — fix what you find broken.
