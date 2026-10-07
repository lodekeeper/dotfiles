# Nethermind SSZ Engine release exposure — 2026-10-07

Requested by Nico in Discord thread 1553610308503736350, message1557330166898888818. Read-only GitHub API verification; no live runtime testing.

## Verified evidence

- Latest stable release2.1.0 published2026-10-01T22:43:39Z. Latest release API and recent release list agree; no newer client release. https://github.com/NethermindEth/nethermind/releases/tag/2.1.0
- Tag2.1.0 SszRestPaths.cs lines176–184 still implements GetEngineApiForkName through a NamedReleaseSpec cast and returns null for plain ReleaseSpec. File objecta9cbff976f962fc2a07faca0cc03e9bebb162ab5. https://github.com/NethermindEth/nethermind/blob/2.1.0/src/Nethermind/Nethermind.Merge.Plugin/SszRest/Handlers/SszRestPaths.cs#L176-L184
- Tag2.1.0 ForkchoiceUpdatedSszHandler.cs lines48–57 uses that result for fork-header matching; mismatch becomes400 unsupported-fork. Issue14006 describes the chainspec fork resolution failure and body availability false negatives. https://github.com/NethermindEth/nethermind/issues/14006
- Tag2.1.0 exposes /engine/v1/ (SszRestPaths.cs line58), so current-spec negotiation can reach the faulty handler.
- Tag2.0.0 also contains the defective helper (lines174–182), but exposes old /engine/v2/ routes. Do not conflate code presence with current-spec auto-negotiation exposure.
- Tags1.39.0/1.39.3 have older SSZ REST code but not that GetEngineApiForkName helper in this file.1.38.0 has no file at this path.
- FixPR14302 merged into master2026-10-06T14:19:11Z atf4605b584504da6f39309de073833ecde38e0323. It replaces the identity-based resolver with release EIP markers and fixes capabilities advertisement. It is not present in2.1.0; direct tagged-source inspection proves the bug remains even though release/master ancestry is diverged. https://github.com/NethermindEth/nethermind/pull/14302
- Nazar reports fixed master2.2.0-preview+0c56218d works with LodestarPR10204, and the earlier defective master triggered auto JSON-RPC fallback. This is reported testing, not our runtime verification of released2.1.0. https://github.com/ChainSafe/lodestar/pull/10204#issuecomment-6035378195

Conclusion: broken code has shipped; only the fix is currently master-only. Independent response review approved; reviewer separately verified latest stable, tagged resolver, FCU validation, and release routing. Do not imply all SSZ methods fail or that Lodestar auto cannot fall back to JSON-RPC.
