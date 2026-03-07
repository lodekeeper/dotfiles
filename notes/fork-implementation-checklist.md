# Fork Implementation Checklist

Use this checklist when implementing a new consensus fork in Lodestar (e.g., Gloas, Fulu, Heze).

> Goal: avoid missing one surface (state transition, networking, API, storage, tests, interop) while moving fast.

---

## 0) Scope + Tracking

- [ ] Fork name/version captured (spec branch + commit/hash)
- [ ] Target branch/worktree created
- [ ] Tracking issue and/or project topic linked
- [ ] Out-of-scope items explicitly listed
- [ ] Feature flags / rollout assumptions documented

## 1) Spec Intake

- [ ] Run `scripts/spec/extract-spec-section.sh <fork-or-feature>` to gather primary pseudocode
- [ ] Build section map: spec path + function/type references
- [ ] Identify all changed constants/configs (preset + config files)
- [ ] Identify all new/changed invariants and validation rules
- [ ] List required backward-compatibility constraints

## 2) Data Model / Types (SSZ + State)

- [ ] New SSZ types added in the right package(s)
- [ ] Existing SSZ types updated safely (with migration compatibility considered)
- [ ] Fork-tagged type wiring added (phase0/altair/.../new fork)
- [ ] State fields added/removed/renamed with serialization implications reviewed
- [ ] Type exports + consumers updated (no hidden stale imports)

## 3) State Transition Logic

- [ ] Fork activation gating (slot/epoch/version) implemented
- [ ] Per-block/per-slot/per-epoch transitions updated
- [ ] New validation paths integrated (including error types/reasons)
- [ ] Any changed ordering/dependencies covered (before/after conditions)
- [ ] Consensus-critical edge cases listed and handled

## 4) Fork Choice / Chain Processing

- [ ] Fork choice data dependencies updated (proto-array / cache shape)
- [ ] Head computation assumptions revalidated under new rules
- [ ] Checkpoint/finality interactions reviewed for new fields/paths
- [ ] Range-sync / backfill / block import paths updated where needed
- [ ] Reorg/restart behavior considered (cache miss + fallback paths)

## 5) Networking (Req/Resp + Gossip)

- [ ] New/changed reqresp methods wired (types, handlers, validation)
- [ ] New/changed gossip topics integrated (encoding, validators, scoring)
- [ ] Backward compatibility with old peers validated where required
- [ ] Topic/subnet/mesh expectations documented and monitored
- [ ] Any envelope/auxiliary object flows fully linked to blocks/states

## 6) API Surface

- [ ] Beacon API outputs updated for fork semantics
- [ ] Engine API interactions reviewed for payload/status semantics
- [ ] Debug/state endpoints tested for finalized/justified/head variants
- [ ] Versioning behavior correct pre/post fork boundary
- [ ] Error messages/status codes still meaningful

## 7) Storage / Regen / Caches

- [ ] DB persistence for new fork data added
- [ ] Archive migration/hot→cold paths validated
- [ ] Regen paths tested for missing preferred variant + fallback logic
- [ ] Cache keying/invalidation updated for new dimensions
- [ ] Restart-from-db path verified (no startup regression)

## 8) Metrics / Observability

- [ ] New metrics added for fork-critical flows
- [ ] Existing metrics labels remain stable or migration documented
- [ ] Logs include enough context for triage
- [ ] Grafana/Loki queries identified for first-5-min diagnostics
- [ ] Alert implications reviewed (new false-positive risks)

## 9) Config / Presets / Genesis Inputs

- [ ] Preset/config constants wired for devnet/testnet/mainnet contexts
- [ ] Genesis/checkpoint assumptions validated for the fork
- [ ] Local helper scripts updated if artifact paths changed
- [ ] CLI/help text updated for any new options

## 10) Testing Matrix

### Unit/Property
- [ ] New logic has direct unit tests (happy path + edge cases)
- [ ] Regression tests added for discovered bugs
- [ ] Serialization/SSZ roundtrip tests updated

### Integration/E2E
- [ ] Block processing across boundary tested
- [ ] Sync from checkpoint tested
- [ ] Restart from existing DB tested
- [ ] Reqresp/gossip integration tested for new objects/topics

### Spec vectors
- [ ] Official consensus-spec tests run (or explicit gap logged)
- [ ] Any missing vectors called out and tracked

## 11) Interop / Devnet Validation

- [ ] At least one mixed-client scenario run
- [ ] Lodestar↔Lodestar scenario run for new networking behavior
- [ ] Known client divergence risks listed
- [ ] Devnet triage baseline captured (`scripts/debug/devnet-triage.sh`)

## 12) PR Hygiene + Review Flow

- [ ] PR title/body reflect actual diff scope
- [ ] Commits grouped logically (no unrelated churn)
- [ ] Reviewer prompts include changed-file scope
- [ ] Sub-agent findings filtered against real diff file list
- [ ] All review comments handled in-thread

## 13) Exit Criteria (Ready to Merge)

- [ ] No unresolved blocking comments
- [ ] Required checks green (or failures explicitly non-blocking + documented)
- [ ] Risk notes + rollback plan documented
- [ ] Follow-up issues created for deferred non-critical improvements

---

## Quick Summary Block (copy into PR description)

- Fork coverage: [ ] state transition  [ ] fork choice  [ ] networking  [ ] API  [ ] storage
- Validation: [ ] unit  [ ] integration  [ ] e2e  [ ] checkpoint sync  [ ] restart
- Interop: [ ] mixed-client run  [ ] Lodestar↔Lodestar run
- Risks/known gaps:
  - ...

