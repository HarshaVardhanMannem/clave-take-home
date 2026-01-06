# Data Ingestion & Cleaning Pipeline Guide

## Overview

This guide provides a comprehensive explanation of the data cleaning and ingestion pipeline that processes restaurant data from three sources (Toast POS, DoorDash, and Square) and loads it into a unified PostgreSQL database schema.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Pipeline Flow](#pipeline-flow)
3. [Data Cleaning Process](#data-cleaning-process)
4. [Data Ingestion Process](#data-ingestion-process)
5. [Setup & Configuration](#setup--configuration)
6. [Running the Pipeline](#running-the-pipeline)
7. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### System Components

```
┌─────────────────┐
│  Source Data    │
│  (JSON Files)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Data Cleaning  │
│  & Normalization│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Product        │
│  Matching       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Data           │
│  Transformation │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Database       │
│  (Unified Schema)│
└─────────────────┘
```

### Data Sources

1. **Toast POS** (`toast_pos_export.json`)
   - Nested structure: Orders → Checks → Selections
   - Includes modifiers, payments, locations
   - Source system identifier: `'toast'`

2. **DoorDash** (`doordash_orders.json`)
   - Flat order structure
   - Includes delivery information, commissions
   - Source system identifier: `'doordash'`

3. **Square** (`square/` directory)
   - Split files: `orders.json`, `catalog.json`, `payments.json`, `locations.json`
   - Catalog-based product structure
   - Source system identifier: `'square'`

---

## Pipeline Flow

### Step-by-Step Process

```
1. INITIALIZATION
   ├── Load configuration
   ├── Connect to database
   └── Set up reference data (locations, categories)

2. FOR EACH SOURCE:
   ├── Load JSON data
   ├── Parse and validate
   ├── Clean and normalize
   ├── Match products
   ├── Transform to unified format
   └── Insert into database

3. FINALIZATION
   ├── Commit transaction
   ├── Generate statistics
   └── Report results
```

### Detailed Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA INGESTION PIPELINE                   │
└─────────────────────────────────────────────────────────────┘

1. SETUP PHASE
   │
   ├─► Load Environment Variables (.env)
   │   └─► DATABASE_URL
   │
   ├─► Test Database Connection
   │   └─► Verify PostgreSQL/Supabase connectivity
   │
   └─► Initialize Reference Data
       ├─► Unified Locations (DOWNTOWN, AIRPORT, MALL, etc.)
       ├─► Location ID Mappings (source → unified)
       └─► Load existing categories/products for matching

2. DATA LOADING PHASE (Per Source)
   │
   ├─► Read JSON File(s)
   │   └─► Handle encoding, parse JSON
   │
   └─► Validate Structure
       └─► Check required fields, data types

3. DATA CLEANING PHASE (Per Record)
   │
   ├─► Text Normalization
   │   ├─► Remove Emojis (🍔, 🍟, 🥤, etc.)
   │   ├─► Fix Typos (griled → grilled, coffe → coffee)
   │   ├─► Normalize Whitespace
   │   └─► Preserve Original Case
   │
   ├─► Category Normalization
   │   ├─► Apply Category Mappings
   │   ├─► Standardize Names (ENTREES → Entrees)
   │   └─► Remove Emojis from Categories
   │
   └─► Product Name Normalization
       ├─► Remove Emojis
       ├─► Fix Typos
       ├─► Create Product Code (for matching)
       └─► Preserve Display Name

4. PRODUCT MATCHING PHASE
   │
   ├─► Exact Match
   │   └─► Match by normalized product code
   │
   ├─► Dictionary Match
   │   └─► Use predefined mappings (TYPO_CORRECTIONS)
   │
   └─► Fuzzy Match
       ├─► Calculate similarity score (Levenshtein)
       └─► Match if confidence > threshold (0.7)

5. DATA TRANSFORMATION PHASE
   │
   ├─► Map Locations
   │   └─► Source location ID → Unified location ID
   │
   ├─► Map Categories
   │   └─► Source category → Unified category ID
   │
   ├─► Map Products
   │   └─► Source product → Unified product ID
   │
   └─► Transform Order Data
       ├─► Convert dates/timestamps
       ├─► Convert amounts to cents
       ├─► Map order types
       └─► Extract payment information

6. DATABASE INSERTION PHASE
   │
   ├─► Insert/Update Categories
   │   ├─► category_name (normalized, no emojis)
   │   └─► display_name (original, with emojis)
   │
   ├─► Insert/Update Products
   │   ├─► product_name (original)
   │   ├─► normalized_name (cleaned)
   │   └─► product_code (for matching)
   │
   ├─► Insert Orders
   │   ├─► source_system ('toast', 'doordash', 'square')
   │   ├─► source_order_id (original ID)
   │   └─► Financial data (in cents)
   │
   ├─► Insert Order Items
   │   ├─► product_name (original)
   │   ├─► normalized_product_name (cleaned)
   │   ├─► category_name (normalized, no emojis)
   │   └─► source_system (preserved)
   │
   └─► Insert Payments
       ├─► Link to orders
       └─► Payment type, amount, method

7. COMMIT & REPORTING PHASE
   │
   ├─► Commit Transaction
   │   └─► All-or-nothing atomicity
   │
   └─► Generate Statistics
       ├─► Records processed
       ├─► Products matched
       ├─► Errors encountered
       └─► Performance metrics
```

---

## Data Cleaning Process

### 1. Emoji Removal

**Purpose**: Remove emojis from product names and categories while preserving the text content.

**Implementation**:
- Uses comprehensive Unicode ranges to detect emojis
- Preserves original text if emoji removal would result in empty string
- Normalizes whitespace after emoji removal

**Example**:
```
Input:  "🍔 Burgers" → Output: "Burgers"
Input:  "🍟 French Fries" → Output: "French Fries"
Input:  "🥤 Coca-Cola" → Output: "Coca-Cola"
```

**Code Location**: `scripts/utils/text_normalization.py::remove_emojis()`

### 2. Typo Correction

**Purpose**: Fix common spelling errors in product names while preserving original case.

**Implementation**:
- Uses word boundary matching to avoid partial matches
- Sorts typos by length (longest first) for accurate matching
- Preserves case: "Coffe" → "Coffee", "coffe" → "coffee"

**Example**:
```
Input:  "Griled Chiken Sandwhich" → Output: "Grilled Chicken Sandwich"
Input:  "Coffe" → Output: "Coffee"
Input:  "expresso" → Output: "espresso"
```

**Configuration**: `scripts/config/product_matching_config.py::TYPO_CORRECTIONS`

**Code Location**: `scripts/utils/text_normalization.py::fix_typos()`

### 3. Category Normalization

**Purpose**: Standardize category names across all sources.

**Process**:
1. Remove emojis
2. Fix typos
3. Apply category mappings (e.g., "ENTREES" → "Entrees")
4. Normalize case

**Example**:
```
Input:  "🍔 Burgers" → Output: "Burgers"
Input:  "ENTREES" → Output: "Entrees"
Input:  "🍟 Sides" → Output: "Sides"
```

**Configuration**: `scripts/config/product_matching_config.py::CATEGORY_NORMALIZATION`

**Code Location**: `scripts/utils/text_normalization.py::normalize_category()`

### 4. Product Name Normalization

**Purpose**: Clean product names for matching while preserving original for display.

**Process**:
1. Remove emojis
2. Fix typos
3. Normalize whitespace
4. Create product code (lowercase, alphanumeric only)

**Example**:
```
Input:  "🍔 Classic Burger"
Normalized Name: "Classic Burger"
Product Code: "classicburger"
```

**Code Location**: `scripts/utils/text_normalization.py::normalize_product_name()`

### 5. Product Code Generation

**Purpose**: Create standardized codes for product matching across sources.

**Process**:
- Lowercase conversion
- Remove all non-alphanumeric characters
- Remove whitespace

**Example**:
```
"Classic Burger" → "classicburger"
"Grilled Chicken Sandwich" → "grilledchickensandwich"
"Coca-Cola (Large)" → "cocacolalarge"
```

**Code Location**: `scripts/utils/text_normalization.py::create_product_code()`

---

## Data Ingestion Process

### Source-Specific Processing

#### Toast POS Ingestion

**File**: `toast_pos_export.json`

**Structure**:
```json
{
  "orders": [
    {
      "guid": "order_123",
      "restaurantGuid": "loc_downtown_001",
      "checks": [
        {
          "selections": [
            {
              "displayName": "🍔 Classic Burger",
              "itemGroup": { "name": "🍔 Burgers" },
              "price": 12.99,
              "quantity": 1
            }
          ]
        }
      ],
      "payments": [...]
    }
  ]
}
```

**Processing Steps**:
1. Extract order-level data (dates, location, status)
2. For each check (table):
   - Extract check-level data
   - For each selection (item):
     - Normalize product name and category
     - Match product to unified products
     - Calculate prices in cents
     - Insert order item
3. Extract and insert payments

**Code Location**: `scripts/ingest_unified_data.py::ingest_toast_data()`

#### DoorDash Ingestion

**File**: `doordash_orders.json`

**Structure**:
```json
{
  "orders": [
    {
      "order_id": "DD123",
      "store_id": "str_downtown_001",
      "order_items": [
        {
          "name": "Griled Chiken Sandwhich",
          "category": "ENTREES",
          "quantity": 1,
          "unit_price": 10.99,
          "total_price": 10.99
        }
      ],
      "commission": 2.50,
      "merchant_payout": 8.49
    }
  ]
}
```

**Processing Steps**:
1. Extract order data (dates, location, delivery info)
2. Calculate commissions and merchant payouts
3. For each order item:
   - Normalize product name and category
   - Match product
   - Insert order item
4. Note: DoorDash doesn't have separate payment records

**Code Location**: `scripts/ingest_unified_data.py::ingest_doordash_data()`

#### Square Ingestion

**Files**: `square/orders.json`, `square/catalog.json`, `square/payments.json`, `square/locations.json`

**Structure**:
```json
// catalog.json
{
  "objects": [
    {
      "type": "ITEM",
      "id": "ITEM_BURGER",
      "item_data": {
        "name": "Classic Burger",
        "category_id": "CAT_BURGERS",
        "variations": [
          {
            "id": "VAR_BURGER_REG",
            "item_variation_data": { "name": "Regular", "price_money": { "amount": 1299 } }
          }
        ]
      }
    }
  ]
}

// orders.json
{
  "orders": [
    {
      "id": "ord_123",
      "location_id": "LCN001DOWNTOWN",
      "line_items": [
        {
          "catalog_object_id": "VAR_BURGER_REG",
          "quantity": "2",
          "gross_sales_money": { "amount": 2598 }
        }
      ]
    }
  ]
}
```

**Processing Steps**:
1. Build catalog lookup (variation_id → item info)
2. Build category lookup (category_id → category name)
3. Build payments lookup (order_id → payment)
4. For each order:
   - Map location
   - For each line item:
     - Look up catalog item
     - Build product name (item + variation)
     - Normalize and match product
     - Insert order item
   - Insert payment if available

**Code Location**: `scripts/ingest_unified_data.py::ingest_square_data()`

### Database Schema Structure

#### Unified Tables

1. **unified_locations**
   - Standardized location codes (DOWNTOWN, AIRPORT, etc.)
   - Address information
   - Timezone

2. **location_id_mapping**
   - Maps source location IDs to unified location IDs
   - Example: `('toast', 'loc_downtown_001') → location_id: 1`

3. **unified_categories**
   - `category_name`: Normalized, emoji-free
   - `display_name`: Original with emojis (if any)

4. **unified_products**
   - `product_name`: Original name
   - `normalized_name`: Cleaned name
   - `product_code`: For matching

5. **product_name_mapping**
   - Maps source product names to unified products
   - Includes confidence scores

6. **unified_orders**
   - `source_system`: 'toast', 'doordash', or 'square'
   - `source_order_id`: Original order ID
   - Financial data (in cents)
   - Order type, status, dates

7. **unified_order_items**
   - `product_name`: Original from source
   - `normalized_product_name`: Cleaned
   - `category_name`: Normalized, emoji-free
   - `source_system`: Preserved for filtering

8. **unified_payments**
   - Payment type, method, amount
   - Linked to orders

---

## Setup & Configuration

### Prerequisites

1. **Python 3.8+**
2. **PostgreSQL Database** (or Supabase)
3. **Environment Variables** (`.env` file)

### Installation

```bash
# 1. Install dependencies
cd clave-take-home/scripts
pip install -r requirements.txt

# 2. Create .env file in project root
cat > .env << EOF
DATABASE_URL=postgresql://user:password@host:port/database
EOF

# 3. Test database connection
python -c "from scripts.db_connection import test_connection; test_connection()"
```

### Database Schema Setup

```bash
# Create unified schema
python scripts/create_schema.py

# Or manually using psql
psql $DATABASE_URL -f schemas/unified_schema.sql
```

### Configuration Files

**Location**: `scripts/config/product_matching_config.py`

**Key Configurations**:
- `TYPO_CORRECTIONS`: Dictionary of typos → corrections
- `CATEGORY_NORMALIZATION`: Category name mappings
- `LOCATION_MAPPINGS`: Source location IDs → unified codes
- `LOCATION_DETAILS`: Unified location information
- `PRODUCT_NAME_MAPPINGS`: Product name mappings

---

## Running the Pipeline

### Basic Usage

```bash
# Ingest all sources
python scripts/ingest_unified_data.py --all

# Ingest specific source
python scripts/ingest_unified_data.py --toast data/sources/toast_pos_export.json
python scripts/ingest_unified_data.py --doordash data/sources/doordash_orders.json
python scripts/ingest_unified_data.py --square-dir data/sources/square

# Dry run (test without committing)
python scripts/ingest_unified_data.py --all --dry-run
```

### Command-Line Options

```
--toast PATH          Path to Toast JSON file
--doordash PATH       Path to DoorDash JSON file
--square-dir PATH     Path to Square data directory
--all                 Ingest all sources
--dry-run             Test run without committing to database
```

### Pipeline Execution Flow

```
1. Initialize
   ├─► Load configuration
   ├─► Connect to database
   └─► Set up reference data

2. Process Each Source
   ├─► Load JSON data
   ├─► Clean and normalize
   ├─► Match products
   ├─► Transform data
   └─► Insert into database

3. Finalize
   ├─► Commit transaction
   └─► Print statistics
```

### Expected Output

```
Setting up reference data (locations, categories)...
✓ Set up 4 locations
✓ Loaded 0 existing categories
✓ Loaded 0 existing products

Ingesting Toast data...
Processing Toast orders: 100%|████████| 150/150 [00:05<00:00, 28.5it/s]
✓ Toast data ingestion completed

Ingesting DoorDash data...
Processing DoorDash orders: 100%|████████| 200/200 [00:03<00:00, 65.2it/s]
✓ DoorDash data ingestion completed

Ingesting Square data...
Processing Square orders: 100%|████████| 180/180 [00:04<00:00, 42.1it/s]
✓ Square data ingestion completed

✓ Data ingestion completed and committed!

Statistics:
  Locations: 4
  Categories: 12
  Products: 45
  Orders: 530
  Order Items: 1,245
  Payments: 480
```

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Failed

**Error**: `Database connection failed: could not translate host name`

**Solution**:
- Check `.env` file exists and has correct `DATABASE_URL`
- Verify database credentials
- Ensure database is accessible from your network

#### 2. Schema Not Found

**Error**: `relation "unified_orders" does not exist`

**Solution**:
```bash
# Create schema
python scripts/create_schema.py
```

#### 3. Emojis Not Removed

**Issue**: Emojis still appear in `category_name` or `normalized_product_name`

**Solution**:
- Verify data was re-ingested after emoji removal fix
- Check `normalize_category()` and `normalize_product_name()` are called
- Clear tables and re-ingest:
  ```bash
  python scripts/clear_all_tables.py --yes
  python scripts/ingest_unified_data.py --all
  ```

#### 4. Product Matching Issues

**Issue**: Products not matching across sources

**Solution**:
- Check `product_matching_config.py` for typos and mappings
- Verify product codes are generated correctly
- Review match confidence scores in `product_name_mapping` table

#### 5. Data Loss

**Issue**: Some records not appearing in database

**Solution**:
- Check for errors in logs
- Verify foreign key constraints are satisfied
- Ensure location mappings exist for all source locations
- Check for NULL values in required fields

### Debugging Tips

1. **Enable SQL Logging**:
   ```python
   # In db_connection.py
   engine = create_engine(connection_string, echo=True)
   ```

2. **Dry Run First**:
   ```bash
   python scripts/ingest_unified_data.py --all --dry-run
   ```

3. **Check Statistics**:
   - Review ingestion statistics output
   - Compare record counts with source files
   - Query database to verify data

4. **Test Individual Components**:
   ```bash
   # Test text normalization
   python scripts/test_data_cleaning.py
   
   # Test emoji removal
   python scripts/test_emoji_removal.py
   ```

---

## Data Quality Assurance

### Validation Checks

1. **Emoji Removal**: Verify no emojis in `normalized_name` or `category_name`
2. **Product Matching**: Check confidence scores in `product_name_mapping`
3. **Data Completeness**: Compare record counts with source files
4. **Referential Integrity**: Verify foreign keys are valid
5. **Financial Accuracy**: Verify amounts match source data

### Query Examples

```sql
-- Check for emojis in normalized fields
SELECT * FROM unified_categories 
WHERE category_name ~ '[\U0001F300-\U0001F9FF]';

-- Check product matching confidence
SELECT source_system, AVG(confidence_score) as avg_confidence
FROM product_name_mapping
GROUP BY source_system;

-- Verify data completeness
SELECT 
    source_system,
    COUNT(*) as order_count,
    SUM(total_cents) / 100.0 as total_revenue
FROM unified_orders
GROUP BY source_system;
```

---

## Summary

The data ingestion pipeline:

1. **Loads** JSON data from three sources
2. **Cleans** text by removing emojis and fixing typos
3. **Normalizes** categories and product names
4. **Matches** products across sources using fuzzy matching
5. **Transforms** data to unified schema format
6. **Inserts** into PostgreSQL database with proper relationships

All data is cleaned, normalized, and stored in a unified schema that enables cross-source analytics and natural language querying.

---

## Additional Resources

- **Schema Documentation**: `schemas/SCHEMA_DOCUMENTATION.md`
- **Example Queries**: `schemas/EXAMPLE_QUERIES.sql`
- **Query by Source**: `schemas/QUERY_BY_SOURCE_SYSTEM.md`
- **Configuration**: `scripts/config/product_matching_config.py`






