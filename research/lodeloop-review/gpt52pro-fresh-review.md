🧿 oracle 0.8.6 — AI confidence monitored, citations required.
Launching browser mode (gpt-5.2-pro) with ~5,894 tokens.
This run can take up to an hour (usually ~10 minutes).
Answer:
Below is a *code-level* review of your `lodeloop` loop runner as written. I’ll focus on real bugs / edge cases / robustness & security risks, and then contrast the architecture with **snarktank/ralph** and **frankbria/ralph-claude-code** (both “Ralph loop” implementations). ([GitHub][1])

I’ll refer to locations by **file + function + the relevant snippet** (since your paste doesn’t include line numbers).

---

## 1) Critical correctness bugs (will misbehave today)

### 1.1 `parse_args` can crash under `set -u` (missing `$2`)

**Where:** `lodeloop.sh:parse_args()`
**Snippet:** `-n|--max-iterations) MAX_ITERATIONS="$2"; shift 2 ;;` (same pattern for `--agent`, `--timeout`, `--notify`)

If user runs `lodeloop --timeout task.json` (forgetting the value), `$2` is unbound → immediate exit due to `set -u`.

**Fix:**
Add a helper to require a value:

```bash
require_arg() {
  local opt="$1"
  local val="${2-}"
  if [[ -z "$val" || "$val" == -* ]]; then
    echo "Error: $opt requires a value" >&2
    exit 1
  fi
}
```

and in parsing:

```bash
-n|--max-iterations) require_arg "$1" "${2-}"; MAX_ITERATIONS="$2"; shift 2 ;;
```

Also validate numeric inputs:

```bash
[[ "$MAX_ITERATIONS" =~ ^[0-9]+$ ]] || { echo "Error: --max-iterations must be an integer" >&2; exit 1; }
[[ "$ITER_TIMEOUT" =~ ^[0-9]+$ ]]    || { echo "Error: --timeout must be an integer seconds" >&2; exit 1; }
```

---

### 1.2 `parse_args` treats the *last* positional as TASK_FILE (silently)

**Where:** `lodeloop.sh:parse_args()`
**Snippet:** `*) TASK_FILE="$1"; shift ;;`

If someone does: `lodeloop task.json extra.json`, you’ll silently run `extra.json`. With automation tools, silent ambiguity is dangerous.

**Fix:** reject multiple positionals:

```bash
*) 
  if [[ -n "$TASK_FILE" ]]; then
    echo "Error: multiple task files provided: '$TASK_FILE' and '$1'" >&2
    exit 1
  fi
  TASK_FILE="$1"; shift ;;
```

---

### 1.3 Relative `workdir` is not resolved relative to task file

**Where:** `lodeloop.sh:resolve_paths()`
**Snippet:** `WORKDIR=$(jq -r '.workdir // ""' "$TASK_FILE")`

If task has `"workdir": "repo"` you interpret it relative to the *current shell directory*, not relative to the task file directory. This is a common footgun.

**Fix:** anchor relative paths to the task file directory:

```bash
local task_dir
task_dir="$(cd "$(dirname "$TASK_FILE")" && pwd)"

WORKDIR="$(jq -r '.workdir // empty' "$TASK_FILE")"
if [[ -z "$WORKDIR" || "$WORKDIR" == "null" ]]; then
  WORKDIR="$task_dir"
elif [[ "$WORKDIR" != /* ]]; then
  WORKDIR="$task_dir/$WORKDIR"
fi
WORKDIR="${WORKDIR/#\~/$HOME}"
```

Also error out if `WORKDIR` doesn’t exist:

```bash
[[ -d "$WORKDIR" ]] || { echo "Error: workdir not found: $WORKDIR" >&2; exit 1; }
```

---

### 1.4 You can mark the *wrong story* complete

**Where:** `lodeloop.sh:main()` after verification success
**Snippet:**

* On success you do: `story_id=$(jq -r '[.stories[] | select(.passes != true)] ... .[0].id' "$TASK_FILE")`
* Then unconditionally: `(.stories[] | select(.id == "$story_id")).passes = true`

This assumes the agent worked on “the first incomplete story” and that “verification passing” implies that story is complete. That is not guaranteed:

* verification may not cover the story at all (e.g., lint only)
* agent may have fixed something else
* agent may have changed nothing and tests already passed

**This is the biggest logic flaw**: your completion tracking isn’t causally linked to the work.

**Concrete fixes (pick one):**

1. **Require an explicit completion signal** from the agent output that includes story id, and parse it (Ralph-claude-code uses explicit exit/analysis signals; see its emphasis on “exit detection” / response analysis) ([GitHub][2])
   Example: agent must print `LODELOOP_DONE: STORY-123` after passing verification; you parse the last log file and only then mark `passes=true`.
2. **Require a matching commit**: only mark story complete if the last commit message includes that story id and the working tree is clean.
3. **Per-story verify commands**: each story defines its own acceptance checks; mark complete only if those pass.

---

### 1.5 `jq` update is injection-prone (story id containing quotes breaks JSON update)

**Where:** `lodeloop.sh:main()` story completion
**Snippet:** `jq "(.stories[] | select(.id == \"$story_id\")).passes = true" ...`

If `story_id` contains `"`, `\`, or `)` etc., the jq program becomes invalid or does something unintended. You’re reading story ids from user-controlled JSON, so treat it as hostile.

**Fix:** use `jq --arg`:

```bash
tmp=$(mktemp)
jq --arg sid "$story_id" '(.stories[] | select(.id == $sid)).passes = true' "$TASK_FILE" > "$tmp" && mv "$tmp" "$TASK_FILE"
```

Do the same in `handle_reset` if you mutate `.stories[]` fields.

---

### 1.6 `run_agent` always returns success (hides agent failure from the loop)

**Where:** `lodeloop.sh:run_agent()`
**Snippet:** after running the agent, you always `return 0`.

So even if Codex/Claude exits nonzero or times out, the outer loop can’t distinguish:

* a “no-op” iteration
* a “tool crashed / auth failed”
* a “timeout” iteration

This breaks circuit breaker behavior and diagnostics.

**Fix:** return the real exit code:

```bash
if [[ $exit_code -eq 124 ]]; then
  echo "⏱️  Agent timed out..."
fi
return "$exit_code"
```

Then in `main`, treat nonzero as an error signal for the circuit breaker and for `last_failure_context`.

---

## 2) Security risks (some are “expected”, but you should still harden)

### 2.1 `send_notification` is command injection (`eval`)

**Where:** `lib/notify.sh:send_notification()`
**Snippet:** `eval "$cmd" 2>/dev/null || true`

If `--notify` is supplied from anywhere untrusted (CI, shared scripts, copied examples), this is full RCE.

**Fix:** avoid eval. If you want “shell command string”, run it via `bash -c` but do not interpolate placeholders into code—pass values as env:

```bash
LODELOOP_STATUS="$status" LODELOOP_ITERATIONS="$iterations" LODELOOP_STORIES="$stories" \
  bash -c "$cmd"
```

…and document placeholders as `$LODELOOP_STATUS` etc. If you insist on `{status}` substitution, do it and then execute via an argv array *only when the notify format is restricted*, e.g., a single executable + args.

---

### 2.2 Verification commands execute arbitrary shell (`bash -c "$cmd"`)

**Where:** `lib/verify.sh:run_verification()`
This is likely intentional (project-defined checks), but it means `task.json` is effectively a script execution config. If the task file can be modified by the agent or by a malicious repo, you’ve created a self-escalating loop.

**Mitigations:**

* require task file ownership / permissions (e.g., refuse if world-writable)
* optionally support a “safe mode” that only allows commands from an allowlist (`npm test`, `pytest`, etc.)
* log each command + duration + exit code as structured JSON for postmortems

---

### 2.3 Claude permissions are overly broad (`Bash(.*)`)

**Where:** `lodeloop.sh:run_agent()` for claude
**Snippet:** `claude ... --allowedTools "Bash(.*)" "Read" "Write" "Edit"`

That effectively allows Claude to run any shell command without prompting. In contrast, **ralph-claude-code** defaults to a much more restricted tool allowlist (safe git subcommands + a couple of runners) explicitly to prevent destructive commands. ([GitHub][3])
(Also, Claude Code docs show `--allowedTools` takes a list of rules, e.g. `"Bash(git log *)" "Read"`. ([Claude][4]))

**Fix:** default to a restricted allowlist (and allow opt-out via config flag):

```bash
DEFAULT_ALLOWED_TOOLS=( "Read" "Write" "Edit" "Bash(git status*)" "Bash(git diff*)" "Bash(git add*)" "Bash(git commit*)" "Bash(npm test*)" "Bash(pytest*)" )
claude -p "$prompt" --allowedTools "${DEFAULT_ALLOWED_TOOLS[@]}"
```

…and provide `--allow-all-bash` if someone really wants it.

---

### 2.4 Context file exfiltration (you may leak secrets)

**Where:** `lib/prompt.sh:build_prompt()`
You slurp arbitrary `.context_files[]` content into the prompt. That can include `.env`, keys, credentials, prod configs.

**Fix:** add deny patterns by default (`.env`, `id_rsa`, `*.pem`, `.aws/`, etc.), and cap size:

```bash
max_bytes=20000
if [[ -f "$file" ]]; then
  [[ "$(wc -c <"$file")" -le "$max_bytes" ]] || continue
fi
```

Also print a warning listing any context files skipped due to deny rules or size.

---

## 3) Robustness issues / edge cases

### 3.1 Missing dependency checks (`jq`, `git`, `timeout`)

**Where:** multiple

* `resolve_paths` uses `jq`
* `main` uses `git`
* `run_agent` uses `timeout`

Under `set -e`, a missing command becomes a hard crash with little context.

**Fix:** at startup:

```bash
need_cmds=(jq timeout)
[[ "$AGENT" == "codex" ]] && need_cmds+=(codex) || need_cmds+=(claude)
for c in "${need_cmds[@]}"; do command -v "$c" >/dev/null || { echo "Missing dependency: $c" >&2; exit 1; }; done
```

(If you have fallback behavior like your NVM logic for codex, check `nvm` too.)

---

### 3.2 Concurrency: no lockfile → state corruption

If two `lodeloop` processes run in the same `WORKDIR`, you’ll race on:

* `.lodeloop/progress.md`
* `.lodeloop/circuit.json`
* `.lodeloop/result.json`
* and **task.json** itself

**Fix:** `flock` a lock file:

```bash
exec 9>"$STATE_DIR/lock"
flock -n 9 || { echo "Error: lodeloop already running for $WORKDIR" >&2; exit 1; }
```

---

### 3.3 Task file mutation is non-atomic and risky

You use `mktemp + mv`, which is good, but:

* you don’t preserve file permissions/ownership
* you can lose edits if editor is open
* you violate your own prompt instruction: “Do NOT modify task.json file — the loop runner handles story completion tracking.” (You *do* handle it, but the agent might still modify it. There’s no protection.)

**Fixes:**

* store state in `.lodeloop/state.json` and leave the user task file immutable; derive “completion” from state (safer)
* if you keep mutating task.json: validate it first, ensure it’s not symlinked (symlink attacks), and preserve mode:

```bash
[[ ! -L "$TASK_FILE" ]] || { echo "Refusing to modify symlinked task file" >&2; exit 1; }
mode=$(stat -c '%a' "$TASK_FILE" 2>/dev/null || stat -f '%Lp' "$TASK_FILE")
# after mv, chmod "$mode" "$TASK_FILE"
```

---

### 3.4 Circuit breaker “same error” is not actually “same error”

**Where:** `lib/circuit_breaker.sh:record_loop_result()`
You increment `consecutive_same_error` on *any* iteration with errors, regardless of whether it’s the same error.

**Fix:** hash the error signature and compare:

* store `last_error_hash`
* compute hash of (say) last 50 lines of verify output
* increment only if hash matches

You already have verify output available in `main` (`verify_output`). Pass an error hash into `record_loop_result` and compare in circuit breaker.

---

### 3.5 Verification runner continues after failure; logs are not captured well

**Where:** `lib/verify.sh`
You run all commands even after one fails, but you don’t summarize failures, and you return only `0/1`.

**Fix:** keep per-command status and exit codes, and emit a concise failure block the prompt can use:

* command
* exit code
* tail of output

Also, consider “fail fast” default with `--verify-continue` optional.

---

### 3.6 Git progress detection is weak and can be fooled

**Where:** `lodeloop.sh:main()`
You compute `files_changed` via:

* diff between start and current SHA *only if HEAD changed*
* plus uncommitted changes count

But:

* agent could amend commits, reset, or squash (HEAD changes in odd ways)
* agent could modify then revert (net zero diff)
* HEAD might not change if agent doesn’t commit; you still want to count actual diffs

**Fix:** track a baseline tree state:

* `git rev-parse HEAD^{tree}` for committed baseline
* plus hash of working tree + index (`git status --porcelain=v1` hash)
  or simpler: always compute `git diff --name-only HEAD` and `--cached` and treat non-empty as progress, and separately track if HEAD advanced.

---

### 3.7 Autocommit behavior is surprising and can be harmful

**Where:** `main()` on verification pass
You auto-commit *any* uncommitted changes with message `feat($project): $story_id` and ignore the agent’s requested message format.

Problems:

* commit message doesn’t include title (your prompt requests it)
* could commit accidental changes (formatting, secrets, debug logs)
* could commit when verification succeeded for unrelated reasons
* forces `--no-gpg-sign` silently

**Fixes:**

* only auto-commit if agent explicitly requested it (again: signal)
* enforce “working tree must be clean except expected files”
* allow `--no-auto-commit`
* never silently disable gpg signing; make it a flag

---

## 4) Prompt / loop design issues (why it gets stuck)

### 4.1 Failure context can explode token budget

**Where:** `lib/prompt.sh:failure_section`
You embed *full* `failure_context` inside a fenced code block. Verification output can be huge (test logs), and you then also include full task JSON and context files.

**Fix:**

* cap failure context size (e.g., last 200 lines or 20k chars)
* include a short summary: failing command + last N lines

---

### 4.2 You don’t provide a “stop condition” from the model side

**Ralph baseline:** snarktank/ralph exits when agent output contains `COMPLETE`. ([GitHub][5])
**Ralph-claude-code:** emphasizes “intelligent exit detection” with explicit exit signals and analysis. ([GitHub][2])

`lodeloop` relies on local story count reaching zero (but see 1.4: you may mark wrong stories complete). You also don’t parse model output for completion state, or detect “agent is stuck repeating itself”.

**Fix:** add an explicit loop protocol:

* agent must output `LODELOOP_PLAN`, `LODELOOP_DONE`, `LODELOOP_BLOCKED`, etc.
* analyze logs for repeated patterns (ralph-claude-code does semantic response analysis + circuit breaker sophistication) ([GitHub][2])

---

## 5) Missing features compared to the Ralph implementations

### 5.1 Archiving runs (snarktank/ralph)

Ralph archives `prd.json` and progress when branch changes. ([GitHub][5])
`lodeloop` overwrites logs per iteration but does not “archive a run” (e.g., when feature/task file changes, or when reset happens). That makes postmortems harder.

**Add:** `STATE_DIR/archive/<timestamp>/` snapshot:

* task file
* progress
* circuit state
* last N logs

---

### 5.2 Rate limiting / API overuse protection (frankbria/ralph-claude-code)

ralph-claude-code includes call rate limiting (default 100/hour) + session continuity and expiry. ([GitHub][2])
`lodeloop` only has a max iterations + per-iteration timeout; nothing controls “calls per hour” or “budget”.

**Add:**

* `--max-calls-per-hour`
* `--max-cost` or `--max-tokens` (if tools provide)
* sleep/backoff strategy on repeated failures

---

### 5.3 Safer tool permissions defaults (frankbria/ralph-claude-code)

ralph-claude-code defaults to restricted tool rules (safe git subcommands; avoids broad `Bash(git *)` because it enables destructive actions). ([GitHub][3])
`lodeloop` gives Claude `Bash(.*)` by default—much riskier.

---

### 5.4 Better “stuck loop” detection

ralph-claude-code calls out multi-stage response analysis + circuit breaker improvements. ([GitHub][2])
Your circuit breaker uses only `files_changed` and “any error counts as same error”.

**Add:**

* detect repeated identical verify tail
* detect “test-only loops” (they track this kind of pattern) ([GitHub][3])
* detect “no diff across N iterations” even if timestamps change

---

## 6) Concrete patch list (highest ROI)

If you only do 8 things, do these:

1. **Fix arg parsing** (`$2` required + numeric validation).
2. **Resolve `workdir` correctly** (relative to task file).
3. **Stop using `eval`** in notifications.
4. **Return the agent exit code** from `run_agent` and feed it into circuit breaker.
5. **Fix jq injection** with `--arg`.
6. **Do not mark stories complete unless you can prove which story was completed** (signal/commit/story-specific checks).
7. **Restrict Claude default allowed tools** (no `Bash(.*)` by default; match Claude Code’s documented allowed tool rules). ([Claude][4])
8. **Add lockfile** to prevent concurrent runs from corrupting state.

---

If you want, paste a representative `task.json` you use in practice (with a couple stories + verify section), and I’ll show a concrete “story completion protocol” that’s hard to game (commit-based + log-signal-based) while still keeping the loop simple.

[1]: https://github.com/snarktank/ralph "GitHub - snarktank/ralph: Ralph is an autonomous AI agent loop that runs repeatedly until all PRD items are complete."
[2]: https://github.com/frankbria/ralph-claude-code "GitHub - frankbria/ralph-claude-code: Autonomous AI development loop for Claude Code with intelligent exit detection"
[3]: https://raw.githubusercontent.com/frankbria/ralph-claude-code/main/ralph_loop.sh "raw.githubusercontent.com"
[4]: https://code.claude.com/docs/en/cli-reference?utm_source=chatgpt.com "CLI reference - Claude Code Docs"
[5]: https://raw.githubusercontent.com/snarktank/ralph/main/ralph.sh "raw.githubusercontent.com"


2m51s · gpt-5.2-pro[browser] · ↑5.89k ↓4.27k ↻0 Δ10.16k
