# Database Optimization Guide

This directory contains optimization scripts for improving query performance through materialized views and strategic indexes.

## Files

- **`optimization_materialized_views.sql`** - Creates materialized views and indexes
- **`refresh_materialized_views.sql`** - Provides refresh strategies for materialized views

## Quick Start

### 1. Create Materialized Views and Indexes

```bash
# Run after unified_schema.sql and source_analysis_views.sql
psql $DATABASE_URL -f schemas/optimization_materialized_views.sql
```

### 2. Set Up Refresh Schedule

```bash
# Option A: Use PostgreSQL cron (if pg_cron extension available)
psql $DATABASE_URL -c "SELECT cron.schedule('refresh-views', '*/15 * * * *', 'SELECT refresh_materialized_views_smart();');"

# Option B: Use external cron
# Add to crontab:
# */15 * * * * psql $DATABASE_URL -c "SELECT refresh_materialized_views_smart();"
```

## Materialized Views Created

### 1. `mv_daily_sales_summary`
**Optimizes:**
- "Show me total sales by location"
- "What was the revenue yesterday?"
- "Compare sales between Downtown and Airport"
- "Daily revenue for the first week"

**Refresh Frequency:** Every 15 minutes (incremental) or daily (full)

### 2. `mv_product_sales_summary`
**Optimizes:**
- "List the top 10 selling items"
- "Which category generates the most revenue?"

**Refresh Frequency:** Daily (products change less frequently)

### 3. `mv_product_location_sales`
**Optimizes:**
- "Top selling items at the Mall"
- "Beverage sales across all locations"

**Refresh Frequency:** Daily

### 4. `mv_hourly_sales_pattern`
**Optimizes:**
- "What were hourly sales on the 3rd?"
- "Show me peak hours for each location"

**Refresh Frequency:** Every 15 minutes (incremental)

### 5. `mv_payment_methods_by_source`
**Optimizes:**
- "Which payment methods are most popular?"

**Refresh Frequency:** Hourly (payments change frequently)

### 6. `mv_order_type_performance`
**Optimizes:**
- "Compare delivery vs dine-in revenue"
- "Average order value by channel"

**Refresh Frequency:** Every 15 minutes

### 7. `mv_category_sales_summary`
**Optimizes:**
- "Which category generates the most revenue?"
- "Beverage sales across all locations"

**Refresh Frequency:** Daily

### 8. `mv_location_performance`
**Optimizes:**
- "Which location had the highest sales?"
- "Compare sales between Downtown and Airport"

**Refresh Frequency:** Every 15 minutes

## Indexes Created

### Composite Indexes
- `idx_orders_date_location_source_voided` - Date + Location + Source queries
- `idx_orders_type_date_voided` - Order type comparisons
- `idx_orders_source_date_voided` - Source system queries
- `idx_orders_timestamp_location_voided` - Hourly patterns
- `idx_order_items_product_order` - Product analysis
- `idx_order_items_category_source` - Category by source
- `idx_payments_date_type` - Payment analysis
- `idx_payments_type_source_amount` - Payment methods

### Covering Indexes
- `idx_orders_covering_daily` - Eliminates table lookups for daily sales
- `idx_order_items_covering_product` - Eliminates table lookups for product queries

### Partial Indexes
- `idx_orders_active_date_location` - Active orders only (voided = FALSE)
- `idx_orders_doordash_date` - DoorDash orders only
- `idx_orders_delivery_date` - Delivery orders only

## Performance Improvements

### Expected Query Speed Improvements

| Query Type | Before | After | Improvement |
|------------|--------|-------|-------------|
| Daily sales by location | 200-500ms | 10-50ms | **10-50x faster** |
| Top products | 300-600ms | 20-80ms | **15-30x faster** |
| Hourly patterns | 400-800ms | 15-60ms | **25-50x faster** |
| Payment methods | 200-400ms | 10-40ms | **20-40x faster** |
| Location comparisons | 300-500ms | 15-50ms | **20-30x faster** |

### Materialized View Benefits

1. **Pre-aggregated Data**: No need to compute aggregations on-the-fly
2. **Indexed Results**: Materialized views have their own indexes
3. **Reduced Joins**: Data is already joined and aggregated
4. **Faster Queries**: 10-50x faster than querying base tables

## Refresh Strategies

### Full Refresh
- **When**: After bulk data loads, when data integrity is critical
- **Speed**: Slower (30-60 seconds for all views)
- **Command**: `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_sales_summary;`

### Incremental Refresh
- **When**: Regular scheduled updates (every 15 minutes)
- **Speed**: Faster (5-15 seconds for recent data)
- **Method**: DELETE + INSERT for last 24-48 hours

### Smart Refresh
- **When**: Automated scheduling
- **Logic**: Full refresh if data > 1 day old, incremental otherwise
- **Function**: `SELECT refresh_materialized_views_smart();`

## Monitoring

### Check View Freshness
```sql
SELECT 
    'mv_daily_sales_summary' as view_name,
    MAX(order_date) as last_data_date,
    CURRENT_DATE - MAX(order_date) as days_behind
FROM mv_daily_sales_summary;
```

### Check Index Usage
```sql
SELECT 
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read
FROM pg_stat_user_indexes
WHERE tablename LIKE 'mv_%'
ORDER BY idx_scan DESC;
```

### Check View Sizes
```sql
SELECT 
    matviewname,
    pg_size_pretty(pg_total_relation_size('public.'||matviewname)) as size
FROM pg_matviews
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size('public.'||matviewname) DESC;
```

## Backward Compatibility

Regular views are created that point to materialized views:
- `v_daily_sales_summary` → `mv_daily_sales_summary`
- `v_product_sales_summary` → `mv_product_sales_summary`
- `v_hourly_sales_pattern` → `mv_hourly_sales_pattern`
- `v_payment_methods_by_source` → `mv_payment_methods_by_source`

Existing queries using these views will automatically benefit from materialized views without code changes.

## Maintenance

### Regular Maintenance Tasks

1. **Refresh Views**: Every 15 minutes (automated)
2. **Update Statistics**: Weekly
   ```sql
   ANALYZE unified_orders;
   ANALYZE unified_order_items;
   ```
3. **Reindex**: Monthly (if needed)
   ```sql
   REINDEX TABLE mv_daily_sales_summary;
   ```
4. **Monitor Growth**: Check view sizes monthly

### Troubleshooting

**Problem**: Views are stale
- **Solution**: Run `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_sales_summary;`

**Problem**: Queries still slow
- **Solution**: Check if query is using materialized view (EXPLAIN ANALYZE)
- **Solution**: Verify indexes are being used (pg_stat_user_indexes)

**Problem**: Refresh takes too long
- **Solution**: Use incremental refresh instead of full refresh
- **Solution**: Refresh during low-traffic periods

## Next Steps

1. ✅ Run `optimization_materialized_views.sql` to create views and indexes
2. ✅ Set up refresh schedule (every 15 minutes recommended)
3. ✅ Monitor query performance improvements
4. ✅ Adjust refresh frequency based on data update patterns
5. ✅ Consider partitioning for very large datasets (> 10M rows)

## Additional Optimizations

For even better performance, consider:
- **Table Partitioning**: Partition `unified_orders` by date
- **Query Result Caching**: Cache common query results in Redis
- **Read Replicas**: Use read replicas for analytics queries
- **Columnar Storage**: Consider columnar storage for analytics workloads


