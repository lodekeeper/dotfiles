# Research: Discord Voice Channel Participation for OpenClaw

**Date:** 2026-03-17
**Requested by:** Nico
**Duration:** ~45 minutes
**Confidence:** HIGH
**Models used:** Claude Opus (orchestration), Claude Sonnet (4 research agents + architecture design)

## Executive Summary

Adding voice channel support to Lodekeeper is **feasible, low-cost, and low-risk**. The recommended approach is a **standalone Node.js bridge process** that runs alongside OpenClaw, connecting to Discord voice channels via `@discordjs/voice` (already bundled in OpenClaw) and piping audio through a STT→LLM→TTS pipeline.

**Key numbers:**
- **Cost:** ~$0.02/min (Deepgram STT + OpenAI TTS) → ~$0.60/day at 30 min usage
- **Latency:** ~1.7s typical end-to-end (acceptable for AI voice assistant)
- **Dev effort:** 5-7 days for MVP, another 5-7 for production-ready
- **Resource impact:** ~150MB RAM, ~1 CPU core (manageable alongside consensus client)

The architecture is designed so the voice bridge can crash without affecting the existing text bot.

## Recommended Architecture

### Standalone Bridge Process

```
Discord Voice Channel
        │ Opus packets (UDP)
        ▼
┌──────────────────────────────────────┐
│     lodekeeper-voice (Node.js)       │
│                                      │
│  @discordjs/voice → VAD → Deepgram  │
│  streaming STT → Claude Sonnet →    │
│  OpenAI TTS → AudioPlayer → Discord │
└──────────────────────────────────────┘
        │ IPC (staging channel)
        ▼
┌──────────────────────────────────────┐
│     OpenClaw (existing, untouched)   │
│     Text bot (Telegram + Discord)    │
└──────────────────────────────────────┘
```

**Why standalone bridge over alternatives:**
- **vs Plugin extension:** Plugin bugs could crash the text bot. The Discord plugin is a 165K-line bundle — modifying it is fragile and breaks on OpenClaw upgrades
- **vs Pipecat:** Python framework in a Node.js ecosystem. No native Discord transport. Overkill for a single-bot deployment

### Provider Stack (Recommended)

| Component | Provider | Cost | Latency |
|-----------|----------|------|---------|
| STT | Deepgram Nova-3 (streaming) | $0.0043/min | 200-300ms |
| LLM | Claude Sonnet (via Anthropic API) | Existing spend | 400-800ms first token |
| TTS (MVP) | OpenAI TTS (tts-1, "onyx" voice) | $0.015/min | 400-600ms |
| TTS (v2) | ElevenLabs WebSocket streaming | ~$0.05/min | 200-300ms first chunk |

**Deepgram key advantage:** Streaming STT runs *concurrently* with speech — by the time the user stops talking, the transcript is already nearly complete. This shaves ~1s off perceived latency vs batch Whisper.

### Session Bridging

**MVP:** Bridge manages its own conversation history, calls Anthropic API directly. Voice context is isolated from text context (acceptable trade-off for simplicity).

**v2:** "Staging channel" pattern — create a hidden Discord text channel as a message bus. Bridge writes transcripts there, OpenClaw's existing text plugin picks them up naturally, agent responds, bridge reads response → TTS. **Zero OpenClaw core changes required.**

### Turn-Taking & Interruptions

- **VAD:** Deepgram's built-in `endpointing` (300ms silence threshold) handles turn detection natively
- **Interruption:** When user speaks while bot is talking, immediately stop TTS playback + abort in-flight requests
- **Multi-speaker (MVP):** First-speaker-wins FIFO queue
- **Multi-speaker (v2):** Parallel STT with ordered response queue

### server2 Resource Protection

- Process runs at `nice +10` (lower priority than consensus client)
- Max 1 concurrent voice channel enforced in code
- 300MB pm2 memory restart threshold
- Auto-leave on idle (5 min) + hard session cap (30 min)
- CPU kill switch: if free memory < 2GB, reject voice session

## Latency Budget

```
Stage                              Typical    Max
───────────────────────────────────────────────────
Deepgram endpointing (silence)     350ms      500ms
STT (overlaps with silence detect)  ~0ms*     200ms
LLM first token (Claude Sonnet)    800ms     2000ms
TTS first chunk (OpenAI / 11Labs)  250-500ms  900ms
Discord playback buffer             80ms      150ms
───────────────────────────────────────────────────
TOTAL                              ~1.7s     ~3.5s

* Streaming STT runs during speech — net latency ~0
```

The LLM first-token is the bottleneck. Mitigations: play a brief "thinking" sound, use Sonnet (not Opus) for speed, or upgrade to OpenAI Realtime API in v3 (~$0.14/min with mini, bypasses the STT→LLM→TTS chain entirely).

## Cost Analysis

| Scenario | Cost/Hour | Cost/Day (30 min) | Cost/Month |
|----------|-----------|-------------------|------------|
| MVP (Deepgram + OpenAI TTS) | $1.20 | $0.60 | ~$18 |
| Production (Deepgram + ElevenLabs) | $3.60 | $1.80 | ~$54 |
| Premium (OpenAI Realtime Mini) | $8.40 | $4.20 | ~$126 |
| Fully local (whisper.cpp + Piper) | $0 | $0 | $0 |

Risk of cost overrun is minimal — hard session cap (30 min) + idle timeout (5 min) prevent runaway charges.

## Implementation Plan

### Phase 1: MVP (5-7 days)
- Standalone `~/lodekeeper-voice/` project
- @discordjs/voice join/leave + audio receive
- Deepgram streaming STT
- Direct Claude Sonnet API call
- OpenAI TTS → AudioPlayer playback
- Basic interruption handling
- /voicejoin + /voiceleave slash commands

**Acceptance:** One user can have a 5-turn voice conversation, <4s latency, bot stops on interrupt.

### Phase 2: Production (5-7 days)
- Multi-speaker FIFO queue
- ElevenLabs WebSocket streaming TTS
- OpenClaw staging channel integration (shared context)
- Cost controls, idle timeout, health monitoring
- pm2 deployment with resource limits

### Phase 3: Polish (3-5 days)
- Custom Lodekeeper voice (ElevenLabs voice cloning)
- Cross-channel context (voice aware of text history)
- Wake word detection ("Hey Lodekeeper")
- Token/cost tracking per session

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Latency >3s (feels slow) | Medium | High | Streaming TTS, "thinking" sound, Sonnet for speed |
| CPU contention with beacon node | Medium | High | nice +10, max 1 channel, memory kill switch |
| Token reuse conflict (2 Discord clients) | Low | Medium | Try shared first; dedicated voice bot app if needed |
| STT mishears technical jargon | Low | Low | Deepgram keyword boosting for Ethereum terms |
| Cost overrun | Very Low | Low | Hard caps: 30 min session, 5 min idle timeout |
| @discordjs/voice native dep issues | Low | Medium | Pre-test; opusscript pure JS fallback available |

## Critical Notes / Open Questions

1. **Shared Discord token:** Two processes (OpenClaw + voice bridge) sharing one bot token *should* work — Discord supports concurrent text + voice gateways. But if OpenClaw's gateway connection doesn't include `GUILD_VOICE_STATES` intent, the bridge won't receive voice state updates. Need to verify OpenClaw's intent config, or create a dedicated voice bot application.

2. **Staging channel pattern (v2):** This is a creative hack — using a hidden Discord text channel as IPC. It works because OpenClaw's Discord plugin monitors all channels it can see. The risk: if OpenClaw throttles bot-only channels or treats them differently, this breaks. Test early.

3. **server2 CPU reality check:** server2 already runs at 86-91°C with 90%+ sustained CPU. Adding voice processing is a real concern. The `nice +10` + max-1-channel + memory kill switch should protect the beacon node, but monitor closely during initial deployment. Consider whether a cheaper VPS specifically for voice might be worth the isolation.

4. **Why not OpenAI Realtime API from the start?** It would be the simplest pipeline (voice-in → voice-out, no STT/TTS chain) with best latency (~300-500ms). But at $0.14-0.30/min it's 7-15x the modular approach. The architecture supports swapping to it later as a drop-in replacement for the STT→LLM→TTS chain.

## Sources

- @discordjs/voice v0.19.1 — https://discord.js.org/docs/packages/voice
- Deepgram Nova-3 — https://deepgram.com/pricing ($0.0043/min streaming)
- OpenAI TTS / Realtime pricing — https://developers.openai.com/api/docs/pricing
- ElevenLabs Conversational AI — https://elevenlabs.io/conversational-ai
- Pipecat framework — https://github.com/pipecat-ai/pipecat (18k+ stars)
- Discord-VC-LLM reference impl — https://github.com/Eidenz/Discord-VC-LLM
- AssemblyAI Discord voice tutorial — https://www.assemblyai.com/blog/build-a-discord-voice-bot-to-add-chatgpt-to-your-voice-channel

---

**Full architecture document:** ~/research/discord-voice-bot/drafts/architecture.md (911 lines)
**Research synthesis:** ~/research/discord-voice-bot/findings/synthesis.md
