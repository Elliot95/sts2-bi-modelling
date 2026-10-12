-- fct_event_choice must be unique on run / player / floor / choice_index.
select run_id, player_id, floor_number, choice_index, count(*) as n
from {{ ref('fct_event_choice') }}
group by 1, 2, 3, 4
having count(*) > 1
