Review of "Hybrid Verification — Payload as Pure Verification with Verified Buffer for Execution Requests" Proposal
1. Exploitation of Verified Buffer and Reorg Behavior

Attack Vector: The verified buffer is designed to store execution requests only after EE verification. However, what happens during a reorg that changes the status of the payload (i.e., FULL vs EMPTY) or alters the parent block's execution request verification status? If an execution request is valid in one chain but becomes invalid in another due to a reorg, the verified execution requests stored in the buffer may become stale or inconsistent.

Severity: HIGH

Potential Failure: A reorg could leave a previously valid execution request in the verified buffer, and the next block could incorrectly apply outdated or invalid requests, leading to state inconsistencies. To mitigate this, more robust reorg handling mechanisms should be explicitly defined, potentially involving a reset or validation step for the execution request buffer during chain reorganization.

2. Equivalence of on_block Application vs. Payload States

Attack Vector: The proposal relies on applying the execution requests from the verified buffer before the state transition (on_block). This approach must guarantee that the results are equivalent to applying requests directly from the payload states, which is not trivially proven. Multiple skipped slots, epoch boundaries with EMPTY payloads, or reorgs across epoch boundaries could introduce subtle inconsistencies.

Severity: HIGH

Potential Failure: The key concern here is that by applying execution requests in on_block after starting from block_states, it could lead to discrepancies, especially in edge cases involving skipped slots or when an epoch boundary causes changes in how requests are applied. A formal equivalence proof or extensive testing is needed to ensure that this new method doesn't break the expected behavior of the state transition.

3. Edge Case Scenarios: Epoch Boundary with EMPTY Payload

Attack Vector: The handling of epoch boundaries with EMPTY payloads is critical. In this case, the block_states are expected to remain unchanged, and there is no verified execution request to apply. However, the interaction between the fork-choice level's verified buffer and epoch processing could introduce race conditions or conflicts, especially when combining process_epoch with the verified execution requests.

Severity: MEDIUM

Potential Failure: If the state from a previous epoch, with an EMPTY payload, is re-used without verifying the consistency of the execution requests, this might cause unexpected mutations to state in subsequent epochs. Specifically, the verified buffer should not be accidentally applied in cases where no execution requests are expected due to an EMPTY payload.

4. State Root in ExecutionPayloadEnvelope

Attack Vector: If the process_execution_payload method no longer processes execution requests as part of the state transition, then the state_root included in the ExecutionPayloadEnvelope will reflect only the CL-computable effects and not execution requests. This may result in an inconsistency where the payload's state root doesn't match the actual state after applying the execution requests.

Severity: CRITICAL

Potential Failure: This could lead to consensus-breaking scenarios where nodes reject valid payloads due to a mismatch in state root verification. This breaks the assumption that the state_root field accurately represents the state of the system after execution request processing. A robust solution is needed to reconcile this discrepancy, or the proposal must redefine what the state_root in the envelope represents.

5. In-Place Mutation of Block States in on_execution_payload

Attack Vector: The in-place mutation of block_states via on_execution_payload (to set the availability bit) introduces potential risks to the determinism of checkpoint states. The availability bit is mutated without proper isolation or backup, which could cause non-deterministic behavior when accessing block state after payload application.

Severity: HIGH

Potential Failure: If the availability bit is mutated directly on block_states, it might result in non-deterministic behavior when nodes sync or process historical data. This could affect the consistency of the checkpoint state, especially in cases of reorgs or forks. A more isolated, explicit approach for modifying block_states might be needed to ensure consistency.

6. Memory and DoS Vulnerability with Verified Execution Requests

Attack Vector: An attacker could potentially flood the store.verified_execution_requests with a large number of execution requests that are never validated, effectively consuming memory and causing a DoS vulnerability. This is especially dangerous if the buffer is not bounded or cleaned up periodically.

Severity: MEDIUM

Potential Failure: Without a garbage collection strategy or limits on the number of requests that can be stored in verified_execution_requests, this could lead to significant memory bloat. The proposal should include a strategy for pruning verified execution requests once they have been processed or are no longer relevant.

7. Initial Sync / Checkpoint Sync Complexity

Attack Vector: The hybrid approach requires that execution requests be verified and stored at the fork-choice level. During initial sync or checkpoint sync, nodes must account for the possibility that not all execution requests are verified at the time of syncing, potentially causing confusion or desynchronization.

Severity: MEDIUM

Potential Failure: If initial sync or checkpoint sync fails to properly handle the case where execution requests have not yet been verified, nodes could end up with inconsistent state roots or invalid state at checkpoints. To resolve this, a more explicit mechanism for syncing the execution request buffer and ensuring its completeness during initial sync must be defined.

8. Pruning Strategy for Verified Execution Requests

Attack Vector: The proposal does not define a clear strategy for when to prune the entries in verified_execution_requests. Without proper pruning, old or stale requests could accumulate, leading to unbounded memory growth and potential performance degradation.

Severity: LOW

Potential Failure: If entries in verified_execution_requests are not cleared once they have been applied or processed, the buffer could grow indefinitely, leading to memory bloat. The proposal needs to address when and how to prune or reset these entries to avoid memory consumption issues.

9. General Fork-Choice Handling and latest_block_hash Refactor

Attack Vector: The latest_block_hash has been moved from block_states to fork-choice level. This introduces additional complexity in ensuring consistency during fork-choice decisions, especially during reorgs and when determining the latest block hash from potential forks.

Severity: MEDIUM

Potential Failure: The movement of latest_block_hash to the fork-choice level could cause inconsistencies when determining the parent block hash in certain reorg scenarios. Special care must be taken to ensure that the new structure works smoothly across all fork-choice situations, or it could lead to issues with block validation and chain selection. A detailed simulation or testing is required to validate this change.

Conclusion

While the hybrid verification approach offers a strong solution to some of the issues in the earlier proposal, there are several critical concerns, particularly related to the handling of reorgs, state root verification, and the potential for memory-related attacks. A more robust reorg handling mechanism, formal proofs of equivalence for state transition behavior, and better memory management strategies are crucial to ensure this proposal's viability in production environments.