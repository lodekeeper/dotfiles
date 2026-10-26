**Motivation**

Follow-up to #10329. Pre-gloas, every gossip data column re-triggers getBlobs, so a `null` answer is retried up to `MAX_GET_BLOBS_ATTEMPTS` times. Post-gloas, getBlobs is triggered once per block, from the bid after block import, so a `null` answer is never retried.

**Description**

- Post-gloas, every failed getBlobsV2 attempt (`null` or a rejected request) arms the existing trailing retry. That gives the same cap of 3 attempts at least 1 s apart as pre-gloas. Retries stop once the sampled columns are complete
- Pre-gloas behavior is unchanged
- Remove the TODO at the bid trigger, since the retry now lives in `GetBlobsTracker`

Retries are not timed to a point in the slot. On glamsterdam-devnet-8 over the last 24h, the post-gloas `null` rate of the single request depended mostly on the EL: reth 1%, geth, besu and nimbusel about 5%, erigon 16%, ethrex about 30%, nethermind 61%. That points at EL blob pool behavior more than at when in the slot we ask, so it doesn't support picking a slot time yet.

**AI Assistance Disclosure**

Written with AI assistance (Claude), including the devnet data, implementation, tests and description.
