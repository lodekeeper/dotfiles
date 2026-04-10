# Upstream p2p-interface.md issues (alpha.4)

Noted during parity check on 2026-04-10. These exist in upstream spec, not introduced by #2.

## Fixed in our branch

- `envelope.block_root` → `envelope.beacon_block_root` in `execution_payload` gossip (2 occurrences). Trivial field name bug. Fixed in `2ece03dfb`.

## Deferred (require major rework, out of scope for #2)

- `beacon_block` gossip: `parent_bid` alias used inline but never declared upfront
- `beacon_block` gossip: no explicit REJECT for `bid.parent_block_hash` consistency against parent bid
- `beacon_block` gossip: "has been seen" / "passes all validation" language is vague for the deferred payload model
- `payload_attestation_message` gossip: no clarification that `payload_present = True` means local `on_execution_payload` acceptance
