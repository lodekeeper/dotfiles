# Validator block signing type design

Reviewed PR #10293 base: 95577761f36. Read-only investigation; no source changes or compiler verification performed.

## Root cause

ValidatorStore.signBlock accepts BeaconBlock | BlindedBeaconBlock but promises SignedBeaconBlock | SignedBlindedBeaconBlock. Its implementation already asserts that return type. The mock simply performs the same valid envelope operation, returning {message: block, signature}.

The all-forks aliases in packages/types/src/types.ts index TypesByFork for the complete signed container. Consequently they represent a union of signed envelopes, whereas the implementation produces one envelope containing a union-valued message. TypeScript does not generally distribute the latter into the former. Before Heze, older block shapes were structural subsets of newer shapes, allowing the broad envelope to fit an older branch. Heze removes eth1Data/deposits and also changes the execution payload bid shape, breaking that accidental structural coverage. The per-fork SSZ definitions are correct and must not be weakened.

Vitest NormalizedProcedure explicitly uses Parameters<T> and ReturnType<T>. The block mock parameter is therefore the broad method input, not the particular fork supplied later by the test. A fork-generic method alone does not restore correlation in this normalized mock type; retaining a union-of-envelopes return leaves the original issue.

Signing interfaces are otherwise consistent: SignableMessage BLOCK_V2 accepts the same unsigned full/blinded union, and the signature is the same BLSSignature across forks. API publishing uses the signed aliases, so a local broad return type would merely move the incompatibility into publishing code.

## Smallest coherent broader proposal

Represent the existing public signed block aliases as their common envelope around their existing fork-dependent message alias:

    export type SignedBeaconBlock<F extends ForkAll = ForkAll> = {
      message: BeaconBlock<F>;
      signature: phase0.SignedBeaconBlock["signature"];
    };
    export type SignedBlindedBeaconBlock<F extends ForkPostBellatrix = ForkPostBellatrix> = {
      message: BlindedBeaconBlock<F>;
      signature: bellatrix.SignedBlindedBeaconBlock["signature"];
    };

This changes only aggregate TypeScript envelope representation. For each concrete F the result is structurally identical to that fork's current signed SSZ value type. TypesByFork, actual SSZ containers, Heze's removed fields, and fork-specific unsigned message types remain untouched. No optionalizing removed fields, casts in tests, or new parallel alias needed. Remove the three test casts and, if compilation confirms it, the existing signBlock return assertion too.

The proposal requires compiler validation, especially the mixed full/blinded union assignability and API publishing/typeguards, before approval of implementation. If mixed envelope construction still fails, do not add another assertion: inspect whether the aggregate aliases need a shared envelope for the mixed signing return, with corresponding API acceptance, before choosing broader scope.

## Verification scope

Run workspace type checks since these exported aliases reach API, beacon-node, and validator consumers. Run lint and the focused validator services/block.test.ts tests plus existing signBlock tests. Validate both concrete Heze/full and Bellatrix/blinded values remain assignable to their exact fork-specialized signed aliases, and that Heze's removed fields are not reintroduced. No SSZ runtime change or new broad spec-vector run is required for an envelope-only type fix.
