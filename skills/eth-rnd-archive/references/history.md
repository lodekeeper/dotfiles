# eth-rnd-archive — verification log

Dated evidence and one-off observations behind the recipes in `../SKILL.md`, moved out of it on 2026-10-04 to keep the skill short. The recipes themselves stay in SKILL.md; this file only records where and when they were verified.

## Resolving Discord message links

- 2026-09-24: channel mention `<#1552704440946139209>` matched the execution-dev "BAL retention window" thread starter stub to the millisecond.
- 2026-09-24 (seen once): a thread opened on a message starting with a mention rendered `<@774033563732541451>` as `@ignacio (jsign)` in the thread title.

## Reading linked posts and comments (all read-only)

- ethresear.ch, 2026-09-25: `https://ethresear.ch/t/<id>.json` returned HTTP 200, ~38 KB for topic 26086.
- GitHub PR / commit links, 2026-09-25: verified on execution-apis 40924d49, PR 885 and execution-specs PR 3652. execution-apis#885's body still described a field its latest commit had removed (PR body lagging its newest commit). A Discord link inside a PR body decoded to the top-level message that opened the thread it was posted in.
- Multi-commit PR recipe, 2026-09-25: verified on a merged 7-commit PR in a personal, non-fork repo (omerfirmak/zevm#58), where a fixture-version bump showed up as a one-line URL change in the workflow diff.
- X/Twitter via api.fxtwitter.com: verified on a trent_vanepps status; the `name=large` photo was ~330 KB, 2002x2048.
- GitHub release links, 2026-09-26: release notes for besu-eth/besu 26.9.0 were 12.7 KB. Its changelog line "Schedule the Amsterdam fork on Sepolia at timestamp 1791294816" converts offline to Tue 2026-10-06 13:53:36 UTC. Its `published_at` preceded the Discord post by 21.5h.

## ACD call outcomes

- EIPsInsight: verified on ACDE #246 (2026-09-24), HTTP 200; the recap resolved the retention-window and 200M gas-limit outcomes.
- Forkcast artifacts: `acde/2026-09-24_246` returned 200 while the `path` field form (`acde/246`) 404ed. Re-checked 2026-10-04: `acdc/2026-10-01_188/tldr.json` 200, `acdc/188/tldr.json` 404, `acdt/2026-09-28_098/tldr.json` 200 but `acdt/2026-09-28_98` 404 (keep the zero-padded `number`).
- A "Mon Sep 29" day label that was really a Tuesday was once logged, hence the weekday check.

## Searching the notes

- 2026-09-25: the ugrep context-window pattern `.{0,120}NEEDLE.{0,120}` aborted with `exceeds complexity limits` on the UTF-8 notes.

## Critical-alert keywords

- 2026-09-25: `<@&595681771690000403>` resolved as the Lodestar team role by usage (36 archive messages, e.g. barnabasbusa 2025-09-10 "lodestar<@&595681771690000403> nodes"); an inference, not a Discord lookup. Bare "cc <@&595681771690000403>" pings with no other keyword: tbenr 2025-10-31, parithosh 2026-01-30.
