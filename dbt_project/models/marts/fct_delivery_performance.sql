-- fct_delivery_performance: delivery KPIs by state, category and month.
-- Used by the Delivery Performance dashboard page and the delay model eval.
-- Grain: purchase_ym × customer_state × main_category

with orders as (
    select * from {{ ref('stg_orders') }}
),

agg as (
    select
        purchase_ym,
        customer_state,
        customer_region,
        main_category,

        count(order_id)                             as order_count,
        avg(cast(is_late as integer))               as late_rate,
        avg(delay_days)                             as avg_delay_days,
        max(delay_days)                             as max_delay_days,
        percentile_cont(0.5) within group
            (order by delay_days)                   as median_delay_days,
        percentile_cont(0.95) within group
            (order by delay_days)                   as p95_delay_days,
        avg(estimated_days)                         as avg_estimated_days,
        avg(actual_days)                            as avg_actual_days,
        avg(review_score)                           as avg_review_score,

        -- SLA bands
        sum(case when delay_days = 0   then 1 else 0 end) as on_time_count,
        sum(case when delay_days between 1 and 3
                                       then 1 else 0 end) as minor_delay_count,
        sum(case when delay_days between 4 and 7
                                       then 1 else 0 end) as moderate_delay_count,
        sum(case when delay_days > 7   then 1 else 0 end) as severe_delay_count

    from orders
    group by 1, 2, 3, 4
),

with_pcts as (
    select
        *,
        round(100.0 * on_time_count     / nullif(order_count, 0), 2) as on_time_pct,
        round(100.0 * minor_delay_count / nullif(order_count, 0), 2) as minor_delay_pct,
        round(100.0 * severe_delay_count/ nullif(order_count, 0), 2) as severe_delay_pct
    from agg
)

select * from with_pcts
order by purchase_ym desc, late_rate desc
