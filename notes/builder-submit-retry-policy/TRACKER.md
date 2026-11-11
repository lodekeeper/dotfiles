# Builder submit timeout/retry policy

Source: wemeetagain #10526 issuecomment6778723811, routed2026-11-10T20:48UTC.

Base unstable:a3ea62064abc4023be4ce3c09f24d0ed2849c366. #10526 remainsOPEN at6ec55d55558a91ed0b66201f80eba5b9d075e24a.

- [x] BACKLOG logged; live source/PR comments and existing ownership checked.
- [x] Recovered earlier same-turn attempt from topic50 sessions_history: /home/openclaw/lodestar-builder-submit-deadline (branchfix/builder-submit-slot-deadline),3modifiedsourcefiles+http.test.ts. No live implementer process. Previous4realclienttests passed with customVitestconfig/staledonor dependencies; standardtests failed missing@lodestar/native and types201errors. These are not a passing quality gate.
- [x] Created clean alternate worktree /home/openclaw/lodestar-builder-submit-slot-budget; left untouched after detecting retained work. No cleanup performed.
- [x] Design consult identified415fallback signal leak even with retries0; strict total cancellation needs#10526 fix or carefullyscoped alternative. Existingretainedpatch doesnot reject zero-budget beforefetch and usesAbortSignal.timeout which is asynchronous; inadequate as-is.
- [ ] Clarify hardinflightcutoff vs no-new-retries policy; preserve useful late responses. ScopequestiondraftpendingpeerQA.
- [ ] Implement complete scopedpolicy; fake-timer regression tests throughrealclient, bothsubmitversions, short/late slots,415fallback,cancellation,bodydeadline.
- [ ] Establish isolated dependency setup, lint/types/build and meaningfulnegativecontrols.
- [ ] Persona reviews, signedcommit, forkpush/PR and sourcecommentreply.

Speccompliance:N/A initially (internal requestpolicy, no state-transition implementation altered); builderAPI source references should be retained if protocol semantics change. No merge/deploy authorized.

Notes: maincheckout is unrelateda370658/fix/merge-incremental-attester-duties and hasnon-taskuntrackedfiles; notswitching ormutating it. Prior worktree node_modules borrowoldmain and standardsetup lacksnative; do notrunpnpm againstit. Exploratoryreads hadsomeabsentguessedpaths, correctedwithoutsourcechange.
