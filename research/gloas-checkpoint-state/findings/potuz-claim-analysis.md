Let's carefully analyze the positions of Potuz and Dapplion regarding the Gloas (ePBS) checkpoint state ambiguity in Ethereum consensus.

1. Potuz's Claim: Is there an issue with justified balances?

Potuz's position: "There can't be any issues with justified balances nor any consensus split."

Dapplion's counter: He claims that justified balances can be underspecified post-Gloas due to the ambiguity in how the payload is handled. Specifically, Dapplion points out that the justified checkpoint doesn't uniquely determine the justified balances, because it doesn't account for whether the payload is included or not.

Analysis of Dapplion's Scenario:

Justified block at epoch 1, justified at epoch 20: The key issue Dapplion raises is that, under the current spec, the justified block at epoch 1 is referenced at epoch 20. If this block has skipped epochs, and some nodes have the payload while others don't, this can cause significant divergence in the calculated balances at epoch 20.

Payload impact: In Ethereum's Gloas (ePBS), the payload can modify state variables, particularly validator balances (e.g., deposits, exits, slashing). The payload from a justified block at epoch 1, when applied at epoch 20, can greatly influence the balances of validators.

Potuz's Argument vs. Dapplion's Scenario:

Potuz claims that no issues with justified balances can arise, as long as the justified state points to the correct post-CL state at the block with the checkpoint root. However, Dapplion correctly identifies that if some nodes apply the payload and others don’t, the balances can diverge, because the justified checkpoint doesn't capture the full state when the execution payload is missing.

Conclusion: Potuz's view that there cannot be issues with justified balances doesn't fully account for the scenario where different nodes have seen different payloads, which Dapplion rightly highlights as an ambiguity. Hence, Dapplion is correct that justified balances can diverge.

2. API Issue vs. Consensus Impact: Can nodes compute different justified states?

Is this only an API problem? Potuz argues it’s an API issue, suggesting that the core consensus state isn’t impacted by the problem. However, Dapplion's point suggests that this is a consensus issue, because the different state views based on payload availability can lead to divergent views on justified balances, which ultimately influences fork choice and consensus.

Trace through the relevant functions:

store_target_checkpoint_state: This function is key in determining how the state of a block and its payload are tracked. It uses block_states[target.root] to advance to the next epoch boundary, but doesn't necessarily include the payload effects.

Effect of divergent states: If nodes have different views of whether the payload is included, they might end up with different justified balances, affecting their fork choice decisions (i.e., which chain they consider valid). This divergence compromises consensus because nodes need to agree on the same state to avoid splits in the network.

Conclusion: The issue is not only an API problem. As Dapplion correctly points out, it can lead to divergence in fork choice and inconsistent justified balances across nodes. Yes, two spec-compliant nodes can compute different justified states if they disagree on which payloads have been processed, leading to a consensus issue.

3. Scenario with Some Nodes Having Seen the Payload and Others Haven't

In this scenario, some nodes have seen the payload and others haven't, which directly impacts state transition calculations and ultimately, the justified balances.

store_target_checkpoint_state: This function can advance through epoch boundaries, but it doesn't account for the payload effect on balances when different nodes have seen different payloads. If one node has seen the payload and others haven't, this will lead to inconsistent states across nodes, because the justified checkpoint alone doesn't capture all the effects of the execution payload.

Gloas Spec Mechanism: The spec’s reliance on the justified checkpoint root without considering the payload means that nodes that have seen the payload will have different state calculations from nodes that haven't, resulting in possible consensus splits.

Conclusion: The spec doesn’t handle this clearly; it assumes that the checkpoint alone is sufficient for justified balances, but fails to account for payloads that might be missing or delayed in certain nodes. This is a flaw in how the state is handled post-Gloas.

4. Sproul's Suggestion: Change to the Checkpoint Type

Sproul references Dapplion's argument and leans towards changing the Checkpoint type, which he feels is a conceptually correct fix. Let’s assess this:

Current spec: The current spec ties the justified checkpoint to the block root and not the payload. This design creates the ambiguity in how the payload can influence the state.

Changing the Checkpoint Type: If the Checkpoint type is changed to include both the block root and the payload state, it would resolve the ambiguity by making the payload state a first-class part of the justified state. This would remove the possibility of divergent views between nodes, because the justified state would unambiguously include the necessary execution payload effects, thus fixing the issue of missing payloads or divergent states.

Conclusion: Sproul is likely correct that changing the Checkpoint type is a clean and conceptually correct fix, as it would remove the ambiguity that currently exists in how justified balances are calculated and would ensure consensus integrity across nodes.

5. Comparison to the 'Payload as Pre-State Transition' Proposal

Proposal: Moving all payload effects to be applied at the start of the next on_block, eliminating payload_states.

Impact of this proposal: This would simplify the system by ensuring that payload effects are always applied at the start of the next block's processing, rather than as part of a separate state transition. This could resolve the issue of divergent states because all nodes would process the payload effects before any other block effects.

Comparison to changing Checkpoint type: Changing the Checkpoint type would fix the current ambiguity by including the payload in the justification itself, while the payload-as-pre-state-transition proposal would make the payload effects uniform across all nodes by ensuring they are processed consistently at the start of each block. Both approaches address the same issue, but the payload-as-pre-state solution might simplify the design further, as it avoids having separate payload_states.

Conclusion: Both approaches solve the issue, but the payload-as-pre-state proposal might be conceptually cleaner, while the Checkpoint type change is more of a specific adjustment that keeps the checkpoint system in place but modifies it to better represent the full state (including payload).

Final Summary:

Potuz's claim that there can't be issues with justified balances overlooks the scenario where nodes have differing views on payloads, which can cause divergent balances, as Dapplion pointed out.

This is not just an API issue—it affects fork choice consensus, as different nodes can compute different justified states.

The spec does not handle the scenario where some nodes have seen the payload while others haven't, leading to inconsistent states and potential consensus issues.

Sproul's suggestion to change the Checkpoint type is a good fix, as it resolves the ambiguity by including the payload state in the checkpoint.

The 'payload as pre-state transition' proposal is another valid approach, potentially simpler, as it ensures uniform processing of the payload across all nodes at the start of the next block.

In conclusion, both Dapplion's concern and Sproul's proposal have merit, with the payload-as-pre-state transition possibly providing a cleaner long-term solution.