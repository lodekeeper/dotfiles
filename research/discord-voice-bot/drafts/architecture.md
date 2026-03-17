# Discord Voice Bot — Architecture Design

**Author:** Lodekeeper (systems architect role)  
**Date:** 2026-03-17  
**Status:** Draft v1  
**Based on:** `findings/synthesis.md`  
**Target deployment:** server2 (CPU/memory constrained, runs Ethereum consensus client)

---

## Table of Contents

1. [Recommended Approach](#1-recommended-approach)
2. [System Architecture](#2-system-architecture)
3. [Provider Recommendations](#3-provider-recommendations)
4. [Session Bridging Design](#4-session-bridging-design)
5. [Turn-Taking & Interruption Handling](#5-turn-taking--interruption-handling)
6. [Implementation Plan](#6-implementation-plan)
7. [Risk Assessment](#7-risk-assessment)
8. [OpenClaw-Specific Considerations](#8-openclaw-specific-considerations)

---

## 1. Recommended Approach

**→ Option 2: Standalone Bridge Process**

### Decision

After evaluating all three options against the constraints (CPU-constrained server, no OpenClaw core changes, reliable text bot must keep running), the **standalone bridge process** is the clear winner.

### Evaluation Matrix

| Criterion | Plugin Extension | **Standalone Bridge** | Pipecat |
|-----------|-----------------|----------------------|---------|
| Development effort | High | **Low** | Medium |
| Reliability (crash isolation) | Poor (takes down text bot) | **Excellent** | Good |
| Maintainability | Poor (tied to OpenClaw internals) | **Good** | Fair |
| End-to-end latency | Best (in-process) | Good (+50-100ms IPC) | Fair (+Python overhead) |
| OpenClaw core changes required | Yes | **No** | No |
| Ecosystem fit | Node.js native | **Node.js native** | Python (foreign) |
| Deploy complexity | Low | **Low (one more process)** | High (Python env + Discord transport) |
| Resource footprint | Shared with OpenClaw | ~150MB dedicated | ~200-400MB (Python) |

### Why NOT the alternatives

**Plugin Extension** is off the table. OpenClaw's Discord plugin is a 165KB bundled module. Modifying it means either patching the bundle (fragile, breaks on upgrades) or forking the entire OpenClaw codebase. Voice bugs could crash the text bot, losing Telegram+Discord text functionality for Nico. The development complexity is also highest: you need to understand OpenClaw's internal job/session routing to add a new inbound/outbound handler type.

**Pipecat** is an excellent framework but the wrong tool here. It's Python in a Node.js ecosystem, has no native Discord transport (would need to be written from scratch), and its strength—orchestrating complex multi-modal pipelines—is overkill for a single-bot deployment. The 30+ service integrations are irrelevant when we've already chosen providers.

**Standalone Bridge** is the right call because:
1. No risk to the existing text bot
2. Uses `@discordjs/voice` already in node_modules (no new core deps)
3. Can be deployed, restarted, and iterated independently
4. The only "integration penalty" is a small IPC/session-bridging overhead (~50-100ms) — negligible given the overall 1.2-3.2s pipeline latency
5. Nico can kill the voice bridge if it misbehaves without impacting anything else

---

## 2. System Architecture

### Component Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                          server2                                   │
│                                                                    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │                   Voice Bridge (Node.js)                │    │
│   │                   lodekeeper-voice / voice-bridge.js    │    │
│   │                                                         │    │
│   │  ┌──────────────────┐     ┌───────────────────────┐    │    │
│   │  │  Discord Gateway │     │   Session Manager     │    │    │
│   │  │  (@discordjs/    │     │   (per voice channel) │    │    │
│   │  │   voice v0.19.1) │     │                       │    │    │
│   │  │                  │     │  - conversation hist  │    │    │
│   │  │  VoiceConnection │     │  - speaker state      │    │    │
│   │  │  AudioReceiver   │     │  - VAD state          │    │    │
│   │  │  AudioPlayer     │     │  - TTS playback state │    │    │
│   │  └──────┬───────────┘     └───────────┬───────────┘    │    │
│   │         │ Opus packets                │                 │    │
│   │         ▼                             │                 │    │
│   │  ┌──────────────┐                     │                 │    │
│   │  │  VAD + PCM   │ (silence detection) │                 │    │
│   │  │  Processor   │                     │                 │    │
│   │  └──────┬───────┘                     │                 │    │
│   │         │ audio buffer (on turn-end)  │                 │    │
│   │         ▼                             │                 │    │
│   │  ┌──────────────┐                     │                 │    │
│   │  │  STT Client  │──transcript text────►                 │    │
│   │  │  (Deepgram   │                     │                 │    │
│   │  │   streaming) │                     │                 │    │
│   │  └──────────────┘                     │                 │    │
│   │                                       │                 │    │
│   │                              ┌────────▼──────────┐      │    │
│   │                              │  OpenClaw IPC     │      │    │
│   │                              │  (sessions API or │      │    │
│   │                              │   direct LLM call)│      │    │
│   │                              └────────┬──────────┘      │    │
│   │                                       │ response text    │    │
│   │                                       ▼                 │    │
│   │                              ┌────────────────────┐     │    │
│   │                              │   TTS Client       │     │    │
│   │                              │   (OpenAI TTS /    │     │    │
│   │                              │    ElevenLabs WS)  │     │    │
│   │                              └────────┬───────────┘     │    │
│   │                                       │ PCM/Opus chunks │    │
│   │                                       ▼                 │    │
│   │                              ┌────────────────────┐     │    │
│   │                              │   Audio Playback   │     │    │
│   │                              │   (AudioPlayer     │     │    │
│   │                              │    @discordjs/voice│     │    │
│   │                              └────────────────────┘     │    │
│   └─────────────────────────────────────────────────────────┘    │
│                                │                                   │
│   ┌────────────────────────────▼──────────────────────────┐       │
│   │                OpenClaw Main Process                  │       │
│   │                                                       │       │
│   │   agent:main:discord:channel:<text-ch-id>  (text)    │       │
│   │   agent:main:discord:voice:<voice-ch-id>   (voice)   │       │
│   │   agent:main:telegram:direct:<user-id>     (telegram)│       │
│   │                                                       │       │
│   │   Existing Claude Sonnet/Opus models                  │       │
│   └───────────────────────────────────────────────────────┘       │
└────────────────────────────────────────────────────────────────────┘
         ▲                                           ▲
         │ Discord WebSocket (text gateway)          │ Discord UDP (voice)
         ▼                                           ▼
┌────────────────────────────────────────────────────────────────────┐
│                         Discord API                               │
│                                                                    │
│  Text channels (WebSocket)          Voice channels (UDP/Opus)     │
└────────────────────────────────────────────────────────────────────┘
```

### Process Boundaries

| Process | Responsibility | Communication |
|---------|---------------|---------------|
| OpenClaw (existing) | Text gateway, agent sessions, Claude API | Discord WebSocket, Telegram |
| Voice Bridge (new) | Voice gateway, STT/TTS pipeline | Discord UDP, HTTP APIs, IPC to OpenClaw |

The two processes share **nothing at runtime** except the Discord bot token and an IPC channel. They run independently. The bridge can crash and restart without OpenClaw noticing.

### Data Flow (Happy Path)

```
1. User joins voice channel → Discord sends VoiceStateUpdate event
2. Bridge (if configured) auto-joins OR waits for /voicejoin slash command
3. User speaks → @discordjs/voice delivers per-user Opus packets (20ms frames)
4. VAD Processor decodes Opus → PCM, monitors RMS energy
5. On voice-start: start buffering, note speaker ID
6. On silence (300ms threshold): end of turn detected
7. Send PCM buffer → Deepgram streaming STT
8. Deepgram returns transcript (partial during, final on silence)
9. Transcript sent to OpenClaw agent session (IPC)
10. Agent processes, returns text response
11. Response text sent to TTS (OpenAI or ElevenLabs)
12. TTS returns PCM/MP3 chunks (streaming)
13. Bridge encodes to Opus, streams to AudioPlayer
14. AudioPlayer plays audio into voice channel
15. All users hear Lodekeeper's response
```

### Key Interfaces

**Bridge ↔ Discord:** `@discordjs/voice` handles all voice gateway protocol (UDP, SRTP, Opus). This is already battle-tested.

**Bridge ↔ STT:** HTTP POST or WebSocket stream to Deepgram. Latency advantage: Deepgram streaming allows partial transcripts during speech, final transcript on silence.

**Bridge ↔ OpenClaw:** Two options (see Section 4). For MVP: direct LLM API call with managed history. For v2: OpenClaw sessions IPC.

**Bridge ↔ TTS:** REST API (OpenAI) or WebSocket (ElevenLabs). For streaming, ElevenLabs WebSocket delivers audio chunks as they're generated, allowing playback to start before TTS is complete.

---

## 3. Provider Recommendations

### STT (Speech-to-Text)

**Recommended: Deepgram Nova-3 (streaming)**

| Tier | Provider | Latency | Cost/min | Notes |
|------|----------|---------|---------|-------|
| 🟢 Good | OpenAI Whisper API | 1-3s | $0.006 | Batch only, no streaming |
| 🟡 Better | OpenAI gpt-4o-mini-transcribe | 0.5-1s | $0.003 | Newer, faster, streaming |
| 🔵 Best | **Deepgram Nova-3** | 200-300ms | **$0.0043** | Real-time streaming, best latency/price |

**Why Deepgram for production:**
- Streaming API means transcription happens *concurrently with speech*, not after
- 200-300ms latency vs 1-3s for batch Whisper — shaves ~1s off the pipeline
- Better noise handling than Whisper for voice channel audio quality
- `endpointing` parameter natively handles silence detection (can replace custom VAD)
- Price is actually lower than Whisper despite better performance

**Deepgram-specific setup:**
```javascript
const deepgram = createClient(process.env.DEEPGRAM_API_KEY);
const connection = deepgram.listen.live({
  model: 'nova-3',
  language: 'en-US',
  punctuate: true,
  endpointing: 300,       // 300ms silence = end of utterance
  interim_results: true,  // partial transcripts for responsiveness
  vad_events: true,       // voice activity events
});
```

**Fallback option:** For cost-zero testing, `openai.audio.transcriptions.create()` with buffered audio works fine in development.

---

### TTS (Text-to-Speech)

**Recommended: OpenAI TTS for MVP, ElevenLabs streaming for production**

| Tier | Provider | Latency (first audio) | Quality | Cost estimate |
|------|----------|----------------------|---------|---------------|
| 🟢 Good | **OpenAI TTS (tts-1)** | 400-600ms | Good | ~$0.015/1K chars |
| 🟡 Better | OpenAI TTS HD (tts-1-hd) | 600-900ms | Very good | ~$0.030/1K chars |
| 🔵 Best | **ElevenLabs WebSocket** | 200-300ms | Excellent | ~$0.18/1K chars (but streaming = less waste) |

**For MVP: OpenAI TTS**
- Simple REST API: `openai.audio.speech.create({ model: 'tts-1', voice: 'onyx', input: text })`
- Returns MP3/Opus, encode back to Discord-compatible Opus stream
- `onyx` voice suits a technical AI assistant
- No streaming, but latency is acceptable for v1

**For v2: ElevenLabs WebSocket streaming**
- Connects via WebSocket, send text chunks, receive audio chunks in real-time
- First audio chunk arrives in 200-300ms even for long responses
- Allows playback to begin *while* text is still being generated (huge UX improvement)
- Higher per-character cost but real-time streaming means you only pay for what's spoken (no wasted audio for interrupted responses)
- Custom voice cloning possible (Lodekeeper-specific persona voice)

**Voice character:** Use a consistent voice ID. `onyx` (OpenAI) or a custom ElevenLabs voice trained on authoritative/calm speech. Lodekeeper should sound confident, not chipper.

---

### LLM

**No new provider needed.** The bridge reuses the same Anthropic Claude API already configured in OpenClaw. The session bridging design (Section 4) determines whether this is:
- A direct API call (bridge manages conversation) — MVP
- Routed through OpenClaw agent session — v2

**Cost impact:** Voice adds ~5-15 message exchanges per voice session. Negligible compared to existing usage.

---

### Cost Summary

| Configuration | STT | TTS | Total | Notes |
|--------------|-----|-----|-------|-------|
| MVP (OpenAI STT + TTS) | $0.003/min | $0.015/min | **~$0.02/min** | Simple, reliable |
| Production (Deepgram + OpenAI TTS) | $0.0043/min | $0.015/min | **~$0.02/min** | Better latency |
| Premium (Deepgram + ElevenLabs) | $0.0043/min | ~$0.05/min | **~$0.06/min** | Best quality |

At typical usage (30 min/day active voice), production config costs **~$0.60/day**. Even the premium config is **~$1.80/day** — extremely low.

---

## 4. Session Bridging Design

This is the most architecturally significant decision. How does the voice bridge communicate with the OpenClaw agent, and should voice share context with text?

### Option A: Bridge-Managed LLM (MVP)

```
Voice Bridge maintains its own:
  - Conversation history per (voice channel, user) tuple
  - Calls Anthropic API directly with Claude Sonnet
  - Does NOT interact with OpenClaw sessions at all
```

**Pros:** Simple, zero IPC complexity, no OpenClaw dependency at runtime.  
**Cons:** Voice context is isolated from text context. If a user discussed something in Discord text, the voice session doesn't know about it.

**Verdict: Use for MVP.** The text/voice context split is acceptable for initial deployment.

---

### Option B: OpenClaw Session IPC (v2 target)

```
Voice Bridge:
  - Sends transcript via OpenClaw CLI:
      openclaw session send agent:main:discord:voice:<CHANNEL_ID> "<transcript>"
  - Captures response from openclaw CLI stdout
  - OR: uses OpenClaw HTTP sessions API on localhost:PORT
```

This requires a new session key pattern `agent:main:discord:voice:<CHANNEL_ID>` that:
1. Routes inbound to the existing Claude agent (same model)
2. Has a **different outbound handler** — instead of posting to Discord text channel, it returns the response text to the bridge's IPC listener

**How to implement the outbound capture without core changes:**

The bridge can use a lightweight approach: write transcripts as if a human typed them into a *dedicated voice text channel* (a private bot channel only the bot can see). The agent's response posts to that hidden text channel. The bridge has a Discord message listener on that channel to pick up responses and convert to TTS.

```
User speaks → STT → bridge writes to #voice-staging-<channel-id> (hidden channel)
                    → OpenClaw Discord plugin picks it up as normal text message
                    → Agent responds → Discord plugin posts to #voice-staging-<channel-id>
                    → Bridge hears the new message → TTS → play audio
```

This is hacky but requires **zero OpenClaw code changes**. The "staging channel" acts as a message bus.

**Recommended v2 IPC: Staging Channel Pattern**

```
┌──────────────────────────────────────────────────────┐
│                    Discord                           │
│                                                      │
│  #voice-staging-VC1  (hidden, bot-only text channel) │
│                                                      │
│   Bridge writes: "User said: what's the fork choice?"│
│   OpenClaw reads: normal text message                │
│   Agent replies:  "The fork choice algorithm is..."  │
│   Bridge reads:   TTS → voice channel                │
└──────────────────────────────────────────────────────┘
```

**Context continuity** with this approach:
- The `agent:main:discord:channel:<staging-channel-id>` session accumulates shared history
- If users also chat in the text channel, a separate session key means contexts remain separate (simpler)
- For full context continuity across text+voice, use the same channel ID for both (more complex routing, deferred to v3)

---

### Session Ownership Decision

| Concern | Recommendation |
|---------|----------------|
| Should voice get its own session? | **Yes (for MVP)** — isolated history, simpler |
| Should it share with text channel? | **v2 target** — staging channel pattern |
| How to handle multiple concurrent speakers? | One sub-session per speaker (voice channel session forks per user) |
| Context continuity across voice/text? | v3 feature — requires OpenClaw core change or aggressive staging channel use |

---

### Conversation History Management

The bridge maintains a per-(channel, user) conversation ring buffer:

```javascript
const voiceSessions = new Map(); // channelId → { history: [], lastActive: Date }

// Prune old sessions after 30 min inactivity
setInterval(() => {
  for (const [key, session] of voiceSessions) {
    if (Date.now() - session.lastActive > 30 * 60 * 1000) {
      voiceSessions.delete(key);
    }
  }
}, 5 * 60 * 1000);

// History: rolling last N messages to bound token usage
const MAX_VOICE_HISTORY = 20; // ~10 turns
```

The system prompt for voice sessions should differ slightly from text: shorter responses, more conversational, explicit acknowledgment that this is voice ("I'll keep my answer brief for voice").

---

## 5. Turn-Taking & Interruption Handling

This is where voice bots fail in practice. Getting this right is critical for a natural experience.

### Voice Activity Detection (VAD)

**Two-tier approach:**

**Tier 1 — Energy-based (MVP):**
```javascript
function getRMS(pcmBuffer) {
  let sum = 0;
  for (let i = 0; i < pcmBuffer.length; i += 2) {
    const sample = pcmBuffer.readInt16LE(i) / 32768;
    sum += sample * sample;
  }
  return Math.sqrt(sum / (pcmBuffer.length / 2));
}

const SPEECH_THRESHOLD = 0.01;   // above this = speaking
const SILENCE_DURATION = 350;     // ms of silence = end of turn
```

**Tier 2 — Deepgram VAD events (v2):**
```javascript
// Deepgram emits SpeechStarted and UtteranceEnd events automatically
// when endpointing is enabled — no custom VAD needed
connection.on(LiveTranscriptionEvents.UtteranceEnd, (data) => {
  // treat final transcript as complete turn
});
```

For MVP, Deepgram's built-in endpointing (`endpointing: 300`) handles this natively. Custom RMS VAD is only needed if not using Deepgram streaming.

---

### Turn State Machine

```
                    ┌──────────┐
                    │  IDLE    │ (no one speaking, bot can speak)
                    └──────┬───┘
                           │ RMS > threshold
                           ▼
                    ┌──────────┐
          ┌────────►│LISTENING │ (accumulating audio, waiting for silence)
          │         └──────┬───┘
          │                │ silence > 350ms
          │                ▼
          │         ┌──────────┐
          │         │PROCESSING│ (STT in flight, LLM in flight)
          │         └──────┬───┘
          │                │ response ready
          │                ▼
          │         ┌──────────┐
          └─────────│ SPEAKING │ (TTS playing to Discord)
     user starts    └──────────┘
     speaking
```

**State transitions are per voice channel**, not per user. If multiple users are in the channel, the first speaker to start a new turn wins. Others are queued (see multi-speaker below).

---

### Interruption Handling

When Lodekeeper is SPEAKING and a user starts talking:

```javascript
audioPlayer.on('stateChange', (old, newState) => {
  // when playing audio
});

// Monitor each user's audio stream even while bot is speaking
userStream.on('data', (opusPacket) => {
  if (currentState === 'SPEAKING' && getRMS(decode(opusPacket)) > SPEECH_THRESHOLD) {
    // Interruption detected
    audioPlayer.stop(true);                    // stop immediately
    ttsAbortController?.abort();               // cancel in-flight TTS request
    currentState = 'LISTENING';                // start listening to interrupter
    noteSpeaker(userId);                       // switch active speaker
    log(`[voice] Interrupted by ${userId}`);
  }
});
```

**Hard interruption (immediate stop):** Stop mid-sentence. More natural. Users expect this behavior from voice assistants. The in-flight TTS request should be aborted (ElevenLabs WebSocket: close connection; OpenAI REST: AbortController).

**Soft interruption (grace period):** Wait 500ms to confirm it's a real interruption, not background noise. Better for noisy channels. Use for MVP.

---

### Multi-Speaker Handling

**MVP: First-Speaker-Wins Queue**

```javascript
const speakerQueue = [];
let activeSpeaker = null;

function onUserSpeaking(userId) {
  if (activeSpeaker === null) {
    activeSpeaker = userId;
    startListeningTo(userId);
  } else if (activeSpeaker !== userId) {
    if (!speakerQueue.includes(userId)) {
      speakerQueue.push(userId);
    }
  }
}

function onTurnComplete() {
  activeSpeaker = speakerQueue.shift() ?? null;
  if (activeSpeaker) {
    // process queued speaker's buffered audio
  }
}
```

**v2: Parallel Processing**
- Allow multiple users to speak concurrently
- Maintain separate conversation history per user
- Bot responds to each user in order (queue still), but STT/LLM can run in parallel

**v3: Smart Turn-Taking**
- Detect when a user is asking a question vs making a statement
- Prioritize questions over comments
- Handle back-and-forth conversation between multiple humans (bot tracks speaker identities)

---

### Noise Suppression

Server-side voice bots don't need echo cancellation (no speaker-mic feedback loop), but Discord voice channels can have background noise. Deepgram handles this well natively. Tuning:

- `SPEECH_THRESHOLD = 0.01` is conservative (background noise typically < 0.005 RMS)
- If false positives occur, increase to `0.02-0.03`
- For channels with loud background: use Deepgram's `smart_format: true` + `filler_words: false` to clean up transcripts

---

## 6. Implementation Plan

### Phase 1: MVP (Estimated: 5-7 days)

**Goal:** Lodekeeper can join a voice channel, hear one user, respond with speech.

**Tasks:**

```
Day 1: Project setup
  - Create ~/lodekeeper-voice/ as standalone Node.js project
  - Install @discordjs/voice (ref from openclaw node_modules or fresh install)
  - Install @discordjs/opus, libsodium-wrappers, ffmpeg
  - Test: bot joins voice channel, plays a sine wave

Day 2: Audio receive + VAD
  - Subscribe to per-user AudioReceiveStream
  - Decode Opus → PCM
  - Implement RMS-based VAD + turn detection
  - Test: console.log "user started speaking / stopped speaking"

Day 3: STT integration
  - Integrate Deepgram streaming with live WebSocket
  - Send PCM chunks in real-time as user speaks
  - Receive final transcript on UtteranceEnd
  - Test: console.log transcript accurately

Day 4: LLM integration
  - Direct Anthropic API call with conversation history
  - System prompt tuned for voice (brief, conversational)
  - Test: transcript in → response out

Day 5: TTS + playback
  - OpenAI TTS REST call → MP3 buffer
  - Create readable stream from MP3, pipe to AudioPlayer
  - Test: bot speaks response in voice channel

Day 6: Commands + polish
  - /voicejoin slash command (Discord App Commands)
  - /voiceleave slash command
  - Basic interruption handling (stop on new speech)
  - Graceful error handling (STT timeout, LLM error)

Day 7: Testing + deployment
  - Deploy as pm2 process on server2
  - Environment variable setup (DISCORD_TOKEN, DEEPGRAM_KEY, OPENAI_KEY)
  - Smoke test in real Discord voice channel
```

**MVP Acceptance Criteria:**
- [ ] Bot joins/leaves on command
- [ ] One user can have a 5-turn voice conversation
- [ ] Latency < 4s end-to-end (acceptable for async voice)
- [ ] Bot stops playing when user interrupts
- [ ] Gracefully handles STT/TTS errors without crashing

**MVP Exclusions:**
- No multi-speaker support
- No OpenClaw session integration (direct LLM calls)
- No conversation persistence
- No streaming TTS
- No wake word / always-listening mode

---

### Phase 2: Production Ready (Estimated: 5-7 days)

**Goal:** Multi-user support, OpenClaw session integration, streaming TTS.

**Tasks:**
- Multi-speaker queue (per-user audio streams)
- ElevenLabs WebSocket streaming TTS (first audio in 200-300ms)
- OpenClaw staging channel IPC (shared context with text sessions)
- Cost controls: max voice session duration (30 min), idle timeout (5 min)
- Inactivity auto-leave (bot leaves if no speech for 5 min)
- Conversation persistence (ring buffer per session, logged to file)
- Health monitoring: expose `/health` HTTP endpoint, pm2 restart on crash
- Rate limiting: max 1 concurrent voice channel per server (server2 constraint)
- Logging: structured logs to `~/logs/voice-bridge.log` with daily rotation

---

### Phase 3: v2 (Estimated: 3-5 days, post-production)

**Goal:** Enhanced UX, Lodekeeper persona voice, analytics.

**Tasks:**
- ElevenLabs voice cloning for Lodekeeper custom voice
- Proactive voice: bot can speak unprompted (e.g., "Nico, that attestation window closes in 2 epochs")
- Cross-channel context: voice session aware of recent Discord text history
- `/voicestatus` command showing active session info
- Token/cost tracking per session (logged to metrics)
- Wake word detection (optional): "Hey Lodekeeper"
- Multi-language detection (Deepgram supports auto-detect)

---

### Dependency Checklist (Pre-Implementation)

```bash
# System dependencies (server2)
sudo apt install ffmpeg libopus-dev

# Node.js packages
npm install @discordjs/voice @discordjs/opus libsodium-wrappers
npm install deepgram-sdk
npm install openai
npm install @anthropic-ai/sdk  # if calling directly (not via openclaw)

# Check @discordjs/voice already available via OpenClaw
ls /path/to/openclaw/node_modules/@discordjs/voice
```

---

## 7. Risk Assessment

### R1: End-to-End Latency (HIGH RISK)

**Scenario:** User speaks, waits 4+ seconds for response. Feels unnatural.

**Root causes:**
- LLM first-token latency (500-2000ms) dominates the pipeline
- Non-streaming TTS adds another 400-900ms before any audio plays
- Deepgram streaming VAD endpointing adds 300ms intentional delay

**Mitigation:**
- Use Deepgram streaming (overlap STT with end of speech detection)
- Use ElevenLabs WebSocket streaming TTS (first chunk in 200-300ms)
- Use Claude Sonnet (not Opus) for voice — faster first token
- Play a brief "thinking" sound (e.g., short hum) while LLM is processing — sets UX expectations
- Partial acknowledgment: play "hmm" or "let me think" while waiting for LLM
- For v2: OpenAI Realtime API bypasses the STT→LLM→TTS chain entirely at 300-500ms, but costs 10-15x more

**Acceptable baseline:** 1.5-2.5s is tolerable for an AI assistant. 3s+ starts to feel slow. Aim for < 2s in production config.

---

### R2: CPU Overload on server2 (HIGH RISK)

**Scenario:** Voice processing + Ethereum consensus client compete for CPU. Node is unstable.

**Root causes:**
- Opus decode/encode is CPU-intensive if many parallel streams
- Node.js is single-threaded; heavy audio processing can block event loop
- server2 may already be at 60-80% CPU during peak consensus activity

**Mitigation:**
- Voice bridge is a separate process — can be `nice`'d:
  ```bash
  nice -n 10 node voice-bridge.js  # lower priority than consensus client
  ```
- Limit concurrent voice channels to **1** (server2 constraint)
- Move Opus decode to worker thread (off main event loop)
- Monitor CPU in pm2: `pm2 monit`
- Set up CPU threshold alert: if consensus client CPU > 90%, auto-leave voice channel
- **Hard kill switch:** if server2 is under memory pressure (< 2GB free), don't start voice session

---

### R3: Cost Overrun (MEDIUM RISK)

**Scenario:** Voice session left running for hours, accumulates large bill.

**Root causes:**
- Nico (or others) leaves voice channel with bot still active
- STT charges for silence detection time
- TTS charges per character even for short responses

**Mitigation:**
- **Hard session cap:** 30 minutes max per voice session (auto-leave + notify in text channel)
- **Idle timeout:** 5 minutes with no speech → auto-leave
- **Daily budget alert:** sum Deepgram + OpenAI usage, alert if > $5/day
- **STT optimization:** Deepgram's `endpointing` charges only for final transcripts, not streaming audio
- Estimated worst-case: 2 hours/day × $0.06/hr = $0.12/day — very low risk at this usage level

---

### R4: @discordjs/voice Compatibility Issues (MEDIUM RISK)

**Scenario:** Missing native deps (libopus, ffmpeg, libsodium) prevent voice connection.

**Root causes:**
- `@discordjs/voice` requires native addons that may not be installed on server2
- The bundled v0.19.1 in OpenClaw node_modules may have different peer dep requirements

**Mitigation:**
- Check early: `node -e "require('@discordjs/voice')"` in a test script
- Pre-install deps: `apt install ffmpeg libopus0 libopus-dev`
- Use `opusscript` (pure JS fallback) if `@discordjs/opus` native addon fails
- Pin specific tested versions in voice bridge `package.json`

---

### R5: Multi-Speaker Chaos (LOW-MEDIUM RISK)

**Scenario:** Multiple people speaking simultaneously, bot confused, responses garbled.

**Root causes:**
- @discordjs/voice delivers separate per-user streams; bridge must demux correctly
- If two users finish speaking at the same time, two STT jobs race

**Mitigation:**
- MVP: strict one-speaker queue (first speaker wins, others buffered)
- Clear state management per speaker (userId → VAD state, audio buffer)
- If two turns complete simultaneously, process in order of turn-start time (FIFO)

---

### R6: Network Disruption (LOW RISK)

**Scenario:** Discord UDP voice connection drops, reconnect logic fails.

**Root causes:**
- Server2 network blips, Discord outages, rate limiting
- Voice connections are UDP — no built-in reliability

**Mitigation:**
- `@discordjs/voice` has built-in reconnect logic (`reconnectAttempts`)
- Bridge should handle `Disconnected` → reconnect up to 3 times, then leave+notify
- Text fallback: if voice bridge fails, Lodekeeper continues working in text mode

---

### R7: STT Quality / Hallucinations (LOW RISK)

**Scenario:** Deepgram mishears user, LLM gets confused input.

**Root causes:**
- Background noise, non-native accents, technical jargon ("attestation", "RANDAO")
- Deepgram can hallucinate rare technical terms

**Mitigation:**
- Custom vocabulary / keyword boosting in Deepgram:
  ```javascript
  keywords: ['Lodestar', 'attestation', 'validator', 'finalization', 'Ethereum']
  ```
- Log all transcripts to file for quality monitoring
- Post transcript to Discord text channel as confirmation (optional): "I heard: *{transcript}*"

---

## 8. OpenClaw-Specific Considerations

### The @discordjs/voice Situation

OpenClaw bundles `@discordjs/voice v0.19.1` in its node_modules but never uses it. This means:

1. **It's tested-installed** on server2 — the module resolves without error
2. **Native deps may or may not be present** — the bundle may use `opusscript` (pure JS) rather than `@discordjs/opus` (native). Check: `ls node_modules/@discordjs/opus`
3. **The voice bridge should NOT share OpenClaw's node_modules** — create `~/lodekeeper-voice/` as an independent project with its own `node_modules` and a fixed `package.json`. Don't rely on OpenClaw's internal dependency tree.

```
~/lodekeeper-voice/
  package.json        ← pinned deps, independent of openclaw
  node_modules/       ← isolated install
  src/
    voice-bridge.js
    vad.js
    stt-client.js
    tts-client.js
    session-manager.js
  .env                ← DISCORD_TOKEN, DEEPGRAM_KEY, OPENAI_KEY
```

---

### The Discord Token Reuse

The bridge reuses the same bot token as OpenClaw's Discord plugin. This is fine:
- Discord allows one bot to have concurrent text gateway (WebSocket) + voice gateway (UDP) connections
- The bridge's voice `GatewayIntents` are separate from OpenClaw's text intents
- **However:** both processes use the same Discord client identity. If OpenClaw connects with `GatewayIntentBits.GuildVoiceStates`, the bridge also needs it. Make sure OpenClaw's gateway connection includes `GUILD_VOICE_STATES` intent (needed to receive voice state updates).

If there's an intent conflict, the alternative is creating a **second Discord bot application** specifically for voice — same server, different bot user. This adds a second bot visible in the server but cleanly separates concerns.

**Recommendation:** Try shared token first. If intent conflicts arise, create a dedicated voice bot application.

---

### Existing Session Routing

OpenClaw's text plugin routes Discord messages to: `agent:main:discord:channel:<CHANNEL_ID>`

For voice, we need a new session namespace. **Don't conflict with existing sessions.** The staging channel approach (Section 4, Option B) creates a real Discord text channel as the IPC bus:

1. Create a private text channel: `#voice-sessions-lodekeeper` (or one per voice channel)
2. OpenClaw's existing plugin naturally picks up messages there (it monitors all text channels)
3. The bridge has its own Discord client that also monitors this channel for bot responses
4. This requires **no OpenClaw changes** — it looks like a normal text conversation to OpenClaw

**Channel ID mapping** (to be created during Phase 2 setup):
```
Voice Channel: #general-voice (ID: 123456789)
  → Staging Channel: #voice-stage-123456789 (private, bot-only)
  → Session Key: agent:main:discord:channel:<staging-channel-id>
```

---

### Process Management

The voice bridge should run as a `pm2` process alongside OpenClaw:

```bash
# Add to pm2 ecosystem
pm2 start ~/lodekeeper-voice/src/voice-bridge.js \
  --name lodekeeper-voice \
  --max-memory-restart 300M \
  --restart-delay 5000 \
  --env production

# Make it nice (lower CPU priority than consensus client)
pm2 set lodekeeper-voice:niceness 10

# Save to pm2 startup
pm2 save
```

**Resource limits:**
- Max memory: 300MB restart threshold (if it leaks, auto-restart)
- CPU nice: +10 (lower priority than the beacon node at nice 0)
- Max concurrent voice channels: 1 (enforced in bridge code)

---

### Startup Sequencing

The voice bridge should start **after** OpenClaw:

```bash
# In pm2 ecosystem.config.js
{
  name: 'lodekeeper-voice',
  script: 'src/voice-bridge.js',
  wait_ready: false,
  listen_timeout: 10000,
  // Start 10s after OpenClaw to ensure text bot is operational
}
```

Or use a simple health check on startup: wait until `agent:main:discord:channel:*` session exists (check via OpenClaw API) before accepting voice commands.

---

### Environment Variable Management

The voice bridge needs:
```
DISCORD_TOKEN=<same token as openclaw>
DEEPGRAM_API_KEY=<new, get from deepgram.com>
OPENAI_API_KEY=<same as openclaw or separate>
ANTHROPIC_API_KEY=<same as openclaw>
VOICE_MAX_SESSION_MINUTES=30
VOICE_IDLE_TIMEOUT_MINUTES=5
VOICE_MAX_CONCURRENT=1
LOG_LEVEL=info
```

Store in `~/lodekeeper-voice/.env`. Add `.env` to `.gitignore`. Do NOT commit to any repo.

---

## Appendix A: Architecture Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Integration approach | Standalone bridge | No core changes, crash isolation |
| STT provider | Deepgram Nova-3 | Best latency/price, streaming |
| TTS provider (MVP) | OpenAI TTS | Simple API, adequate quality |
| TTS provider (v2) | ElevenLabs WebSocket | Streaming, best quality |
| LLM | Claude Sonnet (direct) | Existing key, faster than Opus |
| VAD | Deepgram endpointing | Built-in, no custom code |
| Multi-speaker | FIFO queue | Simple, safe for MVP |
| Session bridging (MVP) | Bridge-managed history | No IPC complexity |
| Session bridging (v2) | Staging channel pattern | Shared context, no core changes |
| Process management | pm2 + nice | Existing infra, CPU priority |
| Token strategy | Shared bot token | Try first; dedicated if conflicts |

---

## Appendix B: Latency Budget (Production Config)

```
Stage                           Min      Typ      Max
─────────────────────────────────────────────────────
Deepgram endpointing silence    300ms    350ms    500ms
Deepgram STT (streaming)        100ms    200ms    400ms
  (final transcript latency,    
   most of this overlaps with
   the silence detection period)
LLM first token (Claude Sonnet) 400ms    800ms    2000ms
TTS first chunk (ElevenLabs WS) 150ms    250ms    500ms
Discord audio buffer + playback  50ms     80ms    150ms
─────────────────────────────────────────────────────
TOTAL                           ~1.0s   ~1.7s    ~3.5s
```

The key insight: STT runs **concurrently** with the silence detection period. By the time Deepgram fires `UtteranceEnd`, it's already been processing audio for the last 300ms. Net STT cost to perceived latency is ~0ms for well-tuned streaming.

The LLM first-token latency (400-800ms typical for Sonnet) is the bottleneck. A "thinking" sound or partial acknowledgment before the response starts closes this gap perceptually.

---

*Architecture document complete. Next step: implement Phase 1 MVP per the plan in Section 6.*
