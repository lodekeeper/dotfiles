# Fork choice dump: what past chats, issues and PRs say (research notes)

Collected 2026-10-10. This is a read-only survey. Nothing was posted anywhere.

## Sources searched

- `~/ethereum-repos/eth-rnd-archive`: the public Eth R&D Discord export at commit `ae3fc7d6` (2026-10-09). Quotes below give the in-repo path. To build a web link, prefix the path with `https://github.com/ethereum/eth-rnd-archive/blob/master/` and URL-encode it (some paths contain emoji or spaces).
- GitHub, read-only. Repos: `ethereum/beacon-APIs`, `OffchainLabs/prysm`, `ChainSafe/lodestar`, `Consensys/teku`, `sigp/lighthouse`, `ethpandaops/go-eth2-client`, `ethereum/execution-apis`, `ethereum/go-ethereum`. Also one public gist by Savid.
- Lodekeeper notes: `~/.openclaw/workspace/memory/**`, `bank/`, `BACKLOG*.md`. `~/eth-rnd-archive-notes` returned nothing.
- Transcripts:
  - `~/.claude/projects/*/*.jsonl`
  - `~/.openclaw/agents/main/sessions/` (including the `.bak`, `.reset` and `.zst` files)
  - `session-sqlite-import-archive/`
  - `agent/openclaw-agent.sqlite`, searched on a copy with the zstd events decompressed.
- **Limitation:** the transcripts contain almost no ChainSafe-internal Discord history (#lodestar-developer, #lodestar-private). The only ChainSafe-server conversation found is the trigger message itself. Most of the "many chats" are in the public Eth R&D archive.

Discord ID mapping, used only to resolve `<@id>` mentions in the archive:

| ID | Person |
|---|---|
| 586161934425128960 | nflaig |
| 755590043632140352 | potuz |
| 504202741933932544 | tbenr |
| 881905303011086387 | etan_status |
| 84562395988508672 | samcm |
| 181594452228308992 | Savid |
| 199561711278227457 | parithosh |
| 575994543527297055 | tuyen4818 / twoeths, who implemented Lodestar's v2 in #9444 |

---

## 0. The trigger (context for the write-up)

**What happened (PRIVATE, see §5):**
- 2026-10-09 22:13 UTC, ChainSafe Discord, #lodestar-developer › "v1.50.0 Planning" thread. Nico (nflaig) posted "can be also fixed via fork choice dump" together with a screenshot of a Lodekeeper note.
- That note said: after restart, beta nodes logged `Too deep reorg` from `engine_forkchoiceUpdatedV3` for about 35 s.
  - The EL was geth 1.17.8, whose `engine.maxreorgdepth` guard defaults to 32.
  - On restart the beacon node replays from finalized and sends fcU for heads 33–62 blocks behind geth's head. Geth refuses until the replay catches up.
  - The note's own suggestion was: "skip fcU during catch-up when the EL head is known to be ahead".
- 2026-10-10 04:53 UTC, Nico: "there ae tons of chats were we discussed the fork choce dump and for what it is useful, please search those and write up a public gist with the goals this needs ot fulfill and study other clients".

**The EL-side rule that produces this error (all public):**
- `ethereum/execution-apis#786` (mkalinin, merged 2026-04-23) "Restrict no-reorg to the prefix of known finalized". It introduces `-38006: Too deep reorg` with an implementation-specific depth.
- go-ethereum #34767 implemented it with a hardcoded cap of 32. `go-ethereum#35335` (merged 2026-07-10) added the flag `--engine.maxreorgdepth`: default 32, `0` means no limit.
- Erigon reads the cap from `MAX_REORG_DEPTH` (per geth#35335).
- ethrex hard-caps at 128. Lodekeeper reported "Reorg depth 2548 exceeds the client's limit of 128" in `interop-🌃/_threads/@Barnabas we can also remove/2026-06-11.json`.
- Related: `ethereum/EIPs#11601` "Execution-Layer Reorg State Retention Window" (nerolation, merged). In `history-expiry/2026-05-07.json`, arnetheduck argued reorg depth should be based on finality, not on the weak subjectivity period (WSP).

**Earlier occurrences of the same symptom:**
- `ChainSafe/lodestar#9716` (2026-07-27), deep sync. Geth showed `Refusing too deep reorg … exceeds limit 32` because the CL "is replaying" behind geth's head.
- `interop-🌃/_threads/I added proposer equivocation to/2026-08-06.json`, nflaig: "ethrex always unhappy after restart" (`Too deep reorg, engine_forkchoiceUpdatedV4`).
- 2022:
  - `ChainSafe/lodestar#3647`: "Restarting the lodestar beacon results in a flood of `error: Error pushing notifyForkchoiceUpdate()`".
  - `#3717` (g11tech): "lodestar's fcU calls 'resets/reverts' the connected EL's head to hundereds of blocks behind".
  - Both are cited as consequences of restart-from-finalized in `#4000` (see G1).

---

## 1. Goals and use cases (deduplicated; only what is evidenced)

### G1. Resume after a restart from the persisted fork choice instead of replaying from finalized

Today Lodestar rebuilds fork choice from the finalized (anchor) state on start-up. The head regresses, fcU points the EL at stale heads, and the node lags behind its EL and its peers. Persisting fork choice on shutdown (and/or periodically) and reloading it would avoid this. This is the goal behind Nico's 2026-10-09 remark.

| Who / when | Where | Quote |
|---|---|---|
| dapplion, 2022-05-10 (open, `prio-low`) | `ChainSafe/lodestar#4000` "Persist fork-choice state > start from head" | "persist the fork-choice state (on shutdown and / or periodically) and restore that state on startup. This approach will prevent "reverting" the head to a much older state." |
| twoeths, 2025-10-31 (open) | `ChainSafe/lodestar#8592` "Persist fork_choice on stop and load on restart" | "when we restart a lodestar beacon node, we completely ignore the old forkchoice, and we start from the head of the finalized state. This cause the node to be out of date compared to EL, and other CL peers". He points to Lighthouse's `load_fork_choice` / `persist_fork_choice` as the reference. |
| g11tech, 2022-06-30 | `interop-🌃/2022-06-30.json` | "each time lodestar starts it starts from the last finalized … we don't persist our forkChoice (yet)" |
| nflaig, 2026-10-09 (private) | ChainSafe Discord | "can be also fixed via fork choice dump" |
| Code, `origin/unstable` b726a05 | `packages/beacon-node/src/chain/chain.ts:569-571`, in `close()` | "Since we don't persist unfinalized fork-choice, we can abort any ongoing unfinalized block writes. // TODO: persist fork choice to disk and allow unfinalized block writes to complete." |

Additional angles:
- **Non-finality.** The `#4000` TODO list includes "Estimate the positives of strategy (2) vs (1), specially in periods of long non-finality".
- **Holesky retro.** matthewkeil, `ChainSafe/lodestar#7504` (2025-02-27): "persist the most recent state root after fork-choice update … Then update that file on each fork-choice update … on startup the node will read the root from the file".

### G2. Keep track of orphaned blocks and payload envelopes across restarts so they get pruned (hot-DB leak)

The fork choice rebuilt after a restart does not know about pre-restart orphans, so archiving never deletes them.

| Who / when | Where | Quote |
|---|---|---|
| nflaig, 2026-09-28 | `ChainSafe/lodestar#10206`, closed in favour of fork choice persistence | "the right solution for this is to dump fork choice and reload it on startup so we don't lose track of orphaned payload, and this would also solve pruning of orphaned blocks" |
| nflaig, 2026-09-28 | `#8592` comment | "persisting fork choice would also fix a hot db leak" (17 stranded hot envelopes on glamsterdam-devnet-8); "we still need to handle unclean shutdowns (OOM, SIGKILL, crash) where fork choice is not persisted" |

### G3. Live debugging of network splits: is a fork caused by fork choice, or by nodes not seeing the other branch?

| Who / when | Where | Quote |
|---|---|---|
| nflaig, 2026-06-08 (glamsterdam-devnet-5, up to 13 forks) | `interop-🌃/2026-06-08.json` | "we should take fork choice dumps and figure out fi those are split because of fc, or because they didn't even see the other forks" |
| potuz / stefanbratanov, 2026-05-03 | `interop-🌃/2026-05-03.json` | potuz: "Is this a forkchoice split?"; stefanbratanov: "got a fork choice dump from teku-geth-1" |
| nflaig, 2026-10-07 | `GET__eth_v2_debug_fork_choice_endpoint/2026-10-07.json` | "I remember in holesky, this endpoint was very important for us" |
| potuz, 2025-02-25 (Holesky / Pectra) | `interop-🌃/2025-02-25.json` | "can you give me a forkchoice dump? `eth/v1/debug/fork_choice`"; "can you take a forkchoice dump from those reth nodes? … not reth, but LH I mean" |
| paulhauner, 2022-08-11 (Goerli merge) | `interop-🌃/2022-08-11.json` | "I dumped the fork choice struct from a LH node about 10s before the merge transition block finalized and analyzed it" (hackmd) |
| m.kalinin, 2022-08-12 | `interop-🌃/2022-08-12.json` | Analysis of the same dump: "All tips are 1-block forks from the canonical chain, except for one" |
| potuz, 2022-08-27 | `pectra-public/2022-08-27.json` | "Enrico posted a forkchoice dump with some long fork but not any indication that it became canonical" |
| Others | `interop-🌃/2023-01-11.json`, `2023-03-13.json`, `2023-03-14.json` | Goerli incidents. potuz: "trying to get a forkchoice dump to see the justification status of that late block" |

### G4. Gloas/ePBS debugging of payload status, PTC votes and `should_build_on_full` (the driver for v2)

Under Gloas, fork choice nodes are `(block_root, payload_status)`. Bugs in PTC vote counting and in the FULL/EMPTY decision could not be debugged with v1.

| Who / when | Where | Quote |
|---|---|---|
| potuz, 2026-02-05 | `epbs/2026-02-05.json` | "did you take care of the forkchoice endpoint? We need to be able to see forks on Forky" |
| nflaig, same day | `ethereum/beacon-APIs#576` | "Noted by @potuz, we need to update the current endpoint to be able to see forks on Forky." |
| potuz, 2026-03-04 (ePBS devnet-0) | `epbs/2026-03-04.json` | "shit we don't have the forkchoice dump endpoint working in that image"; "how to see the full picture without Dora and the forkchoice dump endpoint" |
| potuz / nflaig, 2026-05-29 (Lodestar built on EMPTY at slot 22912) | `epbs/_threads/devnet forkchoice issue/2026-05-29.json` | potuz: "do you have a forkchoice dump that includes them? / have the API people even agreed on a format for the forkchoice dump?" nflaig: "looking at the weights via fork choice, it's `EMPTY=9504` and `FULL=15968`" |
| nflaig, 2026-06-05 (slot 7218 payload reorg) | `interop-🌃/_threads/why was payload of 7218 allowed to be reorged_/2026-06-05.json` | "prysm and lodestar both have the new forkchoice v2 api, either we persist that somewhere or I will add this to lodestar internally / this is painful to debug like this"; "trying to reconstruct fork choice state from logs, but I didn't log every single ptc attestation we get" |
| nflaig, 2026-06-10 | `interop-🌃/_threads/ethrex error logs/2026-06-10.json` | "I love the new v2 fork choice api, finally can see ptc votes" |
| nflaig, 2026-06-23 | `…/ethrex error logs/2026-06-23.json` | "prysm vote counts are all over the place … super confusing if you look the the v2 fork choice dumps" |
| potuz, 2025-02-06 (early ePBS) | `epbs/2025-02-06.json` | "do you know if I can get a forkchoice dump from the node running in kurtosis?"; "forky support for ePBS would be super major" |
| nflaig, 2026-10-07 | v2 thread | "at this point anything is better than shipping mainnet using the v1 endpoint" |

### G5. Historical capture for post-mortems

Dumps are lost on restart, and logs do not hold enough detail to rebuild fork choice. The archive contains repeated requests for dumps from a past moment, and for someone (Xatu, forky, or the client itself) to record them continuously.

| Who / when | Where | Quote |
|---|---|---|
| potuz, 2024-08-14 | `uncategorized/2024-08-14.json` | "You still have forkchoice dumps taken regularly right?" (to parithosh) |
| potuz, 2025-12-19 | `consensus-dev/2025-12-19.json` | "Forkchoice dumps have been incredibly helpful diagnosing bugs." Also argues off-chain data is "lost forever" without retention. |
| potuz / parithosh, 2023-03-13 | `interop-🌃/2023-03-13.json` | potuz: "do you have forkchoice dumps from lighthouse nodes around this time?" parithosh: "sorry i just have forkchoice dumps from teku-geth" |
| nflaig / potuz, 2026-06-05 | 7218 thread | nflaig: "either we persist that somewhere or I will add this to lodestar internally". potuz: "do we have this in Xatu already?" (no answer in thread) |
| terencechain / potuz, 2026-05-16 | `interop-🌃/2026-05-16.json` | Capture before restart. terencechain: "that's why I'm hesitant to restart prysm nodes". potuz: "I dumped logs and forkchoice dumps now, you can kill the node" |
| etan_status, 2022-10-27 (long-split stress test) | `cl-testing/2022-10-27.json` | "`--debug-fork-choice=true`, then periodically poll/save the REST endpoint" (Nimbus) |
| potuz / parithosh, 2022-09-30 | `protocol-fellowship/2022-09-30.json` | potuz: a viewer that would "show you a "history" of the forkchoice view". parithosh: idea "to pipe the forkchoice view through to grafana … for historic info storage" |
| samcm, 2026-10-07 | `ethpandaops/go-eth2-client#61` | Infrastructure exists: "Sepolia lighthouse fork choice snapshots stopped at the Glamsterdam fork". Forky keeps snapshot frames. |

### G6. Visualization and cross-client comparison through a common format

| Who / when | Where | Quote |
|---|---|---|
| tbenr, 2022-08-23 | `tooling/2022-08-23.json` | protovis started as Teku-only: "it is pretty tailored for the protoarray" |
| tbenr, 2022-08-25 | `ethereum/beacon-APIs#231` | "To allow monitoring and debugging tools for inspect and visualize fork choice state … across multiple clients" |
| twoeths, 2023-02-14 | `ChainSafe/lodestar#5144`, the `/eth/v0/debug/forkchoice` proto-array dump | "We want to dump all proto nodes to know the current status of forkchoice to compare to other nodes/clients" |
| tbenr, 2026-10-07 / 10-09 | v2 threads | "i have my own forky (https://github.com/tbenr/protovis) and i want this to be merged"; "https://tbenr.github.io/protovis/ should be able to load dumps and follow nodes exposing latest api" |
| nflaig, 2026-10-07 | v2 thread | "I am kinda also thinking about implementing my own forky now" |
| nflaig, 2026-10-07 | `ChainSafe/lodestar#10191`, on who consumes the endpoint | "consumers are manual curl users, claude using curl or other tools, or forky and similar tooling" |

### G7. Fork alerting and monitoring

- potuz, 2022-08-26, `tooling/2022-08-26.json`: "We just merged that forkchoice endpoint to start getting emails when there are forks" (Prysm).

### G8. Forensics on invalid branches

- etan_status, 2025-03-14 (Holesky), `interop-🌃/2025-03-14.json`: piped `fork_choice.json | jq '… select(.validity=="INVALID") | .block_root'` into a DB block dump. "just dumping the blocks for the entire fork choice, is enough, I guess / states can be recomputed".
- tbenr, 2025-01-21, `interop-🌃/2025-01-21.json`: used Teku's dump to contradict an EL `latestValidHash`. "from teku's forkchoice dump I see several other canonical blocks imported succesfully after thatn one."
- ajsutton, 2022-08-26: "knowing that the EL invalidated something is actually really helpful when debugging issues."

### G9. SSZ encoding of the dump (raised, not agreed)

- nflaig, 2026-06-01, `apis/2026-06-01.json`: "I think what potuz meant is encode the fork choice dump as ssz instead of json, which already right now (pre-gloas) is not possible."
- potuz, 2025-09-26, `epbs/2025-09-26.json`. When nc1234 questioned `ForkChoiceNode` in the ssz_static tests, potuz replied: "Except perhaps for the forkchoice dump if we ever go that route". Details are in §2 R7.

### Not evidenced

No chat explicitly proposes **turning dumps into fork-choice spec tests or reproducing bugs offline from a dump**. Do not claim this as a stated goal. The closest items:
- potuz, 2026-06-05: "I need to start testing this in a more controlled environment".
- nflaig, 2026-06-05: asks that devnet entrants pass the basic fork-choice tests from consensus-specs#5206.

---

## 2. Requirements and constraints

**R1. Expose what clients already store; do not add storage or heavy computation for a debug API.**
- ajsutton, 2022-08-26: "I really want to avoid or at least really minimise calculations to support this API."
- potuz, 2022-08-25 (beacon-APIs#232): "Prysm cannot know the justified checkpoints of the nodes, it does know the justified epoch though."
- potuz, 2026-10-07: "I'd definitely not store anything, I may even return 0 before storing an extra root per node"; "I can compute it per node, the endpoint may be dossing".
- tbenr: "i don't want you to store stuff you don't currently store just for the API".
- Pruning limits what can be reported. potuz: "as we prune forkchoice the earlier epoch's will always have the checkpoint already gone."
- Outcome: `OffchainLabs/prysm#17636` returns a zero root where it cannot recover one.
- Storage cost of PTC tracking. terencechain, approving prysm#16862: "we're adding 4KB to the store in the happy case, and much more in the non-finality case, for a debug endpoint".

**R2. A debug dump should mirror each client's internal structure and dump as much as possible.**
- rolfyone (Teku), PR #615: "because it's a debug endpoint, thats our internal representation … it might be useful to keep simple and just output our data structures".
- tbenr: "it was just a natural full FC dump for us."
- nflaig, #615: "for debugging purposes in general should dump as much data as possible".
- Counterpoint from 2022: Prysm removed and later re-added its dump because "it was borked due to having different forkchoice implementations" (potuz, `tooling/2022-08-23.json`). protolambda on #231: "It doesn't have to enshrine the protoarray".

**R3. Gloas node model.**
- One node per `(block_root, payload_status ∈ {pending, empty, full})`. Pre-Gloas blocks are a single `full` node.
- `parent_payload_status` is required to build the tree. tbenr (PR #615, 2026-09-25): "Teku encodes it in the hash of PENDING/EMPTY nodes … Prysm does not … so a consumer cannot build the tree from both."
- `execution_block_hash` is defined per variant: FULL is the payload hash; PENDING/EMPTY is the bid's `parent_block_hash`.
- v1 cannot represent a Gloas block whose payload is not yet revealed. `beacon-APIs#639` (qu0b): Lighthouse emits `null`, Teku emits `optimistic`, and strict consumers reject the whole response. `beacon-APIs#658` proposed `not_yet_revealed` and was closed in favour of v2.

**R4. PTC votes: counts, not per-index data.**
- potuz, 2026-05-29: Prysm "will only keep a bitlist and a count"; "the endpoint returns for each node simply the number of votes, number of votes for timely and number of votes for available"; "last time to decide if having the per-index data is useful or not. I'm leaning not".
- nflaig asked for the total so that "no" votes and missing votes can be told apart: "how would be know if 257 was `no`, or if we had missed votes?" potuz: "I am exposing the total count as well."
- Spec as merged: counts are "per committee position, including repeated validator indices, and are the same for all nodes of a block".

**R5. Top-level store context.**
- Merged: `justified_checkpoint`, `finalized_checkpoint`, `fork_choice_nodes`, `extra_data`.
- nflaig also proposed `head` (block_root + payload_status); it was not adopted. Lodestar returns it in `extra_data`.
- Prysm's `extra_data` carries `proposer_boost_root`, `previous_proposer_boost_root`, the unrealized checkpoints and `head_root`. potuz in 2022: "global store fields … everyone has: justification/finalization checkpoints, proposer boost info, head root".

**R6. `extra_data` is free-form and unspecified.**
- nflaig, #615: "this seems to be a free form field which clients can populate as they would like, so defining that in the spec seems the opposite of what we want for it".
- Timestamp format: tbenr asks for unix seconds instead of Go `time.String()` (#615 and prysm#17636).

**R7. Wire format: JSON only, response wrapped in `data`.**
- SSZ is currently impossible. nflaig: "it returns enums (`validity`) and has this arbitrary `extra_data` field … wen `Enum` ssz type?"
- etan_status: "optional isn't an SSZ type. also, fork-choice stores are not an SSZ object… it's a regular python object not an SSZ Container". He prioritised unbounded lists first.
- All Lodestar dump routes (`/eth/v0/debug/forkchoice`, v1, v2) are `onlySupport: WireFormat.json` (`packages/api/src/beacon/routes/debug.ts`).

**R8. Versioning.**
- v2 plus deprecation of v1 won.
- nflaig, 2026-06-02, initially: "do we need a v2? it only adds new fields + is json only, we might be fine with keeping v1".
- twoeths, on lodestar#9444: "there's a consumer of this api, it's in a spec for a reason".
- samcm: "Happy for a hard cutover if Forky is the only real user of v1".

**R9. Cross-client standardization has to be pushed.**
- nflaig, 2026-05-29: "for gloas it's hard to move some stuff because nobody has strong opinions or gives feedback on api stuff".
- nflaig, 2026-10-07: "if other clients don't wanna participate, they just have to implement what we decide now".
- Consumers hacked around v1 differences (go-eth2-client#61; nflaig: "claude is willing to hack around everything").

**R10. Requirements specific to persistence (G1/G2).**
- Make it optional. wemeetagain on #4000: "We should make sure this feature has an enable/disable flag".
- Handle unclean shutdowns (nflaig, #8592).
- Research other clients, and the cost of persisting plus pruning (dapplion's #4000 TODOs).
- Persist the execution validity status. m.kalinin, 2022-06-30: "Will `NOT_VALIDATED` payloads be resent to EL on startup?" potuz: "In prysm we persist this status, except for blocks that haven't been finalized".
- Maybe relevant, size: a fork choice that grows "unbounded" when archiving lags (#9718, cited in #9716) is what would get persisted.

---

## 3. Open questions and disagreements

1. **Restart-from-finalized as a recovery tool vs persistence.**
   - g11tech on #4000 (2022): "helps us recover lots of random scenarios by restarting, especially where local EL can be buggy".
   - etan, 2025-03-14: with Nethermind it "was sufficient to just restart nimbus to reset forkchoice".
   - Persisting removes this escape hatch unless it is behind a flag or a reset option. #4000 is still `prio-low` and open, and so is #8592.
2. **Who stores historical dumps: Xatu/forky, or the client?** Open (2026-06-05).
3. **Explicit `pending` node.**
   - potuz: "I dislike Enrico's Claude that adds an explicit pending node".
   - tbenr: filtering it out would need a `pending_weight`.
   - Kept in the spec.
4. **Per-node full `Checkpoint` vs epoch only.**
   - tbenr offered to roll back to epochs if that is easier for Prysm. potuz said "I can compute it per node".
   - Merged with `Checkpoint`. Prysm may return a zero root (prysm#17636 is still open).
5. **`parent_root` of EMPTY/FULL equals its own `block_root`.** Nico proposed it, tbenr was OK with it, and the Codex bot on lodestar#10191 called it wrong. It is in the spec.
6. **Standardizing `extra_data` fields.**
   - nflaig, 2026-10-07: "not sure we wanna standardize some of these, but now would be the chance".
   - rolfyone (2026-06-08) wanted `state_root`, `justified_root` and the unrealized fields promoted to top level.
   - Unresolved; the merged spec keeps `extra_data` free-form.
7. **`extra_data.timestamp` format** in prysm#17636 (tbenr vs james-prysm): open.
8. **SSZ encoding:** blocked on the enum and the free-form `extra_data`, and needs an SSZ Enum/Optional; deprioritised.
9. **Is anyone using it?** potuz, 2026-09-30: "an endpoint that absolutely no one uses ever, ever, ever, not even the pandaOps guys and forky". This contrasts with nflaig's Holesky remark and with Forky consuming it.

---

## 4. State of beacon-APIs standardization

**v1, `GET /eth/v1/debug/fork_choice`**
- Introduced by `ethereum/beacon-APIs#232` (rolfyone, merged 2022-10-29), which came out of issue #231 (tbenr).
- Follow-ups: #263 (checkpoints vs epochs, closed) and #303 (lowercase `validity` enum, merged 2023-02-14).
- #474 (nflaig, merged 2024-10-15) made the nodes list required.
- Deprecated by #615: "Use `GET /eth/v2/debug/fork_choice` for Gloas and later forks."

**v2, `GET /eth/v2/debug/fork_choice`**
- Issue `beacon-APIs#576` (nflaig, 2026-02-05, closed 2026-10-07).
- PR `beacon-APIs#615` (potuz, opened 2026-06-02, merged 2026-10-07 15:40 UTC; approved by tbenr and nflaig).
- Response: `{data: {justified_checkpoint, finalized_checkpoint, fork_choice_nodes[NodeV2] (minItems 1), extra_data}}`.
- `NodeV2` required fields:
  - `slot`, `block_root`
  - `payload_status` (pending|empty|full)
  - `parent_root`, `parent_payload_status` (null if the parent was pruned)
  - `justified_checkpoint`, `finalized_checkpoint`
  - `weight` ("raw stored weight … in Gwei")
  - `validity` (valid|invalid|optimistic)
  - `execution_block_hash`
  - `payload_attester_count`, `payload_availability_yes_count`, `payload_data_availability_yes_count`
  - `extra_data`
- Not included: a top-level `head`; per-node unrealized checkpoints, `state_root` and timestamps (left to `extra_data`).

**Implementations**

| Client | Status |
|---|---|
| Prysm | `OffchainLabs/prysm#16862` (potuz, merged 2026-06-03): pre-spec shape, no `data` wrapper, PTC counts in `extra_data`; also tracks individual PTC votes in fork choice. `#17636` (nflaig, open) aligns it with the merged spec. |
| Lodestar | `#9444` (twoeths, merged 2026-06-02, shipped in v1.44.0): pre-spec shape. `#10191` (nflaig, merged 2026-10-07): spec-aligned. `#10297`: `extra_data` gains `state_root`, the unrealized roots and `attestation_score`. Both are in `v1.50.0-rc.0`. |
| Teku | `Consensys/teku#10800` "getForkchoiceV2" (rolfyone, merged 2026-06-24), "roughly like" #615. tbenr, 2026-10-07: "teku has a preliminary v2 but waiting this to settle". |
| Lighthouse | `sigp/lighthouse#10215` (SamAg19, opened 2026-10-05, open). The v1 endpoint returns `null` validity/hash for Gloas blocks (#639). go-eth2-client#61 says Lighthouse reports `not_yet_revealed`. |
| Nimbus, Grandine | No v2 PR found by GitHub search. tomi0x, 2026-06-09: "Nimbus doesn't have forkchoice running yet" (meaning ePBS fork choice). |
| Consumers | `ethpandaops/go-eth2-client#60` (Savid, merged 2026-10-07) is typed strictly to the merged spec. Forky (ethpandaops). tbenr's protovis (loads dumps, follows live nodes on the latest API). Savid's design-notes gist: https://gist.github.com/Savid/bbb5d45f3436f6ca477ec40b7840b08e. |
| beacon-APIs `CHANGES.md` | Lists #615 (v2 added, v1 deprecated) with every client column blank. |

**Lodestar-only:** `/eth/v0/debug/forkchoice` is a raw proto-array dump (`#5144`, 2023, `getProtoArrayNodes`). It has more fields (best child/descendant, state/target roots, unrealized checkpoints), JSON only.

---

## 5. Sensitive and private content (keep out of the public gist or paraphrase)

**ChainSafe Discord #lodestar-developer › "v1.50.0 Planning" thread (internal)**
- Nico's trigger message, his request, and the screenshot.
- The screenshot names internal fleet groups and nodes (`beta-super`, `beta-mainnet-super`, "unstable group") and mentions watchtower auto-update timing.
- Safe to paraphrase: "after a restart, Lodestar sent fcU for heads 33–62 blocks behind geth's head; geth's default reorg-depth cap of 32 refused them for about 35 s". Do not name fleet nodes.

**Telegram "Lodestar WG" private group, topic "glamsterdam-devnet-5 sync", 2026-06-07**
- Nico asked Lodekeeper to "pull a fork choice dump via the api to confirm" whether two nodes had really synced from finalized (they were optimistic).
- Contains internal host names (`devnet-ax41-*`). If used at all, state it only generically: "verify a node's sync/optimistic state".

**Internal Lodekeeper notes**
- `memory/archive/2026-09-28.md` fleet sweep (about 52 `Too deep reorg` fcU rejects on internal nodes): do not cite.
- Skill docs referencing SSH hosts and key paths: do not cite.

**Public Eth R&D archive, but do not reproduce these details**
- Lodekeeper's posts on 2026-06-11 include devnet SSH hostnames and log paths.
- `interop-🌃/2026-06-06.json` contains an Erigon log line with a raw IPv6 peer address.
- etan's 2025-03-14 message contains a local filesystem path.

**Other**
- No security advisories or GHSA content touch this topic.
- Lodestar's own bugs discussed in public threads are fine to reference by public link if needed: the PTC `notify_ptc_messages` slot-check bug (2026-05-29), and the "deathstar" adversarial devnet node.
- The Discord user ID mapping above is internal research aid. Use handles, not IDs, in the gist.

---

## 6. Maybe relevant

- **Weight semantics.** tbenr's 2022 sketch had `weight_mode`: NON_COMULATIVE | COMULATIVE_TO_ROOT | COMULATIVE_TO_HEAD (beacon-APIs#232 comment, 2022-08-26). The v2 spec now says "raw stored weight". Lodestar #10297 adds `attestation_score`, which excludes proposer boost.
- **Visualization request.** potuz, 2022-08-23: "I'd draw larger the descendant of the heaviest chain".
- **Gap slots.** protolambda, 2022-08-25 (#231): "Should this endpoint output nodes for gap slots?" (no resolution recorded).
- **Size remark.** protolambda / dankrad, 2021-08-23 (`pectra-public/2021-08-23.json`), discussing safe-head APIs: dumping all weights to re-evaluate fork choice externally "gets large (even though lighthouse already supports it for debugging purposes)".
- **Exact restore is hard.** potuz, 2023-09-13 (`consensus-dev/2023-09-13.json`), on undoing a bad import: "If you are able to complete restore the forkchoice tree … then you should be fine. I don't believe anyone can do this in a reasonable manner". This is about rollback, not persistence, but it shows that a persisted or restored fork choice must be exact (weights, pruning, unrealized justification).
- **Intervening in fork choice during incidents.** ensi321, `ChainSafe/lodestar#7504`: whitelisting blocks, disabling optimistic sync.
- **Validity enum.** Prysm in 2022 only had an optimistic boolean. ajsutton suggested `execution_optimistic ? OPTIMISTIC : VALID`, and keeping `invalid` because it is informative (`tooling/2022-08-26.json`).
- **What Forky keeps per snapshot.** Panda exposes Forky "frames": per-node snapshots with metadata plus a `fork_choice_nodes` dump. This is from Lodekeeper skill notes on 2026-10-04, which are internal.
