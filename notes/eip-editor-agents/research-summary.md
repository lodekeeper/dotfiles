# EIP Editor Feedback AGENTS.md Research

Date: 2026-08-04

Scope: `ethereum/EIPs` pull requests #12093 down to #10981, the latest 1000 PRs by creation order at scrape time.

Method:
- Read existing repo guidance: `EIPS/eip-1.md`, `eip-template.md`, `.github/PULL_REQUEST_TEMPLATE.md`, and `.github/instructions/review.instructions.md`.
- Scraped issue comments, inline review comments, and review bodies for the sampled PRs using GitHub REST API as `lodekeeper`.
- Filtered human comments to current and emeritus EIP editors listed in `EIPS/eip-1.md`.
- Used regex buckets only as triage/ranking signals; final AGENTS.md wording was manually distilled from the repo guidance plus inspected examples.

Data:
- Raw PR list: `notes/eip-editor-agents/data/recent_prs.json`
- Raw all-comments JSONL: `notes/eip-editor-agents/data/all_comments.jsonl`
- Editor-filtered JSONL: `notes/eip-editor-agents/data/editor_comments.jsonl`
- Heuristic summary JSON: `notes/eip-editor-agents/data/summary.json`
- Local EIPs draft: `/home/openclaw/EIPs-agents-md/AGENTS.md`

Counts:
- Sampled PRs: 1000
- Non-empty comments/review bodies scraped: 5414
- Non-empty current/emeritus editor comments/review bodies: 1147
- Editor comment authors in the sample: `jochem-brouwer` 729, `SamWilsn` 206, `g11tech` 104, `lightclient` 65, `gcolvin` 32, `xinbenlv` 11.

Recurring editor-feedback themes observed:
- Normative language and RFC 2119/8174 placement: uppercase requirements outside Specification are repeatedly flagged, including in Security Considerations.
- Template/section structure: missing or misplaced Test Cases, Backwards Compatibility, Copyright, Rationale, and Specification content come up often.
- Front matter and filename hygiene: title case, sentence-case description, matching `eip:` number and filename, author/discussions/status/category fields.
- Final/status wording: proposals should read as if already Final; editor comments discourage future-tense/process-state wording and references to proposal statuses in stable text.
- Dependencies: `requires` should be present for real dependencies, but editors also push back on circular or unnecessary dependencies.
- Links/assets: external links are often rejected unless they are EIP-1-permitted/pinned; reviewers suggest moving files into `assets/eip-N/` and using relative links.
- Motivation vs Rationale: editors move problem justification to Motivation and design-choice explanation to Rationale.
- Security Considerations: the section must be proposal-specific, not generic advice.
- Core-EIP tests: Test Cases can be TODO in Draft, but consensus-affecting Core proposals need real tests before advancement.
- Scope routing: ERC-style proposals are redirected to `ethereum/ERCs`; technical-content debate is redirected to Ethereum Magicians.

Important existing artifact:
- The repo already has `.github/instructions/review.instructions.md`, which is a solid AI-review seed. The root `AGENTS.md` draft should not replace it blindly; it should either incorporate it, point to it, or consolidate the guidance so authors and generic coding agents see the same rules before opening PRs.
