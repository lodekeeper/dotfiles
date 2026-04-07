# Devil's Advocate Review

---

### Review of the Proposal: **Payload as Pure Verification**

The proposal makes significant changes to the Ethereum consensus layer (CL) by decoupling execution payloads from the state transition process. It proposes that execution requests be included in the execution payload bid and handled during the `process_block` phase before the execution payload itself is verified, while avoiding state mutations until later. Here are my rigorous challenges to this proposal, breaking it down by each section.

---

### **1. Can a malicious builder exploit the fact that execution requests are processed before EE verification?**

**Challenge:**  
Yes, a malicious builder could exploit this. The proposal allows the builder to commit to execution requests (deposits, withdrawals, consolidations) before the payload is verified. If the builder includes fraudulent or incorrect execution requests, the payload verification later may fail, but **the builder’s actions are already embedded in the state**.

- **What could go wrong:** If the execution request is fraudulent, the builder could still escape penalties as the state would be recorded with these invalid requests, and it might be difficult to identify the fraud immediately. The *EMPTY* state (if the payload never arrives) could potentially let the builder off the hook. This is especially concerning if builders can strategically submit invalid execution requests for some operational advantage (like delaying the finalization of the block and possibly profiting from MEV attacks).
- **Edge case:** What happens if the payload is corrupted during transmission, causing a mismatch in execution requests? The system needs to handle cases where the payload's execution requests differ from those committed in the bid, but there's no explicit mention of slashing or penalties.
- **Severity:** **HIGH**

**Mitigation:**  
A better approach would involve committing to execution requests only after payload verification or introducing a more rigorous punishment system for builders submitting invalid execution requests. **Fixable** with additional checks.

---

### **2. What happens if the bid's execution requests don't match the actual payload?**

**Challenge:**  
If the builder commits to execution requests in the bid and they don’t match the actual payload later on, it leads to an invalid state where the block is effectively “empty” but the builder may still receive the payout, or at least not suffer immediate penalties.

- **What could go wrong:** The proposal doesn't specify a **penalty or slashing mechanism** for invalid execution requests. What happens to the block rewards for the builder? Is there a mechanism to invalidate the block entirely, even if it’s already committed in the state? 
- **Edge case:** Builders who intentionally introduce discrepancies can manipulate the system, waiting for the payload to never arrive and thus **potentially dodging slashing**.
- **Severity:** **CRITICAL** (due to lack of a clear penalty system)

**Mitigation:**  
Add slashing mechanisms or penalties for fraudulent execution request mismatches between the bid and payload. Require some form of cryptographic proof or guarantee on the validity of execution requests at bid time. **Fixable** with added safeguards.

---

### **3. Does removing payload states break any fork-choice invariants?**

**Challenge:**  
The proposal removes `payload_states` from the fork-choice store and replaces it with `payload_block_hashes`. This is a significant change in how fork-choice works, as `payload_states` previously allowed nodes to make decisions based on the state at a given block root.

- **What could go wrong:** Removing `payload_states` could **break the consistency of fork-choice invariants**, as the payload’s effects on the state are no longer tracked explicitly. The shift to using `payload_block_hashes` and assuming fork-choice consistency could lead to **inconsistent states** when blocks are not fully validated (i.e., when they are EMPTY).
- **Edge case:** What happens if the fork choice has to choose between two blocks with conflicting states but no clear signal from the payload? Is there a risk of choosing a block that has become invalid due to mismatched payload requests?
- **Severity:** **HIGH**

**Mitigation:**  
Implement rigorous consistency checks or provide additional guarantees that fork-choice decisions will always align with the state of the latest finalized block, even with the change in how payload data is handled. **Fixable** but requires careful synchronization.

---

### **4. Are there MEV implications of committing to execution requests early?**

**Challenge:**  
Yes, committing to execution requests early could enable MEV (Maximum Extractable Value) opportunities for malicious builders.

- **What could go wrong:** Builders might intentionally create discrepancies between the committed execution requests in the bid and the actual payload. This allows them to **capitalize on timing and bid strategies**. For instance, if they anticipate that a payload will fail or be delayed, they could submit a block with execution requests that optimize for a different set of conditions or future blocks.
- **Severity:** **HIGH** (due to the potential for exploiting the timing window)

**Mitigation:**  
Implement stricter validation on the execution request submission process or require a more transparent bidding and request-validation process. Consider adding a mechanism to penalize builders who exploit these discrepancies for MEV purposes. **Fixable** with stricter checks.

---

### **5. Does this work correctly during inactivity leak / low participation scenarios?**

**Challenge:**  
In inactivity leak or low participation scenarios, blocks may be proposed with no valid execution payloads, leaving the chain with empty blocks.

- **What could go wrong:** The proposal’s handling of the *EMPTY* state could lead to inefficiencies in low-participation scenarios, where **blocks may still be processed and accepted** even when they lack valid payloads. The validation of empty blocks could increase the chances of stalled or inefficient block propagation.
- **Edge case:** If there are low number of builders or a delayed response from the execution engine, **blocks might be recorded but never actually processed**, leading to chain divergence or slow finalization.
- **Severity:** **MEDIUM**

**Mitigation:**  
Introduce a more robust system to handle inactivity leaks, potentially requiring validation of more than just the bid or placing additional constraints on when empty blocks can be accepted. **Fixable** but needs further design.

---

### **6. What about the interaction with optimistic sync?**

**Challenge:**  
The interaction with optimistic sync is not addressed in the proposal. Optimistic synchronization could lead to discrepancies between the block header's state and the payload's state.

- **What could go wrong:** If optimistic sync is used, validators may end up processing blocks that haven’t been fully verified, leading to **incorrect state transitions** or misalignments between the beacon chain and execution engine state.
- **Edge case:** If the sync process doesn’t properly verify execution requests or if optimistic syncing leads to an incorrect assumption about the payload’s validity, the chain could get out of sync or accept invalid blocks.
- **Severity:** **HIGH**

**Mitigation:**  
Clarify the interaction with optimistic sync and make sure that any mechanism in place guarantees state consistency. **Fixable** with more thorough sync handling.

---

### **7. Does this break any existing test vectors or fork choice tests?**

**Challenge:**  
There is no mention of whether the proposal has been tested against existing fork choice tests and vectors.

- **What could go wrong:** The proposal’s removal of `payload_states` and changes to block header handling could break **existing test vectors** that expect these fields to be present or used in fork choice decisions. 
- **Severity:** **MEDIUM**

**Mitigation:**  
Ensure the proposal is tested against existing test vectors to guarantee compatibility with current specifications. **Fixable** through comprehensive testing.

---

### **8. Missing questions:**

- **Bid size limits:** Are there limits on the size of execution requests to prevent excessively large bids?
- **Slashing/penalty mechanism:** What happens if a builder commits to execution requests that the execution engine later rejects?
- **Builder API and MEV-Boost impact:** How do changes to the bid flow affect MEV-Boost infrastructure and relay systems?
- **Gossip validation:** Can execution requests in the bid be validated without execution engine access? This needs clearer handling.
  
**Severity:** **MEDIUM** (Some unanswered questions can lead to inefficiencies or system vulnerabilities)

---

### **Conclusion:**  
The proposal offers significant improvements by ensuring that the finalized state is truly finalized and removing `payload_states` from fork-choice metadata. However, **multiple critical flaws** and edge cases need attention, especially around the potential for malicious exploitation by builders, the handling of mismatches between execution requests and payloads, and ensuring consistency with existing systems like optimistic sync and MEV-Boost. Without addressing these issues, the proposal may lead to significant vulnerabilities and inefficiencies in the protocol.

**Final Rating:** **HIGH** (with several CRITICAL and HIGH issues needing resolution).