-- Every calendar day between the first and last loaded day should be present.
-- A gap means a failed or partial load, and the 7-day share would quietly
-- average over fewer days.

with bounds as (
    select min(generation_day) as first_day, max(generation_day) as last_day
    from {{ ref('mart_daily_mix') }}
),

calendar as (
    select generate_series(first_day, last_day, interval '1 day')::date as generation_day
    from bounds
)

select calendar.generation_day as missing_day
from calendar
left join {{ ref('mart_daily_mix') }} as mix using (generation_day)
where mix.generation_day is null
