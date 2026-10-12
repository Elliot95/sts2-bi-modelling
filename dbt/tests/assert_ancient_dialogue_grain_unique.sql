-- dim_ancient_dialogue must be unique on Ancient / character / conversation / line.
select event_id, character, conversation, line, count(*) as n
from {{ ref('dim_ancient_dialogue') }}
group by 1, 2, 3, 4
having count(*) > 1
