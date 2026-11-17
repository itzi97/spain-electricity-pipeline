-- One row per technology per day, renamed and typed. Includes REE's own
-- "Total generation" row, flagged with is_reported_total, so marts can
-- reconcile against it.

select
    technology_id,
    technology                                  as technology_name,
    renewable_class,
    renewable_class = 'total'                   as is_reported_total,
    day                                         as generation_day,
    mwh::numeric(14, 3)                         as net_generation_mwh,
    share::numeric(12, 10)                      as share_of_total,
    api_last_update,
    updated_at                                  as loaded_at
from {{ source('raw', 'ree_generation_daily') }}
