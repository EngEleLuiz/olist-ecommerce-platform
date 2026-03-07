-- fct_orders: main order fact table.
-- One row per delivered order, ready for BI and ad-hoc analysis.
-- Grain: order_id

with orders as (
    select * from {{ ref('stg_orders') }}
),

delivery as (
    select
        order_id,
        is_peak_season,
        is_weekend_purchase,
        state_seller_late_rate
    from {{ ref('int_delivery_features') }}
)

select
    o.order_id,
    o.customer_unique_id,
    o.order_purchase_timestamp,
    o.purchase_ym,
    o.purchase_year,
    o.purchase_month,
    o.purchase_dow,
    o.purchase_hour,

    -- Geography
    o.customer_state,
    o.customer_region,
    o.customer_city,

    -- Financials
    o.payment_value,
    o.total_price,
    o.total_freight,
    o.freight_ratio,
    o.max_installments,
    o.main_payment_type,

    -- Items
    o.item_count,
    o.distinct_sellers,
    o.distinct_products,
    o.main_category,

    -- Delivery
    o.estimated_days,
    o.actual_days,
    o.delay_days,
    o.is_late,

    -- Satisfaction
    o.review_score,
    o.review_sentiment,

    -- Contextual flags from delivery features
    d.is_peak_season,
    d.is_weekend_purchase

from orders o
left join delivery d using (order_id)
