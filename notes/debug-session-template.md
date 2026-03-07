# Debug Session Template

> Use this at the start of every non-trivial investigation.
> Copy to `memory/debug-<YYYY-MM-DD>-<topic>.md` and fill in as you go.
> Updated: 2026-03-07

---

## Session Header

| Field | Value |
|---|---|
| **Date** | YYYY-MM-DD |
| **Topic** | Brief title (e.g. "EPBS headState crash on restart") |
| **Linked PR / Issue** | #XXXX / N/A |
| **Environment** | Devnet / mainnet / local / kurtosis |
| **Node(s)** | e.g. `feat4`, `lodestar-b2` |
| **Time budget** | e.g. "2h max, then escalate" |

---

## 1. Symptom

*What's the observable failure? Exact error message, stack trace, or anomaly.*

```
<paste error / log snippet here>
```

**Reproduction rate:** Consistent / Occasional / Rare  
**First seen:** (commit / deploy / timestamp)  
**Impact:** Crash / Degraded perf / Silent data error / Other

---

## 2. Initial Hypotheses

*Before looking at any evidence. List at least two competing theories.*

1. **H1:** ...
2. **H2:** ...
3. **H3:** ...

---

## 3. Evidence Collected

*Timestamped log. Add entries as you go — don't reconstruct from memory later.*

### [HH:MM UTC] Initial triage
```bash
# commands run + outputs
```
**Finding:**

### [HH:MM UTC] <next investigation step>
```bash
# commands
```
**Finding:**

### [HH:MM UTC] ...

---

## 4. Ruled Out

*What have you eliminated, and why? This is as important as what you found.*

| Hypothesis | Evidence Against | Status |
|---|---|---|
| H1: ... | Log shows X, not Y | ❌ Ruled out |
| H2: ... | Cannot reproduce with X | ❌ Ruled out |

---

## 5. Working Theory

*Current best explanation for the failure.*

> **Theory:** ...
>
> **Confidence:** Low / Medium / High
>
> **Key supporting evidence:**
> - ...
> - ...

---

## 6. Root Cause (fill when confirmed)

*Exact root cause. Be specific — which file, which condition, which state.*

> **Root cause:**
>
> **Triggering condition:**
>
> **Why it wasn't caught earlier:**

---

## 7. Fix

*Describe the fix applied (or proposed). Link to PR.*

**Fix summary:**

**PR / Commit:**

**Regression test added?** Yes / No / N/A

---

## 8. Next Steps

- [ ] ...
- [ ] ...

---

## 9. Lessons Learned

*What would make this faster next time? Update AGENTS.md or relevant skill if significant.*

- ...

---

## Quick Reference: Common Starting Points

```bash
# Zombie/port check
lsof -iTCP:9000 -sTCP:LISTEN; lsof -iTCP:5052 -sTCP:LISTEN

# Run devnet triage script (if node name known)
bash ~/.openclaw/workspace/scripts/debug/devnet-triage.sh [node-name]

# Recent Loki errors (via grafana-loki skill)
# → see skills/grafana-loki/SKILL.md

# Git: recent commits on branch
git log --oneline -20

# Node.js heap snapshot (if memory issue)
# → see skills/memory-profiling/SKILL.md

# Check connected peers
curl -s http://localhost:9596/eth/v1/node/peers | jq '.data | length'

# Slot/epoch at suspected crash time (use beacon-node skill)
```
