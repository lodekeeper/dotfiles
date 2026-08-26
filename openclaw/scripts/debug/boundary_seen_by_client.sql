-- Lodestar vs peers, epoch-boundary block-seen p90 (Xatu). CL client = meta_consensus_implementation
-- (NOT meta_client_implementation = sentry sw). force_primary_key: bound BOTH slot(int) AND slot_start_date_time.
SELECT toStartOfWeek(slot_start_date_time) AS week, meta_consensus_implementation AS cl,
  round(quantileIf(0.9)(seen_slot_start_diff, slot%32=0))  AS eb_p90,
  round(quantileIf(0.9)(seen_slot_start_diff, slot%32!=0)) AS oth_p90,
  round(quantileIf(0.5)(seen_slot_start_diff, slot%32=0))  AS eb_p50
FROM mainnet.fct_block_first_seen_by_node
WHERE slot BETWEEN 14453998 AND 15073198
  AND slot_start_date_time >= '2026-06-01' AND slot_start_date_time < '2026-08-26'
  AND meta_consensus_implementation IN ('lodestar','prysm','teku')
GROUP BY week, cl ORDER BY cl, week;
