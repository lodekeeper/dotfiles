**feat2 vs unstable — last 24h, top movers per domain (>=±10%)**
Full table (every metric, all 5 host pairs): <https://gist.github.com/lodekeeper/5a125ed24d2c64c8e76bb89cf263f5c5>
Caveat: `_total` on size/queue gauges is gauge-not-counter (e.g. db_size_bytes_total). solo/semi base counters are tiny so % look huge.

**BLS** (74):
• `mainnet-super` `bls_thread_pool_workers_busy` **+608%** u=0.00945 f=0.0669
• `sas` `bls_thread_pool_queue_length` **+288%** u=0.183 f=0.708
**Validator** (225):
• `super` `vm_prev_epoch_on_chain_source_attester_miss_total` **+1205%** u=373 f=4.87e+03
• `super` `vm_prev_epoch_on_chain_target_attester_miss_total` **+1012%** u=441 f=4.91e+03
**ForkChoice/Sync** (96):
• `sas` `fork_choice_compute_deltas_new_vote_validators_count` **+651%** u=8.87e+06 f=6.66e+07
• `semi` `fork_choice_compute_deltas_new_vote_validators_count` **+620%** u=9.37e+06 f=6.75e+07
**Gossip** (613):
• `semi` `gossip_validation_queue_key_age_seconds_sum` **+39957%** u=2.2 f=881
• `mainnet-super` `seen_cache_attestation_data_slot_total` **+16200%** u=3 f=489
**BlockProc/State** (299):
• `super` `awaiting_block_gossip_messages_per_slot_total` **+294388%** u=11 f=3.24e+04
• `super` `block_processor_queue_job_wait_time_seconds_sum` **+6828%** u=2.12 f=147
**libp2p/reqresp** (485):
• `solo` `discovery_peers_to_connect` **+193159250%** u=0.00222 f=4.29e+03
• `mainnet-super` `discovery_peers_to_connect` **+67599%** u=0.368 f=249
**CPU/Heap/GC** (99):
• `sas` `buffer_pool_hits_total` **+5400%** u=4 f=220
• `mainnet-super` `nodejs_active_requests_total` **+3250%** u=2 f=67
**DB/REST/misc** (51):
• `sas` `db_size_bytes_total` **+5905%** u=2.19e+11 f=1.32e+13
• `super` `scrape_duration_seconds` **+1166%** u=0.166 f=2.1

