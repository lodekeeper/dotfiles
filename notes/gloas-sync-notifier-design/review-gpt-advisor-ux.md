# Current design UX assessment

The current direction is broadly good UX because it keeps `exec-block` as the primary operator anchor and keeps the happy path compact. That matters for notifier output: most of the time, people are scanning for change, not reading prose.

The weak spot is not the semantics but the moment of interpretation. When the same execution hash appears across consecutive slots, the operator's real question is "did we intentionally build on the same target, or am I missing a state transition?" A bare exceptional `payload:` line answers that, but only after a small mental jump. `payload` is short, but it is slightly underspecified as a label.

So the current design is close, but the UX problem is real: repeated hashes are the place where ambiguity shows up, and the annotation should make that repeated-hash case legible immediately.

# Alternative display options

**1. `exec-block` + exceptional `payload: pending|empty`**

This is the best option for compactness and continuity with the existing display. It works if the surrounding notifier context already makes clear that `payload` refers to the slot outcome rather than a second object. Its downside is that the label is terse enough to invite a brief "payload of what?" pause, especially for someone scanning logs quickly.

**2. `exec-block` + `payload-outcome: pending|empty`**

This is the clearest operator-facing wording of the three. It keeps the same model as the current design, but removes most of the ambiguity in the label. The tradeoff is a bit of verbosity, but this is a good place to spend characters because it resolves the exact UX problem at issue.

**3. parent/build-target hash + carry-forward annotation**

This has a real UX intuition behind it: explain repeated hashes by explicitly saying they were carried forward. The problem is that `carried`, `carry-forward`, or similar wording starts to sound like protocol-internal storytelling rather than a simple status line. It also tempts the UI toward annotating `full` in normal cases, which adds noise without adding much operator value.

My read is that this option contains the right insight but the wrong surface wording. The useful part is "help the operator understand repeated hashes"; the risky part is introducing a new term of art to do it.

# Analysis of Nico's parent-hash annotation idea

Nico's instinct is directionally right: always showing the build target and annotating why it did not advance is better UX than leaving repeated hashes unexplained. The operator benefit is immediate: the repeated hash stops looking suspicious and starts looking intentionally explained.

Where I would push back is on expressing that as an explicit parent-oriented or previous-payload concept. Once the display says, in effect, "the previous payload was X, therefore this hash repeated," it starts exposing the mechanism instead of just exposing the state the operator cares about. That increases cognitive load and reopens the abstraction problem you were trying to close.

So I think the idea is good if translated into current-row outcome wording, not good if translated into `prev-payload`, `carried(full)`, or similar phrasing.

In other words:
- **Good UX:** same build-target hash, plus a lightweight annotation that the current slot is `pending` or `empty`
- **Less good UX:** same hash, plus a mini explanation of parent/carry-forward mechanics

If the goal is "when the hash repeats, I instantly know why," then outcome annotation achieves that with less conceptual overhead than carry-forward terminology.

# Recommended display format

Recommend:

- FULL: `exec-block: valid(124 0xdef...)`
- PENDING: `exec-block: valid(123 0xabc...) - payload-outcome: pending`
- EMPTY: `exec-block: valid(123 0xabc...) - payload-outcome: empty`

If brevity is absolutely critical, `payload: pending|empty` is an acceptable fallback. But from a pure UX/display perspective, I would prefer `payload-outcome` over bare `payload`.

I would **not** recommend annotating `full` in the normal case, and I would **not** recommend introducing `carried(...)` wording unless there is strong evidence operators already think in those terms.

# Why

This format best balances the three UX goals that matter here:

1. **Keep the happy path quiet.** FULL should remain a single clean `exec-block` line.
2. **Make repeated hashes self-explanatory.** Non-FULL cases get an explicit annotation right where the operator is already looking.
3. **Avoid new jargon.** `payload-outcome` is descriptive without importing parent-variant or carry-forward concepts into the UI.

So my recommendation is essentially: keep Nico's insight, but not Nico's likely wording. The notifier should explain repeated hashes by annotating the current row's outcome, not by teaching the operator an internal carry-forward model.