-- REE publishes its own total for each day. If the technologies we keep do not
-- add up to it, a technology has gone missing from the mapping or the load.
-- Tolerance: 0.1% of the day's total.

with ours as (
    select generation_day, sum(net_generation_mwh) as summed_mwh
    from {{ ref('fct_generation_daily') }}
    group by generation_day
),

theirs as (
    select generation_day, net_generation_mwh as reported_mwh
    from {{ ref('stg_ree__generation_daily') }}
    where is_reported_total
)

select
    theirs.generation_day,
    theirs.reported_mwh,
    ours.summed_mwh
from theirs
left join ours using (generation_day)
where ours.summed_mwh is null
   or abs(ours.summed_mwh - theirs.reported_mwh) > 0.001 * theirs.reported_mwh
