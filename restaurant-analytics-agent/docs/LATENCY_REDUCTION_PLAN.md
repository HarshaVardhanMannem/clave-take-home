# Latency Reduction Plan
## Comprehensive Analysis & Optimization Strategy

**Document Version**: 1.0  
**Date**: 2026-01-05  
**Status**: Implementation Ready

---

## Executive Summary

This document provides a comprehensive analysis of latency bottlenecks in the Restaurant Analytics Agent system and proposes actionable optimizations to reduce query processing time from **18-25 seconds** to **8-12 seconds** (50-60% improvement).

### Current Performance Baseline

| Metric | Current | Target | Improvement |
|--------|---------|-------|-------------|
| **P50 Latency** | 18-20s | 8-10s | 50% |
| **P95 Latency** | 35-45s | 15-20s | 55% |
| **P99 Latency** | 60+s | 25-30s | 50% |
| **Throughput** | 3-4 qpm | 8-10 qpm | 2.5x |

---

## 1. Current Architecture Analysis

### 1.1 Agent Workflow

```
User Query
    ↓
[Parallel] Intent Classifier (5s) + Schema Analyzer (5s) → 5s total
    ↓
SQL Generator (4.5s)
    ↓
SQL Validator (80ms)
    ↓
SQL Execution (200ms)
    ↓
[Parallel] Answer Generator (3.5s) + Viz Planner (3s) → 3.5s total
    ↓
Response Building (30ms)
─────────────────────────────────────────────────────────
Total: ~13.3s (theoretical) | ~18-20s (actual with overhead)
```

### 1.2 Latency Breakdown

| Component | Time | % of Total | Type |
|-----------|------|------------|------|
| Intent Classifier | 5s | 25% | LLM |
| Schema Analyzer | 5s | 25% | LLM |
| SQL Generator | 4.5s | 22.5% | LLM |
| SQL Validator | 80ms | 0.4% | Rules |
| SQL Execution | 200ms | 1% | Database |
| Answer Generator | 3.5s | 17.5% | LLM |
| Visualization Planner | 3s | 15% | LLM |
| State Management | 50ms | 0.25% | Code |
| Response Building | 30ms | 0.15% | Code |
| **Overhead/Retries** | **2-5s** | **10-25%** | **Various** |

### 1.3 Database Schema Analysis

**Strengths:**
- ✅ Pre-aggregated views available (`v_daily_sales_summary`, `v_payment_methods_by_source`, etc.)
- ✅ Proper indexing on foreign keys and date columns
- ✅ Normalized structure reduces data duplication

**Opportunities:**
- ⚠️ Views are not materialized (recomputed on each query)
- ⚠️ No query result caching
- ⚠️ Large schema knowledge base loaded for every query
- ⚠️ No prepared statement caching

---

## 2. Optimization Strategies

### 2.1 High-Impact Optimizations (Phase 1)

#### 2.1.1 Implement Multi-Level Caching

**Impact**: 50-80% reduction for cached queries (2-5 seconds saved)

**Implementation:**

1. **Query Result Cache** (Redis/Memory)
   ```python
   # Cache key: hash(query + intent + entities)
   # TTL: 1 hour for common queries, 24 hours for historical data
   # Invalidate: On data ingestion
   ```

2. **Intent Classification Cache**
   ```python
   # Cache common query patterns → intent mappings
   # Examples: "top products" → product_analysis
   # Cache hit rate: ~40-50% for common queries
   ```

3. **Schema Analysis Cache**
   ```python
   # Cache: query_pattern → {tables, columns, joins}
   # Pattern matching: "revenue by location" → cached schema
   # Cache hit rate: ~30-40%
   ```

4. **SQL Generation Cache**
   ```python
   # Cache: normalized_query → generated_sql
   # Normalize: lowercase, remove extra spaces, standardize entities
   # Cache hit rate: ~20-30% for repeated queries
   ```

**Expected Savings:**
- Cache hit: 2-5 seconds (skip LLM calls)
- Cache miss: 0ms overhead (cache check is fast)

**Code Changes:**
```python
# backend/utils/cache.py
from functools import lru_cache
import hashlib
import json

class QueryCache:
    def __init__(self, ttl=3600):
        self.cache = {}
        self.ttl = ttl
    
    def get_cache_key(self, query: str, context: dict) -> str:
        normalized = query.lower().strip()
        context_str = json.dumps(context, sort_keys=True)
        return hashlib.md5(f"{normalized}:{context_str}".encode()).hexdigest()
    
    def get(self, key: str):
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['timestamp'] < self.ttl:
                return entry['value']
            del self.cache[key]
        return None
    
    def set(self, key: str, value: any):
        self.cache[key] = {
            'value': value,
            'timestamp': time.time()
        }
```

#### 2.1.2 Materialize Analytics Views

**Impact**: 30-50% reduction in SQL execution time (60-100ms saved)

**Current Issue:**
Views like `v_daily_sales_summary` are computed on-the-fly, which can be slow for large datasets.

**Solution:**
Convert frequently-used views to materialized views with refresh strategy.

```sql
-- Convert views to materialized views
CREATE MATERIALIZED VIEW mv_daily_sales_summary AS
SELECT 
    order_date,
    unified_location_id,
    source_system,
    order_type,
    COUNT(DISTINCT order_id) as order_count,
    SUM(total_cents) / 100.0 as total_revenue,
    -- ... rest of view definition
FROM unified_orders
WHERE voided = FALSE
GROUP BY order_date, unified_location_id, source_system, order_type;

-- Create indexes on materialized view
CREATE INDEX idx_mv_daily_date ON mv_daily_sales_summary(order_date);
CREATE INDEX idx_mv_daily_location ON mv_daily_sales_summary(unified_location_id);
CREATE INDEX idx_mv_daily_source ON mv_daily_sales_summary(source_system);

-- Refresh strategy (run via cron or trigger)
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_sales_summary;
```

**Refresh Strategy:**
- **Incremental Refresh**: Only refresh new data (last 24 hours)
- **Scheduled Refresh**: Every 15 minutes during business hours
- **Event-Driven**: Refresh on data ingestion completion

**Expected Savings:**
- View computation: 50-200ms → 5-10ms (10-20x faster)
- Total query time: 200ms → 50-100ms

#### 2.1.3 Optimize Schema Knowledge Loading

**Impact**: 100-200ms saved per query

**Current Issue:**
Large `SCHEMA_KNOWLEDGE` dictionary is loaded and serialized for every query.

**Solution:**
1. Pre-serialize schema knowledge to JSON string
2. Cache the serialized version
3. Use smaller, focused schema summaries per agent

```python
# backend/config/schema_knowledge.py

# Pre-serialize at module load
_SCHEMA_SUMMARY_CACHE = None

def get_schema_summary() -> str:
    """Get cached schema summary string"""
    global _SCHEMA_SUMMARY_CACHE
    if _SCHEMA_SUMMARY_CACHE is None:
        # Create focused summary (not full knowledge base)
        summary = {
            "tables": {k: {
                "description": v["description"],
                "key_columns": list(v["key_columns"].keys())[:10],  # Top 10 columns
                "use_for": v["use_for"][:5]  # Top 5 use cases
            } for k, v in SCHEMA_KNOWLEDGE["tables"].items()},
            "views": SCHEMA_KNOWLEDGE.get("views", {}),
        }
        _SCHEMA_SUMMARY_CACHE = json.dumps(summary, indent=2)
    return _SCHEMA_SUMMARY_CACHE
```

**Expected Savings:**
- Schema serialization: 50-100ms → 1-2ms (50x faster)

#### 2.1.4 Use Faster Models for Simple Tasks

**Impact**: 20-30% reduction in LLM latency (4-6 seconds saved)

**Current**: All agents use the same 30B parameter model

**Optimization:**
```python
# Use fast model for simpler tasks
INTENT_CLASSIFIER_MODEL = "fast"  # Smaller, faster model
SCHEMA_ANALYZER_MODEL = "fast"    # Smaller, faster model
SQL_GENERATOR_MODEL = "default"   # Keep large model (complex task)
VIZ_PLANNER_MODEL = "fast"        # Smaller, faster model
ANSWER_GENERATOR_MODEL = "fast"   # Smaller, faster model
```

**Model Selection Strategy:**
- **Intent Classifier**: Fast model (classification is simple)
- **Schema Analyzer**: Fast model (pattern matching)
- **SQL Generator**: Default model (complex reasoning needed)
- **Viz Planner**: Fast model (simple selection)
- **Answer Generator**: Fast model (text generation)

**Expected Savings:**
- Intent: 5s → 2.5s (50% faster)
- Schema: 5s → 2.5s (50% faster)
- Viz: 3s → 1.5s (50% faster)
- Answer: 3.5s → 2s (43% faster)
- **Total: 16.5s → 9.5s** (42% reduction)

#### 2.1.5 Reduce Reasoning Budget for Simple Tasks

**Impact**: 10-15% reduction in LLM latency (2-3 seconds saved)

**Current**: All agents use `reasoning_budget=1024`

**Optimization:**
```python
# backend/agents/intent_classifier.py
llm = create_llm(
    reasoning_budget=256,  # Reduced from 1024
    enable_thinking=False,  # Disable for classification
)

# backend/agents/schema_analyzer.py
llm = create_llm(
    reasoning_budget=512,  # Reduced from 1024
    enable_thinking=False,
)

# backend/agents/sql_generator.py
llm = create_llm(
    reasoning_budget=1024,  # Keep high (complex task)
    enable_thinking=True,
)

# backend/agents/viz_planner.py
llm = create_llm(
    reasoning_budget=128,  # Minimal (simple selection)
    enable_thinking=False,
)
```

**Expected Savings:**
- Intent: 5s → 4s (20% faster)
- Schema: 5s → 4s (20% faster)
- Viz: 3s → 2s (33% faster)
- **Total: 13s → 10s** (23% reduction)

---

### 2.2 Medium-Impact Optimizations (Phase 2)

#### 2.2.1 Implement Query Pattern Recognition

**Impact**: 30-40% reduction for common patterns (5-7 seconds saved)

**Strategy:**
Pre-define SQL templates for common query patterns and match queries to templates before LLM generation.

```python
# backend/utils/query_patterns.py

QUERY_PATTERNS = {
    "top_products": {
        "pattern": r"(top|best|most|highest).*(product|item|menu)",
        "intent": QueryIntent.PRODUCT_ANALYSIS,
        "sql_template": """
            SELECT product, SUM(total_revenue) as revenue
            FROM v_product_sales_summary
            GROUP BY product
            ORDER BY revenue DESC
            LIMIT {limit}
        """,
        "tables": ["v_product_sales_summary"],
    },
    "revenue_by_location": {
        "pattern": r"(revenue|sales).*(location|store|restaurant)",
        "intent": QueryIntent.LOCATION_COMPARISON,
        "sql_template": """
            SELECT location_name, SUM(total_revenue) as revenue
            FROM v_daily_sales_summary
            GROUP BY location_name
            ORDER BY revenue DESC
        """,
        "tables": ["v_daily_sales_summary"],
    },
    # ... more patterns
}

def match_query_pattern(query: str) -> dict | None:
    """Match query to known pattern"""
    query_lower = query.lower()
    for pattern_name, pattern_def in QUERY_PATTERNS.items():
        if re.search(pattern_def["pattern"], query_lower):
            return pattern_def
    return None
```

**Expected Savings:**
- Pattern match: Skip 3-4 LLM calls (10-15s saved)
- Pattern miss: 5ms overhead (negligible)

#### 2.2.2 Optimize Database Query Execution

**Impact**: 20-30% reduction in SQL execution time (40-60ms saved)

**Strategies:**

1. **Use Prepared Statements**
   ```python
   # Cache prepared statements for common query patterns
   # Reduces query planning time
   ```

2. **Add Query Hints**
   ```sql
   -- Use index hints for common patterns
   SELECT /*+ INDEX(unified_orders idx_order_date) */ ...
   ```

3. **Optimize View Queries**
   ```sql
   -- Use materialized views instead of views
   -- Add covering indexes for common SELECT patterns
   ```

4. **Connection Pool Tuning**
   ```python
   # Increase pool size for concurrent queries
   db_pool_min_size: 10  # Up from 5
   db_pool_max_size: 30  # Up from 20
   ```

**Expected Savings:**
- Query planning: 20-30ms → 5-10ms
- Total execution: 200ms → 150ms

#### 2.2.3 Implement Early Exit Strategies

**Impact**: 5-10% reduction (1-2 seconds saved)

**Strategies:**

1. **Skip Visualization for Empty Results**
   ```python
   if not formatted_results:
       viz_response = VisualizationResponse(type=VisualizationType.TABLE, config={})
       # Skip viz_planner LLM call (saves 3s)
   ```

2. **Skip Answer Generation for Simple Queries**
   ```python
   # If query is simple metric (single number), skip answer generation
   if is_simple_metric(query, results):
       answer = f"Result: {results[0]['value']}"
       # Skip answer_generator LLM call (saves 3.5s)
   ```

3. **Fast Path for Cached Intent**
   ```python
   # If intent is cached and high confidence, skip schema analysis
   if cached_intent and confidence > 0.9:
       # Use cached schema (saves 5s)
   ```

**Expected Savings:**
- Empty results: 3s (skip viz planner)
- Simple metrics: 3.5s (skip answer generator)
- Cached intent: 5s (skip schema analyzer)

#### 2.2.4 Optimize Prompt Lengths

**Impact**: 5-10% reduction in LLM latency (1-2 seconds saved)

**Current**: Verbose prompts with extensive examples

**Optimization:**
1. Use concise, structured prompts
2. Move examples to few-shot learning (separate call)
3. Use prompt templates with minimal context

```python
# Before: 500+ tokens
# After: 200-300 tokens (40% reduction)

# Example: SQL Generator
SQL_GENERATOR_PROMPT = """Generate PostgreSQL query.

Query: {user_query}
Intent: {intent}
Tables: {tables}
Columns: {columns}

Rules:
- Use views for aggregates
- Divide *_cents by 100.0
- Filter voided=FALSE
- GROUP BY for comparisons

Return JSON: {{"sql": "...", "explanation": "..."}}
"""
```

**Expected Savings:**
- Token reduction: 40% → 20-30% faster LLM calls
- Total: 1-2 seconds saved

---

### 2.3 Database Schema Optimizations

#### 2.3.1 Add Strategic Indexes

**Impact**: 30-50% faster queries (50-100ms saved)

**Current Indexes (from schema):**
- ✅ Basic indexes on foreign keys and date columns exist
- ⚠️ Missing composite indexes for common query patterns
- ⚠️ Missing partial indexes with WHERE clauses

**Recommended Additional Indexes:**

```sql
-- 1. Composite index for date + location + source queries (most common pattern)
CREATE INDEX idx_orders_date_location_source_voided 
ON unified_orders(order_date, unified_location_id, source_system) 
WHERE voided = FALSE;

-- 2. Order type + date for comparison queries
CREATE INDEX idx_orders_type_date_voided 
ON unified_orders(order_type, order_date) 
WHERE voided = FALSE;

-- 3. Source system + date for source analysis
CREATE INDEX idx_orders_source_date_voided 
ON unified_orders(source_system, order_date) 
WHERE voided = FALSE;

-- 4. Covering index for payment analysis (includes amount for faster aggregation)
CREATE INDEX idx_payments_type_source_amount 
ON unified_payments(payment_type, source_system, amount_cents);

-- 5. Product analysis with date (for time-based product queries)
CREATE INDEX idx_order_items_product_order_date 
ON unified_order_items(unified_product_id, order_id) 
INCLUDE (quantity, total_price_cents, category_name);

-- 6. Category + source for category analysis by source
CREATE INDEX idx_order_items_category_source 
ON unified_order_items(category_name, source_system) 
INCLUDE (quantity, total_price_cents);

-- 7. Timestamp-based queries (hourly patterns)
CREATE INDEX idx_orders_timestamp_location 
ON unified_orders(order_timestamp, unified_location_id) 
WHERE voided = FALSE;

-- 8. Payment date + type for payment method analysis
CREATE INDEX idx_payments_date_type 
ON unified_payments(payment_date, payment_type, source_system);
```

**Index Usage Analysis:**

Run this to identify missing indexes:
```sql
-- Find slow queries that could benefit from indexes
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE schemaname = 'public'
AND tablename IN ('unified_orders', 'unified_order_items', 'unified_payments')
ORDER BY correlation DESC;
```

**Expected Savings:**
- Query execution: 200ms → 100-150ms (50% faster)
- Index scan vs table scan: 10-50x faster
- Composite queries: 300-500ms → 100-150ms (3-5x faster)

#### 2.3.2 Partition Large Tables

**Impact**: 20-30% faster queries on large datasets

**Strategy:**
Partition `unified_orders` by `order_date` for time-based queries.

```sql
-- Partition by month
CREATE TABLE unified_orders_2025_01 PARTITION OF unified_orders
FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- Enables partition pruning (only scan relevant partitions)
```

**Expected Savings:**
- Large date ranges: 500ms → 200ms
- Partition pruning: Only scan relevant months

#### 2.3.3 Create Materialized Views for Common Aggregations

**Impact**: 50-70% faster for aggregated queries

**Priority Views to Materialize:**

1. `mv_daily_sales_summary` (highest priority)
2. `mv_product_sales_summary`
3. `mv_payment_methods_by_source`
4. `mv_order_type_source_performance`

**Refresh Strategy:**
```python
# backend/utils/materialized_views.py

async def refresh_materialized_views():
    """Refresh all materialized views"""
    views = [
        "mv_daily_sales_summary",
        "mv_product_sales_summary",
        "mv_payment_methods_by_source",
    ]
    
    for view in views:
        await SupabasePool.execute_query(
            f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"
        )
```

**Expected Savings:**
- View computation: 100-200ms → 5-10ms
- Total query: 200ms → 50-100ms

---

### 2.4 Backend Code Optimizations

#### 2.4.1 Optimize State Management

**Impact**: 20-50ms saved per query

**Current**: Deep copying state for parallel execution

**Optimization:**
```python
# Use immutable state structures
# Avoid deep copying by using references where safe
# Only copy mutable fields (agent_trace)
```

#### 2.4.2 Batch LLM Calls Where Possible

**Impact**: 10-20% reduction for batch queries

**Strategy:**
If multiple similar queries arrive, batch them into single LLM call.

```python
# Batch intent classification for similar queries
def batch_classify_intents(queries: list[str]) -> list[dict]:
    """Classify multiple queries in one LLM call"""
    prompt = f"Classify these queries:\n{queries}"
    # Single LLM call instead of N calls
```

#### 2.4.3 Implement Connection Pooling for LLM

**Impact**: 5-10% reduction in LLM overhead

**Strategy:**
Reuse LLM connections instead of creating new ones per call.

```python
# Pool LLM instances
class LLMPool:
    def __init__(self):
        self.pool = {}
    
    def get_llm(self, model_type: str):
        if model_type not in self.pool:
            self.pool[model_type] = create_llm(...)
        return self.pool[model_type]
```

---

## 3. Implementation Roadmap

### Phase 1: Quick Wins (Week 1-2)

**Priority**: High  
**Effort**: Low-Medium  
**Expected Impact**: 30-40% improvement

1. ✅ **Implement Caching** (2-3 days)
   - Query result cache
   - Intent classification cache
   - Schema analysis cache

2. ✅ **Use Fast Models** (1 day)
   - Configure fast model for simple tasks
   - Update agent configurations

3. ✅ **Reduce Reasoning Budget** (1 day)
   - Update reasoning budgets per agent
   - Test accuracy impact

4. ✅ **Early Exit Strategies** (1 day)
   - Skip viz for empty results
   - Skip answer for simple metrics

**Expected Result**: 18-20s → 12-14s (30-35% improvement)

### Phase 2: Database Optimizations (Week 3-4)

**Priority**: High  
**Effort**: Medium  
**Expected Impact**: 20-30% improvement

1. ✅ **Materialize Views** (2-3 days)
   - Convert views to materialized views
   - Implement refresh strategy
   - Update agent prompts to use materialized views

2. ✅ **Add Strategic Indexes** (1-2 days)
   - Create composite indexes
   - Create covering indexes
   - Monitor query performance

3. ✅ **Optimize Schema Knowledge** (1 day)
   - Pre-serialize schema summaries
   - Create focused summaries per agent

**Expected Result**: 12-14s → 9-11s (additional 20-25% improvement)

### Phase 3: Advanced Optimizations (Week 5-8)

**Priority**: Medium  
**Effort**: Medium-High  
**Expected Impact**: 15-20% improvement

1. ✅ **Query Pattern Recognition** (1 week)
   - Define common patterns
   - Implement pattern matching
   - Create SQL templates

2. ✅ **Prompt Optimization** (3-4 days)
   - Reduce prompt lengths
   - Optimize prompt structure
   - Test accuracy impact

3. ✅ **Database Query Optimization** (2-3 days)
   - Prepared statements
   - Query hints
   - Connection pool tuning

**Expected Result**: 9-11s → 8-10s (additional 10-15% improvement)

### Phase 4: Long-term Optimizations (Month 3+)

**Priority**: Low-Medium  
**Effort**: High  
**Expected Impact**: 10-15% improvement

1. **Table Partitioning** (2-3 weeks)
   - Partition by date
   - Implement partition management
   - Update queries for partition awareness

2. **Advanced Caching** (1-2 weeks)
   - Redis integration
   - Distributed caching
   - Cache invalidation strategies

3. **Batch Processing** (2-3 weeks)
   - Batch similar queries
   - Parallel query processing
   - Queue management

---

## 4. Expected Performance Improvements

### Cumulative Impact

| Phase | Optimization | Time Saved | New Total | Improvement |
|-------|-------------|------------|-----------|-------------|
| **Baseline** | Current | - | 18-20s | - |
| **Phase 1** | Caching + Fast Models + Early Exit | 6-7s | 12-13s | 35% |
| **Phase 2** | Materialized Views + Indexes | 2-3s | 9-10s | 50% |
| **Phase 3** | Pattern Recognition + Prompts | 1-2s | 8-9s | 55% |
| **Phase 4** | Partitioning + Advanced Caching | 0.5-1s | 7.5-8.5s | 60% |

### Performance Targets

| Metric | Current | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|--------|---------|---------|---------|---------|---------|
| **P50 Latency** | 18-20s | 12-13s | 9-10s | 8-9s | 7.5-8.5s |
| **P95 Latency** | 35-45s | 22-25s | 16-18s | 14-16s | 12-14s |
| **P99 Latency** | 60+s | 35-40s | 25-30s | 20-25s | 18-22s |
| **Throughput** | 3-4 qpm | 5-6 qpm | 7-8 qpm | 8-9 qpm | 10-12 qpm |

---

## 5. Risk Assessment & Mitigation

### 5.1 Accuracy Risks

**Risk**: Faster models may reduce accuracy

**Mitigation**:
- A/B test fast vs default models
- Monitor accuracy metrics
- Fallback to default model if confidence < threshold

### 5.2 Cache Invalidation

**Risk**: Stale cache data after data ingestion

**Mitigation**:
- Event-driven cache invalidation
- TTL-based expiration
- Version-based cache keys

### 5.3 Materialized View Maintenance

**Risk**: Stale data in materialized views

**Mitigation**:
- Incremental refresh strategy
- Event-driven refresh on data ingestion
- Health checks for view freshness

---

## 6. Monitoring & Metrics

### 6.1 Key Metrics to Track

1. **Latency Metrics**
   - P50, P75, P90, P95, P99 latencies
   - Latency by agent
   - Latency by query type

2. **Cache Metrics**
   - Cache hit rate
   - Cache miss rate
   - Cache size and memory usage

3. **Database Metrics**
   - Query execution time
   - Index usage
   - Materialized view refresh time

4. **LLM Metrics**
   - LLM call latency
   - Token usage
   - Error rate

### 6.2 Recommended Dashboards

1. **Latency Dashboard**
   - Real-time latency percentiles
   - Latency trends
   - Agent-level breakdown

2. **Cache Dashboard**
   - Hit/miss rates
   - Cache performance
   - Memory usage

3. **Database Dashboard**
   - Query performance
   - Index usage
   - Materialized view status

---

## 7. Implementation Checklist

### Phase 1 (Week 1-2)

- [ ] Implement query result cache
- [ ] Implement intent classification cache
- [ ] Implement schema analysis cache
- [ ] Configure fast models for simple tasks
- [ ] Reduce reasoning budgets
- [ ] Add early exit for empty results
- [ ] Add early exit for simple metrics

### Phase 2 (Week 3-4)

- [ ] Convert views to materialized views
- [ ] Implement materialized view refresh strategy
- [ ] Add composite indexes
- [ ] Add covering indexes
- [ ] Optimize schema knowledge loading
- [ ] Pre-serialize schema summaries

### Phase 3 (Week 5-8)

- [ ] Implement query pattern recognition
- [ ] Create SQL templates for common patterns
- [ ] Optimize prompt lengths
- [ ] Implement prepared statements
- [ ] Tune connection pool settings

### Phase 4 (Month 3+)

- [ ] Implement table partitioning
- [ ] Set up Redis for distributed caching
- [ ] Implement batch processing
- [ ] Advanced cache invalidation

---

## 8. Success Criteria

### Minimum Viable Improvements

- ✅ **P50 Latency**: < 12 seconds (40% improvement)
- ✅ **P95 Latency**: < 20 seconds (50% improvement)
- ✅ **Cache Hit Rate**: > 30% for common queries
- ✅ **SQL Execution**: < 100ms average

### Stretch Goals

- 🎯 **P50 Latency**: < 8 seconds (60% improvement)
- 🎯 **P95 Latency**: < 15 seconds (65% improvement)
- 🎯 **Cache Hit Rate**: > 50% for common queries
- 🎯 **Throughput**: > 10 queries/minute

---

## 9. Conclusion

By implementing the optimizations outlined in this document, we can achieve:

- **50-60% latency reduction** for typical queries
- **2.5x throughput improvement**
- **Better user experience** with faster response times
- **Reduced infrastructure costs** (fewer LLM API calls)

The highest-impact optimizations are:
1. **Caching** (Phase 1) - 30-40% improvement
2. **Materialized Views** (Phase 2) - 20-30% improvement
3. **Fast Models** (Phase 1) - 20-30% improvement

These should be prioritized for maximum impact with minimal risk.

---

## Appendix A: Code Examples

### A.1 Caching Implementation

```python
# backend/utils/cache.py
import time
import hashlib
import json
from typing import Any, Optional
from functools import lru_cache

class QueryCache:
    """Multi-level cache for query results and agent outputs"""
    
    def __init__(self, default_ttl: int = 3600):
        self.cache: dict[str, dict] = {}
        self.default_ttl = default_ttl
    
    def _make_key(self, prefix: str, query: str, context: dict = None) -> str:
        """Generate cache key"""
        normalized = query.lower().strip()
        context_str = json.dumps(context or {}, sort_keys=True)
        combined = f"{prefix}:{normalized}:{context_str}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired"""
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        if time.time() - entry['timestamp'] > entry['ttl']:
            del self.cache[key]
            return None
        
        return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set cached value"""
        self.cache[key] = {
            'value': value,
            'timestamp': time.time(),
            'ttl': ttl or self.default_ttl
        }
    
    def invalidate_pattern(self, pattern: str):
        """Invalidate all keys matching pattern"""
        keys_to_delete = [k for k in self.cache.keys() if pattern in k]
        for key in keys_to_delete:
            del self.cache[key]

# Global cache instance
query_cache = QueryCache(default_ttl=3600)
intent_cache = QueryCache(default_ttl=86400)  # 24 hours
schema_cache = QueryCache(default_ttl=86400)  # 24 hours
```

### A.2 Materialized View Refresh

```python
# backend/utils/materialized_views.py
import logging
from .database import SupabasePool

logger = logging.getLogger(__name__)

MATERIALIZED_VIEWS = [
    "mv_daily_sales_summary",
    "mv_product_sales_summary",
    "mv_payment_methods_by_source",
    "mv_order_type_source_performance",
    "mv_source_performance_summary",
]

async def refresh_all_materialized_views():
    """Refresh all materialized views concurrently"""
    for view in MATERIALIZED_VIEWS:
        try:
            await SupabasePool.execute_query(
                f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"
            )
            logger.info(f"Refreshed materialized view: {view}")
        except Exception as e:
            logger.error(f"Failed to refresh {view}: {e}")

async def refresh_incremental(view_name: str, since_date: str):
    """Incremental refresh for date-partitioned views"""
    # Implementation depends on view structure
    pass
```

### A.3 Query Pattern Matching

```python
# backend/utils/query_patterns.py
import re
from typing import Optional
from ..models.state import QueryIntent

QUERY_PATTERNS = {
    "top_products": {
        "pattern": r"(top|best|most|highest|popular).*\b(product|item|menu|selling)",
        "intent": QueryIntent.PRODUCT_ANALYSIS,
        "sql_template": """
            SELECT product, SUM(total_revenue) as revenue
            FROM v_product_sales_summary
            GROUP BY product
            ORDER BY revenue DESC
            LIMIT {limit}
        """,
        "tables": ["v_product_sales_summary"],
    },
    "revenue_by_location": {
        "pattern": r"(revenue|sales|total).*\b(location|store|restaurant)",
        "intent": QueryIntent.LOCATION_COMPARISON,
        "sql_template": """
            SELECT location_name, SUM(total_revenue) as revenue
            FROM v_daily_sales_summary
            GROUP BY location_name
            ORDER BY revenue DESC
        """,
        "tables": ["v_daily_sales_summary"],
    },
    "payment_methods": {
        "pattern": r"(payment|method|card|cash).*\b(used|most|top)",
        "intent": QueryIntent.PAYMENT_ANALYSIS,
        "sql_template": """
            SELECT payment_type, SUM(transaction_count) as count, SUM(total_amount) as total
            FROM v_payment_methods_by_source
            GROUP BY payment_type
            ORDER BY count DESC
        """,
        "tables": ["v_payment_methods_by_source"],
    },
}

def match_query_pattern(query: str) -> Optional[dict]:
    """Match query to known pattern"""
    query_lower = query.lower()
    for pattern_name, pattern_def in QUERY_PATTERNS.items():
        if re.search(pattern_def["pattern"], query_lower):
            return pattern_def
    return None
```

### A.4 Fast Model Configuration

```python
# backend/config/agent_config.py
from typing import Literal

AGENT_MODEL_CONFIG = {
    "intent_classifier": {
        "model_type": "fast",
        "reasoning_budget": 256,
        "enable_thinking": False,
        "temperature": 0.1,
    },
    "schema_analyzer": {
        "model_type": "fast",
        "reasoning_budget": 512,
        "enable_thinking": False,
        "temperature": 0.1,
    },
    "sql_generator": {
        "model_type": "default",  # Keep large model
        "reasoning_budget": 1024,
        "enable_thinking": True,
        "temperature": 0.2,
    },
    "viz_planner": {
        "model_type": "fast",
        "reasoning_budget": 128,
        "enable_thinking": False,
        "temperature": 0.1,
    },
    "answer_generator": {
        "model_type": "fast",
        "reasoning_budget": 512,
        "enable_thinking": False,
        "temperature": 0.3,
    },
}
```

---

## Appendix B: SQL Optimization Scripts

### B.1 Create Materialized Views

```sql
-- Convert v_daily_sales_summary to materialized view
CREATE MATERIALIZED VIEW mv_daily_sales_summary AS
SELECT 
    uo.order_date,
    ul.location_code,
    ul.location_name,
    uo.order_type,
    uo.source_system,
    COUNT(DISTINCT uo.order_id) as order_count,
    COUNT(DISTINCT uoi.order_item_id) as item_count,
    SUM(uo.subtotal_cents) / 100.0 as total_subtotal,
    SUM(uo.tax_cents) / 100.0 as total_tax,
    SUM(uo.tip_cents) / 100.0 as total_tips,
    SUM(uo.total_cents) / 100.0 as total_revenue,
    SUM(uo.service_fee_cents) / 100.0 as total_service_fees,
    SUM(uo.delivery_fee_cents) / 100.0 as total_delivery_fees,
    SUM(uo.commission_cents) / 100.0 as total_commissions,
    SUM(COALESCE(uo.merchant_payout_cents, uo.total_cents - COALESCE(uo.commission_cents, 0))) / 100.0 as net_revenue
FROM unified_orders uo
JOIN unified_locations ul ON uo.unified_location_id = ul.location_id
LEFT JOIN unified_order_items uoi ON uo.order_id = uoi.order_id
WHERE uo.voided = FALSE
GROUP BY uo.order_date, ul.location_code, ul.location_name, uo.order_type, uo.source_system;

-- Create indexes on materialized view
CREATE INDEX idx_mv_daily_date ON mv_daily_sales_summary(order_date);
CREATE INDEX idx_mv_daily_location ON mv_daily_sales_summary(location_code);
CREATE INDEX idx_mv_daily_source ON mv_daily_sales_summary(source_system);
CREATE INDEX idx_mv_daily_type ON mv_daily_sales_summary(order_type);
```

### B.2 Add Composite Indexes

```sql
-- Run these to add recommended composite indexes
-- (See section 2.3.1 for full list)

CREATE INDEX CONCURRENTLY idx_orders_date_location_source_voided 
ON unified_orders(order_date, unified_location_id, source_system) 
WHERE voided = FALSE;

CREATE INDEX CONCURRENTLY idx_orders_type_date_voided 
ON unified_orders(order_type, order_date) 
WHERE voided = FALSE;
```

---

**Document End**

