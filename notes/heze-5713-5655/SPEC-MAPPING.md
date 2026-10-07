# Spec mapping and validation plan

## #5713 — EIP-8365
- `apply_pending_deposit`: Heze-only rejection before signature checking for unknown validator + BLS prefix 0x00.
- Existing validators: untouched top-up path, regardless of supplied withdrawal credentials/signature.
- Epoch queue logic/churn: unchanged; rejected deposits are still consumed from queue and consume churn before apply.
- Queued pre-fork deposits: pending queue survives upgrade and guard is evaluated at application fork.
- Upstream six minimal vectors generated at exact PR head `68702a5b2`, before #5655 schema changes; fixtures in `vectors8365/minimal/heze/epoch_processing/pending_deposits`.

## #5655 — EIP-8015
- SSZ state gaps at indices 8,9,10,28 (width46) and body gaps at 1,6 (width13); remaining fields retain gindices.
- Upgrade: `eth1DepositIndex == depositRequestsStartIndex` required; no legacy field copies.
- Block/epoch: no Eth1 voting/reset or deposit count checks at Heze.
- Deposit requests: no start-index initialization at Heze, preserve pending queue and builder semantics.
- Validator/block production: remove legacy fields only at Heze, preserve pre-Heze bodies.
- State view: Heze has no Eth1Data; accessor throws before access, matching the Gloas execution-header convention without changing the interface.
- Serialized block byte parsers: fork-specific Heze offsets since Eth1Data and deposits offsets disappear.
- Genesis: Heze default state must remain schema-correct/RANDAO seeded; legacy proof/index genesis processors cannot act on removed fields.
- Targeted upstream fork, sanity and pending-deposit fixtures generated from master `c489a9907` (includes #5655). Other EIP-8365-only behavior is excluded when validating this independent PR.

## Review policy
Nico explicitly requested self-review. Parent will read entire diffs, inspect exact spec source, and run independent validations; no separate review-agent gate or auto-generated reviewer verdict is substituted for that review.
