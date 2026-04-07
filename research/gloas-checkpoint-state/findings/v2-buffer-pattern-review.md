Here’s an aggressive breakdown of the questions at hand, focusing on the design decision to use the fork-choice-level buffer for deferring payload effects.

1. Is the fork-choice-level buffer a valid alternative to putting execution_requests in the bid? Or is Potuz right that the bid is the only way?

Counterpoint to Potuz: The fork-choice-level buffer is a valid alternative. While it's true that the bid approach allows for tightly coupled execution requests and bids, the buffer mechanism doesn’t necessarily require putting execution requests in the bid itself. Storing execution requests in the buffer at the fork-choice level (in store.verified_execution_requests) decouples the proposer’s job from execution request handling. The fork-choice handles the propagation of those requests at the right time. This approach allows for more flexible management of state, leveraging the concept of delayed execution while still preserving integrity across blocks.

Considerations:

Potuz's idea of sending execution requests with the bid doesn’t fundamentally solve the issue of post-state determinism, given the uncertainty around missed slots and reorgs.

The buffer mechanism still operates under the premise that execution requests are stored and applied before the state transition of the next block. This design doesn’t eliminate the need for validation but defers its application, reducing complexity in the proposer’s role.

2. What are the failure modes of the buffer approach?

Missed slots (100 slots before the next block):

In the case of 100 missed slots, the issue isn’t whether the requests are valid but rather whether the context in which those requests were made is still relevant.

Ethereum's consensus already includes tolerance for stale or delayed information (pending requests). If an execution request was verified on the current chain state, but the next state differs drastically (due to missed slots), the request might be applied in an inconsistent state, resulting in incorrect execution or reverts.

This failure is mitigated if the system can track and revalidate payloads and execution requests on the arrival of the new block, making sure they align with the actual chain state.

Reorg removing the payload but the buffer entry persists:

This introduces the possibility of executing requests that no longer apply due to the reorg. The buffer’s existence at the fork-choice level doesn’t automatically resolve this.

Failure mode: The proposer may end up applying execution requests that were valid in one chain state but are invalid in the new chain after a reorg. This could lead to a broken state transition. A solution could involve a mechanism to invalidate or discard execution requests that no longer match the final chain state after a reorg.

Proposer gaming the system by building on an EMPTY parent:

Yes, a proposer can theoretically choose to build on an empty parent to avoid certain execution requests.

Failure mode: If a proposer knows the buffer has unsatisfied execution requests that could negatively impact their preferred state, they might try to bypass those by selecting an empty parent, effectively stalling execution requests. This could lead to an inefficient consensus process where execution is delayed or blocked due to malicious behavior at the proposer level.

3. Potuz says "results may vary depending on how many missed slots there are." This is true for both approaches (bid and buffer). Is this actually a problem, or is this just how pending queues work in Ethereum consensus?

Yes, it's a problem, but it’s inherent in Ethereum's consensus model:

Missed slots or delays in the processing of requests aren’t new challenges in Ethereum. The actual issue lies in how those pending requests are applied or invalidated after a delay. For the buffer approach, if the missed slots cause a significant divergence between the requested execution and the chain state, this could result in errors or misaligned state transitions.

The difference is that the bid approach would put these requests within the bid, ensuring that they are immediately tied to the block context. The buffer relies on deferred execution, which inherently comes with a greater possibility of deviation.

In short, the missed slot issue is common in pending transaction handling but becomes more noticeable when execution isn’t immediate. It doesn’t break Ethereum, but it does complicate things, requiring checks to ensure state correctness.

4. Is moving execution request application responsibility to fork-choice level (on_block) rather than state-transition level (process_execution_payload) fundamentally unsound? Does it break any invariants?

Fundamentally unsound?: Moving the responsibility to the fork-choice level isn’t unsound, but it’s a significant shift in how Ethereum’s consensus has typically handled execution. The state transition logic has historically been tightly coupled to the process of payload verification and application.

Invariants: The primary concern is whether deferring execution will break the consistency of Ethereum’s execution environment. If the buffer is allowed to alter state transitions indirectly, the critical invariant of state consistency across blocks must be preserved. This requires robust synchronization between the execution requests in the buffer and the actual state. If the buffer contains incorrect or outdated requests, this could cause the state transition to break. Proper tracking and validation need to be in place to ensure no invalid state is applied.

5. During checkpoint sync, the syncing node doesn't have store.verified_execution_requests. How does it reconstruct the correct state? Is this a gap?

Sync node gap:

During checkpoint sync, the syncing node’s lack of store.verified_execution_requests could lead to issues when trying to apply deferred execution requests that are expected to be verified at the fork-choice level. This is a potential gap.

Failure mode: A syncing node, not having the full set of execution requests, could process an incomplete state transition, causing discrepancies with other nodes that have fully synced state transitions. If the execution requests are applied incorrectly or missed due to lack of sync information, this could lead to inconsistencies in state and validation.

The syncing process needs to ensure that any missed execution requests are fetched from historical data or reconstructed in some manner, otherwise it risks applying incorrect state changes.

Conclusion:
The buffer approach is a valid alternative, but it introduces complexity, particularly in cases of reorgs, missed slots, and proposer gaming. The trade-off is flexibility in handling execution requests versus potential risks in state consistency. To make the fork-choice-level buffer work reliably, it will require strong mechanisms to handle missed slots, state revalidation post-reorg, and proposer behavior, making sure no one can game the system. The lack of execution requests during checkpoint sync is a clear gap that needs to be addressed by ensuring proper reconstruction of state and handling of deferred execution.