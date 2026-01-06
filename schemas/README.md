# Database Schema Files

This directory contains the unified database schema for the restaurant data integration project.

## Main Schema

### `unified_schema.sql` ⭐
The primary database schema that unifies data from all three sources (Toast POS, DoorDash, Square).

**Features:**
- Unified locations, categories, products, orders, and payments
- Source system tracking (`source_system` field in all tables)
- Pre-built analytics views
- Optimized for cross-source analytics and natural language querying

**Usage:**
```bash
# Create schema using Python script
python scripts/create_schema.py

# Or manually using psql
psql $DATABASE_URL -f schemas/unified_schema.sql
```

## Schema Structure

The unified schema includes:

### Core Tables
- `unified_locations` - Standardized location data
- `location_id_mapping` - Maps source location IDs to unified IDs
- `unified_categories` - Normalized categories (emoji-free)
- `unified_products` - Matched products across sources
- `product_name_mapping` - Product matching mappings
- `unified_orders` - All orders with source tracking
- `unified_order_items` - Order line items
- `unified_order_item_modifiers` - Item modifiers
- `unified_payments` - Payment transactions

### Analytics - Materialized Views Only

**Note:** This project uses **materialized views only** for analytics (not regular views). Materialized views are pre-aggregated and 10-50x faster.

**Materialized Views** (created via `create_materialized_views.py`):
- `mv_daily_sales_summary` - Daily sales aggregations
- `mv_product_sales_summary` - Product-level analytics
- `mv_product_location_sales` - Product sales by location
- `mv_hourly_sales_pattern` - Temporal sales patterns
- `mv_payment_methods_by_source` - Payment method aggregations
- `mv_order_type_performance` - Order type comparisons
- `mv_category_sales_summary` - Category-level aggregations
- `mv_location_performance` - Location performance metrics

Regular views (`v_*`) and source analysis views are **not used** in this project.

## Querying Data

All tables include `source_system` field ('toast', 'doordash', 'square') for filtering:

```sql
-- Query by source system
SELECT * FROM unified_orders WHERE source_system = 'toast';

-- Compare all sources
SELECT 
    source_system,
    COUNT(*) as order_count,
    SUM(total_cents) / 100.0 as revenue
FROM unified_orders
GROUP BY source_system;
```

## Documentation

- **`EXAMPLE_QUERIES.sql`** - SQL query examples
- **`QUERY_BY_SOURCE_SYSTEM.md`** - Guide for querying by source
- **`SCHEMA_DOCUMENTATION.md`** - Detailed schema design documentation
- **`SCHEMA_MAPPING.md`** - Field mapping reference

## Data Types

- **Monetary values**: Stored as cents (integers)
  - Display: `total_cents / 100.0`
  - Storage: `$12.99 = 1299 cents`

- **Timestamps**: Stored in UTC
  - Convert to location timezone for display


## Quick Start

### Recommended: Use the ETL Pipeline Orchestrator

```bash
# Full pipeline (schema + materialized views + ingestion) - RECOMMENDED
python scripts/run_etl_pipeline.py --full

# Only ingest data (assumes schema and materialized views exist)
python scripts/run_etl_pipeline.py --ingest-only
```

### Manual Steps (Advanced)

1. Create the schema: `python scripts/create_schema.py`
2. Create materialized views: `python scripts/create_materialized_views.py` (required for analytics)
3. Ingest data: `python scripts/ingest_unified_data.py --all`
4. Query data: Use materialized views (mv_*) - See `EXAMPLE_QUERIES.sql` for examples

For complete pipeline documentation, see: **[docs/DATA_INGESTION_GUIDE.md](../docs/DATA_INGESTION_GUIDE.md)**
