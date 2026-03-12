# Retrieval Gap Report

- generated_at: 2026-03-12T15:04:47.429711+00:00
- sample_count: 12
- lexical_top3_hit_rate: 0.25
- vector_top3_hit_rate: 0.5
- hybrid_top3_hit_rate: 0.5
- hybrid_top3_lift_vs_lexical_pct: 100.0
- grounding_coverage: 1.0
- similar_cases_availability: 0.9167

## Stage Gate
- hybrid_lift_ge_15pct: True
- grounding_coverage_ge_95pct: True
- similar_cases_availability_ge_90pct: True

## Gaps
- rq-003: query=客户投诉升级要求马上人工接管 expected_doc_ids=['case-003'] expected_source_types=['history_case'] hybrid_top3=['case-033', 'case-073', 'case-053']
- rq-005: query=发票争议需要核对交易记录 expected_doc_ids=['case-005'] expected_source_types=['history_case'] hybrid_top3=['case-075', 'case-065', 'case-085']
- rq-006: query=账号锁定后怎么重置凭据 expected_doc_ids=['case-006'] expected_source_types=['history_case'] hybrid_top3=['case-066', 'case-036', 'case-086']
- rq-008: query=物流延迟投诉怎么触发补偿流程 expected_doc_ids=['case-008'] expected_source_types=['history_case'] hybrid_top3=['case-098', 'case-018', 'case-088']
- rq-009: query=消息丢失要重放并校验幂等键 expected_doc_ids=['case-009'] expected_source_types=['history_case'] hybrid_top3=['case-099', 'case-049', 'case-069']
- rq-012: query=用户要投诉处理并升级人工客服 expected_doc_ids=['sop-002'] expected_source_types=['sop', 'history_case'] hybrid_top3=['case-028', 'case-018', 'case-011']

## Suggestions
- Add new FAQ/SOP entries for repeated gap queries.
- Backfill historical cases with richer context snippets.
- Keep hybrid as default for grounded and similar-cases flows.
