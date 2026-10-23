Not the default. `check-latest` defaults to `false` in both setup-node versions we pin (v6.3.0 and v7.1.0). With `false`, `node-version: 24` uses whatever 24.x is already in the runner toolcache.

Releases still got new Node versions because none of the release paths go through these five workflows:
- Docker images are built `FROM node:24-slim` on fresh builders, so each release gets the current tag. v1.48.0 to v1.50.0 shipped 24.21.0, and v1.50.1 shipped 24.22.1
- publish-stable, publish-rc, binaries and the test workflows use `.github/actions/setup-and-build`, which has set `check-latest: true` since it was added in [#6437](https://github.com/ChainSafe/lodestar/pull/6437)

The five workflows changed here did lag. On 10-22 nightly-builder-smoke used the cached 24.21.0 ([log](https://github.com/ChainSafe/lodestar/actions/runs/39710662218/job/119600958798)), although the 24.22.1 security release had been out since 10-20. On 10-23 it downloaded 24.22.1 ([log](https://github.com/ChainSafe/lodestar/actions/runs/39888864739/job/120203494095)).

None of the five ship anything, so you're right that it doesn't matter for what users run. It only keeps CI on the same Node as the release builds, at the cost of one tarball download per run. I can open a PR to drop it if you'd rather keep them on the toolcache.
