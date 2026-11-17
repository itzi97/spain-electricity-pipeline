select
    technology_id,
    technology          as technology_name,
    technology_group,
    is_renewable
from {{ ref('technology_groups') }}
where technology_group <> 'total'
