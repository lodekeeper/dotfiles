# Supplemental internal chat findings — 2026-10-10

Private research index; do not include chat URLs, identities or quotations in the public gist. Direct Discord provider search recovered these conversations, correcting the earlier transcript-coverage limitation.

## 2025-03-04T14:51:16.866000+00:00 — nflaig

Source: https://discord.com/channels/593655374469660673/1346490705454956555/1346495218937237504

another idea that was floating around is that we could dump our fork choice state to disk and that in combination with last unfinalized state should allow us to continue syncing from where the node was left of before the restart, I have some concerns with this approach and it has is limitation
- it does not work for someone who has not had a node synced to head
- if node crashes due to oom or another bug, the fork choice state would not be persisted
- the fork choice stale might be stale and lead us on the wrong chain?? I am still not sure about this one

## 2026-01-22T15:17:35.427000+00:00 — wemeetagain

Source: https://discord.com/channels/593655374469660673/1463911962738954251/1463915508356354264

yes the point is not the data loss, its a more a matter of being able to ensure you boot a node into a coherent state

## 2026-01-22T15:16:51.514000+00:00 — nflaig

Source: https://discord.com/channels/593655374469660673/1463911962738954251/1463915324171620562

if a single node loses data I don't see how it matters as long as this node can reboot from a last consistent data point

## 2026-01-22T15:15:50.409000+00:00 — nflaig

Source: https://discord.com/channels/593655374469660673/1463911962738954251/1463915067878674593

if the node crashes we will likely never persist the fork choice, would be interesting to see what other clients do

## 2026-01-22T15:13:55.245000+00:00 — wemeetagain

Source: https://discord.com/channels/593655374469660673/1463911962738954251/1463914584846110963

I mean more about if we persisted fork choice and shutdown before persisting all blocks, then on reboot the chain state is out of sync

## 2026-08-06T09:05:21.069000+00:00 — lodekeeper

Source: https://discord.com/channels/593655374469660673/1534847441172430888/1534849852926595194

Yep, that line is inside the transient bad window I found.

At `08:55:04` Lodestar was still catching up after the `08:34:45` restart, and Besu was flipping FCU results between `VALID` and `INVALID`. The invalid FCUs stopped at `08:56:11`; by the final check the node matched the Besu cohort at head slot `164718`, `sync_distance=0`, EL not syncing.

So this specific error looks like restart/catch-up churn with Besu, not a persistent wedge.

## 2026-08-06T08:56:53.157000+00:00 — nflaig

Source: https://discord.com/channels/593655374469660673/1534847441172430888/1534847722589523978

<@534934855113506836> I feel like EL really don't like it anymore if we send them old fcus, it seems like restoring the head from forkchoice dump is almost a requirement now with gloas and the fcu changes to allow reorgs on the EL side, previously, ELs just ignore these old fcu calls, not it keeps getting the node stuck after restarts

## 2026-09-28T19:25:13.238000+00:00 — nflaig

Source: https://discord.com/channels/593655374469660673/1549190045813178488/1554212405066735677

so fc dump should fix it magically

## 2026-05-27T21:00:44.237000+00:00 — nflaig

Source: https://discord.com/channels/593655374469660673/1508945283248291921/1509300347284357271

<@534934855113506836> a 3rd annoyance from this, we always have to resync from last finalized, the fc dump would be handy here 😅

## 2026-07-09T07:56:24.467000+00:00 — nflaig

Source: https://discord.com/channels/593655374469660673/1372263082415493200/1524685642523738243

no strong opinion, in case of `ForkChoiceNode` it caused issues with porting fcr between phase0 and gloas. also forkchoice internals shouldn't be ssz containers. but I agree with your statement in general, can put up a PR for this so we can see what others think

## 2025-11-16T20:45:33.563000+00:00 — nflaig

Source: https://discord.com/channels/593655374469660673/605818244036821012/1439718057445425242

saw this come up in a few chats, this would probably be resolved if we dump forkchoice + reload blocks from hot db

## Requirements reinforced (safe generic public synthesis)

- Preserve both a fork-choice snapshot and a usable state/DB seed, not just a head root.
- Snapshot restoration is local restart recovery, not a replacement for first sync, weak-subjectivity checks, or a means to force a community-selected fork.
- Data loss within a crash window is acceptable only if restart selects a coherent committed point.
- Validate stale snapshots and retain recovery/fallback paths; a remembered head is not authority to ignore new messages.
- Persisted inputs and hot-block replay avoid unnecessary peer resync; EL reorg policy makes stale-head fcUs more than logging noise.
- A dump's serialization schema is an implementation artifact, not a requirement to make consensus-spec fork-choice internals SSZ containers.

