-- fct_potion_run must be unique on run / player / potion.
select run_id, player_id, potion_id, count(*) as n
from {{ ref('fct_potion_run') }}
group by 1, 2, 3
having count(*) > 1
