# Kurtosis ethereum-package Config Reference

Full documentation: https://github.com/ethpandaops/ethereum-package

## Participant Fields

```yaml
participants:
  - el_type: reth|geth|nethermind|besu|erigon|ethereumjs|nimbus-eth1|ethrex
    el_image: <docker-image>            # omit for the package default; e.g., ghcr.io/paradigmxyz/reth:latest
    el_extra_params: []                  # extra CLI flags for EL
    cl_type: lodestar|lighthouse|prysm|teku|nimbus|grandine
    cl_image: <docker-image>            # omit for the package default; e.g., lodestar:custom
    cl_extra_params: []                  # extra CLI flags for CL beacon
    vc_type: <same-as-cl_type>          # defaults to cl_type
    vc_image: <docker-image>            # custom VC image (if different from CL)
    vc_extra_params: []                 # extra CLI flags for VC
    supernode: false                    # subscribe to all subnets / custody all columns (PeerDAS only)
    use_separate_vc: true               # false = beacon+VC in one process (default false for teku/nimbus)
    count: 1                            # number of instances with this config
    validator_count: 64                 # validators assigned to this participant
```

## Network Parameters

```yaml
network_params:
  # Fork epochs (0 = from genesis; unscheduled = 18446744073709551615)
  # altair..fulu default to 0; gloas/heze default to unscheduled
  gloas_fork_epoch: 1

  # Timing
  seconds_per_slot: 12          # default 12, use 6 for faster devnets
  preset: mainnet               # or minimal (8 slots/epoch; uses *_MINIMAL default images). No slots_per_epoch key

  # Network
  network_id: "3151908"
  deposit_contract_address: "0x..."

  # Validator
  num_validator_keys_per_node: 64
  preregistered_validator_keys_mnemonic: "..."
```

## Additional Services

```yaml
additional_services:
  - dora              # chain explorer UI
  - assertoor         # automated testing
  - prometheus        # metrics collection
  - grafana           # metrics dashboards
  - spamoor           # transaction spammer (use instead of the removed blob_spammer)
  - forkmon           # fork monitor
  - blockscout        # block explorer with contract verification
```

Unknown names stop the run (`Invalid additional_services`); the allowed list is `ADDITIONAL_SERVICES_PARAMS` in ethereum-package `src/package_io/sanity_check.star`.

## Assertoor Parameters

```yaml
assertoor_params:
  run_stability_check: true          # chain health, finality, reorgs
  run_block_proposal_check: true     # every client pair proposes a block
  run_transaction_test: false        # transaction lifecycle
  run_blob_transaction_test: false   # blob tx test
  run_opcodes_transaction_test: false
  tests: []                          # custom test configs
```

## Port Publisher

```yaml
port_publisher:
  el:
    enabled: true
    public_port_start: 32000    # EL HTTP/WS
  cl:
    enabled: true
    public_port_start: 33000    # CL beacon API
  vc:
    enabled: false
    public_port_start: 34000
```

Each CL/EL node gets a block of 7 ports, each VC 3 (cl-1 from 33000 with beacon API on 33001, cl-2 from 33007).

## Global Settings

```yaml
global_log_level: info|debug|warn|error    # default: info
```

## Example: Minimal 2-Node Devnet

```yaml
participants:
  - el_type: geth
    cl_type: lodestar
    count: 1
    validator_count: 128

  - el_type: reth
    cl_type: lighthouse
    count: 1
    validator_count: 128

network_params:
  seconds_per_slot: 6

additional_services:
  - dora
```

## Client Docker Images

### Defaults
Omit `el_image` / `cl_image` / `vc_image` to get the package defaults — `DEFAULT_EL_IMAGES`, `DEFAULT_CL_IMAGES`, `DEFAULT_VC_IMAGES` (and `*_MINIMAL` for `preset: minimal`) in ethereum-package `src/package_io/input_parser.star`. That file is the source of truth; the README's per-client list can lag it (e.g. Prysm defaults to `offchainlabs/prysm-beacon-chain:stable`).

### ethpandaops Feature Branches
ethpandaops publishes custom builds at: `ethpandaops/<client>:<branch-name>`
Check: https://github.com/orgs/ethpandaops/packages
