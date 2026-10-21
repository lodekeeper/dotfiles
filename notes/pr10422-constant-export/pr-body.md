Stacked on #10422, targeting `nflaig/builder-bid-deadline` as requested in [the review thread](https://github.com/ChainSafe/lodestar/pull/10422#discussion_r4330293014).

- Re-export `BLOCK_PRODUCTION_RACE_CUTOFF_GLOAS_BPS` from the existing beacon-node options barrel, alongside `BUILDER_BID_LAG_BUFFER_MS`.
- Import both constants from `@lodestar/beacon-node` in the CLI instead of using the `/api` subpath for the cutoff.

The definition, value and deadline behavior are unchanged; the existing `/api` export remains available. The stacked diff contains only the two-file refactor.

## Validation

- `pnpm lint`: passed.
- Fresh API, beacon-node and CLI builds: passed.
- Beacon-node and CLI `check-types`: passed.
- Runtime smoke check from the CLI package: the root and existing `/api` cutoff exports resolve to the same value (1667); the root lag-buffer export remains 250ms.
- Two independent source reviews approved the exact diff.

Implemented with AI assistance (Codex).
