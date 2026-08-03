-- Staging: light cleaning/typing pass over the raw bronze table.
-- No business logic here — just consistent naming and types.

select
    order_id,
    customer_id,
    product_id,
    product_name,
    region,
    cast(price as decimal(10,2)) as unit_price,
    cast(quantity as integer) as quantity,
    event_timestamp,
    ingested_at
from bronze_orders
