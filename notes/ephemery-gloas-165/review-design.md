# Devil's Advocate Review

Base: `9cb14e3381b08b7eb399b37c9b9e48e66eb2c791`

Reviewed diff SHA-256: `e9afb1427ad8b7335bf86043f0b07d127a99043496b31369f3811f41b8ae191b`

Files reviewed: `packages/config/src/chainConfig/networks/ephemery.ts` and `packages/config/test/unit/networks.test.ts`.

## Overall Assessment

The minimal preset update is sound for an explicitly reset-timed draft, with no merge before upstream PR 75 is finalized and iteration 165 resets.

## Objections

No actionable objections within the agreed scope.

- Activation is necessary: retaining the current preset leaves Gloas disabled indefinitely because iteration rollover changes identity, not fork epochs.
- Normalizing both genesis BPO changes to one effective 15-blob entry is correct. Retaining two entries at epoch zero would resolve the first entry, 12, in Lodestar's current stable-sort lookup.
- The two additional Ephemery overrides and disabled Heze version align supported config fields with upstream without adding machinery.
- Inherited Gloas timing and churn values match generator v6.2.1 defaults; redundant overrides are unnecessary.
- Existing historical identity tests remain useful, and new cases cover Gloas/version/blob behavior at the new base and later iterations.
- Iteration-aware fork schedules would permit deployment before reset, but are unnecessary for the explicitly timed draft. The static preset must not be merged or advertised as safe for iteration 164: its identity can roll backward while its Gloas and BPO schedule cannot.

## Verdict

SOUND: no fundamental issues for the stated reset-timed draft. Approval does not remove the upstream-finalization and reset merge gates, nor claim live-network validation.
