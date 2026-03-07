-- stg_orders: clean column names + light casts from Gold
-- Nothing is dropped here — staging is a transparent rename layer

with source as (
    select * from {{ source('gold', 'gold_orders') }}
),

renamed as (
    select
        -- Identity
        order_id,
        customer_id,
        customer_unique_id,

        -- Timestamps
        order_purchase_timestamp,
        cast(purchase_year  as integer) as purchase_year,
        cast(purchase_month as integer) as purchase_month,
        cast(purchase_dow   as integer) as purchase_dow,
        cast(purchase_hour  as integer) as purchase_hour,
        purchase_ym,

        -- Delivery
        cast(estimated_days as integer) as estimated_days,
        cast(actual_days    as integer) as actual_days,
        cast(delay_days     as integer) as delay_days,
        cast(is_late        as boolean) as is_late,

        -- Financials
        cast(total_price         as decimal(12, 2)) as total_price,
        cast(total_freight       as decimal(12, 2)) as total_freight,
        cast(payment_value       as decimal(12, 2)) as payment_value,
        cast(freight_ratio       as decimal(6,  4)) as freight_ratio,
        cast(max_installments    as integer)         as max_installments,
        main_payment_type,

        -- Items
        cast(item_count          as integer) as item_count,
        cast(distinct_sellers    as integer) as distinct_sellers,
        cast(distinct_products   as integer) as distinct_products,
        cast(avg_product_weight_g as decimal(10, 2)) as avg_product_weight_g,
        main_category,

        -- Review
        cast(review_score as integer) as review_score,
        review_sentiment,

        -- Geography
        customer_state,
        customer_region,
        customer_city

    from source
    where order_id is not null
)

select * from renamed
