#!/usr/bin/env python3
"""Weekly mainnet orphan rate at epoch-boundary slots (slot%32==0) vs others, via Xatu fct_block.
Tests twoeths' hypothesis: LH enabling epoch-boundary proposer-boost-reorg (v8.2.0, Jun22) raised
boundary reorgs. Run: panda clickhouse clickhouse-refined "<SQL below>"."""
SQL = """
SELECT toStartOfWeek(slot_start_date_time) AS week,
  countIf(status='orphaned' AND slot%32=0) AS eb_orph, countIf(slot%32=0) AS eb_tot,
  round(countIf(status='orphaned' AND slot%32=0)*100.0/countIf(slot%32=0),3) AS eb_orphan_pct,
  round(countIf(status='orphaned' AND slot%32!=0)*100.0/countIf(slot%32!=0),4) AS other_orphan_pct
FROM mainnet.fct_block FINAL
WHERE slot_start_date_time >= '2026-05-25' AND slot_start_date_time < '2026-08-26'
GROUP BY week ORDER BY week
"""
print(SQL)
