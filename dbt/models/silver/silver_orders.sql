-- Silver: business-ready order data with derived fields.
-- This is what the Alerts panel and dashboard will query from.

select
    order_id,
    customer_id,
    product_id,
    product_name,
    region,
    unit_price,
    quantity,
    round(unit_price * quantity, 2) as order_total,
    event_timestamp,
    ingested_at
from {{ ref('stg_orders') }}
