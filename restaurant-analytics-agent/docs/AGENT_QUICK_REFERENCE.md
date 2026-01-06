# Agent Implementation Quick Reference

## Agent Pipeline Overview

```
User Query
    ↓
[Intent Classifier] → Intent, Entities, Time Range
    ↓
[Schema Analyzer] → Tables, Columns, Joins
    ↓
[SQL Generator] → PostgreSQL Query
    ↓
[SQL Validator] → Validation (Rules-based)
    ↓
[Result Validator] → Pass-through
    ↓
[Visualization Planner] → Chart Type & Config
    ↓
SQL Execution (in main.py)
    ↓
[Answer Generator] → Natural Language Answer
    ↓
Response
```

## LLM Calls Summary

| Agent | LLM Model | Temperature | Max Tokens | Reasoning | Avg Latency |
|-------|-----------|-------------|------------|-----------|-------------|
| Intent Classifier | nemotron-3-nano-30b | 0.1 | 1024 | 1024 | 5s |
| Schema Analyzer | nemotron-3-nano-30b | 0.1 | 512 | - | 5s |
| SQL Generator | nemotron-3-nano-30b | 0.2 | 1024 | 1024 | 4.5s |
| SQL Validator | **None** (Rules) | - | - | - | 80ms |
| Result Validator | **None** (Pass-through) | - | - | - | 8ms |
| Visualization Planner | nemotron-3-nano-30b | 0.1 | 512 | - | 3s |
| Answer Generator | nemotron-3-nano-30b | 0.3 | 1024 | 1024 | 3.5s |

**Total LLM Calls**: 5-6 per query (depending on retries)

## Latency Summary

| Scenario | Typical Latency | Notes |
|----------|----------------|-------|
| **Successful Query** | 18-22s | No retries |
| **With SQL Gen Retry** | 23-28s | +1 retry |
| **With SQL Exec Retry** | 40-50s | Full workflow restart |
| **Multiple Retries** | 60+ seconds | Worst case |

**Breakdown**:
- LLM Calls: ~21s (75%)
- Database: ~200ms (1%)
- Other: ~1s (4%)

## Retry Logic

### SQL Generation Retries
- **Trigger**: SQL validation fails
- **Max Retries**: 2
- **Overhead**: +4.5s per retry
- **Mechanism**: Loop back to SQL Generator with error context

### SQL Execution Retries
- **Trigger**: PostgreSQL error
- **Max Retries**: 2
- **Overhead**: +20s per retry (full workflow restart)
- **Mechanism**: Restart entire workflow with error context

## Key Files

| File | Purpose |
|------|---------|
| `agent_framework.py` | LangGraph workflow definition |
| `agents/intent_classifier.py` | Intent & entity extraction |
| `agents/schema_analyzer.py` | Table/column selection |
| `agents/sql_generator.py` | SQL query generation |
| `agents/sql_validator.py` | SQL validation (rules) |
| `agents/viz_planner.py` | Chart type selection |
| `agents/answer_generator.py` | Natural language answer |
| `models/state.py` | AgentState definition |
| `main.py` | API endpoint & SQL execution |

## State Flow

```
AgentState (TypedDict)
    ↓
Intent Classifier → Updates: intent, entities, time_range
    ↓
Schema Analyzer → Updates: tables, columns, joins
    ↓
SQL Generator → Updates: generated_sql, explanation
    ↓
SQL Validator → Updates: validation_passed, errors
    ↓
Result Validator → Updates: results_valid
    ↓
Visualization Planner → Updates: visualization_type, config
    ↓
Answer Generator → Updates: generated_answer, insights
```

## Error Handling

| Agent | Fallback Strategy |
|-------|-------------------|
| Intent Classifier | Set intent to UNKNOWN, request clarification |
| Schema Analyzer | Heuristic-based table selection |
| SQL Generator | Return empty SQL, trigger validation error |
| SQL Validator | Mark as failed, trigger retry |
| Visualization Planner | Intent-based heuristic selection |
| Answer Generator | Template-based answer |

## Performance Optimization Priorities

### High Impact (Quick Wins)
1. ✅ **Caching** - 50-80% reduction for cached queries
2. ✅ **Retry Logic** - 50-70% reduction in retry overhead
3. ✅ **Faster Models** - 20-30% reduction for simple tasks

### Medium Impact (Medium Effort)
4. ✅ **Parallelization** - 30-40% reduction overall
5. ✅ **Reduce Reasoning** - 10-15% reduction
6. ✅ **Early Exit** - 5-10% reduction

### Low Impact (Long-term)
7. ✅ **Prompt Optimization** - 5-10% reduction
8. ✅ **Batch Processing** - 20-30% throughput improvement

## Configuration

### Environment Variables
```bash
# LLM Configuration
NVIDIA_API_KEY=your_key
NVIDIA_MODEL=ai-nemotron-3-nano-30b-a3b
NVIDIA_MODEL_FAST=ai-nemotron-3-nano-30b-a3b

# Database
SUPABASE_DB_URL=postgresql://...

# Retry Settings
MAX_RETRIES=2
MAX_QUERY_TIMEOUT=30
```

### Settings (config/settings.py)
- `max_retries`: 2
- `max_query_timeout`: 30 seconds
- `db_pool_min_size`: 5
- `db_pool_max_size`: 20

## Monitoring

### Key Metrics
- **Latency**: P50, P75, P90, P95, P99
- **Retry Rate**: By agent type
- **Error Rate**: By error type
- **Throughput**: Queries per minute

### Log Patterns
```
[query_id] Processing query: ...
Intent classifier processing: ...
Intent classified: {intent} (confidence: {conf})
Schema analysis complete: {tables} tables, {joins} joins
SQL generated: {length} chars
Validation passed with {warnings} warnings
Query processed in {time}ms. Agents: [...]
```

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| High latency | Sequential LLM calls | Parallelize agents |
| Frequent retries | SQL generation errors | Improve prompts, add examples |
| SQL execution errors | Wrong column names | Better schema knowledge |
| Empty results | Date range issues | Improve time mapping |
| Slow responses | LLM API latency | Use faster models, cache |

## Documentation Files

- `AGENT_IMPLEMENTATION.md` - Full implementation details
- `LATENCY_ANALYSIS.md` - Detailed performance analysis
- `ARCHITECTURE.md` - System architecture
- `AGENT_QUICK_REFERENCE.md` - This file


