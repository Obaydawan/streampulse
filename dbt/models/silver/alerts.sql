-- Alerts: unified anomaly + data-quality view for the dashboard.
-- Three sources, unioned into one structured table:
--   1. data_quality   — rejected events from Phase 2 (schema/validation failures)
--   2. high_value_order — order total far above its region's average
--   3. region_spike   — a region with a disproportionately high order count

with quality_alerts as (

    select
        'DQ-' || row_number() over (order by rejected_at) as alert_id,
        rejected_at as alert_timestamp,
        'warning' as severity,
        coalesce(json_extract_string(raw_value, '$.region'), 'unknown') as region,
        'data_quality' as alert_type,
        reason
    from rejected_events

),

high_value_alerts as (

    select
        'HV-' || o.order_id as alert_id,
        o.event_timestamp as alert_timestamp,
        'info' as severity,
        o.region,
        'high_value_order' as alert_type,
        'Order total $' || o.order_total || ' exceeds 3x regional average' as reason
    from {{ ref('silver_orders') }} o
    where o.order_total > (
        select avg(o2.order_total) * 3
        from {{ ref('silver_orders') }} o2
        where o2.region = o.region
    )

),

region_counts as (

    select region, count(*) as order_count
    from {{ ref('silver_orders') }}
    group by region

),

region_spike_alerts as (

    select
        'RS-' || rc.region as alert_id,
        current_timestamp as alert_timestamp,
        'warning' as severity,
        rc.region,
        'region_spike' as alert_type,
        'Region order count (' || rc.order_count ||
            ') exceeds 1.5x the average region count (' ||
            round(avg_all.avg_count, 1) || ')' as reason
    from region_counts rc
    cross join (select avg(order_count) as avg_count from region_counts) avg_all
    where rc.order_count > avg_all.avg_count * 1.5

)

select * from quality_alerts
union all
select * from high_value_alerts
union all
select * from region_spike_alerts
order by alert_timestamp desc
