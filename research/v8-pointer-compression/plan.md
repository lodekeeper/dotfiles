# V8 Pointer Compression for Lodestar — Research Plan

## Question
Can we apply V8 pointer compression to Lodestar to reduce memory usage ~50%?

## Article
https://blog.platformatic.dev/we-cut-nodejs-memory-in-half
- Node.js 25 + `--experimental-enable-pointer-compression` compile flag
- 50% heap reduction, 2-4% latency overhead, better GC tail latencies
- 4GB heap limit per V8 isolate (with IsolateGroups, per-isolate not per-process)
- NAN addons incompatible, NAPI addons fine

## Compatibility Check (done)
- @chainsafe/blst: napi-rs ✅
- snappy: @napi-rs/snappy ✅
- classic-level: NAPI prebuilds ✅
- Worker threads: 4 (BLS pool, network core, discv5, state regen) — IsolateGroups helps

## Key Research Questions
1. **Heap usage**: What's typical heap vs native/Buffer memory split on mainnet beacon node?
   - If heap >4GB, pointer compression is blocked
   - If heap <2GB, savings are still significant but less dramatic
2. **Node 25 compatibility**: Breaking changes vs Node 22 LTS? Can Lodestar run on v25?
3. **Performance impact**: Would 2-4% latency matter for attestation timing / block processing?
4. **GC improvement**: Could better tail latencies reduce missed attestations?
5. **Docker feasibility**: Can we build a Lodestar Docker image based on node-caged?
6. **Testing approach**: engineMock + checkpoint sync for local testing

## Research Agents
1. **web-research**: Node 25 changes, pointer compression community experience, other projects using it
2. **lodestar-analysis**: Heap profiling data, memory usage patterns, Node 25 compat in codebase

## Output
Research report → implementation if feasible → branch on lodekeeper/lodestar
