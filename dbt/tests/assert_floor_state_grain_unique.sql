-- fct_floor_state must be unique on its grain (run / floor / player).
-- A duplicate here would double-count HP/gold in every floor-level visual.
select run_id, floor_number, player_id, count(*) as n
from {{ ref('fct_floor_state') }}
group by run_id, floor_number, player_id
having count(*) > 1
