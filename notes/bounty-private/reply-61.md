> we never connect directly to a relay pre-fulu (mainnet), users always run either run mev-boost or commit-boost which should verify the signature

Confirmed. Lodestar doesn't verify the bid signature on the pre-Gloas builder path; it treats `--builder.urls` as a trusted endpoint. The docs say so too: `docs/pages/run/beacon-management/mev-and-builder-integration.md` recommends going through mev-boost "as currently Lodestar assumes this to be a trusted endpoint". The sidecars do the bid checks, and both check the signature by default:

- **mev-boost** v1.12 (`server/get_header.go`): the bid pubkey must equal the configured relay pubkey, and the relay's BLS signature over the builder domain is verified. That check is only skipped with `SKIP_RELAY_SIGNATURE_CHECK=1`. It also checks the parent hash and drops zero-value bids and empty block hashes.
- **commit-boost** v0.11.0 (`crates/pbs/src/mev_boost/get_header.rs`): verifies the relay signature (`skip_sigverify` defaults to false). It also checks the parent hash, timestamp, a non-empty block hash and tx root, and the min bid. With extra validation enabled, it also checks block number and gas limit against the parent block.

So the all-zero-signature bid from the report is rejected by either sidecar. The report points `--builder.urls` straight at the relay, which the docs advise against. Neither sidecar can check that the `block_hash` is valid on the EL. That's inherent to the blinded flow, and a relay that does this costs the proposer the slot, which the circuit breaker then limits.
