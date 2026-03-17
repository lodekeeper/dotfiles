# Discord Voice Bot Research — Synthesis of Findings

## 1. Existing Frameworks & Reference Implementations

### @discordjs/voice (v0.19.1)
- **Already a dependency** in OpenClaw's node_modules
- Provides: `joinVoiceChannel()`, `VoiceConnection`, `AudioReceiveStream`, `AudioPlayer`
- Handles Opus encoding/decoding, libsodium encryption, UDP transport
- Receives per-user audio streams (Opus packets, 20ms frames)
- Requires `@discordjs/opus` or `opusscript` + `libsodium-wrappers` + `ffmpeg`

### Production Reference Implementations
1. **Discord-VC-LLM** (github.com/Eidenz/Discord-VC-LLM) — Node.js, OpenAI-compatible STT/LLM/TTS APIs
   - Full pipeline: join VC → listen → STT → LLM → TTS → play audio
   - Supports trigger words, interrupt ("stop"), multiple modes
   - Most complete reference for our use case

2. **AssemblyAI Tutorial** — Step-by-step Node.js guide
   - Uses AssemblyAI STT + OpenAI LLM + ElevenLabs TTS
   - Shows exact @discordjs/voice patterns for audio receive/play

3. **discord-voice-ai** (github.com/itzzkirito) — Whisper + ElevenLabs
4. **LLMChat** (github.com/hc20k) — Multi-LLM with voice cloning
5. **Saya Voice Assistant** — LM Studio local + voice cloning

### Voice AI Frameworks
1. **Pipecat** (pipecat-ai/pipecat) — Python, by Daily.co
   - 18k+ stars, most active framework
   - Orchestrates STT→LLM→TTS pipeline with frame-based streaming
   - Supports 30+ services, WebRTC/WebSocket transports
   - Has Discord transport? Not natively — uses Daily/LiveKit rooms
   
2. **LiveKit Agents** — Go/Python
   - Full WebRTC platform with AI agent framework
   - Built-in STT/TTS/LLM orchestration
   - No native Discord integration

## 2. Voice AI APIs Comparison

### Option A: OpenAI Realtime API (Voice-to-Voice)
- **Latency:** ~300-500ms end-to-end (single service, no STT→LLM→TTS chain)
- **Pricing:** Audio input $32/1M tokens (~$0.06/min), Audio output $64/1M tokens (~$0.24/min)
- **Total:** ~$0.30/min of conversation
- **Mini variant:** gpt-realtime-mini: $10/1M input, $20/1M output — ~$0.06/min + $0.08/min = ~$0.14/min
- **Pros:** Lowest latency, simplest pipeline (no separate STT/TTS), built-in turn-taking
- **Cons:** Expensive for long sessions, locked to OpenAI models

### Option B: Modular Pipeline (STT + LLM + TTS)
**STT Options:**
- Deepgram Nova-3: $0.0043/min streaming, <300ms latency — best price/performance
- OpenAI Whisper API: $0.006/min
- OpenAI gpt-4o-mini-transcribe: $0.003/min (cheapest)
- Google Cloud STT: $0.016/min

**LLM:** Existing OpenClaw session (already paid for)

**TTS Options:**
- OpenAI gpt-4o-mini-tts: $0.015/min — good quality, lowest latency
- ElevenLabs: ~$0.18/1K chars, WebSocket streaming, <300ms latency
- Deepgram Aura TTS: $0.015/min
- Google Cloud TTS: $4/1M chars standard (free 4M/month)

**Best modular combo:** Deepgram STT ($0.0043/min) + OpenClaw LLM (existing) + OpenAI TTS ($0.015/min) = **~$0.02/min**

### Option C: Local/Hybrid
- Whisper.cpp local: Free, ~1-3s latency on CPU
- Piper TTS local: Free, fast on CPU
- Trade-off: Much higher latency, more CPU on server2

## 3. OpenClaw Architecture

### Current Discord Plugin
- 165K line bundled module at `dist/discord-BGqJ05Bl.js`
- Uses discord.js with text-only message handling
- Session routing: `agent:main:discord:channel:<CHANNEL_ID>`
- `@discordjs/voice v0.19.1` already in node_modules (unused)
- Plugin system: `registerPluginCommand()` pattern

### Integration Architecture Options

**Option 1: OpenClaw Plugin Extension (deep integration)**
- Extend Discord plugin to handle voice gateway events
- Add voice-related message types to session routing
- Pros: Native integration, shared sessions with text
- Cons: Requires OpenClaw core changes, complex

**Option 2: Standalone Bridge Process (recommended)**
- Separate Node.js process that:
  1. Uses the same Discord bot token
  2. Joins voice channels via @discordjs/voice
  3. Handles STT/TTS pipeline
  4. Bridges to agent sessions via `sessions_send` / `openclaw message send`
- Pros: Decoupled, can crash without affecting text bot, easy to iterate
- Cons: Separate process to manage, slight latency from session bridging

**Option 3: Pipecat + Custom Discord Transport**
- Write a Discord voice transport for Pipecat
- Pipecat handles the STT→LLM→TTS orchestration
- Pros: Best pipeline management, interruption handling
- Cons: Python (not Node.js), doesn't integrate with OpenClaw sessions natively

## 4. Cost & Operations

### Per-Hour Cost Estimates
| Approach | Cost/Hour | Notes |
|----------|-----------|-------|
| OpenAI Realtime (full) | ~$18/hr | Premium quality, lowest latency |
| OpenAI Realtime Mini | ~$8.40/hr | Good balance |
| Modular (Deepgram + OpenAI TTS) | ~$1.20/hr | Best value |
| Modular (local STT + cloud TTS) | ~$0.90/hr | Cheapest cloud |
| Fully local | ~$0/hr | Worst latency |

### Latency Budget (Modular Pipeline)
| Stage | Time |
|-------|------|
| Audio accumulation (silence detection) | 300-500ms |
| STT (Deepgram streaming) | 200-300ms |
| LLM (first token, streaming) | 500-2000ms |
| TTS (first chunk, streaming) | 200-400ms |
| Total end-to-end | **1.2-3.2s** |

### Infrastructure
- CPU: Minimal for Opus decode/encode (~1 core)
- RAM: ~100-200MB for voice connection + buffers
- Network: ~64kbps per user (Opus), negligible
- Can run on server2 alongside existing services

### Practical Challenges
- **Turn detection:** VAD (Voice Activity Detection) + silence threshold (200-500ms)
- **Interruptions:** Stop TTS playback when user starts speaking
- **Multi-speaker:** @discordjs/voice provides separate per-user streams
- **Echo cancellation:** Not needed (server-side, no mic feedback)
- **Bot joining UX:** Slash command `/join` or text command
