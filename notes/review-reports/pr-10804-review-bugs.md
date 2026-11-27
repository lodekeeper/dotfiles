# PR #10804 bug review

Reviewer: review-bugs
Reviewed commit: 68f02ac7937ff07827ed23bb0f5df5bd72f64251

## Result

No functional bugs found.

## Inspection

Reviewed both object and serialized root lookup paths, cache hits and misses, cold-store fallback, and the finalized-slot computation. Traced getBlockHexDefaultStatus through getBlockHex and isFinalizedRootOrDescendant: a conflicting root below finalized is filtered before the new comparison. Traced unfinalized initialization: it inserts a dummy finalized ProtoBlock, so the new getFinalizedBlock lookup does not introduce an unavailable-finalized-root failure there. Read the new tests and all existing feedback.

## Verification boundary

Static review of the exact-head worktree and saved PR feedback. No source edits or GitHub writes. Test execution is owned by the parent reviewer and was not duplicated.
