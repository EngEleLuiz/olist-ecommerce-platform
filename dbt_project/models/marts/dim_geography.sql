-- dim_geography: Brazilian state dimension enriched with market metrics.
-- Drives map visualisations and regional drill-downs in the dashboard.
-- Grain: customer_state

with state_metrics as (
    select * from {{ ref('int_state_metrics') }}
),

-- Brazilian state metadata seed (capital cities, coordinates for maps)
states as (
    select * from {{ ref('br_states') }}
)

select
    sm.customer_state                               as state_code,
    sm.customer_region                              as region,
    s.state_name,
    s.capital,
    s.lat,
    s.lng,

    -- Market size
    sm.total_orders,
    sm.total_gmv,
    sm.total_unique_customers,
    sm.avg_order_value,

    -- Rankings
    sm.gmv_rank,
    sm.volume_rank,
    sm.reliability_rank,
    sm.satisfaction_rank,
    sm.gmv_share_pct,

    -- Quality
    sm.avg_late_rate,
    sm.avg_review_score,
    sm.avg_freight_ratio,
    sm.avg_mom_growth,

    -- Activity window
    sm.first_active_ym,
    sm.last_active_ym,
    sm.active_months

from state_metrics sm
left join states s on sm.customer_state = s.state_code
