---
name: ethereum-rnd
description: Use when working on Ethereum protocol development, consensus layer, execution layer, beacon chain, EIPs, networking, or any Ethereum R&D topic. Provides reference lookup across specs, APIs, research forums, and governance resources.
---

# Ethereum R&D Reference Lookup

You have access to 17 Ethereum R&D resources for answering questions about Ethereum protocol development.

## Local-First Access (MANDATORY)

**Always use local repos at `~/ethereum-repos/` first, read at a freshly fetched upstream ref.** Every GitHub repo below except `ethereum/research` is shallow-cloned there. The working trees can be months stale and some sit on feature branches with local work (e.g. EIPs), so never `cat`/`grep` the working tree (eth-rnd-archive excepted, see section 12) and never checkout/pull/reset it: fetch the dev branch into its remote-tracking ref, then read with `git show` / `git grep` / `git ls-tree`. Never use WebFetch for content available locally.

| Repo | Dev branch `<b>` |
|---|---|
| consensus-specs, beacon-APIs, EIPs, pm, devp2p, annotated-spec | `master` |
| execution-apis, builder-specs | `main` |
| execution-specs | `forks/amsterdam` |

```bash
# 1. Fetch (updates only refs/remotes/origin/<b>), then note the ref date to quote in answers
r=consensus-specs; b=master
git -C ~/ethereum-repos/$r fetch -q --depth=1 origin +refs/heads/$b:refs/remotes/origin/$b
git -C ~/ethereum-repos/$r log -1 --format='%cs %h' origin/$b

# 2. Read / list / search at that ref
git -C ~/ethereum-repos/consensus-specs show origin/master:specs/gloas/beacon-chain.md
git -C ~/ethereum-repos/consensus-specs ls-tree --name-only origin/master specs/
git -C ~/ethereum-repos/consensus-specs grep -n "def process_attestation" origin/master -- specs/
git -C ~/ethereum-repos/EIPs grep -l "blob" origin/master -- EIPS/ | head -20
git -C ~/ethereum-repos/beacon-APIs grep -n "publishBlockV2" origin/master -- apis/
```

If the fetch fails, fall back to the raw URLs in each section. Client code (Lodestar, Lighthouse, …): use the consensus-clients skill (same pattern, per-client dev branches). To *run* pyspec or its tests, use the working clone `~/consensus-specs` (check its branch first; `uv run python`, `make test k=<test> fork=<fork>`).

**Why local-first:**
- Instant access (no network latency)
- Can use grep/find for powerful cross-file search
- Works offline
- No rate limits or URL guessing
- Can diff between versions

**Fallback:** Only use web scraping for non-GitHub resources (ethresear.ch, ethereum-magicians, forkcast.org, eth2book, leanroadmap, strawmap). For anything in `~/ethereum-repos/`, always use local access. For web access, use the web-scraping skill (`skills/web-scraping/SKILL.md`) which provides tiered fetching with Cloudflare bypass.

## Quick Reference: Which Resource to Use

| Question type | Go to |
|---|---|
| How does the beacon chain handle X? | consensus-specs |
| What beacon API endpoint does Y? | beacon-APIs |
| What JSON-RPC method does Z? | execution-apis |
| How does the EL implement X? | execution-specs (EELS) |
| How does MEV/builder API work? | builder-specs |
| How does peer discovery/networking work? | devp2p |
| What does EIP-NNNN specify? | EIPs |
| Why was X designed this way? | annotated-spec, eth2book |
| What did ACD decide about X? | forkcast (pm notes only for old calls) |
| What are researchers discussing about X? | ethresear.ch |
| What's the governance status of EIP-NNNN? | ethereum-magicians |
| What's happening with consensus redesign? | leanroadmap |
| What's the overall roadmap status? | strawmap |
| What did R&D Discord say about X? | eth-rnd-archive |

---

## 1. ethereum/consensus-specs — Consensus Layer Specifications

The canonical source for Ethereum's proof-of-stake protocol.

**Structure:** Specs are organized by fork in `specs/{fork}/` with consistent filenames.

**Forks (in order):**
- `phase0` (epoch 0) — foundational beacon chain
- `altair` (epoch 74240) — light client support, sync committees
- `bellatrix` (epoch 144896) — the merge
- `capella` (epoch 194048) — withdrawals
- `deneb` (epoch 269568) — blob transactions (EIP-4844)
- `electra` (epoch 364032) — validator consolidation, max EB
- `fulu` (epoch 411392) — PeerDAS (data availability sampling); current mainnet fork
- `gloas` (in development; CL half of Glamsterdam, run on glamsterdam-devnet-N, specced in the v1.7.0 pre-releases) — ePBS (EIP-7732) with the Payload Timeliness Committee (PTC)
- `heze` (in development; CL half of Hegotá) — FOCIL (EIP-7805)
- `_features/` — candidate EIPs specced in isolation (e.g. `eip7716`, `eip8025`)

Mainnet config sets `GLOAS_FORK_EPOCH` and `HEZE_FORK_EPOCH` to FAR_FUTURE.

**Key files per fork:**
- `beacon-chain.md` — state transition, data structures, epoch processing
- `validator.md` — validator duties, attestation, proposal
- `fork-choice.md` — fork choice rule (LMD-GHOST + Casper FFG)
- `p2p-interface.md` — gossipsub topics, req/resp protocols
- `fork.md` — fork transition logic
- `light-client/` — light client sync protocol (altair+)

**How to fetch:**
```
https://raw.githubusercontent.com/ethereum/consensus-specs/master/specs/{fork}/{file}.md
```

Example — read the Electra beacon chain spec (after the fetch above):
```bash
git -C ~/ethereum-repos/consensus-specs show origin/master:specs/electra/beacon-chain.md
```

**Additional content:**
- `ssz/simple-serialize.md` — SSZ serialization spec
- `configs/` — network configuration (mainnet, minimal)
- `presets/` — parameter presets

---

## 2. ethereum/beacon-APIs — Beacon Node REST API

OpenAPI 3.0 specification for the beacon node and validator client REST APIs.

**Format:** YAML OpenAPI spec. Main file: `beacon-node-oapi.yaml`. `validator-flow.md` is the validator client ↔ beacon node interaction reference.

**Key directories:**
- `apis/` — individual endpoint definitions
- `types/` — shared data type schemas
- `params/` — parameter definitions

**API categories:**
- Beacon endpoints — chain state, blocks, validators, attestations
- Config endpoints — spec values, fork schedule
- Debug endpoints — chain heads, state dumps
- Events endpoints — SSE event stream
- Node endpoints — identity, peers, sync status
- Validator endpoints — duties, block production, attestation

**How to fetch:**
```
https://raw.githubusercontent.com/ethereum/beacon-APIs/master/apis/{category}/{endpoint}.yaml
```

**Rendered docs (human-readable):**
```
https://ethereum.github.io/beacon-APIs/
```

---

## 3. ethereum/execution-apis — Execution Layer APIs

OpenRPC specification for JSON-RPC and Engine API.

**Format:** YAML split across multiple files in `src/`, compiled to `openrpc.json`.

**Two API surfaces:**
- **JSON-RPC** (`eth_*` namespace) — standard client API for users/apps
- **Engine API** (`engine_*` namespace) — authenticated CL↔EL communication

**Key directories:**
- `src/eth/` — JSON-RPC method specs
- `src/engine/` — Engine API specs (organized by fork)
- `src/schemas/` — shared type definitions

**How to fetch:**
```
https://raw.githubusercontent.com/ethereum/execution-apis/main/src/engine/{fork}.md
https://raw.githubusercontent.com/ethereum/execution-apis/main/src/eth/{category}.yaml   # block, state, transaction, fee_market, ...
```

**Rendered docs:**
```
https://ethereum.github.io/execution-apis/
```

---

## 4. ethereum/execution-specs (EELS) — Executable Execution Layer Spec

Python implementation of the execution layer that serves as the formal specification.

**Language:** Python 3.11+. Prioritizes readability over performance.

**Structure:** Fork modules from Frontier (2015) through Prague, Osaka, BPO1–5 and Amsterdam, each containing the full EL state transition logic.

**Key paths:**
- `src/ethereum/forks/{fork}/` — fork-specific implementation
- `src/ethereum/forks/{fork}/vm/` — EVM implementation for that fork
- `tests/` — test suite

**How to fetch:**
```
https://raw.githubusercontent.com/ethereum/execution-specs/forks/amsterdam/src/ethereum/forks/{fork}/{file}.py
```

---

## 5. ethereum/builder-specs — Builder API (PBS)

OpenAPI specification for proposer-builder separation. Defines how consensus clients source blocks from external builders.

**Format:** YAML OpenAPI spec. Main file: `builder-oapi.yaml`

**Key directories:**
- `apis/builder/` — builder endpoint definitions
- `specs/` — specs organized by fork
- `types/` — shared types

**How to fetch:**
```
https://raw.githubusercontent.com/ethereum/builder-specs/main/specs/{fork}/builder.md
```

**Rendered docs:**
```
https://ethereum.github.io/builder-specs/
```

---

## 6. ethereum/devp2p — Networking Protocol Specifications

Peer-to-peer networking specs for node discovery and communication.

**Key spec files:**

| File | Protocol |
|---|---|
| `rlpx.md` | RLPx transport protocol (encrypted TCP) |
| `discv4.md` | Node Discovery v4 (Kademlia-based) |
| `discv5/discv5.md` | Node Discovery v5 (current generation) |
| `enr.md` | Ethereum Node Records (peer identity) |
| `dnsdisc.md` | DNS-based node discovery |
| `caps/eth.md` | Ethereum Wire Protocol (current eth/72, EIP-8070) |
| `caps/snap.md` | Snapshot Sync Protocol (current snap/2, EIP-8189) |
| `caps/wit.md` | State Witness Protocol (wit/0), runs alongside eth |
| `caps/les.md` | Light Ethereum Subprotocol (les/4) |

**How to fetch:**
```
https://raw.githubusercontent.com/ethereum/devp2p/master/{file}.md
https://raw.githubusercontent.com/ethereum/devp2p/master/caps/{protocol}.md
```

---

## 7. ethereum/EIPs — Ethereum Improvement Proposals

All EIPs as individual markdown files.

**File pattern:** `EIPS/eip-{number}.md`

**Categories:**
- **Core** — consensus protocol changes
- **Networking** — p2p layer changes
- **Interface** — user/app interaction standards
- **Meta** — process/governance
- **Informational** — guidelines

**How to fetch a specific EIP:**
```
https://raw.githubusercontent.com/ethereum/EIPs/master/EIPS/eip-{number}.md
```

**Or the rendered version:**
```
https://eips.ethereum.org/EIPS/eip-{number}
```

**Note:** ERCs (token/contract standards) are now in a separate repo `ethereum/ERCs`.

---

## 8. ethereum/annotated-spec — Vitalik's Design Rationale

Annotated versions of the consensus spec focused on explaining *why* things were designed the way they are, not just *what* they do.

**Coverage:** phase0, altair, merge (not "bellatrix"), capella, deneb, phase1 (does not cover electra+)

**Note:** The Bellatrix fork is named `merge` in this repo's directory structure.

**How to fetch:**
```
https://raw.githubusercontent.com/ethereum/annotated-spec/master/{fork}/beacon-chain.md
```

**When to use:** When someone asks "why does the protocol do X?" rather than "what does the protocol do?"

---

## 9. ethereum/research — Protocol Research Code

Vitalik's research codebase. Python scripts and notebooks covering cryptography, data structures, economic analysis, and protocol experiments.

**Topics include:** zkSNARKs, zkSTARKs, Verkle tries, Casper, sharding, erasure coding, polynomial commitments, beacon chain simulations

**Note:** Explicitly unmaintained — code is offered as-is. Useful as reference for understanding research concepts, not as production code.

**How to fetch:**
```
https://raw.githubusercontent.com/ethereum/research/master/{topic}/{file}.py
```

---

## 10. ethereum/pm — AllCoreDevs Meeting Notes

Central coordination hub for Ethereum protocol development.

**Key directories:**
- `AllCoreDevs-EL-Meetings/` — Execution Layer calls (ACDE), files `Meeting {number}.md` (with a space)
- `AllCoreDevs-CL-Meetings/` — Consensus Layer calls (ACDC), files `call_{number}.md`
- `Breakout-Room-Meetings/` — specialized topic discussions
- `Network-Upgrade-Archive/` — historical upgrade coordination
- Root files `glamsterdam-pm.md` (testnet activation schedule) and `glamsterdam-mainnet-plan.md` (mainnet upgrade plan)

**Coverage:** pm notes only cover ACDC ≤150 and ACDE ≤204. For later calls use forkcast artifacts (section 11) or EIPsInsight (see the eth-rnd-archive skill).

**Schedule:** Alternating weeks — one week CL focus, next week EL focus.

**How to fetch meeting notes:**
```
https://raw.githubusercontent.com/ethereum/pm/master/AllCoreDevs-CL-Meetings/call_{number}.md
https://raw.githubusercontent.com/ethereum/pm/master/AllCoreDevs-EL-Meetings/Meeting%20{number}.md
```

---

## 11. forkcast.org — Protocol Call Tracker

Tracker for Ethereum protocol calls, EIP inclusion stages and upgrades. Route pages (`/calls/...`, `/eips`) return only a client-rendered shell; the data is served as JSON. Read `https://forkcast.org/llms.txt` first, it documents every endpoint.

**Call series tracked** (`series` map in `/api/calls.json`):
- **ACDC** — All Core Devs Consensus (consensus layer)
- **ACDE** — All Core Devs Execution (execution layer)
- **ACDT** — All Core Devs Testing
- **Breakouts** — focil, epbs, bal, rpc, pqts, price, tli, zkevm, etm, awd, pqi, fcr, aa, p2p, ssz, ethproofs

**Per-call artifacts** (vary by call; recent ACDC/ACDE calls have the JSON ones): `tldr.json`, `key_decisions.json` (structured `eips`), `notes.json`, `eip_mentions.json`, `transcript.vtt`, `chat.txt`.

**Also tracks network events** (devnet/testnet/mainnet activations): `/feed.xml`, or `gh api repos/ethereum/forkcast/contents/src/data/events.ts`.

**JSON endpoints (plain curl, no auth):**
```
https://forkcast.org/api/calls.json                              — every call: type, date, number
https://forkcast.org/artifacts/{series}/{date}_{number}/{file}   — one call, e.g. acdt/2026-09-28_098/tldr.json
https://forkcast.org/search-light.json                           — TL;DRs + decisions across all calls (~1.3 MB)
https://forkcast.org/api/eips/{id}.json                          — one EIP incl. per-upgrade inclusion-stage history
https://forkcast.org/api/upgrades.json                           — upgrades; projectedActivation is an estimate
https://forkcast.org/api/eip-stage-changes.json                  — latest inclusion-stage changes
```
Build the artifact dir from the call record's `date` + `number` verbatim (`number` is zero-padded); its `path` field (e.g. `acdt/098`) 404s under `/artifacts/` but is the human-facing link: `https://forkcast.org/calls/{path}/`.

**When to use:** When someone asks what was discussed or decided in a specific ACD call, or wants to find the most recent call for a topic. Prefer forkcast over raw pm meeting notes: it has richer content (summaries, decisions, transcripts) and pm stops at ACDC 150 / ACDE 204. Summaries are edited/AI-compiled, so cross-check a reported decision against the transcript.

---

## 12. ethereum/eth-rnd-archive — Eth R&D Discord Archive

Machine-readable archive of all discussions in the Eth R&D Discord server, committed hourly ("Archive N messages from #channel").

**Local clone:** `~/ethereum-repos/eth-rnd-archive` stays on `master` and is `git pull`ed hourly by the eth-rnd-archive skill's `check-updates.sh`, so read its working tree directly (the one exception to the fetch-then-read rule). For tracking, digests and resolving Discord links/mentions, use the eth-rnd-archive skill (`skills/eth-rnd-archive/SKILL.md`).

**Format:** JSON files per day per channel: `{channel}/YYYY-MM-DD.json`; threads under `{channel}/_threads/<thread title>/YYYY-MM-DD.json`

Each message contains: `author`, `category`, `parent` (channel name for thread messages, empty for top-level), `content`, `created_at`, `attachments`.

**~125 channels including:**
- `consensus-dev`, `execution-dev`, `allcoredevs` — core client development
- `interop-🌃` — cross-client devnet coordination (Glamsterdam devnet triage happens here)
- `epbs`, `inclusion-lists`, `data-availability-sampling`, `apis` — current protocol work
- `evm`, `pos-consensus` — specific protocol areas
- `cryptography`, `formal-methods`, `post-quantum` — research
- `networking`, `el-networking` — p2p layer
- `beacon-network`, `light-clients` — network protocols, features
- Historical only: `pectra-upgrade` (last file 2025-05), `fusaka-upgrade` (2025-12), `portal-network` (2021), `account-abstraction` (2022)

**How to search for a topic:**
1. Identify the likely channel(s) from the list above (`ls ~/ethereum-repos/eth-rnd-archive/`)
2. Find matching daily files: `grep -rl "<keyword>" ~/ethereum-repos/eth-rnd-archive/<channel>/ | sort | tail`
3. Parse the JSON and search message content for relevant keywords

**Tip:** Start with the most relevant channel. For broad protocol questions try `consensus-dev` or `execution-dev`. For specific features, use the dedicated channel.

---

## 13. ethresear.ch — Ethereum Research Forum

Discourse forum for protocol research. Use the web-scraping skill for access.

**Key categories:**
- Proof-of-Stake, Execution Layer Research, Cryptography
- Economics, Networking, Privacy, ZK-SNARKs

**How to search (use JSON API via web-scraping skill):**
```
python3 skills/web-scraping/scripts/auto_scrape.py "https://ethresear.ch/search.json?q={query}"
```

**How to read a specific post:**
```
python3 skills/web-scraping/scripts/auto_scrape.py "https://ethresear.ch/t/{topic-slug}/{topic-id}.json"
```

---

## 14. ethereum-magicians.org — EIP Governance Forum

Discourse forum focused on EIP/ERC governance and protocol coordination.

**Key categories:**
- EIPs (896 topics) — proposal discussions
- ERCs (461 topics) — token/contract standards
- RIPs (18 topics) — rollup improvement proposals
- Protocol Calls & Happenings — meeting coordination

**How to search (use JSON API via web-scraping skill):**
```
python3 skills/web-scraping/scripts/auto_scrape.py "https://ethereum-magicians.org/search.json?q={query}"
```

**When to use:** For understanding the governance status, community sentiment, or discussion history around a specific EIP.

---

## 15. eth2book.info — "Upgrading Ethereum" by Ben Edgington

Comprehensive technical reference book on Ethereum's proof-of-stake transition.

**Structure:**
- Part 1: Building — goals and development processes
- Part 2: Technical Overview — beacon chain, validators, consensus, networking
- Part 3: Annotated Specification — detailed spec walkthrough with types, containers, helpers, state transitions
- Part 4: Upgrades — hard forks, the merge

**Coverage:** Up to Capella (edition 0.3, work in progress). Does not cover Deneb+.

**How to fetch (via web-scraping skill):**
```
python3 skills/web-scraping/scripts/auto_scrape.py "https://eth2book.info/latest/part2/building_blocks/{topic}/"
python3 skills/web-scraping/scripts/auto_scrape.py "https://eth2book.info/latest/part3/transition/{topic}/"
```

**When to use:** For thorough explanations of beacon chain fundamentals — validator lifecycle, consensus mechanics, incentive structures. Best for "explain how X works" questions about the core protocol.

---

## 16. leanroadmap.org — Lean Consensus Roadmap

Tracks Ethereum's consensus layer redesign — forward-looking research and engineering.

**Key workstreams:**
- **Lean Cryptography** — hash-based signatures, post-quantum, SNARK-compatible
- **Lean Consensus** — 3-slot finality, faster block times
- **Lean Governance** — upgrade bundling strategy
- **Lean Craft** — minimalism, modularity, formal verification

**Topics:** Gossipsub v2.0, attester-proposer separation, Poseidon hash cryptanalysis

**Note:** This is a JS-rendered SPA — may need the web-scraping skill's DynamicFetcher or Camoufox tier. Use web_search as fallback for specific lean consensus topics.

---

## 17. strawmap.org — L1 Strawmap: Ethereum Draft Roadmap

The official EF Protocol draft roadmap for Ethereum L1, maintained by the EF Architecture team (Ansgar, Barnabé, Francesco, Justin Drake). A living document updated at least quarterly.

**Format:** Google Drawings diagram embedded via iframe. Requires Google sign-in to view. Not machine-readable — use the sidebar FAQ and info below as reference.

**URL:**
```
https://strawmap.org/
```

**Google Drawings source (requires auth):**
```
https://docs.google.com/drawings/d/1GkcGfQv9kxgrYQMyu0BYGcZya0gIDG_wQ7GsFJEsdzY/edit?usp=sharing
```

**Structure:** The diagram is a timeline of forks progressing left to right, organized into three color-coded horizontal layers:
- **Consensus Layer (CL)** — consensus protocol upgrades
- **Data Layer (DL)** — data availability upgrades
- **Execution Layer (EL)** — execution engine upgrades

Dark boxes denote headliners, grey boxes indicate offchain upgrades, black boxes represent north stars. Arrows signal hard technical dependencies or natural fork progressions.

**Fork naming:** CL forks follow a star-based scheme with incrementing first letters: Altair, Bellatrix, Capella, Deneb, Electra, Fulu, Gloas, Heze, I*, J* (I*/J* are placeholders, I* pronounced "I star"). An upgrade name joins the EL city and the CL star: Glamsterdam = Amsterdam + Gloas, Hegotá = Bogotá + Heze. CL spec dirs use the star name (`specs/gloas`); the EL uses the city (`forks/amsterdam`, `src/engine/bogota.md`).

**Time horizon:** ~7 forks through end of decade (~one fork every 6 months). Well beyond ACD's typical next-two-forks focus.

**Five north stars (long-term goals):**
1. **fast L1** — transaction inclusion and chain finality in seconds
2. **gigagas L1** — 1 gigagas/sec (10K TPS) at L1 via zkEVMs and real-time proving
3. **teragas L2** — 1 GB/sec (10M TPS) at L2 via data availability sampling
4. **post-quantum L1** — century-scale cryptographic security via hash-based schemes
5. **private L1** — privacy as first-class citizen via L1 shielded transfers

**Headliners:** Each fork typically has one CL and one EL headliner (e.g. Glamsterdam: ePBS + BALs).

**Contact:** strawmap@ethereum.org or the maintainers on X (@adietrichs, @barnabemonnot, @fradamt, @drakefjustin).

**When to use:** When someone asks about the overall Ethereum roadmap, which features are planned for which forks, north star goals, or the multi-year direction of L1 development. Direct the user to strawmap.org since the diagram requires Google auth.

---

## General Tips

1. **ALWAYS use local repos** — fetch the dev branch, then `git show`/`git grep` at `origin/<b>` in `~/ethereum-repos/` (see Local-First Access). For non-GitHub sources (ethresear.ch, ethereum-magicians, forkcast, eth2book, leanroadmap, strawmap), use the web-scraping skill (`skills/web-scraping/SKILL.md`).
2. **For OpenAPI specs** (beacon-APIs, builder-specs), read the YAML locally: `git -C ~/ethereum-repos/beacon-APIs show origin/master:apis/...`
3. **For "why" questions**, check annotated-spec and eth2book before the raw specs
4. **For recent protocol decisions**, use forkcast's JSON (pm notes stop at ACDC 150 / ACDE 204), ethresear.ch via web-scraping skill
5. **For implementation details**, the consensus-specs Python code is executable and testable — it's not just documentation
6. **Fork order matters** — each fork builds on the previous. Start with the latest relevant fork and reference earlier ones for context
7. **Cross-file search is powerful** — `git -C ~/ethereum-repos/consensus-specs grep -n "term" origin/master -- specs/` finds all references instantly
