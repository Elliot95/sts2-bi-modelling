-- fct_combat must be unique on run / player / floor / room.
select run_id, player_id, floor_number, room_index, count(*) as n
from {{ ref('fct_combat') }}
group by 1, 2, 3, 4
having count(*) > 1
