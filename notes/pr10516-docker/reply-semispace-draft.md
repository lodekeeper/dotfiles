Thanks, confirmed `--max-semi-space-size=64` is wired into both Docker images, `./lodestar`, docker-compose and the standalone-binary command. The production image exposes it in `NODE_OPTIONS` and the `--version` check succeeds on Node 26.13.0.

A local check with 8 GiB old space shows Node 26's V8 heap limit increasing from 8,288 to 8,384 MiB with the flag, matching Node 24.22.2 (8,384 MiB with or without it). That confirms the configured limit; my short allocation probe did not grow new space to its cap, so it does not independently reproduce the peak-size table.

I have not redeployed feat2 or rerun `processEffectiveBalanceUpdates`. The current-head [Benchmark run](https://github.com/ChainSafe/lodestar/actions/runs/42027589761) still fails, so the GC comparison and benchmark explanation remain unverified.
