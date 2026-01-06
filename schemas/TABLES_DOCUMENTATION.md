# Unified Restaurant Core Tables — LLM Reference

This document defines the canonical core tables used to unify restaurant data from Toast, DoorDash, and Square.
It is intended to be referenced by an LLM for SQL generation and analytics.

====================================================================
GENERAL RULES
====================================================================

- Monetary values are stored in CENTS unless explicitly converted.
- Orders with `voided = TRUE` must be excluded unless explicitly requested.
- Always respect table grain to avoid double counting.
- Do not invent columns or joins.
- Prefer analytics views if available; use base tables only when necessary.

====================================================================
TABLE: unified_locations
====================================================================

Purpose:
Canonical list of physical restaurant locations.

Grain:
One row per physical restaurant location.

Primary Key:
- location_id

Columns:
- location_id (SERIAL): Internal unique ID
- location_code (VARCHAR): Short unique identifier (e.g., DOWNTOWN, AIRPORT)
- location_name (VARCHAR): Human-readable name
- address_line1 (VARCHAR)
- city (VARCHAR)
- state (VARCHAR)
- zip_code (VARCHAR)
- country (VARCHAR): Default 'US'
- timezone (VARCHAR): Used for time-based analytics
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

Used For:
- Location-based grouping
- Display names
- Timezone-aware reporting

Join Rules:
- unified_orders.unified_location_id → unified_locations.location_id

Do NOT Use For:
- Revenue or order analytics directly

====================================================================
TABLE: location_id_mapping
====================================================================

Purpose:
Maps source-system location IDs to unified locations.

Grain:
One row per (source_system, source_location_id).

Primary Key:
- mapping_id

Columns:
- mapping_id (SERIAL)
- unified_location_id (INTEGER)
- source_system (VARCHAR): toast | doordash | square
- source_location_id (VARCHAR)
- created_at (TIMESTAMP)

Used For:
- ETL pipelines
- Debugging ingestion issues

LLM RULE:
Never use this table for analytics or reporting.

====================================================================
TABLE: unified_categories
====================================================================

Purpose:
Normalized, emoji-free product categories.

Grain:
One row per category.

Primary Key:
- category_id

Columns:
- category_id (SERIAL)
- category_name (VARCHAR): Canonical category
- display_name (VARCHAR): Original category name
- parent_category_id (INTEGER)
- created_at (TIMESTAMP)

Used For:
- Category-level rollups
- Menu structure analysis

====================================================================
TABLE: unified_products
====================================================================

Purpose:
Canonical menu product definitions.

Grain:
One row per unique product.

Primary Key:
- product_id

Columns:
- product_id (SERIAL)
- product_code (VARCHAR): Standardized identifier
- product_name (VARCHAR)
- normalized_name (VARCHAR): Cleaned name
- category_id (INTEGER)
- description (TEXT)
- is_alcohol (BOOLEAN)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

Used For:
- Product-level analytics
- Menu optimization

Join Rules:
- unified_order_items.unified_product_id → unified_products.product_id

====================================================================
TABLE: product_name_mapping
====================================================================

Purpose:
Maps source-specific product names to unified products.

Grain:
One row per source product → unified product mapping.

Primary Key:
- mapping_id

Columns:
- mapping_id (SERIAL)
- unified_product_id (INTEGER)
- source_system (VARCHAR)
- source_product_name (VARCHAR)
- source_item_id (VARCHAR)
- confidence_score (DECIMAL): 0.0–1.0
- created_at (TIMESTAMP)

Used For:
- Debugging product matching
- Data quality analysis

LLM RULE:
Do not use for revenue, quantity, or sales metrics.

====================================================================
TABLE: unified_orders
====================================================================

Purpose:
Canonical order-level fact table.

Grain:
One row per order.

Primary Key:
- order_id

Columns:
- order_id (SERIAL)
- unified_location_id (INTEGER)
- source_system (VARCHAR)
- source_order_id (VARCHAR)
- external_order_id (VARCHAR)

Timing:
- order_date (DATE)
- order_timestamp (TIMESTAMP)
- closed_timestamp (TIMESTAMP)
- paid_timestamp (TIMESTAMP)

Order Metadata:
- order_type (VARCHAR): DINE_IN | TAKE_OUT | DELIVERY | PICKUP
- source_type (VARCHAR): POS | ONLINE | THIRD_PARTY

Financials (CENTS):
- subtotal_cents
- tax_cents
- tip_cents
- service_fee_cents
- delivery_fee_cents
- discount_cents
- total_cents
- commission_cents
- merchant_payout_cents

Status:
- status (VARCHAR): COMPLETED | CANCELLED | REFUNDED
- voided (BOOLEAN)

Other:
- server_name (VARCHAR)
- customer_name (VARCHAR)
- notes (TEXT)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

MANDATORY FILTER:
WHERE voided = FALSE

Used For:
- Revenue
- Order counts
- Time-based analysis

Join Rules:
- unified_orders.unified_location_id → unified_locations.location_id

====================================================================
TABLE: unified_order_items
====================================================================

Purpose:
Line-item details for orders.

Grain:
One row per product per order.

Primary Key:
- order_item_id

Columns:
- order_item_id (SERIAL)
- order_id (INTEGER)
- unified_product_id (INTEGER, nullable)
- source_item_id (VARCHAR)

Product Info:
- product_name (VARCHAR)
- normalized_product_name (VARCHAR)
- category_name (VARCHAR)

Pricing (CENTS):
- quantity (INTEGER)
- unit_price_cents
- total_price_cents
- tax_cents

Other:
- special_instructions (TEXT)
- source_system (VARCHAR)
- match_confidence (DECIMAL)
- created_at (TIMESTAMP)

Used For:
- Product performance
- Category analytics
- Item-level reporting

Join Rules:
- unified_order_items.order_id → unified_orders.order_id

====================================================================
TABLE: unified_order_item_modifiers
====================================================================

Purpose:
Captures item modifiers and add-ons.

Grain:
One row per modifier per order item.

Primary Key:
- modifier_id

Columns:
- modifier_id (SERIAL)
- order_item_id (INTEGER)
- modifier_name (VARCHAR)
- price_cents (BIGINT)
- created_at (TIMESTAMP)

Used For:
- Modifier revenue
- Customization analysis

LLM RULE:
Do not assume modifiers exist for all items.

====================================================================
TABLE: unified_payments
====================================================================

Purpose:
Payment transaction records.

Grain:
One row per payment transaction.

Primary Key:
- payment_id

Columns:
- payment_id (SERIAL)
- order_id (INTEGER)
- source_system (VARCHAR)
- source_payment_id (VARCHAR)

Timing:
- payment_timestamp (TIMESTAMP)
- payment_date (DATE)

Payment Details:
- payment_type (VARCHAR): CREDIT | DEBIT | CASH | WALLET | OTHER
- card_brand (VARCHAR)
- card_last_4 (VARCHAR)
- wallet_type (VARCHAR)

Amounts (CENTS):
- amount_cents
- tip_cents
- processing_fee_cents

Status:
- status (VARCHAR)
- refund_status (VARCHAR)

Used For:
- Payment method analysis
- Tip reporting
- Fee reconciliation

Join Rules:
- unified_payments.order_id → unified_orders.order_id
