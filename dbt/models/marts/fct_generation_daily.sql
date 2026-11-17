-- Daily net generation per technology, without REE's total row.

select
    g.generation_day,
    g.technology_id,
    t.technology_group,
    t.is_renewable,
    g.net_generation_mwh,
    g.share_of_total
from {{ ref('stg_ree__generation_daily') }} as g
join {{ ref('dim_technology') }} as t using (technology_id)
where not g.is_reported_total
