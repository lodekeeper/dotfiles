**feat2 vs beta — last 24h, top movers per domain (≥±10%)** _no `super` hoodi; b=beta f=feat2_
Full table (solo/semi/sas/mainnet-super): <https://gist.github.com/lodekeeper/a11e51b6e7b2cbc20e81d6a56d9d8e04>
Counter-suffix metrics use `increase(metric[24h])` so uptime-independent. Watch `_total` on size/queue *gauges* (`db_size_bytes_total` etc).

**BLS** (29):
• `sas` `bls_thread_pool_queue_length` **+1073%** b=0.0658 f=0.772
• `mainnet-super` `bls_thread_pool_workers_busy` **+804%** b=0.0075 f=0.0678
**Validator** (60):
• `sas` `oppool_aggregated_attestation_pool_packed_attestations_committee_count` **+117%** b=47 f=102
• `sas` `oppool_aggregated_attestation_pool_packed_attestations_scanned_slots_total` **+75.4%** b=65 f=114
**ForkChoice/Sync** (26):
• `sas` `fork_choice_compute_deltas_new_vote_validators_count` **+633%** b=9.22e+06 f=6.76e+07
• `sas` `sync_unknown_block_pending_blocks_size` **+277%** b=0.0892 f=0.336
**Gossip** (309):
• `solo` `gossipsub_peer_read_stream_err_count_total` **+3285%** b=157 f=5.32e+03
• `mainnet-super` `gossip_validation_queue_concurrency` **+2646%** b=0.00482 f=0.132
**BlockProc/State** (96):
• `mainnet-super` `execution_engine_http_client_active_requests` **+12600%** b=6.94e-05 f=0.00882
• `mainnet-super` `engine_http_processor_queue_concurrency_total` **+11000%** b=1 f=111
**libp2p/reqresp** (264):
• `solo` `libp2p_quic_inbound_connections_total` **+173340%** b=103 f=1.79e+05
• `solo` `attnets_service_committee_subscriptions_time_to_stable_mesh_seconds_sum` **+40986%** b=0.117 f=48.1
**CPU/Heap/GC** (51):
• `mainnet-super` `nodejs_active_requests_total` **+3450%** b=2 f=71
• `mainnet-super` `buffer_pool_hits_total` **+931%** b=13 f=134
**DB/REST/misc** (18):
• `sas` `scrape_duration_seconds` **+371%** b=0.262 f=1.23
• `solo` `prune_history_fetch_keys_time_seconds_sum` **+119%** b=23.9 f=52.3

