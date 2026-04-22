# Gloas Notifier UX Evaluation Criteria

Last updated: 2026-04-22 UTC

## Purpose

These criteria define what a *good* notifier display should let an operator infer at a glance, independent of the underlying implementation semantics.

They are meant to help choose between the candidate display shapes in `UX_ALTERNATIVES.md`.

## Core operator questions

A single synced log line should make it as easy as possible to answer:

1. **What execution block would the node build on next?**
2. **Did the build target advance compared with the previous slot?**
3. **If the build target did *not* advance, is that because the current head's payload was empty / unresolved, or for some other reason?**
4. **Is the current head in a normal/happy state or an exceptional one?**
5. **Am I seeing a user-facing protocol fact, or leaking an internal fork-choice implementation detail?**

## Display quality criteria

### 1. Stable primary row
There should be one obvious primary execution row that keeps the same meaning across pre-Gloas and Gloas.

### 2. Happy-path compactness
The normal FULL / healthy case should stay visually close to pre-Gloas output. If the display gets noisier in the common path, the added information has to clearly justify the cost.

### 3. Repeated-hash interpretability
If the same execution hash appears in two consecutive slots, the operator should be able to understand whether that is:
- expected carry-forward because the newer head had no payload
- temporary unresolved state
- or something else unexpected

### 4. No extra abstraction debt
The display should avoid inventing a new user-facing concept (for example a parent-payload bookkeeping row) unless it materially improves operator understanding.

### 5. Honest degraded mode
If only partial information is known, the display should make that explicit instead of implying false precision.

### 6. Low parsing burden
A reader should not need to mentally join multiple internal concepts just to understand the line. If a notation needs a long explanation to make sense, it is probably a poor log UX.

## Practical decision pressure

These criteria suggest a tension:
- **compactness** pushes toward a single `exec-block` row
- **interpretability of repeated hashes** pushes toward some explicit annotation for EMPTY / PENDING

So the best solution is likely one that:
- keeps one stable primary row
- adds the smallest possible *exceptional-state annotation* only when needed
- avoids introducing a second parent-oriented abstraction

## Strong warning sign

A candidate display should be rejected if, after reading one example line, a reviewer still has to ask:

> "Wait, is this telling me about the current head's payload, the parent beacon block's payload, or the execution block the next proposer will build on?"

If that ambiguity remains, the UX is not clean enough.

## Current lean before advisor reply

Best likely shape under these criteria:
- keep `exec-block` as the stable primary row
- add a minimal exceptional-state annotation only when helpful
- prefer wording that describes the *current head outcome* rather than introducing a separate `prev-payload` style concept
