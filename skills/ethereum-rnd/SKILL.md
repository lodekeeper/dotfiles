---
name: ethereum-rnd
description: Use when working on Ethereum protocol development, consensus layer, execution layer, beacon chain, EIPs, networking, or any Ethereum R&D topic. Provides reference lookup across specs, APIs, research forums, and governance resources.
---

# Ethereum R&D Reference Lookup

You have access to 17 Ethereum R&D resources for answering questions about Ethereum protocol development.

## Local-First Access (MANDATORY)

**Always use local repos at `~/ethereum-repos/` first.** All GitHub-hosted resources below are cloned locally. Use `grep`, `find`, and `cat` — never use WebFetch for content available locally.

To update repos: `bash scripts/clone-repos.sh ~/ethereum-repos` (does `git pull` on existing clones).

Search and read content directly:

```bash
# Search consensus specs for a function
grep -r "process_attestation" ~/ethereum-repos/consensus-specs/specs/ --include="*.md"

# Read a specific spec file
cat ~/ethereum-repos/consensus-specs/specs/electra/beacon-chain.md

# Find all EIPs mentioning a topic
grep -rl "blob" ~/ethereum-repos/EIPs/EIPS/ | head -20

# Search beacon API endpoints
grep -r "post_beacon_blocks" ~/ethereum-repos/beacon-APIs/apis/

# Find where a function is defined across client repos
grep -rn "processAttestation\|process_attestation" ~/ethereum-repos/lodestar/packages/ ~/ethereum-repos/lighthouse/consensus/ --include="*.ts" --include="*.rs"
```

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
| What did ACD decide about X? | pm, forkcast |
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
- `fulu` (epoch 411392) — data availability sampling
- `gloas` (in development) — builder integration, inclusion lists
- `heze` (in development) — next after gloas

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

Example — read the Electra beacon chain spec:
```bash
cat ~/ethereum-repos/consensus-specs/specs/electra/beacon-chain.md
```

**Additional content:**
- `ssz/simple-serialize.md` — SSZ serialization spec
- `configs/` — network configuration (mainnet, minimal)
- `presets/` — parameter presets

---

## 2. ethereum/beacon-APIs — Beacon Node REST API

OpenAPI 3.0 specification for the beacon node and validator client REST APIs.

**Format:** YAML OpenAPI spec. Main file: `beacon-node-oapi.yaml`

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
https://raw.githubusercontent.com/ethereum/execution-apis/main/src/eth/{method}.yaml
```

**Rendered docs:**
```
https://ethereum.github.io/execution-apis/
```

---

## 4. ethereum/execution-specs (EELS) — Executable Execution Layer Spec

Python implementation of the execution layer that serves as the formal specification.

**Language:** Python 3.11+. Prioritizes readability over performance.

**Structure:** Fork modules from Frontier (2015) through Prague/Osaka (2025+), each containing the full EL state transition logic.

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
| `caps/eth.md` | Ethereum Wire Protocol (eth/68) |
| `caps/snap.md` | Snapshot Sync Protocol (snap/1) |
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
- `AllCoreDevs-EL-Meetings/` — Execution Layer calls (ACDE)
- `AllCoreDevs-CL-Meetings/` — Consensus Layer calls (ACDC)
- `Breakout-Room-Meetings/` — specialized topic discussions
- `Network-Upgrade-Archive/` — historical upgrade coordination

**Schedule:** Alternating weeks — one week CL focus, next week EL focus.

**How to fetch meeting notes:**
```
https://raw.githubusercontent.com/ethereum/pm/master/AllCoreDevs-CL-Meetings/call_{number}.md
https://raw.githubusercontent.com/ethereum/pm/master/AllCoreDevs-EL-Meetings/Meeting_{number}.md
```

---

## 11. forkcast.org — Protocol Call Tracker

Comprehensive tracker for all Ethereum protocol development calls. JS-rendered SPA — requires Playwright MCP for full access, but URL patterns are predictable.

**Call series tracked:**
- **ACDC** — All Core Devs Consensus (consensus layer)
- **ACDE** — All Core Devs Execution (execution layer)
- **ACDT** — All Core Devs Testing
- **Breakouts** — FOCIL, EPBS, BAL, RPC, PQTS, PRICE, TLI, ZKEVM, ETM, AWD

**Per-call detail includes:**
- Embedded YouTube recording with timestamps
- Full timestamped transcript with speaker labels
- AI-generated summary (highlights + action items)
- Link to agenda (GitHub pm issue)

**Also tracks network events:** Pectra/Fusaka devnet launches, testnet activations, mainnet upgrades, blob parameter changes (BPO1/BPO2).

**URL patterns:**
```
https://forkcast.org/calls                          — full call list + calendar
https://forkcast.org/calls/acdc/{number}            — specific ACDC call
https://forkcast.org/calls/acde/{number}            — specific ACDE call
https://forkcast.org/calls/acdt/{number}            — specific ACDT call
https://forkcast.org/calls/{breakout}/{number}      — specific breakout call (focil, epbs, bal, etc.)
```

**How to use:** Navigate with Playwright MCP to get transcripts and summaries. For the call list, the page loads without JS issues. Individual call pages need a brief wait for transcript data to load.

**When to use:** When someone asks what was discussed or decided in a specific ACD call, or wants to find the most recent call for a topic. Prefer forkcast over raw pm meeting notes — it has richer content (transcripts, summaries, YouTube links).

---

## 12. ethereum/eth-rnd-archive — Eth R&D Discord Archive

Machine-readable archive of all discussions in the Eth R&D Discord server. Updated weekly.

**Format:** JSON files per day per channel: `{channel}/YYYY-MM-DD.json`

Each message contains: author, category, content, timestamp, attachments.

**115+ channels including:**
- `consensus-dev`, `execution-dev` — core client development
- `evm`, `pos-consensus` — specific protocol areas
- `cryptography`, `formal-methods`, `post-quantum` — research
- `networking`, `el-networking` — p2p layer
- `pectra-upgrade`, `fusaka-upgrade` — upgrade coordination
- `beacon-network`, `portal-network` — network protocols
- `account-abstraction`, `light-clients` — features

**How to search for a topic:**
1. Identify the likely channel(s) from the list above
2. Fetch recent daily JSON files from that channel:
```
https://raw.githubusercontent.com/ethereum/eth-rnd-archive/master/{channel}/YYYY-MM-DD.json
```
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

**Fork naming:** CL forks follow a star-based scheme with incrementing first letters: Altair, Bellatrix, Capella, Deneb, Electra, Fulu, Glamsterdam, Hegotá, I*, J* (I*/J* are placeholders, I* pronounced "I star").

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

1. **ALWAYS use local repos** — `grep`/`cat` on `~/ethereum-repos/`. For non-GitHub sources (ethresear.ch, ethereum-magicians, forkcast, eth2book, leanroadmap, strawmap), use the web-scraping skill (`skills/web-scraping/SKILL.md`).
2. **For OpenAPI specs** (beacon-APIs, builder-specs), read the YAML locally: `cat ~/ethereum-repos/beacon-APIs/apis/...`
3. **For "why" questions**, check annotated-spec and eth2book before the raw specs
4. **For recent protocol decisions**, check pm meeting notes locally, ethresear.ch via web-scraping skill
5. **For implementation details**, the consensus-specs Python code is executable and testable — it's not just documentation
6. **Fork order matters** — each fork builds on the previous. Start with the latest relevant fork and reference earlier ones for context
7. **Cross-file search is powerful** — `grep -r "term" ~/ethereum-repos/consensus-specs/specs/` finds all references instantly
