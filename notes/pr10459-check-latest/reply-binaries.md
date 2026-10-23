The binaries bundle the same Node that builds them. publish-stable and publish-rc call `binaries.yml`, and that uses the `setup-and-build` composite with `check-latest: true`. caxa then copies `process.execPath` into the bundle as `node_modules/.bin/node` (`includeNode` defaults to true), so each binary ships the newest 24.x available at release time.

v1.50.1 shows this. Both binaries jobs resolved 24.22.1 ([amd64](https://github.com/ChainSafe/lodestar/actions/runs/39817322856/job/119963229910), [arm64](https://github.com/ChainSafe/lodestar/actions/runs/39817322856/job/119963229937)). On ubuntu-latest, 24.22.1 was already in the toolcache. The Warp arm64 runner didn't have it cached, so the job downloaded it. Without `check-latest`, that job would have used an older 24.x from the cache if it had one, the way the Warp x64 nightly smoke run used 24.21.0.

So for the binaries `check-latest` does matter, and the composite already sets it. #10459 didn't touch that path.
