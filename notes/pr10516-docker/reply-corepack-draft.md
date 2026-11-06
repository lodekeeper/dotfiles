Verified at `86ec5cb64a`: the production image builds successfully and `--version` reports the correct commit on Node 26.13.0. Both Dockerfiles now install Corepack before using it.

`Dockerfile.dev` also builds, and `--version` reports the same commit. Its first build hit `NameServerFailure` fetching a Zig dependency; retrying with `--network=host` succeeded. Both resulting images load the native addon and expose `--max-old-space-size=8192 --max-semi-space-size=64`.

This addresses the missing-Corepack P1. These checks are linux/amd64 only.
