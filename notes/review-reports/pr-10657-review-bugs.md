# PR #10657 bug review

Reviewer: review-bugs
Reviewed commit: 8e82b32aaab2f2adf68ea8e26e93b7e9a29ba520

## Result

No functional bugs found.

## Inspection

Reviewed every changed production and test file and all prior feedback. Traced collectHeadRange through ForkChoice.iterateAncestorBlocks and ProtoArray.iterateAncestorNodes/getParentNodeIndex, including the head-excluding iterator contract and Gloas FULL/EMPTY parent selection. Checked explicit PENDING-head inclusion for block serving, FULL-only column serving, scalar copy isolation from later mutations/reorgs, ascending response order, sparse ranges, one predecessor for skipped-slot detection, finalized archive boundaries, capped counts and safe exclusive-end checks. The snapshot includes at most the requested slot records plus one predecessor; traversal time remains proportional to ancestry depth as documented. Read regression fixtures using real ProtoArray insertions, payload arrivals, and replacement heads.

## Verification boundary

Static review of the exact-head worktree and saved PR feedback. No source edits or GitHub writes. Test execution is owned by the parent reviewer and was not duplicated.
