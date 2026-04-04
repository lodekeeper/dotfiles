# Migration: anthropic/ API → claude-cli/ (Claude Code CLI)

## Why

Anthropic changed billing so third-party API apps draw from "extra usage" credits, not plan limits. If you're on a Max/Pro subscription, using the `anthropic/` provider hits API billing instead of your subscription. The `claude-cli/` backend routes through the Claude Code CLI binary, which authenticates via your subscription — no API credits needed.

## Steps

### 1. Verify Claude CLI is installed and authenticated

```bash
claude --version        # should be 2.x+
claude auth status      # should show authMethod: claude.ai, subscriptionType: max/pro
```

### 2. Add the claude-cli backend to openclaw.json

Under `agents.defaults.cliBackends`, add:

```json
"claude-cli": {
  "command": "/path/to/claude",
  "args": ["-p", "--output-format", "stream-json", "--verbose", "--permission-mode", "bypassPermissions"],
  "resumeArgs": ["-p", "--output-format", "stream-json", "--verbose", "--permission-mode", "bypassPermissions", "--resume", "{sessionId}"],
  "output": "jsonl",
  "input": "arg",
  "modelArg": "--model",
  "modelAliases": {
    "opus": "opus",
    "claude-opus-4-6": "opus",
    "sonnet": "sonnet",
    "claude-sonnet-4-6": "sonnet",
    "haiku": "haiku",
    "claude-haiku-3-5": "haiku"
  },
  "sessionArg": "--session-id",
  "sessionMode": "always",
  "sessionIdFields": ["session_id", "sessionId", "conversation_id", "conversationId"],
  "systemPromptArg": "--append-system-prompt",
  "systemPromptMode": "append",
  "systemPromptWhen": "first",
  "clearEnv": ["ANTHROPIC_API_KEY"],
  "serialize": false
}
```

Find your claude binary path with `which claude`.

### 3. Add claude-cli models to the catalog

Under `agents.defaults.models`:

```json
"claude-cli/claude-opus-4-6": { "alias": "opus" },
"claude-cli/claude-sonnet-4-6": { "alias": "sonnet" },
"claude-cli/claude-haiku-4-5": { "alias": "haiku" }
```

### 4. Update the default model

```json
"agents.defaults.model": {
  "primary": "claude-cli/claude-opus-4-6",
  "fallbacks": ["openai-codex/gpt-5.4"]
}
```

### 5. Update cron jobs

Change all cron jobs that use `anthropic/claude-*` models to `claude-cli/claude-*`:

```bash
# Find affected jobs
grep -n "anthropic/" ~/.openclaw/cron/jobs.json

# Replace (carefully, or edit manually)
sed -i 's|"anthropic/claude-opus-4-6"|"claude-cli/claude-opus-4-6"|g' ~/.openclaw/cron/jobs.json
sed -i 's|"anthropic/claude-sonnet-4-6"|"claude-cli/claude-sonnet-4-6"|g' ~/.openclaw/cron/jobs.json
```

### 6. Restart the gateway

```bash
systemctl --user restart openclaw-gateway
```

### 7. Verify

```bash
# Check startup logs
journalctl --user -u openclaw-gateway -n 20

# Confirm dispatches use claude-cli
journalctl --user -u openclaw-gateway | grep "cli exec"
# Should show: provider=claude-cli model=opus/sonnet

# Confirm no anthropic/ in active use
grep "anthropic/" ~/.openclaw/openclaw.json
# Should only appear in the models catalog, not in agents.defaults.model or cron jobs
```

## Key settings

| Setting | Recommended | Why |
|---------|-------------|-----|
| `serialize` | `false` | Allows parallel sessions (crons + conversations) |
| `maxConcurrent` | 10-20 | Each CLI process is ~200-400MB; scale to your RAM |
| `timeoutSeconds` (crons) | 600+ | CLI startup adds overhead vs direct API |

## Known cosmetic issue

Gateway startup logs `startup model warmup failed for claude-cli/claude-opus-4-6: Error: Unknown model`. This is harmless — the warmup probe uses the fully-qualified name but runtime routing via aliases works fine.

## Keeping anthropic/ entries

You can leave `anthropic/` entries in the models catalog — they're just idle definitions. Just make sure nothing references them as a primary model or in cron job payloads.
