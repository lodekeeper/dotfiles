# SSZ #556 terminal-offset design consultation

## Verdict
Approve conditional `Uint32Array | Float64Array` backing storage, chosen by relative `size >= 2 ** 32`, in BOTH fixed and variable offset readers. Keep trailing sentinel and branchless consumers unchanged. This preserves existing library behavior without imposing 8-byte slots on normal inputs. No public signature changes: both readers are private.

## Source evidence and specification nuance
- Inspected exact PR head 8ac6df088d3b6964af0ce4f659838443caa865ba, `packages/ssz/src/type/arrayComposite.ts`. Both readers currently truncate their appended terminal boundary to uint32. Fixed reader also truncates any interior synthesized boundary above uint32.
- `ByteVectorType` constructor has no 32-bit cap; lengthBytes is assigned directly to fixedSize, and construction does not allocate the payload. A one-element vector of ByteVectorType(2**32) reaches the faulty sentinel with two slots only. Existing ordinary-number terminal handling could preserve this numeric bound.
- IMPORTANT: local `/home/openclaw/ethereum-repos/consensus-specs/ssz/simple-serialize.md:231` serialization algorithm for vectors, containers, lists, progressive variants has an UNCONDITIONAL `assert sum(fixed_lengths + variable_lengths) < 2 ** (BYTES_PER_LENGTH_OFFSET * BITS_PER_BYTE)`. This includes fixed-size arrays. Therefore distinguish a supported library input / compatibility concern from a spec-valid outer SSZ array. Do not claim that fixed-size SSZ array serialization >=2**32 is allowed by this specification. The original broad PR claim may be spec-correct but does not establish that the implementation can silently truncate previously accepted bounds.
- Online source retrieval was attempted; raw master/dev URLs returned 404. Spec observation above is explicitly from the available local checkout.

## Minimal implementation
Return and local offset variable types become the union. At each allocation use `size >= 2 ** 32 ? new Float64Array(count + 1) : new Uint32Array(count + 1)`. Fixed and variable readers need independent dispatch because variable reader allocates its own storage. Empty variable input remains `new Uint32Array(1)` (one zero sentinel, NOT zero-length array). Avoid extra allocation helper unless style warrants it. Comments should explain preservation of existing numeric input ranges, not wire offsets becoming 64-bit.

## Regression coverage
Use real ByteVectorType instances for fixed-size metadata; spy only element deserializers to capture start/end and return tiny Uint8Array / LeafNode. Tiny ByteViews and synthetic large end intentionally exercise boundary routing, not actual GiB payload deserialization. Cover both exported value/tree helpers, fixed and variable layouts:
- size = 2**32 - 1: maximal Uint32 terminal still preserved;
- size = 2**32: regression boundary;
- size = 2**32 + small delta: general wide numeric endpoint;
- nonzero start: choose storage by end-start, preserve absolute child ranges;
- two fixed elements: verify interior offsets >=2**32 also survive (e.g. fixedSize=2**32, length=2).
Variable test needs a real 4-byte header with firstOffset=4 and wide synthetic size; a ByteListType or analogous actual variable element suffices. Do not imply this synthetic fixture validates an actual giant buffer or SSZ spec validity.
Retain existing empty-array and malformed-offset tests. No need to export internals solely to inspect constructor choice.

## Performance
Normal allocation width/length stays unchanged; added allocation-time comparison is O(1). Union typed-array accesses can affect JIT specialization even when wide arrays are rare; measure existing focused small/large composite benchmarks on normal fixtures before claiming no regression. Wide path necessarily doubles offset storage versus Uint32 but applies only to previously mishandled huge ranges. Avoid broad microbenchmark assertions or introducing last-element branches.
