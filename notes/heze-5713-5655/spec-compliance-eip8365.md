# EIP-8365 self-review and spec compliance

Verdict: faithful (parent self-review requested by Nico).

Reference: ethereum/consensus-specs#5713, exact head `68702a5b201ef974817830fc358baf8fd6035c7b`, `specs/heze/beacon-chain.md` modified `apply_pending_deposit`.

Implementation: `/home/openclaw/lodestar-heze-eip8365/packages/state-transition/src/epoch/processPendingDeposits.ts`.

- Fork sequence is computed once in processPendingDeposits and passed to the private applyPendingDeposit helper at both call sites.
- Prefix check is inside the unknown-validator branch, before signature verification: fork >= Heze and BLS withdrawal prefix returns without registry/balance/cache mutation.
- Existing validator branch unchanged: supplied credentials and deposit signature do not inhibit top-ups.
- No extra prefix whitelist; non-BLS prefixes retain original proof-of-possession behavior.
- Epoch churn/queue processing is unchanged. Rejected deposits consume churn and are dequeued, without refund; deposits queued before Heze are evaluated using the application fork.
- Real-signature unit tests cover accepted execution and compounding prefixes, invalid/valid BLS new deposits and top-ups, both same-pubkey orderings, churn exhaustion and pre-fork pending queue.
- Independent parent Vitest validation: six generated upstream minimal reftests, all passed; eleven focused unit regressions, all passed.
- Implementer broader targeted regressions: twenty passed across pending deposits, lookup and processDeposit.
- Build/type/lint gates recorded separately in validation logs. Initial unrelated failures from stale native1.1/Fastify5.12.1 dependencies were resolved using isolated packages matching current repository pin (native2.0/Fastify5.12.5), without changing code/dependencies/lockfiles or main checkout.
- No independent review agent used; user explicitly requested parent self-review.
