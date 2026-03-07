-- fct_customer_ltv: customer LTV and RFM segmentation.
-- The ML-predicted LTV (BG/NBD + Gamma-Gamma) is joined here from the
-- ml_predictions seed after the nightly model run writes its outputs.
-- Grain: customer_unique_id

with customers as (
    select * from {{ ref('int_customer_orders') }}
),

-- LTV predictions are written by the ML pipeline as a CSV seed
-- and refreshed daily. Falls back to spend-based LTV estimate if missing.
ltv_preds as (
    select * from {{ ref('ltv_predictions') }}
),

rfm as (
    select
        customer_unique_id,
        customer_state,
        customer_region,
        customer_city,

        -- RFM raw values
        total_orders                                as frequency,
        repeat_purchases,
        recency_days,
        T_days,
        total_spend,
        avg_order_value,

        -- RFM scores (1-5 quintile buckets)
        ntile(5) over (order by recency_days asc)   as recency_score,
        ntile(5) over (order by total_orders desc)  as frequency_score,
        ntile(5) over (order by total_spend desc)   as monetary_score,

        -- Behaviour
        preferred_category,
        preferred_payment,
        avg_installments,
        avg_freight_ratio,
        late_order_rate,
        avg_review_score,
        is_repeat_customer,

        first_purchase_at,
        last_purchase_at

    from customers
),

scored as (
    select
        r.*,
        coalesce(l.predicted_ltv_90d,  r.avg_order_value * 1.0) as predicted_ltv_90d,
        coalesce(l.predicted_ltv_365d, r.avg_order_value * 2.5) as predicted_ltv_365d,
        coalesce(l.predicted_purchases_90d, 0)                   as predicted_purchases_90d,

        -- RFM composite score
        (r.recency_score + r.frequency_score + r.monetary_score) as rfm_total,

        -- Segment
        case
            when r.recency_score >= 4 and r.frequency_score >= 4
                then 'Champions'
            when r.recency_score >= 3 and r.frequency_score >= 3
                then 'Loyal'
            when r.recency_score >= 4 and r.frequency_score <= 2
                then 'New Customers'
            when r.recency_score <= 2 and r.frequency_score >= 3
                then 'At Risk'
            when r.recency_score <= 2 and r.frequency_score <= 2
                then 'Lost'
            else 'Potential Loyalists'
        end                                                       as rfm_segment

    from rfm r
    left join ltv_preds l using (customer_unique_id)
)

select * from scored
