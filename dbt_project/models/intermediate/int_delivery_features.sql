-- int_delivery_features: all features used by the XGBoost delivery delay model.
-- Includes seller reliability signals joined at order time.
-- Used by: fct_delivery_performance, ML training notebook

with orders as (
    select * from {{ ref('stg_orders') }}
),

sellers as (
    select
        seller_id,
        seller_state,
        seller_tier,
        late_rate                                   as seller_late_rate,
        avg_delay_days                              as seller_avg_delay,
        avg_review_score                            as seller_avg_review,
        total_orders                                as seller_total_orders
    from {{ ref('stg_sellers') }}
),

-- Seller id isn't in gold_orders (aggregated away), so we approximate
-- seller signals using customer_state as a proxy for the distribution.
-- In prod this would be enriched with a seller lookup.
state_seller_agg as (
    select
        seller_state,
        avg(seller_late_rate)                       as state_avg_seller_late_rate,
        avg(seller_avg_delay)                       as state_avg_seller_delay,
        count(seller_id)                            as state_seller_count
    from sellers
    group by 1
),

features as (
    select
        o.order_id,
        o.customer_unique_id,
        o.order_purchase_timestamp,

        -- Temporal features
        o.purchase_year,
        o.purchase_month,
        o.purchase_dow,
        o.purchase_hour,

        -- Is this a holiday period? (Brazilian Q4 + Black Friday peak)
        case
            when o.purchase_month in (11, 12)   then 1
            else 0
        end                                         as is_peak_season,

        case
            when o.purchase_dow in (6, 7)        then 1
            else 0
        end                                         as is_weekend_purchase,

        -- Order characteristics
        o.item_count,
        o.total_price,
        o.total_freight,
        o.freight_ratio,
        o.max_installments,
        o.estimated_days,
        o.distinct_sellers,
        o.avg_product_weight_g,
        o.main_category,
        o.main_payment_type,

        -- Geography
        o.customer_state,
        o.customer_region,

        -- State-level seller reliability (proxy)
        coalesce(ssa.state_avg_seller_late_rate, 0) as state_seller_late_rate,
        coalesce(ssa.state_avg_seller_delay, 0)     as state_seller_avg_delay,
        coalesce(ssa.state_seller_count, 0)         as state_seller_count,

        -- Target
        o.is_late,
        o.delay_days

    from orders o
    left join state_seller_agg ssa
        on o.customer_state = ssa.seller_state
)

select * from features
