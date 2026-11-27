# PR #10796 security review

Reviewer: review-security
Reviewed commit: 0926e6f13fe3e2e89c193794ff26bb7d8d73456f

No security vulnerabilities identified.

## Scope and checks

- Reviewed every changed production file and the request/response encoding, timeout, worker-event forwarding, and stream lifecycle around them. No existing inline review findings required reconciliation at the saved snapshot.
- The serving caller grants a finite initial credit window and refunds credit only when an item is consumed. Request and credit events retain FIFO order through the same worker port. The peer cannot inject bridge credits or request IDs directly.
- Cancellation wakes a producer parked on credit, suppresses later responses, invokes the underlying iterator's return, and removes handler state. An already-running iterator read remains subject to its existing completion behavior; this PR does not introduce that limitation.
- The outbound requester retains its pre-existing eager behavior and existing response-count/decoding limits. Passing Infinity does not newly make peer input unbounded.
- Checked the exact lockfile dependency sources, @libp2p/utils 7.4.6 and @chainsafe/libp2p-quic 2.1.6 from their npm release tarballs. AbstractStream retains unsent bytes in writeBuffer; QUIC serializes native writes and buffers subsequent writes there. The high-water check therefore does not bypass QUIC backpressure. Drain/close/abort listeners are removed on every settled wait, and stalled writes and final close have timeout paths.
- libp2p applies maxInboundStreams per connection and protocol, rather than as a shared global quota that one peer could exhaust for other connections.

No source edits or tests were run. Parent owns test execution and publishing.
