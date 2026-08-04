# Reviewer: review-linter
# PR: #9505
# Reviewed commit: 350d13c7c384b379eab3934d0de7b8cd494f5a4d
# Result: no findings

I found no style, maintainability, or test-wiring issues in the changed files.

Review notes:
- Checked the Heze SSZ/type scaffolding around `InclusionListsByIndicesRequest`, `PayloadAttributes`, and fork-copy patterns in `packages/types/src/heze/sszTypes.ts` and `packages/types/src/heze/types.ts`.
- Checked the config additions for `MIN_SLOTS_FOR_INCLUSION_LISTS_REQUESTS` in `packages/config/src/chainConfig/configs/mainnet.ts`, `packages/config/src/chainConfig/configs/minimal.ts`, `packages/config/src/chainConfig/types.ts`, and `packages/config/src/chainConfig/params.ts`.
- Checked spec-test skip wiring in `packages/beacon-node/test/spec/utils/specTestIterator.ts`, including the Heze proposer-boost and fork-suite skip changes.
- Checked specrefs mappings/exceptions in `specrefs/configs.yml`; also reviewed the current working-tree specrefs exception/mapping updates in `specrefs/.ethspecify.yml`, `specrefs/dataclasses.yml`, and `specrefs/functions.yml`.

Validation run:
- `ethspecify check --path=specrefs` passed with all 1089 references valid.
- `pnpm biome check` on the changed TypeScript files passed. The command emitted the expected local Node engine warning (`node v22.19.0` vs repo `^24.13.0`), but no lint findings.
- `pnpm --filter @lodestar/types check-types` passed with the same Node engine warning.
- `pnpm --filter @lodestar/config check-types` passed with the same Node engine warning.
