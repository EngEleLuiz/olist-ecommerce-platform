-- CSV bulk-load helpers (run manually after first docker compose up)
--
-- These statements use PostgreSQL COPY which reads files from inside the
-- container. The easiest workflow is to use pgAdmin's Import/Export tool
-- (right-click table → Import/Export) or psql \copy from your host:
--
--   psql -h localhost -U olist -d olist -c \
--     "\copy raw.orders FROM 'data/olist_orders_dataset.csv' CSV HEADER"
--
-- The tables below are created on-demand so you can query raw data
-- in pgAdmin alongside your dbt mart tables.

-- ── Raw orders ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.orders (
    order_id                        TEXT PRIMARY KEY,
    customer_id                     TEXT,
    order_status                    TEXT,
    order_purchase_timestamp        TIMESTAMPTZ,
    order_approved_at               TIMESTAMPTZ,
    order_delivered_carrier_date    TIMESTAMPTZ,
    order_delivered_customer_date   TIMESTAMPTZ,
    order_estimated_delivery_date   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS raw.order_items (
    order_id            TEXT,
    order_item_id       INTEGER,
    product_id          TEXT,
    seller_id           TEXT,
    shipping_limit_date TIMESTAMPTZ,
    price               NUMERIC(10,2),
    freight_value       NUMERIC(10,2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS raw.order_payments (
    order_id                TEXT,
    payment_sequential      INTEGER,
    payment_type            TEXT,
    payment_installments    INTEGER,
    payment_value           NUMERIC(10,2),
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE IF NOT EXISTS raw.order_reviews (
    review_id               TEXT PRIMARY KEY,
    order_id                TEXT,
    review_score            SMALLINT,
    review_comment_title    TEXT,
    review_comment_message  TEXT,
    review_creation_date    TIMESTAMPTZ,
    review_answer_timestamp TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS raw.customers (
    customer_id                 TEXT PRIMARY KEY,
    customer_unique_id          TEXT,
    customer_zip_code_prefix    TEXT,
    customer_city               TEXT,
    customer_state              CHAR(2)
);

CREATE TABLE IF NOT EXISTS raw.sellers (
    seller_id                   TEXT PRIMARY KEY,
    seller_zip_code_prefix      TEXT,
    seller_city                 TEXT,
    seller_state                CHAR(2)
);

CREATE TABLE IF NOT EXISTS raw.products (
    product_id                  TEXT PRIMARY KEY,
    product_category_name       TEXT,
    product_name_length         INTEGER,
    product_description_length  INTEGER,
    product_photos_qty          INTEGER,
    product_weight_g            NUMERIC(10,2),
    product_length_cm           NUMERIC(10,2),
    product_height_cm           NUMERIC(10,2),
    product_width_cm            NUMERIC(10,2)
);

CREATE TABLE IF NOT EXISTS raw.product_category_translation (
    product_category_name           TEXT PRIMARY KEY,
    product_category_name_english   TEXT
);

CREATE TABLE IF NOT EXISTS raw.geolocation (
    geolocation_zip_code_prefix TEXT,
    geolocation_lat             NUMERIC(10,6),
    geolocation_lng             NUMERIC(10,6),
    geolocation_city            TEXT,
    geolocation_state           CHAR(2)
);

-- Quick-load shortcut — run this block in pgAdmin Query Tool after mounting
-- the project folder, adjusting the path to your actual data/ location.
-- Example (run from psql, not pgAdmin):
--
-- \copy raw.orders                     FROM '/path/to/data/olist_orders_dataset.csv'                   CSV HEADER
-- \copy raw.order_items                FROM '/path/to/data/olist_order_items_dataset.csv'              CSV HEADER
-- \copy raw.order_payments             FROM '/path/to/data/olist_order_payments_dataset.csv'           CSV HEADER
-- \copy raw.order_reviews              FROM '/path/to/data/olist_order_reviews_dataset.csv'            CSV HEADER
-- \copy raw.customers                  FROM '/path/to/data/olist_customers_dataset.csv'                CSV HEADER
-- \copy raw.sellers                    FROM '/path/to/data/olist_sellers_dataset.csv'                  CSV HEADER
-- \copy raw.products                   FROM '/path/to/data/olist_products_dataset.csv'                 CSV HEADER
-- \copy raw.product_category_translation FROM '/path/to/data/product_category_name_translation.csv'   CSV HEADER
-- \copy raw.geolocation                FROM '/path/to/data/olist_geolocation_dataset.csv'              CSV HEADER
