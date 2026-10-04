---
name: codex
description: Use OpenAI Codex CLI for complex debugging, code analysis, and getting a second AI perspective. Invoke when stuck on subtle bugs, spec mismatches, off-by-one errors, or when multiple approaches have failed.
---

# How to Use Codex from Claude Code

Codex is an AI-powered CLI tool that can help with complex debugging, code analysis, and technical questions. When you encounter difficult problems that would benefit from a second perspective or deep analysis, use Codex.

## Models (verified 2026-10-04, codex-cli 0.160.0, ChatGPT subscription login)

- Config default (`~/.codex/config.toml`): `gpt-6-astra` at `xhigh`.
- **Hard tasks: astra max** — `-m gpt-6-astra -c model_reasoning_effort=max`.
- Other models: `gpt-6.1-sol`, `gpt-6-sol`, `gpt-6-luna` (lighter). Efforts: `low|medium|high|xhigh|max` (`ultra` on astra/sol).
- Claude-side equivalent for hard tasks: `claude -p --model fable --effort max "<prompt>"`.

## When to Use Codex

- Debugging subtle bugs (e.g., bitstream alignment issues, off-by-one errors)
- Analyzing complex algorithms against specifications
- Getting a detailed code review with specific bug identification
- Understanding obscure file formats or protocols
- When you've tried multiple approaches and are stuck

## The File-Based Pattern

Codex works best with a file-based input/output pattern. Use a private temp dir so parallel sessions don't clobber each other:

```bash
D=$(mktemp -d)   # question in $D/question.txt, reply in $D/reply.txt
```

### Step 1: Create a Question File

Write your question and all relevant context to `$D/question.txt`:

```
Write to $D/question.txt:
- Clear problem statement
- The specific error or symptom
- The relevant code (full functions, not snippets)
- What you've already tried
- Specific questions you want answered
```

Example structure:
```
I have a [component] that fails with [specific error].

Here is the full function:
```c
[paste complete code]
```

Key observations:
1. [What works]
2. [What fails]
3. [When it fails]

Can you identify:
1. [Specific question 1]
2. [Specific question 2]
```

### Step 2: Invoke Codex

Q&A / analysis (read-only sandbox):

```bash
cat "$D/question.txt" | codex exec -m gpt-6-astra -c model_reasoning_effort=max -s read-only --skip-git-repo-check -o "$D/reply.txt"
```

Agentic run that edits files in a repo:

```bash
codex exec -m gpt-6-astra -c model_reasoning_effort=max --dangerously-bypass-approvals-and-sandbox -C <repo> -o "$D/reply.txt" "<task>"
```

Flags:
- `exec`: Non-interactive execution mode (required for CLI use); prompt from argument or stdin
- `-m` / `-c model_reasoning_effort=…`: model + effort (omit both for the config default, astra at xhigh)
- `-s read-only`: no writes; `--dangerously-bypass-approvals-and-sandbox`: full access, no prompts (`--full-auto` no longer exists)
- `--skip-git-repo-check`: needed when the cwd is not a git repo (e.g. `/tmp`)
- `-o "$D/reply.txt"`: write the final message to this file

**Runtime:** `max` effort can run well past the Bash tool's 120s default. Pass `timeout: 600000` for foreground runs. For anything that may take longer, detach so it survives session teardown and poll the reply file:

```bash
setsid bash -c 'cat "$0/question.txt" | codex exec -m gpt-6-astra -c model_reasoning_effort=max -s read-only --skip-git-repo-check -o "$0/reply.txt" > "$0/codex.log" 2>&1' "$D" </dev/null >/dev/null 2>&1 & disown
```

### Step 3: Read the Reply

```bash
Read $D/reply.txt
```

Codex will provide detailed analysis. Evaluate its suggestions critically - it may identify real bugs but can occasionally misinterpret specifications.

## Example Session

```
# 1. Create the question
D=$(mktemp -d)
Write $D/question.txt with:
- Problem: "Progressive JPEG decoder fails at block 1477 with Huffman error"
- Code: [full AC refinement function]
- Questions: "Identify bugs in EOB handling, ZRL handling, run counting"

# 2. Invoke Codex
cat "$D/question.txt" | codex exec -m gpt-6-astra -c model_reasoning_effort=max -s read-only --skip-git-repo-check -o "$D/reply.txt"

# 3. Read and apply
Read $D/reply.txt
# Codex identified 12 potential bugs with detailed explanations
# Evaluate each, verify against spec, apply fixes
```

## Tips

1. **Provide complete code**: Don't truncate functions. Codex needs full context.

2. **Be specific**: "Why does this fail?" is worse than "Why does Huffman decoding fail after processing 1477 blocks in AC refinement scan?"

3. **Include the spec**: If debugging against a standard (JPEG, PNG, etc.), mention the relevant spec sections.

4. **Verify suggestions**: Codex is helpful but not infallible. In one session, it incorrectly identified the EOB run formula as buggy when it was actually correct. Always verify against authoritative sources.

5. **Iterate if needed**: If the first response doesn't solve the problem, create a new question.txt with additional context from what you learned.

## Common Issues

**"stdin is not a terminal"**: Use `codex exec` not bare `codex`

**"unexpected argument '--full-auto'"**: Removed in recent codex-cli; use `-s read-only` or `--dangerously-bypass-approvals-and-sandbox`

**"Not inside a trusted directory"**: Add `--skip-git-repo-check` (or run from a git repo / pass `-C <repo>`)

**No output**: Check that `-o` flag has a valid path

## Alternative: Direct Piping

For shorter questions:
```bash
echo "Explain the JPEG progressive AC refinement algorithm" | codex exec -s read-only --skip-git-repo-check
```

But for debugging, the file-based pattern is better because you can refine the question and keep a record.
