# OpenClaw Compaction & Memory Internals — Deep Dive

> Generated: 2026-02-26  
> Source: OpenClaw docs (concepts, reference, gateway config) + current `openclaw.json`

---

## A. COMPACTION MECHANICS

### Trigger Conditions

Auto-compaction fires in **two** scenarios (Pi runtime semantics):

1. **Overflow recovery**: The model returns a **context overflow error** → compact → retry the original request.
2. **Threshold maintenance**: After a *successful* turn, when:
   ```
   contextTokens > contextWindow - reserveTokens
   ```
   Where `contextWindow` is the model's context window and `reserveTokens` is headroom for prompts + next model output.

### What Gets Summarized vs Preserved

- **Summarized**: Older conversation history is compressed into a single `compaction` entry in the transcript JSONL.
- **Preserved**:
  - The compaction summary itself (persisted in JSONL with `firstKeptEntryId` and `tokensBefore`)
  - All messages **after** `firstKeptEntryId` (controlled by `keepRecentTokens`)
  - System prompt, workspace files, tool schemas — rebuilt fresh each run

After compaction, the model sees: `[compaction summary] + [recent messages after cutoff]`.

### Configurable Parameters

| Parameter | Default | Location | Purpose |
|-----------|---------|----------|---------|
| `compaction.enabled` | `true` | Pi settings | Master switch |
| `compaction.reserveTokens` | `16384` | Pi settings | Headroom reserved before compaction triggers |
| `compaction.keepRecentTokens` | `20000` | Pi settings | Recent messages to preserve through compaction |
| `compaction.reserveTokensFloor` | `20000` | `agents.defaults.compaction` | **Floor** enforced by OpenClaw — if Pi's `reserveTokens` is below this, OpenClaw bumps it up |
| `compaction.mode` | `"default"` | `agents.defaults.compaction` | `"default"` or `"safeguard"` — safeguard enables chunked summarization for very long histories |

**Our current config**:
```json
"compaction": { "mode": "safeguard" }
```
- `reserveTokensFloor` is NOT explicitly set → uses default `20000`
- `mode` is `"safeguard"` → chunked summarization enabled ✅

### How the Summary Is Generated

- Compaction runs as an **embedded Pi agent turn** — the same model that runs the session generates the summary.
- The summary is stored as a `compaction` entry in the JSONL transcript with:
  - `firstKeptEntryId`: pointer to where "kept" messages start
  - `tokensBefore`: token count before compaction
- In `"safeguard"` mode: history is chunked for summarization (handles very long sessions better than default).

### Implementation Path

- Floor enforcement: `ensurePiCompactionReserveTokens()` in `src/agents/pi-settings.ts`
- Called from: `src/agents/pi-embedded-runner.ts`

---

## B. MEMORY FLUSH (PRE-COMPACTION)

### Mechanism

Before auto-compaction fires, OpenClaw runs a **silent agentic turn** that instructs the model to write durable state to disk. This is the "memory flush."

### Timing / Trigger

The flush fires when:
```
sessionTokenEstimate > contextWindow - reserveTokensFloor - softThresholdTokens
```

This is a **soft threshold** — it triggers *before* compaction would fire, giving the model a chance to persist state.

**Sequence:**
1. Session token estimate crosses soft threshold → **memory flush fires**
2. Silent turn runs (model writes to `memory/YYYY-MM-DD.md` or similar)
3. Token count continues rising → **compaction fires** at the hard threshold
4. Older history is summarized; flush data survives on disk

### Configuration

```json5
agents.defaults.compaction.memoryFlush: {
  enabled: true,              // default: true
  softThresholdTokens: 4000,  // default: 4000 — gap between flush and compaction
  systemPrompt: "Session nearing compaction. Store durable memories now.",
  prompt: "Write any lasting notes to memory/YYYY-MM-DD.md; reply with NO_REPLY if nothing to store."
}
```

### Current Config

**Not explicitly configured** in our `openclaw.json` → all defaults apply:
- `enabled`: `true`
- `softThresholdTokens`: `4000`
- Default system/user prompts with `NO_REPLY` suppression

### Key Behaviors

- **Silent**: Uses `NO_REPLY` convention — user never sees the flush turn
- **Streaming suppression**: As of 2026.1.10, partial streaming is also suppressed when output starts with `NO_REPLY`
- **One flush per compaction cycle**: Tracked via `memoryFlushAt` and `memoryFlushCompactionCount` in `sessions.json`
- **Requires writable workspace**: Skipped when `workspaceAccess: "ro"` or `"none"`
- **Only embedded Pi sessions**: CLI backends skip the flush

### Customization Opportunities

**Yes, both prompts are fully customizable.** We can improve state preservation by:

1. **Increasing `softThresholdTokens`** (e.g., `6000`–`8000`) to give the model more time/tokens for the flush turn
2. **Customizing the prompts** to be more specific about what to preserve:
   ```json5
   memoryFlush: {
     enabled: true,
     softThresholdTokens: 8000,
     systemPrompt: "CRITICAL: Session is about to be compacted. You MUST preserve the following to memory/YYYY-MM-DD.md:\n1. Current task state and progress\n2. Active PR numbers and branches\n3. Any decisions made this session\n4. Pending items and next steps\n5. Key file paths and code locations being worked on",
     prompt: "Write a structured state dump to memory/YYYY-MM-DD.md covering all active work context. Use headers for organization. Reply with NO_REPLY when done."
   }
   ```
3. **Increasing `reserveTokensFloor`** (e.g., `24000`) to ensure the flush turn has enough headroom to actually execute tool calls (read/write files)

---

## C. SESSION PRUNING

### Current Config

**Not explicitly configured** in our `openclaw.json`. Pruning behavior:

- For **Anthropic OAuth/setup-token** profiles: `cache-ttl` pruning is auto-enabled with heartbeat `1h`
- For **Anthropic API key** profiles: `cache-ttl` pruning is auto-enabled, heartbeat `30m`, `cacheControlTtl` `1h`
- We're using Anthropic with a setup token (`anthropic:default` mode `token`) → smart defaults likely apply

### How Pruning Works

- **Mode**: `cache-ttl` — pruning runs when last Anthropic call is older than `ttl` (default `5m`)
- **What it prunes**: Only `toolResult` messages. User/assistant messages are **never modified**
- **In-memory only**: Does NOT rewrite JSONL on disk
- **Protected**: Last `keepLastAssistants` (default `3`) assistant messages' tool results are safe
- **Image blocks**: Never trimmed

### Pruning Stages

1. **Soft-trim** (oversized results): Keep head + tail, insert `...`, append size note
   - `maxChars: 4000`, `headChars: 1500`, `tailChars: 1500`
2. **Hard-clear** (oldest results): Replace entire result with placeholder
   - `placeholder: "[Old tool result content cleared]"`

### Interaction with Compaction

Pruning and compaction are **independent mechanisms**:
- **Pruning**: Transient, per-request, reduces what the model sees
- **Compaction**: Persistent, rewrites transcript history

**Can aggressive pruning delay compaction?** Yes, indirectly:
- Pruning reduces the in-memory token count the model processes
- But `contextTokens` tracking is a runtime estimate — if pruning reduces the effective context, the compaction threshold takes longer to hit
- However, pruning doesn't change the stored token counters used for compaction decisions
- **Net effect**: Pruning buys time before compaction but doesn't prevent it

### Configuration Options

```json5
agents.defaults.contextPruning: {
  mode: "cache-ttl",           // off | cache-ttl | adaptive | aggressive
  ttl: "5m",                   // for cache-ttl mode
  keepLastAssistants: 3,
  softTrimRatio: 0.3,          // adaptive mode
  hardClearRatio: 0.5,         // adaptive mode
  minPrunableToolChars: 50000, // adaptive mode
  softTrim: { maxChars: 4000, headChars: 1500, tailChars: 1500 },
  hardClear: { enabled: true, placeholder: "[Old tool result content cleared]" },
  tools: { allow: ["exec", "read"], deny: ["*image*"] }  // restrict which tools get pruned
}
```

---

## D. MEMORY SEARCH

### Current Config

We're using **memory-lancedb** plugin (not the default `memory-core`):

```json
"plugins": {
  "slots": {
    "memory": "memory-lancedb"
  },
  "entries": {
    "memory-lancedb": {
      "enabled": true,
      "config": {
        "embedding": {
          "apiKey": "sk-proj-...",  // OpenAI key
          "model": "text-embedding-3-small"
        },
        "autoCapture": true,
        "autoRecall": true
      }
    }
  }
}
```

### What This Means

- **Provider**: LanceDB (vector DB plugin, replacing default SQLite-based `memory-core`)
- **Embedding model**: OpenAI `text-embedding-3-small`
- **Auto-capture**: `true` — automatically captures memories
- **Auto-recall**: `true` — automatically recalls relevant memories
- Tools: `memory_search`, `memory_store`, `memory_recall`, `memory_forget` (provided by plugin)

### QMD Backend

**Status: NOT enabled.**

QMD is an experimental alternative backend that combines BM25 + vectors + reranking. It requires:
- Installing the QMD CLI separately
- Setting `memory.backend = "qmd"` in config
- SQLite with extension support

**Should it be enabled?** For our use case (long-running autonomous agent):
- **Pros**: Hybrid BM25 + vector search is stronger for exact tokens (IDs, code symbols, error strings). Session JSONL indexing (`memory.qmd.sessions.enabled`) would let us recall past conversations.
- **Cons**: Extra dependency, runs as subprocess, first queries are slow (model downloads). We already have LanceDB which is solid for vector search.
- **Recommendation**: Not urgent. LanceDB + OpenAI embeddings is a good baseline. Consider QMD if we find vector-only search missing exact-match queries.

### Session Memory Search

**Status: NOT enabled.**

Available as experimental feature:
```json5
agents.defaults.memorySearch: {
  experimental: { sessionMemory: true },
  sources: ["memory", "sessions"]
}
```

This would index session transcripts and make them searchable via `memory_search`. Could be valuable for our long-running agent to recall past session context.

**Note**: This is the `memory-core` feature path. Since we're using `memory-lancedb`, we'd need to check if the LanceDB plugin has equivalent session indexing.

### Hybrid Search (BM25 + Vector)

Available in the default `memory-core` backend:
```json5
agents.defaults.memorySearch.query.hybrid: {
  enabled: true,
  vectorWeight: 0.7,
  textWeight: 0.3,
  candidateMultiplier: 4
}
```

**Not applicable** to our `memory-lancedb` setup — LanceDB has its own search semantics.

---

## E. CONFIGURATION OPPORTUNITIES

### What We Could Change to Improve Resilience

#### 1. Tune Memory Flush (HIGH IMPACT)

```json5
compaction: {
  mode: "safeguard",
  reserveTokensFloor: 24000,  // up from 20000 — more headroom for flush
  memoryFlush: {
    enabled: true,
    softThresholdTokens: 8000,  // up from 4000 — earlier flush trigger
    systemPrompt: "CRITICAL: Session nearing compaction. Preserve all active task state, decisions, PR numbers, branches, file paths, and next steps to memory files NOW.",
    prompt: "Write a comprehensive state dump to memory/YYYY-MM-DD.md. Include: (1) active tasks and progress, (2) current branch/PR context, (3) recent decisions, (4) pending items. Reply NO_REPLY when done."
  }
}
```

#### 2. Enable Context Pruning (MEDIUM IMPACT)

We don't have explicit pruning configured. Adding it would extend session life:
```json5
contextPruning: {
  mode: "adaptive",
  keepLastAssistants: 5,
  softTrimRatio: 0.25,
  hardClearRatio: 0.45,
  tools: { deny: ["browser", "canvas"] }  // keep browser/canvas results intact
}
```

#### 3. Increase Context Token Budget (LOW-MEDIUM IMPACT)

```json5
agents.defaults.contextTokens: 200000  // explicitly set for Claude Opus 4.6
```
This ensures the context window is fully utilized.

#### 4. Session Reset Tuning

Currently using defaults (daily reset at 4am). For long-running autonomous agent:
```json5
session: {
  reset: {
    mode: "daily",
    atHour: 4,
    idleMinutes: 480  // 8 hours idle before reset
  }
}
```

### Features Available But Not Enabled

| Feature | Status | Config Path | Notes |
|---------|--------|-------------|-------|
| Session memory search | OFF | `memorySearch.experimental.sessionMemory` | Would let agent recall past sessions |
| QMD backend | OFF | `memory.backend: "qmd"` | Hybrid BM25+vector, session JSONL indexing |
| Embedding cache | OFF (or default) | `memorySearch.cache.enabled` | Reduces re-embedding costs |
| Extra memory paths | OFF | `memorySearch.extraPaths` | Index docs outside workspace |
| Memory citations | default | `memory.citations` | `auto`/`on`/`off` for source attribution |
| Custom flush prompts | DEFAULT | `compaction.memoryFlush.prompt` | Generic prompts, could be specialized |
| Adaptive pruning | OFF | `contextPruning.mode: "adaptive"` | Would extend context lifetime |
| Block streaming | OFF | `blockStreamingDefault` | Incremental responses |

### Optimal Configuration for Long-Running Autonomous Agent

```json5
{
  agents: {
    defaults: {
      compaction: {
        mode: "safeguard",
        reserveTokensFloor: 24000,
        memoryFlush: {
          enabled: true,
          softThresholdTokens: 8000,
          systemPrompt: "CRITICAL: Session nearing compaction. You MUST persist all active work state to disk before context is lost. Include: task progress, PR/branch context, decisions, code locations, pending items, and next steps.",
          prompt: "Write a structured state dump to memory/YYYY-MM-DD.md. Organize by: ## Active Tasks, ## Decisions, ## Context, ## Next Steps. Reply NO_REPLY when done."
        }
      },
      contextPruning: {
        mode: "adaptive",
        keepLastAssistants: 5,
        softTrimRatio: 0.25,
        hardClearRatio: 0.45,
        minPrunableToolChars: 30000,
        softTrim: { maxChars: 6000, headChars: 2500, tailChars: 2500 },
        hardClear: { enabled: true, placeholder: "[Older tool output cleared — re-read file if needed]" }
      },
      contextTokens: 200000
    }
  }
}
```

---

## F. WORKSPACE FILES

### Files Injected Into Context Automatically

OpenClaw injects these workspace files (if present) under **"Project Context"** in the system prompt:

| File | Purpose | Behavior |
|------|---------|----------|
| `AGENTS.md` | Global instructions, coding conventions | Always loaded |
| `SOUL.md` | Personality, tone, identity | Always loaded |
| `TOOLS.md` | Local tool notes (cameras, SSH hosts, etc.) | Always loaded |
| `IDENTITY.md` | Agent identity | Always loaded |
| `USER.md` | User preferences | Always loaded |
| `HEARTBEAT.md` | Heartbeat checklist | Always loaded |
| `BOOTSTRAP.md` | First-run instructions | First run only |

### Size Control

- **Per-file truncation**: `agents.defaults.bootstrapMaxChars` (default `20000` chars)
- Files exceeding this are truncated (head + tail with marker)
- `/context list` shows raw vs injected sizes and whether truncation occurred

### Can We Control What Gets Loaded?

- **No opt-out per file** — all present files in the set are loaded
- **Size control**: Reduce `bootstrapMaxChars` to limit per-file injection
- **Content control**: Edit the files themselves — they're plain markdown
- **Skip bootstrap creation**: `agents.defaults.skipBootstrap: true` prevents auto-creation of default files (but won't prevent loading existing ones)

### How Workspace Files Interact with Compaction

**Workspace files are NOT part of the conversation history.** They are:
- Rebuilt fresh in the **system prompt** on every run
- Never summarized by compaction
- Always present regardless of compaction state

This means:
- **Workspace files survive compaction perfectly** — they're always re-injected
- **They count against context budget** every turn — a large `AGENTS.md` or `TOOLS.md` reduces space for conversation history
- **They accelerate compaction** — more tokens consumed by workspace files = less room for history = earlier compaction trigger

### Current Workspace File Impact

From `/context list`, our workspace loads:
- `AGENTS.md`: ~436 tokens
- `TOOLS.md`: Potentially large (could be truncated at 20k chars ≈ ~5k tokens)

**Optimization**: Keep workspace files lean. Every 1000 tokens saved in workspace files = 1000 more tokens of conversation history before compaction.

---

## APPENDIX: Session Store Fields (Compaction-Related)

From `sessions.json` per session key:

| Field | Purpose |
|-------|---------|
| `sessionId` | Current transcript file id |
| `compactionCount` | Number of auto-compactions completed |
| `memoryFlushAt` | Timestamp of last pre-compaction memory flush |
| `memoryFlushCompactionCount` | Compaction count when last flush ran |
| `inputTokens` / `outputTokens` / `totalTokens` | Rolling token stats |
| `contextTokens` | Runtime context estimate (not a guarantee) |

## APPENDIX: Transcript Entry Types

| Type | In Model Context? | Persisted? |
|------|-------------------|------------|
| `message` | Yes | Yes (JSONL) |
| `custom_message` | Yes (can be hidden from UI) | Yes (JSONL) |
| `custom` | No | Yes (JSONL) |
| `compaction` | Yes (as summary) | Yes (JSONL) |
| `branch_summary` | Yes | Yes (JSONL) |

## APPENDIX: Full Configuration Reference Paths

```
agents.defaults.compaction.mode                          # "default" | "safeguard"
agents.defaults.compaction.reserveTokensFloor            # number (default 20000)
agents.defaults.compaction.memoryFlush.enabled            # boolean (default true)
agents.defaults.compaction.memoryFlush.softThresholdTokens # number (default 4000)
agents.defaults.compaction.memoryFlush.systemPrompt       # string
agents.defaults.compaction.memoryFlush.prompt             # string
agents.defaults.contextPruning.mode                      # "off" | "cache-ttl" | "adaptive" | "aggressive"
agents.defaults.contextPruning.ttl                       # duration (cache-ttl mode)
agents.defaults.contextPruning.keepLastAssistants        # number (default 3)
agents.defaults.contextPruning.softTrimRatio             # number (default 0.3)
agents.defaults.contextPruning.hardClearRatio            # number (default 0.5)
agents.defaults.contextPruning.minPrunableToolChars      # number (default 50000)
agents.defaults.contextPruning.softTrim.maxChars         # number (default 4000)
agents.defaults.contextPruning.softTrim.headChars        # number (default 1500)
agents.defaults.contextPruning.softTrim.tailChars        # number (default 1500)
agents.defaults.contextPruning.hardClear.enabled         # boolean (default true)
agents.defaults.contextPruning.hardClear.placeholder     # string
agents.defaults.contextPruning.tools.allow               # string[]
agents.defaults.contextPruning.tools.deny                # string[]
agents.defaults.contextTokens                            # number
agents.defaults.bootstrapMaxChars                        # number (default 20000)
agents.defaults.memorySearch.provider                    # "openai" | "gemini" | "voyage" | "local"
agents.defaults.memorySearch.model                       # string
agents.defaults.memorySearch.extraPaths                  # string[]
agents.defaults.memorySearch.experimental.sessionMemory  # boolean
agents.defaults.memorySearch.sources                     # ("memory" | "sessions")[]
agents.defaults.memorySearch.query.hybrid.enabled        # boolean
agents.defaults.memorySearch.query.hybrid.vectorWeight   # number
agents.defaults.memorySearch.query.hybrid.textWeight     # number
agents.defaults.memorySearch.cache.enabled               # boolean
agents.defaults.memorySearch.cache.maxEntries            # number (default 50000)
memory.backend                                           # "qmd" (opt-in)
memory.citations                                         # "auto" | "on" | "off"
memory.qmd.command                                       # string
memory.qmd.includeDefaultMemory                          # boolean
memory.qmd.paths[]                                       # extra index paths
memory.qmd.sessions.enabled                              # boolean (session JSONL indexing)
memory.qmd.sessions.retentionDays                        # number
memory.qmd.update.interval                               # duration (default "5m")
memory.qmd.limits.maxResults                             # number
memory.qmd.limits.timeoutMs                              # number
plugins.slots.memory                                     # "memory-core" | "memory-lancedb" | "none"
session.reset.mode                                       # "daily" | "idle"
session.reset.atHour                                     # number
session.reset.idleMinutes                                # number
```
