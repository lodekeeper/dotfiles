# Adversarial Critique of `v1.md` (Ruthless Review)

**Target draft:** `/home/openclaw/research/web-search-skill/drafts/v1.md`  
**Reviewer stance:** skeptical, failure-oriented, ops-focused  
**Date:** 2026-03-06

---

## Major Conclusions: Stress-Test + Confidence

| # | Major conclusion in draft | Adversarial verdict | Confidence |
|---|---|---|---|
| 1 | Multi-provider orchestration is better than single-provider search | Directionally correct, but currently asserted without quantified evidence. Needs benchmark proof. | **HIGH** |
| 2 | Baseline should be Brave/SearxNG + fallback + verticals | Plausible architecture, but provider mix is opinionated and lacks cost/latency/coverage data. | **MEDIUM** |
| 3 | Query routing is the key quality lever | Likely true, but classifier error cost is ignored; wrong routing can be worse than broad fanout. | **MEDIUM** |
| 4 | Free/low-cost/growth pricing tiers are practical | Incomplete: no QPS assumptions, no expected query volume, no egress/ops labor costs. | **LOW** |
| 5 | Proposed MVP provider set is sufficient | Over-optimistic. Missing reliability/legal screening and provider-specific failure modes. | **LOW** |
| 6 | RRF + dedup + synthesis with citations yields trustworthy answers | Only if provenance is strict and quote-level grounding is enforced; draft does not enforce this yet. | **MEDIUM** |
| 7 | Operational reliability can be handled with circuit breakers + token buckets | Necessary but not sufficient. Missing observability, SLIs/SLOs, and degradation policies. | **MEDIUM** |

---

## Section-by-Section Critique

## 1) Executive Summary

### Weak claims
- “Answer-anything” is marketing language, not an engineering target.
- “Strongest approach” is asserted with no eval protocol or baseline numbers.

### Missing evidence
- No benchmark matrix (query classes, recall@k, latency p95, citation precision, cost/query).
- No justification for why this provider set beats alternatives.

### Hidden assumptions
- Assumes providers are independent enough to reduce correlated failure; in practice many depend on similar upstream indexes.
- Assumes synthesis improves quality rather than hallucination risk.

### Overlooked alternatives
- Retrieval-first/no-synthesis mode as default for safety-critical tasks.
- Domain-first search policies (e.g., “spec-only mode” for Ethereum protocol questions).

### Operational risks
- Overpromising capabilities increases trust risk when system fails on edge cases.

### Concrete fixes
1. Replace “answer-anything” with explicit target envelope (e.g., “>=85% citation-supported answers on defined benchmark”).
2. Add a one-page eval plan and minimum acceptance criteria.
3. Separate “retrieval quality” from “answer quality” metrics.

---

## 2) Problem Statement

### Weak claims
- Requirements are good but too generic; no measurable success definition.

### Missing evidence
- No user personas or query distribution assumptions.

### Hidden assumptions
- “Arbitrary internet questions” assumes uniform value across domains; in reality domain coverage requirements vary sharply.

### Operational risks
- Without scope boundaries, architecture will sprawl and become unmaintainable.

### Concrete fixes
1. Add scope statement: supported query classes for MVP vs out-of-scope.
2. Define SLAs: availability, latency, and citation integrity targets.
3. Add “fail closed” behavior for low-confidence answers.

---

## 3) Prior Art / Related Work

### Weak claims
- “Observed market shifts” (Google CSE sunsetting, Bing API retirement) are high-impact claims with no citations or verification timestamp.
- “SearxNG is strongest” is opinion presented as fact.

### Missing evidence
- No feature comparison table (cost, legal risk, freshness, geo coverage, quotas, metadata richness).

### Hidden assumptions
- Treats unofficial wrappers as only “fragile,” but not as potential compliance exposure.

### Overlooked alternatives
- Commercial APIs with stronger compliance/SLA guarantees.
- Existing retrieval orchestration frameworks that reduce custom maintenance.

### Operational risks
- Underspecified legal/ToS constraints can become production blockers.

### Concrete fixes
1. Add a cited provider matrix with “last verified” dates.
2. Add compliance column: ToS constraints, robots policy, redistribution rights.
3. Add kill-switch policy for unofficial endpoints.

---

## 4) Analysis

### 4.1 Why single-provider fails
**Good instinct, weak proof.**

- Missing quantified examples where single-provider fails vs routed ensemble.
- Should include at least 20–50 representative queries with failure annotations.

**Fix:** include a small benchmark appendix with head-to-head comparisons.

---

### 4.2 Free vs paid tiers
**Most fragile part of the draft.**

- Cost model is hand-wavy (“~$10–15/mo”, “$50+”) with no workload assumptions.
- Ignores engineering/ops labor cost of self-hosting SearxNG.
- Ignores infra costs (compute, bandwidth, monitoring, storage, retries).

**Fix:** add a workload-based cost table:
- assumptions: queries/day, avg fanout, fetch depth, cache hit ratio
- outputs: API cost, infra cost, ops burden, expected p95 latency

---

### 4.3 Query routing as key improvement
**Likely right, but under-specified and risky.**

- No routing confidence thresholds.
- No handling for multi-intent queries (e.g., “compare EIP implementation and papers”).
- No fallback when classifier confidence is low.

**Fix:**
1. Use multi-label routing with confidence-weighted fanout.
2. Add “uncertain intent => broad cheap fanout first, then refine.”
3. Log routing decisions + post-hoc win/loss attribution.

---

### 4.4 Operational reliability requirements
**Necessary primitives, missing operations doctrine.**

- Circuit breakers/token buckets/backoff are baseline mechanics only.
- Missing observability model (SLIs, SLOs, alerts, runbooks).
- Missing degradation policy (what user sees on partial outage).

**Fix:**
1. Define SLIs: success rate, non-empty citations, p95 latency, provider health score.
2. Define SLOs and burn-rate alerting.
3. Add deterministic degradation ladder:
   - full synthesis
   - retrieval-only with ranked links
   - cached results only
   - explicit failure message

---

## 5) Proposed Approach

### Weak claims / hidden assumptions
- “LLM fallback classifier” assumes classification quality > added latency/cost; unproven.
- “Optional deep mode” ignores prompt injection and data poisoning from fetched pages.

### Missing risks
- Security: fetched web content can inject hostile instructions into synthesis.
- Privacy: query logs may contain sensitive terms.
- Compliance: crawling and content reuse rights.

### Concrete fixes
1. Add content-safety layer before synthesis (strip scripts, limit promptable text, isolate instructions).
2. Enforce strict citation grounding: every synthesized claim must map to URL+quote snippet.
3. Add privacy policy for logs/retention and redaction.

---

## 6) Recommended Initial Provider Set (MVP)

### Critique
- Provider list is broad but unprioritized by reliability and legal confidence.
- Some sources are weak for guaranteed machine access over time.
- No “must-have vs optional” split tied to hard requirements.

### Concrete fixes
1. Split providers into tiers:
   - **Tier A (must-have stable):** 2 general providers + GitHub + one academic source
   - **Tier B (nice-to-have):** HN, StackExchange, Wikipedia
   - **Tier C (experimental):** sources with fragile access patterns
2. Add per-provider contract tests (schema, auth, quota, timeout behavior).
3. Define provider retirement policy (deprecate after sustained failure rate).

---

## 7) Tradeoffs

### Missing tradeoffs
- Not enough discussion of **latency vs coverage** and **precision vs recall**.
- No explicit “when not to synthesize.”

### Concrete fixes
- Add operating modes:
  1. **Fast mode:** minimal fanout, no deep fetch
  2. **Balanced mode:** moderate fanout + rerank
  3. **Research mode:** broad fanout + deep fetch + synthesis
- Expose mode selection in CLI and default conservatively.

---

## 8) Implementation Sketch

### Weaknesses
- High-level only; no data contracts.
- No canonical result schema.
- No testing plan beyond integration mention.

### Concrete fixes
1. Define a normalized result schema (`source`, `url`, `title`, `snippet`, `timestamp`, `score`, `provenance`, `license`).
2. Add deterministic reranking config and reproducibility controls.
3. Add test pyramid:
   - unit tests (routing, dedup, score fusion)
   - contract tests (providers)
   - replay tests (fixed query set)
   - chaos tests (timeouts, 429 storms)

---

## 9) Risk Assessment Table

### Gaps in current table
- Missing **security prompt-injection** risk from fetched pages.
- Missing **legal/compliance** risk for scraping and redistribution.
- Missing **quality drift** risk (provider index changes over time).
- Missing **vendor lock-in** risk.

### Concrete fixes
Add new rows:
1. Prompt injection via web content (High likelihood / High impact)
2. ToS/compliance violations (Medium / High)
3. Relevance drift after provider changes (High / Medium)
4. Silent citation mismatch bugs (Medium / High)

---

## 10) Open Questions

### Critique
- Questions are relevant but not prioritized by blocking impact.

### Concrete fixes
Reframe as decisions with deadlines:
1. **D0 (blocking):** default backbone provider strategy (self-hosted vs paid-first)
2. **D1 (blocking):** citation strictness policy (claim-level grounding requirements)
3. **D2 (non-blocking):** always-on synthesis vs opt-in
4. **D3 (non-blocking):** Ethereum routing precedence rules

---

## 11) Next Steps

### Critique
- Current steps are process-heavy and evidence-light.

### Concrete fixes (better execution sequence)
1. Build benchmark set (100 queries across classes + expected source types).
2. Implement minimal orchestrator with 3–4 stable providers.
3. Run baseline eval (quality/cost/latency).
4. Add synthesis only after retrieval metrics pass thresholds.
5. Expand providers based on measured marginal gain, not intuition.

---

## Non-Negotiable Additions Before Final `output.md`

1. **Evidence appendix** with citations for market/provider claims.
2. **Metrics + evaluation protocol** (retrieval and answer quality separated).
3. **Security/compliance section** (prompt-injection, ToS, data handling).
4. **Workload-based cost model** with explicit assumptions.
5. **Operational SLOs + degradation ladder**.

---

## Final Adversarial Verdict

The draft has strong architectural intuition but currently reads as **expert opinion without enough falsifiable evidence**. It is suitable as an internal hypothesis memo, not yet as a design decision record. Tighten claims, quantify tradeoffs, and harden security/compliance posture before implementation.

**Overall confidence in this critique:** **MEDIUM-HIGH**.