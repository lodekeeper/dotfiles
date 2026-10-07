# EIP-8365 self-review and spec compliance

Verdict: faithful (parent self-review requested by Nico).

Reference: ethereum/consensus-specs#5713, exact head `68702a5b201ef974817830fc358baf8fd6035c7b`, `specs/heze/beacon-chain.md` modified `apply_pending_deposit`.

Implementation: `/home/openclaw/lodestar-heze-eip8365/packages/state-transition/src/epoch/processPendingDeposits.ts`.

- The Heze guard uses the application fork computed from state.slot by processPendingDeposits. Following nflaig review 4204379754, the private applyPendingDeposit helper accepts fork: ForkSeq first, passed by both call sites; the public processPendingDeposits signature remains unchanged and compatible with sibling EIP-8015 type widening.
- Prefix check is inside the unknown-validator branch, before signature verification: fork >= Heze and BLS withdrawal prefix returns without registry/balance/cache mutation.
- Existing validator branch unchanged: supplied credentials and deposit signature do not inhibit top-ups.
- No extra prefix whitelist; non-BLS prefixes retain original proof-of-possession behavior.
- Epoch churn/queue processing is unchanged. Rejected deposits consume churn and are dequeued, without refund; deposits queued before Heze are evaluated using the application fork.
- Real-signature unit tests cover accepted execution and compounding prefixes, invalid/valid BLS new deposits and top-ups, both same-pubkey orderings, churn exhaustion and pre-fork pending queue.
- Independent parent Vitest validation: six generated upstream minimal reftests, all passed; eleven focused unit regressions, all passed.
- Implementer broader targeted regressions: twenty passed across pending deposits, lookup and processDeposit.
- Build/type/lint gates recorded separately in validation logs. Initial unrelated failures from stale native1.1/Fastify5.12.1 dependencies were resolved using isolated packages matching current repository pin (native2.0/Fastify5.12.5), without changing code/dependencies/lockfiles or main checkout.
- No independent review agent used; user explicitly requested parent self-review.

## Explicit-fork follow-up validation (2026-10-07 08:23 UTC)
- Signed commit `1bd4bef654f`: behavior-preserving private signature/caller refactor only.
- 20 deposit unit cases and6 exact upstream Heze vectors passed; lint, full type checks and state-transition build passed.
- Independent design/final advisor and bug review approved (review-fork-advisor.md, review-fork-bugs.md).
- Review reply: https://github.com/ChainSafe/lodestar/pull/10292#discussion_r4204652469.
