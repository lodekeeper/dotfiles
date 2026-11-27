# PR #10657 security review

Reviewer: review-security
Reviewed commit: 8e82b32aaab2f2adf68ea8e26e93b7e9a29ba520

No security vulnerabilities identified.

## Scope and checks

- Reviewed all changed handlers, snapshot collection, surrounding column canonical-root resolution, request decoding assumptions, and the regression fixtures.
- The collector copies only scalar records inside the capped requested slot interval plus one predecessor. Even during an extended finality delay, a stalled peer no longer retains the entire ancestor-node array through this path.
- Parent traversal can still be long for an old requested interval, but getAllAncestorNodes already walked the entire chain without a traversal cap. This is not a newly introduced peer-triggerable unbounded traversal.
- The head and selected FULL/EMPTY ancestors are snapshotted synchronously before serving reads. Late payload arrival or head reorganization cannot change the stored payload-status choices. Serving a PENDING Gloas beacon head does not skip beacon-block import validation; data columns still require FULL status.
- Count caps precede the new safe-integer end checks. Unsafe individual uint64s are rejected by the existing SSZ decoding boundary. The removed archive entry limit was redundant with the capped exclusive slot interval, which has at most one beacon block per slot.
- Reconciled the saved maintainer feedback and follow-up: redundant start-slot checks and the archive limit were removed; real ProtoArray Gloas fixtures replaced fabricated ancestry; the PENDING-head change is documented. No unresolved inline security finding was present.

No source edits or tests were run. Parent owns test execution and publishing.
