# EIP-8025 Optional Execution Proofs — Tracker

Last updated: 2026-02-17 01:11 UTC

## Goal
Run a full local **kurtosis interop devnet** with:
- Lodestar + Lighthouse + Prysm
- 1-2 execution clients
- Optional execution proofs flowing end-to-end

## Hard Constraints (from Nico)
- Top priority until completion
- No pauses between cycles except urgent notifications/CI or direct message from Nico
- **Do not open PR** before kurtosis interop is validated locally

## Phase Plan
- [x] A. Foundation (types/constants)
- [x] F. CLI/runtime switches (early)
- [x] B. Networking
  - [x] B1. Gossip topic plumbing (`execution_proof`)
  - [x] B2. Req/Resp: `ExecutionProofsByRoot` + `ExecutionProofsByRange`
  - [x] B4. ENR `zkvm` signaling
- [x] C. ExecutionProofPool + handler wiring
- [x] D. REST API (`GET/POST /eth/v1/beacon/pool/execution_proofs`)
- [ ] E. Sync integration (deferred — gossip sufficient for devnet, full DA gating later)
- [x] G. Kurtosis mixed-client devnet validated locally (Lodestar + Lighthouse)

## Completed Work
- `5ee6cf364c` — Phase A: EIP-8025 SSZ types/constants (`ExecutionProof`, ids, size limits)
- `50cb096d34` — Phase F: `--activate-zkvm`, `--chain.minProofsRequired`, `--chain.zkvmGenerationProofTypes`
- `e33b004043` — Phase B1: `execution_proof` gossip topic wiring (topic parsing, queue, scoring, handler, zkvm-gated subscription)
- `ae6f0f4bde` — Phase B2: `ExecutionProofsByRoot` + `ExecutionProofsByRange` req/resp protocols + types + rate limiting + stubs
- `3e8fae062b` — Phase B4: ENR `zkvm` key signaling (MetadataController + ENRKey.zkvm)
- `da648a690a` — Phase C: ExecutionProofPool + gossip/reqresp handler wiring
- `08b4871ab3` — Phase D: REST API `GET/POST /eth/v1/beacon/pool/execution_proofs` + `publishExecutionProof`

- `87162f96c1` — Phase G: Dummy prover script + kurtosis devnet config + README
- `0f5c73402b` — Fix API submit path (best-effort gossip publish), fix dummy prover SSE timeout, validate local kurtosis run
- `5b1afeb0ee` — Fix: bridge `activateZkvm` CLI flag to network options (root cause of missing gossip subscription); mixed-client config + API test data

## Next Immediate Steps
1. ~~**Commit mixed-client follow-ups**: bridge `--activateZkvm` into network options; update API test fixtures~~ ✅ Done
2. ~~**Prysm interop**: 3-client interop validated (2026-02-17)~~ ✅ Done
3. **Phase E (deferred)**: Sync integration — range sync proof fetching (not needed for initial devnet)
4. ~~**Polish**: Review all commits, ensure consistency, fix any edge cases found in testing~~ ✅ Done
5. **Pre-PR cleanup**: Review all 16 commits, run full lint, consider squash strategy
6. **Open PR**: 3-client interop is validated — ready to proceed

## Interop Validation Target (before PR)
- Lodestar node in zkvm mode interoperates with Lighthouse + Prysm nodes
- Proof gossip observed across clients
- Req/resp proof fetch works by root and range
- Kurtosis devnet healthy (assertor/dora/log checks)

## Current Validation Status
- ✅ Local kurtosis mixed-client devnet runs with 6 CL nodes (Lodestar + Lighthouse + Prysm)
- ✅ Dummy prover receives head SSE events and submits proofs successfully
- ✅ `GET /eth/v1/beacon/pool/execution_proofs` returns stored proofs on Lodestar zkvm node
- ✅ After Fulu activation (epoch 1), Lodestar publishes `execution_proof` gossip
- ✅ Lighthouse receives/validates execution proofs via gossip (`Successfully verified gossip execution proof`)
- ✅ Prysm receives proofs via gossip and confirms DA requirements met (`Received enough execution proofs`)
- ✅ Prysm supernode generates and broadcasts proof types 0,1 natively
- ✅ Docker + Kurtosis environment working locally
- ✅ Fixed: gossip handler now passes clockSlot for far-future proof rejection
- ✅ Added: ExecutionProofPool unit tests (15 tests covering all pool operations)
- ✅ **3-CLIENT INTEROP VALIDATED** (2026-02-17): Lodestar + Lighthouse + Prysm all gossiping proofs successfully
