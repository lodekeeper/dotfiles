Review of the Hybrid Verification — Payload as Pure Verification with Verified Buffer for Execution Requests Proposal
1. Verified Buffer Approach and Execution Request Timing Semantics: HIGH Confidence

Claim: The verified buffer approach preserves execution request timing semantics by ensuring that execution requests are applied before the state transition in the subsequent block, identical to the current approach in the spec.

Analysis: The proposal successfully moves execution requests from being directly processed in process_execution_payload to being verified and stored at the fork-choice level. This ensures that execution requests are applied at the same time, just before the state_transition in on_block. This guarantees that timing semantics are preserved because the execution requests from a slot are applied before the transition of the next slot, ensuring no change in the ordering of operations. The approach essentially swaps the state mutation location but keeps the order intact.

Conclusion: This claim holds true, and the transition is seamless without introducing any significant timing deviation.

2. Block States and Payload Independence: HIGH Confidence

Claim: Block states are independent of the payload status under this design.

Analysis: The proposal removes the payload_states and instead uses store.verified_execution_requests for the fork-choice logic. Execution requests are never directly stored in block_states, which means the CL state in block_states does not depend on whether the payload is FULL or EMPTY. This independence is fundamental because it ensures that the finalized state for any block is derived solely from the beacon block chain (FFG), without ambiguity from execution requests in the payload.

Conclusion: This design decision ensures that block_states is independent of payload status and addresses any ambiguity related to execution request application. High confidence in its correctness.

3. Checkpoint State Determinism in Edge Cases: MEDIUM Confidence

Claim: The checkpoint state determinism holds in all edge cases (skipped slots, reorgs, multiple empty slots).

Analysis: The hybrid approach handles edge cases like skipped slots and reorgs by ensuring that block_states is used as the source of truth, with execution requests applied only at the fork-choice level. This means the state is consistently deterministically derived from the beacon chain's finalized state, irrespective of whether the payload was FULL or EMPTY. However, specific edge cases like multiple skipped slots or complex reorgs (with potential forks) still require thorough testing to ensure that the behavior holds across different network conditions.

Conclusion: The design appears robust, but further testing is required to confirm that the determinism holds in all edge cases, especially those that involve multiple skipped slots or reorgs.

4. Removal of Payload States and Safety for Fork Choice: HIGH Confidence

Claim: Removing payload_states is safe for fork choice.

Analysis: By shifting the application of execution requests to the fork-choice level and removing the payload_states from the Store, the proposal simplifies the state management while preserving fork-choice consistency. Since the decision to apply execution requests (whether a block is FULL or EMPTY) is already captured by store.verified_execution_requests, this approach ensures that the fork-choice tree remains unaffected by the removal of payload_states. The fork-choice logic remains robust, and the hybrid design does not introduce any ambiguity or inconsistency in the block selection process.

Conclusion: This claim holds true, and the removal of payload_states does not break fork choice. High confidence in the claim.

5. State Root Semantics in ExecutionPayloadEnvelope: MEDIUM Confidence

Claim: The state root semantics change in ExecutionPayloadEnvelope, with the state root now reflecting only the minimal bookkeeping state (availability bit, latest_block_hash), not execution request processing.

Analysis: This change to the state_root semantics is technically sound but introduces a subtle difference. The state root previously represented the full state, including execution requests. Now, it only includes minimal changes like the availability bit and the latest_block_hash, which simplifies the state verification process but might affect certain cryptographic verifications if an external observer is looking for a full snapshot of the state, including execution requests.

Conclusion: The change is technically viable but requires careful consideration of how it affects the overall state verification process. Medium confidence in this claim due to potential subtle impacts on specific external use cases or verification mechanisms.

Additional Strengths:

Simplified API and Checkpoint Logic: The separation of concerns between CL and EL-derived data ensures that the beacon APIs return deterministic results for finalized and justified states, addressing earlier ambiguities regarding payload statuses.

Stronger Trust Model for Execution Requests: By ensuring that execution requests are only applied after EE verification, the proposal strengthens the security model by preventing fraudulent or malformed requests from entering the CL state.

No Change to Bid Size: The bid size remains unchanged since execution requests are not included in the bid, which ensures there is no additional bandwidth overhead.

Flagged Weaknesses or Overstated Claims:

Edge Case Behavior: The claim that checkpoint state determinism holds across all edge cases (e.g., skipped slots, reorgs) should be tested more rigorously. While the design is theoretically sound, practical testing under edge conditions is necessary to validate its robustness.

State Root Semantics Change: The change in how state_root is computed and represented in ExecutionPayloadEnvelope may introduce minor discrepancies in certain cryptographic verifications or external interactions that require a full state snapshot.

Conclusion:

Overall, the proposal strengthens the trust model for execution requests and significantly simplifies the state management by decoupling payload effects from the CL state, providing clarity for both the checkpoint state and the fork-choice logic. The hybrid approach addresses key flaws in previous versions, particularly the handling of execution requests and their verification process. The main concern lies in the need for rigorous testing of edge cases, but the design appears technically sound with high confidence in its core claims.