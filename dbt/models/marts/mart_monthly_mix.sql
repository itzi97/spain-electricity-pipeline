-- Net generation per month and technology group, with each group's share of the month.

with monthly as (
    select
        date_trunc('month', generation_day)::date  as month,
        technology_group,
        bool_or(is_renewable)                      as is_renewable,
        count(distinct generation_day)             as days_with_data,
        sum(net_generation_mwh)                    as net_generation_mwh
    from {{ ref('fct_generation_daily') }}
    group by 1, 2
)

select
    month,
    technology_group,
    is_renewable,
    days_with_data,
    round(net_generation_mwh, 3)                                                    as net_generation_mwh,
    round(net_generation_mwh / sum(net_generation_mwh) over (partition by month), 4) as share_of_month
from monthly
