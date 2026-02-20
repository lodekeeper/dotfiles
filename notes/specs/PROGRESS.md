# Consensus Specs Study — Progress Tracker

## Plan
Read specs alongside Lodestar code. Document learnings. Open PRs for any issues found.

## Priority Order
1. **Gloas/EPBS** (active work area)
2. **Phase0** (foundation)
3. **Altair** (sync committees, light client)
4. **Bellatrix** (the merge, execution payloads)
5. **Capella** (withdrawals)
6. **Deneb** (blobs, KZG)
7. **Electra** (current mainnet fork)
8. **PeerDAS/Fulu** (next fork)

## Additional Resources
- **Beacon APIs** (`~/beacon-APIs`) — OpenAPI spec for beacon node REST API, includes `validator-flow.md` (implementation reference for validator client ↔ beacon node interaction)

## Format per section
- Spec file: `consensus-specs/specs/<fork>/<topic>.md`
- Lodestar impl: `packages/<pkg>/src/...`
- Spec tests: `packages/beacon-node/test/spec/...`
- Notes: `notes/specs/<fork>-<topic>.md`
- Cross-reference: Lighthouse (Rust), Prysm (Go), Teku (Java) when useful
- Verify findings with gpt-advisor / Codex CLI before opening PRs

## Progress

### Gloas/EPBS
- [x] Beacon chain changes (`specs/gloas/beacon-chain.md`) — notes in `gloas-beacon-chain.md`
- [x] Fork choice (`specs/gloas/fork-choice.md`) — notes in `gloas-fork-choice.md`
- [x] Builder (`specs/gloas/builder.md`) — notes in `gloas-builder.md`
- [x] P2P networking (`specs/gloas/p2p-interface.md`) — notes in `gloas-p2p-interface.md`
- [x] Validator (`specs/gloas/validator.md`) — notes in `gloas-validator.md`
- [x] Fork logic (`specs/gloas/fork.md`) — notes in `gloas-fork.md`

### Phase0
- [x] Beacon chain state transition (`specs/phase0/beacon-chain.md`) — notes in `phase0-beacon-chain.md`
- [x] Fork choice (`specs/phase0/fork-choice.md`) — notes in `phase0-fork-choice.md`
- [x] P2P networking (`specs/phase0/p2p-interface.md`) — notes in `phase0-p2p-interface.md`
- [x] Validator (`specs/phase0/validator.md`) — notes in `phase0-validator.md`
- [x] Weak subjectivity (`specs/phase0/weak-subjectivity.md`) — notes in `phase0-weak-subjectivity.md`

### Altair
- [x] Beacon chain changes (`specs/altair/beacon-chain.md`) — notes in `altair-beacon-chain.md`
- [x] Light client sync protocol (`specs/altair/light-client/`) — notes in `altair-light-client.md`
- [x] Fork choice updates (`specs/altair/fork-choice.md`) — minimal (timing helpers only)

### Bellatrix
- [x] Beacon chain (execution payloads) — notes in `bellatrix-beacon-chain.md`
- [x] Fork choice (POS transition, Engine API, proposer reorgs) — notes in `bellatrix-fork-choice.md`

### Capella
- [x] Beacon chain (withdrawals, BLS-to-execution changes, historical summaries) — notes in `capella-beacon-chain.md`

### Deneb
- [x] Beacon chain (blob sidecars, KZG commitments, EIP-4844/4788/7044/7045/7514) — notes in `deneb-beacon-chain.md`
- [x] Fork choice (is_data_available, PayloadAttributes with beacon root)
- [x] P2P (blob subnets, BlobSidecarsByRange/Root, gossip validation)
- [x] Validator (BlobsBundle, sidecar construction, subnet assignment)
- [x] Polynomial commitments (KZG proof system, trusted setup — delegated to c-kzg native lib)

### Electra
- [x] Beacon chain (5 EIPs: EIP-6110 on-chain deposits, EIP-7002 EL exits, EIP-7251 MaxEB/consolidations, EIP-7549 attestation format, EIP-7691 blob increase) — notes in `electra-beacon-chain.md`
- [x] P2P (SingleAttestation gossip, 9 blob subnets, updated limits)
- [x] Validator (SingleAttestation construction, execution requests, compute_on_chain_aggregate)
- [x] Fork upgrade (upgradeStateToElectra — complex migration)

### PeerDAS/Fulu
- [x] DAS core (custody groups, column assignment, reconstruction, sampling) — notes in `fulu-peerdas.md`
- [x] Beacon chain (EIP-7917 proposer lookahead, EIP-7892 blob schedule, modified process_execution_payload)
- [x] Fork choice (simplified is_data_available for columns)
- [x] P2P (128 column subnets, DataColumnSidecarsByRange/Root, Status v2, MetaData v3, ENR cgc/nfd)
- [x] Validator (validator custody scaling, sidecar construction, distributed blob publishing)

---
*Started: 2026-02-15*
*Last updated: 2026-02-18 — Gloas/EPBS ✅, Phase0 ✅, Altair ✅, Bellatrix ✅, Capella ✅, Deneb ✅, Electra ✅, Fulu/PeerDAS ✅*
*🎉 ALL FORKS COMPLETE*
