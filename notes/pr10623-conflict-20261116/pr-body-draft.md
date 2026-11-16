## Summary

The shared validator pubkey cache assumes validator indices remain identical across branches. Fork transitions that change how pending deposits are processed can violate that assumption, letting an unfinalized side branch poison later canonical lookups.

- Keep only the trusted finalized registry prefix in the shared dense cache. Track unfinalized pubkey candidates separately and verify candidate indices against the requesting state's registry, in both TypeScript and native state transitions.
- Promote eligible pubkeys synchronously after accepted block import and trusted checkpoint regeneration, including activation across skipped epochs; prune finalized candidates.
- Validate every retained entry when loading a persisted pubkey snapshot and truncate entries beyond the startup anchor.
- Preserve the ordinary parallel signature-verification path. For exceptional batches whose attester-slashing proofs reference validators added earlier in the batch, resolve keys against each block's pre-state while retaining the common epoch context.

## Validation

Original fix (`c45c978f0c`):

- Root lint and type checks passed. TypeScript state-transition units: 449 passed; CLI units: 228 passed.
- TypeScript consensus-spec tests: minimal 67,457 passed / 123 skipped; mainnet 9,241 passed / 56 skipped (`v1.7.0-beta.4`).
- Native state-transition units passed for mainnet and minimal. Native state-transition spec suites: minimal 5,594 passed / 133 skipped; mainnet 5,186 passed / 541 skipped.
- Bindings: 521 distinct cases passed across the suite and the two era-dependent file reruns, with 3 missing ERE-fixture skips. The initial run lacked the era fixture; supplying the CI-specified fixture let all 89 blocked cases pass.
- Beacon-node: 2,504 distinct cases passed across the suite and one isolated rerun, with 9 skips. The broad run's KZG case exceeded its 20s timeout; it passed isolated in 8.97s without changing the limit.
- Branch-order, restart, Gloas/Heze and no-fork control reproductions pass. Original signed phase0/Electra batches pass with the production BLS worker pool; wrong-candidate signatures, invalid state roots and verifier shutdown reject as expected.
- Regression coverage includes interior snapshot corruption, trusted/candidate loading, accepted-import promotion, and skipped-epoch activation with both state implementations.

No live-network attack or full engine/DA end-to-end run was performed. The separate generic-SSZ native suite was not run because its pinned fixture bundles are absent.

### Merge refresh (`26925e224e`)

Merged `unstable` at `5c2cf84ec1`, retaining the trusted/candidate pubkey modes and upstream's native Heze support change. Root build, lint and type checks passed, as did all 444 state-transition unit tests and seven TypeScript/native reproduction scenarios (including the TypeScript restart check). These checks ran on the resolved merge tree. The broader spec, bindings and beacon-node suite results above are from the original fix; those suites were not rerun for this merge.

## AI assistance

Implementation assisted by OpenAI Codex.
