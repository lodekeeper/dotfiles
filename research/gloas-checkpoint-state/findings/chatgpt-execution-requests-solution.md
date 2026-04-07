To solve the problem you've presented—ensuring execution requests (like deposits, withdrawals, and consolidations) in ePBS (Ethereum Gloas) can be safely incorporated into CL state without modifying the state during the epoch transition and without trusting the builder’s unverified payload commitment—we need to carefully design a solution that honors your design constraints.

Key Constraints Recap:

No modification to CL state in the payload.

No divergence between FULL and EMPTY payloads, meaning state changes must be independent of whether a payload is processed or not.

No trust in builder’s unverified commitment: We cannot rely on the builder’s pre-commitment to execution requests, as this could lead to fraudulent state changes.

Economic penalties for malicious behavior: The builder loses the bid, but the state corruption from fraudulent execution requests cannot persist if the payload is EMPTY.

Must avoid zk proofs, exotic cryptography, or complex changes for implementation feasibility.

Analyzing Potential Solutions:
1. Deterministic Execution Requests Based on CL State (Like Withdrawals)

One potential solution is to make execution requests deterministic based on the CL state alone, similar to how withdrawals are handled.

Withdrawals: They are CL → EL, and the CL computes payload_expected_withdrawals from validator state deterministically. The builder's payload only verifies consistency with this computation.

Execution Requests (EL → CL): Unlike withdrawals, execution requests (like deposits, exits) originate from smart contract calls, and the CL cannot independently compute or verify them without executing the payload. However, could we determine the validity of these requests based on the CL state alone, in a deterministic fashion, similar to how withdrawals are handled?

Issue: It seems unlikely that we can make execution requests deterministic purely from CL state, because these requests often depend on specific logic embedded in the smart contract. For instance, an exit request or deposit could depend on the current balance or status of a particular account, and these may not be determinable solely from the CL state.

2. Deferred Request Processing (Delaying Execution Requests)

One approach is to defer execution requests until a later point in the process where they do not affect the epoch transition or the CL state during the process_block.

This could be done by buffering execution requests in a provisional queue or pending request pool that is not incorporated into the CL state immediately.

These requests could be verified and processed after payload verification when the EL output is available.

Issue: Deferring requests too long could cause delays and potentially conflict with the epoch transition. Also, handling cases where the payload never arrives (EMPTY case) becomes more complex.

3. Commit-Reveal Scheme for Execution Requests

Another possible solution could involve a commit-reveal scheme:

Commitment: Builders commit to execution requests without revealing their contents initially (using a hash).

Reveal: Once the payload is verified, the builder reveals the actual execution requests and these are processed only after verification.

This would mean the builder commits to execution requests in a way that is cryptographically verifiable, but they are not processed until after verification, preserving the integrity of the state.

Issue: A commitment scheme would likely require significant cryptographic support (not feasible without exotic cryptography) and may reintroduce timing issues with the EMPTY payload if not handled correctly.

4. Reversible Fraudulent Requests

The protocol could enforce that fraudulent requests are always reversible. If a builder submits an invalid or fraudulent execution request, it must be possible to undo any state changes caused by these requests if the payload is found to be invalid.

This could involve buffering state changes in a non-canonical buffer during the verification phase and only committing them to the canonical state after payload verification.

In the case of an EMPTY payload (when no valid payload arrives), these state changes would not be applied, thus preventing permanent corruption of the CL state.

Issue: Reversibility adds complexity to the system. We would need to maintain separate provisional state changes and ensure that invalid requests (especially in case of fraud) can be correctly reverted.

5. Pending Execution Request Queues

Rather than immediately applying execution requests, we could delay their impact on the CL state by putting them in a pending queue. Only once the payload is verified would these requests be incorporated into the state.

This could be accomplished through a two-tier queue system: one for requests that are verified during the process_block phase, and one for requests that are pending verification.

The requests would not be processed until after the verification of the execution payload, ensuring that the builder cannot maliciously alter the state before the verification process.

Issue: This introduces some complexity in terms of handling the state of the pending queue and ensuring that requests are correctly processed post-verification. Additionally, skipped slots (in case of an EMPTY payload) could introduce additional complications regarding the pending request queue.

6. Modify Slot Structure to Ensure Verification First

The slot structure could be modified so that execution request verification happens before the epoch transition. This would involve ensuring that the execution requests are validated and processed as part of the block verification process rather than before it.

This ensures that no state changes from the execution requests are committed until the payload is verified.

Issue: Changing the slot structure could have wide-reaching implications on the protocol's timing and synchronization. It might not be feasible within the current draft spec and could cause inconsistencies with the empty slot handling mechanism.

7. Provisional Buffer for Execution Requests

Instead of allowing execution requests to directly affect the CL state, they could be put into a provisional buffer that would only become canonical after the payload is verified.

This means the requests are held in a temporary space that does not alter the canonical CL state.

Upon payload verification, the requests would be checked, and if valid, they would be moved from the provisional buffer to the canonical state. If the payload is EMPTY, the buffer is discarded.

Issue: Managing the provisional buffer and ensuring it is correctly cleared if the payload is empty introduces complexity. However, this could be a feasible solution if implemented with care.

Conclusion: Fundamental Tension and Key Insight

The fundamental tension here is the need to process execution requests before verifying the payload, but without modifying the CL state or trusting the builder's unverified commitment. This is complicated by the fact that execution requests (like deposits or withdrawals) are EL → CL, meaning the CL cannot validate them independently; it needs the EE for verification.

Unfortunately, there doesn't appear to be a clean solution where execution requests can be incorporated directly into CL state without trusting the builder's payload commitment or introducing complexity that reintroduces ambiguity at the epoch boundary.

However, the provisional buffer approach might be the most feasible. By delaying the incorporation of execution requests until after payload verification, you can avoid modifying the CL state prematurely. This would allow the builder’s payload to be verified without trusting unverified execution requests, while maintaining clear and consistent state transitions.

This approach does require careful handling of provisional state changes and robust rollback mechanisms in the case of EMPTY payloads, but it seems like the most practical way to satisfy the constraints.