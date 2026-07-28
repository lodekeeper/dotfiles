Upstream tracking/fix is now filed:

- sigstore/sigstore-js issue: https://github.com/sigstore/sigstore-js/issues/1708
- sigstore/sigstore-js PR: https://github.com/sigstore/sigstore-js/pull/1709

The upstream PR changes `@sigstore/sign`'s Rekor conflict behavior so create-entry `409` conflicts fetch the existing Rekor entry by default. It preserves explicit `fetchOnConflict: false`, adds a regression test, and includes a changeset.

I also updated this PR body to reference the upstream issue/PR and the similar downstream SocialGouv/code-du-travail-numerique#7419 + apify/apify-shared-js#649 reports.

🤖 Generated with AI assistance
