# EIP-8015 self-review and spec compliance

Verdict: pending final public type/build gates (parent self-review requested by Nico).

Reference: ethereum/consensus-specs#5655; merged head `a5ab894edd2c22494dfe46dc880946d636f5cdf7`; targeted vectors generated from master `c489a99077c16bad7d75053257c50633d12d314d`.

## Layout and transition
- Heze state has width46 active fields with gaps8,9,10,28; no eth1Data,eth1DataVotes,eth1DepositIndex,depositRequestsStartIndex.
- Heze body has width13 active fields with gaps1,6; no eth1Data,deposits. Surviving field order/generalized indices remain unchanged; checked for every field against Gloas and explicit light-client indices735,2945,2946.
- upgradeStateToHeze checks legacy deposit-index equality before changing/committing prestate and copies only surviving fields. Newly added inclusion-list bits remain zero as previous Heze upgrade required.
- Block processing skips Eth1 voting at Heze; epoch skips Eth1 vote-reset; operation processing does not access removed deposits or enforce obsolete empty-deposits condition.
- Pre-Heze validation remains unchanged; Fulu/Gloas reject nonempty legacy deposit bodies.
- Deposit-request start-index writes remain limited to Electra, and post-Heze requests continue queuing properly.

## Consumers
- Heze block production does not include removed body fields; pre-Heze production still includes them.
- State-view Eth1 accessor is optional and returns undefined at Heze, without fabricated fields; native facade follows same contract.
- Raw signed-block parent payload-hash picker uses correct Heze bid-offset pointer492 instead of Gloas568. Network processor passes actual fork; unit test uses nonempty operation section to exercise offset navigation.
- Existing state-byte loaders calculate offsets by field name and continue working with compact Heze serialization; regression covers state load, modified-validator migration and pubkey/count extraction.
- Genesis defaults preserve RANDAO entropy without adding legacy fields. Legacy proof/index genesis processors explicitly reject Heze.
- Public block/API/signing types require final full-build checks after structural inheritance assumptions were exposed by removing legacy fields.

## Validation
- Exact upstream Heze reftests:92passed across fork(7),pending-deposits(43),sanity(42).
- Standalone EIP-8015 intentionally does not implement EIP-8365's new BLS-validator rejection (independent PR#10292); those six distinct vectors are tested on that PR.
- Gloas compatibility and targeted unit gates recorded in separate logs.
- No review-agent verdict used; user explicitly requested self-review. Parent reviewed complete production changes and regression fixtures against formal spec.
