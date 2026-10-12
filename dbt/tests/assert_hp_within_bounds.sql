{{ config(severity='warn') }}
-- HP should sit in [0, max_hp]. Warn rather than fail until we know whether
-- the game ever legitimately records over-max HP (e.g. mid-event snapshots).
select run_id, floor_number, player_id, current_hp, max_hp
from {{ ref('fct_floor_state') }}
where current_hp < 0
   or current_hp > max_hp
