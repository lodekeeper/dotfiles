# PR10516 follow-up verification

Source: new replies4480449399 and6658059092, routed2026-11-05T12:38:27Z.
Head:86ec5cb64a582f4a5e5363283149c2aaf32763d4, worktree/home/openclaw/lodestar-pr10516, clean.

- [x] Existing BACKLOG task and build processes reconciled before work.
- [x] Actor gh lodekeeper verified; all inline and issue comment surfaces read (large historic bot benchmark output saved/reviewed as context, not new request).
- [x] Corepack pinned0.36.0 before enable in bothfiles; docs updated.
- [x] Existing production exacthead build passed258s. ResultimageSHA7c0f49dee8d32977e0dbf1341e965c2481ae552876cbd430bccfc6bf5eaa2739, version86ec5cb, Node26.13.0, flagsold8192/semi64.
- [x] Existing devbuild failed ZigdependencyDNS NameServerFailure, notCorepack. Hostnetworkretry canceled, no livebuild remained.
- [x] Devbuild succeeded with --network=host after originalDNSfailure; bothimages version/nativeimport/nodeoptions smokechecks6/6passed onlinux/amd64.
- [x] Semi64 wiring verified onall5launchsurfaces. V8heaplimitNode26 8288→8384MiB matchesNode24.22.2 both8384. Allocationprobe didnotreachnewspacecap, so peaksize table is not independentlyconfirmed. No benchmarkcausality or redeployclaims.
- [x] Exact-head peerQA approved, precision tweak incorporated; inline4480704854 and issue6658562585 posted and verified as lodekeeper.
- [x] BACKLOG and daily note complete; notification/checklist finalization follows after checking no newer comments.

No source, deployment, services, gateway, cron, credentials or workspaceVCS changes authorized/performed. No fullPRapproval implied. Initial filesystemread referenced absent scripts/build_binary.sh; corrected to actual workflow.

CurrentheadCI has Benchmarkfailure (oneworkflow/runcheck countedtwice acrosssurfaces), otherobservedevidence57success. Followupguardexit2 is a falsepositive: “Run allCI on26 only” doesnotclaimsinglefile/scope; Nodeupgrade legitimatelytouches29files. Source/title/body remaincoherent, noauthorPRmetadataeditneeded.

## Outcome
Corepack finding addressed byc3338e98c9 and independently verified at86ec5cb64a; semi64 launch wiring and configured heap limit verified. No fullPR approval. Benchmark still fails and author-owned liveGC/redeploy remains pending. Source and maincheckout untouched; images/logs retained.
