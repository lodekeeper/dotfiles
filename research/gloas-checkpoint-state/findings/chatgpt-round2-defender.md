Argument in Favor of the "Payload as Pre-State Transition" Proposal

This proposal, which suggests deferring payload effects and applying them as a pre-state transition before the state transition function (state_transition) in the Ethereum consensus protocol, addresses several challenges in the current design, particularly the complexity associated with the two-state store approach in Gloas (ePBS). Below is a detailed argument in favor of this proposal, covering all specified points.

1. Simplification over Current Gloas

In the current Gloas (ePBS) specification, the on_block function branches based on whether the parent block's payload is FULL or EMPTY, choosing between block_states and payload_states to select the appropriate starting state. This introduces unnecessary complexity, as it forces nodes to maintain two distinct state stores and require additional branching logic to determine which store to use based on the parent block's payload status.

Cognitive Complexity Comparison:

Current Gloas: The cognitive burden on developers and implementers is relatively high, as they must reason about the correctness of two parallel state stores and their interaction. This branching is especially problematic when trying to reason about the effects of one store over another, and can lead to subtle bugs when payloads change or aren't fully available.

Proposal ("Payload as Pre-State Transition"): By eliminating the need for payload_states, the proposal simplifies the flow by consolidating the state store into a single block_states store. The on_block flow is linear: assertions, state copying, application of payload effects, followed by the state transition. This is simpler to understand, test, and implement, as it reduces branching and makes the state flow more deterministic.

The cleaner approach helps reduce the mental load on both developers and validators who need to track and maintain consistency across states.

2. Precedent in Other Protocols

The concept of applying "pre-state transitions" before a main state transition is not new and has precedent in other blockchain protocols. Below are a few examples:

Cosmos SDK (BeginBlocker): The BeginBlocker function in Cosmos SDK applies block-level state mutations (such as processing transactions, updating state, and validating conditions) before the core state transition logic is executed. This mirrors the idea of deferring payload effects (like execution requests and block hash updates) to be processed before the actual state transition.

Solana: Solana applies transaction preprocessing before block processing, including ensuring that block and transaction data are prepared and validated prior to state updates. This allows for a separation of concerns between validation and actual state transition.

Bitcoin: While Bitcoin doesn't have the complexity of a beacon chain-like state transition, the principle of applying certain operations in a separate "pre-state" step before final block validation can be found in its transaction validation process before state changes (such as the UTXO set update).

The pre-state transition concept is consistent with existing industry patterns, indicating that it is a widely understood and effective method for handling similar state mutation challenges in blockchain protocols.

3. Audit Scope

The proposed approach makes the pre-state mutation bounded and easier to audit because:

Mutations:

Pending execution requests are clearly defined and deterministically verified. They are either valid or not based on the verified execution requests.

Availability bit: This flag is simply a boolean toggle based on the parent block’s status and is deterministic.

Latest block hash: This is updated directly from the parent’s payload and is also deterministic.

Each mutation is independent and based solely on the parent state and the payload, making them easy to reason about. Given the same inputs (parent state and payload), the mutations will always produce the same results. This greatly simplifies auditing and reasoning about the code.

4. Alternative Cost

Passing Store to state_transition (Fork-choice-aware): Making the store fork-choice-aware within the state_transition would introduce additional complexity in the form of maintaining fork-specific state within the state transition function. This increases the risk of bugs and the difficulty of ensuring that all state transitions respect the correct fork choice without side effects.

Maintaining Two State Stores: Maintaining two state stores (block_states and payload_states) involves additional memory overhead and requires complex branching logic in on_block to select the correct starting state. This creates additional complexity in the implementation, increases the likelihood of edge cases, and requires rigorous testing to ensure consistency.

The pre-state transition proposal eliminates these alternatives, offering a much simpler and more maintainable solution, reducing implementation complexity and potential bugs.

5. "Pure state_transition" Invariant

The current Gloas specification already breaks the "pure state transition" invariant because it branches between block_states and payload_states based on the fork-choice-level knowledge (parent payload status). This introduces fork-choice contamination into the state transition, as different states can be selected based on the availability of the parent payload, violating the principle that state transitions should be deterministic and independent of fork choice.

The proposal restores the pure state transition invariant by deferring payload effects before the state transition is executed, thus eliminating the need for fork-specific logic inside the state transition function itself.

6. Checkpoint State Determinism

This proposal solves the checkpoint state ambiguity (as raised in consensus-specs#5074) by applying payload effects before the state transition function. By applying these effects in a controlled, deterministic manner prior to state transition, the final state is guaranteed to be the same regardless of whether the payload was fully available or not. Since all payload-dependent mutations are applied beforehand, the finalized state is independent of the payload status at the time of finalization, thus ensuring determinism in the checkpoint state.

This approach addresses the ambiguity problem thoroughly. There are no remaining edge cases because the pre-state transition ensures all state mutations are handled before the state transition begins, making the final state independent of the fork-choice-specific payload.

7. Implementation Simplicity

From a client implementer’s perspective, the flow of "apply known mutations then call state_transition" is simpler than maintaining two parallel state caches and deciding which one to use based on the payload status. Implementing this proposal requires fewer branching conditions and simplifies testing and debugging. It also avoids potential bugs related to the complex state handling required when maintaining two state stores.

The simplicity of having one store (block_states) and a clear flow for applying the payload effects before the state transition makes the implementation easier to reason about and faster to implement and test.

8. Optimistic Sync Benefit

Optimistic sync benefits from this approach because the state mutations from the payload (such as execution requests) are decoupled from the core consensus logic. By applying payload mutations independently of the execution state, optimistic syncing can proceed without being impacted by whether the payload data has been fully processed. This allows for quicker syncing and verification of blocks, reducing the need to wait for payload validation before advancing in the chain, improving overall system efficiency.

Conclusion

The "Payload as Pre-State Transition" proposal significantly simplifies the state management and transitions in the Ethereum consensus protocol. By eliminating the need for two state stores and applying payload effects in a pre-state transition step, the proposal addresses multiple challenges, including complexity, auditability, and determinism. Furthermore, the approach aligns with proven patterns in other blockchain protocols, reduces spec complexity, and restores the purity of the state transition invariant. As a result, this proposal offers a cleaner, more maintainable solution that improves both implementation and operational efficiency, particularly in the context of optimistic sync.