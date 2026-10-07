Removed all three casts. The mocks were rebuilding a signed envelope around an all-forks block union; Heze's removal of `eth1Data`/`deposits` exposed the lost union correlation.

They now return concrete signed fixtures and assert that `signBlock` receives the exact produced message, preserving input and publishing coverage. Shared per-fork SSZ types and production signing are unchanged.

Full build, type-check and lint pass, plus 14 focused block-service, signing and Heze SSZ tests.
