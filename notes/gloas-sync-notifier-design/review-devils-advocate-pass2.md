# Main remaining objections

🔴 The document still contains a direct semantic contradiction about the FULL case.
Why: Most of the revision correctly says `payload:` should be omitted in the normal FULL path. But the `Edge Cases` section still says:

```text
### Gloas payload full
Show:
- `exec-block:` for the now-current execution payload
- `payload: full(...)`
```

That reintroduces the exact duplication the revision claims to have removed.
Impact: This is not a cosmetic mistake. It will cause implementation drift, bad tests, and another review round arguing about whether FULL should log one row or two.
Alternative: Delete that line and make the FULL rule absolute everywhere: FULL emits only `exec-block:`.

🟡 `exec-block:` is more coherent now, but it is still not truly "stable" in the ordinary operator sense.
Why: The new contract is much better: "the execution block the node would currently build on for the next block." That is at least a real cross-fork meaning. But it still means the same `head:` can legitimately show a different `exec-block:` later when a PENDING head becomes FULL. That is a semantic shift from how people historically read the field.
Impact: Operators can still misread an `exec-block` change with unchanged `head` as a bug or a reorg unless this behavior is called out very explicitly in comments/tests/review notes.
Alternative: Keep the new contract, but stop overselling it as preserving historical meaning unchanged. Say plainly that the field preserves operator usefulness, not strict historical identity.

🟡 The degraded `exec-block: <hash>` fallback is still a weak spot.
Why: It overloads one label with two shapes: fully resolved tuple vs hash-only anchor. That is honest, but it is not clean. Existing tooling and operator habits will treat `exec-block:` as structured.
Impact: Silent format divergence will break grepability and any parser expecting `<status>(<number> <hash>)`.
Alternative: If the degraded path is real, encode it explicitly as `exec-block: unresolved(<hash>)` or similar. Do not make consumers infer degradation from missing structure.

🟡 Atomicity is still underspecified.
Why: The design assumes `exec-block:` and `payload:` describe the same sampled head state, but it does not say the notifier must derive both from one consistent snapshot. In Gloas, reveal/import timing matters.
Impact: Without an explicit snapshot rule, the implementation can log an inherited `exec-block:` from one view of head state and `payload: pending|empty` from another.
Alternative: Add one sentence to the implementation section: both rows must be derived from the same head/fork-choice snapshot or not emitted together.

🟢 `empty` is still slightly too diagnosis-shaped.
Why: The revised text is better, but `empty = settled missed/absent case` still sounds closer to root-cause interpretation than pure observation.
Impact: Probably minor if the implementation already uses a well-defined internal state, but the wording invites operators to read more certainty into it than may be justified.
Alternative: Either define exactly what internal condition maps to `empty`, or phrase it more observationally.

# Did the revision fix the biggest problems?

Mostly yes.

The biggest problems in the previous draft were:
- `prev-payload:` was the wrong abstraction
- FULL duplicated the same fact twice
- the document was still too entangled with fork-choice variant bookkeeping

This revision fixes the first two and materially improves the third.

The key improvement is that the design now has a coherent split:
- `exec-block:` = what the node would currently build on next
- `payload:` = only the current head's exceptional lifecycle state

That is a real operator-facing model. It is no longer fighting itself the way the previous version did.

What is left are cleanup issues and one format-design question, not a fundamentally broken abstraction.

# What would you still change?

1. Make the FULL rule globally consistent.
   - Remove the stray `payload: full(...)` language from `Edge Cases`.
   - State once, unambiguously: FULL means no `payload:` row.

2. Tighten the degraded-path formatting.
   - Prefer `exec-block: unresolved(<hash>)` over bare `exec-block: <hash>`.
   - That preserves honesty without weakening the shape of the field.

3. Add an atomic snapshot requirement.
   - `exec-block:` and `payload:` must be computed from the same head/fork-choice view.

4. Tone down the "preserve semantics" claim.
   - The field preserves operator intent across forks, not literal historical identity.
   - That is still good enough, and more truthful.

5. Tighten the wording around `empty`.
   - Either define the exact state transition that produces it, or use wording that stays observational.

# Is the design acceptable now?

Yes, with edits.

The revised design is now broadly coherent and much closer to the right abstraction. I would not block it on architecture anymore. I would block it only until the internal contradiction about FULL is removed and the degraded/atomicity semantics are tightened, because those are the remaining places where implementation confusion can still leak into the notifier.