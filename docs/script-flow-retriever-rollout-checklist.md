# Script Flow Retriever Rollout Checklist

This runbook helps operate `search_script_flows` on pgvector-based retriever safely.

## 1) Apply DB migrations

Run backend migrations and verify that revision `0086` is applied.

- Required tables:
  - `script_flow_node_indexes`
  - `script_flow_edge_indexes`

## 2) Queue backfill reindex for published flows

Use the new API endpoint per agent:

- `POST /api/v1/agents/{agent_id}/script-flows/reindex-published`

Example body:

```json
{
  "limit": 500,
  "force_all_published": true
}
```

Notes:

- `force_all_published=true` is recommended for the first migration run.
- Repeat until all target agents are queued.

## 3) Ensure index worker is running

The worker `backend/app/workers/script_flow_index.py` processes pending queue
for script flow index rebuilds.

Watch logs for:

- `script_flow_index_worker_batch`
- `script_flow_indexed`
- `script_flow_index_failed`

## 4) Verify index readiness

For each target agent, confirm:

- no long-lived `index_status='pending'` for published flows,
- `index_status='indexed'` reaches current `published_version`.

Also verify node embeddings are populated (`embedding IS NOT NULL`) for
searchable nodes.

## 5) Configure retrieval engine on staging

Set environment:

- `RUNTIME_SCRIPT_FLOW_RETRIEVAL_ENGINE=retriever`

Current recommended mode is retriever-only.

## 6) Smoke test scenarios

Check at least:

- objection handling with expected tactic output,
- required follow-up question behavior,
- communication style / phrase constraints,
- no-match behavior (graceful fallback answer).

Use API sandbox endpoint:

- `POST /api/v1/agents/{agent_id}/script-flows/test-search`

Inspect response fields:

- `retrieval_engine`
- `matches`
- `debug`

## 7) Observe for regressions

Track logs/metrics for 24-48h on staging:

- match rate (`search_script_flows_match` vs `search_script_flows_no_matches`),
- latency of `search_script_flows`,
- error rate (`search_script_flows_failed`).

If stable, repeat on production with gradual rollout.

## 8) Production rollout

Recommended order:

1. Enable retriever for a subset of agents/tenants.
2. Monitor logs and quality.
3. Expand to full rollout.

After stable window, keep runtime on retriever and remove any leftover legacy docs/config mentions.
