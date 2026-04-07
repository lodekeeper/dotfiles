# Payload Verification Review

---

## Review of Proposal: Payload as Pure Verification

### 1. **Strongest Arguments**
The central argument of this proposal is that by decoupling execution payload processing from the Consensus Layer (CL) state mutations, the finalized state becomes fully deterministic and unambiguous. The approach aligns with the existing design precedent for **withdrawals**, where the payload verification step doesn’t mutate CL state, and it provides the same type of verification for execution-related state changes. 

Key strengths:
- **Deterministic Finalized State:** By ensuring that execution-related state changes are entirely driven by the beacon block and payload verification, the finalized state becomes deterministic, reducing ambiguity.
- **Clean Separation of CL State Mutations:** Following the existing design of withdrawals, the proposal cleanly separates verification from actual state mutations, which simplifies the logic and ensures clarity in the state transition process.
- **Simplified Checkpoint and Beacon API Logic:** By ensuring that all CL-related mutations (like execution requests and withdrawals) are deterministic and based solely on beacon blocks, the proposal simplifies checkpoint state and API logic, resolving ambiguity in state synchronization.

### 2. **Comparison to Alternative Approaches**
- **Get_Ancestor Inference:** The get_ancestor approach would involve inferring the execution payload state from ancestor blocks, potentially leading to ambiguity when the payloads diverge. This approach doesn't guarantee deterministic state because it could be influenced by the payload's availability status (FULL or EMPTY). In contrast, this proposal ensures that execution-related state changes are always processed deterministically in the beacon block, irrespective of the payload’s status.
  
- **Checkpoint Triple:** The checkpoint triple approach can partially resolve ambiguity in some cases but still depends on intermediary states. This proposal eliminates the need for tracking divergent states by simplifying the fork choice logic and removing unnecessary metadata like `payload_states`. The separation of concerns between fork choice and execution state mutations is clearer.

- **Buffer Approach:** The buffer approach involves temporarily storing execution requests and payload states, creating a separate buffer layer to handle these states. While this has its own merits, such as simplifying the management of state divergence during transitions, it still risks reintroducing complexity in the fork choice and synchronization of state across various blocks. This proposal avoids that by ensuring that the payload verification does not require state mutations.

### 3. **Adherence to Existing Gloas Design Patterns**
The proposal follows the existing **withdrawal** pattern by ensuring that execution-related state mutations are pre-computed during the `process_block` phase and verified later. This mirrors the withdrawal processing, where the payload verification step is decoupled from CL state mutations, making the implementation consistent with the established design of the Gloas protocol.

- **Withdrawal Precedent:** The withdrawal processing step works in a similar manner: the execution state related to withdrawals is queued up and only verified during the payload verification step. Extending this pattern to execution requests strengthens the proposal by keeping it consistent with the Gloas design principle that state changes should be deterministic and come from finalized data (the beacon block).

### 4. **Tradeoff Analysis and Acceptability**
- **Bid Size Increases:** The introduction of `execution_requests` in the bid could increase the bid size, especially in scenarios with mass deposit events. However, this is mitigated by the fact that the data is already transmitted in the execution payload and merely shifts where the data is processed. From a network bandwidth perspective, this is a minimal change.
  
- **Execution Requests Committed Before Payload Verification:** This is a legitimate concern, as it means that execution requests could be processed before payload verification, potentially leading to issues if the payload turns out to be invalid. However, the proposal argues that this trust model is already in place with withdrawals. If the builder commits to fraudulent execution requests, the payload verification will fail, leading to the slot being considered EMPTY, and the builder forfeiting their bid. This seems acceptable as it preserves the integrity of the system while holding builders accountable for their commitments.

- **`latest_block_hash` Refactor:** The change in the handling of `latest_block_hash` at the fork-choice level is significant, but it aligns well with the principle that payload status is more appropriately tracked at the fork-choice level, not in the CL state. This tradeoff improves the clarity and separation of responsibilities between fork choice and CL state transitions, although it introduces a moderate refactor.

- **Builder API Changes:** The introduction of execution requests in the bid means that builder APIs need to accommodate this new requirement. The impact on existing infrastructure, like MEV-boost and relays, will need to be carefully considered. However, this is a necessary step for the proposal to work and should be evaluated for feasibility in future implementation stages.

### 5. **Confidence Rating for Each Major Claim**
- **Finalized State Deterministic:** HIGH. The elimination of ambiguous state mutations and the reliance on beacon block roots for execution request processing ensures that the finalized state is deterministic.
  
- **Checkpoint State Unambiguous:** HIGH. By removing the need for divergence in payload state tracking, the checkpoint state becomes deterministic and unambiguous, avoiding unnecessary complexity in synchronization.

- **No `payload_states` Divergence:** HIGH. The proposal’s removal of `payload_states` and the shift to tracking payload status via fork-choice metadata ensure that no state divergence occurs. This is a sound design choice that simplifies state management.

- **Bid Size Impact Acceptable:** MEDIUM. While the bid size increases, the overall impact is modest, with the only potential issue arising from pathological cases. This is acceptable given the tradeoff between verification speed and payload size.

- **Execution Requests Committed Before Payload Verification:** HIGH. This matches the existing withdrawal processing model, where execution requests are trusted and checked for consistency later. It is a reasonable risk, given the accountability of the builder.

- **Refactor of `latest_block_hash`:** MEDIUM. This introduces a moderate refactor, but it is well-aligned with the separation of fork choice and state transitions. The impact is acceptable in terms of protocol clarity, but careful mapping in implementation will be required.

### 6. **Additional Evidence to Strengthen the Proposal**
- **Network Impact Analysis:** While the proposal addresses bid size and the shift in data handling, a more thorough analysis of network bandwidth and latency implications could further strengthen the argument. Specifically, testing the behavior under pathological conditions (e.g., mass deposit events) would help characterize the tradeoffs more clearly.

- **Fork-Choice Impact Simulation:** A detailed simulation of the fork-choice logic under the new model would provide more confidence that the refactor of `latest_block_hash` will work seamlessly in all scenarios. This would help quantify potential risks related to state divergence or incorrect parent-child relationships.

- **Backward Compatibility with MEV-Boost:** An investigation into how the builder API changes might impact MEV-boost infrastructure or other existing relay systems would provide additional assurance that the proposal does not introduce undue disruption to existing ecosystems.

---

**Conclusion:** The proposal to decouple execution payload from the Consensus Layer state transition, making it a pure verification step, represents a sound technical direction that aligns with the Gloas design principles and withdrawal precedents. It offers a deterministic, unambiguous, and simplified state transition model that should improve clarity in state synchronization and API behavior. The tradeoffs are well-characterized, and the proposal builds on existing patterns in the Gloas protocol, making it a robust approach for future implementations.