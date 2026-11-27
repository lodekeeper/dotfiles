# PR #10804 security review

Reviewer: review-security
Reviewed commit: 68f02ac7937ff07827ed23bb0f5df5bd72f64251

No security vulnerabilities identified.

## Scope and checks

- Reviewed both by-root block retrieval paths and their cache, hot database, and archive branches. No existing inline review findings required reconciliation at the saved snapshot.
- Verified that getBlockHexDefaultStatus delegates to getBlockHex, which rejects roots not equal to or descended from the current finalized root through ProtoArray.isFinalizedRootOrDescendant. The new slot comparison is not applied to arbitrary fork roots retained pending pruning. It marks the finalized root itself, not a competing block at the same or an earlier slot.
- The root and finality reads happen synchronously before asynchronous database access. A subsequent finalization can make an earlier false flag stale, but cannot invalidate a true finalized result; this is not an attacker-controlled finality escalation.
- Serialized and object-returning branches use the same condition and preserve execution-optimistic handling. Archive behavior is unchanged.

No source edits or tests were run. Parent owns test execution and publishing.
