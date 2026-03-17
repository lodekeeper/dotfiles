# Architecture Critique — Discord Voice Bot

**Reviewer:** Lodekeeper (devil's advocate)  
**Date:** 2026-03-17  
**Document reviewed:** `drafts/architecture.md` (Draft v1)  
**Verdict summary:** Solid framing, meaningful blind spots. Several "it'll be fine" assumptions will bite you in production.

---

## Overall Assessment

The architecture is well-structured and the standalone bridge decision is correct. The evaluation matrix, phased plan, and risk register show mature thinking. But several critical issues are **understated or mischaracterized** — particularly around the shared Discord token, the staging channel IPC pattern, the latency budget optimism, and the CPU safety story on server2. Those four areas alone could sink the project or create hard-to-debug production failures.

---

## Section 1: Recommended Approach

### Evaluation Matrix Issues

**"Development effort: Low" for the Standalone Bridge is wrong.**

5–7 days for a working voice bot in Node.js is *medium* effort, not low. The matrix is inflated against alternatives to make the decision look cleaner than it is. `@discordjs/voice` is sparsely documented, its per-user AudioReceiveStream behavior has subtle edge cases (SSRC demuxing, late-join packets), and you're implementing VAD + turn detection from scratch. None of that is "low" effort.

**"Resource footprint: ~150MB"** looks like a binary-size estimate, not a runtime footprint during an active session. In practice: voice bridge + Deepgram WS SDK + OpenAI SDK + Anthropic SDK + active audio buffers (PCM for a 2-minute conversation is ~10MB per user) + libsodium + worker threads + Node.js heap = **300–400MB at runtime**, not 150. The 300MB pm2 restart threshold mentioned in Section 8 correctly uses the real number — these two figures are inconsistent within the same document.

**The Pipecat dismissal is too quick.** "Python in a Node.js ecosystem" is a real cost, but Pipecat has already solved exactly the hard problems this architecture re-implements from scratch: VAD integration, turn-taking state machines, interruption handling, streaming TTS pipeline management. You're writing all of that yourself. The architectural debt should be accounted for honestly.

### Assumption Not Addressed

There is no discussion of **what happens when Nico is the only person in a voice channel and goes quiet** — does the bot leave? Does it stay joined indefinitely? The idle timeout exists for the bridge, but what's the lifecycle of the bot *joining in the first place*? Slash command required, or does it auto-join on voice channel entry? Auto-join opens an always-on attack surface; slash command adds UX friction. This needs to be an explicit decision.

---

## Section 2: System Architecture

### Process Isolation Is Good — But the Recovery Story Is Missing

"The bridge can crash and restart without OpenClaw noticing" is true for text functionality. But if the bridge crashes mid-conversation, the user has no idea what happened — they spoke, the bot went silent, and there's no feedback in text or voice. The document doesn't address the user-facing failure experience. A bot that silently fails is worse than one that says "sorry, I lost my connection" in text.

### The "Shares Nothing Except the Discord Bot Token" Claim

This is understated. Shared token + shared Discord identity + two independent gateway sessions is not "sharing nothing." It's the most architecturally fragile thing in this design. See deep analysis below (Section 8 / "@discordjs/voice Situation").

### Data Flow Gap

Step 1 says "User joins voice channel → Discord sends VoiceStateUpdate event." But what about the inverse: the bot needs to track when *users leave* to clean up their audio streams and VAD state. If a user drops off Discord without leaving the voice channel properly, their AudioReceiveStream may stay open, burning CPU on empty Opus frames. The cleanup path isn't shown.

---

## Section 3: Provider Recommendations

### Deepgram Cost Is Understated

The $0.0043/min figure assumes you pay only for spoken audio. But for **streaming transcription with a persistent WebSocket**, Deepgram's billing starts when the connection opens. If the bridge maintains an open Deepgram connection for the entire voice session (necessary for low latency), you pay for idle monitoring time between utterances. For a session with 3 minutes of actual speech in a 15-minute window, real cost is 15 × $0.0043 = $0.065, not 3 × $0.0043 = $0.013. That's a 5× difference. The cost table is marketing math.

### ElevenLabs Cost Assumption Is Thin

"$0.05/min" assumes ~280 characters/minute of bot speech — fine for brief replies. But in technical Ethereum conversations ("explain how ePBS changes the fork choice"), the bot might generate 400–800 word responses. That's 2,000–4,000 characters per exchange, potentially $0.36–$0.72 per exchange. For a 30-minute deep session with 10 technical questions, that's **$3–7 per session**, not the sub-$2/day estimate. The cost model needs a "high-verbosity" scenario.

### "LLM Cost Negligible" — Probably True But Not Verified

For short conversational turns, yes. But there's no token budget analysis. Voice sessions accumulate history (ring buffer of 20 messages) — at Claude Sonnet pricing ($3/M input tokens), a 20-message history with technical content could be 10K–30K tokens per request by message 15. That's $0.03–$0.09 per inference call × 15 calls = $0.45–$1.35 per session. Not negligible for long technical sessions.

---

## Section 4: Session Bridging Design

### The Staging Channel Pattern Will Not Work As Described

This section has the most serious flaw in the document and it's buried under "hacky but requires zero OpenClaw code changes." Let me be explicit:

**Problem 1: The loopback/echo problem.**

When the bridge writes a message to `#voice-staging-VC1`, OpenClaw receives it (it monitors all text channels) and responds. The bridge is also listening to ALL messages in that channel (to pick up OpenClaw's response). This means:

- Bridge writes user transcript → bridge receives its own message back (echo)
- Bridge must filter its own messages by bot user ID
- OpenClaw writes a response → bridge receives it
- Bridge must distinguish "this is OpenClaw's response" from "this is the bridge's own message"

The filtering logic is not described anywhere. Without it, the bridge will either infinite-loop (process its own writes as new turns) or silently drop responses. The document says "Bridge has a Discord message listener on that channel to pick up responses" as if this is trivial. It is not.

**Problem 2: Message ordering is not guaranteed.**

If LLM processing is slow (2s), and another user speaks in the staging channel (or a previous response arrives late), messages may arrive out of order. The bridge needs a correlation ID scheme — tagging each transcript message with a UUID and matching responses to requests. None of this is designed.

**Problem 3: "Hidden, bot-only" channels aren't really hidden.**

Server admins can always see them. And "hidden from regular users" requires explicit permission overwrites on every role, which needs to be maintained as the server's role structure evolves. If someone with `Administrator` joins the staging channel and starts typing, they now inject inputs into the voice bot's conversation context. This is a security/sanity concern that isn't mentioned.

**Problem 4: "Zero OpenClaw code changes" may be false.**

OpenClaw's Discord plugin may have channel allowlist configurations, mention-required settings, or other filters that prevent it from processing messages in the staging channel. The document assumes OpenClaw monitors ALL channels indiscriminately, which may not be true (and would be bad practice if it were). At minimum, the staging channel setup requires verifying OpenClaw's channel routing configuration — that's a config change even if not a code change.

**The deeper issue: Why is this v2?**

The MVP uses direct LLM calls, which is the right call. But the staging channel pattern is presented as the v2 upgrade path, and it's the most fragile option available. A simpler v2 path would be an HTTP API server in OpenClaw (even a minimal one) that the bridge calls directly. That's ~20 lines of Express code and removes all the Discord round-trip overhead and loopback complexity. The staging channel pattern solves "no code changes" at the cost of significant production reliability.

### Conversation History Bug

The ring buffer cleanup code has a logic issue:

```javascript
if (Date.now() - session.lastActive > 30 * 60 * 1000) {
  voiceSessions.delete(key);
}
```

This runs every 5 minutes, but there's no code shown that updates `lastActive` during an active conversation. If `lastActive` is only set at session creation and not updated on each turn, a long conversation (30+ min) will have its history silently deleted mid-session. The history wipe will look like amnesia — the bot will forget everything said earlier in the conversation while still in the voice channel.

---

## Section 5: Turn-Taking & Interruption Handling

### State Machine Has No Error Path

The state diagram shows a clean happy path: IDLE → LISTENING → PROCESSING → SPEAKING → back to IDLE. But there are no error transitions. What happens when:

- STT call times out? (Bot stays in PROCESSING forever)
- LLM returns an error? (Same)
- TTS request fails? (Bot stays in SPEAKING with no audio)
- AudioPlayer disconnects mid-stream?

Missing error states will cause the state machine to wedge in production. Once wedged in PROCESSING, no further voice input will be processed because the bot appears to be "waiting for a response."

### Soft vs Hard Interruption Contradiction

Section 5 says: "Soft interruption (grace period): Wait 500ms to confirm it's a real interruption, not background noise. **Better for noisy channels. Use for MVP.**"

But the state machine diagram shows an immediate transition from SPEAKING to LISTENING on interruption detection. Which is it? The code snippet (`audioPlayer.stop(true)` immediately) implements hard interruption, contradicting the "soft for MVP" recommendation in the text. This inconsistency will confuse implementation.

### Multi-Speaker Queue: Stale Audio Problem

When user B speaks while the bot is responding to user A, their audio is buffered. If the bot's response to A takes 8 seconds, user B's buffered audio from 8 seconds ago gets sent to STT. By the time the bot responds to B, user B has probably moved on, said something else, or is confused why the bot is answering a question they asked 10 seconds ago. 

The document addresses this with "v2: parallel processing" but doesn't acknowledge that the MVP queue has a fundamentally broken UX for multi-speaker scenarios. It should either discard stale audio (with a timeout, e.g., 10s) or acknowledge this limitation more explicitly in MVP exclusions.

---

## Section 6: Implementation Plan

### Day 1 Is Blocked Before Writing a Line of Code

"Install @discordjs/opus, libsodium-wrappers, ffmpeg" requires:
```bash
sudo apt install ffmpeg libopus-dev
```

Per `TOOLS.md`: "No sudo — stay sandboxed to my user/home directory. Ask Nico for system installs." This is a hard blocker requiring human intervention before any code runs. It should be listed as a **pre-requisite requiring Nico's approval**, not buried in Day 1 tasks. If Nico is unavailable, the entire Day 1 is blocked.

Additionally: `ffmpeg` is used for audio transcoding but the document doesn't specify whether `@discordjs/voice` needs it for Opus encode/decode or whether `@discordjs/opus` (native addon) handles that. If the native addon isn't available and `opusscript` (pure JS) is used as fallback, CPU usage during audio processing is significantly higher.

### Timeline Is Optimistic Without a Debugging Buffer

5–7 days assumes everything works first try. The realistic breakdown:

- Day 1–2: Setup and first Discord voice connection. With native addon issues, this easily becomes Day 1–3.
- Day 3 (STT): Deepgram streaming WebSocket connection management is non-trivial. The connection lifecycle (open per session vs. per utterance, handling reconnects, handling `close` events from Deepgram's side after periods of silence) is a common source of bugs. Estimate Day 3–4.
- Day 5 (TTS+playback): Piping MP3 from OpenAI REST through a Node.js stream into AudioPlayer involves format conversion (MP3 → Opus) that requires ffmpeg or a transcoding step. If ffmpeg isn't available or the pipeline is misconfigured, you get silence. This is a full day of debugging, not a task.
- Day 7 (deployment): `pm2 start` is simple, but "smoke test in real Discord voice channel" may reveal issues (intent conflicts, permission errors, audio quality problems) that cascade back to Day 3–5.

**More realistic estimate: 8–12 days for Phase 1 MVP** with adequate buffer for platform-specific issues.

### Phase 2 ElevenLabs Streaming Is Underestimated

"5–7 days" for Phase 2 includes "ElevenLabs WebSocket streaming TTS" as a line item. This deserves more respect. ElevenLabs streaming requires:
- WebSocket connection lifecycle management
- Handling `audio` events with base64-encoded PCM chunks
- Buffering and backpressure management (ElevenLabs sends faster than real-time)
- Interruption: cleanly aborting a streaming session mid-playback
- Reconnection and error handling

This alone is 2–3 days of work. Phase 2 is more like 8–10 days total.

---

## Section 7: Risk Assessment

### R2 (CPU Overload) Mitigation Is Inadequate

The mitigation says:
> "Voice bridge is a separate process — can be `nice`'d: `nice -n 10 node voice-bridge.js`"

This is misleading. `nice` affects CPU scheduling priority, but **Node.js is single-threaded**. If the voice bridge's event loop blocks on synchronous Opus decode or a tight callback, `nice` doesn't help — the process still consumes 100% of its allocated CPU time slice. The beacon node at `nice 0` doesn't preempt the voice bridge when it's in a blocking operation.

More importantly: the beacon client (Lodestar) is also Node.js. Both processes share the same Node.js binary runtime characteristics — neither yields the event loop voluntarily during CPU-intensive operations. During Lodestar's finalization processing, attestation aggregation windows, or state transition computation, it can monopolize a CPU core for 1–3 seconds. During this time, the voice bridge's event loop is starved regardless of nice level.

**The hard kill switch** (don't start voice if < 2GB free) is the right idea, but it's mentioned as a mitigation without any implementation path. The MVP plan has no memory monitoring code. Before deploying on server2, you need a concrete answer to: "What's the current available memory/CPU headroom on server2 during peak beacon client load?" If that headroom is < 2 CPU-seconds per second and < 400MB RAM, this project shouldn't deploy there without hardware upgrades.

### R3 (Cost Overrun) — Missing: Concurrent Session Abuse

The cost analysis assumes Nico is the only user. But "multiple users in a voice channel" is possible. If 3 people join and all start chatting, the cost model (1 active speaker at a time) still generates 3× the conversation depth (3× the history). And if the staging channel v2 pattern is used, bot text responses are also sent to the staging channel — counting against any Discord API rate limits for that bot.

### Missing Risk: Discord Rate Limits

Not a single mention of Discord rate limits anywhere in the document. Discord's gateway has rate limits on:
- Sending messages (5/sec per channel)
- Voice state updates (1/sec)
- Modifying voice connection state

For the staging channel pattern in v2: if voice sessions are high-frequency (many short utterances), the bridge could hit the 5-messages/sec limit on the staging channel, causing queued messages to be delayed. This directly impacts perceived latency and is not acknowledged.

---

## Section 8: OpenClaw-Specific Considerations

### The Shared Token Analysis Is Wrong

The document says: "Discord allows one bot to have concurrent text gateway (WebSocket) + voice gateway (UDP) connections."

This is correct for **a single gateway connection** that sends both text messages and voice state updates. But the architecture has **two independent gateway WebSocket sessions** for the same bot token — one in OpenClaw and one in the voice bridge. That's not the same thing.

Here's what actually happens with two processes connecting via the same token simultaneously:

1. **Session conflict:** Discord assigns a `session_id` per gateway connection. When the bridge connects and sends IDENTIFY, Discord accepts it and gives it a new session_id. Now two sessions exist for the same bot. Discord may send a `READY` event to both, or it may invalidate the older session.

2. **Event duplication:** Both processes receive ALL events matching their subscribed intents. The bridge receives all text messages (including ones in the staging channel) because it subscribed to `GUILD_MESSAGES`. OpenClaw receives all voice state updates because it subscribed to `GUILD_VOICE_STATES`. Each process receives more events than needed, and both may try to act on the same event.

3. **Voice state update routing:** To join a voice channel, `@discordjs/voice` sends an `OP 4 Voice State Update` on the gateway it controls. But if OpenClaw's gateway session (different session_id) is the "primary" one from Discord's perspective, voice state updates sent via the bridge's gateway session may be ignored or cause inconsistent state on Discord's side.

4. **Reconnect race:** When one process reconnects (after a crash or network blip), it may invalidate the other's session. The reconnect sends IDENTIFY again, which creates a new session — potentially expiring the existing gateway session that the other process thought was still valid.

**This is a real production hazard, not a "try it and see" situation.** The "create a dedicated voice bot application" fallback mentioned at the end of this section is actually the correct approach. It should be the **default recommendation** with the shared token as an optional optimization if Discord behavior permits it — not the other way around.

### "The Bridge Has Its Own Discord Client" + Same Token = Gateway Sharding Required

If the bridge truly runs its own Discord client (separate Node.js process, separate WebSocket connection), it needs to shard properly with OpenClaw or use a different bot token. The document presents these as equivalent options and recommends trying the wrong one first.

### OpenClaw Session Health Check Not Specified

"Wait until `agent:main:discord:channel:*` session exists (check via OpenClaw API)" — what API? Is there an HTTP endpoint for this? The document doesn't specify. If it's a `openclaw sessions list` CLI call, polling that on startup adds brittle shell-parsing logic to the bridge startup sequence. This should be a concrete spec.

### pm2 `ecosystem.config.js` Is Missing `cwd`

The pm2 snippet:
```javascript
{
  name: 'lodekeeper-voice',
  script: 'src/voice-bridge.js',
  ...
}
```
is missing the `cwd` field. Without it, pm2 starts the process from whatever directory pm2 was invoked from, which will break relative path resolution for `.env`, `logs/`, etc.

---

## Appendix B: Latency Budget — Optimistic Numbers

The key claim: **"STT runs concurrently with the silence detection period. Net STT cost to perceived latency is ~0ms."**

This is partially true but overstated. Here's what actually happens with Deepgram:

- Deepgram streaming processes audio in real-time during speech ✓
- Deepgram fires `UtteranceEnd` after detecting the silence threshold ✓
- BUT: the `UtteranceEnd` event carries the *finalized* transcript, which Deepgram generates **after** receiving the silence signal. Typical finalization adds **100–300ms** after the endpointing silence fires.
- So the actual latency is: `silence_detection (300–500ms) + finalization (100–300ms) = 400–800ms` before you have a final transcript, not ~0ms overlap.

**LLM first token (Claude Sonnet): 400–800ms "typical" is optimistic.** Observed API latency for Claude Sonnet (claude-sonnet-4) under normal conditions is 600–1500ms first token. The 400ms minimum is achievable under ideal conditions but is not "typical." Under peak API load (evenings UTC), 2–3s first token is not uncommon.

**ElevenLabs first chunk: 150–250ms.** Marketing claim. Real-world testing consistently shows 300–600ms for first audio chunk, especially on first connection in a session (TLS handshake + WebSocket upgrade + context initialization). Repeat utterances in the same session can hit 200ms. Cold session start is 400–700ms.

**Network latency not budgeted.** server2 → Deepgram API: ~30–80ms RTT. server2 → OpenAI TTS: ~30–80ms RTT. Each API call adds round-trip latency that's entirely absent from the budget. For 3 API calls: add 100–250ms to the total.

**Revised realistic budget:**

```
Stage                           Typ      P90
──────────────────────────────────────────────
Deepgram endpointing + STT      700ms    1200ms
  (silence + finalization, not "0ms overlap")
Network RTT (STT + LLM + TTS)   200ms     350ms
LLM first token (Sonnet)        900ms    2000ms
TTS first chunk (ElevenLabs)    400ms     700ms
Discord buffer + playback        80ms     150ms
──────────────────────────────────────────────
TOTAL                          ~2.3s     ~4.4s
```

**The P90 of ~4.4s regularly exceeds the "3s+ feels slow" threshold** identified in the document itself. The table in Appendix B showing "~1.7s typical" is aspirational, not operational.

---

## Summary of Critical Issues

| Issue | Severity | Section | Status in Doc |
|-------|----------|---------|---------------|
| Shared Discord token — two independent gateway sessions | 🔴 Critical | §8 | Mischaracterized as safe |
| Staging channel loopback/echo problem | 🔴 Critical | §4 | Not addressed |
| Latency budget ~35% optimistic (P50); P90 regularly > 3s | 🟠 High | Appendix B | Overstated as solved |
| CPU safety on server2 — nice level doesn't protect event loop | 🟠 High | §7 R2 | Mitigation inadequate |
| 150MB footprint vs. 300-400MB reality | 🟠 High | §1, §8 | Internally inconsistent |
| VAD state machine: no error states (wedge risk) | 🟠 High | §5 | Missing entirely |
| Sudo required for system deps — Day 1 blocker | 🟡 Medium | §6 | Buried in task list |
| Multi-speaker stale audio (queue UX broken for MVP) | 🟡 Medium | §5 | Deferred without impact note |
| `lastActive` not updated → history silently wiped | 🟡 Medium | §4 | Code bug in example |
| Hard kill switch (memory check) not in MVP plan | 🟡 Medium | §7 R2 | Mentioned, unimplemented |
| Deepgram cost model ignores idle WS connection billing | 🟡 Medium | §3 | Off by 5× |
| Staging channel: requires OpenClaw config verification | 🟡 Medium | §4 | Claimed "zero changes" |
| pm2 `cwd` missing in config snippet | 🟢 Low | §8 | Omission |
| Timeline 5–7d optimistic; 8–12d realistic | 🟢 Low | §6 | Underestimated |

---

## Recommendations

1. **Fix the token situation first.** Create a dedicated Discord bot application for voice. Don't share the gateway with OpenClaw. The debugging cost of mysterious gateway session conflicts far exceeds the ~10 minutes it takes to create a second bot application.

2. **Redesign the v2 IPC.** The staging channel pattern has too many edge cases. A lightweight HTTP endpoint in the bridge (or a simple Unix socket) is a better IPC mechanism. Keep it out of Discord entirely.

3. **Revise the latency budget.** Add network RTT, use P90 not P50, and stop claiming STT adds 0ms. Design the UX around 2–3s typical, not 1.7s. The "thinking sound" mitigation is correct and should be in the MVP, not listed as optional.

4. **Add error states to the turn-taking state machine.** Every state needs a timeout and a recovery path. Without this, the first STT or LLM timeout will wedge the bot permanently.

5. **Measure server2 headroom before committing.** Get a baseline of CPU and memory during peak beacon client load. If headroom is < 20% CPU and < 500MB RAM, voice on server2 is a bad idea regardless of nice levels. Know this before Day 1.

6. **Pre-flight the sudo dependency.** Get Nico to approve `sudo apt install ffmpeg libopus-dev` before calling Day 1 "Day 1."

---

*End of critique. The architecture has good bones — the decisions in §1 are right, the component breakdown is clean, and the risk register shows good awareness. The issues above are fixable. None of them require starting over. They do require honest acknowledgment before the implementation begins.*
