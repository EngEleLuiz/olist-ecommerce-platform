-- fct_revenue: monthly GMV and revenue metrics.
-- Primary table for the Revenue dashboard page.
-- Grain: purchase_ym × customer_state

with monthly as (
    select * from {{ ref('stg_kpi_monthly') }}
),

state_metrics as (
    select * from {{ ref('int_state_metrics') }}
),

enriched as (
    select
        m.purchase_ym,
        m.customer_state,
        m.customer_region,

        -- Volume
        m.order_count,
        m.unique_customers,
        m.total_items_sold,

        -- Revenue
        m.gmv,
        m.avg_order_value,

        -- Growth
        m.gmv_mom_growth,

        -- Quality
        m.avg_review_score,
        m.late_rate,
        m.avg_delay_days,
        m.avg_freight_ratio,

        -- State context
        s.gmv_rank,
        s.gmv_share_pct,
        s.total_gmv                                 as state_all_time_gmv,

        -- Revenue per customer (current month)
        case
            when m.unique_customers > 0
            then m.gmv / m.unique_customers
            else 0
        end                                         as revenue_per_customer,

        -- Freight as % of GMV
        round(m.avg_freight_ratio * 100, 2)         as freight_pct_of_gmv

    from monthly m
    left join state_metrics s using (customer_state)
)

select * from enriched
order by purchase_ym desc, gmv desc
