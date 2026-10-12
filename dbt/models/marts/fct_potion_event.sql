-- Grain: one row per potion per action on a floor (run / player / floor /
-- potion / action). For "when do I use potions?" by floor and act.
select
    run_id,
    player_id,
    floor_number,
    act_index + 1   as act,
    potion_id,
    action,
    was_picked
from {{ ref('stg_sts2__potion_events') }}
