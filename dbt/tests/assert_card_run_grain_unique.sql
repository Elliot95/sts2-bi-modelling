-- fct_card_run must be unique on its grain (run / player / card).
select run_id, player_id, card_id, count(*) as n
from {{ ref('fct_card_run') }}
group by run_id, player_id, card_id
having count(*) > 1
