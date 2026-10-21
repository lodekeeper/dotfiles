Stacked on #10422, targeting `nflaig/builder-bid-deadline` as requested in [the review thread](https://github.com/ChainSafe/lodestar/pull/10422#discussion_r4330293014).

- Re-export `BLOCK_PRODUCTION_RACE_CUTOFF_GLOAS_BPS` from the existing beacon-node options barrel, alongside `BUILDER_BID_LAG_BUFFER_MS`.
- Import both constants from `@lodestar/beacon-node` in the CLI instead of using the `/api` subpath for the cutoff.

The definition, value and deadline behavior are unchanged; the existing `/api` export remains available. The stacked diff contains only the two-file refactor.

## Validation

Pending final build/type/runtime-import checks. Root lint passed; both independent source reviews approved.

Implemented with AI assistance (Codex).
