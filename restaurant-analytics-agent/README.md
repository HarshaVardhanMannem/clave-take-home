# Restaurant Analytics Agent

A Natural Language to SQL agent system for restaurant analytics. Converts natural language queries into SQL, executes them on Supabase, and generates visualizations.

## Features

- **Natural Language Understanding**: Converts plain English queries into SQL
- **Multi-Agent Architecture**: Uses LangGraph for orchestrated agent workflow
- **Smart Schema Awareness**: Knows about tables, columns, and optimization strategies
- **SQL Validation**: Validates queries for safety and correctness
- **Auto-Retry**: Automatically fixes common SQL generation errors
- **Visualization Planning**: Suggests appropriate chart types based on data
- **Chart.js Integration**: Generates Chart.js compatible configurations

> ⚠️ **Data Note:** The current database contains data from **January 1-4, 2025** only.

## Tech Stack

- **Backend**: FastAPI + Python 3.11
- **Agent Framework**: LangGraph + LangChain
- **Database**: Supabase (PostgreSQL with SSL)
- **LLM**: NVIDIA Nemotron (via NVIDIA API)
- **Visualization**: Chart.js compatible configs

## Quick Start

### 1. Install Dependencies

```bash
cd restaurant-analytics-agent
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
# Supabase Database
SUPABASE_DB_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres

# NVIDIA API
NVIDIA_API_KEY=your-nvidia-api-key
NVIDIA_MODEL=ai-nemotron-3-nano-30b-a3b

# Server
API_HOST=0.0.0.0
API_PORT=8000
```

### 3. Run the Server

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Test the API

```bash
# Health check
curl http://localhost:8000/api/health

# Query example
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What were total sales yesterday?"}'
```

## API Endpoints

### Main Query Endpoint

**POST** `/api/query`

Process a natural language query.

```json
{
  "query": "Show me the top 10 selling products last month",
  "include_chart": true,
  "max_results": 100
}
```

Response:
```json
{
  "success": true,
  "query_id": "uuid",
  "intent": "product_analysis",
  "sql": "SELECT product_name, total_quantity_sold...",
  "explanation": "This query retrieves the top 10 products...",
  "results": [...],
  "result_count": 10,
  "columns": ["product_name", "total_quantity_sold", "total_revenue"],
  "visualization": {
    "type": "bar_chart",
    "config": {...},
    "chart_js_config": {...}
  },
  "execution_time_ms": 45.2
}
```

### Other Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/schema` | GET | Get database schema info |
| `/api/examples` | GET | Get example queries |
| `/api/explain` | POST | Explain query without executing |
| `/api/validate-sql` | POST | Validate SQL query |
| `/api/stats` | GET | Get API statistics |

## Agent Workflow

```
User Query
     ↓
┌─────────────────┐
│ Intent Classifier│ → Extract intent, entities, time range
└────────┬────────┘
         ↓
    Need Clarification? ──YES──→ Return clarification question
         │ NO
         ↓
┌─────────────────┐
│ Schema Analyzer  │ → Identify tables, columns, joins
└────────┬────────┘
         ↓
┌─────────────────┐
│ SQL Generator    │ → Generate PostgreSQL query
└────────┬────────┘
         ↓
┌─────────────────┐
│ SQL Validator    │ → Validate safety & correctness
└────────┬────────┘
         ↓
    Validation Passed? ──NO──→ Retry (max 2 times)
         │ YES
         ↓
    Execute on Supabase
         ↓
┌─────────────────┐
│ Viz Planner     │ → Select chart type
└────────┬────────┘
         ↓
    Return Results + Visualization
```

## Query Intent Types

| Intent | Description | Example Query |
|--------|-------------|---------------|
| `sales_analysis` | Revenue, totals, sales | "Total sales yesterday" |
| `product_analysis` | Product performance, rankings | "Top 10 products" |
| `location_comparison` | Compare stores | "Revenue by location" |
| `time_series` | Trends, patterns | "Daily sales last month" |
| `payment_analysis` | Payment methods, tips | "Credit vs cash breakdown" |
| `order_type_analysis` | Dine-in/delivery/takeout | "Compare order types" |
| `source_comparison` | Toast/DoorDash/Square | "Revenue by source" |
| `category_analysis` | Category performance | "Sales by category" |

## Visualization Types

| Type | When Used |
|------|-----------|
| `bar_chart` | Categorical comparison, rankings |
| `line_chart` | Time series, trends |
| `pie_chart` | Part-to-whole (≤8 categories) |
| `table` | Detailed data, many columns |
| `stacked_bar` | Composition within categories |
| `heatmap` | Two-dimensional patterns |

## Schema Knowledge

The agent understands these tables:

### Base Tables
- `unified_orders` - Main order data (money in cents)
- `unified_order_items` - Line items (money in cents)
- `unified_products` - Product catalog
- `unified_locations` - Restaurant locations
- `unified_payments` - Payment transactions (money in cents)

### Optimized Views (Pre-aggregated, Faster)
- `v_daily_sales_summary` - Daily metrics (money in dollars)
- `v_product_sales_summary` - Product metrics (money in dollars)
- `v_hourly_sales_pattern` - Hourly patterns (money in dollars)

### Critical Rules
1. Base tables: Divide `*_cents` by 100.0 for dollars
2. Views: Already in dollars, don't divide
3. Always filter `voided = FALSE` on `unified_orders`
4. Prefer views for aggregations (faster)

## Running Tests

```bash
# Unit tests (no external dependencies)
pytest tests/test_agents.py -v

# Integration tests (requires .env)
pytest tests/test_integration.py -v --timeout=60
```

## Project Structure

```
restaurant-analytics-agent/
├── backend/
│   ├── main.py                    # FastAPI app
│   ├── agent_framework.py         # LangGraph workflow
│   ├── database.py                # Supabase connection
│   ├── visualization.py           # Chart generator
│   ├── agents/
│   │   ├── intent_classifier.py   # Query understanding
│   │   ├── schema_analyzer.py     # Table selection
│   │   ├── sql_generator.py       # SQL generation
│   │   ├── sql_validator.py       # Safety validation
│   │   └── viz_planner.py         # Visualization selection
│   ├── models/
│   │   ├── state.py               # AgentState TypedDict
│   │   ├── requests.py            # API request models
│   │   └── responses.py           # API response models
│   ├── config/
│   │   ├── settings.py            # Environment config
│   │   └── schema_knowledge.py    # Schema metadata
│   └── utils/
│       ├── validators.py          # SQL validation
│       └── formatters.py          # Data formatting
├── tests/
│   ├── test_agents.py             # Unit tests
│   ├── test_integration.py        # Integration tests
│   └── fixtures/
│       └── sample_queries.json    # Test data
├── requirements.txt
└── README.md
```

## Example Queries

> **Note:** The database currently contains data from **January 1-4, 2025** only.

```
"What were total sales on January 2nd?"
"Show me the top 10 selling products"
"Compare revenue across all locations"
"What are our busiest hours?"
"Payment method breakdown"
"Daily revenue trend from Jan 1-4, 2025"
"Compare dine-in vs delivery vs takeout"
"Which categories generate the most revenue?"
"Average order value by location"
"Toast vs DoorDash revenue comparison"
"Total orders by source system"
"Sales breakdown by order type"
```

## Error Handling

The API returns structured error responses:

```json
{
  "success": false,
  "error_code": "SQL_GENERATION_FAILED",
  "error_message": "Failed to generate valid SQL",
  "details": {
    "errors": ["Missing voided filter"],
    "retries": 2
  },
  "suggestions": [
    "Try rephrasing your question",
    "Be more specific about what data you want"
  ]
}
```

## License

MIT License

