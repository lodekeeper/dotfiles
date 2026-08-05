## Summary

- Add a root `AGENTS.md` draft for EIP author/agent review guidance.
- Consolidate EIP-1, `eip-template.md`, the PR template, existing `.github/instructions/review.instructions.md`, and recurring editor feedback from recent PRs.
- Keep the scope as internal review on the `lodekeeper/EIPs` fork before considering any upstream PR.

## Research Notes

This draft was informed by a scrape of the latest 1000 `ethereum/EIPs` PRs at the time of the run (#12093 down to #10981): 5414 non-empty comments/review bodies total, 1147 from current/emeritus editors listed in EIP-1.

Workspace research artifacts:

- `notes/eip-editor-agents/research-summary.md`
- `notes/eip-editor-agents/data/`
- `scripts/github/scrape_eips_editor_feedback.py`

## Verification

- `git diff --check HEAD^..HEAD`

## Disclosure

Drafted with AI assistance.
