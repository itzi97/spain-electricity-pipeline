-- One row per day: how much Spain generated, and how much of it was renewable.
-- The 7-day figure is a ratio of sums, not an average of daily ratios, so a
-- windy low-demand Sunday does not count as much as a busy Tuesday.

with daily as (
    select
        generation_day,
        sum(net_generation_mwh)                                             as total_mwh,
        sum(net_generation_mwh) filter (where is_renewable)                 as renewable_mwh,
        sum(net_generation_mwh) filter (where technology_group = 'wind')    as wind_mwh,
        sum(net_generation_mwh) filter (where technology_group = 'solar')   as solar_mwh,
        sum(net_generation_mwh) filter (where technology_group = 'hydro')   as hydro_mwh,
        sum(net_generation_mwh) filter (where technology_group = 'nuclear') as nuclear_mwh,
        sum(net_generation_mwh) filter (where technology_group = 'combined_cycle') as combined_cycle_mwh
    from {{ ref('fct_generation_daily') }}
    group by generation_day
),

top_technology as (
    select distinct on (f.generation_day)
        f.generation_day,
        d.technology_name as top_technology
    from {{ ref('fct_generation_daily') }} as f
    join {{ ref('dim_technology') }} as d using (technology_id)
    order by f.generation_day, f.net_generation_mwh desc
)

select
    daily.generation_day,
    round(daily.total_mwh, 3)                                       as total_mwh,
    round(daily.renewable_mwh, 3)                                   as renewable_mwh,
    round(daily.renewable_mwh / nullif(daily.total_mwh, 0), 4)      as renewable_share,
    round(
        sum(daily.renewable_mwh) over last_7_days
        / nullif(sum(daily.total_mwh) over last_7_days, 0),
        4
    )                                                               as renewable_share_7d,
    round(coalesce(daily.wind_mwh, 0), 3)                           as wind_mwh,
    round(coalesce(daily.solar_mwh, 0), 3)                          as solar_mwh,
    round(coalesce(daily.hydro_mwh, 0), 3)                          as hydro_mwh,
    round(coalesce(daily.nuclear_mwh, 0), 3)                        as nuclear_mwh,
    round(coalesce(daily.combined_cycle_mwh, 0), 3)                 as combined_cycle_mwh,
    top_technology.top_technology
from daily
join top_technology using (generation_day)
window last_7_days as (order by daily.generation_day rows between 6 preceding and current row)
