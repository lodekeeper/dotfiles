# Main objections

🔴 `exec-block:` is no longer actually “stable”; the proposal quietly changes what operators think it refers to.
Why: Pre-Gloas, `exec-block:` effectively meant “the execution payload in the head.” The proposal rewrites that to “the execution block the head is anchored to / what the next block will build on.” Those are only equivalent pre-Gloas and Gloas-FULL. In Gloas-PENDING/EMPTY, `exec-block:` now points at the parent execution block while the beacon head is a different object entirely.
Impact: Operators will read `exec-block:` as “the head’s execution block” because that is what the field historically looked like. In the exact states where clarity matters most, the row becomes easy to misread.
Alternative: Admit the semantic split instead of pretending continuity. Keep `exec-block:` as the concrete execution block you actually have, and add a separate `head-payload:`/`payload-status:` row only when the current head is not full.

🔴 The design claims to avoid abstraction leakage, but it still smuggles fork-choice internals into user semantics.
Why: `payload: pending|empty|full` is still a thin wrapper over internal variant state. Renaming the leak does not remove it. The proposal also depends on parent-variant resolution for number/status, then tells itself that the leak is gone because the log line no longer says `prev-payload:`.
Impact: The implementation remains coupled to fork-choice bookkeeping, but now the user-facing story pretends it is a simple operator abstraction. That mismatch is exactly how notifiers become misleading.
Alternative: If Nico’s point is “do not expose variant bookkeeping,” then do the minimal thing: show only concrete operator-relevant anomalies. Example: emit `payload-status: pending` or `payload-status: empty` only when the head payload is not fully available. Otherwise keep the legacy line alone.

🔴 `payload:` duplicates `exec-block:` badly enough to make the healthy path noisy and the unhealthy path ambiguous.
Why: In Gloas-FULL, both rows print the same number/hash. That is not “intentional redundancy”; it is evidence the model is fighting itself. In Gloas-PENDING/EMPTY, `exec-block:` points to the inherited parent while `payload:` describes the head, so the operator gets two different objects with no explicit statement that they are different objects.
Impact: The log line becomes harder, not easier, to reason about. Healthy FULL output wastes space on duplicate facts; unhealthy output forces the operator to mentally reconstruct which row refers to the head and which refers to the inherited execution anchor.
Alternative: Make `payload:` conditional. Do not print it for FULL. Only print `payload: pending` / `payload: empty` when there is genuinely new information beyond `exec-block:`.

🟡 The degraded `exec-block: <hash>` fallback is a format regression disguised as honesty.
Why: The design starts from “keep pre-Gloas semantics stable,” then introduces a new, structurally different form with missing status and number. That breaks comparability, parsing, grep habits, and operator intuition. It also weakens the meaning of the label: now `exec-block:` can mean either “validated execution block tuple” or “some anchor hash we think matters.”
Impact: Consumers of the notifier lose a stable shape. Humans and tooling will both mis-handle the degraded case.
Alternative: If you cannot resolve the block to the same confidence level, say that explicitly with a distinct label such as `exec-anchor-hash:` or `exec-block: unresolved(<hash>)`. Do not silently overload the main row.

🟡 The proposal overstates a shaky implementation invariant.
Why: It leans heavily on “`ProtoBlock.executionPayloadBlockHash` is already set to bid parent hash, therefore the notifier naturally has the execution anchor.” Hash, maybe. Number/status, not necessarily. The document itself has to invent a degraded mode because the supposedly natural invariant is incomplete.
Impact: The design reads cleaner on paper than it will behave in real code. The notifier logic still depends on partial parent resolution, racey reveal timing, and fork-choice state availability.
Alternative: Design around the weakest reliable fact, not the strongest hoped-for one. If only the hash is guaranteed early, then treat early Gloas state as a payload-status problem, not as a fully reconstructed `exec-block:` story.

🟡 `empty` is underspecified for operators.
Why: The document says `empty` is the “settled missed/absent case,” but that still compresses multiple realities: missed reveal, no payload expected, not yet fetched but later impossible, or implementation-specific no-payload handling. The text wants a clean operator term without proving that all underlying causes are operationally equivalent.
Impact: Operators may infer a stronger diagnosis than the system can actually support.
Alternative: Either tighten the contract around exactly what event produces `empty`, or use a more obviously observational term such as `payload: absent` and document what it does not imply.

🟢 The proposal says it wants compact logs, then chooses the least compact version of the design.
Why: It keeps legacy `exec-block:`, adds `payload:` always for Gloas, accepts duplicate FULL output, and adds degraded-format branching.
Impact: More surface area, more docs, more reviewer confusion, more test cases.
Alternative: Preserve the old line and add one small exceptional row only when Gloas introduces a non-legacy condition.

# Best alternative if you reject the current recommendation

Reject the “always print `exec-block` + always print `payload` for Gloas” recommendation.

Use a narrower design:

- Keep `exec-block:` as the legacy row.
- For Gloas, print an extra row only when the head payload is not in the ordinary FULL state.
- Suggested shape:
  - Gloas FULL: no extra row; just `exec-block:`
  - Gloas PENDING: `payload-status: pending`
  - Gloas EMPTY: `payload-status: empty`
- If you truly need the bid parent hash for debugging before full resolution, use a clearly distinct field such as `exec-anchor:` rather than overloading `exec-block:`.

Why this is better:

- It matches Nico’s feedback more closely: do not promote fork-choice bookkeeping into a permanent operator abstraction.
- It keeps the common case compact.
- It avoids the worst duplication in FULL.
- It makes anomalous Gloas states stand out instead of normalizing them into every synced line.
- It avoids pretending that `exec-block:` still means exactly what it used to mean when it does not.

If you insist on keeping a payload row, at minimum suppress it in FULL. Printing the same tuple twice is bad design, not a harmless tradeoff.

# Missing edge cases

- What happens when the bid `parent_block_hash` is known but refers to an execution block the node has not validated locally yet? `valid(...)` becomes especially dangerous here.
- What happens if fork-choice parent resolution races with reveal/import and the notifier samples halfway through? The design assumes a clean state snapshot.
- What happens if the head changes between computing `exec-block:` and `payload:`? You can easily log a parent anchor for one head and a payload state for another unless resolution is atomic.
- What happens for reorgs where the new head is PENDING but the old head was FULL? The operator may see what looks like a backwards execution movement with no explicit explanation.
- What happens if the parent variant is pruned, unavailable, or inconsistent during startup/recovery? The degraded form is mentioned, but the operational meaning is not.
- What happens to downstream tooling that parses `exec-block: <status>(<number> <hash>)` today? The new hash-only form is a silent breaking change.
- What happens if `empty` later turns out not to be terminal in some implementation path? The design treats it as settled.
- What happens in mixed-version fleets where some nodes emit only legacy `exec-block:` and others emit the new Gloas rows? The comparability story is weak.

# Is the design acceptable as-is?

No.

The core mistake is pretending there is one neat “stable” `exec-block:` abstraction when Gloas has split the underlying meaning. The proposal then papers over that split by adding `payload:` everywhere, which produces duplication in FULL and ambiguity in PENDING/EMPTY. A smaller design — legacy `exec-block:` plus an extra status row only for abnormal/non-FULL Gloas states — is cleaner, closer to Nico’s feedback, and less likely to confuse operators.