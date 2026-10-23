# PR10457 live Ephemery sync

Source: Nico issuecomment6362905469, 2026-10-23. No merge/deployment authorized.

Exact head: 611e3f9956a0bf219d3dd3357529bea0d4c1e2a7, clean worktree /home/openclaw/lodestar-ephemery-gloas.

- [x] BACKLOG task logged first.
- [x] Read all live PR comments and current metadata.
- [x] Upstream ephemery-genesis75 MERGED 2026-10-22T11:56:04Z, merge9c2cac445414a12d8ed4f8bcec5f004bca70e898. Final release ephemery-165 published17:37:58Z.
- [x] Final release config comparison:93comparable supported fields match, only CONFIG_NAME normalized. Gloas0,chainID39438165,genesis1792696200,max15-at0.
- [x] Exact head dependency/CLI build passed from existing isolated store; no install or main-checkout mutation.
- [x] Started isolated node11:01:34UTC with --network ephemery --execution.engineMock --supernode. Fresh DB, no paramsFile, checkpoint or genesis override. Automatic preset downloads succeeded. Genesis matches final165release byte-for-byte.
- [x] CI reconciled workflow runs/check-runs/statuses: observed_green,0failing/pending/action_required/cancelled,30ok,2skipped across overlapping surfaces; not branch-protection proof.
- [x] Synced genesis->head 11:01:34->11:08:30 UTC; followed head to slot 4850 (wall). Gloas fork 0x8000101b. Finalized 149 0x6cf16c...0a42 matches ChainSafe + Ethstaker (public-checkpoint-final.json).
- [x] Peer QA: Lighthouse/Teku over TCP+QUIC, 4-5 outbound peers, only goodbye was Teku 130 (too many peers). 0 error-level lines, 2 startup warns. Replied issuecomment-6363694909; in-thread on Codex P1 discussion_r4358961033 (moot post-reset). PR body left as is.
- [x] SIGINT pid 1927304 at 11:20:09, graceful exit in 2s. Data/logs kept in ~/devnet-runs/pr10457-ephemery-165-20261023/.
- [x] Backlog/checklist updated; notification marked done.

## Interim observations
Python urllib asset probe got403; Node fetch and actual Lodestar automatic downloader returned200. Corrected a wrong log filename (rotation suffix) and ENR accessor in read-only diagnostics. No production behavior conclusions from those local probe errors.
Initial discovery took~90s; first peer connected and genesis sync reachedslot287 at11:03:30UTC. Bootnodes with eth2 advertise same forkDigest0xdd5cee2e as local.
Public ChainSafe/Ethstaker/Bordel checkpoint genesis fields match iteration165; pandaops endpoint genesis response is stale164, so do not use that response as iteration proof. No source fix indicated.
