# Public text QA

Approved with one minor terminology correction: in bot_timeout, replace "both RPC clients" with "both the JSON-RPC and REST clients". The fallback is genuinely 12,000 ms in both transport paths, as checked in this review.

All substantive claims are supported by inspected code or the parent's reported verification: 19 identity tests and 51 total focused tests passed at 8692572, exact-head build/type/lint/unit CI green, fixed slot-0/slot-1 timer assertions, and real execution.timeout fallback.

Thread parent IDs are correct: identity 4330846964 is our P2; timeout 4263645869 is the original bot P2; Kurtosis 4330958984 is nflaig's request, with Marko's "will do" reply 4330975745 in that thread.

The COMMENT event and explicit pending-final-approval language are consistent. The draft does not claim Kurtosis ran, and correctly separates deterministic polling tests from end-to-end activation/discovery/bidding evidence. Agreeing to future head_v2 tracking and pending-payment/withdrawal reconciliation does not imply agreement to defer the requested runtime validation.

No other corrections required. No source or GitHub writes performed.
