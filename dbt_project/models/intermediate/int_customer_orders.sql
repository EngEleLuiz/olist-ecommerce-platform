-- int_customer_orders: aggregates all orders per customer.
-- Used by: fct_customer_ltv, fct_rfm, dim_customers

with orders as (
    select * from {{ ref('stg_orders') }}
),

customer_agg as (
    select
        customer_unique_id,
        customer_state,
        customer_region,
        customer_city,

        -- Volume
        count(order_id)                             as total_orders,
        sum(payment_value)                          as total_spend,
        avg(payment_value)                          as avg_order_value,
        sum(item_count)                             as total_items,

        -- First / last purchase
        min(order_purchase_timestamp)               as first_purchase_at,
        max(order_purchase_timestamp)               as last_purchase_at,

        -- Recency (days since last purchase — relative to dataset max date)
        datediff(
            'day',
            max(order_purchase_timestamp),
            (select max(order_purchase_timestamp) from {{ ref('stg_orders') }})
        )                                           as recency_days,

        -- Customer lifespan in days
        datediff(
            'day',
            min(order_purchase_timestamp),
            (select max(order_purchase_timestamp) from {{ ref('stg_orders') }})
        )                                           as T_days,

        -- Quality signals
        avg(review_score)                           as avg_review_score,
        avg(cast(is_late as integer))               as late_order_rate,
        avg(delay_days)                             as avg_delay_days,

        -- Behaviour
        avg(freight_ratio)                          as avg_freight_ratio,
        avg(max_installments)                       as avg_installments,
        mode() within group (order by main_payment_type)  as preferred_payment,
        mode() within group (order by main_category)      as preferred_category

    from orders
    group by 1, 2, 3, 4
),

with_repeat as (
    select
        *,
        -- BG/NBD requires repeat purchases (total - 1, floored at 0)
        greatest(total_orders - 1, 0)              as repeat_purchases,
        -- Flag multi-purchase customers
        (total_orders > 1)                         as is_repeat_customer
    from customer_agg
)

select * from with_repeat
