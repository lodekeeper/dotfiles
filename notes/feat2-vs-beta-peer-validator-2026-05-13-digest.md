**Peer churn — feat2 vs beta 24h** <https://gist.github.com/lodekeeper/fbc6652bf8d6d86d538ca05ac800c772>
• `mainnet-super` `discovery_peers_to_connect` **+inf** b=0 f=243
• `solo` `libp2p_quic_inbound_connections_total` **+173340%** b=103 f=1.79e+05
• `solo` `libp2p_tcp_inbound_connections_total` **-88.0%** b=2.82e+05 f=3.38e+04
• `solo` `sync_head_peers_count` **-95.0%** b=3.52e+03 f=176
• `solo` `gossipsub_peer_read_err_count` **+3285%** b=157 f=5.32e+03
• `mainnet-super` `gossipsub_msg_publish_peers` **+182.5%** b=3.98e+05 f=1.13e+06
• `mainnet-super` `app_peer_score_sum` **-125.5%** b=-1.03e+03 f=-2.32e+03

**Validator perf — feat2 vs beta 24h** <https://gist.github.com/lodekeeper/7995992dd0456e50391978982baeba60>
• `sas` `vm_prev_attester_miss` **-31.2%** b=467 f=321
• `sas` `vm_prev_target_miss` **-30.3%** b=501 f=349
• `sas` `vm_prev_source_miss` **-28.5%** b=558 f=399
• `sas` `vm_blk_delay_sum` **+15.9%** b=8.09 f=9.37
• `semi` `vm_attn_in_blk_delay_slots` **+41.4%** b=517 f=731
• `sas` `vm_in_sync_committee` **-100.0%** b=0.0617 f=0
• `sas` `vm_prev_sync_hits` **-100.0%** b=1.02 f=0
• `sas` `produced_sync_contrib_parts_sum` **-100.0%** b=4.92e+03 f=0
• `sas` `oppool_pkd_atts_committee_count` **+117.0%** b=47 f=102
• `sas` `vm_proposer_bal_delta_gwei` **+16.9%** b=2.39e+08 f=2.79e+08
• `sas` `block_production_seconds_sum` **+28.4%** b=9.47 f=12.2

**Net read:** feat2-sas attester/target/source misses ↓~30% vs beta — the positive Cayman was after. But feat2-sas sync-committee duties dropped to zero (`vm_in_sync_committee` + `vm_prev_sync_hits` + `produced_sync_contrib_parts` all 0; nonzero on beta-sas) — part of the gain is just fewer duties; worth confirming sync-committee signing path isn't broken. Peer side: feat2-solo flipped transports (TCP↓88% / QUIC↑173k×) and lost 95% of sync-head peers; mainnet-super `app_peer_score_sum` doubled negative.
