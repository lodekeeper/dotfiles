# PR #10796 — architecture review

Reviewer: reviewer-architect
Reviewed commit: 0926e6f13fe3e2e89c193794ff26bb7d8d73456f

## Verdict

No architectural concerns — changes align with existing patterns.

No changed-line architectural findings identified.

## Scope and rationale

- The serving bridge applies flow control inside the existing generic async-iterable/event adapter. Credit travels opposite the response through the existing directional worker event bus; it does not introduce reqresp details into sync or chain abstractions.
- The window bounds response items before encoding, while `sendChunks` bounds queued encoded bytes. These address distinct buffering layers, and the encoding generator naturally propagates a paused transport sink back to the bridge consumer. Returning credit when the consumer takes an item permits the documented small lookahead without draining the entire serving response.
- The explicit requester `Infinity` window preserves the pre-existing eager requester behavior. The main-thread network methods consume through the existing exact-one, bounded-array, or sequential collection adapters. The change does not introduce a new requester streaming contract or shift transport concerns into those adapters.
- Fresh drain-event waiting and the close timeout remain encapsulated in `@lodestar/reqresp`. Importing `MAX_CONCURRENT_REQUESTS` adds no package dependency: reqresp already depends on params, and its outbound self-rate-limiter already uses that constant.
- The inbound limit is applied through the existing libp2p protocol-registration API. Its scope is per connection and negotiated protocol, rather than a node-wide memory cap. The bridge window and write-buffer high-water mark are likewise per active request/stream; the implementation does not require a stronger global guarantee for architectural consistency.
- No new technology stack, upward package dependency, state-transition side effect, or validator/beacon-node boundary violation is introduced.

## Review method

Read the exact manifest diff and all supplied issue comments, inline comments, and reviews. Inspected both worker endpoints, the worker event wiring, response encoding, network response collection, outbound rate limiting, and the available libp2p stream/registration implementation for supporting context. No source edits, tests, or GitHub writes performed.
